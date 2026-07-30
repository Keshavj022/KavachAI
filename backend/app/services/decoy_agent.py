"""Decoy agent orchestrator — the conversation loop.

For each caller utterance it, in order:
  1. records the caller turn and extracts + accumulates intelligence,
  2. runs the local trained detector (classifier + arc tracker) to update the
     deterministic scam probability and arc stage,
  3. cross-references extracted identifiers against the known-fraud graph,
  4. decides the agent mode (MONITOR / STALL / WRAP_UP) deterministically,
  5. asks Ollama for Ramesh's next line (persona-locked, caller's language,
     4-second timeout → in-character fallback),
  6. synthesizes the reply with local TTS (or a pre-cached / text fallback).

Detection and the mode decision are deterministic and never delegated to the
LLM. The LLM authors only Ramesh's conversational line. Everything is local —
no network call leaves the machine in this loop.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.enums import STAGE_ORDER, ScamStage
from app.services import persona, text_llm, tts_service
from app.services.call_detector import detect
from app.services.decoy_session import DecoySession
from app.services.detection_engine import KNOWN_SCAMMER_RISK, known_scammer_lookup
from app.services.extractor import extract_identifiers
from app.services.persona import AgentMode

logger = logging.getLogger("kavach.decoy")

# Short replies keep the decoy terse AND keep TTS synthesis short enough that the
# voice arrives while the call is still live.
_MAX_TOKENS = 40
_TEMPERATURE = 0.7


def _decoy_reply(prompt: str) -> str | None:
    """Ask the active LLM (Groq or Ollama) for the decoy's next line."""
    text = text_llm.generate(prompt=prompt, max_tokens=_MAX_TOKENS,
                             temperature=_TEMPERATURE)
    if not text:
        return None
    # Keep the first line and strip any leaked label/quotes.
    return persona.clean_line(text.split("\n")[0]) or None


def _update_detection(session: DecoySession) -> None:
    """Run the local trained detector over the caller-only transcript."""
    result = detect(session.scammer_transcript)
    session.scam_probability = result.confidence
    session.max_scam_probability = max(session.max_scam_probability, result.confidence)
    # Arc stage is monotonic across the call.
    if STAGE_ORDER[result.stage.value] >= STAGE_ORDER[session.current_stage.value]:
        session.current_stage = result.stage
    session.scam_type = result.scam_type
    for flag in result.red_flags:
        if flag not in session.red_flags:
            session.red_flags.append(flag)


def _graph_cross_reference(session: DecoySession, db: Session, caller_text: str) -> None:
    """Look up freshly seen identifiers in the known-fraud graph.

    A match upgrades scam confidence directly — the network already knows this
    number/UPI/account, so we do not need the model to be sure.
    """
    identifiers = extract_identifiers(caller_text)
    if not identifiers:
        return
    match = known_scammer_lookup(db, identifiers)
    if match is not None and match.risk_score >= KNOWN_SCAMMER_RISK:
        session.known_ring_hit = True
        session.scam_probability = max(session.scam_probability, float(match.risk_score))
        session.max_scam_probability = max(session.max_scam_probability,
                                           float(match.risk_score))
        flag = f"Known reported {match.type}: {match.value}"
        if flag not in session.red_flags:
            session.red_flags.append(flag)


# When the generative fraudster is deterministically walking the arc, the caller
# IS running a confirmed scam of a known shape. These per-stage probability floors
# ensure the guardian interrupt fires at the isolation beat (the emotional peak)
# even if the trained classifier under-scores a particular generated phrasing —
# the classifier still drives the value whenever it scores higher.
_STAGE_PROB_FLOOR: dict[ScamStage, float] = {
    ScamStage.authority_claim: 0.35,
    ScamStage.accusation: 0.60,
    ScamStage.isolation: 0.82,
    ScamStage.money_demand: 0.92,
}


def process_caller_utterance(
    session: DecoySession,
    db: Session,
    caller_text: str,
    language: str,
    override_reply: str | None = None,
    min_stage: ScamStage | None = None,
) -> dict:
    """Advance the decoy one turn. Returns the data the WebSocket streams.

    Synchronous (Ollama + TTS are blocking); call from the loop via
    ``asyncio.to_thread`` so the event loop is never blocked.

    ``override_reply`` supplies Ramesh's line directly (demo mode uses the fixed,
    pre-generated script line so the reply is deterministic and its voice clip is
    cache-served). When None, the line is authored live by the LLM — the
    production / live-mic path.
    """
    detection = process_caller_detection(session, db, caller_text, language, min_stage)
    reply, used_fallback = generate_decoy_reply(
        session, language, session.mode, override_reply
    )
    return {**detection, "agent_text": reply, "agent_audio": None,
            "used_fallback_reply": used_fallback}


def process_caller_detection(
    session: DecoySession,
    db: Session,
    caller_text: str,
    language: str,
    min_stage: ScamStage | None = None,
) -> dict:
    """Record the caller line, run detection + extraction, decide the mode.

    Returns the detection payload (no reply). Split out from the reply so the WS
    can stream the caller's line + detection immediately, then generate + voice
    the decoy's answer while the caller audio plays — keeping the call snappy.
    """
    session.language = language
    session.add_turn("scammer", caller_text, language)

    # Intelligence + detection + graph, all deterministic.
    new_entities = session.ingest_caller_entities(caller_text)
    _graph_cross_reference(session, db, caller_text)
    _update_detection(session)

    # Generative-fraudster mode: the caller is deliberately walking the scam arc,
    # so advance the arc stage to the beat it is playing and floor the scam
    # probability for that beat (both monotonic; the classifier still wins when it
    # scores higher).
    if min_stage is not None:
        if STAGE_ORDER[min_stage.value] > STAGE_ORDER[session.current_stage.value]:
            session.current_stage = min_stage
        floor = _STAGE_PROB_FLOOR.get(min_stage, 0.0)
        session.scam_probability = max(session.scam_probability, floor)
        session.max_scam_probability = max(
            session.max_scam_probability, session.scam_probability
        )

    mode = session.decide_mode()
    return {
        "mode": mode.value,
        "scam_probability": round(session.scam_probability, 4),
        "stage": session.current_stage.value,
        "scam_type": session.scam_type,
        "red_flags": list(session.red_flags),
        "new_identifiers": new_entities,
        "identifiers_total": session.intel.total_identifiers(),
        "known_ring_hit": session.known_ring_hit,
        "interrupt": session.should_interrupt(),
        "wrap_up": mode == AgentMode.wrap_up,
    }


def generate_decoy_reply(
    session: DecoySession, language: str, mode: AgentMode,
    override_reply: str | None = None,
) -> tuple[str, bool]:
    """Author the decoy's next line (LLM, persona-locked; fallback on timeout).

    Returns (reply_text, used_fallback). Appends the reply to the transcript.
    """
    if override_reply is not None and override_reply.strip():
        session.add_turn("agent", override_reply.strip(), language)
        return override_reply.strip(), False
    prompt = persona.build_prompt(
        transcript=session.full_transcript,
        last_caller_utterance=session.turns[-1]["text"] if session.turns else "",
        mode=mode,
        name=session.user_name,
    )
    reply = _decoy_reply(prompt)
    used_fallback = reply is None
    if reply is None:
        reply = persona.fallback_reply(mode, language)
    session.add_turn("agent", reply, language)
    return reply, used_fallback


def synthesize_reply(text: str, language: str, mode_value: str) -> str | None:
    """Blocking TTS for one agent reply. Call from the loop via to_thread.

    Returns a served audio filename or None (text-only). A pre-cached stall clip
    is the fallback when in STALL mode and the live model is unavailable.
    """
    stall_type = "hold_on" if mode_value == AgentMode.stall.value else None
    return tts_service.synthesize(text, language, stall_type=stall_type, mode=mode_value)


def synthesize_caller(text: str, language: str) -> str | None:
    """Blocking TTS for one caller (fraudster) line, in the scammer voice.

    Returns a served audio filename or None (text-only). Call from the loop via
    to_thread so slow synthesis never blocks the event loop.
    """
    return tts_service.synthesize(text, language, role="scammer")


def greeting_line(session: DecoySession) -> dict:
    """Ramesh's opening greeting when the decoy answers the call.

    Returns text only — TTS is NOT run here so ``session/start`` never blocks on
    speech synthesis. The decoy's spoken voice comes through the WebSocket agent
    replies, where TTS runs off the event loop.
    """
    text = persona.greeting(session.language, session.user_name)
    session.add_turn("agent", text, session.language)
    return {"agent_text": text, "agent_audio": None, "mode": "monitor"}

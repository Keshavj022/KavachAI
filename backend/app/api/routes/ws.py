"""Live-call detection websocket.

Client connects to ``/ws/call/{session_id}?token=...`` and runs one of:

  * Scripted Demo mode — the server auto-advances a canned transcript, running
    the real detector on each turn (deterministic, demo-safe).
  * Live mic mode — the client streams short audio chunks (binary frames); the
    server transcribes each LOCALLY with faster-whisper, appends to the rolling
    in-memory transcript, discards the audio, and runs the detector on the
    transcript-so-far.

Detection is done by the few-shot Groq LLM (``services/call_detector``), which
falls back to the local rule-based scorer if Groq is unavailable. The interrupt
decision is made deterministically in ``CallDetectionState`` — not by the LLM.

Privacy: raw audio never leaves the machine. Only transcript text is sent to
the cloud detector, and only in this prototype.
"""

from __future__ import annotations

import asyncio
import json
import logging

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.database import SessionLocal
from app.models.call import CallSession
from app.models.enums import STAGE_ORDER, Verdict
from app.schemas.detection import Source, WSMessage
from app.services import stt
from app.services.call_detector import (
    CallDetectionState,
    DetectionResult,
    de_escalation,
    detect,
)
from app.services.demo_scripts import get_script
from app.services.rag import retrieve_sources

logger = logging.getLogger("kavach.ws")
router = APIRouter(tags=["ws"])

# Delay between scripted utterances in demo mode (seconds) — deterministic
# pacing so the meter climbs visibly during a live demo.
_DEMO_TICK_DELAY = 1.6


class _Stream:
    """Mutable per-connection state shared by the frame helpers."""

    def __init__(self, db, session: CallSession) -> None:
        self.db = db
        self.session = session
        self.state = CallDetectionState()
        self.transcript = ""
        self.max_conf = 0.0
        self.interrupt_sent = False
        self.cached_sources: list[Source] = []
        self.language: str | None = None  # None → Whisper auto-detect


@router.websocket("/ws/call/{session_id}")
async def call_ws(websocket: WebSocket, session_id: int, token: str = "") -> None:
    """Stream live detection for a call session."""
    await websocket.accept()

    user_id = _authenticate(token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        session = db.get(CallSession, session_id)
        if session is None or session.user_id != user_id:
            await websocket.close(code=4404)
            return

        stream = _Stream(db, session)

        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break
            if message.get("type") == "websocket.disconnect":
                break

            # --- Binary frame → an audio chunk (live mic mode). ---
            if message.get("bytes") is not None:
                await _handle_audio_chunk(websocket, stream, message["bytes"])
                continue

            # --- Text frame → a JSON control message. ---
            raw = message.get("text")
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action")
            stream.language = _lang(msg.get("language"))

            if action == "start" and msg.get("mode") == "demo":
                await _run_scripted(websocket, stream, msg.get("script", "digital_arrest"))
                break

            if action == "start" and msg.get("mode") == "live":
                # Nothing to do until audio chunks arrive; acknowledge readiness.
                await websocket.send_json(
                    WSMessage(partial_transcript="", detector="fallback").model_dump()
                )
                continue

            # Back-compat: a client may still push recognized text directly.
            if action == "append":
                text = str(msg.get("text", "")).strip()
                if text:
                    stream.transcript = f"{stream.transcript}\n{text}".strip()
                    frame = await _process(stream)
                    await websocket.send_json(frame.model_dump())
                continue

            if action == "stop":
                await _finish(websocket, stream)
                break

    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("WS error on session %s: %s", session_id, exc)
    finally:
        db.close()


# --------------------------------------------------------------------------
async def _run_scripted(websocket: WebSocket, stream: _Stream, script_id: str) -> None:
    """Feed a canned transcript line by line through the real detector."""
    script = get_script(script_id)
    for line in script.lines:
        stream.transcript = f"{stream.transcript}\n{line}".strip()
        frame = await _process(stream)
        await websocket.send_json(frame.model_dump())
        await asyncio.sleep(_DEMO_TICK_DELAY)
    await _finish(websocket, stream)


async def _handle_audio_chunk(websocket: WebSocket, stream: _Stream, chunk: bytes) -> None:
    """Transcribe one audio chunk locally, append text, run the detector."""
    text = await asyncio.to_thread(stt.transcribe_audio_bytes, chunk, stream.language)
    if not text:
        # STT unavailable or chunk undecodable — keep the call alive silently.
        return
    stream.transcript = f"{stream.transcript}\n{text}".strip()
    frame = await _process(stream)
    await websocket.send_json(frame.model_dump())


def _verdict_for(result: DetectionResult, interrupt: bool) -> Verdict:
    if result.scam_type == "legitimate":
        return Verdict.safe
    if interrupt or result.confidence >= 0.7:
        return Verdict.scam
    if result.confidence >= 0.4:
        return Verdict.suspicious
    return Verdict.safe


async def _process(stream: _Stream, done: bool = False) -> WSMessage:
    """Run detection on the transcript-so-far and build the client frame."""
    # detect() runs the local trained models (no network) in a worker thread so
    # the sklearn call never blocks the event loop.
    result: DetectionResult = await asyncio.to_thread(detect, stream.transcript)
    decision = stream.state.update(result)
    stream.max_conf = max(stream.max_conf, result.confidence)
    verdict = _verdict_for(result, decision.interrupt)

    lang = stream.language or "en"
    explanation: str | None = None
    sources: list[Source] = []
    if decision.interrupt:
        # Pre-written template keyed by the stage reached — never generated.
        explanation = de_escalation(stream.state.highest_stage, lang) or None
        if not stream.interrupt_sent:
            stream.cached_sources = await asyncio.to_thread(
                retrieve_sources, stream.transcript, 1
            )
            stream.interrupt_sent = True
        sources = stream.cached_sources
    elif decision.warn:
        explanation = de_escalation(stream.state.highest_stage, lang) or None

    _persist(stream, result, decision, verdict)

    return WSMessage(
        partial_transcript=stream.transcript,
        stage=result.stage,
        confidence=result.confidence,
        verdict=verdict,
        interrupt=decision.interrupt,
        warn=decision.warn,
        explanation=explanation,
        red_flags=result.red_flags,
        sources=sources,
        known_scammer=False,
        detector=result.source,
        done=done,
    )


def _persist(stream: _Stream, result: DetectionResult, decision, verdict: Verdict) -> None:
    """Persist rolling detection state on the CallSession row."""
    s = stream.session
    s.transcript = stream.transcript
    s.max_confidence = stream.max_conf
    if STAGE_ORDER[result.stage.value] > STAGE_ORDER[s.stage_reached]:
        s.stage_reached = result.stage.value
    s.outcome = verdict.value
    if decision.interrupt:
        s.interrupted = True
    stream.db.commit()


async def _finish(websocket: WebSocket, stream: _Stream) -> None:
    """Send a final frame (done=True) with the current assessment."""
    frame = await _process(stream, done=True)
    try:
        await websocket.send_json(frame.model_dump())
    except Exception:
        pass


def _authenticate(token: str) -> int | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def _lang(value) -> str | None:
    """Normalize a language hint; '' or 'auto' → None (Whisper auto-detect)."""
    if not value or str(value).lower() == "auto":
        return None
    return str(value).lower()

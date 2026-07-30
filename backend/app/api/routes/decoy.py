"""Decoy Agent — REST + WebSocket routes.

The decoy answers a suspicious call on the user's behalf, plays the Ramesh
persona, and streams the live conversation + detection + extracted intelligence
to the frontend. On a confirmed scam it generates an intelligence package.

Real OS/telecom call interception (an AI literally answering a cellular call)
requires Android CallScreeningService or a VoIP middleware layer and is out of
scope for this prototype: the "scammer" audio comes from a demo script (or the
browser mic), and the rest of the pipeline — STT, detection, extraction,
response generation, TTS, packaging — is the real thing. This is stated plainly
and never obscured.

Privacy: the entire decoy loop runs locally. The only network action is the mock
submission to authorities, and only on explicit user confirmation after the call.
"""

from __future__ import annotations

import asyncio
import json
import logging

import jwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.security import decode_access_token
from app.database import SessionLocal, get_db
from app.models.call import CallSession
from app.models.decoy import DecoyPackage
from app.models.enums import Role
from app.models.evidence import Evidence
from app.models.user import User
from app.schemas.decoy import DecoyStartRequest, DecoyStartResponse, SubmitResponse
from app.services import decoy_agent, decoy_session, fraudster, persona, tts_service
from app.services.evidence import decrypt_evidence
from app.services.intelligence_package import generate_package
from app.services.persona import normalize_language

logger = logging.getLogger("kavach.decoy")
router = APIRouter(prefix="/api/decoy", tags=["decoy"])


def _audio_url(filename: str | None) -> str | None:
    if not filename:
        return None
    return f"/api/decoy/audio/{filename}"


# --------------------------------------------------------------------------
# REST
# --------------------------------------------------------------------------
@router.post("/session/start", response_model=DecoyStartResponse,
             status_code=status.HTTP_201_CREATED)
def start_session(
    payload: DecoyStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a decoy call session. Creates the persisted CallSession + live state."""
    cs = CallSession(user_id=current_user.id, outcome="safe")
    db.add(cs)
    db.commit()
    db.refresh(cs)

    lang = normalize_language(payload.language)
    scenario = payload.scenario or _scenario_for(payload.language, lang)
    session = decoy_session.create_session(
        cs.id, current_user.id, language=lang, demo_mode=payload.demo_mode,
        user_name=(current_user.full_name or "").strip(), scenario=scenario,
    )
    # The decoy answers as the real account holder. The greeting text is returned
    # for reference; it is spoken (synthesized LIVE) as the first WebSocket turn,
    # so session/start stays fast and nothing is pre-recorded.
    greeting_text = persona.greeting(lang, session.user_name)
    return DecoyStartResponse(
        session_id=cs.id,
        greeting_text=greeting_text,
        persona_intro_audio_url=None,
        demo_scripts=list(fraudster.SCENARIOS.keys()),
    )


def _scenario_for(raw_language: str | None, lang: str) -> str:
    """Pick a scenario when the client didn't send one (back-compat)."""
    return "tech_support" if (raw_language or lang) == "en" else "digital_arrest"


@router.get("/audio/{filename:path}")
def get_audio(filename: str):
    """Serve a generated / pre-cached TTS clip. Path-traversal guarded."""
    base = tts_service.TTS_CACHE_DIR.resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")
    return FileResponse(target, media_type="audio/wav")


@router.post("/session/{session_id}/end")
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force a graceful wrap-up + package generation if not already ended."""
    session = decoy_session.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    result = _finalize(db, session)
    return {"verdict": session.verdict, "package_id": session.package_id, **result}


@router.get("/package/{package_id}")
def get_package(
    package_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the intelligence package JSON (minus encrypted audio). Owner only.

    Authority users may view any package (for the command-center story).
    """
    row = db.get(DecoyPackage, package_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if row.user_id != current_user.id and current_user.role != Role.authority.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    payload = json.loads(row.package_json)
    payload["submission_id"] = row.submission_id
    payload["submission_status"] = row.submission_status
    return payload


@router.get("/package/{package_id}/evidence")
def get_package_evidence(
    package_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.authority)),
):
    """Decrypted evidence — AUTHORITY ROLE ONLY. Citizens receive 403.

    The citizen the decoy protected can never retrieve the evidence; only an
    authenticated authority user can, mirroring the call-evidence design.
    """
    row = db.get(DecoyPackage, package_id)
    if row is None or row.evidence_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    ev = db.get(Evidence, row.evidence_id)
    if ev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    plaintext = decrypt_evidence(ev)
    return {
        "package_id": package_id,
        "sha256_hash": ev.sha256_hash,
        "created_at": ev.created_at.isoformat(),
        "integrity_verified": plaintext is not None,
        "segment": plaintext,  # transcript segment (audio in production)
        "note": "Prototype preserves the transcript segment; production stores the "
        "encrypted audio segment. Access is restricted to the authority role.",
    }


@router.post("/package/{package_id}/submit", response_model=SubmitResponse)
def submit_package(
    package_id: str,
    channel: str = "1930",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit the package to a MOCK 1930/Chakshu endpoint (clearly a stub).

    In production this posts to the official Chakshu / 1930 intake APIs. Here it
    records a mock submission id so the flow is demonstrable end to end.
    """
    row = db.get(DecoyPackage, package_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    if row.user_id != current_user.id and current_user.role != Role.authority.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    import uuid

    row.submission_id = f"MOCK-{channel.upper()}-{uuid.uuid4().hex[:10].upper()}"
    row.submission_status = "received"
    db.commit()
    logger.info("[MOCK SUBMISSION] package %s → %s (%s)", package_id, channel,
                row.submission_id)
    return SubmitResponse(submission_id=row.submission_id, status="received", channel=channel)


# --------------------------------------------------------------------------
# WebSocket
# --------------------------------------------------------------------------
@router.websocket("/ws/{session_id}")
async def decoy_ws(websocket: WebSocket, session_id: int, token: str = "") -> None:
    """Stream the decoy conversation loop for a session.

    Client → server:
      {"type": "demo_start", "script": "digital_arrest_hi"}   run scripted scam
      {"type": "demo_tick", "text": "..."}                    one caller line
      {"type": "end"}                                         force wrap-up
      binary frame                                            live mic audio chunk
    Server → client: one ``turn`` frame per exchange (caller line + detection +
      agent reply, each with its voice clip), then ``call_ended``. The frontend
      plays the turns back in order so audio and transcript stay in lockstep.
    """
    await websocket.accept()
    user_id = _authenticate(token)
    if user_id is None:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    conn = _Conn(websocket)
    try:
        cs = db.get(CallSession, session_id)
        if cs is None or cs.user_id != user_id:
            await websocket.close(code=4404)
            return
        session = decoy_session.get_session(session_id)
        if session is None:
            session = decoy_session.create_session(session_id, user_id)

        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break
            if message.get("type") == "websocket.disconnect":
                break

            if message.get("bytes") is not None:
                await _handle_audio(conn, db, session, message["bytes"])
                continue

            raw = message.get("text")
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")
            if mtype in ("demo_start", "start"):
                if msg.get("scenario"):
                    session.scenario = msg["scenario"]
                await _run_generative(conn, db, session)
                break
            if mtype == "demo_tick":
                await _advance(conn, db, session, str(msg.get("text", "")),
                               session.language)
                if session.should_wrap_up():
                    await _wrap_and_end(conn, db, session)
                    break
                continue
            if mtype == "end":
                await _wrap_and_end(conn, db, session)
                break
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Decoy WS error on session %s: %s", session_id, exc)
    finally:
        await conn.aclose()
        db.close()


class _Conn:
    """Per-connection context. Serializes sends on one socket.

    Voice is synthesized inline per turn (both the caller and the agent line) and
    shipped with the turn frame, so the frontend can play audio and reveal text
    in lockstep. There are no background senders, so ``send`` is the only writer.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self.ws = websocket
        self._send_lock = asyncio.Lock()   # never interleave two sends

    async def send(self, payload: dict) -> None:
        async with self._send_lock:
            await self.ws.send_json(payload)

    async def aclose(self) -> None:
        # Nothing to drain — synthesis is inline, not backgrounded.
        return


async def _run_generative(conn: "_Conn", db: Session, session) -> None:
    """A live, fully generated scam call — nothing scripted or pre-recorded.

    The local LLM plays the fraudster, walking the scam arc (authority → accusation
    → isolation → money demand); the decoy answers as the account holder. Both
    lines are authored live and synthesized live (bf16 Parler), so every call is
    different. The frontend plays the turns back as a queue so text and the
    confidence meter stay locked to the audio.
    """
    # The decoy picks up first — voiced live as an agent-only turn.
    greeting = persona.greeting(session.language, session.user_name)
    session.add_turn("agent", greeting, session.language)
    greeting_audio = await asyncio.get_running_loop().run_in_executor(
        tts_service.tts_pool, decoy_agent.synthesize_reply, greeting,
        session.language, "monitor"
    )
    await conn.send({
        "type": "turn",
        "scammer": None,
        "detection": None,
        "mode": "monitor",
        "agent": {
            "text": greeting, "language": session.language,
            "audio_url": _audio_url(greeting_audio), "used_fallback": False,
        },
    })

    for turn_idx in range(len(fraudster.ARC)):
        stage = fraudster.stage_for_turn(turn_idx)
        caller_text, _ = await asyncio.to_thread(
            fraudster.next_line,
            scenario=session.scenario,
            stage=stage,
            victim_name=session.user_name or "sir",
            transcript=session.full_transcript,
        )
        await _advance(conn, db, session, caller_text, session.language,
                       forced_stage=stage)
        if session.should_wrap_up():
            break
    await _wrap_and_end(conn, db, session)


async def _advance(conn: "_Conn", db: Session, session, caller_text: str,
                   language: str, agent_override: str | None = None,
                   forced_stage=None) -> None:
    """Process one caller utterance and stream it as TWO pipelined frames.

    The caller's line + detection is sent as soon as the caller voice is
    synthesized, so the frontend can start playing it immediately; the decoy's
    answer is then authored and voiced *while that caller clip plays*, and sent as
    a second frame. This overlap keeps the live call snappy instead of waiting for
    the whole exchange before anything is heard. Both frames are ``turn`` frames
    with the unused half null (the frontend queue plays each in order).

    ``forced_stage`` advances the arc to the beat the generative caller is playing.
    """
    loop = asyncio.get_running_loop()

    # 1) Detection first (fast, CPU), then the caller voice on the dedicated TTS
    #    thread. All Parler synthesis goes through tts_pool so it never runs
    #    concurrently with another generate (which cripples MPS).
    detection = await asyncio.to_thread(
        decoy_agent.process_caller_detection, session, db, caller_text, language,
        forced_stage,
    )
    caller_audio = await loop.run_in_executor(
        tts_service.tts_pool, decoy_agent.synthesize_caller, caller_text, language
    )
    # 2) Stream the caller frame NOW — the client starts playing it.
    await conn.send({
        "type": "turn",
        "scammer": {"text": caller_text, "language": language,
                    "audio_url": _audio_url(caller_audio)},
        "detection": {
            "scam_prob": detection["scam_probability"],
            "stage": detection["stage"],
            "scam_type": detection["scam_type"],
            "red_flags": detection["red_flags"],
            "new_identifiers": detection["new_identifiers"],
            "identifiers_total": detection["identifiers_total"],
            "known_ring_hit": detection["known_ring_hit"],
        },
        "mode": detection["mode"],
        "agent": None,
    })
    # 3) Author + voice the decoy reply while the caller clip plays.
    reply, used_fallback = await asyncio.to_thread(
        decoy_agent.generate_decoy_reply, session, language, session.mode, agent_override
    )
    agent_audio = await loop.run_in_executor(
        tts_service.tts_pool, decoy_agent.synthesize_reply, reply, language,
        session.mode.value,
    )
    # 4) Stream the decoy frame.
    await conn.send({
        "type": "turn",
        "scammer": None,
        "detection": None,
        "mode": session.mode.value,
        "agent": {"text": reply, "language": language,
                  "audio_url": _audio_url(agent_audio), "used_fallback": used_fallback},
    })


async def _handle_audio(conn: "_Conn", db: Session, session, chunk: bytes) -> None:
    """Live-mic path: transcribe locally, then advance the loop."""
    from app.services import stt

    text = await asyncio.to_thread(stt.transcribe_audio_bytes, chunk, session.language)
    if not text:
        return
    await _advance(conn, db, session, text, session.language)
    if session.should_wrap_up():
        await _wrap_and_end(conn, db, session)


async def _wrap_and_end(conn: "_Conn", db: Session, session) -> None:
    result = await asyncio.to_thread(_finalize, db, session)
    await conn.send({
        "type": "call_ended",
        "verdict": session.verdict,
        "package_id": session.package_id,
        "duration_seconds": int(session.elapsed_seconds),
        "identifiers_total": session.intel.total_identifiers(),
        "time_to_first_identifier": session.time_to_first_identifier,
        **result,
    })


def _finalize(db: Session, session) -> dict:
    """Compute the verdict, persist state, and generate a package if a scam."""
    if session.ended:
        return {"already_ended": True}
    session.ended = True
    is_scam = session.confirmed_scam()
    session.verdict = "scam" if is_scam else "safe"

    # Persist the CallSession outcome.
    cs = db.get(CallSession, session.session_id)
    if cs is not None:
        from datetime import datetime, timezone

        cs.transcript = session.full_transcript
        cs.max_confidence = session.max_scam_probability
        cs.outcome = "scam" if is_scam else "safe"
        cs.stage_reached = session.current_stage.value
        cs.interrupted = is_scam
        cs.ended_at = datetime.now(timezone.utc)
        db.commit()

    if is_scam:
        try:
            pkg = generate_package(db, session)
            session.package_id = pkg.package_id
            return {"package_id": pkg.package_id}
        except Exception as exc:  # never hang the call on a packaging failure
            logger.warning("Package generation failed for session %s: %s",
                           session.session_id, exc)
            db.rollback()
            return {"package_error": True}
    return {}


def _authenticate(token: str) -> int | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

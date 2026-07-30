"""Streaming speech-to-text with a rolling, in-memory-only buffer.

Privacy / data-minimisation design (CLAUDE.md Section 10), encoded literally:

  * Audio is held in a bounded, in-memory ring buffer and continuously
    discarded. Nothing is ever written to disk here.
  * Only a transcript (text) leaves this module. The raw audio is dropped as
    soon as it has been transcribed or has aged out of the window.
  * Persistence of any segment happens elsewhere and only on a confirmed scam
    (see ``services/evidence.py``), never in normal operation.

STT itself uses ``faster-whisper`` if installed; if not (or if it fails to
load) the app still runs — Demo mode and the client ``append`` path supply
text directly, so the live-call feature never hard-depends on STT weights.
"""

from __future__ import annotations

import logging
from collections import deque

from app.config import settings

logger = logging.getLogger("kavach.stt")


class RollingAudioBuffer:
    """A bounded in-memory buffer of recent audio chunks.

    Holds at most ``max_chunks`` most-recent chunks; older audio is evicted and
    lost. There is deliberately no method to flush this to disk.
    """

    def __init__(self, max_chunks: int = 32) -> None:
        self._chunks: deque[bytes] = deque(maxlen=max_chunks)

    def append(self, chunk: bytes) -> None:
        self._chunks.append(chunk)

    def snapshot(self) -> bytes:
        """Return the current window as one bytes object (for transcription)."""
        return b"".join(self._chunks)

    def clear(self) -> None:
        """Discard all buffered audio."""
        self._chunks.clear()


class _WhisperTranscriber:
    """Lazy faster-whisper wrapper (loaded only if the library is present)."""

    def __init__(self, model_size: str) -> None:
        from faster_whisper import WhisperModel  # optional dependency

        # CPU-friendly int8 as per the brief; no GPU assumed.
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio, language: str | None = "en") -> str:
        """Transcribe a path / file-like / numpy array. ``language=None`` lets
        Whisper auto-detect (English + Hindi/Hinglish)."""
        segments, _info = self._model.transcribe(audio, language=language)
        return " ".join(seg.text.strip() for seg in segments).strip()


_transcriber: _WhisperTranscriber | None = None
_tried = False


def stt_available() -> bool:
    """Whether a working STT backend is loaded."""
    return _get_transcriber() is not None


def _get_transcriber() -> _WhisperTranscriber | None:
    global _transcriber, _tried
    if _tried:
        return _transcriber
    _tried = True
    try:
        _transcriber = _WhisperTranscriber(settings.whisper_model_size)
        logger.info("STT: faster-whisper '%s' loaded.", settings.whisper_model_size)
    except Exception as exc:
        logger.info(
            "STT: faster-whisper unavailable (%s). Live audio transcription is "
            "disabled; Demo mode and text input still work.",
            exc,
        )
        _transcriber = None
    return _transcriber


def transcribe(audio, language: str | None = "en") -> str | None:
    """Transcribe a numpy PCM array / path / file-like to text, or None.

    Returns None when no STT backend is available, signalling the caller to
    fall back to text supplied directly by the client.
    """
    transcriber = _get_transcriber()
    if transcriber is None:
        return None
    try:
        return transcriber.transcribe(audio, language=language)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("STT transcription failed (%s).", exc)
        return None


def transcribe_audio_bytes(data: bytes, language: str | None = None) -> str | None:
    """Transcribe one audio chunk (e.g. a WebM/Opus blob from the browser).

    The bytes are decoded in-memory (``BytesIO``) and never written to disk —
    the privacy contract is that audio is transcribed on-device and discarded;
    only the resulting text moves on. Returns None if STT is unavailable or the
    chunk cannot be decoded, so the caller degrades gracefully.

    ``language=None`` auto-detects (supports English + Hindi/Hinglish); pass
    "en" or "hi" to force a language.
    """
    import io

    if not data:
        return None
    transcriber = _get_transcriber()
    if transcriber is None:
        return None
    try:
        text = transcriber.transcribe(io.BytesIO(data), language=language)
        return text or None
    except Exception as exc:
        logger.info("STT chunk decode/transcribe failed (%s).", exc)
        return None
    finally:
        # Nothing persisted: the BytesIO and the caller's chunk are dropped.
        pass

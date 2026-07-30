"""Text-to-speech for the decoy — Indic Parler-TTS (local), with fallbacks.

Model: ``ai4bharat/indic-parler-tts`` (Apache 2.0). Voice is fixed per language
by a natural-language caption + a named speaker (see ``persona.py``), so Ramesh
sounds consistent. Everything runs locally — audio never leaves the machine.

Graceful degradation, in order:
  1. Live Parler-TTS synthesis, if the model is installed and loaded.
  2. A pre-cached clip keyed by (language, stall_type) — instant playback that
     covers the demo when the live model is slow or absent.
  3. Text-only — the frontend shows Ramesh's line without audio.

Generation is synchronous here but must be called via ``asyncio.to_thread`` from
the loop so it never blocks the conversation. Audio is written to a served
cache dir and referenced by URL over the WebSocket.
"""

from __future__ import annotations

import hashlib
import logging
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import settings
from app.services import persona

logger = logging.getLogger("kavach.tts")

# All Parler operations (model load + every synthesis) run on this ONE dedicated
# thread. MPS is slow and error-prone when a model is driven from many rotating
# worker threads (as asyncio.to_thread does) — pinning every generate to a single
# thread keeps synthesis at its baseline RTF and serializes GPU access.
tts_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parler")


def warm_parler_blocking() -> None:
    """Load Parler and run one dummy synth — call via ``tts_pool`` at startup so
    the model is created on the same thread every synthesis later runs on."""
    tts = _get_tts_blocking()
    if tts is not None:
        try:
            tts.synthesize("नमस्ते", persona.parler_description("agent", "hi"))
        except Exception:  # pragma: no cover
            pass

# Where generated + pre-cached clips live (served read-only by the decoy route).
TTS_CACHE_DIR = Path(__file__).resolve().parent.parent / "ml" / "tts_models" / "cache"
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
PRECACHED_DIR = TTS_CACHE_DIR / "precached"
PRECACHED_DIR.mkdir(parents=True, exist_ok=True)

_SAMPLE_RATE = 44100


class _ParlerTTS:
    """Lazy Indic Parler-TTS wrapper (loaded only if the package is present)."""

    def __init__(self) -> None:
        import os

        # Let any op unsupported on MPS fall back to CPU instead of erroring.
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

        import torch  # noqa: F401
        from parler_tts import ParlerTTSForConditionalGeneration  # type: ignore
        from transformers import AutoTokenizer

        self._torch = torch
        # Device: DECOY_TTS_DEVICE overrides; otherwise prefer Apple MPS, then
        # CUDA, then CPU. MPS produces valid audio and is comparable-or-faster
        # than CPU on Apple silicon.
        override = os.environ.get("DECOY_TTS_DEVICE") or settings.tts_device
        if override:
            self._device = override
        elif torch.backends.mps.is_available():
            self._device = "mps"
        elif torch.cuda.is_available():
            self._device = "cuda"
        else:
            self._device = "cpu"
        # CRITICAL for real-time: load in bfloat16 on GPU/MPS. float32 makes this
        # model ~20x slower on Apple silicon (RTF ~11 vs ~1.5) — the difference
        # between "unusable" and live turn-by-turn synthesis. CPU stays float32
        # (bf16 matmul is not consistently faster there).
        self._dtype = torch.float32 if self._device == "cpu" else torch.bfloat16
        model_id = "ai4bharat/indic-parler-tts"
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(model_id).to(
            self._device, dtype=self._dtype
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        self._desc_tokenizer = AutoTokenizer.from_pretrained(
            self._model.config.text_encoder._name_or_path
        )
        self._sr = self._model.config.sampling_rate
        # Audio-token rate (≈86/s). Used to cap generation length so a line can
        # never run away to the model's ~30s maximum (which makes a single synth
        # take ~45s). Our lines are short, so a modest cap keeps synthesis fast.
        self._frame_rate = int(
            getattr(self._model.audio_encoder.config, "frame_rate", 86) or 86
        )

    # Never synthesize more than this many seconds of audio for one line —
    # bounds worst-case latency to keep the live conversation snappy. Lines are
    # 1-2 sentences, so this rarely bites but caps any runaway.
    _MAX_AUDIO_SECONDS = 7

    def synthesize(self, text: str, description: str) -> bytes:
        import soundfile as sf  # type: ignore
        import io

        desc_ids = self._desc_tokenizer(description, return_tensors="pt").to(self._device)
        prompt_ids = self._tokenizer(text, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            audio = self._model.generate(
                input_ids=desc_ids.input_ids,
                attention_mask=desc_ids.attention_mask,
                prompt_input_ids=prompt_ids.input_ids,
                prompt_attention_mask=prompt_ids.attention_mask,
                max_new_tokens=self._frame_rate * self._MAX_AUDIO_SECONDS,
            )
        # bf16 → float32 on CPU before encoding to PCM.
        arr = audio.to(self._torch.float32).cpu().numpy().squeeze()
        # Free MPS memory after each generate. Without this, successive
        # generations slow down dramatically (RTF drifts from ~1.8 to >10 over a
        # few calls) as the MPS allocator fragments — which would make a live,
        # multi-turn call progressively unusable.
        del audio
        if self._device == "mps":
            try:
                self._torch.mps.empty_cache()
            except Exception:
                pass
        buf = io.BytesIO()
        sf.write(buf, arr, self._model.config.sampling_rate, format="WAV")
        return buf.getvalue()


# The Indic Parler-TTS model is ~2.5 GB and takes tens of seconds to load (and
# downloads on first use). Loading it must NEVER block a request or the
# conversation loop, so it loads on a background thread; until it is ready,
# ``synthesize`` returns None (text-only) and the call flows normally. Once
# loaded, voice appears automatically.
import threading

_tts: _ParlerTTS | None = None
_load_state = "idle"  # idle | loading | ready | failed
_load_lock = threading.Lock()


def _load_worker() -> None:
    global _tts, _load_state
    try:
        logger.info("Loading Indic Parler-TTS in background (first load is slow)…")
        model = _ParlerTTS()
        _tts = model
        _load_state = "ready"
        logger.info("Indic Parler-TTS ready (device=%s).", model._device)
    except Exception as exc:
        _load_state = "failed"
        logger.info(
            "Indic Parler-TTS unavailable (%s). Using pre-cached clips / text-only. "
            "Install parler-tts and let the model finish downloading to enable voice.",
            exc,
        )


def start_loading() -> None:
    """Kick off the background model load once (safe to call repeatedly)."""
    global _load_state
    with _load_lock:
        if _load_state in ("idle", "failed") and _tts is None:
            _load_state = "loading"
            threading.Thread(target=_load_worker, name="tts-load", daemon=True).start()


def _get_tts() -> _ParlerTTS | None:
    """Return the loaded model, or None while it loads / if it failed.

    Non-blocking: triggers the background load on first call and returns
    immediately. The caller degrades to a pre-cached clip or text-only.
    """
    if _tts is None:
        start_loading()
    return _tts


def _get_tts_blocking() -> _ParlerTTS | None:
    """Load Parler synchronously (once) and return it — for offline pre-gen.

    Unlike ``_get_tts`` this WAITS for the model so a short-lived script actually
    synthesizes instead of exiting before the background load finishes.
    """
    global _tts, _load_state
    if _tts is None:
        with _load_lock:
            if _tts is None:
                try:
                    _tts = _ParlerTTS()
                    _load_state = "ready"
                    logger.info("Indic Parler-TTS ready (device=%s, bf16=%s).",
                                _tts._device, _tts._dtype != _tts._torch.float32)
                except Exception as exc:
                    _load_state = "failed"
                    logger.warning("Parler blocking load failed: %s", exc)
    return _tts


def tts_available() -> bool:
    return _tts is not None


def load_state() -> str:
    return _load_state


def _silent_wav(seconds: float = 0.4) -> bytes:
    """A short silent WAV — a valid audio URL when nothing else is available."""
    import io
    import struct

    n = int(_SAMPLE_RATE * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SAMPLE_RATE)
        w.writeframes(struct.pack("<%dh" % n, *([0] * n)))
    return buf.getvalue()


def _cache_write(name: str, data: bytes) -> str:
    """Write audio to the cache dir and return its served relative path."""
    path = TTS_CACHE_DIR / name
    path.write_bytes(data)
    return name


def precached_clip(language: str, stall_type: str) -> str | None:
    """Return the served filename of a pre-cached clip, if one exists."""
    candidate = PRECACHED_DIR / f"{language}_{stall_type}.wav"
    if candidate.exists():
        return f"precached/{candidate.name}"
    return None


def cache_name(text: str, language: str, role: str) -> str:
    """Deterministic cache filename for a (role, language, text) clip.

    The pre-generation script writes clips under this exact name so the live
    demo cache-hits them instantly. Kept stable — do not change the key format.
    """
    key = hashlib.sha256(f"{role}:{language}:{text}".encode()).hexdigest()[:16]
    return f"gen_{key}.wav"


def pregenerate(text: str, language: str, role: str, *, force: bool = True) -> str:
    """Offline: render one line with the ACTIVE engine and write it to the cache.

    Unlike ``synthesize`` (which stays non-blocking on the hot path), this waits
    for the model and always produces audio, so the pre-gen script can fill the
    cache regardless of ``SVARA_BACKEND``. Returns "write" | "skip" | "fail".
    """
    if not text:
        return "skip"
    name = cache_name(text, language, role)
    path = TTS_CACHE_DIR / name
    if path.exists() and not force:
        return "skip"

    engine = (settings.tts_engine or "parler").lower()
    data: bytes | None = None
    try:
        if engine == "svara":
            from app.services import svara_tts

            data = svara_tts.synthesize_blocking(
                text, persona.svara_speaker_id(role, language),
                persona.svara_emotion(role), backend="transformers",
            )
        else:
            tts = _get_tts_blocking()
            if tts is not None:
                data = tts.synthesize(text, persona.parler_description(role, language))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Pre-gen synthesis failed (%s).", exc)
        return "fail"
    if not data:
        return "fail"
    path.write_bytes(data)
    return "write"


def synthesize(
    text: str,
    language: str,
    *,
    stall_type: str | None = None,
    role: str = "agent",
    mode: str | None = None,
) -> str | None:
    """Synthesize ``text`` for ``language`` in the voice for ``role``.

    ``role`` is ``"agent"`` (Ramesh, the decoy) or ``"scammer"`` (the caller);
    each has a distinct voice so the two speakers are audibly different. ``mode``
    (agent MONITOR/STALL/WRAP_UP) tunes the emotion for the svara engine.

    Returns a served relative filename (under the TTS cache dir), or None if no
    audio could be produced (frontend then shows text only). Never raises.
    """
    if not text:
        return None

    # 0) Cache hit — identical (role, language, text) was synthesized before.
    # Synthesis is the expensive step (seconds on GPU/MPS); a demo run re-uses
    # the same lines, so serving the existing clip makes repeat runs instant and
    # frees the event loop to actually stream the audio. Pre-generated demo
    # clips (see app.ml.pregen_demo) land here.
    name = cache_name(text, language, role)
    if (TTS_CACHE_DIR / name).exists():
        return name

    engine = (settings.tts_engine or "svara").lower()

    if engine == "svara":
        # 1a) Svara-TTS (primary). Returns None while the model loads or when the
        # backend is "off" (the local-demo default → serve the cache only).
        from app.services import svara_tts

        speaker = persona.svara_speaker_id(role, language)
        emotion = persona.svara_emotion(role, mode)
        data = svara_tts.synthesize(text, speaker, emotion)
        if data:
            return _cache_write(name, data)
    else:
        # 1b) Indic Parler-TTS. The description names a valid roster speaker and
        # is passed as-is (it already contains the speaker name — do not prepend).
        tts = _get_tts()
        if tts is not None:
            try:
                description = persona.parler_description(role, language)
                data = tts.synthesize(text, description)
                return _cache_write(name, data)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Parler synthesis failed (%s); using fallback.", exc)

    # 2) Pre-cached stall clip (agent stalls only).
    if role == "agent" and stall_type:
        clip = precached_clip(language, stall_type)
        if clip:
            return clip

    # 3) No audio — the frontend renders the text (paced to reading length).
    return None

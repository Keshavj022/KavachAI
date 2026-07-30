"""Svara-TTS (kenpath/svara-tts-v1) — the decoy's primary voice engine.

Svara is an Orpheus-style TTS model: a Llama-3.2-3B backbone autoregressively
emits discrete audio tokens, which a SNAC 24 kHz codec decodes into a waveform.
Voice is selected by a plain ``"Language (Gender)"`` speaker string and an
optional emotion tag (``<anger>``, ``<fear>``, ``<clear>``, …) placed at the end
of the text. Everything runs locally — audio never leaves the machine.

Two backends, chosen by ``SVARA_BACKEND``:

  * ``vllm`` — the production / submission path. vLLM serves the 3B model in
    real time on a CUDA GPU. This is what the deployed build uses.
  * ``transformers`` — a portable ``model.generate()`` fallback. Correct on any
    machine (incl. Apple MPS) but slow for a 3B model, so on a laptop it is used
    only to PRE-GENERATE the fixed demo lines offline into the TTS cache, which
    the live demo then serves instantly.
  * ``off`` — skip live synthesis entirely; serve only pre-generated cache clips
    (the default, safe local-demo path on a machine without a GPU/vLLM).

The prompt/token format and the SNAC token→audio mapping follow the official
svara inference implementation (github.com/Kenpath/svara-tts-inference).
"""

from __future__ import annotations

import io
import logging
import threading
import wave

from app.config import settings

logger = logging.getLogger("kavach.svara")

# --- Svara / Orpheus token constants (from the model's tokenizer) -----------
TOKENISER_LENGTH = 128256
BOS_TOKEN = 128000
END_OF_TEXT = 128001
END_OF_TURN = 128009
START_OF_SPEECH = 128257
END_OF_SPEECH = 128258
START_OF_HUMAN = 128259
END_OF_HUMAN = 128260
START_OF_AI = 128261
END_OF_AI = 128262
PAD_TOKEN = 128263
AUDIO_TOKEN = 156939  # <|audio|> marker used inside the human text block

AUDIO_TOKENS_START = TOKENISER_LENGTH + 10  # 128266
AUDIO_VOCAB_SIZE = 4096
_AUDIO_TOKEN_MAX = AUDIO_TOKENS_START + 7 * AUDIO_VOCAB_SIZE  # 156938

SAMPLE_RATE = 24000

# Generation is deterministic-ish for a stable demo voice.
_MAX_NEW_TOKENS = 2048
_TEMPERATURE = 0.4
_TOP_P = 0.9
_REPETITION_PENALTY = 1.1


def _resolve_device() -> str:
    """Pick the compute device: explicit override, else mps→cuda→cpu."""
    override = settings.tts_device
    if override:
        return override
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:  # pragma: no cover - torch import guard
        pass
    return "cpu"


# --------------------------------------------------------------------------
# Prompt construction (standard TTS: speaker + text → input token ids)
# --------------------------------------------------------------------------
def build_prompt_ids(text: str, speaker_id: str, tokenizer) -> list[int]:
    """Assemble the Svara prompt token ids for one line.

    Layout (standard TTS): BOS, [START_OF_HUMAN, AUDIO_TOKEN, text…, END_OF_HUMAN,
    END_OF_TURN], START_OF_AI, START_OF_SPEECH — the model then emits speech
    tokens until END_OF_SPEECH.
    """
    prompt = f"{speaker_id}: {text}"
    text_ids = tokenizer(prompt, add_special_tokens=False).input_ids
    return (
        [BOS_TOKEN, START_OF_HUMAN, AUDIO_TOKEN]
        + list(text_ids)
        + [END_OF_HUMAN, END_OF_TURN, START_OF_AI, START_OF_SPEECH]
    )


def tokens_to_codes(token_ids: list[int]) -> list[int]:
    """Map generated audio token ids → raw SNAC codes in [0, 4096].

    Each audio token's band is its position modulo 7; the code is the token id
    minus the band's vocabulary offset. Non-audio tokens (e.g. a trailing
    END_OF_SPEECH) are dropped; the result is truncated to whole 7-token frames.
    """
    codes: list[int] = []
    good = 0
    for tid in token_ids:
        if tid == END_OF_SPEECH:
            break
        if not (AUDIO_TOKENS_START <= tid < _AUDIO_TOKEN_MAX):
            continue
        band = good % 7
        code = tid - AUDIO_TOKENS_START - band * AUDIO_VOCAB_SIZE
        if 0 <= code <= AUDIO_VOCAB_SIZE:
            codes.append(code)
            good += 1
    usable = (len(codes) // 7) * 7
    return codes[:usable]


# --------------------------------------------------------------------------
# SNAC decoder (tokens → waveform), lazily loaded and cached.
# --------------------------------------------------------------------------
class _Snac:
    def __init__(self, device: str) -> None:
        import torch
        from snac import SNAC  # type: ignore

        self._torch = torch
        self.device = device
        self.model = SNAC.from_pretrained(settings.svara_snac_model).eval().to(device)

    def decode(self, codes: list[int]) -> bytes:
        """Decode whole-frame SNAC codes into a 24 kHz mono WAV (bytes)."""
        import numpy as np

        torch = self._torch
        if len(codes) < 7:
            return b""
        frames = len(codes) // 7
        t = torch.tensor(codes[: frames * 7], dtype=torch.int32, device=self.device).view(frames, 7)
        codes_0 = t[:, 0].reshape(1, -1)
        codes_1 = t[:, [1, 4]].reshape(1, -1)
        codes_2 = t[:, [2, 3, 5, 6]].reshape(1, -1)
        with torch.inference_mode():
            audio = self.model.decode([codes_0, codes_1, codes_2])  # [1, 1, T]
        x = audio.detach().float().cpu().numpy().reshape(-1)
        pcm16 = (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16)
        return _pcm_to_wav(pcm16.tobytes())


def _pcm_to_wav(pcm16: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm16)
    return buf.getvalue()


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------
class _TransformersBackend:
    """Portable model.generate() path — correct anywhere, slow for a 3B model.

    Used for offline pre-generation on a laptop (and as a CPU/MPS fallback).
    """

    def __init__(self, device: str) -> None:
        import os

        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._torch = torch
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(settings.svara_model)
        dtype = torch.float32 if device in ("cpu", "mps") else torch.bfloat16
        self.model = (
            AutoModelForCausalLM.from_pretrained(settings.svara_model, torch_dtype=dtype)
            .eval()
            .to(device)
        )

    def generate_tokens(self, text: str, speaker_id: str) -> list[int]:
        torch = self._torch
        prompt_ids = build_prompt_ids(text, speaker_id, self.tokenizer)
        input_ids = torch.tensor([prompt_ids], dtype=torch.int64, device=self.device)
        with torch.no_grad():
            out = self.model.generate(
                input_ids,
                max_new_tokens=_MAX_NEW_TOKENS,
                do_sample=True,
                temperature=_TEMPERATURE,
                top_p=_TOP_P,
                repetition_penalty=_REPETITION_PENALTY,
                eos_token_id=END_OF_SPEECH,
                pad_token_id=PAD_TOKEN,
            )
        return out[0][input_ids.shape[1]:].tolist()


class _VLLMBackend:
    """Real-time vLLM path — the production / submission engine (CUDA)."""

    def __init__(self) -> None:
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams  # type: ignore

        self.tokenizer = AutoTokenizer.from_pretrained(settings.svara_model)
        self.llm = LLM(model=settings.svara_model, dtype="bfloat16")
        self._sampling = SamplingParams(
            temperature=_TEMPERATURE,
            top_p=_TOP_P,
            repetition_penalty=_REPETITION_PENALTY,
            max_tokens=_MAX_NEW_TOKENS,
            stop_token_ids=[END_OF_SPEECH],
        )

    def generate_tokens(self, text: str, speaker_id: str) -> list[int]:
        prompt_ids = build_prompt_ids(text, speaker_id, self.tokenizer)
        out = self.llm.generate(
            prompt_token_ids=[prompt_ids], sampling_params=self._sampling
        )
        return list(out[0].outputs[0].token_ids)


# --------------------------------------------------------------------------
# Lazy loader — never blocks a request or the conversation loop.
# --------------------------------------------------------------------------
_backend = None
_snac: _Snac | None = None
_load_state = "idle"  # idle | loading | ready | failed
_load_lock = threading.Lock()


def _select_backend_name(override: str | None = None) -> str:
    name = (override or settings.svara_backend or "auto").lower()
    if name == "auto":
        try:
            import vllm  # noqa: F401

            return "vllm"
        except Exception:
            return "transformers"
    return name


def _load_worker(backend_name: str) -> None:
    global _backend, _snac, _load_state
    try:
        device = _resolve_device()
        logger.info("Loading Svara-TTS backend=%s device=%s (first load is slow)…",
                    backend_name, device)
        if backend_name == "vllm":
            _backend = _VLLMBackend()
        else:
            _backend = _TransformersBackend(device)
        _snac = _Snac(device)
        _load_state = "ready"
        logger.info("Svara-TTS ready (backend=%s, device=%s).", backend_name, device)
    except Exception as exc:
        _load_state = "failed"
        logger.info(
            "Svara-TTS unavailable (%s). The demo will serve pre-generated cache "
            "clips or text-only. Install snac + the model (and vLLM for real-time) "
            "to enable live synthesis.", exc,
        )


def start_loading(backend: str | None = None) -> None:
    """Kick off the background model load once (safe to call repeatedly)."""
    global _load_state
    name = _select_backend_name(backend)
    if name == "off":
        return
    with _load_lock:
        if _load_state in ("idle", "failed") and _backend is None:
            _load_state = "loading"
            threading.Thread(
                target=_load_worker, args=(name,), name="svara-load", daemon=True
            ).start()


def load_state() -> str:
    return _load_state


def synthesize(text: str, speaker_id: str, emotion: str | None = None) -> bytes | None:
    """Synthesize one line → 24 kHz mono WAV bytes, or None if unavailable.

    Non-blocking with respect to loading: if the model is still loading (or the
    backend is ``off``) this returns None and the caller falls back to a cached
    clip or text. Never raises.
    """
    if not text or _select_backend_name() == "off":
        return None
    if _backend is None or _snac is None:
        start_loading()
        return None
    prompt_text = f"{text} {emotion}".strip() if emotion else text
    try:
        token_ids = _backend.generate_tokens(prompt_text, speaker_id)
        codes = tokens_to_codes(token_ids)
        return _snac.decode(codes) or None
    except Exception as exc:  # pragma: no cover - never break the call on TTS
        logger.warning("Svara synthesis failed (%s).", exc)
        return None


def synthesize_blocking(
    text: str, speaker_id: str, emotion: str | None = None, *, backend: str = "transformers"
) -> bytes | None:
    """Synchronously load (if needed) and synthesize — for offline pre-generation.

    Unlike ``synthesize`` this WAITS for the model to load and produce audio, so
    the pre-gen script can fill the cache. Forces the ``transformers`` backend by
    default (portable, no GPU/vLLM required). Never raises.
    """
    global _backend, _snac, _load_state
    if not text:
        return None
    try:
        if _backend is None or _snac is None:
            name = _select_backend_name(backend)
            device = _resolve_device()
            _backend = _VLLMBackend() if name == "vllm" else _TransformersBackend(device)
            _snac = _Snac(device)
            _load_state = "ready"
        token_ids = _backend.generate_tokens(
            f"{text} {emotion}".strip() if emotion else text, speaker_id
        )
        codes = tokens_to_codes(token_ids)
        return _snac.decode(codes) or None
    except Exception as exc:
        logger.warning("Svara blocking synthesis failed (%s).", exc)
        return None

"""Unified text-generation client for the decoy conversation.

Both the generative fraudster and the decoy author their lines through this one
function. It routes to whichever provider is configured:

  * **Groq** (``TEXT_PROVIDER=groq`` or ``auto`` with ``GROQ_API_KEY`` set) — a
    fast, OpenAI-compatible cloud endpoint. Offloading generation to the cloud
    leaves the local GPU entirely free for the TTS, which is the fastest path on
    a laptop. Note: this sends the transcript off-device.
  * **Ollama** (``ollama``, or ``auto`` with no Groq key) — fully local; nothing
    leaves the machine. The privacy-first path.

Either way this returns a single stripped line, or ``None`` on
timeout/failure/refusal, so callers fall back to a short in-character line and
the call never stalls.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("kavach.text_llm")

_TIMEOUT = 15.0


def provider() -> str:
    """Resolve the active provider: 'groq' or 'ollama'."""
    choice = (settings.text_provider or "auto").lower()
    if choice == "groq":
        return "groq"
    if choice == "ollama":
        return "ollama"
    # auto
    return "groq" if settings.groq_api_key.strip() else "ollama"


def generate(
    *,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 64,
    temperature: float = 0.8,
) -> str | None:
    """Generate one line via the active provider. None on any failure.

    Groq is the primary engine whenever ``GROQ_API_KEY`` is set; Ollama is used
    only as the fallback when no key is present (so the app still runs fully
    local out of the box). On a Groq error the caller uses a short in-character
    line rather than silently switching to a local model.
    """
    if provider() == "groq":
        return _groq(prompt, system, max_tokens, temperature)
    return _ollama(prompt, system, max_tokens, temperature)


def _groq(prompt: str, system: str | None, max_tokens: int, temperature: float) -> str | None:
    key = settings.groq_api_key.strip()
    if not key:
        return None
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        resp = httpx.post(
            f"{settings.groq_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": settings.groq_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as exc:
        logger.info("Groq generation unavailable (%s).", exc)
        return None


def _ollama(prompt: str, system: str | None, max_tokens: int, temperature: float) -> str | None:
    body = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "30m",
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_gpu": settings.ollama_num_gpu,  # CPU by default → GPU free for TTS
        },
    }
    if system:
        body["system"] = system
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate", json=body, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return (resp.json().get("response", "") or "").strip() or None
    except Exception as exc:
        logger.info("Ollama generation unavailable (%s).", exc)
        return None

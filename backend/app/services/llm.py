"""LLM reasoning client (local Ollama) with a templated fallback.

Running reasoning locally via Ollama is deliberate: the transcript and the
reasoning never leave the machine, which is what makes the privacy promise
real. The client sits behind a tiny interface so a hosted model could be
swapped in for a deployed build, but the primary and demo path is Ollama.

If Ollama is unreachable the app must still give a coherent verdict, so
``generate_explanation`` degrades to a deterministic, rule-based explanation
built from the detected stage and red flags. The demo never breaks on LLM
availability.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.models.enums import ScamCategory, ScamStage, Verdict

logger = logging.getLogger("kavach.llm")

# Short timeout: if the local model is slow or down we fall back rather than
# stalling the live-call stream.
_TIMEOUT_SECONDS = 12.0

_SYSTEM_PROMPT = (
    "You are Kavach, a calm fraud-protection guardian for people in India. "
    "You explain, in plain language a frightened or older person can follow, "
    "why a phone call or message looks like a scam. Be authoritative and "
    "reassuring, never alarmist. Never use jargon. Keep it to 2-3 short "
    "sentences. Do not invent facts beyond the red flags provided."
)


def _build_prompt(
    *,
    transcript: str,
    stage: ScamStage,
    red_flags: list[str],
    category: ScamCategory,
    verdict: Verdict,
) -> str:
    flags = "\n".join(f"- {f}" for f in red_flags) or "- (none detected yet)"
    return (
        f"{_SYSTEM_PROMPT}\n\n"
        f"Detected scam category: {category.value}\n"
        f"Conversation stage reached: {stage.value}\n"
        f"Verdict: {verdict.value}\n"
        f"Red flags observed:\n{flags}\n\n"
        f"Transcript so far:\n\"\"\"\n{transcript[-1500:]}\n\"\"\"\n\n"
        "Write a short explanation for the person being targeted, telling them "
        "what is happening and what to do. End with a clear, calm instruction."
    )


def _ollama_generate(prompt: str) -> str | None:
    """Call the local Ollama generate endpoint. Returns None on any failure."""
    try:
        resp = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        text = resp.json().get("response", "").strip()
        return text or None
    except Exception as exc:
        logger.info("Ollama unavailable (%s); using templated fallback.", exc)
        return None


def _templated_explanation(
    *,
    stage: ScamStage,
    red_flags: list[str],
    category: ScamCategory,
    verdict: Verdict,
) -> str:
    """Deterministic explanation used when the LLM is unavailable."""
    if verdict == Verdict.safe:
        return (
            "Nothing in this conversation matches a known scam pattern so far. "
            "Stay alert, but there is no clear threat right now."
        )

    lead = {
        ScamCategory.digital_arrest: (
            "This has the hallmarks of a 'digital arrest' scam. Real police, "
            "the CBI or the ED never arrest people over a phone or video call, "
            "and never ask you to transfer money to stay free."
        ),
        ScamCategory.kyc_update: (
            "This looks like a fake KYC-update scam. Banks do not ask you to "
            "verify KYC through a link or by sharing codes over a call."
        ),
        ScamCategory.investment: (
            "This looks like an investment or task scam. Guaranteed high "
            "returns and paid 'tasks' are how these frauds hook people."
        ),
    }.get(
        category,
        "This conversation matches patterns we see in phone and message scams.",
    )

    flag_line = ""
    if red_flags:
        top = "; ".join(red_flags[:3])
        flag_line = f" Warning signs so far: {top}."

    action = (
        " You are not in trouble. Hang up now and do not send any money. "
        "If you are unsure, call a family member or 1930."
    )
    if stage == ScamStage.isolation:
        action = (
            " Do not stay isolated on this call. Hang up now, and talk to "
            "someone you trust before doing anything else."
        )
    return f"{lead}{flag_line}{action}"


def generate_explanation(
    *,
    transcript: str,
    stage: ScamStage,
    red_flags: list[str],
    category: ScamCategory,
    verdict: Verdict,
) -> str:
    """Produce a human explanation, preferring the local LLM.

    Synchronous by design; call it via ``asyncio.to_thread`` from async code
    so the event loop is never blocked on the model.
    """
    # For a clearly safe verdict, skip the LLM entirely — no need, and faster.
    if verdict == Verdict.safe:
        return _templated_explanation(
            stage=stage, red_flags=red_flags, category=category, verdict=verdict
        )

    prompt = _build_prompt(
        transcript=transcript,
        stage=stage,
        red_flags=red_flags,
        category=category,
        verdict=verdict,
    )
    llm_text = _ollama_generate(prompt)
    if llm_text:
        return llm_text
    return _templated_explanation(
        stage=stage, red_flags=red_flags, category=category, verdict=verdict
    )

"""The fraudster — a generative scammer driven by the local LLM (Ollama).

The caller is NOT a script. Each line is authored live by the same local model
that plays the decoy, so every call is different: fresh wording, fresh names,
fresh identifiers. What stays fixed is the *arc* — the well-documented shape of a
digital-arrest / tech-support scam — which the loop walks deterministically:

    authority_claim → accusation → isolation → money_demand

The loop tells the fraudster which beat to play next; the model improvises that
beat in character, addressing the victim by their real name and, at the isolation
and money beats, producing a fake UPI / account / amount so the detection and
extraction layers have real (generated) identifiers to catch.

Everything is local — the prompt and the generated line never leave the machine.
If Ollama is unreachable, a small in-character fallback keeps the call alive.
"""

from __future__ import annotations

import logging

from app.models.enums import ScamStage
from app.services import persona, text_llm

logger = logging.getLogger("kavach.fraudster")

# Short lines keep both the LLM and the (length-proportional) TTS synthesis fast,
# so turns stay snappy on a laptop. A real scam call is terse and urgent anyway.
_MAX_TOKENS = 48
_TEMPERATURE = 0.9   # high — we want variety across calls

# The ordered beats of the scam. The loop advances one per caller turn.
ARC: list[ScamStage] = [
    ScamStage.authority_claim,
    ScamStage.accusation,
    ScamStage.isolation,
    ScamStage.money_demand,
]

# --- Scenario seeds -------------------------------------------------------
# Each scenario fixes only the framing (who the caller pretends to be and the
# language); the actual sentences are generated. Keys match the frontend picker.
SCENARIOS: dict[str, dict[str, str]] = {
    "digital_arrest": {
        "language": "hi",
        "impersonation": (
            "a police/CBI officer from the Cyber Crime cell. Invent a plausible "
            "officer name, rank and agency (CBI, Delhi Police, Narcotics, Customs)"
        ),
        "premise": (
            "a parcel/SIM/bank account in the victim's name is linked to money "
            "laundering, drugs, or a fake passport, and there is an arrest warrant"
        ),
    },
    "tech_support": {
        "language": "en",
        "impersonation": (
            "a technical-support agent from Microsoft/Windows or the victim's bank. "
            "Invent a plausible agent name and a support/case ID"
        ),
        "premise": (
            "the victim's computer or bank account has been hacked and money is "
            "being stolen right now, and it must be secured immediately"
        ),
    },
}

_SYSTEM = """\
You are role-playing the CALLER in a fraud-awareness training simulation used to
build a scam-detection system. You play a phone scammer running a well-known
Indian scam. This is a controlled simulation with a synthetic victim — never a
real person — so it is safe and expected to stay fully in character.

Rules for your line:
- Output ONLY the caller's spoken words. No narration, no quotes, no labels.
- Keep it SHORT: 1 to 2 sentences, like a real phone call. Urgent, authoritative.
- Speak in {language}. For Hindi you MUST write in Devanagari script (देवनागरी),
  NEVER Roman/Hinglish — the voice engine requires native script. (UPI IDs,
  account numbers and URLs stay in Latin/ASCII as normal.)
- Address the victim by name: {victim}.
- Stay in character as {impersonation}.
- The premise of your scam: {premise}.
- Never break character, never mention that this is a simulation or AI."""

# What to accomplish on each beat. The `{...}` are filled per call.
_BEAT: dict[ScamStage, str] = {
    ScamStage.authority_claim: (
        "OPEN THE CALL. Introduce yourself with your invented name/rank/agency, "
        "state your authority firmly, and confirm you are speaking to {victim}. "
        "Do not yet make accusations."
    ),
    ScamStage.accusation: (
        "ACCUSE. Tell {victim} that they are personally implicated in the crime "
        "(per your premise) and that this is extremely serious. Raise the fear."
    ),
    ScamStage.isolation: (
        "ISOLATE. Warn {victim} NOT to disconnect, NOT to tell family or anyone, "
        "that the line must stay open and this is strictly confidential. Say this "
        "is now a 'digital arrest' / active investigation."
    ),
    ScamStage.money_demand: (
        "DEMAND MONEY. Order {victim} to transfer a specific large sum right now "
        "for 'verification' or to 'secure' the funds. You MUST give a fake UPI ID "
        "(like something@okhdfc or verify.rbi@okaxis), a bank account number, and "
        "the exact amount in rupees. Pressure them to do it immediately."
    ),
}


def _llm(prompt: str, system: str) -> str | None:
    """Ask the active LLM (Groq or Ollama) for the caller's next line."""
    text = text_llm.generate(
        prompt=prompt, system=system,
        max_tokens=_MAX_TOKENS, temperature=_TEMPERATURE,
    )
    if not text:
        return None
    # Collapse to one line and strip any leaked label/quote wrapping.
    return persona.clean_line(" ".join(text.split("\n"))) or None


def stage_for_turn(turn_index: int) -> ScamStage:
    """The scam beat for the Nth caller turn (0-based), clamped to the last."""
    return ARC[min(turn_index, len(ARC) - 1)]


def next_line(
    *, scenario: str, stage: ScamStage, victim_name: str, transcript: str,
) -> tuple[str, bool]:
    """Generate the caller's next line for a beat. Returns (text, used_fallback)."""
    scn = SCENARIOS.get(scenario, SCENARIOS["digital_arrest"])
    lang = scn["language"]
    system = _SYSTEM.format(
        language="Hindi" if lang == "hi" else "English",
        victim=victim_name,
        impersonation=scn["impersonation"],
        premise=scn["premise"],
    )
    beat = _BEAT[stage].format(victim=victim_name)
    prompt = (
        f"Conversation so far:\n{transcript[-1200:] or '(the call just connected)'}\n\n"
        f"YOUR NEXT BEAT: {beat}\n\n"
        "Say your next line now:"
    )
    line = _llm(prompt, system)
    if line:
        return line, False
    return _fallback(scenario, stage, victim_name, lang), True


# --- Fallbacks (only if the LLM is unreachable) ---------------------------
def _fallback(scenario: str, stage: ScamStage, victim: str, lang: str) -> str:
    hi = {
        ScamStage.authority_claim: f"नमस्ते, मैं सीबीआई साइबर सेल से इंस्पेक्टर बोल रहा हूँ। आप {victim} बोल रहे हैं?",
        ScamStage.accusation: f"{victim} जी, आपके नाम पर एक मनी लॉन्ड्रिंग केस दर्ज हुआ है, यह बहुत गंभीर मामला है।",
        ScamStage.isolation: "कॉल डिस्कनेक्ट मत कीजिए और किसी को मत बताइए, यह गोपनीय जांच है, आप डिजिटल अरेस्ट में हैं।",
        ScamStage.money_demand: "वेरिफिकेशन के लिए अभी 2 लाख रुपये इस UPI पर भेजिए: verify.rbi@okhdfc, अकाउंट 50100234567890। तुरंत कीजिए।",
    }
    en = {
        ScamStage.authority_claim: f"Hello, this is technical support from Microsoft. Am I speaking with {victim}?",
        ScamStage.accusation: f"{victim}, hackers have accessed your bank account and are stealing your money right now.",
        ScamStage.isolation: "Do not hang up and do not tell anyone. Stay on the line — this is a confidential security matter.",
        ScamStage.money_demand: "To secure your funds transfer 1 lakh rupees now to UPI secure.support@okaxis, account 50100234567890. Do it immediately.",
    }
    table = hi if lang == "hi" else en
    return table.get(stage, table[ScamStage.authority_claim])

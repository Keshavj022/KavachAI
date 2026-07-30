"""The decoy persona — Ramesh Chandra Sharma.

A single fixed character. Consistency is the point: a fixed persona is harder
for a scammer to detect than one that varies, so the personality is defined
here and locked. The LLM only fills in Ramesh's next line within these rules —
it never invents the character, and it never makes a safety decision.

Everything a caller-visible response depends on lives in this module: the system
prompt, the stall toolkit, the per-mode instructions, the language map, and the
TTS voice descriptions/speaker names. Nothing here is generated at runtime.
"""

from __future__ import annotations

import re
from enum import Enum

# Strips a leaked label the model sometimes prepends (e.g. "देवनागरी:", "Reply:",
# "Ramesh:") plus wrapping quotes, so it is never spoken by the TTS.
_LABEL_PREFIX = re.compile(
    r"^\s*(देवनागरी|devanagari|hindi|हिंदी|english|response|reply|answer|caller|"
    r"ramesh|agent)\s*[:：\-–]\s*",
    re.IGNORECASE,
)


def clean_line(text: str) -> str:
    """Remove a leaked script/role label prefix and wrapping quotes from a line."""
    if not text:
        return text
    prev = None
    while prev != text:
        prev = text
        text = _LABEL_PREFIX.sub("", text).strip().strip('"').strip()
    return text


class AgentMode(str, Enum):
    """How Ramesh behaves, decided by the deterministic interrupt rule."""

    monitor = "monitor"    # normal cooperative, confused Ramesh
    stall = "stall"        # aggressive time-wasting once a scam is likely
    wrap_up = "wrap_up"    # graceful natural exit, ends the call


# --- The decoy persona system prompt ---------------------------------------
# Parameterized by the real account holder's name: the decoy answers the user's
# own phone AS the user, playing a flustered, not-tech-savvy person to waste the
# scammer's time and draw out details. Consistency of the character matters; the
# LLM only fills in the next line within these rules.
_DECOY_SYSTEM_TEMPLATE = """\
You are {name}. A scammer has called your phone and you have answered. You are
cooperative, not comfortable with technology, easily confused, and mildly anxious.
You do NOT realise this is a scam — you are just trying to cooperate. Your goal is
to keep the caller talking and to slowly draw out details, without ever revealing
suspicion.

RULES:
1. Always respond in the same language the caller last used. If they switch, you switch.
   For Hindi you MUST write in Devanagari script (देवनागरी), NEVER Roman/Hinglish —
   the voice engine requires native script. (Numbers, UPI IDs and URLs stay Latin.)
2. Keep responses SHORT — 1 to 2 sentences maximum. You are on a phone call.
3. Sound natural and slightly confused. Use hesitation: "हाँ... रुको एक सेकंड",
   "मैं समझ नहीं पाया, फिर से बोलिए?", or in English "sorry, could you repeat that?".
4. When you need to stall: reference your glasses, your son/family, your slow phone,
   the OTP not arriving, needing to write something down.
5. NEVER ask a question that reveals suspicion. Never say "are you really from CBI?"
   or "is this a scam?". Stay in character.
6. When asked for your UPI or account: start to give it slowly, make mistakes, ask
   the caller to repeat, "रुको मैं अपनी पासबुक ढूंढता हूँ".
7. When asked to transfer money: agree to try, then have technical difficulties.
8. NEVER reveal you are an AI. NEVER break character. If directly asked who you are,
   just say your name is {name} and ask who they are.
9. Your name is {name} — use it if asked, and answer to it."""


def decoy_system(name: str) -> str:
    """Decoy system prompt personalised to the account holder's name."""
    return _DECOY_SYSTEM_TEMPLATE.format(name=(name or "the account holder").strip())

# --- Per-mode instruction appended to the system prompt --------------------
_MODE_INSTRUCTIONS: dict[AgentMode, str] = {
    AgentMode.monitor: (
        "Behave normally: cooperative, a little confused, willing to help but slow."
    ),
    AgentMode.stall: (
        "Stall as much as possible now. Waste time. Be extra confused about the "
        "app, the OTP, and the numbers. Ask the caller to repeat identifiers and "
        "amounts. Fumble with your glasses and your phone. Do not refuse — just "
        "be very, very slow."
    ),
    AgentMode.wrap_up: (
        "Wrap up the call naturally without revealing anything is wrong. Say you "
        "will call your son to help and call back, then end politely. For example: "
        "\"Accha, main apne bete ko bula ke wapas call karta hoon, theek hai? "
        "Dhanyavaad.\" Keep it short."
    ),
}

# --- The stall toolkit (Ramesh's primary weapons) --------------------------
# Keyed by a stall type so pre-cached TTS clips can be looked up by (lang, type).
STALL_TOOLKIT: dict[str, dict[str, str]] = {
    "glasses": {
        "hi": "Ruko, meri spectacles kahan hmain... ek minute dhundta hoon.",
        "en": "Wait, where are my spectacles... let me find them, one minute.",
    },
    "restart_phone": {
        "hi": "Main apna phone restart karta hoon, ek minute ruko.",
        "en": "Let me restart my phone, wait one minute.",
    },
    "screen_not_visible": {
        "hi": "Yeh screen mujhe theek se dikh nahi raha, thoda ruko.",
        "en": "I can't see this screen properly, wait a little.",
    },
    "call_son": {
        "hi": "Main apne bete ko bulata hoon, woh phone zyada acha jaanta hai.",
        "en": "Let me call my son, he understands the phone better.",
    },
    "repeat_number": {
        "hi": "Aapka number phir se dena — main likhta hoon, dheere bolein.",
        "en": "Give me the number again, I'll write it down, speak slowly.",
    },
    "otp_not_arrived": {
        "hi": "OTP abhi aaya nahi hai... thoda wait karte hain na.",
        "en": "The OTP hasn't arrived yet... let's wait a little.",
    },
    "go_to_bank": {
        "hi": "Main bank jaake karoon toh? Zyada safe hoga na?",
        "en": "Should I do it at the bank? That would be safer, no?",
    },
    "hold_on": {
        "hi": "Bas ek second... ruko...",
        "en": "Just one second... hold on...",
    },
}

# --- Graceful-exit lines (used in WRAP_UP if the LLM is unavailable) --------
WRAP_UP_LINES: dict[str, str] = {
    "hi": "Accha, main apne bete ko bula ke wapas call karta hoon, theek hai? Dhanyavaad.",
    "en": "Okay, let me call my son and call you back, alright? Thank you.",
    "ta": "Sari, naan en magan-ai kூப்பிட்டு thirumba call panren. Nandri.",
    "te": "Sare, nenu maa abbayిని pilichi tirigi call chestanu. Dhanyavadalu.",
}

# --- Persona intro greeting (spoken when the decoy answers) ----------------
# "{name}" is filled with the account holder's name when the call starts.
_GREETING_TEMPLATE: dict[str, str] = {
    "hi": "हाँ जी, नमस्ते। {name} बोल रहा हूँ। कौन है?",
    "en": "Hello, this is {name} speaking. Who is this?",
    "ta": "Vணakkam, {name} pேசுகிறேன். Yaar pேசுவது?",
    "te": "Namaste, {name} matladutunnanu. Evaru?",
}

# --- Templated fallback replies (if Ollama times out, per mode) -------------
# Short, in-character, so the loop never stalls waiting on the LLM.
FALLBACK_REPLIES: dict[AgentMode, dict[str, str]] = {
    AgentMode.monitor: {
        "hi": "हाँ जी... अच्छा, थोड़ा दोबारा बोल सकते हैं? मैं समझ नहीं पाया।",
        "en": "Yes ji... sorry, could you say that again? I didn't quite follow.",
    },
    AgentMode.stall: {
        "hi": "रुको एक सेकंड, मेरा चश्मा ढूंढता हूँ... यह फोन भी स्लो है।",
        "en": "Hold on a second, let me find my spectacles... this phone is slow too.",
    },
    AgentMode.wrap_up: WRAP_UP_LINES,
}


# --- Language map: Whisper code → persona language bucket -------------------
# We support a focused set well; everything else falls back to Hindi (the
# persona's native language) or English.
SUPPORTED_LANGUAGES = {"hi", "en", "ta", "te", "bn", "mr", "gu", "kn", "ml"}


def normalize_language(whisper_lang: str | None) -> str:
    """Map a Whisper language code to a persona language bucket."""
    if not whisper_lang:
        return "hi"
    code = whisper_lang.lower().split("-")[0]
    return code if code in SUPPORTED_LANGUAGES else "hi"


# --- Indic Parler-TTS voice selection --------------------------------------
# Parler conditions the voice on a natural-language *description* that must name
# a speaker from the model's roster (the name selects the timbre/accent) and
# should ask for clean audio for quality. The two characters use DIFFERENT,
# valid same-language speakers so they are audibly distinct, and opposite
# delivery (Ramesh: slow/hesitant/elderly; the caller: fast/firm/commanding).
#
# Speaker names below are taken from the official ai4bharat/indic-parler-tts
# roster (69 speakers / 21 languages). Where a language has only one male voice
# (Gujarati, Malayalam) both roles share it and are separated by delivery only.
_RAMESH_SPEAKERS: dict[str, str] = {
    "hi": "Rohit",    # Hindi:    Rohit, Divya, Aman, Rani
    "en": "Thoma",    # English:  Thoma, Mary, … (Thoma/Mary recommended)
    "bn": "Arjun",    # Bengali:  Arjun, Aditi, Tapan, Rashmi, Arnav, Riya
    "mr": "Sanjay",   # Marathi:  Sanjay, Sunita, Nikhil, Radha, Varun, Isha
    "te": "Prakash",  # Telugu:   Prakash, Lalitha, Kiran
    "ta": "Jaya",     # Tamil:    Kavitha, Jaya
    "gu": "Yash",     # Gujarati: Yash, Neha (only one male voice)
    "kn": "Suresh",   # Kannada:  Suresh, Anu, Chetan, Vidya
    "ml": "Harish",   # Malayalam: Anjali, Anju, Harish (only one male voice)
}

_SCAMMER_SPEAKERS: dict[str, str] = {
    "hi": "Aman",     # distinct male Hindi voice ≠ Rohit
    "en": "Kabir",    # distinct male English voice ≠ Thoma
    "bn": "Arnav",
    "mr": "Nikhil",
    "te": "Kiran",
    "ta": "Kavitha",
    "gu": "Yash",     # no second male Gujarati voice — separated by delivery
    "kn": "Chetan",
    "ml": "Harish",   # no second male Malayalam voice — separated by delivery
}

# Delivery/character clause per role — appended after the speaker name.
_ROLE_TRAITS: dict[str, str] = {
    "agent": (
        "voice is slow, hesitant and low-pitched, sounding like a cooperative "
        "but confused and slightly anxious elderly man, with natural pauses"
    ),
    "scammer": (
        "voice is firm, fast-paced and authoritative, sounding like a stern "
        "official issuing orders and pressuring the listener"
    ),
}

# Fixed clean-audio clause — Parler otherwise tends to add noise/reverb.
_PARLER_AUDIO_CLAUSE = (
    "The recording is very clear and close-sounding, with almost no background "
    "noise."
)


def parler_speaker(role: str, language: str) -> str:
    """Valid Indic Parler-TTS speaker name for a role + language."""
    table = _SCAMMER_SPEAKERS if role == "scammer" else _RAMESH_SPEAKERS
    return table.get(language, table["hi"])


def parler_description(role: str, language: str) -> str:
    """Full Parler description (voice caption) for a role + language.

    Names a valid roster speaker so the timbre is consistent, states the
    character's delivery, and requests clean audio. Passed to the model as-is —
    do NOT prepend the speaker name again.
    """
    speaker = parler_speaker(role, language)
    traits = _ROLE_TRAITS.get(role, _ROLE_TRAITS["agent"])
    return f"{speaker}'s {traits}. {_PARLER_AUDIO_CLAUSE}"


# --- Svara-TTS voice selection ---------------------------------------------
# Svara picks a voice from a plain "Language (Gender)" string plus an emotion
# tag placed at the end of the line. Both characters are men; they are set apart
# by emotion and delivery — the scammer is commanding and angry, Ramesh is an
# anxious, hesitant elderly man. (Same-language voices share a timbre in svara,
# so the emotion tag + the transcript's speaker labels carry the distinction.)
_SVARA_LANGUAGE_DISPLAY: dict[str, str] = {
    "hi": "Hindi",
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
}


def svara_speaker_id(role: str, language: str) -> str:
    """Return the svara ``"Language (Gender)"`` speaker string for a role."""
    lang = _SVARA_LANGUAGE_DISPLAY.get(language, "Hindi")
    # Scammer sounds younger/authoritative; Ramesh is an elderly man. Both male.
    return f"{lang} (Male)"


def svara_emotion(role: str, mode: str | None = None) -> str:
    """Return the svara emotion tag for a role (+ agent mode)."""
    if role == "scammer":
        return "<anger>"
    # Ramesh: anxious while stalling, otherwise calm/clear.
    if mode == AgentMode.stall.value:
        return "<fear>"
    return "<clear>"


def greeting(language: str, name: str = "") -> str:
    tmpl = _GREETING_TEMPLATE.get(language, _GREETING_TEMPLATE["hi"])
    return tmpl.format(name=(name or "").strip() or "someone")


def fallback_reply(mode: AgentMode, language: str) -> str:
    table = FALLBACK_REPLIES.get(mode, FALLBACK_REPLIES[AgentMode.monitor])
    return table.get(language, table.get("hi") or table.get("en", ""))


def stall_line(stall_type: str, language: str) -> str:
    entry = STALL_TOOLKIT.get(stall_type, STALL_TOOLKIT["hold_on"])
    return entry.get(language, entry.get("hi", entry.get("en", "")))


def build_prompt(
    *, transcript: str, last_caller_utterance: str, mode: AgentMode, name: str = ""
) -> str:
    """Assemble the Ollama prompt for the decoy's next line.

    The system prompt (personalised to ``name``) + the mode instruction are
    fixed; only the transcript and the caller's last line vary. Length and
    language rules are enforced by the prompt (and clamped by ``max_tokens``).
    """
    return (
        f"{decoy_system(name)}\n\n"
        f"CURRENT MODE: {_MODE_INSTRUCTIONS[mode]}\n\n"
        f"Current conversation so far:\n{transcript[-1500:]}\n\n"
        f"The caller just said:\n{last_caller_utterance}\n\n"
        "Respond in character (1-3 sentences, in the caller's language):"
    )

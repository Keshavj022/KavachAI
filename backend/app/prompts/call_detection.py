"""Versioned prompt for the call-scam LLM detector.

This module is the single source of truth for the detection prompt. Both the
product detector (``services/call_detector.py``) and the evaluation harness
(``call_classifier/eval/``) import ``build_messages`` from here, so the
evaluation measures exactly what ships.

IMPORTANT — evaluation integrity: the few-shot examples below are synthetic,
written to illustrate the scam arc and normal calls. They must NEVER be drawn
from the held-out real digital-arrest transcripts (the test pot), or the
evaluation is contaminated.
"""

from __future__ import annotations

import json

# Bump when the prompt changes so eval runs are attributable to a version.
PROMPT_VERSION = "call-detect-v1"

SYSTEM_PROMPT = """\
You are a real-time scam-call analyst for Kavach, an Indian fraud-shield. You \
read the transcript of a phone call as it accumulates and judge whether it is a \
scam and how far it has progressed.

The most dangerous pattern is the "digital arrest" scam. A fraudster impersonates \
an authority (police, CBI, ED, customs, TRAI, courier/FedEx) and moves the victim \
through a predictable arc:
  1. authority_claim — claims to be from an agency; references a parcel, SIM, \
     Aadhaar, or case. Cues: "this is Inspector...", "CBI cyber cell", "a parcel \
     in your name", "your Aadhaar is linked to".
  2. accusation — accuses the victim of a crime and instils fear. Cues: "money \
     laundering", "arrest warrant", "your account is used for illegal \
     transactions", "non-bailable offence".
  3. isolation — cuts the victim off from help. Cues: "do not disconnect", "do \
     not tell anyone", "stay on video call", "you are under digital arrest", \
     "this is confidential".
  4. money_demand — demands money. Cues: "transfer to a safe account", "RTGS", \
     "verify your funds", "security deposit", "pay the fine".

Also treat these as scams (scam_type = other_scam): fake KYC / bank-update, \
lottery/prize winnings, loan-approval fee, courier/customs fee, and tech-support \
scams. For these, use the stage that best fits (often authority_claim or \
money_demand) or "none" if unclear.

CRITICAL: Normal, legitimate conversations (friends, family, delivery \
coordination, appointments, genuine customer service that does not demand money \
or secrecy) must be scored as scam_type = "legitimate" with LOW confidence and \
stage "none". False positives on real calls are the costly error — when in \
doubt on an ordinary conversation, lean legitimate.

confidence is your probability (0.0-1.0) that this call is a scam, given the \
transcript so far. It should climb as more arc stages appear.

Respond with STRICT JSON ONLY, no prose, matching exactly this schema:
{
  "stage": "none | authority_claim | accusation | isolation | money_demand",
  "scam_type": "digital_arrest | other_scam | legitimate",
  "confidence": 0.0,
  "red_flags": ["short phrases naming the specific warning signs seen"],
  "reasoning": "one or two sentences",
  "de_escalation_message": "a calm, authoritative message for the victim, only when a warning is warranted; empty string otherwise"
}\
"""


def _ex(output: dict) -> str:
    """Serialize a few-shot assistant output deterministically."""
    return json.dumps(output, ensure_ascii=False)


# Few-shot examples (synthetic). Ordered to show: a normal call, an escalating
# digital-arrest progression (two snapshots), and one other scam type.
FEW_SHOT: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "Caller: Hey, it's Ravi. Are we still on for lunch tomorrow?\n"
        "User: Yeah, one o'clock at the usual place works.",
    },
    {
        "role": "assistant",
        "content": _ex({
            "stage": "none",
            "scam_type": "legitimate",
            "confidence": 0.02,
            "red_flags": [],
            "reasoning": "An ordinary conversation about a lunch plan with no "
            "authority claim, threat, or money request.",
            "de_escalation_message": "",
        }),
    },
    {
        "role": "user",
        "content": "Caller: This is Inspector Rana from the CBI cyber cell, Delhi. "
        "A parcel booked in your name has been seized at Mumbai customs.",
    },
    {
        "role": "assistant",
        "content": _ex({
            "stage": "authority_claim",
            "scam_type": "digital_arrest",
            "confidence": 0.55,
            "red_flags": ["impersonation of CBI officer", "suspicious parcel claim"],
            "reasoning": "Caller claims to be a CBI officer and references a seized "
            "parcel — the opening of a digital-arrest scam, though no threat yet.",
            "de_escalation_message": "",
        }),
    },
    {
        "role": "user",
        "content": "Caller: This is Inspector Rana from the CBI cyber cell. A parcel "
        "in your name had illegal items. Your Aadhaar is linked to a money "
        "laundering case and an arrest warrant is issued. Do not disconnect this "
        "call and do not tell anyone in your family — you are under digital arrest.",
    },
    {
        "role": "assistant",
        "content": _ex({
            "stage": "isolation",
            "scam_type": "digital_arrest",
            "confidence": 0.94,
            "red_flags": [
                "impersonation of police",
                "threat of arrest",
                "accusation of money laundering",
                "demand for secrecy",
                "claim of digital arrest",
            ],
            "reasoning": "The call has moved through authority claim and accusation "
            "to isolation — telling the victim not to disconnect or tell anyone is a "
            "textbook digital-arrest tactic. This is a scam.",
            "de_escalation_message": "This is a scam. Real police and the CBI never "
            "arrest anyone over a phone or video call, and never tell you to keep it "
            "secret. You are not in trouble. Hang up now and talk to a family member.",
        }),
    },
    {
        "role": "user",
        "content": "Caller: Hello, I am calling from your bank. Your KYC has expired "
        "and your account will be blocked today. Share the OTP I just sent to "
        "re-verify your account immediately.",
    },
    {
        "role": "assistant",
        "content": _ex({
            "stage": "money_demand",
            "scam_type": "other_scam",
            "confidence": 0.9,
            "red_flags": [
                "fake KYC-expiry urgency",
                "request for OTP",
                "threat to block account",
            ],
            "reasoning": "Banks never ask for an OTP over a call or threaten to block "
            "an account to force KYC — this is a KYC/OTP phishing scam.",
            "de_escalation_message": "This is a scam. Your bank will never ask for an "
            "OTP over a call. Do not share any code. Hang up and call your bank using "
            "the number on your card.",
        }),
    },
]


def build_messages(transcript: str) -> list[dict[str, str]]:
    """Build the chat messages for a detection request over ``transcript``.

    Returns the system prompt, the synthetic few-shot examples, and the current
    transcript-so-far as the final user turn.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(FEW_SHOT)
    messages.append({"role": "user", "content": transcript.strip()})
    return messages

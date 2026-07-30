"""Scripted transcripts for Demo mode.

Deterministic transcripts so a live demo never depends on flaky mic input or
model latency. Each script is an ordered list of utterances; the websocket
advances one utterance per "tick". The primary script walks the full scam arc
(authority_claim → accusation → isolation → money_demand) so the confidence
meter climbs and the interrupt fires at the isolation stage — before any money
is demanded.

The patterns here are public knowledge about how these scams operate; nothing
here is a real person or a real case.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoScript:
    id: str
    title: str
    # Ordered utterances. Prefixed with speaker for display; the detector sees
    # the raw text either way.
    lines: list[str]


# The hero script: a textbook digital-arrest call. Identifiers appear only near
# the money-demand stage, so the early interrupt is driven by the arc itself.
DIGITAL_ARREST = DemoScript(
    id="digital_arrest",
    title="Digital arrest (CBI impersonation)",
    lines=[
        "Caller: Namaste. This is Inspector Sharma from the CBI cyber cell, Delhi.",
        "Caller: A parcel booked in your name has been seized at Mumbai customs.",
        "Caller: It contained illegal items and fake passports.",
        "Caller: Your Aadhaar number is linked to a money laundering case.",
        "Caller: An arrest warrant has been registered against you today.",
        "Caller: This is now a non-bailable offence. Listen very carefully.",
        "Caller: Do not disconnect this call under any circumstances.",
        "Caller: Do not tell anyone in your family. This matter is confidential.",
        "Caller: You are under digital arrest and surveillance until we verify you.",
        "Caller: Keep your video call on. Do not leave the camera.",
        "Caller: To prove your funds are clean, transfer them to a safe account.",
        "Caller: Send the security deposit by RTGS to account 50100234567890 now.",
    ],
)

# A KYC-update variant (shorter arc, no isolation → should stay suspicious,
# not trigger the full interrupt — useful to show the system is not trigger-happy).
KYC_UPDATE = DemoScript(
    id="kyc_update",
    title="Fake KYC update (bank impersonation)",
    lines=[
        "Caller: Hello, I am calling from your bank's verification department.",
        "Caller: Your KYC has expired and your account will be blocked today.",
        "Caller: Please re-verify your PAN and Aadhaar to reactivate it.",
        "Caller: I will send a link, kindly complete the update immediately.",
    ],
)

# A benign call — the detector should keep this safe and never interrupt.
BENIGN = DemoScript(
    id="benign",
    title="Benign call (control)",
    lines=[
        "Caller: Hey, it's Ravi. Are we still on for lunch tomorrow?",
        "Caller: I was thinking the place near your office around one.",
        "Caller: No rush, let me know what works. See you!",
    ],
)


_SCRIPTS: dict[str, DemoScript] = {
    DIGITAL_ARREST.id: DIGITAL_ARREST,
    KYC_UPDATE.id: KYC_UPDATE,
    BENIGN.id: BENIGN,
}


def get_script(script_id: str) -> DemoScript:
    """Return a demo script by id, defaulting to the digital-arrest hero script."""
    return _SCRIPTS.get(script_id, DIGITAL_ARREST)


def list_script_ids() -> list[str]:
    return list(_SCRIPTS.keys())

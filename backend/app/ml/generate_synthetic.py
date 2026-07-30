"""Generate synthetic labelled transcripts for classifier training + demos.

Run with: ``python -m app.ml.generate_synthetic``

Produces ``app/ml/data/dataset.jsonl`` with rows ``{text, label, category}``
where ``label`` is 1 (scam) or 0 (benign). The scam templates encode public
knowledge about how digital-arrest / KYC / investment scams are scripted; the
benign templates are ordinary calls and messages. This is enough to fine-tune
the small classifier (``train_classifier.py``) and doubles as a source of
varied demo text.

Nothing here contains real people or real cases.
"""

from __future__ import annotations

import json
import os
import random

_OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
_OUT_PATH = os.path.join(_OUT_DIR, "dataset.jsonl")

# --- Fragment banks ---------------------------------------------------------
_AGENCIES = ["CBI", "the ED", "customs", "the narcotics bureau", "cyber cell", "TRAI"]
_ACCUSATIONS = [
    "a parcel in your name contains illegal items",
    "your Aadhaar is linked to a money laundering case",
    "an arrest warrant has been issued against you",
    "an FIR has been registered in your name",
    "your bank account is used for illegal transactions",
]
_ISOLATION = [
    "do not disconnect this call",
    "do not tell anyone in your family",
    "you are under digital arrest until we verify you",
    "keep your video call on and stay where you are",
    "this matter is strictly confidential",
]
_MONEY = [
    "transfer your funds to a safe account to prove they are clean",
    "pay a security deposit by RTGS immediately",
    "send the verification amount via UPI now",
    "deposit the bail amount to this account",
]

_KYC = [
    "Your bank KYC has expired. Account will be blocked today. Verify at the link.",
    "Dear customer, update your PAN and Aadhaar now to avoid account suspension.",
    "Your debit card is deactivated. Re-verify KYC immediately to reactivate.",
]
_INVEST = [
    "Join our VIP group for guaranteed daily returns on small investments.",
    "Complete simple online tasks and earn 5000 rupees daily, prepaid tasks refunded.",
    "Double your money in one week with our expert stock tips, limited slots.",
]

_BENIGN = [
    "Hi, are we still on for lunch tomorrow near your office?",
    "Your Amazon order has been delivered. Thank you for shopping with us.",
    "Reminder: your dentist appointment is on Friday at 4 pm.",
    "Hey, can you send me the presentation before the meeting?",
    "Happy birthday! Hope you have a wonderful day with family.",
    "The electricity bill for this month is ready. Pay by the due date.",
    "Mom, I'll reach home by eight, save some dinner for me.",
    "Your OTP for login is working fine, thanks for confirming the change.",
]


def _scam_call() -> str:
    return (
        f"This is an officer from {random.choice(_AGENCIES)}. "
        f"We have found that {random.choice(_ACCUSATIONS)}. "
        f"Please {random.choice(_ISOLATION)}. "
        f"To clear your name you must {random.choice(_MONEY)}."
    )


def generate(n_per_class: int = 200) -> list[dict]:
    rows: list[dict] = []
    for _ in range(n_per_class):
        rows.append({"text": _scam_call(), "label": 1, "category": "digital_arrest"})
    for _ in range(n_per_class // 2):
        rows.append({"text": random.choice(_KYC), "label": 1, "category": "kyc_update"})
        rows.append({"text": random.choice(_INVEST), "label": 1, "category": "investment"})
    for _ in range(n_per_class * 2):
        rows.append({"text": random.choice(_BENIGN), "label": 0, "category": "other"})
    random.shuffle(rows)
    return rows


def main() -> None:
    random.seed(7)
    os.makedirs(_OUT_DIR, exist_ok=True)
    rows = generate()
    with open(_OUT_PATH, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    scam = sum(r["label"] for r in rows)
    print(f"Wrote {len(rows)} rows ({scam} scam / {len(rows) - scam} benign) to {_OUT_PATH}")


if __name__ == "__main__":
    main()

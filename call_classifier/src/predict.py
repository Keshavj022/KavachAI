"""Inference interface for the call detector — fully local, deterministic.

This is the reference implementation the backend mirrors. It loads the trained
classifier + arc tracker + threshold from ``data/artifacts/`` and scores a
growing transcript. There is NO network call here — reasoning models were used
only at training time to label public data; inference is entirely on-device.

De-escalation messages are PRE-WRITTEN templates keyed by stage — never
generated at runtime (a generated warning to a panicking victim is a
hallucination risk we do not take).

    from predict import CallDetector
    det = CallDetector()                 # one per call (holds monotonic state)
    det.analyze("caller: this is the cbi ... transfer to a safe account")
    -> {scam_probability, stage, verdict, interrupt, warn, de_escalation}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from app.services.asr_norm import asr_normalize  # noqa: E402  (shared)

STAGES = config.STAGES
STAGE_ORDER = config.STAGE_ORDER

# Pre-written de-escalation templates (never generated at runtime), per stage
# and language. Kept short and calm.
DE_ESCALATION = {
    "en": {
        "accusation": "Be careful — this call is showing scam warning signs. Do "
        "not act on threats or accusations made over a phone call.",
        "isolation": "This is a scam. Real police and agencies never tell you to "
        "keep a call secret or stay on the line. You are not in trouble. Hang up "
        "and talk to someone you trust.",
        "money_demand": "This is a scam. No genuine agency asks you to transfer "
        "money, share an OTP, or move funds to a 'safe account'. Do not pay. Hang "
        "up now.",
    },
    "hi": {
        "accusation": "Saavdhaan — is call mein scam ke sanket hain. Phone par di "
        "gayi dhamki ya aarop par bharosa na karein.",
        "isolation": "Yeh ek scam hai. Asli police kabhi call ko chhupane ya line "
        "par bane rehne ko nahi kehti. Ghabraayein nahi. Call kaat dein aur kisi "
        "bharosemand vyakti se baat karein.",
        "money_demand": "Yeh ek scam hai. Koi asli sansthaan paisa transfer, OTP, "
        "ya 'safe account' nahi maangti. Paisa na bhejein. Abhi call kaat dein.",
    },
}


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


# Deterministic stage cues. The trained arc tracker under-detects the rare
# later stages (the Groq annotation produced few 'isolation' labels), so the
# stage decision is BACKSTOPPED by these auditable cue rules — the safety-
# critical interrupt must never depend solely on an under-trained model.
_STAGE_CUES = {
    "authority_claim": ["police", "cbi", "officer", "department", "government",
                        "bank", "fedex", "courier", "trai", "customs", "interpol",
                        "calling from", "verification team"],
    "accusation": ["money laundering", "arrest", "warrant", "illegal", "drugs",
                   "parcel", "fir", "misused", "suspicious activity",
                   "fraudulent", "non bailable", "complaint against"],
    "isolation": ["do not tell", "dont tell", "do not disconnect",
                  "dont disconnect", "stay on the", "confidential", "do not hang",
                  "dont hang", "under arrest", "surveillance", "do not cut"],
    "money_demand": ["transfer", "rtgs", "neft", "safe account",
                     "verification account", "otp", "card number", "cvv",
                     "gift card", "bitcoin", "security deposit", "pay the fine"],
}


def _rule_stage(text_norm: str) -> str:
    """Highest scam-arc stage evidenced by deterministic cue phrases."""
    highest = "none"
    for stage in ("authority_claim", "accusation", "isolation", "money_demand"):
        if any(cue in text_norm for cue in _STAGE_CUES[stage]):
            if STAGE_ORDER[stage] > STAGE_ORDER[highest]:
                highest = stage
    return highest


class CallDetector:
    """Stateful, on-device call scam detector. One instance per call."""

    def __init__(self, artifacts_dir: Path | None = None,
                 threshold: float | None = None) -> None:
        art = artifacts_dir or config.ARTIFACTS
        deploy = json.load(open(art / "call_deployment.json"))
        self.threshold = threshold if threshold is not None else float(deploy["threshold"])
        self._clf = joblib.load(art / "call_classifier.joblib")
        self._clf_is_proba = hasattr(self._clf, "predict_proba")
        arc_path = art / "call_arc_tracker.joblib"
        self._arc = joblib.load(arc_path) if arc_path.exists() else None
        # Per-call monotonic state.
        self.highest_stage = "none"
        self.interrupt_fired = False

    def _scam_prob(self, text_norm: str) -> float:
        if self._clf_is_proba:
            return float(self._clf.predict_proba([text_norm])[0, 1])
        return _sigmoid(float(self._clf.decision_function([text_norm])[0]))

    def _stage(self, text_norm: str) -> str:
        # Combine the trained model with the deterministic cue floor; take the
        # higher stage. Then enforce monotonicity across the call.
        model_stage = "none"
        if self._arc is not None:
            model_stage = str(self._arc.predict([text_norm])[0])
        rule_stage = _rule_stage(text_norm)
        candidate = model_stage if STAGE_ORDER.get(model_stage, 0) >= STAGE_ORDER[rule_stage] else rule_stage
        if STAGE_ORDER.get(candidate, 0) > STAGE_ORDER[self.highest_stage]:
            self.highest_stage = candidate
        return self.highest_stage

    def analyze(self, transcript_so_far: str, language: str = "en") -> dict:
        """Score the growing transcript. Applies the shared asr_normalize so the
        runtime register matches training."""
        norm = asr_normalize(transcript_so_far)
        scam_prob = self._scam_prob(norm) if norm else 0.0
        stage = self._stage(norm) if norm else "none"
        order = STAGE_ORDER[stage]

        # Deterministic interrupt rule (in code, not learned).
        interrupt = self.interrupt_fired
        warn = False
        if not interrupt:
            if scam_prob >= self.threshold and order >= STAGE_ORDER["isolation"]:
                interrupt = True
            elif order >= STAGE_ORDER["money_demand"]:
                # Fast scam: money demanded with no prior interrupt → fire now.
                interrupt = True
            elif scam_prob >= self.threshold and stage == "accusation":
                warn = True
        if interrupt:
            self.interrupt_fired = True

        verdict = "scam" if (interrupt or scam_prob >= self.threshold) else (
            "suspicious" if scam_prob >= 0.4 else "safe")
        msg = ""
        if interrupt:
            key = "money_demand" if stage == "money_demand" else "isolation"
            msg = DE_ESCALATION.get(language, DE_ESCALATION["en"]).get(key, "")
        elif warn:
            msg = DE_ESCALATION.get(language, DE_ESCALATION["en"])["accusation"]

        return {
            "scam_probability": round(scam_prob, 4),
            "stage": stage,
            "verdict": verdict,
            "interrupt": interrupt,
            "warn": warn,
            "de_escalation": msg,
        }


if __name__ == "__main__":
    det = CallDetector()
    demo = [
        "caller hello sir this is inspector sharma from the cbi cyber cell",
        "caller a parcel in your name has illegal items and your aadhaar is in a money laundering case",
        "caller do not disconnect this call and do not tell anyone you are under digital arrest",
        "caller transfer your money to this safe verification account now",
    ]
    t = ""
    for line in demo:
        t = (t + " " + line).strip()
        r = det.analyze(t)
        print(f"p={r['scam_probability']:.2f} stage={r['stage']:15s} "
              f"interrupt={r['interrupt']} warn={r['warn']}")

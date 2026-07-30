"""Scam text classifier — the trained SMS Linear SVM, with a rule fallback.

The message/Fraud-Shield path uses the SVM trained in ``sms_classifier/`` (a
TF-IDF word+char + engineered-features Linear SVM, tuned threshold 0.505). If
the artifact is missing, a transparent keyword/rule scorer runs so the app never
crashes.

Two entry points:
  * ``classify(text) -> Classification`` — scam probability + category, kept for
    backward compatibility (the call-path fallback still uses it).
  * ``classify_message(text) -> dict`` — ``{label, malicious_probability,
    threshold}`` — the interface the message route uses.

KNOWN ISSUE (documented, not papered over): the SVM false-positives on
legitimate transactional / banking SMS (OTPs, payment confirmations, balance
alerts) because it keys on currency symbols + digit density. The message route
already runs the known-scammer graph lookup as a FAST PATH before this model; a
future trusted-sender / transaction-pattern allowlist should sit here too — see
``TRANSACTIONAL_ALLOWLIST_HOOK`` below.

The SVM "probability" is a sigmoid of the decision margin — monotonic but
UNCALIBRATED; it is valid for the fixed 0.505 threshold, not as a true
probability.
"""

from __future__ import annotations

import logging
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.models.enums import ScamCategory

logger = logging.getLogger("kavach.classifier")

_DEFAULT_SMS_DIR = Path(__file__).resolve().parent.parent / "ml" / "models" / "sms"

# Hook for a future trusted-sender / transactional-pattern exception. Populate
# with sender ids or regexes that should never be flagged (bank short codes,
# verified OTP templates). Empty for now — the FP issue is real and left visible.
TRANSACTIONAL_ALLOWLIST_HOOK: list[str] = []


@dataclass
class Classification:
    scam_probability: float
    category: ScamCategory


# --- Category keyword clusters (used for the rule fallback AND to tag category
#     alongside the binary SVM, which has no category head) ------------------
_CATEGORY_KEYWORDS: dict[ScamCategory, list[str]] = {
    ScamCategory.digital_arrest: ["digital arrest", "cbi", "police", "arrest",
        "money laundering", "narcotics", "customs", "enforcement directorate",
        "fir", "warrant", "under surveillance", "safe account"],
    ScamCategory.kyc_update: ["kyc", "verify your account", "account will be blocked",
        "pan card", "update your", "aadhaar update", "re-verify", "reactivate"],
    ScamCategory.investment: ["investment", "guaranteed return", "guaranteed returns",
        "profit", "trading", "double your money", "task", "earn daily", "stock tip"],
    ScamCategory.fake_delivery: ["parcel", "courier", "delivery", "package",
        "customs duty", "shipment", "address confirmation"],
    ScamCategory.refund: ["refund", "cashback", "overpaid", "reversal"],
    ScamCategory.loan: ["pre-approved loan", "instant loan", "loan approved",
        "low interest loan", "processing fee"],
}
_STRONG_SIGNALS = ["digital arrest", "money laundering", "safe account",
    "do not tell anyone", "do not disconnect", "arrest warrant",
    "verify your funds", "otp", "account will be blocked", "stay on the line"]
_BENIGN_SIGNALS = ["meeting", "lunch", "birthday", "see you", "how are you",
    "reschedule"]


def _category(text: str) -> ScamCategory:
    lowered = text.lower()
    best, best_hits = ScamCategory.other, 0
    for cat, words in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for w in words if w in lowered)
        if hits > best_hits:
            best, best_hits = cat, hits
    return best


# --- Trained SVM loading (lazy singleton) -----------------------------------
class _SvmModel:
    def __init__(self, pipe, threshold: float) -> None:
        self.pipe = pipe
        self.threshold = threshold


_svm: _SvmModel | None = None
_svm_tried = False


def _sms_dir() -> Path:
    return Path(settings.sms_model_dir) if settings.sms_model_dir else _DEFAULT_SMS_DIR


def _get_svm() -> _SvmModel | None:
    global _svm, _svm_tried
    if _svm_tried:
        return _svm
    _svm_tried = True
    d = _sms_dir()
    path = d / "sms_classifier.joblib"
    if not path.exists():
        logger.info("SMS model not found at %s — using rule fallback.", d)
        return None
    try:
        import joblib

        # The saved pipeline references the training feature module as
        # ``features_lib``; expose the vendored copy under that name so the
        # pickle resolves. (Single feature implementation, vendored intact.)
        import app.services.sms_features as sms_features

        sys.modules.setdefault("features_lib", sms_features)
        pipe = joblib.load(path)

        threshold = 0.505
        dep = d / "sms_deployment.json"
        if dep.exists():
            import json

            threshold = float(json.load(open(dep)).get("threshold", 0.505))
        _svm = _SvmModel(pipe, threshold)
        logger.info("Loaded trained SMS classifier from %s (threshold %.3f).",
                    d, threshold)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load SMS model (%s); using rule fallback.", exc)
        _svm = None
    return _svm


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _svm_probability(model: _SvmModel, text: str) -> float:
    """Malicious probability = sigmoid of the SVM decision margin (uncalibrated)."""
    if hasattr(model.pipe, "predict_proba"):
        return float(model.pipe.predict_proba([text])[0, 1])
    return _sigmoid(float(model.pipe.decision_function([text])[0]))


# --- Rule fallback ----------------------------------------------------------
def _rule_probability(text: str) -> float:
    lowered = text.lower()
    hits = max((sum(1 for w in words if w in lowered))
               for words in _CATEGORY_KEYWORDS.values())
    strong = sum(1 for s in _STRONG_SIGNALS if s in lowered)
    benign = sum(1 for b in _BENIGN_SIGNALS if b in lowered)
    raw = 0.22 * hits + 0.30 * strong - 0.18 * benign
    return max(0.02, min(0.99, raw))


# --- Public API -------------------------------------------------------------
def classify(text: str) -> Classification:
    """Scam probability + category (SVM if available, else rule fallback)."""
    if not text or not text.strip():
        return Classification(0.02, ScamCategory.other)
    model = _get_svm()
    prob = _svm_probability(model, text) if model else _rule_probability(text)
    return Classification(round(prob, 3), _category(text))


def classify_message(text: str) -> dict:
    """Message-path interface: ``{label, malicious_probability, threshold}``.

    Uses the trained SVM (or the rule fallback). Callers should run the
    known-scammer graph lookup as a fast path BEFORE this.
    """
    model = _get_svm()
    if model is not None:
        prob = _svm_probability(model, text)
        threshold = model.threshold
        source = "trained_svm"
    else:
        prob = _rule_probability(text)
        threshold = 0.5
        source = "rule_fallback"
    return {
        "label": "malicious" if prob >= threshold else "legit",
        "malicious_probability": round(prob, 4),
        "threshold": round(threshold, 4),
        "category": _category(text).value,
        "source": source,
    }

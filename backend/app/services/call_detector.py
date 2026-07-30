"""Call-scam detector — fully local, on-device, deterministic.

The runtime detection path has NO network call. A reasoning model (Groq) was
used ONLY at build time, offline, to generate stage labels on public data
(see ``call_classifier/src/03_annotate_stages.py``). Inference here is:

    local Whisper STT (elsewhere) → shared asr_normalize → trained classifier
    → trained arc tracker (+ deterministic cue backstop) → interrupt rule
    → PRE-WRITTEN de-escalation template.

The interrupt decision is made in code (``CallDetectionState``), not by a model,
so it is thresholdable and auditable. De-escalation messages are pre-written
templates keyed by stage — never generated at runtime (a generated warning to a
panicking victim is a hallucination risk we do not take).

Graceful degradation: if the trained artifacts are missing, the detector falls
back to the local rule-based arc scorer + classifier and keeps serving. Nothing
500s.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.models.enums import STAGE_ORDER, ScamStage
from app.services.arc_scorer import ArcScorer
from app.services.asr_norm import asr_normalize
from app.services.classifier import classify

logger = logging.getLogger("kavach.call_detector")

_DEFAULT_CALL_DIR = Path(__file__).resolve().parent.parent / "ml" / "models" / "call"
_WARN_CONF = 0.7
_WARN_ANY_STAGE_CONF = 0.9

# Deterministic stage cues — backstop the trained arc tracker on the rare later
# stages so the safety-critical interrupt never depends solely on the model.
_STAGE_CUES = {
    "authority_claim": ["police", "cbi", "officer", "department", "government",
                        "bank", "fedex", "courier", "trai", "customs", "interpol",
                        "calling from", "verification team"],
    "accusation": ["money laundering", "arrest", "warrant", "illegal", "drugs",
                   "parcel", "fir", "misused", "suspicious activity",
                   "fraudulent", "non bailable", "complaint against"],
    "isolation": ["do not tell", "dont tell", "do not disconnect",
                  "dont disconnect", "stay on the", "confidential", "do not hang",
                  "dont hang", "under arrest", "surveillance", "do not cut",
                  "digital arrest"],
    "money_demand": ["transfer", "rtgs", "neft", "safe account",
                     "verification account", "otp", "card number", "cvv",
                     "gift card", "bitcoin", "security deposit", "pay the fine"],
}

# Pre-written de-escalation templates (never generated at runtime).
_DE_ESCALATION = {
    "en": {
        "accusation": "Be careful — this call is showing scam warning signs. Do "
        "not act on threats made over a phone call.",
        "isolation": "This is a scam. Real police and agencies never tell you to "
        "keep a call secret or stay on the line. You are not in trouble. Hang up "
        "and talk to someone you trust.",
        "money_demand": "This is a scam. No genuine agency asks you to transfer "
        "money, share an OTP, or move funds to a 'safe account'. Do not pay. Hang "
        "up now.",
    },
    "hi": {
        "accusation": "Saavdhaan — is call mein scam ke sanket hain. Phone par di "
        "gayi dhamki par bharosa na karein.",
        "isolation": "Yeh ek scam hai. Asli police kabhi call chhupane ya line par "
        "bane rehne ko nahi kehti. Ghabraayein nahi. Call kaat dein aur kisi "
        "bharosemand vyakti se baat karein.",
        "money_demand": "Yeh ek scam hai. Koi asli sansthaan paisa transfer, OTP "
        "ya 'safe account' nahi maangti. Paisa na bhejein. Abhi call kaat dein.",
    },
}


@dataclass
class DetectionResult:
    stage: ScamStage
    scam_type: str  # digital_arrest | other_scam | legitimate
    confidence: float
    red_flags: list[str]
    reasoning: str
    de_escalation_message: str
    source: str  # "on_device_model" | "fallback"


@dataclass
class InterruptDecision:
    action: str  # interrupt | warn | monitor
    interrupt: bool
    warn: bool


# --------------------------------------------------------------------------
# Trained-model loading (lazy singleton)
# --------------------------------------------------------------------------
class _Models:
    def __init__(self, clf, arc, threshold: float) -> None:
        self.clf = clf
        self.clf_is_proba = hasattr(clf, "predict_proba")
        self.arc = arc
        self.threshold = threshold


_models: _Models | None = None
_load_tried = False


def _model_dir() -> Path:
    return Path(settings.call_model_dir) if settings.call_model_dir else _DEFAULT_CALL_DIR


def _get_models() -> _Models | None:
    global _models, _load_tried
    if _load_tried:
        return _models
    _load_tried = True
    d = _model_dir()
    clf_path = d / "call_classifier.joblib"
    if not clf_path.exists():
        logger.info("Call models not found at %s — using rule-based fallback.", d)
        return None
    try:
        import joblib

        clf = joblib.load(clf_path)
        arc_path = d / "call_arc_tracker.joblib"
        arc = joblib.load(arc_path) if arc_path.exists() else None
        threshold = settings.interrupt_threshold
        _models = _Models(clf, arc, threshold)
        logger.info("Loaded on-device call models from %s.", d)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load call models (%s); using fallback.", exc)
        _models = None
    return _models


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _rule_stage(norm: str) -> tuple[str, list[str]]:
    """Highest cue-evidenced stage + the red flags that fired."""
    highest = "none"
    flags: list[str] = []
    for stage in ("authority_claim", "accusation", "isolation", "money_demand"):
        for cue in _STAGE_CUES[stage]:
            if cue in norm:
                flags.append(cue)
                if STAGE_ORDER[stage] > STAGE_ORDER[highest]:
                    highest = stage
                break
    return highest, flags


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
def detect(transcript: str) -> DetectionResult:
    """Assess the transcript-so-far with the local trained models (or fallback)."""
    if not transcript or not transcript.strip():
        return DetectionResult(ScamStage.none, "legitimate", 0.0, [], "", "",
                               "on_device_model")
    models = _get_models()
    if models is None:
        return _fallback_detect(transcript)

    norm = asr_normalize(transcript)
    # scam probability from the trained classifier.
    if models.clf_is_proba:
        prob = float(models.clf.predict_proba([norm])[0, 1])
    else:
        prob = _sigmoid(float(models.clf.decision_function([norm])[0]))

    # stage = max(trained arc, deterministic cue floor).
    model_stage = "none"
    if models.arc is not None:
        try:
            model_stage = str(models.arc.predict([norm])[0])
        except Exception:
            model_stage = "none"
    rule_stage, flags = _rule_stage(norm)
    stage = model_stage if STAGE_ORDER.get(model_stage, 0) >= STAGE_ORDER[rule_stage] else rule_stage
    stage_enum = ScamStage(stage) if stage in {s.value for s in ScamStage} else ScamStage.none

    if prob < 0.4:
        scam_type = "legitimate"
    elif STAGE_ORDER[stage_enum.value] >= STAGE_ORDER["isolation"] or "digital arrest" in norm:
        scam_type = "digital_arrest"
    else:
        scam_type = "other_scam"

    return DetectionResult(
        stage=stage_enum,
        scam_type=scam_type,
        confidence=round(prob, 4),
        red_flags=flags[:6],
        reasoning="On-device classifier + arc tracker.",
        de_escalation_message="",  # filled by the interrupt state on fire
        source="on_device_model",
    )


def _fallback_detect(transcript: str) -> DetectionResult:
    """Rule-based fallback: arc scorer + rule classifier (no artifacts present)."""
    classification = classify(transcript)
    arc = ArcScorer().evaluate_once(transcript, classification.scam_probability)
    confidence = round(min(1.0, 0.6 * classification.scam_probability
                           + 0.4 * arc.confidence), 3)
    if arc.stage != ScamStage.none and classification.category.value == "digital_arrest":
        scam_type = "digital_arrest"
    elif confidence >= 0.4:
        scam_type = "other_scam"
    else:
        scam_type = "legitimate"
    return DetectionResult(
        stage=arc.stage, scam_type=scam_type, confidence=confidence,
        red_flags=list(arc.red_flags), reasoning="Rule-based fallback.",
        de_escalation_message="", source="fallback",
    )


def de_escalation(stage: ScamStage, language: str = "en") -> str:
    """Return the pre-written template for the given stage (or empty)."""
    if stage == ScamStage.money_demand:
        key = "money_demand"
    elif stage == ScamStage.accusation:
        key = "accusation"
    else:
        key = "isolation"
    return _DE_ESCALATION.get(language, _DE_ESCALATION["en"]).get(key, "")


# --------------------------------------------------------------------------
# Deterministic interrupt state (unchanged contract; in code, not a model)
# --------------------------------------------------------------------------
@dataclass
class CallDetectionState:
    threshold: float = field(default_factory=lambda: settings.interrupt_threshold)
    highest_stage: ScamStage = ScamStage.none
    max_confidence: float = 0.0
    interrupt_fired: bool = False
    last_result: DetectionResult | None = None

    def update(self, result: DetectionResult) -> InterruptDecision:
        if STAGE_ORDER[result.stage.value] > STAGE_ORDER[self.highest_stage.value]:
            self.highest_stage = result.stage
        self.max_confidence = max(self.max_confidence, result.confidence)
        self.last_result = result
        action = self._decide(result)
        if action == "interrupt":
            self.interrupt_fired = True
        return InterruptDecision(action, self.interrupt_fired, action == "warn")

    def _decide(self, r: DetectionResult) -> str:
        if self.interrupt_fired:
            return "interrupt"
        order = STAGE_ORDER[self.highest_stage.value]
        iso = STAGE_ORDER[ScamStage.isolation.value]
        money = STAGE_ORDER[ScamStage.money_demand.value]
        accusation = STAGE_ORDER[ScamStage.accusation.value]
        if r.scam_type == "legitimate":
            return "monitor"
        if order >= money:
            return "interrupt"
        if r.confidence >= self.threshold and order >= iso:
            return "interrupt"
        if (r.confidence >= _WARN_CONF and order >= accusation) or (
            r.confidence >= _WARN_ANY_STAGE_CONF
        ):
            return "warn"
        return "monitor"


def runtime_is_local() -> bool:
    """Always True — the runtime detection path makes no network call."""
    return True


# Backwards-compat shim: older callers imported prompt_version(); the runtime no
# longer uses a prompt. Kept so imports do not break.
def prompt_version() -> str:  # pragma: no cover
    return "on-device-v1"

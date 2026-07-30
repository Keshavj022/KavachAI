"""Detection engine — orchestrates the full pipeline into a verdict.

Pipeline (CLAUDE.md Section 8):
  1. extract identifiers
  2. known-scammer check first (cheap DB lookup on the fraud graph)
  3. fast classifier (transformer or rule fallback)
  4. arc scorer (stateful for calls; one-shot for messages)
  5. LLM reasoning for the human explanation (Ollama or templated fallback)
  6. RAG grounding attaches cited sources (wired in Phase 2)

The verdict object is enriched as it flows through and returned to the caller.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ScamCategory, ScamStage, Verdict
from app.models.identifier import Identifier
from app.schemas.detection import Source, VerdictOut
from app.services import classifier as classifier_svc
from app.services import llm as llm_svc
from app.services.arc_scorer import ArcResult, ArcScorer
from app.services.extractor import ExtractedIdentifier, extract_identifiers

logger = logging.getLogger("kavach.detection")

# Risk at/above which a matched identifier alone yields a scam verdict.
KNOWN_SCAMMER_RISK = 0.7

# Verdict thresholds on the combined confidence.
_SCAM_THRESHOLD = 0.7
_SUSPICIOUS_THRESHOLD = 0.4


def known_scammer_lookup(
    db: Session, identifiers: list[ExtractedIdentifier]
) -> Identifier | None:
    """Return the highest-risk matching known identifier, if any.

    This is the fastest and cheapest path: if the collective network already
    knows a number/UPI/account, we do not need any model to reach a verdict.
    """
    if not identifiers:
        return None
    values = [i.value for i in identifiers]
    # Case-insensitive match on value.
    stmt = (
        select(Identifier)
        .where(func.lower(Identifier.value).in_([v.lower() for v in values]))
        .order_by(Identifier.risk_score.desc())
    )
    return db.scalars(stmt).first()


def _verdict_from_confidence(confidence: float) -> Verdict:
    if confidence >= _SCAM_THRESHOLD:
        return Verdict.scam
    if confidence >= _SUSPICIOUS_THRESHOLD:
        return Verdict.suspicious
    return Verdict.safe


def _combine_confidence(classifier_prob: float, arc_conf: float) -> float:
    """Blend the classifier probability with the arc-derived confidence."""
    return round(min(1.0, 0.6 * classifier_prob + 0.4 * arc_conf), 3)


def analyze_message(
    db: Session,
    content: str,
    channel: str,
    *,
    attach_sources: list[Source] | None = None,
    with_explanation: bool = True,
) -> VerdictOut:
    """Analyse a standalone message (Fraud Shield SMS/WhatsApp check)."""
    identifiers = extract_identifiers(content)

    # 2) Known-scammer fast path.
    match = known_scammer_lookup(db, identifiers)
    classification = classifier_svc.classify(content)

    if match is not None and match.risk_score >= KNOWN_SCAMMER_RISK:
        explanation = (
            f"This {match.type} has already been reported by others as a scam "
            f"({match.report_count} report(s)). Do not engage, do not pay, and "
            "block the sender."
        )
        return VerdictOut(
            verdict=Verdict.scam,
            confidence=round(max(match.risk_score, classification.scam_probability), 3),
            category=classification.category,
            red_flags=[f"Known reported {match.type}: {match.value}"],
            explanation=explanation,
            sources=attach_sources or [],
            known_scammer=True,
            stage=ScamStage.none,
        )

    # 3) The trained SMS model decides the verdict (the known-scammer graph
    #    lookup above is the fast path that runs BEFORE the model).
    sms = classifier_svc.classify_message(content)
    prob = sms["malicious_probability"]
    threshold = sms["threshold"]
    category = ScamCategory(sms["category"]) if sms["category"] in {c.value for c in ScamCategory} \
        else classification.category

    # 4) Arc scoring adds human-readable red flags / stage context.
    arc: ArcResult = ArcScorer().evaluate_once(content, prob)

    if sms["label"] == "malicious":
        verdict = Verdict.scam
    elif prob >= max(0.4, threshold - 0.1):
        verdict = Verdict.suspicious
    else:
        verdict = Verdict.safe

    # 5) Explanation (local templated / Ollama — never on the runtime scam path
    #    of the call flow; this is the message path).
    explanation = ""
    if with_explanation:
        explanation = llm_svc.generate_explanation(
            transcript=content,
            stage=arc.stage,
            red_flags=arc.red_flags,
            category=category,
            verdict=verdict,
        )

    return VerdictOut(
        verdict=verdict,
        confidence=round(prob, 3),
        category=category,
        red_flags=arc.red_flags,
        explanation=explanation,
        sources=attach_sources or [],
        known_scammer=False,
        stage=arc.stage,
    )


def analyze_transcript_tick(
    db: Session,
    scorer: ArcScorer,
    transcript: str,
) -> tuple[VerdictOut, ArcResult]:
    """Analyse the accumulated call transcript for one streaming tick.

    Returns the enriched verdict plus the raw ArcResult (the WS handler uses
    the latter to decide when to run the — relatively expensive — LLM
    explanation, i.e. only once the interrupt fires).
    """
    identifiers = extract_identifiers(transcript)
    classification = classifier_svc.classify(transcript)

    # Known-scammer fast path also applies mid-call (e.g. caller states a UPI).
    match = known_scammer_lookup(db, identifiers)
    known = bool(match is not None and match.risk_score >= KNOWN_SCAMMER_RISK)

    arc = scorer.update(transcript, classification.scam_probability)

    confidence = _combine_confidence(classification.scam_probability, arc.confidence)
    if known:
        confidence = max(confidence, match.risk_score if match else 0.0)

    verdict = _verdict_from_confidence(confidence)
    if known:
        verdict = Verdict.scam

    red_flags = list(arc.red_flags)
    if known and match is not None:
        red_flags.insert(0, f"Known reported {match.type}: {match.value}")

    verdict_out = VerdictOut(
        verdict=verdict,
        confidence=confidence,
        category=classification.category,
        red_flags=red_flags,
        explanation="",  # filled by the WS handler when the interrupt fires
        sources=[],
        known_scammer=known,
        stage=arc.stage,
    )
    # Carry the (possibly boosted) confidence/verdict back onto the ArcResult
    # so the WS handler sees the final numbers.
    arc.confidence = confidence
    return verdict_out, arc

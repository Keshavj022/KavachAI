"""Detection routes: message check and identifier lookup."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.enums import ScamStage, Verdict
from app.models.user import User
from app.rate_limit import limiter
from app.services import detection_engine
from app.services.extractor import ExtractedIdentifier
from app.services.rag import retrieve_sources
from app.schemas.detection import MessageCheckRequest, VerdictOut

router = APIRouter(prefix="/api", tags=["detection"])


@router.post("/detect/message", response_model=VerdictOut)
@limiter.limit("30/minute")
def check_message(
    request: Request,
    payload: MessageCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check a pasted SMS/WhatsApp message and return a grounded verdict."""
    # RAG grounding: retrieve advisory sources relevant to the content.
    sources = retrieve_sources(payload.content, k=1)
    return detection_engine.analyze_message(
        db, payload.content, payload.channel, attach_sources=sources
    )


@router.get("/identifier/lookup", response_model=VerdictOut)
@limiter.limit("60/minute")
def lookup_identifier(
    request: Request,
    value: str = Query(min_length=3, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Known-scammer check for a single identifier value.

    This is the flywheel's payoff (demo step 7): once the network knows a
    number/UPI/account, any citizen who checks it gets an instant verdict with
    no model in the loop.
    """
    # Treat the raw value as a phone by default but also let the extractor
    # normalise it (so "+91 98123 45678" matches the stored "+919812345678").
    from app.services.extractor import extract_identifiers

    extracted = extract_identifiers(value)
    if not extracted:
        # Fall back to matching the literal value.
        from app.models.enums import IdentifierType

        extracted = [ExtractedIdentifier(type=IdentifierType.phone, value=value.strip())]

    match = detection_engine.known_scammer_lookup(db, extracted)
    if match is not None and match.risk_score >= detection_engine.KNOWN_SCAMMER_RISK:
        return VerdictOut(
            verdict=Verdict.scam,
            confidence=round(match.risk_score, 3),
            category=Verdict.scam and _category_hint(match.type),
            red_flags=[
                f"Known reported {match.type}: {match.value}",
                f"Reported {match.report_count} time(s) by the network",
            ],
            explanation=(
                f"This {match.type} is already flagged in the fraud network. "
                "Do not engage, do not pay, and block it."
            ),
            sources=[],
            known_scammer=True,
            stage=ScamStage.none,
        )

    return VerdictOut(
        verdict=Verdict.safe,
        confidence=0.05,
        category=_category_hint("other"),
        red_flags=[],
        explanation="This identifier is not in the fraud network. Stay alert, "
        "but there is no known report against it.",
        sources=[],
        known_scammer=False,
        stage=ScamStage.none,
    )


def _category_hint(_id_type: str):
    """Lookup verdicts are identifier-based, so category is not meaningful."""
    from app.models.enums import ScamCategory

    return ScamCategory.other

"""Fraud-intelligence write path — turns a report into graph knowledge.

When a citizen files a report, the identifiers in it are upserted into the
shared identifier store, their risk and report counts are raised, and every
pair of identifiers in the same report is linked with a co-reported edge. This
is the write half of the flywheel: one citizen's report makes the next
citizen's known-scammer lookup succeed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.identifier import Identifier, IdentifierLink
from app.models.report import Report
from app.services.extractor import ExtractedIdentifier, extract_identifiers

# A single explicit citizen report is a strong signal: a brand-new identifier
# starts at/above the known-scammer threshold so the flywheel pays off after
# the very first report (demo step 7). Repeat reports push it higher.
_FIRST_REPORT_RISK = 0.72
_RISK_INCREMENT = 0.06
_RISK_CAP = 0.99


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _find_identifier(db: Session, value: str) -> Identifier | None:
    return db.scalar(
        select(Identifier).where(func.lower(Identifier.value) == value.lower())
    )


def _upsert_link(
    db: Session, a: Identifier, b: Identifier, reason: str = "co-reported"
) -> None:
    """Create a co-report edge between two identifiers, or bump its weight."""
    existing = db.scalar(
        select(IdentifierLink).where(
            IdentifierLink.source_id.in_([a.id, b.id]),
            IdentifierLink.target_id.in_([a.id, b.id]),
        )
    )
    if existing is not None:
        existing.weight = min(1.0, existing.weight + 0.1)
        return
    db.add(
        IdentifierLink(source_id=a.id, target_id=b.id, weight=0.6, reason=reason)
    )


def ingest_report_identifiers(
    db: Session, report: Report, extra_values: list[str] | None = None
) -> list[Identifier]:
    """Extract, upsert, risk-score and link identifiers for a report.

    ``extra_values`` lets the client add identifiers explicitly (e.g. the
    scammer's number typed into the report form) on top of whatever the
    extractor finds in the report content.
    """
    extracted: list[ExtractedIdentifier] = extract_identifiers(report.content or "")
    for value in extra_values or []:
        extracted.extend(extract_identifiers(value))

    # De-duplicate by (type, value).
    seen: dict[tuple[str, str], ExtractedIdentifier] = {}
    for ex in extracted:
        seen[(ex.type.value, ex.value.lower())] = ex

    idents: list[Identifier] = []
    for ex in seen.values():
        ident = _find_identifier(db, ex.value)
        if ident is None:
            ident = Identifier(
                type=ex.type.value,
                value=ex.value,
                risk_score=_FIRST_REPORT_RISK,
                report_count=1,
                first_seen=_utcnow(),
            )
            db.add(ident)
            db.flush()  # assign an id for linking
        else:
            ident.report_count += 1
            ident.risk_score = min(_RISK_CAP, ident.risk_score + _RISK_INCREMENT)
        idents.append(ident)

    report.identifiers = idents

    # Co-report edges: every pair in this report is linked.
    for i in range(len(idents)):
        for j in range(i + 1, len(idents)):
            _upsert_link(db, idents[i], idents[j], reason="co-reported")

    db.commit()
    for ident in idents:
        db.refresh(ident)
    return idents

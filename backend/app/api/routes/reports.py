"""Report routes: create, list (RBAC), detail."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user
from app.database import get_db
from app.models.call import CallSession
from app.models.enums import Role, ScamCategory, Verdict
from app.models.report import Report
from app.models.user import User
from app.rate_limit import limiter
from app.schemas.report import ReportCreate, ReportCreateResponse, ReportOut
from app.services.alerts import alert_trusted_contacts
from app.services.evidence import preserve_evidence
from app.services.intelligence import ingest_report_identifiers

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _to_out(report: Report, *, alerts_sent: int = 0) -> ReportOut:
    """Build a ReportOut, filling the non-column fields."""
    out = ReportOut.model_validate(report)
    out.reporter_name = report.user.full_name if report.user else None
    out.alerts_sent = alerts_sent
    return out


@router.post("", response_model=ReportCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_report(
    request: Request,
    payload: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """File a report, ingest its identifiers into the graph, and alert contacts.

    This is the flywheel's write step: identifiers are learned here so the next
    citizen who is contacted by the same number gets an instant verdict.
    """
    report = Report(
        user_id=current_user.id,
        call_session_id=payload.call_session_id,
        channel=payload.channel.value,
        scam_category=payload.scam_category.value,
        content=payload.content,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        location_label=payload.location_label,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Learn identifiers (extracted + explicitly supplied).
    ingest_report_identifiers(db, report, extra_values=payload.identifier_values)

    # Preserve evidence ONLY for a confirmed-scam call session. Encrypted +
    # hashed, authority-access only — never returned to the citizen.
    if payload.call_session_id is not None:
        session = db.get(CallSession, payload.call_session_id)
        if (
            session is not None
            and session.user_id == current_user.id
            and session.outcome == Verdict.scam.value
            and session.transcript
        ):
            preserve_evidence(db, report, session.transcript)

    # Break isolation: alert trusted contacts on a genuine scam report.
    alerts_sent = 0
    if payload.notify_contacts and payload.scam_category != ScamCategory.other:
        alerts = alert_trusted_contacts(db, current_user)
        alerts_sent = len(alerts)

    db.refresh(report)
    return _to_out(report, alerts_sent=alerts_sent)


@router.get("", response_model=list[ReportOut])
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    """List reports. Citizens see only their own; authorities see all."""
    stmt = (
        select(Report)
        .options(selectinload(Report.identifiers), selectinload(Report.user))
        .order_by(Report.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if current_user.role != Role.authority.value:
        stmt = stmt.where(Report.user_id == current_user.id)

    reports = db.scalars(stmt).all()
    return [_to_out(r) for r in reports]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a single report. Citizens may only read their own."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if (
        current_user.role != Role.authority.value
        and report.user_id != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    return _to_out(report)

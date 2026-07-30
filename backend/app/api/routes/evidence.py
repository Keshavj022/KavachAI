"""Evidence access — authority role only.

Citizens receive 403 here by construction (``require_role('authority')``);
they can never view or download evidence of a call they were part of.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.database import get_db
from app.models.enums import Role
from app.models.evidence import Evidence
from app.models.report import Report
from app.models.user import User
from app.schemas.evidence import EvidenceList, EvidenceMeta
from app.services.evidence import decrypt_evidence

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/{report_id}", response_model=EvidenceList)
def get_evidence(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(Role.authority)),
):
    """Return preserved evidence metadata (+ decrypted preview) for a report."""
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    rows = db.scalars(
        select(Evidence).where(Evidence.report_id == report_id)
    ).all()

    items: list[EvidenceMeta] = []
    for ev in rows:
        plaintext = decrypt_evidence(ev)
        preview = None
        if plaintext:
            preview = plaintext if len(plaintext) <= 600 else plaintext[:600] + "…"
        items.append(
            EvidenceMeta(
                id=ev.id,
                sha256_hash=ev.sha256_hash,
                created_at=ev.created_at,
                preview=preview,
            )
        )
    return EvidenceList(items=items)

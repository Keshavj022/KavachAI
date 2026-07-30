"""Authority intelligence routes: fraud graph, node detail, dashboard stats.

All routes are gated to the ``authority`` role.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import require_role
from app.database import get_db
from app.models.enums import Role
from app.models.identifier import Identifier, IdentifierLink
from app.models.report import Report
from app.models.user import User
from app.services.graph_service import build_graph, ring_summary

router = APIRouter(prefix="/api", tags=["intelligence"])

_authority = require_role(Role.authority)


@router.get("/graph")
def get_graph(
    db: Session = Depends(get_db),
    _: User = Depends(_authority),
) -> dict:
    """Return the full fraud-network graph as ``{nodes, links}``."""
    return build_graph(db)


@router.get("/graph/node/{identifier_id}")
def get_node_detail(
    identifier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_authority),
) -> dict:
    """Return an identifier's neighbours and the reports that reference it."""
    ident = db.get(Identifier, identifier_id)
    if ident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identifier not found")

    # Neighbour identifiers via links in either direction.
    link_rows = db.scalars(
        select(IdentifierLink).where(
            or_(
                IdentifierLink.source_id == identifier_id,
                IdentifierLink.target_id == identifier_id,
            )
        )
    ).all()
    neighbour_ids = {
        (ln.target_id if ln.source_id == identifier_id else ln.source_id)
        for ln in link_rows
    }
    neighbours = (
        db.scalars(select(Identifier).where(Identifier.id.in_(neighbour_ids))).all()
        if neighbour_ids
        else []
    )

    reports = ident.reports
    return {
        "identifier": {
            "id": ident.id,
            "type": ident.type,
            "value": ident.value,
            "risk": round(ident.risk_score, 3),
            "reports": ident.report_count,
            "first_seen": ident.first_seen.isoformat(),
        },
        "linked_identifiers": [
            {"id": n.id, "type": n.type, "value": n.value, "risk": round(n.risk_score, 3)}
            for n in neighbours
        ],
        "reports": [
            {
                "id": r.id,
                "scam_category": r.scam_category,
                "channel": r.channel,
                "created_at": r.created_at.isoformat(),
                "status": r.status,
            }
            for r in reports
        ],
    }


@router.get("/authority/stats")
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(_authority),
) -> dict:
    """Dashboard summary: totals, category breakdown, recent trend, top rings."""
    total_reports = db.scalar(select(func.count(Report.id))) or 0
    total_identifiers = db.scalar(select(func.count(Identifier.id))) or 0
    high_risk = (
        db.scalar(select(func.count(Identifier.id)).where(Identifier.risk_score >= 0.7))
        or 0
    )

    # Category breakdown.
    cat_rows = db.execute(
        select(Report.scam_category, func.count(Report.id)).group_by(Report.scam_category)
    ).all()
    categories = [{"category": c, "count": n} for c, n in cat_rows]

    # 7-day trend by day.
    now = datetime.now(timezone.utc)
    recent = db.scalars(
        select(Report).where(Report.created_at >= now - timedelta(days=7))
    ).all()
    day_counts: Counter[str] = Counter()
    for r in recent:
        day_counts[r.created_at.strftime("%Y-%m-%d")] += 1
    trend = [
        {
            "date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
            "count": day_counts.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0),
        }
        for i in range(6, -1, -1)
    ]

    rings = ring_summary(db)
    return {
        "total_reports": total_reports,
        "total_identifiers": total_identifiers,
        "high_risk_identifiers": high_risk,
        "active_rings": len(rings),
        "categories": categories,
        "trend": trend,
        "top_rings": rings[:5],
    }

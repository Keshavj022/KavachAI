"""Decoy intelligence-package persistence.

One row per generated package. Ownership is by ``user_id`` (the citizen the
decoy protected). The package JSON is stored inline; the encrypted audio/
transcript evidence lives in the shared ``Evidence`` table (authority-only) and
is linked by ``evidence_id``. Identifiers are ingested into the fraud graph via
the linked ``Report``.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecoyPackage(Base):
    __tablename__ = "decoy_packages"

    # UUID string primary key (the package_id surfaced in the API).
    package_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id"), nullable=True
    )
    evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence.id"), nullable=True
    )
    # Full package as JSON text (identifiers, formatters, FIR narrative, ...).
    package_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Mock-submission bookkeeping.
    submission_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submission_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

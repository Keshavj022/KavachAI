"""Fraud identifiers and the links between them.

These two tables are the data spine of the intelligence layer: identifiers
(phone / UPI / account / URL / device) are extracted from reports and calls,
and links between co-reported identifiers form the edges the fraud-network
graph and ring-clustering operate on.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Association table: a report references many identifiers; an identifier
# appears in many reports.
report_identifiers = Table(
    "report_identifiers",
    Base.metadata,
    Column("report_id", ForeignKey("reports.id"), primary_key=True),
    Column("identifier_id", ForeignKey("identifiers.id"), primary_key=True),
)


class Identifier(Base):
    __tablename__ = "identifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    # IdentifierType enum value
    type: Mapped[str] = mapped_column(String(16), index=True)
    value: Mapped[str] = mapped_column(String(255), index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    report_count: Mapped[int] = mapped_column(Integer, default=0)

    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        secondary=report_identifiers, back_populates="identifiers"
    )


class IdentifierLink(Base):
    """A weighted edge between two identifiers (co-reported, shared device...)."""

    __tablename__ = "identifier_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("identifiers.id"), index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("identifiers.id"), index=True
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str] = mapped_column(String(64), default="co-reported")

    source: Mapped["Identifier"] = relationship(foreign_keys=[source_id])
    target: Mapped["Identifier"] = relationship(foreign_keys=[target_id])

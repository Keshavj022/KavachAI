"""Citizen fraud report."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.identifier import report_identifiers


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    call_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("call_sessions.id"), nullable=True
    )
    # Channel enum value
    channel: Mapped[str] = mapped_column(String(16), default="call")
    # ScamCategory enum value
    scam_category: Mapped[str] = mapped_column(String(32), default="other")
    content: Mapped[str] = mapped_column(Text, default="")
    # ReportStatus enum value
    status: Mapped[str] = mapped_column(String(16), default="filed", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )
    # Optional geolocation for the authority hotspot map.
    location_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    user: Mapped["User"] = relationship(back_populates="reports")  # noqa: F821
    call_session: Mapped["CallSession | None"] = relationship(  # noqa: F821
        back_populates="reports"
    )
    identifiers: Mapped[list["Identifier"]] = relationship(  # noqa: F821
        secondary=report_identifiers, back_populates="reports"
    )
    evidence: Mapped[list["Evidence"]] = relationship(  # noqa: F821
        back_populates="report", cascade="all, delete-orphan"
    )

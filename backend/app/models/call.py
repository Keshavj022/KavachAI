"""Call session model — one live (or simulated) call under detection."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    max_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # Verdict enum value: safe | suspicious | scam
    outcome: Mapped[str] = mapped_column(String(16), default="safe")
    # ScamStage enum value
    stage_reached: Mapped[str] = mapped_column(String(32), default="none")
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="call_sessions")  # noqa: F821
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        back_populates="call_session"
    )

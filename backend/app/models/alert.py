"""Trusted-contact alert record.

An alert is written whenever a scam is confirmed and a trusted contact is
notified. ``simulated`` is True when Twilio credentials are absent and the
alert was only logged, keeping the demo honest about what actually happened.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    trusted_contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("trusted_contacts.id"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(16), default="sms")
    # AlertStatus enum value
    status: Mapped[str] = mapped_column(String(16), default="pending")
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    trusted_contact: Mapped["TrustedContact | None"] = relationship()  # noqa: F821

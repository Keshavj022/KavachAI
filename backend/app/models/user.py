"""User and trusted-contact models."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    # Stored as text; validated against the Role enum at the schema layer.
    role: Mapped[str] = mapped_column(String(32), default="citizen", index=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    trusted_contacts: Mapped[list["TrustedContact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    call_sessions: Mapped[list["CallSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))

    user: Mapped["User"] = relationship(back_populates="trusted_contacts")

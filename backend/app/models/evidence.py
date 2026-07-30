"""Preserved evidence — encrypted, hashed, authority-access only.

By design the encrypted blob and hash are never exposed to the citizen who
was recorded. Only an authenticated ``authority`` user can decrypt via the
evidence endpoint. This removes the misuse incentive behind consumer call
recording while still giving investigators a tamper-evident artefact.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    # Fernet-encrypted segment (audio bytes or transcript segment).
    encrypted_blob: Mapped[bytes] = mapped_column(LargeBinary)
    # SHA-256 of the plaintext, for tamper-evidence.
    sha256_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Fixed to "authority": encodes the access rule at the data layer.
    access_role: Mapped[str] = mapped_column(String(16), default="authority")

    report: Mapped["Report"] = relationship(back_populates="evidence")  # noqa: F821

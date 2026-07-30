"""Evidence preservation — encrypt, hash, store; authority-only decryption.

Privacy / anti-misuse design (CLAUDE.md Sections 1 & 10):

  * Evidence is preserved ONLY when a scam is confirmed — never for normal
    calls.
  * The segment is encrypted at rest with Fernet (AES) using ``EVIDENCE_KEY``.
  * A SHA-256 hash of the plaintext is stored for tamper-evidence.
  * Decryption is exposed only to the ``authority`` role. The citizen who was
    recorded can never view or download it. This removes the misuse incentive
    that got consumer call recording locked down on modern phones.
"""

from __future__ import annotations

import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.models.evidence import Evidence
from app.models.report import Report

logger = logging.getLogger("kavach.evidence")


def _load_fernet() -> Fernet:
    """Return a Fernet using EVIDENCE_KEY, or a volatile key if unset.

    A volatile key keeps the app running on a fresh clone (evidence survives
    only for the process lifetime). In production EVIDENCE_KEY must be set so
    preserved evidence remains decryptable across restarts.
    """
    key = settings.evidence_key.strip()
    if not key:
        if not hasattr(_load_fernet, "_volatile"):
            _load_fernet._volatile = Fernet.generate_key()  # type: ignore[attr-defined]
            logger.warning(
                "EVIDENCE_KEY not set — using a volatile key. Preserved evidence "
                "will not survive a restart. Set EVIDENCE_KEY in production."
            )
        key = _load_fernet._volatile  # type: ignore[attr-defined]
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        logger.error("Invalid EVIDENCE_KEY (%s); using a volatile key instead.", exc)
        _load_fernet._volatile = Fernet.generate_key()  # type: ignore[attr-defined]
        return Fernet(_load_fernet._volatile)  # type: ignore[attr-defined]


def preserve_evidence(db: Session, report: Report, plaintext: str) -> Evidence:
    """Encrypt and store a plaintext segment as evidence for a report."""
    data = plaintext.encode("utf-8")
    sha256 = hashlib.sha256(data).hexdigest()
    encrypted = _load_fernet().encrypt(data)

    evidence = Evidence(
        report_id=report.id,
        encrypted_blob=encrypted,
        sha256_hash=sha256,
        access_role="authority",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    logger.info("Preserved evidence %s for report %s.", evidence.id, report.id)
    return evidence


def decrypt_evidence(evidence: Evidence) -> str | None:
    """Decrypt an evidence blob. Returns None if the key cannot open it.

    Also re-verifies the SHA-256 hash so tampering is detectable.
    """
    try:
        plaintext = _load_fernet().decrypt(bytes(evidence.encrypted_blob))
    except InvalidToken:
        logger.warning("Evidence %s could not be decrypted (key mismatch).", evidence.id)
        return None
    if hashlib.sha256(plaintext).hexdigest() != evidence.sha256_hash:
        logger.error("Evidence %s failed integrity check!", evidence.id)
        return None
    return plaintext.decode("utf-8", errors="replace")

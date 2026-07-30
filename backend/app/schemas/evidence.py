"""Evidence response schemas (authority only)."""

from datetime import datetime

from pydantic import BaseModel


class EvidenceMeta(BaseModel):
    id: int
    sha256_hash: str
    created_at: datetime
    # A short decrypted preview for the investigator. In production this would
    # be a controlled, audited disclosure; here it is a transcript snippet.
    preview: str | None = None


class EvidenceList(BaseModel):
    items: list[EvidenceMeta]

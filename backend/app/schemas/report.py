"""Report schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Channel, IdentifierType, ReportStatus, ScamCategory


class IdentifierBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: IdentifierType
    value: str
    risk_score: float
    report_count: int


class ReportCreate(BaseModel):
    call_session_id: int | None = None
    channel: Channel = Channel.call
    scam_category: ScamCategory = ScamCategory.digital_arrest
    content: str = Field(default="", max_length=8000)
    location_label: str | None = Field(default=None, max_length=128)
    location_lat: float | None = None
    location_lng: float | None = None
    # Identifiers typed in explicitly (e.g. the scammer's number).
    identifier_values: list[str] = Field(default_factory=list)
    # Whether to notify the reporter's trusted contacts (breaks isolation).
    notify_contacts: bool = True


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel: Channel
    scam_category: ScamCategory
    content: str
    status: ReportStatus
    created_at: datetime
    location_lat: float | None
    location_lng: float | None
    location_label: str | None
    identifiers: list[IdentifierBrief] = []
    reporter_name: str | None = None
    alerts_sent: int = 0


class ReportCreateResponse(ReportOut):
    """Report plus how many trusted-contact alerts were dispatched."""

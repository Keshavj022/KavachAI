"""Call session schemas."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ScamStage, Verdict


class CallStartResponse(BaseModel):
    session_id: int
    demo_scripts: list[str]


class CallSummary(BaseModel):
    session_id: int
    started_at: datetime
    ended_at: datetime | None
    transcript: str
    max_confidence: float
    outcome: Verdict
    stage_reached: ScamStage
    interrupted: bool

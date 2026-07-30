"""Detection / verdict schemas shared by the message-check and WS endpoints."""

from pydantic import BaseModel, Field

from app.models.enums import ScamCategory, ScamStage, Verdict


class MessageCheckRequest(BaseModel):
    """Request to check an SMS / WhatsApp / pasted message in Fraud Shield."""

    content: str = Field(min_length=1, max_length=8000)
    channel: str = Field(default="sms", max_length=16)


class Source(BaseModel):
    """A cited RAG source backing the verdict."""

    title: str
    snippet: str
    ref: str = ""


class VerdictOut(BaseModel):
    """The enriched verdict object flowing through the detection layer."""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    category: ScamCategory
    red_flags: list[str] = []
    explanation: str = ""
    sources: list[Source] = []
    known_scammer: bool = False
    stage: ScamStage = ScamStage.none


class WSMessage(BaseModel):
    """A server→client frame on the live-call websocket."""

    partial_transcript: str = ""
    stage: ScamStage = ScamStage.none
    confidence: float = 0.0
    verdict: Verdict = Verdict.safe
    interrupt: bool = False
    # Softer, non-takeover cue (high confidence before the interrupt stage).
    warn: bool = False
    explanation: str | None = None
    red_flags: list[str] = []
    sources: list[Source] = []
    known_scammer: bool = False
    # "groq" when the cloud few-shot detector produced this frame, "fallback"
    # when the local rule-based scorer did. Surfaced for transparency.
    detector: str = "fallback"
    done: bool = False

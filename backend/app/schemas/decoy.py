"""Decoy API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DecoyStartRequest(BaseModel):
    language: str = "hi"
    demo_mode: bool = True
    scenario: str | None = None  # "digital_arrest" | "tech_support"


class DecoyStartResponse(BaseModel):
    session_id: int
    greeting_text: str
    persona_intro_audio_url: str | None = None
    demo_scripts: list[str]


class SubmitResponse(BaseModel):
    submission_id: str
    status: str
    channel: str

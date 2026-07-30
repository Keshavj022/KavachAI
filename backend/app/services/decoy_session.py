"""Decoy session state + the deterministic mode/interrupt rules.

One ``DecoySession`` holds everything accumulated over a single decoy call:
the rolling transcript, the extracted intelligence, the detection state
(scam probability + arc stage), timers, and the current agent mode.

The mode decision (MONITOR / STALL / WRAP_UP) and the "is this a scam" verdict
are **deterministic** — computed here in code from the classifier + arc tracker
outputs, never by the LLM. The LLM only authors Ramesh's conversational line.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import settings
from app.models.enums import STAGE_ORDER, ScamStage
from app.services.entity_extractor import Amount, ExtractedEntities, extract_entities
from app.services.persona import AgentMode

# Thresholds (mirrors the trained call detector; configurable).
INTERRUPT_THRESHOLD = settings.interrupt_threshold          # default 0.735 via env
STALL_PROB_THRESHOLD = 0.6
MAX_DECOY_TURNS = 40
MAX_DECOY_SECONDS = 1800  # 30 minutes


@dataclass
class AccumulatedIntel:
    """Deduplicated intelligence gathered across the whole call."""

    phones: list[str] = field(default_factory=list)
    upis: list[str] = field(default_factory=list)
    accounts: list[str] = field(default_factory=list)
    ifsc: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    amounts: list[Amount] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)
    officer_names: list[str] = field(default_factory=list)
    stations: list[str] = field(default_factory=list)
    fir_numbers: list[str] = field(default_factory=list)

    def total_identifiers(self) -> int:
        return len(self.phones) + len(self.upis) + len(self.accounts) + len(self.ifsc)

    def merge(self, e: ExtractedEntities) -> list[dict]:
        """Merge a chunk's entities; return the list of NEWLY added items."""
        new: list[dict] = []

        def _add(bucket: list, value, kind: str, label: str) -> None:
            if value and value not in bucket:
                bucket.append(value)
                new.append({"type": kind, "value": str(value), "label": label})

        for ident in e.identifiers:
            t = ident.type.value
            if t == "phone":
                _add(self.phones, ident.value, "phone", "Phone")
            elif t == "upi":
                _add(self.upis, ident.value, "upi", "UPI")
            elif t == "account":
                _add(self.accounts, ident.value, "account", "Account")
            elif t == "url":
                _add(self.urls, ident.value, "url", "URL")
        for code in e.ifsc:
            _add(self.ifsc, code, "ifsc", "IFSC")
        for ag in e.agencies:
            _add(self.agencies, ag, "agency", "Agency")
        for name in e.officer_names:
            _add(self.officer_names, name, "officer", "Officer")
        for st in e.stations:
            _add(self.stations, st, "station", "Station")
        for fir in e.fir_numbers:
            _add(self.fir_numbers, fir, "fir", "FIR/Case")
        for amt in e.amounts:
            key = amt.raw.lower()
            if key not in [a.raw.lower() for a in self.amounts]:
                self.amounts.append(amt)
                new.append({"type": "amount", "value": amt.raw, "label": "Amount"})
        return new


@dataclass
class DecoySession:
    """Live state for one decoy call. Held in memory for the call's duration."""

    session_id: int
    user_id: int
    user_name: str = ""          # the account holder — the decoy answers as them
    language: str = "hi"
    demo_mode: bool = True
    scenario: str = "digital_arrest"  # seeds the generative fraudster
    started_at: float = field(default_factory=time.monotonic)

    # Rolling conversation. Each turn: {"speaker": "scammer"|"agent", "text","lang"}
    turns: list[dict] = field(default_factory=list)

    # Detection state (updated by the trained models, deterministic).
    scam_probability: float = 0.0
    max_scam_probability: float = 0.0
    current_stage: ScamStage = ScamStage.none
    red_flags: list[str] = field(default_factory=list)
    scam_type: str = "legitimate"

    intel: AccumulatedIntel = field(default_factory=AccumulatedIntel)
    known_ring_hit: bool = False

    mode: AgentMode = AgentMode.monitor
    ended: bool = False
    verdict: str | None = None  # "scam" | "safe"
    package_id: str | None = None
    time_to_first_identifier: float | None = None

    # --- Transcript helpers ---
    @property
    def turn_count(self) -> int:
        return sum(1 for t in self.turns if t["speaker"] == "scammer")

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def scammer_transcript(self) -> str:
        """Only the caller's words — what detection scores."""
        return "\n".join(t["text"] for t in self.turns if t["speaker"] == "scammer")

    @property
    def full_transcript(self) -> str:
        return "\n".join(f"{t['speaker']}: {t['text']}" for t in self.turns)

    def add_turn(self, speaker: str, text: str, language: str | None = None) -> None:
        self.turns.append({"speaker": speaker, "text": text,
                           "lang": language or self.language})

    def ingest_caller_entities(self, text: str) -> list[dict]:
        """Extract + accumulate entities from a caller utterance; return new ones."""
        new = self.intel.merge(extract_entities(text))
        if new and self.time_to_first_identifier is None:
            first_id = any(n["type"] in {"phone", "upi", "account", "ifsc"} for n in new)
            if first_id:
                self.time_to_first_identifier = round(self.elapsed_seconds, 1)
        return new

    # --- Deterministic decision rules (Section 7 of the brief) ---
    def should_interrupt(self) -> bool:
        return (
            self.scam_probability >= INTERRUPT_THRESHOLD
            and STAGE_ORDER[self.current_stage.value] >= STAGE_ORDER[ScamStage.isolation.value]
        )

    def should_stall(self) -> bool:
        return (
            self.scam_probability >= STALL_PROB_THRESHOLD
            and STAGE_ORDER[self.current_stage.value] >= STAGE_ORDER[ScamStage.accusation.value]
        )

    def should_wrap_up(self) -> bool:
        return (
            self.turn_count >= MAX_DECOY_TURNS
            or self.elapsed_seconds >= MAX_DECOY_SECONDS
            or self.current_stage == ScamStage.money_demand
        )

    def decide_mode(self) -> AgentMode:
        """Pick the agent mode from the current deterministic state."""
        if self.should_wrap_up():
            self.mode = AgentMode.wrap_up
        elif self.should_stall():
            self.mode = AgentMode.stall
        else:
            self.mode = AgentMode.monitor
        return self.mode

    def confirmed_scam(self) -> bool:
        """Final verdict: scam iff we ever crossed the interrupt bar."""
        return (
            self.max_scam_probability >= INTERRUPT_THRESHOLD
            and STAGE_ORDER[self.current_stage.value] >= STAGE_ORDER[ScamStage.isolation.value]
        ) or self.known_ring_hit


# --- In-memory session registry (single-process demo). ----------------------
# Persistence of ownership uses the CallSession DB row; the live, per-turn state
# lives here for the duration of the call.
_registry: dict[int, DecoySession] = {}


def create_session(session_id: int, user_id: int, *, language: str = "hi",
                   demo_mode: bool = True, user_name: str = "",
                   scenario: str = "digital_arrest") -> DecoySession:
    session = DecoySession(session_id=session_id, user_id=user_id,
                           user_name=user_name, language=language,
                           demo_mode=demo_mode, scenario=scenario)
    _registry[session_id] = session
    return session


def get_session(session_id: int) -> DecoySession | None:
    return _registry.get(session_id)


def drop_session(session_id: int) -> None:
    _registry.pop(session_id, None)

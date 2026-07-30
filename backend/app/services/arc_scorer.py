"""Stateful scam-arc scoring.

A digital-arrest scam follows a predictable escalation:

    authority_claim  →  accusation  →  isolation  →  money_demand

This module detects which stage a conversation has reached from cue phrases
and accumulates a confidence score. The critical design property: the
interrupt fires at or after the ``isolation`` stage — deliberately *before*
``money_demand`` — because that is when the victim is being cut off from the
people who would otherwise talk them down, and it is still before any money
moves. This staged logic is implemented as an explicit, readable state
machine rather than a black-box score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.enums import STAGE_ORDER, ScamStage

# --- Cue phrases per stage --------------------------------------------------
# Each entry: the lowercase cue substring and a short human-readable red flag
# shown to the user. Phrases are matched case-insensitively against the
# accumulated transcript.

_STAGE_CUES: dict[ScamStage, list[tuple[str, str]]] = {
    ScamStage.authority_claim: [
        ("cbi", "Caller claimed to be from the CBI"),
        ("central bureau", "Caller claimed to be from the CBI"),
        ("enforcement directorate", "Caller claimed to be from the ED"),
        (" ed ", "Caller claimed to be from the ED"),
        ("narcotics", "Caller claimed to be from the narcotics bureau"),
        ("customs", "Caller claimed to be from customs"),
        ("police", "Caller claimed to be police"),
        ("cyber cell", "Caller claimed to be from the cyber cell"),
        ("trai", "Caller claimed to be from TRAI"),
        ("telecom department", "Caller claimed to be from the telecom department"),
        ("courier", "Caller referenced a suspicious courier / parcel"),
        ("fedex", "Caller referenced a suspicious courier / parcel"),
        ("parcel in your name", "A parcel was said to be in your name"),
        ("officer", "Caller identified as an 'officer'"),
        ("this is inspector", "Caller identified as an 'inspector'"),
        ("aadhaar", "Your Aadhaar was referenced"),
    ],
    ScamStage.accusation: [
        ("money laundering", "Accused you of money laundering"),
        ("drugs", "Claimed drugs were found in your name"),
        ("illegal", "Accused you of an illegal activity"),
        ("arrest warrant", "Threatened an arrest warrant"),
        ("warrant", "Threatened a warrant"),
        ("case has been registered", "Claimed a case was registered against you"),
        ("fir", "Claimed an FIR was filed"),
        ("your name has come up", "Claimed your name came up in an investigation"),
        ("involved in a case", "Claimed you are involved in a case"),
        ("passport will be", "Threatened passport / travel consequences"),
        ("non-bailable", "Threatened a non-bailable offence"),
    ],
    ScamStage.isolation: [
        ("do not tell anyone", "Told you to tell no one"),
        ("don't tell anyone", "Told you to tell no one"),
        ("do not disconnect", "Told you not to disconnect"),
        ("don't disconnect", "Told you not to disconnect"),
        ("stay on the line", "Told you to stay on the line"),
        ("stay on the call", "Told you to stay on the call"),
        ("do not talk to", "Told you not to talk to family"),
        ("confidential", "Called the matter 'confidential'"),
        ("under surveillance", "Claimed you are under surveillance"),
        ("digital arrest", "Used the term 'digital arrest'"),
        ("video call", "Insisted on staying on a video call"),
        ("switch on your camera", "Demanded your camera stay on"),
        ("do not leave", "Told you not to leave the call"),
        ("monitored", "Claimed you are being monitored"),
    ],
    ScamStage.money_demand: [
        ("transfer", "Asked you to transfer money"),
        ("rtgs", "Asked for an RTGS transfer"),
        ("neft", "Asked for a NEFT transfer"),
        ("safe account", "Asked you to move money to a 'safe account'"),
        ("verify your funds", "Asked you to 'verify your funds'"),
        ("refundable", "Claimed the money is 'refundable'"),
        ("deposit", "Asked you to deposit money"),
        ("upi", "Asked for a UPI payment"),
        ("pay a fine", "Demanded a fine payment"),
        ("bail amount", "Demanded a bail amount"),
        ("security deposit", "Demanded a 'security deposit'"),
    ],
}

# Confidence contributed the first time each stage is reached. Tuned so that
# reaching ``isolation`` pushes confidence above the interrupt threshold while
# ``money_demand`` has not yet occurred.
_STAGE_WEIGHT: dict[ScamStage, float] = {
    ScamStage.authority_claim: 0.30,
    ScamStage.accusation: 0.25,
    ScamStage.isolation: 0.32,
    ScamStage.money_demand: 0.13,
}

# Interrupt when confidence crosses this AND stage >= isolation.
INTERRUPT_THRESHOLD = 0.72
# Stage at/after which an interrupt is permitted (before money_demand).
INTERRUPT_MIN_STAGE = ScamStage.isolation


@dataclass
class ArcState:
    """Accumulated state for one call session's arc analysis."""

    stages_seen: set[str] = field(default_factory=set)
    red_flags: list[str] = field(default_factory=list)

    @property
    def stage(self) -> ScamStage:
        """The furthest stage reached so far."""
        if not self.stages_seen:
            return ScamStage.none
        return max(
            (ScamStage(s) for s in self.stages_seen),
            key=lambda s: STAGE_ORDER[s.value],
        )

    @property
    def arc_confidence(self) -> float:
        """Confidence from the arc alone, capped at 1.0."""
        total = sum(_STAGE_WEIGHT[ScamStage(s)] for s in self.stages_seen)
        return min(1.0, round(total, 3))


@dataclass
class ArcResult:
    stage: ScamStage
    confidence: float
    red_flags: list[str]
    interrupt: bool
    new_stage_reached: bool


class ArcScorer:
    """Evaluates the accumulated transcript for scam-arc progression.

    Operate one instance per call session and feed it the full accumulated
    transcript each tick; it tracks which stages have appeared and whether the
    interrupt condition (confidence + stage) is now met.
    """

    def __init__(self) -> None:
        self.state = ArcState()
        self._interrupt_fired = False

    def update(self, transcript: str, classifier_score: float = 0.0) -> ArcResult:
        """Re-evaluate against the accumulated transcript.

        The interrupt gate is decided purely by the arc — the stage reached and
        the arc confidence — so the model score can never on its own trigger a
        takeover. ``classifier_score`` is accepted for a caller that wants to
        blend it into the *displayed* confidence, but this method's own
        ``ArcResult.confidence`` is the pure arc confidence used for gating.
        """
        text = transcript.lower()
        prev_stage_order = STAGE_ORDER[self.state.stage.value]

        for stage, cues in _STAGE_CUES.items():
            for needle, flag in cues:
                if needle in text:
                    self.state.stages_seen.add(stage.value)
                    if flag not in self.state.red_flags:
                        self.state.red_flags.append(flag)

        stage = self.state.stage
        new_stage_reached = STAGE_ORDER[stage.value] > prev_stage_order

        # Pure arc confidence drives the interrupt gate.
        confidence = self.state.arc_confidence

        interrupt_now = (
            confidence >= INTERRUPT_THRESHOLD
            and STAGE_ORDER[stage.value] >= STAGE_ORDER[INTERRUPT_MIN_STAGE.value]
        )
        # Latch: once fired, keep signalling interrupt for this session.
        if interrupt_now:
            self._interrupt_fired = True

        return ArcResult(
            stage=stage,
            confidence=confidence,
            red_flags=list(self.state.red_flags),
            interrupt=self._interrupt_fired,
            new_stage_reached=new_stage_reached,
        )

    def evaluate_once(self, text: str, classifier_score: float = 0.0) -> ArcResult:
        """Stateless one-shot evaluation for single messages (Fraud Shield).

        Uses a fresh state so a standalone SMS is scored on its own content.
        """
        scorer = ArcScorer()
        return scorer.update(text, classifier_score)

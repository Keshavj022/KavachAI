"""Shared enumerations used across models and schemas.

Kept as ``str`` enums so they serialize cleanly to JSON and store as text in
SQLite (portable to Postgres).
"""

from enum import Enum


class Role(str, Enum):
    citizen = "citizen"
    authority = "authority"


class ScamStage(str, Enum):
    """The arc of a digital-arrest scam, in escalation order.

    The arc scorer advances through these; the interrupt fires at or after
    ``isolation`` — deliberately before ``money_demand``.
    """

    none = "none"
    authority_claim = "authority_claim"
    accusation = "accusation"
    isolation = "isolation"
    money_demand = "money_demand"


# Numeric ordering for stage comparisons (higher = later/more dangerous).
STAGE_ORDER: dict[str, int] = {
    ScamStage.none.value: 0,
    ScamStage.authority_claim.value: 1,
    ScamStage.accusation.value: 2,
    ScamStage.isolation.value: 3,
    ScamStage.money_demand.value: 4,
}


class Verdict(str, Enum):
    safe = "safe"
    suspicious = "suspicious"
    scam = "scam"


class ScamCategory(str, Enum):
    """Chakshu-aligned scam taxonomy."""

    digital_arrest = "digital_arrest"
    kyc_update = "kyc_update"
    investment = "investment"
    fake_delivery = "fake_delivery"
    refund = "refund"
    loan = "loan"
    other = "other"


class IdentifierType(str, Enum):
    phone = "phone"
    upi = "upi"
    account = "account"
    url = "url"
    device = "device"


class Channel(str, Enum):
    call = "call"
    sms = "sms"
    whatsapp = "whatsapp"


class ReportStatus(str, Enum):
    filed = "filed"
    under_review = "under_review"
    actioned = "actioned"


class AlertStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"

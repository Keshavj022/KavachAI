"""Intelligence package — the decoy's concrete real-world output.

Generated at call end when a scam is confirmed. It bundles everything the decoy
extracted into a structure formatted for submission to Indian authorities
(1930 helpline, Chakshu portal), plus a pre-templated FIR-ready narrative and a
Fernet-encrypted, SHA-256-hashed evidence blob (authority-only).

The FIR narrative and the report formatters are **pre-written templates** filled
from extracted data. The LLM never authors any of this — it is deterministic and
reviewable.

Reuses the existing infrastructure: the linked ``Report`` ingests identifiers
into the fraud graph; ``evidence.preserve_evidence`` encrypts + hashes the
transcript segment (in production this is the audio segment; the prototype has
no real call audio, which is stated in the code and README).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.decoy import DecoyPackage
from app.models.enums import ScamCategory
from app.models.report import Report
from app.services.decoy_session import DecoySession
from app.services.detection_engine import KNOWN_SCAMMER_RISK, known_scammer_lookup
from app.services.evidence import preserve_evidence
from app.services.extractor import extract_identifiers
from app.services.intelligence import ingest_report_identifiers

KAVACH_VERSION = "1.0"


def _scam_category(session: DecoySession) -> ScamCategory:
    """Map the deterministic scam_type + cues to the Chakshu taxonomy."""
    if session.scam_type == "digital_arrest":
        return ScamCategory.digital_arrest
    text = session.scammer_transcript.lower()
    if any(k in text for k in ("kyc", "account block", "re-verify", "pan card")):
        return ScamCategory.kyc_update
    if any(k in text for k in ("investment", "profit", "trading", "returns")):
        return ScamCategory.investment
    if any(k in text for k in ("parcel", "courier", "customs duty", "fedex")):
        return ScamCategory.fake_delivery
    if any(k in text for k in ("loan", "processing fee")):
        return ScamCategory.loan
    if any(k in text for k in ("refund", "cashback")):
        return ScamCategory.refund
    return ScamCategory.other


# --- The FIR narrative template (pre-written, reviewed, fixed) --------------
def build_fir_narrative(session: DecoySession, *, prior_report_count: int,
                        ring_hit: bool) -> str:
    intel = session.intel
    now = datetime.now(timezone.utc).strftime("%d %B %Y at %H:%M")
    officer = intel.officer_names[0] if intel.officer_names else "an unnamed caller"
    agency = intel.agencies[0] if intel.agencies else "an unspecified agency"
    station = intel.stations[0] if intel.stations else "an unspecified office"
    accusation = "; ".join(session.red_flags[:4]) or "coercive allegations"
    amounts = ", ".join(a.raw for a in intel.amounts) or "an unspecified amount"
    pay_targets = ", ".join(intel.upis + intel.accounts) or "an account provided on the call"
    ifsc = ", ".join(intel.ifsc) or "not provided"
    bank = intel.upis[0].split("@")[-1] if intel.upis else "unspecified bank"
    scam_type = _scam_category(session).value.replace("_", " ")
    red_flags = "; ".join(session.red_flags[:5]) or "pressure and secrecy tactics"

    ring_line = ""
    if ring_hit or prior_report_count > 0:
        ring_line = (
            f" This number/identifier has been linked to {prior_report_count} prior "
            "complaint(s) in the Kavach system, suggesting a coordinated fraud "
            "operation."
        )

    all_ids = intel.phones + intel.upis + intel.accounts + intel.ifsc
    id_list = ", ".join(all_ids) or "none captured"

    return (
        f"On {now}, the complainant received a call. "
        f"The caller identified themselves as {officer} from {agency}, {station}. "
        f"The caller alleged: {accusation}. "
        f"The caller demanded a transfer of {amounts} to {pay_targets} with "
        f"IFSC {ifsc} at {bank}. "
        f"The caller used {scam_type} tactics including {red_flags}.{ring_line} "
        f"Relevant identifiers for investigation: {id_list}."
    )


def _chakshu_formatted(session: DecoySession, category: ScamCategory) -> dict:
    """Pre-filled structure matching the Chakshu 'report suspected fraud' form."""
    intel = session.intel
    return {
        "fraud_category": category.value,
        "communication_mode": "call",
        "suspected_numbers": intel.phones,
        "upi_ids": intel.upis,
        "bank_accounts": intel.accounts,
        "ifsc_codes": intel.ifsc,
        "urls": intel.urls,
        "amount_demanded": [a.raw for a in intel.amounts],
        "impersonated_authority": intel.agencies,
        "description": session.red_flags[:6],
        "language": session.language,
    }


def _report_1930_formatted(session: DecoySession, category: ScamCategory) -> dict:
    """Pre-filled structure for the 1930 cyber-crime helpline intake."""
    intel = session.intel
    return {
        "incident_type": category.value,
        "caller_number": intel.phones[0] if intel.phones else None,
        "money_requested": bool(intel.amounts),
        "amounts": [a.raw for a in intel.amounts],
        "payment_identifiers": {
            "upi": intel.upis, "account": intel.accounts, "ifsc": intel.ifsc,
        },
        "claimed_agency": intel.agencies,
        "claimed_officer": intel.officer_names,
        "claimed_station": intel.stations,
        "fir_reference_quoted": intel.fir_numbers,
        "call_duration_seconds": int(session.elapsed_seconds),
    }


@dataclass
class PackageResult:
    package_id: str
    report_id: int | None
    evidence_id: int | None
    payload: dict


def generate_package(db: Session, session: DecoySession) -> PackageResult:
    """Create the report, ingest identifiers, preserve evidence, build package."""
    category = _scam_category(session)

    # Prior-report count for the ring line (before this report increments it).
    all_id_values = (session.intel.phones + session.intel.upis
                     + session.intel.accounts + session.intel.ifsc)
    prior_report_count = 0
    if all_id_values:
        extracted = extract_identifiers(" ".join(all_id_values))
        match = known_scammer_lookup(db, extracted)
        if match is not None:
            prior_report_count = int(match.report_count)

    # 1) Create the report (drives the graph + dashboard).
    report = Report(
        user_id=session.user_id,
        call_session_id=session.session_id,
        channel="call",
        scam_category=category.value,
        content=session.full_transcript,
        status="filed",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 2) Ingest identifiers into the fraud graph (explicit values too, since
    #    amounts/officers are not identifiers and the transcript is the content).
    ingest_report_identifiers(db, report, extra_values=all_id_values)

    # 3) Preserve evidence: encrypt + hash the transcript segment. In production
    #    this is the recorded audio segment; the prototype has no real call audio.
    evidence = preserve_evidence(db, report, session.full_transcript)

    ring_hit = session.known_ring_hit or prior_report_count > 0
    fir_narrative = build_fir_narrative(
        session, prior_report_count=max(0, prior_report_count - 1), ring_hit=ring_hit
    )

    package_id = str(uuid.uuid4())
    payload = {
        "package_id": package_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kavach_version": KAVACH_VERSION,
        "call_duration_seconds": int(session.elapsed_seconds),
        "language_detected": session.language,
        "scam_type": category.value,
        "confidence": round(session.max_scam_probability, 4),
        "stage_at_wrap_up": session.current_stage.value,
        "transcript": session.full_transcript,
        "identifiers": {
            "phones": session.intel.phones,
            "upis": session.intel.upis,
            "accounts": session.intel.accounts,
            "ifsc": session.intel.ifsc,
            "urls": session.intel.urls,
        },
        "amounts_demanded": [{"raw": a.raw, "value_inr": a.value_inr}
                             for a in session.intel.amounts],
        "agency_claimed": session.intel.agencies,
        "officer_name_claimed": session.intel.officer_names,
        "station_claimed": session.intel.stations,
        "fir_number_claimed": session.intel.fir_numbers,
        "urls_mentioned": session.intel.urls,
        "red_flags": session.red_flags,
        "audio_sha256": evidence.sha256_hash,
        "audio_duration_seconds": int(session.elapsed_seconds),
        "ring_id": f"ring-{report.id}" if ring_hit else None,
        "prior_report_count": max(0, prior_report_count - 1),
        "estimated_victims": max(0, prior_report_count - 1),
        "chakshu_formatted": _chakshu_formatted(session, category),
        "report_1930_formatted": _report_1930_formatted(session, category),
        "fir_narrative": fir_narrative,
    }

    row = DecoyPackage(
        package_id=package_id,
        user_id=session.user_id,
        report_id=report.id,
        evidence_id=evidence.id,
        package_json=json.dumps(payload),
    )
    db.add(row)
    db.commit()

    return PackageResult(package_id=package_id, report_id=report.id,
                         evidence_id=evidence.id, payload=payload)

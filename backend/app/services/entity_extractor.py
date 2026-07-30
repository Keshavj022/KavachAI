"""Decoy entity extraction — extends the shared identifier extractor.

``extractor.extract_identifiers`` already pulls phone / UPI / account / URL.
The decoy needs more: monetary amounts, IFSC codes, the agency and officer the
caller claims to be, the station/office named, and any FIR/case number. This
module adds those on top, accumulating into a structured result the decoy
session merges over the whole call.

Pure regex + keyword heuristics on the (possibly romanized-Hindi) transcript —
no model, no network, never raises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import IdentifierType
from app.services.extractor import ExtractedIdentifier, extract_identifiers

# --- Amounts ----------------------------------------------------------------
# Matches "₹2 lakh", "rs 50000", "2 lakh", "fifty thousand rupees", "₹2,00,000".
_AMOUNT_RE = re.compile(
    r"(?:(?:₹|rs\.?|inr|rupees?|rupaye)\s*)?"
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"(lakh|lakhs|lac|crore|crores|thousand|hazaar|k)?"
    r"(?:\s*(?:₹|rs\.?|inr|rupees?|rupaye))?",
    re.IGNORECASE,
)
_AMOUNT_WORD_MULT = {
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
    "crore": 10_000_000, "crores": 10_000_000,
    "thousand": 1_000, "hazaar": 1_000, "k": 1_000,
}
# Only treat a bare number as money if a currency cue is nearby.
_CURRENCY_CUE = re.compile(r"₹|rs\.?|inr|rupees?|rupaye|lakh|crore|thousand|hazaar",
                           re.IGNORECASE)

# --- IFSC: 4 letters + 0 + 6 alphanumeric ----------------------------------
_IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")

# --- FIR / case / reference numbers ----------------------------------------
_FIR_RE = re.compile(
    r"\b(?:fir|f\.i\.r|case|reference|ref|complaint)\s*(?:no\.?|number|#)?\s*"
    r"[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{3,20})",
    re.IGNORECASE,
)

# --- Agencies the caller may impersonate ------------------------------------
_AGENCIES = {
    "CBI": ["cbi", "central bureau"],
    "ED": ["enforcement directorate", " ed ", "e.d."],
    "TRAI": ["trai", "telecom regulatory"],
    "police": ["police", "cyber cell", "cyber crime", "thana"],
    "customs": ["customs", "custom department"],
    "RBI": ["rbi", "reserve bank"],
    "FedEx": ["fedex", "fed ex"],
    "courier": ["courier", "parcel department", "dhl", "bluedart"],
    "narcotics": ["narcotics", "ncb"],
    "income tax": ["income tax", "it department"],
}

# --- Officer name: "Inspector X", "Officer Y", "Main Inspector X hoon" -------
# The keyword is matched case-insensitively (inline (?i:...)) but the NAME is
# case-sensitive (real names are capitalised) so trailing lowercase Hindi words
# like "bol"/"raha" are not swept into the name.
_OFFICER_RE = re.compile(
    r"(?i:\b(?:inspector|officer|sub-inspector|dsp|acp|constable|agent|"
    r"investigating officer))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
)

# --- Station / office: "X police station", "Delhi cyber cell", "X thana" -----
_STATION_RE = re.compile(
    r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s+"
    r"(?i:police station|thana|cyber cell|cyber crime cell|customs office)"
)


@dataclass
class Amount:
    raw: str
    value_inr: int | None  # normalized rupees where derivable


@dataclass
class ExtractedEntities:
    """Everything a single transcript chunk yields (before accumulation)."""

    identifiers: list[ExtractedIdentifier] = field(default_factory=list)
    ifsc: list[str] = field(default_factory=list)
    amounts: list[Amount] = field(default_factory=list)
    agencies: list[str] = field(default_factory=list)
    officer_names: list[str] = field(default_factory=list)
    stations: list[str] = field(default_factory=list)
    fir_numbers: list[str] = field(default_factory=list)


def _parse_amounts(text: str) -> list[Amount]:
    amounts: list[Amount] = []
    for m in _AMOUNT_RE.finditer(text):
        number, word = m.group(1), (m.group(2) or "").lower()
        span = text[max(0, m.start() - 12): m.end() + 12]
        # Require a currency cue nearby, or an explicit magnitude word, so bare
        # numbers (dates, counts) are not mistaken for money.
        if not word and not _CURRENCY_CUE.search(span):
            continue
        try:
            base = float(number.replace(",", ""))
            value = int(base * _AMOUNT_WORD_MULT.get(word, 1))
        except ValueError:
            value = None
        amounts.append(Amount(raw=m.group(0).strip(), value_inr=value))
    return amounts


def _find_agencies(lowered: str) -> list[str]:
    found = []
    for name, cues in _AGENCIES.items():
        if any(cue in lowered for cue in cues):
            found.append(name)
    return found


def extract_entities(text: str) -> ExtractedEntities:
    """Extract all decoy-relevant entities from one transcript chunk."""
    if not text:
        return ExtractedEntities()
    lowered = text.lower()
    return ExtractedEntities(
        identifiers=extract_identifiers(text),
        ifsc=[m.group(1).upper() for m in _IFSC_RE.finditer(text)],
        amounts=_parse_amounts(text),
        agencies=_find_agencies(lowered),
        officer_names=[m.group(1).strip() for m in _OFFICER_RE.finditer(text)],
        stations=[m.group(1).strip() for m in _STATION_RE.finditer(text)],
        fir_numbers=[m.group(1).strip() for m in _FIR_RE.finditer(text)],
    )

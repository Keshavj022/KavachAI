"""Identifier extraction — the shared data spine.

Pulls phone numbers, UPI VPAs, bank account numbers and URLs out of free text
(SMS bodies, transcripts). Both the detector (known-scammer lookup) and the
graph depend on this producing normalised, comparable identifier values.

Pure regex + light heuristics: no model, no network, never fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import IdentifierType

# --- Patterns ---------------------------------------------------------------

# Indian mobile: optional +91 / 0 prefix, then a 10-digit number starting 6-9.
# Allows spaces/dashes between groups which we strip during normalisation.
_PHONE_RE = re.compile(
    r"(?:(?:\+?91|0)[\-\s]?)?([6-9]\d(?:[\-\s]?\d){8})"
)

# UPI VPA: handle@provider, e.g. name.surname@okhdfc, cbi.refund@okaxis.
_UPI_RE = re.compile(r"\b([a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64})\b")

# URLs (http/https or bare www.). Kept simple and greedy-stopped at whitespace.
_URL_RE = re.compile(r"\b((?:https?://|www\.)[^\s<>()]+)", re.IGNORECASE)

# Bank account numbers: 11–18 consecutive digits (longer than a phone number
# so the two do not collide). Extracted after phones are masked out.
_ACCOUNT_RE = re.compile(r"\b(\d{11,18})\b")


@dataclass(frozen=True)
class ExtractedIdentifier:
    type: IdentifierType
    value: str


def _normalise_phone(raw: str) -> str:
    """Return a canonical +91XXXXXXXXXX form for an Indian mobile number."""
    digits = re.sub(r"\D", "", raw)
    # Drop a leading country/trunk prefix so the 10-digit core is comparable.
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return f"+91{digits[-10:]}" if len(digits) >= 10 else raw


def extract_identifiers(text: str) -> list[ExtractedIdentifier]:
    """Extract and de-duplicate identifiers from ``text``.

    Order of operations matters: emails/UPI and URLs are found first, then
    phones, and only the residual text is scanned for long account numbers so
    a phone's digits are not misread as an account.
    """
    if not text:
        return []

    found: dict[tuple[str, str], ExtractedIdentifier] = {}
    working = text

    def _add(id_type: IdentifierType, value: str) -> None:
        key = (id_type.value, value.lower())
        if key not in found:
            found[key] = ExtractedIdentifier(type=id_type, value=value)

    # 1) URLs (before UPI so a URL's host isn't mistaken for a VPA).
    for m in _URL_RE.finditer(working):
        _add(IdentifierType.url, m.group(1).rstrip(".,"))
    working = _URL_RE.sub(" ", working)

    # 2) UPI VPAs.
    for m in _UPI_RE.finditer(working):
        vpa = m.group(1)
        # Skip anything that looks like a plain email domain only (no dot-less
        # provider handles slip through since providers like okhdfc have none).
        _add(IdentifierType.upi, vpa.lower())
    working = _UPI_RE.sub(" ", working)

    # 3) Phone numbers.
    for m in _PHONE_RE.finditer(working):
        _add(IdentifierType.phone, _normalise_phone(m.group(0)))
    working = _PHONE_RE.sub(" ", working)

    # 4) Residual long digit runs → account numbers.
    for m in _ACCOUNT_RE.finditer(working):
        _add(IdentifierType.account, m.group(1))

    return list(found.values())

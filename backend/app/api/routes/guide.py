"""Citizen-guide contacts endpoint.

Serves the authoritative helpline / portal / legal-section data from a static
JSON config (no database), so it can be updated without a frontend redeploy and
reused by the guide page, the Fraud Shield chat, and the reporting flow.

The numbers, URLs and legal citations are verified against official Government
of India sources (see ``app/data/guide_contacts.json``); they are returned
as-is and must not be altered. The ``lang`` query parameter is accepted for
forward compatibility (client-side i18n currently handles display language).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/guide", tags=["guide"])

_DATA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "guide_contacts.json"
)


@lru_cache
def _load() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@router.get("/contacts")
def get_contacts(lang: str = Query(default="en", max_length=8)) -> dict:
    """Return verified helplines, bank fraud numbers, portals and legal sections.

    Public (no auth) — this is public-safety reference information.
    """
    data = _load()
    return {
        "lang": lang,
        "helplines": data["helplines"],
        "bank_fraud_helplines": data["bank_fraud_helplines"],
        "portals": data["portals"],
        "legal_sections": data["legal_sections"],
    }

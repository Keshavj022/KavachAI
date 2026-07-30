"""Canonical ASR-style text normalization — the ONE shared implementation.

Production input is Whisper output: lowercase, unpunctuated, run-on, no speaker
tags, with ASR errors. The training corpus (ICFD) is clean, punctuated and
speaker-tagged. To make train and inference registers match, the same
``asr_normalize`` is applied to training text AND to the live transcript at
runtime.

This module is deliberately dependency-free (standard library only) so both the
training scripts (``call_classifier/``) and the backend import the exact same
function. A drift between two copies would silently destroy accuracy, so there
must be exactly one implementation — this one.
"""

from __future__ import annotations

import re

# Leading "Agent:" / "Customer:" / "Caller:" style speaker tags at the start of
# a line or after a newline. Whisper output has no speaker tags, so we strip
# them from the training data to match.
_SPEAKER_TAG = re.compile(
    r"(?:^|\n)\s*(?:agent|customer|caller|user|speaker\s*\d*|operator|me|them)\s*:",
    re.IGNORECASE,
)
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def asr_normalize(text: str) -> str:
    """Normalize text to the register a live Whisper transcript would have.

    Steps: strip speaker tags → lowercase → remove punctuation → collapse
    whitespace. Devanagari and other word characters are preserved (Hinglish
    calls keep their content words).
    """
    if not text:
        return ""
    t = _SPEAKER_TAG.sub(" ", text)
    t = t.lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t

"""Shared helpers for the call-dataset exploration scripts.

Read-only: nothing here writes to the four source data directories. All outputs
go under ``exploration_output/``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — never open a window
import matplotlib.pyplot as plt  # noqa: E402

# --- Paths ------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPTS_DIR.parent                       # exploration_output/
ROOT = OUT_DIR.parent                              # call-data-exploration/
FIGURES = OUT_DIR / "figures"
SAMPLES = OUT_DIR / "samples"
SCHEMAS = OUT_DIR / "schemas"
TMP = OUT_DIR / "tmp"
STATS_JSON = OUT_DIR / "stats.json"

DATASETS = {
    "icfd": ROOT / "icfd",
    "call-center": ROOT / "call-center",
    "call-transcript": ROOT / "call-transcript",
    "youtube-scam": ROOT / "youtube-scam",
}

for _d in (FIGURES, SAMPLES, SCHEMAS, TMP):
    _d.mkdir(parents=True, exist_ok=True)


# --- Stats accumulation -----------------------------------------------------
def save_stats(section: str, payload: dict) -> None:
    """Merge a block into exploration_output/stats.json under ``section``."""
    stats: dict = {}
    if STATS_JSON.exists():
        with open(STATS_JSON) as fh:
            stats = json.load(fh)
    stats[section] = payload
    with open(STATS_JSON, "w") as fh:
        json.dump(stats, fh, indent=2, default=_json_default)
    print(f"  [stats] wrote section '{section}'")


def _json_default(o):
    try:
        import numpy as np

        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.ndarray,)):
            return o.tolist()
    except ImportError:
        pass
    return str(o)


def savefig(fig, name: str, dpi: int = 160) -> None:
    fig.savefig(FIGURES / name, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  [fig] {name}")


def write_schema(dataset: str, schema: dict) -> None:
    path = SCHEMAS / f"{dataset}_schema.json"
    with open(path, "w") as fh:
        json.dump(schema, fh, indent=2, default=_json_default)
    print(f"  [schema] {path.name}")


def write_samples(filename: str, text: str) -> None:
    (SAMPLES / filename).write_text(text, encoding="utf-8")
    print(f"  [samples] {filename}")


# --- Text helpers -----------------------------------------------------------
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")

# Small romanized-Hindi marker set for a rough Hinglish signal (limited!).
_HINGLISH_MARKERS = {
    "hai", "kya", "nahi", "nahin", "aap", "mera", "meri", "tum", "kaise",
    "paisa", "paise", "rupaye", "rupee", "bhai", "sahab", "ji", "haan",
    "karo", "karna", "bola", "kyun", "abhi", "theek", "acha", "accha",
}


def detect_language(text: str) -> str:
    """Rough language bucket: 'hindi_script' | 'english' | 'hinglish' | 'other'.

    Method (and its limits): Devanagari presence → hindi_script. Otherwise try
    langdetect; if it says English but the text carries romanized-Hindi marker
    words, call it hinglish. This is a heuristic — langdetect is unreliable on
    short, code-mixed, ASR-noisy text, so treat the split as indicative only.
    """
    if not text or not text.strip():
        return "other"
    if _DEVANAGARI.search(text):
        return "hindi_script"
    tokens = set(_WS.sub(" ", text.lower()).split())
    hinglish_hits = len(tokens & _HINGLISH_MARKERS)
    try:
        from langdetect import detect

        lang = detect(text[:2000])
    except Exception:
        lang = "unknown"
    if lang == "en":
        return "hinglish" if hinglish_hits >= 2 else "english"
    if lang in {"hi", "mr", "ne"}:
        return "hindi_script" if _DEVANAGARI.search(text) else "hinglish"
    # langdetect often misfires on ASR/code-mixed text; fall back to markers.
    if hinglish_hits >= 2:
        return "hinglish"
    return "english" if lang == "unknown" else "other"


def normalize_for_dedup(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for dup detection."""
    if not isinstance(text, str):
        return ""
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


def percentiles(values: list[float]) -> dict:
    """Return summary percentiles for a numeric list."""
    import numpy as np

    if not values:
        return {}
    a = np.asarray(values, dtype=float)
    return {
        "n": int(a.size),
        "min": float(a.min()),
        "p25": float(np.percentile(a, 25)),
        "median": float(np.median(a)),
        "mean": round(float(a.mean()), 2),
        "p75": float(np.percentile(a, 75)),
        "p95": float(np.percentile(a, 95)),
        "max": float(a.max()),
    }


def truncate(text: str, limit: int = 2000) -> str:
    if text is None:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…[TRUNCATED — {len(text)} chars total]"

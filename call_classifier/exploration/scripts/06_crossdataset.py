"""Cross-dataset checks: contamination, near-duplication, comparability.

- Normalized exact-match overlap across all four datasets.
- Shingle (5-gram) near-duplicate overlap between the small real sets, and
  ICFD-vs-real (was ICFD seeded from the real data?).
- SMS-not-a-call flag.
- Length/register comparison figure.

Samples large datasets (sizes stated). Read-only.
"""

from __future__ import annotations

import glob
import io
import json
import zipfile
from collections import Counter

import pyarrow.parquet as pq  # noqa: F401  (kept for parity; not required here)
import zstandard as zstd

import common as c

ICFD = c.DATASETS["icfd"]


def _norm(text: str) -> str:
    return c.normalize_for_dedup(text)


def _shingles(text: str, k: int = 5) -> set:
    toks = _norm(text).split()
    return {" ".join(toks[i:i + k]) for i in range(max(0, len(toks) - k + 1))}


def load_samples() -> dict[str, list[str]]:
    import pandas as pd

    data: dict[str, list[str]] = {}

    # youtube-scam — all
    yt = pd.read_csv(c.DATASETS["youtube-scam"] / "FullTranscriptData.csv",
                     dtype=str, keep_default_na=False)
    data["youtube-scam"] = yt["Content"].tolist()

    # call-transcript — conversation-level full text
    ct = pd.read_csv(c.DATASETS["call-transcript"] / "BETTER30.csv",
                     dtype=str, keep_default_na=False)
    data["call-transcript"] = (
        ct.groupby("CONVERSATION_ID")["TEXT"].apply(lambda s: " ".join(s)).tolist()
    )

    # ICFD — sample source full texts
    icfd_texts = []
    for path in sorted(glob.glob(str(ICFD / "source_conversations" / "*.jsonl.zst"))):
        with open(path, "rb") as fh:
            reader = zstd.ZstdDecompressor().stream_reader(fh)
            for line in io.TextIOWrapper(reader, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                icfd_texts.append(" ".join(t.get("text", "")
                                           for t in rec.get("transcript", [])))
                if len(icfd_texts) >= 3000:
                    break
        if len(icfd_texts) >= 3000:
            break
    data["icfd"] = icfd_texts

    # call-center — sample texts from archives
    cc_texts = []
    for zp in sorted(c.DATASETS["call-center"].glob("*.zip")):
        with zipfile.ZipFile(zp) as zf:
            members = [n for n in zf.namelist() if n.endswith(".json")][:150]
            for name in members:
                try:
                    cc_texts.append(json.loads(zf.read(name)).get("text", ""))
                except Exception:
                    pass
        if len(cc_texts) >= 1500:
            break
    data["call-center"] = cc_texts[:1500]
    return data


def exact_overlap(data: dict[str, list[str]]) -> dict:
    norm_sets = {k: {(_norm(t)) for t in v if len(t) > 20} for k, v in data.items()}
    out = {}
    keys = list(norm_sets)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            inter = norm_sets[a] & norm_sets[b]
            out[f"{a} ∩ {b}"] = len(inter)
    return out


def near_dup(a: list[str], b: list[str], a_cap=300, b_cap=300, thresh=0.5) -> dict:
    """Max shingle-Jaccard near-dup search between two sampled sets."""
    a_sh = [(_shingles(t), t) for t in a[:a_cap] if len(t.split()) >= 6]
    b_sh = [(_shingles(t), t) for t in b[:b_cap] if len(t.split()) >= 6]
    best = 0.0
    best_pair = None
    hits = 0
    for sa, ta in a_sh:
        for sb, tb in b_sh:
            if not sa or not sb:
                continue
            j = len(sa & sb) / len(sa | sb)
            if j > best:
                best, best_pair = j, (ta[:160], tb[:160])
            if j >= thresh:
                hits += 1
    return {"max_jaccard": round(best, 3), "pairs_over_threshold": hits,
            "threshold": thresh,
            "example": best_pair if best >= 0.3 else None}


def sms_flag(data: dict[str, list[str]]) -> dict:
    """Flag any dataset that looks like SMS (short, one-shot, no turns)."""
    import numpy as np

    out = {}
    for k, v in data.items():
        words = [len(t.split()) for t in v if t]
        short = sum(1 for w in words if w < 25)
        out[k] = {
            "median_words": float(np.median(words)) if words else 0,
            "frac_under_25_words": round(short / len(words), 3) if words else 0,
            "looks_like_sms": bool(words and np.median(words) < 25),
        }
    return out


def comparison_fig(data: dict[str, list[str]]) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(8, 5))
    labels, series = [], []
    for k, v in data.items():
        wc = [len(t.split()) for t in v if t]
        labels.append(f"{k}\n(n={len(wc)})")
        series.append(np.clip(wc, 0, 1500))
    ax.boxplot(series, tick_labels=labels, showfliers=False, patch_artist=True)
    ax.set_ylabel("words per record (clipped at 1500)")
    ax.set_title("Record length by dataset (register/length comparison)",
                 fontsize=11, fontweight="bold")
    c.savefig(fig, "cross_length_by_dataset.png")


def main() -> None:
    print("=== Cross-dataset checks ===")
    data = load_samples()
    for k, v in data.items():
        print(f"  loaded {k}: {len(v)} records "
              f"(sampled)" if k in {"icfd", "call-center"} else f"  loaded {k}: {len(v)}")

    print("\n[G] exact normalized overlap:")
    ov = exact_overlap(data)
    for k, n in ov.items():
        print(f"    {k}: {n}")

    print("\n[G] near-duplicate (shingle Jaccard):")
    nd = {
        "youtube-scam vs call-transcript": near_dup(data["youtube-scam"], data["call-transcript"]),
        "icfd vs youtube-scam": near_dup(data["icfd"], data["youtube-scam"]),
        "icfd vs call-transcript": near_dup(data["icfd"], data["call-transcript"]),
        "youtube-scam vs call-center": near_dup(data["youtube-scam"], data["call-center"]),
    }
    for k, v in nd.items():
        print(f"    {k}: max_jaccard={v['max_jaccard']} hits={v['pairs_over_threshold']}")

    print("\n[G] SMS-not-a-call flag:")
    sms = sms_flag(data)
    for k, v in sms.items():
        print(f"    {k}: median_words={v['median_words']} sms_like={v['looks_like_sms']}")

    comparison_fig(data)

    c.save_stats("cross_dataset", {
        "sample_sizes": {k: len(v) for k, v in data.items()},
        "exact_normalized_overlap": ov,
        "near_duplicate": nd,
        "sms_flag": sms,
        "notes": "ICFD & call-center are sampled (3000 / 1500). call-transcript "
        "is conversation-level (65). youtube-scam is all 243.",
    })


if __name__ == "__main__":
    main()

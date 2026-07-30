"""Phase 2b — Conversation-level stratified split + chunk expansion.

ICFD is re-split 70/15/15 **at the conversation level**, stratified on
``case_type × domain`` so every split contains all four case types (especially
the "Ambiguous but Ultimately Normal" hard negatives). call-center and
youtube-scam keep their roles from 01. Chunks are expanded **after** the split,
so no conversation's chunks ever cross splits (leakage-free).

Training/eval unit = a cumulative (partial) transcript:
  * ICFD: cumulative turn-prefixes (reconstructed from the source transcript,
    which carries per-turn timestamps), capped per conversation.
  * call-center: cumulative word-prefixes (partial legit calls).
  * youtube-scam: the opening as-is (already a partial transcript).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from app.services.asr_norm import asr_normalize  # noqa: E402


def split_icfd(df: pd.DataFrame) -> pd.DataFrame:
    """Assign train/val/test to ICFD conversations, stratified per group."""
    rng = np.random.default_rng(config.RANDOM_SEED)
    icfd = df[df.source_dataset == "icfd"].copy()
    icfd["split"] = ""
    for _, grp in icfd.groupby(["case_type", "domain"]):
        idx = grp.index.to_numpy()
        rng.shuffle(idx)
        n = len(idx)
        n_test = max(1, int(round(n * config.TEST_SIZE))) if n >= 3 else 0
        n_val = max(1, int(round(n * config.VAL_SIZE))) if n >= 3 else 0
        test_idx = idx[:n_test]
        val_idx = idx[n_test:n_test + n_val]
        train_idx = idx[n_test + n_val:]
        icfd.loc[test_idx, "split"] = "test"
        icfd.loc[val_idx, "split"] = "val"
        icfd.loc[train_idx, "split"] = "train"
    df.loc[icfd.index, "split"] = icfd["split"]
    return df


def _icfd_chunks(row) -> list[dict]:
    """Cumulative turn-prefix chunks for one ICFD conversation."""
    turns = json.loads(row["turns_json"])
    if not turns:
        return []
    n = len(turns)
    # Choose up to MAX_CHUNKS turn boundaries spread across the call, always
    # including an early prefix and the full transcript.
    k = min(config.MAX_CHUNKS_PER_CONVERSATION, n)
    boundaries = sorted(set(
        int(round(x)) for x in np.linspace(1, n, k)
    ))
    out = []
    for b in boundaries:
        prefix = turns[:b]
        raw = "\n".join(f"{t['speaker']}: {t['text']}" for t in prefix)
        ts = prefix[-1].get("ts")
        out.append({
            "chunk_id": f"{row['conversation_id']}#t{b}",
            "conversation_id": row["conversation_id"],
            "source_dataset": "icfd",
            "split": row["split"],
            "label": row["label"],
            "case_type": row["case_type"],
            "domain": row["domain"],
            "chunk_index": b,
            "n_turns_in_chunk": b,
            "chunk_timestamp": ts,
            "text_norm": asr_normalize(raw),
        })
    return out


def _prefix_chunks(row, fractions=(0.35, 0.6, 1.0)) -> list[dict]:
    """Cumulative word-prefix chunks for a flat source (call-center)."""
    words = row["full_text_norm"].split()
    if not words:
        return []
    out = []
    for f in fractions:
        cut = max(5, int(len(words) * f))
        out.append({
            "chunk_id": f"{row['conversation_id']}#w{int(f*100)}",
            "conversation_id": row["conversation_id"],
            "source_dataset": row["source_dataset"],
            "split": row["split"],
            "label": row["label"],
            "case_type": row["case_type"],
            "domain": row["domain"],
            "chunk_index": cut,
            "n_turns_in_chunk": 0,
            "chunk_timestamp": None,
            "text_norm": " ".join(words[:cut]),
        })
    return out


def _single_chunk(row) -> list[dict]:
    if not row["full_text_norm"].strip():
        return []
    return [{
        "chunk_id": f"{row['conversation_id']}#full",
        "conversation_id": row["conversation_id"],
        "source_dataset": row["source_dataset"],
        "split": row["split"],
        "label": row["label"],
        "case_type": row["case_type"],
        "domain": row["domain"],
        "chunk_index": 0,
        "n_turns_in_chunk": 0,
        "chunk_timestamp": None,
        "text_norm": row["full_text_norm"],
    }]


def main() -> None:
    config.set_global_seed()
    print("=== Phase 2b: split + chunk expansion ===")
    df = pd.read_parquet(config.CORPUS_PARQUET)

    df = split_icfd(df)
    # Persist the conversation-level split back to the corpus.
    df.to_parquet(config.CORPUS_PARQUET, index=False)

    print("\n  ICFD conversation split (stratified on case_type × domain):")
    icfd = df[df.source_dataset == "icfd"]
    print(icfd.groupby(["split", "label"]).size().to_string())
    print("\n  every split has all 4 case types?")
    print(icfd.groupby(["split", "case_type"]).size().unstack(fill_value=0).to_string())

    # Expand to chunks AFTER the split.
    chunks: list[dict] = []
    for _, row in df.iterrows():
        if row["source_dataset"] == "icfd":
            chunks.extend(_icfd_chunks(row))
        elif row["source_dataset"] == "call-center":
            chunks.extend(_prefix_chunks(row))
        else:  # youtube-scam
            chunks.extend(_single_chunk(row))
    cdf = pd.DataFrame(chunks)

    # Leakage guard: no conversation appears in more than one split.
    conv_splits = cdf.groupby("conversation_id")["split"].nunique()
    assert (conv_splits <= 1).all(), "LEAKAGE: a conversation spans multiple splits"

    cdf.to_parquet(config.CHUNKS_PARQUET, index=False)
    print(f"\n  chunks: {len(cdf)} (leakage-free: each conversation in one split)")
    print("  chunks by split × label:")
    print(cdf.groupby(["split", "label"]).size().to_string())
    print(f"\n  saved {config.CHUNKS_PARQUET.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

"""youtube-scam/ (FullTranscriptData.csv) deep dive.

Expected: 243 scam-call transcripts (beginnings), no label column, CC0.
Verify: schema, all-positive?, multi-turn vs flat, language, redaction, Source
URLs (for cross-dataset overlap with call-transcript later).

Read-only. Writes stats['youtube_scam'], schema, samples.
"""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

import common as c

CSV = c.DATASETS["youtube-scam"] / "FullTranscriptData.csv"


def main() -> None:
    print("=== youtube-scam / FullTranscriptData.csv ===")
    df = pd.read_csv(CSV, encoding="utf-8", dtype=str, keep_default_na=False)
    print(f"rows: {len(df)}  columns: {list(df.columns)}")

    schema = {"file": "FullTranscriptData.csv", "n_rows": len(df), "columns": {}}
    for col in df.columns:
        schema["columns"][col] = {
            "n_unique": int(df[col].nunique()),
            "examples": [c.truncate(v, 300) for v in df[col].head(4).tolist()],
        }
    c.write_schema("youtube-scam", schema)

    # Label column? (expected: none — all scam)
    label_like = [col for col in df.columns
                  if col.lower() in {"label", "class", "determination", "type", "scam"}]
    print(f"label-like columns: {label_like or 'NONE (all rows are scam)'}")

    # Source column — URLs? (used for cross-dataset overlap with call-transcript)
    src = df.get("Source")
    url_rate = 0.0
    if src is not None:
        url_rate = src.str.contains(r"https?://|youtu", case=False, regex=True).mean()
        print(f"Source looks like URLs: {url_rate:.1%}; examples: "
              f"{src.head(3).tolist()}")

    # Length: Char_Len column vs computed.
    df["chars"] = df["Content"].str.len()
    df["words"] = df["Content"].str.split().map(len)
    length = {"chars": c.percentiles(df["chars"].tolist()),
              "words": c.percentiles(df["words"].tolist())}
    if "Char_Len" in df.columns:
        try:
            declared = pd.to_numeric(df["Char_Len"], errors="coerce")
            mism = int((declared != df["chars"]).sum())
            print(f"Char_Len vs computed char length mismatches: {mism}/{len(df)}")
        except Exception:
            mism = None

    # Multi-turn vs flat: look for speaker prefixes / turn delimiters.
    joined = "\n".join(df["Content"].head(50).tolist())
    speaker_prefix = len(re.findall(r"(?m)^\s*(caller|scammer|victim|agent|customer|me|them|operator)\s*[:\-]",
                                    joined, re.I))
    newline_turns = df["Content"].str.count(r"\n").mean()
    print(f"speaker-prefix lines in first 50 records: {speaker_prefix}; "
          f"mean newlines/record: {newline_turns:.1f}")

    # Language mix.
    langs = Counter(c.detect_language(t) for t in df["Content"])
    print(f"language buckets: {dict(langs)}")

    # Redaction convention.
    redaction_tokens = ["[NAME]", "[REDACTED]", "XXX", "<PII>", "[PHONE]",
                        "[removed]", "***", "[number]", "[address]"]
    blob = " ".join(df["Content"].tolist())
    redaction = {tok: blob.count(tok) for tok in redaction_tokens if tok in blob}
    print(f"redaction tokens seen: {redaction or 'none of the common ones'}")

    # Duplicates.
    norm = df["Content"].map(c.normalize_for_dedup)
    exact_dupes = int(df["Content"].duplicated().sum())
    near_dupes = int(norm.duplicated().sum())
    empty = int((df["chars"] < 10).sum())
    print(f"exact dup rows: {exact_dupes}; near-dup(normalized): {near_dupes}; "
          f"empty(<10 chars): {empty}")

    # Save 5 full examples.
    ex = ["# youtube-scam — full verbatim examples (all rows are scam)\n"]
    for _, r in df.head(5).iterrows():
        ex.append(f"### ID={r['ID']}  Source={c.truncate(r.get('Source',''),120)}  "
                  f"chars={r['chars']}")
        ex.append("```")
        ex.append(c.truncate(r["Content"], 2000))
        ex.append("```\n")
    c.write_samples("youtubescam_examples.md", "\n".join(ex))

    c.save_stats("youtube_scam", {
        "n_rows": len(df),
        "columns": list(df.columns),
        "has_label_column": bool(label_like),
        "all_scam": True,
        "source_url_rate": round(float(url_rate), 3),
        "source_examples": df.get("Source", pd.Series(dtype=str)).head(5).tolist(),
        "length": length,
        "language_buckets": dict(langs),
        "redaction_tokens": redaction,
        "speaker_prefix_lines_first50": speaker_prefix,
        "mean_newlines_per_record": round(float(newline_turns), 2),
        "exact_dupes": exact_dupes,
        "near_dupes": near_dupes,
        "empty_records": empty,
    })


if __name__ == "__main__":
    main()

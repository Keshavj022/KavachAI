"""Phase 2a — Build the unified conversation-level corpus.

Sources (see brief §3):
  * ICFD (source_conversations/*.jsonl.zst) — synthetic, both classes, 4-way
    case_type, per-turn timestamps, chunk_level_analysis. Built from SOURCE (not
    the streaming parquet) because the parquet collapses case_type to 2 values
    and drops the "Ambiguous but Ultimately Normal" hard negatives we must
    stratify on.
  * call-center — real legit negatives; deduped, sampled ~5k train / ~2k test.
  * youtube-scam — real scam openings; held-out test only.
  * call-transcript — EXCLUDED (corrupt CSV + synthetic despite "real" billing).

All text is normalized with the shared ``asr_normalize`` (imported from the
backend, the single implementation used at runtime too). Splits for ICFD are
assigned later (02_split.py); this script only assigns call-center and
youtube-scam roles. Read-only over raw data.
"""

from __future__ import annotations

import glob
import io
import json
import os
import random
import sys
import zipfile
from pathlib import Path

import pandas as pd
import zstandard as zstd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from app.services.asr_norm import asr_normalize  # noqa: E402  (shared, from backend)

# call-center archive that is a byte-identical duplicate of another (audit §2.2).
CC_EXACT_DUP = "(reupload)PII_redacted_auto_insurance_script.zip"
CC_PER_ARCHIVE_CAP = 1400  # diversify across domains rather than draining medicare


def _to_seconds(v) -> float | None:
    """Coerce a timestamp_end to float seconds.

    ICFD occasionally stores a formula string like '1.27*60' instead of a
    number — evaluate the simple ``a*b`` form, else parse a plain number, else
    return None.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    try:
        if "*" in s:
            a, b = s.split("*", 1)
            return float(a) * float(b)
        return float(s)
    except (ValueError, TypeError):
        return None


def _norm_case_type(ct: str) -> str:
    """Unify 'Clear_Fraud' vs 'Clear Fraud' etc. across main/cross_domain batches."""
    return (ct or "unknown").replace("_", " ").strip()


def _iter_source(path: str):
    with open(path, "rb") as fh:
        reader = zstd.ZstdDecompressor().stream_reader(fh)
        for line in io.TextIOWrapper(reader, encoding="utf-8"):
            line = line.strip()
            if line:
                yield json.loads(line)


def build_icfd() -> list[dict]:
    rows = []
    idx = 0
    for path in sorted(glob.glob(str(config.ICFD / "source_conversations" / "*.jsonl.zst"))):
        for rec in _iter_source(path):
            turns = [
                {"speaker": t.get("speaker"), "text": t.get("text", ""),
                 "ts": _to_seconds(t.get("timestamp_end"))}
                for t in rec.get("transcript", [])
            ]
            if not turns:
                continue
            raw = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns)
            rows.append({
                "conversation_id": f"icfd-{idx:06d}",
                "source_dataset": "icfd",
                "label": 1 if rec.get("final_verdict") == "YES" else 0,
                "case_type": _norm_case_type(rec.get("scenario", {}).get("case_type", "unknown")),
                "domain": rec.get("release_metadata", {}).get("domain", "unknown"),
                "is_synthetic": True,
                "split": "",  # assigned in 02_split
                "n_turns": len(turns),
                "duration": turns[-1]["ts"],
                "full_text_raw": raw,
                "full_text_norm": asr_normalize(raw),
                "turns_json": json.dumps(turns, ensure_ascii=False),
                "chunk_analysis_json": json.dumps(rec.get("chunk_level_analysis", [])),
            })
            idx += 1
    print(f"  ICFD conversations: {len(rows)}")
    return rows


def build_call_center() -> list[dict]:
    """Dedup archives + basenames, sample train/test disjoint, label legit."""
    seen_basenames: set[str] = set()
    collected: list[tuple[str, str]] = []  # (basename, text)
    for zp in sorted(config.CALL_CENTER.glob("*.zip")):
        if zp.name == CC_EXACT_DUP:
            print(f"  skipping exact-duplicate archive: {zp.name}")
            continue
        n_from_archive = 0
        with zipfile.ZipFile(zp) as zf:
            members = [n for n in zf.namelist() if n.endswith(".json")]
            for name in members:
                base = os.path.basename(name)
                if base in seen_basenames:
                    continue
                if n_from_archive >= CC_PER_ARCHIVE_CAP:
                    break
                try:
                    text = json.loads(zf.read(name)).get("text", "")
                except Exception:
                    continue
                if len(text.strip()) < 20:
                    continue
                seen_basenames.add(base)
                collected.append((base, text))
                n_from_archive += 1

    random.Random(config.RANDOM_SEED).shuffle(collected)
    need = config.CALLCENTER_TRAIN_SAMPLE + config.CALLCENTER_TEST_SAMPLE
    collected = collected[:need]
    rows = []
    for i, (base, text) in enumerate(collected):
        split = "cc_train" if i < config.CALLCENTER_TRAIN_SAMPLE else "cc_test"
        rows.append({
            "conversation_id": f"cc-{base}",
            "source_dataset": "call-center",
            "label": 0,
            "case_type": "legit_call_center",
            "domain": "call_center",
            "is_synthetic": False,
            "split": split,
            "n_turns": 0,
            "duration": None,
            "full_text_raw": text,
            "full_text_norm": asr_normalize(text),
            "turns_json": "[]",
            "chunk_analysis_json": "[]",
        })
    print(f"  call-center: {len(rows)} unique sampled "
          f"({config.CALLCENTER_TRAIN_SAMPLE} train / {config.CALLCENTER_TEST_SAMPLE} test), "
          f"from {len(seen_basenames)} deduped basenames scanned")
    return rows


def build_youtube() -> list[dict]:
    df = pd.read_csv(config.YOUTUBE_SCAM, dtype=str, keep_default_na=False)
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "conversation_id": f"yt-{r['ID']}",
            "source_dataset": "youtube-scam",
            "label": 1,
            "case_type": "real_scam_opening",
            "domain": "youtube",
            "is_synthetic": False,
            "split": "yt_test",
            "n_turns": 0,
            "duration": None,
            "full_text_raw": r["Content"],
            "full_text_norm": asr_normalize(r["Content"]),
            "turns_json": "[]",
            "chunk_analysis_json": "[]",
        })
    print(f"  youtube-scam: {len(rows)}")
    return rows


def dedup_and_check(df: pd.DataFrame) -> dict:
    """Exact-normalized dedup within corpus + cross-dataset contamination check."""
    before = len(df)
    # Within-corpus exact dup on normalized text (keep first).
    dup_mask = df["full_text_norm"].duplicated(keep="first")
    n_intra = int(dup_mask.sum())
    df.drop(index=df[dup_mask].index, inplace=True)

    # Cross-dataset contamination: normalized text present in >1 source.
    by_source = df.groupby("full_text_norm")["source_dataset"].nunique()
    contaminated_keys = by_source[by_source > 1].index
    n_cross = int(df["full_text_norm"].isin(contaminated_keys).sum())

    return {
        "rows_before_dedup": before,
        "intra_corpus_exact_dupes_removed": n_intra,
        "rows_after_dedup": len(df),
        "cross_dataset_contaminated_rows": n_cross,
    }


def main() -> None:
    config.set_global_seed()
    print("=== Phase 2a: build corpus ===")
    rows = build_icfd() + build_call_center() + build_youtube()
    df = pd.DataFrame(rows)

    report = dedup_and_check(df)
    print("\n  dedup/contamination:")
    for k, v in report.items():
        print(f"    {k}: {v}")

    print("\n  corpus by source × label:")
    print(df.groupby(["source_dataset", "label"]).size().to_string())
    print("\n  ICFD by case_type:")
    print(df[df.source_dataset == "icfd"]["case_type"].value_counts().to_string())

    df.reset_index(drop=True).to_parquet(config.CORPUS_PARQUET, index=False)
    with open(config.DEDUP_REPORT, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n  saved {config.CORPUS_PARQUET.relative_to(config.ROOT)} "
          f"({len(df)} conversations)")


if __name__ == "__main__":
    main()

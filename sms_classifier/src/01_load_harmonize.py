"""Phase 1 — Load, harmonize, deduplicate, combine.

Loads the UCI SMS Spam Collection and the Mishra/Soni SMS phishing dataset,
harmonizes them to a shared label scheme, concatenates with a `source` column,
then deduplicates ACROSS the combined data BEFORE any split is ever made — the
two corpora overlap heavily, so this is the single most important step for
honest metrics. Saves the cleaned combined set and a dedup report.
"""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd

import utils  # noqa: F401  (importing bootstraps sys.path for config/features_lib)
import config
from features_lib import normalize_for_dedup


def load_uci() -> pd.DataFrame:
    """Load UCI spam.csv: latin-1, drop trailing 'Unnamed' junk columns."""
    df = pd.read_csv(config.UCI_CSV, encoding="latin-1")
    # Keep only the first two columns (v1=label, v2=text); the rest are junk.
    df = df.iloc[:, :2]
    df.columns = ["label", "text"]
    df["label"] = df["label"].str.strip().str.lower()
    df["source"] = "uci"
    print(f"UCI: {len(df)} rows | labels: {df['label'].value_counts().to_dict()}")
    return df[["text", "label", "source"]]


def load_mishra() -> pd.DataFrame:
    """Load Mishra Dataset_5971.csv from the zip; columns LABEL, TEXT, ..."""
    with zipfile.ZipFile(config.MISHRA_ZIP) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(csv_name)
    # The file has some non-utf8 bytes; latin-1 reads every byte losslessly.
    df = pd.read_csv(io.BytesIO(raw), encoding="latin-1")
    df.columns = [c.strip().upper() for c in df.columns]
    df = df.rename(columns={"LABEL": "label", "TEXT": "text"})
    df["label"] = df["label"].str.strip().str.lower()
    df["source"] = "mishra"
    print(f"Mishra: {len(df)} rows | labels: {df['label'].value_counts().to_dict()}")
    return df[["text", "label", "source"]]


def harmonize(df: pd.DataFrame) -> pd.DataFrame:
    """Attach binary and 3-class targets; drop unknown labels."""
    known = set(config.MULTICLASS_MAP)
    before = len(df)
    df = df[df["label"].isin(known)].copy()
    if len(df) != before:
        print(f"  dropped {before - len(df)} rows with unexpected labels")
    df["y_binary"] = df["label"].map(config.BINARY_MAP)
    df["y_multiclass"] = df["label"].map(config.MULTICLASS_MAP)
    # Drop empty/whitespace-only messages.
    df["text"] = df["text"].astype(str)
    df = df[df["text"].str.strip().str.len() > 0].reset_index(drop=True)
    return df


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Remove exact and near-duplicate messages across the combined data.

    - exact: identical raw text.
    - near : identical normalized key (lowercased, punctuation stripped,
      whitespace collapsed, digits removed) — this collapses templated scams
      that differ only by a phone number or amount.

    Duplicates are reported, including how many were cross-dataset overlaps
    (the same message appearing in both corpora), and how many collapsed groups
    had conflicting labels.
    """
    n_start = len(df)

    # 1) Exact raw duplicates.
    exact_dupe_mask = df.duplicated(subset=["text"], keep="first")
    n_exact = int(exact_dupe_mask.sum())
    df = df[~exact_dupe_mask].reset_index(drop=True)

    # 2) Near-duplicates via normalized key.
    df["norm_key"] = df["text"].map(normalize_for_dedup)
    df = df[df["norm_key"].str.len() > 0].reset_index(drop=True)

    # Analyse groups before dropping.
    grp = df.groupby("norm_key")
    group_sizes = grp.size()
    dup_groups = group_sizes[group_sizes > 1]

    # Cross-dataset overlap: normalized keys present in BOTH sources.
    sources_per_key = grp["source"].nunique()
    cross_keys = set(sources_per_key[sources_per_key > 1].index)
    n_cross_overlap_rows = int(df["norm_key"].isin(cross_keys).sum())

    # Label conflicts within a normalized group.
    labels_per_key = grp["label"].nunique()
    conflict_keys = set(labels_per_key[labels_per_key > 1].index)
    n_conflict_groups = len(conflict_keys)

    # Drop near-duplicates, keeping the first occurrence of each key.
    near_dupe_mask = df.duplicated(subset=["norm_key"], keep="first")
    n_near = int(near_dupe_mask.sum())
    df = df[~near_dupe_mask].reset_index(drop=True)

    df = df.drop(columns=["norm_key"])

    report = {
        "rows_before_dedup": n_start,
        "exact_raw_duplicates_removed": n_exact,
        "near_duplicates_removed": n_near,
        "total_removed": n_exact + n_near,
        "rows_after_dedup": len(df),
        "duplicate_groups": int((dup_groups).shape[0]),
        "cross_dataset_overlap_rows": n_cross_overlap_rows,
        "label_conflict_groups": n_conflict_groups,
    }
    return df, report


def main() -> None:
    config.set_global_seed()
    print("=== Phase 1: load, harmonize, deduplicate ===")

    uci = harmonize(load_uci())
    mishra = harmonize(load_mishra())

    combined = pd.concat([uci, mishra], ignore_index=True)
    print(f"\nCombined (pre-dedup): {len(combined)} rows")
    print(f"  by source: {combined['source'].value_counts().to_dict()}")

    clean, report = deduplicate(combined)

    print("\n--- Dedup report ---")
    for k, v in report.items():
        print(f"  {k}: {v}")

    print("\n--- Final combined dataset ---")
    print(f"  rows: {len(clean)}")
    print(f"  binary:     {clean['label'].map(config.BINARY_MAP).map(config.BINARY_NAMES).value_counts().to_dict()}")
    print(f"  3-class:    {clean['label'].value_counts().to_dict()}")
    print(f"  by source:  {clean['source'].value_counts().to_dict()}")
    print("  label x source:")
    print(clean.groupby(["source", "label"]).size().to_string())

    clean.to_parquet(config.COMBINED_CLEAN, index=False)
    with open(config.LABEL_MAP_JSON, "w") as fh:
        json.dump(
            {
                "binary_map": config.BINARY_MAP,
                "binary_names": config.BINARY_NAMES,
                "multiclass_map": config.MULTICLASS_MAP,
                "multiclass_names": config.MULTICLASS_NAMES,
            },
            fh,
            indent=2,
        )
    with open(config.DEDUP_REPORT_JSON, "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"\nSaved: {config.COMBINED_CLEAN.relative_to(config.ROOT)}")
    print(f"Saved: {config.DEDUP_REPORT_JSON.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

"""Phase 3 & 4 — Feature engineering + the split/validation protocol.

Creates the stratified train/val/test split ONCE and saves it (the split is the
contract every later script obeys, so results are reproducible and the test set
stays sacred). Also computes the engineered numeric features and reports how
separable they are from the binary target — a quick, honest read on signal
before any modelling.

Vectorizers are NOT fit here: they are fit on the training split inside the
model pipelines (phases 5–6). This script only defines the split and the
engineered-feature view of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

import utils
import config
from features_lib import engineered_features, ENGINEERED_COLUMNS

plt = utils.plt


def make_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Stratified 70/15/15 train/val/test, stratified on the 3-class label.

    Stratifying on the finer 3-class label also keeps the binary balance and
    guarantees the rare smishing class is represented in every split.
    """
    idx = np.arange(len(df))
    # First carve out the test set (15%).
    train_val_idx, test_idx = train_test_split(
        idx, test_size=config.TEST_SIZE, random_state=config.RANDOM_SEED,
        stratify=df["y_multiclass"].values,
    )
    # Then split the remainder into train and val so val is 15% of the whole.
    val_fraction = config.VAL_SIZE / (1.0 - config.TEST_SIZE)
    train_idx, val_idx = train_test_split(
        train_val_idx, test_size=val_fraction, random_state=config.RANDOM_SEED,
        stratify=df.iloc[train_val_idx]["y_multiclass"].values,
    )

    split = np.empty(len(df), dtype=object)
    split[train_idx] = "train"
    split[val_idx] = "val"
    split[test_idx] = "test"
    out = df.copy()
    out["split"] = split
    return out


def report_split(df: pd.DataFrame) -> dict:
    summary = {}
    for name in ["train", "val", "test"]:
        sub = df[df["split"] == name]
        summary[name] = {
            "n": int(len(sub)),
            "binary": sub["label"].map(config.BINARY_MAP)
            .map(config.BINARY_NAMES).value_counts().to_dict(),
            "multiclass": sub["label"].value_counts().to_dict(),
        }
    return summary


def fig_feature_separability(df: pd.DataFrame, feats: pd.DataFrame) -> dict:
    """Point-biserial correlation of each engineered feature with y_binary."""
    y = df["y_binary"].values.astype(float)
    corrs = {}
    for col in ENGINEERED_COLUMNS:
        x = feats[col].values.astype(float)
        if x.std() == 0:
            corrs[col] = 0.0
        else:
            corrs[col] = float(np.corrcoef(x, y)[0, 1])
    order = sorted(corrs, key=lambda c: abs(corrs[c]))
    vals = [corrs[c] for c in order]
    colors = ["#C62828" if v > 0 else "#2E7D32" for v in vals]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(order, vals, color=colors, alpha=0.85)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel("correlation with 'malicious' (positive → indicates malicious)")
    ax.set_title("Engineered-feature separability (point-biserial r)",
                 fontsize=12, fontweight="bold")
    utils.savefig(fig, "08_feature_separability.png")
    return {c: round(corrs[c], 3) for c in reversed(order)}


def main() -> None:
    config.set_global_seed()
    print("=== Phase 3&4: features + split protocol ===")
    df = utils.load_combined()

    split_df = make_splits(df)
    split_df.to_parquet(config.SPLIT_PARQUET, index=False)
    summary = report_split(split_df)
    print("Split sizes:")
    for name, s in summary.items():
        print(f"  {name:5s}: n={s['n']:5d}  binary={s['binary']}  3-class={s['multiclass']}")

    feats = engineered_features(df["text"])
    sep = fig_feature_separability(df, feats)
    print("\nTop engineered features by |correlation| with malicious:")
    for c, v in list(sep.items())[:6]:
        print(f"  {c:16s} r={v:+.3f}")

    utils.update_metrics("split", {"summary": summary, "feature_separability": sep})
    print(f"\nSaved split: {config.SPLIT_PARQUET.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()

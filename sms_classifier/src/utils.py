"""Shared helpers: path bootstrap, headless plotting, metrics, IO.

Imported by the numbered pipeline scripts. Kept un-numbered so it is importable
(module names cannot start with a digit).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# --- Make the project root importable so scripts can `import config`. --------
_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Headless plotting — never open a window; always save to disk.
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402


def savefig(fig, name: str, dpi: int = 160) -> Path:
    """Save a figure to reports/figures/<name> and close it."""
    path = config.FIGURES_DIR / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved figure: {path.relative_to(config.ROOT)}")
    return path


def load_combined() -> pd.DataFrame:
    """Load the cleaned, deduped, harmonized combined dataset."""
    return pd.read_parquet(config.COMBINED_CLEAN)


def load_splits() -> pd.DataFrame:
    """Load the combined data with a `split` column (train/val/test)."""
    return pd.read_parquet(config.SPLIT_PARQUET)


def split_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (train, val, test) frames from the saved split assignment."""
    df = load_splits()
    return (
        df[df["split"] == "train"].reset_index(drop=True),
        df[df["split"] == "val"].reset_index(drop=True),
        df[df["split"] == "test"].reset_index(drop=True),
    )


def update_metrics(section: str, payload: dict) -> None:
    """Merge a result block into reports/metrics.json under `section`."""
    metrics: dict = {}
    if config.METRICS_JSON.exists():
        with open(config.METRICS_JSON) as fh:
            metrics = json.load(fh)
    metrics[section] = payload
    with open(config.METRICS_JSON, "w") as fh:
        json.dump(metrics, fh, indent=2, default=_json_default)
    print(f"  wrote metrics['{section}'] -> {config.METRICS_JSON.name}")


def read_metrics() -> dict:
    if config.METRICS_JSON.exists():
        with open(config.METRICS_JSON) as fh:
            return json.load(fh)
    return {}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    return str(o)


def false_positive_rate(y_true, y_pred) -> float:
    """FP rate on the legitimate class for the BINARY target (0=legit,1=malicious).

    FPR = P(pred malicious | truly legit) = FP / (FP + TN).
    This is the product's headline metric.
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    legit = y_true == 0
    n_legit = int(legit.sum())
    if n_legit == 0:
        return float("nan")
    fp = int(((y_pred == 1) & legit).sum())
    return fp / n_legit

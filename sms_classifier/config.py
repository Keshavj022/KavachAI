"""Central configuration for the SMS spam / smishing classifier.

Single source of truth for the random seed, paths, split ratios and model
settings so every script is reproducible and consistent. Import from here;
do not hardcode paths or seeds in the scripts.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np

# --- Reproducibility --------------------------------------------------------
RANDOM_SEED = 42


def set_global_seed(seed: int = RANDOM_SEED) -> None:
    """Seed every RNG we can, including torch if it is installed."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:  # torch is optional (only needed for the transformer phase)
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


# --- Paths ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent

# Raw sources (already present in the working area).
UCI_CSV = ROOT / "spam.csv"
MISHRA_ZIP = (
    ROOT
    / "SMS PHISHING DATASET FOR MACHINE LEARNING AND PATTERN RECOGNITION"
    / "Dataset_5971.zip"
)

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
METRICS_JSON = REPORTS_DIR / "metrics.json"

for _d in (DATA_RAW, DATA_PROCESSED, MODELS_DIR, REPORTS_DIR, FIGURES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Processed artefacts.
COMBINED_CLEAN = DATA_PROCESSED / "combined_clean.parquet"
SPLIT_PARQUET = DATA_PROCESSED / "splits.parquet"  # rows tagged train/val/test
LABEL_MAP_JSON = DATA_PROCESSED / "label_maps.json"
DEDUP_REPORT_JSON = DATA_PROCESSED / "dedup_report.json"

# --- Targets ----------------------------------------------------------------
# Primary binary target: legit (0) vs malicious (1).
BINARY_MAP = {"ham": 0, "spam": 1, "smishing": 1}
BINARY_NAMES = {0: "legit", 1: "malicious"}
# Secondary 3-class target.
MULTICLASS_MAP = {"ham": 0, "spam": 1, "smishing": 2}
MULTICLASS_NAMES = {0: "ham", 1: "spam", 2: "smishing"}

# --- Splits -----------------------------------------------------------------
TEST_SIZE = 0.15
VAL_SIZE = 0.15  # of the whole; train is the remaining 0.70
CV_FOLDS = 5

# --- Transformer settings ---------------------------------------------------
TRANSFORMER_MODEL = "distilbert-base-uncased"
TRANSFORMER_MAX_LEN = 128
TRANSFORMER_EPOCHS = 4
TRANSFORMER_BATCH = 16
TRANSFORMER_LR = 2e-5

"""Configuration for the call-model training pipeline.

Single source of truth for the seed, paths, split ratios, thresholds and model
settings. The runtime backend loads the artifacts this pipeline produces.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import numpy as np

RANDOM_SEED = 42


def set_global_seed(seed: int = RANDOM_SEED) -> None:
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


# --- Paths ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent            # call_classifier/
REPO_ROOT = ROOT.parent                           # KavachAI/
BACKEND = REPO_ROOT / "backend"

RAW = ROOT / "data" / "raw"
ICFD = RAW / "icfd"
CALL_CENTER = RAW / "call-center"
YOUTUBE_SCAM = RAW / "youtube-scam" / "FullTranscriptData.csv"

PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "data" / "artifacts"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
METRICS_JSON = REPORTS / "metrics.json"

for _d in (PROCESSED, ARTIFACTS, REPORTS, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

# Processed artefacts.
CORPUS_PARQUET = PROCESSED / "corpus_conversations.parquet"   # conversation-level
CHUNKS_PARQUET = PROCESSED / "corpus_chunks.parquet"          # chunk-level (post-split)
STAGE_LABELS_DIR = PROCESSED / "stage_labels"                 # cached Groq annotations
DEDUP_REPORT = PROCESSED / "dedup_report.json"

# Make the backend importable so we share ONE asr_normalize implementation.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# --- Split ------------------------------------------------------------------
TEST_SIZE = 0.15
VAL_SIZE = 0.15
CV_FOLDS = 5

# --- call-center sampling ---------------------------------------------------
CALLCENTER_TRAIN_SAMPLE = 5000
CALLCENTER_TEST_SAMPLE = 2000

# --- Chunk training sampling (1.1M chunks is a lot; cap chunks/conversation to
#     keep TF-IDF/transformer training tractable — stated in the report). ---
MAX_CHUNKS_PER_CONVERSATION = 8

# --- Interrupt logic --------------------------------------------------------
INTERRUPT_THRESHOLD = 0.7
SCAM_RECALL_FLOOR = 0.90  # threshold chosen on val must keep >= this

# --- Groq annotation (BUILD TIME ONLY) --------------------------------------
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Bound the annotation run so it completes in-session; raise to scale up. The
# script is resumable (caches per-conversation), so re-runs extend coverage.
ANNOTATE_MAX_TRAIN_VAL = int(os.environ.get("ANNOTATE_MAX_TRAIN_VAL", "500"))
ANNOTATE_MAX_TEST = int(os.environ.get("ANNOTATE_MAX_TEST", "150"))

# --- Transformer (optional head-to-head; sampled for tractability) ----------
TRANSFORMER_MODEL = "distilbert-base-uncased"
TRANSFORMER_MAX_LEN = 192
TRANSFORMER_EPOCHS = 2
TRANSFORMER_TRAIN_SAMPLE = 40000  # chunks

STAGES = ["none", "authority_claim", "accusation", "isolation", "money_demand"]
STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}

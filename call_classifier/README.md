# Call Classifier — On-Device Scam-Call Detection Pipeline

> Reproducible ML pipeline that builds the on-device scam-call classifier and arc
> tracker from audited public datasets. Produces the trained artifacts that ship in
> `backend/app/ml/models/call/` and power Kavach's Live Call Guard at runtime.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Sources](#data-sources)
- [Pipeline Steps](#pipeline-steps)
- [Models](#models)
- [Evaluation Results](#evaluation-results)
- [Inference API](#inference-api)
- [Environment Variables](#environment-variables)
- [Setup & Run](#setup--run)
- [Limitations](#limitations)

---

## Executive Summary

- **Deployed classifier:** TF-IDF (word + char n-grams) + Logistic Regression, **12.4 MB**,
  <1 ms/chunk on CPU. Threshold **0.735** (chosen on validation for scam recall ≥ 0.90).
- **0% false-positive rate on real legitimate call-center calls** (5,781 chunks).
- **55.6% recall on real scam openings** (youtube-scam, 243 transcripts) — the
  synthetic→real distribution shift reported plainly.
- **ICFD test: macro-F1 0.935, ROC-AUC 0.985.**
- A DistilBERT head-to-head was run (val macro-F1 0.940 vs 0.934) — it edges the linear
  model slightly but is ~22× larger (269 MB), so the tiny linear model is the on-device choice.
- **Runtime detection is entirely local.** No network call, no API key. LLMs were used
  only at build time to annotate stage labels on public data.

---

## Architecture

```
Audio chunk / demo tick
   → local Whisper transcribe (rolling in-memory buffer, discarded)
   → asr_normalize (shared with backend)
   → identifier extraction → known-scammer lookup (instant verdict if hit)
   → trained TF-IDF + LogReg classifier (scam probability + category)
   → trained TF-IDF + LogReg arc tracker (stage: none → authority_claim →
     accusation → isolation → money_demand)
   → deterministic cue backstop (keyword rules for safety-critical stages)
   → monotonic enforcement (stage never regresses)
   → deterministic interrupt rule:
       interrupt = (scam_prob ≥ 0.735) AND (stage ≥ isolation)
       warn     = (scam_prob ≥ 0.735) AND (stage == accusation)
   → pre-written de-escalation template (LLM never authors safety-critical text)
```

---

## Tech Stack

| Category | Technology |
| --- | --- |
| **Language** | Python 3.11–3.13 |
| **ML / Data** | scikit-learn 1.5.2, pandas 2.2, numpy 1.26, scipy 1.14, joblib 1.4 |
| **Data Storage** | Parquet (pyarrow 18.1), zstandard (for `.jsonl.zst` raw data) |
| **Plotting** | matplotlib 3.9 (headless) |
| **Build-Time Annotation** | Groq API (httpx 0.28, python-dotenv 1.0) |
| **Optional Transformer** | torch 2.8, transformers 4.46, datasets 3.1, accelerate 1.1 |

---

## Project Structure

```
call_classifier/
├── config.py                          # Master config (paths, seeds, splits, thresholds)
├── requirements.txt                   # Pinned dependencies
│
├── data/
│   ├── raw/                           # Raw datasets (gitignored)
│   │   ├── icfd/                      # Indian Conversational Fraud Dataset (31K conversations)
│   │   ├── call-center/               # Real call-center transcripts (6,857 unique)
│   │   └── youtube-scam/              # Real scam openings (243 transcripts)
│   ├── processed/                     # Pipeline outputs
│   │   ├── corpus_conversations.parquet
│   │   ├── corpus_chunks.parquet      # 267K cumulative-prefix chunks
│   │   ├── dedup_report.json
│   │   └── stage_labels/             # Groq annotations (firewalled train_val / test)
│   └── artifacts/                     # Trained model artifacts
│       ├── call_classifier.joblib     # Deployed scam classifier (12.4 MB)
│       ├── call_arc_tracker.joblib    # Deployed arc tracker (2.5 MB)
│       ├── call_deployment.json       # Deployment metadata
│       └── arc_tracker_meta.json
│
├── src/                               # Pipeline scripts (run in order)
│   ├── 01_build_corpus.py             # Ingest, normalize, dedup
│   ├── 02_split.py                    # Stratified split + cumulative chunk expansion
│   ├── 03_annotate_stages.py          # Offline Groq LLM stage annotation
│   ├── 04_train_classifier.py         # Train binary classifiers + DistilBERT benchmark
│   ├── 05_train_arc_tracker.py        # Train multinomial stage tracker
│   ├── 06_evaluate.py                 # Test-set evaluation + lead-time metric
│   ├── 07_error_analysis.py           # Verbatim error breakdown
│   └── predict.py                     # Inference API: CallDetector class
│
├── eval/                              # Legacy LLM evaluation suite
│   ├── run_eval.py
│   ├── REPORT.md
│   └── metrics.json
│
├── exploration/                       # Intake audit & exploratory analysis
│   ├── REPORT.md                      # 10-finding intake audit
│   ├── stats.json
│   ├── schemas/
│   ├── samples/
│   └── scripts/
│
└── reports/                           # Pipeline output reports
    ├── REPORT.md                      # Full training & evaluation report
    ├── error_analysis.md              # Verbatim false positives/negatives
    ├── metrics.json                   # Machine-readable metrics
    ├── stage_annotation_samples.md    # Annotation samples for review
    └── figures/                       # Evaluation charts (PNG)
```

---

## Data Sources

| Source | Size | Role | Notes |
| --- | --- | --- | --- |
| **ICFD** (Indian Conversational Fraud Dataset) | 31,000 conversations (16,393 scam / 14,607 legit) | Primary train/val/test | Synthetic LLM-generated; 4 case types |
| **call-center** | ~6,857 unique transcripts | Real legitimate negatives | Prevents false alarms on ordinary calls |
| **youtube-scam** | 243 transcripts | Held-out real scam test | Real ASR scam openings from scambaiter videos |
| **call-transcript** | — | **Excluded** | Corrupt CSV + synthetic despite "real" billing |

### Data Pipeline

1. **Normalization** (`01_build_corpus.py`): Raw transcripts pass through `asr_normalize()`
   (shared with the backend). 143 duplicate conversations removed.
2. **Stratified Split** (`02_split.py`): ICFD split 70/15/15 at the **conversation level**,
   stratified on `case_type × domain`. Zero data leakage.
3. **Chunk Expansion** (`02_split.py`): Conversations expanded into cumulative prefixes
   **after splitting**. ICFD: cumulative turn-prefixes (capped at 8/conversation).
   call-center: word-prefixes (35%, 60%, 100%). **267,095 total chunks**.

---

## Pipeline Steps

Run each script in order from the `call_classifier` root:

```bash
python src/01_build_corpus.py      # Ingest, normalize, dedup → corpus_conversations.parquet
python src/02_split.py             # Stratified split + chunk expansion → corpus_chunks.parquet
python src/03_annotate_stages.py   # Offline Groq annotation (or rule fallback)
python src/04_train_classifier.py  # Train classifiers + DistilBERT benchmark
python src/05_train_arc_tracker.py # Train arc stage tracker
python src/06_evaluate.py          # Evaluate on 3 test sets + lead-time scoring
python src/07_error_analysis.py    # Generate error analysis report
```

### Stage Annotation (`03_annotate_stages.py`)

No dataset ships with per-turn scam-arc stages. Groq (`llama-3.3-70b-versatile`) annotates
500 train/val + 150 test conversations with monotonic stages:

1. `none` → 2. `authority_claim` → 3. `accusation` → 4. `isolation` → 5. `money_demand`

Test annotations are **firewalled** (separate file, used only for lead-time scoring).
If `GROQ_API_KEY` is missing, a deterministic keyword-matching fallback runs automatically.

---

## Models

### Binary Classifier (Scam vs. Legit)

| Model | Val Macro-F1 | Val FP-Rate | Val Recall | Val ROC-AUC | Size | Latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Logistic Regression (deployed)** | **0.934** | **0.029** | **0.90** | **0.984** | **12.4 MB** | **0.9 ms** |
| Linear SVM | 0.934 | 0.029 | 0.90 | 0.983 | 12.4 MB | 0.9 ms |
| Complement NB | 0.911 | 0.077 | 0.90 | 0.969 | 24 MB | 2.0 ms |
| DistilBERT (40K chunks, 2 epochs) | **0.940** | — | — | — | 269 MB | ~40 min train |

**Features:** `FeatureUnion` of word n-grams (1,2) + char n-grams (2,5) with sublinear TF.

### Arc Stage Tracker

TF-IDF + multinomial Logistic Regression, **2.5 MB**. Predicts the active scam stage for
each cumulative chunk. Monotonic enforcement + deterministic cue backstop at runtime.

---

## Evaluation Results

| Test Set | Metric | Result |
| --- | --- | --- |
| **Real legitimate (call-center)** | FP Rate | **0.00%** (0 / 5,781 chunks) |
| **ICFD re-split test** | Macro-F1 / ROC-AUC | **0.935** / **0.985** |
| — Ambiguous but Ultimately Normal | FP Rate | 2.05% |
| — Clear Normal | FP Rate | 3.19% |
| — Clear Fraud / Subtle Fraud | Recall | 93.7% / 91.2% |
| **Real scam openings (youtube-scam)** | Recall | **55.6%** (135 / 243) |

### Lead Time (Hero Metric)

- Interrupt fired in **114/150** test scam calls
- Fired at-or-before money demand in **48/67** calls that reach a money demand
- **Median lead = 0 turns** (honest limitation — isolation is under-labelled)

---

## Inference API

The `CallDetector` class in `src/predict.py` provides a stateful, per-call interface:

```python
from predict import CallDetector

detector = CallDetector()  # One instance per call (maintains state)
result = detector.analyze("caller: this is the CBI cyber cell... transfer funds to a safe account")
```

**Output:**
```json
{
  "scam_probability": 0.9421,
  "stage": "money_demand",
  "verdict": "scam",
  "interrupt": true,
  "warn": false,
  "de_escalation": "This is a scam. No genuine agency asks you to transfer money..."
}
```

### Interrupt Logic (Deterministic)

```
interrupt = (scam_prob ≥ 0.735) AND (stage ≥ isolation)
warn      = (scam_prob ≥ 0.735) AND (stage == accusation)
money_demand reached with no prior interrupt → interrupt immediately
```

---

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | For annotation only | — | Groq API key (build-time stage labelling) |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model override |
| `ANNOTATE_MAX_TRAIN_VAL` | No | `500` | Max conversations to annotate (train/val) |
| `ANNOTATE_MAX_TEST` | No | `150` | Max conversations to annotate (test) |

> **Zero environment variables are required for inference.** The trained artifacts run
> entirely locally.

---

## Setup & Run

```bash
cd call_classifier
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the full pipeline
python src/01_build_corpus.py
python src/02_split.py
python src/03_annotate_stages.py     # Uses GROQ_API_KEY if present, else rule fallback
python src/04_train_classifier.py
python src/05_train_arc_tracker.py
python src/06_evaluate.py
python src/07_error_analysis.py

# Test inference
python src/predict.py
```

Python 3.11–3.13. The transformer stack (torch/transformers/datasets/accelerate) is only
needed for the DistilBERT benchmark in `04_train_classifier.py`; the rest of the pipeline
runs without it.

---

## Limitations

1. **Synthetic→real gap.** Models trained on synthetic ICFD catch 90% of ICFD scam chunks
   but only 56% of real ASR scam openings. Reported plainly, not hidden.
2. **Isolation under-labelling.** Only 40 training examples for the `isolation` stage,
   directly hurting lead time. The cue-rule backstop mitigates this.
3. **Lead time is ~0 turns.** Many ICFD scams skip isolation (authority → money directly).
   Better isolation coverage — not a model-architecture change — is the fix.
4. **No data leakage.** Split at conversation level before chunk expansion. 0 cross-dataset
   overlaps confirmed by audit.

---

*Read `reports/REPORT.md` for the full training & evaluation report with figures and
verbatim error analysis.*

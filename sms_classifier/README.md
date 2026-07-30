# SMS Classifier — On-Device Spam / Smishing Detection Pipeline

> Leakage-controlled, FP-rate-first SMS classifier built from two public datasets.
> Classical TF-IDF baselines and a fine-tuned DistilBERT are compared head-to-head
> on one sacred test set. The deployed model is a **TF-IDF + Linear SVM** at a
> **0.27% false-positive rate**.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Sources & Deduplication](#data-sources--deduplication)
- [Feature Engineering](#feature-engineering)
- [Pipeline Steps](#pipeline-steps)
- [Models](#models)
- [Evaluation Results](#evaluation-results)
- [Inference API](#inference-api)
- [Setup & Run](#setup--run)
- [Limitations](#limitations)

---

## Executive Summary

| Metric (Sacred Test Set) | Value |
| --- | --- |
| **False-positive rate (legit → malicious)** | **0.27%** (2 / 749 legit) |
| Malicious recall | 93.4% |
| Malicious precision | 98.6% |
| Macro-F1 | 0.976 |
| ROC-AUC / PR-AUC | 0.998 / 0.993 |

- **Deployed model:** TF-IDF (word + char n-grams) + engineered features → Linear SVM,
  threshold **0.505** (chosen on validation, not test).
- **Sub-millisecond inference** on CPU, ~3 MB model size.
- **DistilBERT did not beat** the TF-IDF baselines on this data — the tiny, fast classical
  model is the recommended choice for on-device deployment.
- **Key limitation:** After leakage-safe deduplication, only 178 unique smishing messages
  remain. The 3-class model catches smishing at only ~44% recall, but the **binary model**
  catches smishing *as malicious* with >93% recall.

---

## Tech Stack

| Category | Technology |
| --- | --- |
| **Language** | Python 3.11–3.13 |
| **Classical ML** | scikit-learn 1.5.2 (LinearSVC, LogReg, NB, TfidfVectorizer, Pipeline) |
| **Data** | pandas 2.2, numpy 1.26, scipy 1.14, pyarrow 18.1 |
| **Serialization** | joblib 1.4 |
| **Plotting** | matplotlib 3.9 (headless), wordcloud 1.9 |
| **Optional Transformer** | torch 2.8, transformers 4.46, datasets 3.1, accelerate 1.1 |

---

## Project Structure

```
sms_classifier/
├── config.py                          # Seeds, paths, split ratios, model settings
├── requirements.txt                   # Pinned dependencies
├── spam.csv                           # UCI SMS Spam Collection source (given)
├── SMS PHISHING DATASET .../          # Mishra & Soni source (given)
│   └── Dataset_5971.zip
│
├── data/
│   ├── raw/                           # Workspace for unzipped data
│   └── processed/
│       ├── combined_clean.parquet     # Cleaned, deduplicated dataset (5,895 rows)
│       ├── splits.parquet             # Train (70%) / Val (15%) / Test (15%)
│       ├── label_maps.json            # Binary + 3-class target mappings
│       └── dedup_report.json          # Deduplication statistics
│
├── models/                            # Saved model artifacts
│   ├── baseline_linear_svm_binary.joblib   # ← Deployed model
│   ├── baseline_logreg_binary.joblib
│   ├── baseline_multinomial_nb_binary.joblib
│   ├── baseline_complement_nb_binary.joblib
│   ├── deployment.json                # Deployed model metadata + test metrics
│   └── transformer_binary/            # Fine-tuned DistilBERT checkpoint
│
├── src/
│   ├── utils.py                       # Shared helpers (headless plotting, metrics, IO)
│   ├── features_lib.py               # Text normalization + engineered features transformer
│   ├── 01_load_harmonize.py           # Load UCI + Mishra, harmonize, dedup
│   ├── 02_eda.py                      # EDA figures + stats
│   ├── 03_features.py                 # Stratified split + feature separability analysis
│   ├── 04_baselines.py                # Train classical models (5-fold CV + val)
│   ├── 05_transformer.py              # Fine-tune DistilBERT (optional, ~2.4 min on MPS)
│   ├── 06_evaluate.py                 # Sacred test-set eval, threshold tuning, deployment
│   ├── 07_error_analysis.py           # FP/FN inspection for deployed model
│   └── predict.py                     # Inference: classify(text) → {label, prob, threshold}
│
└── reports/
    ├── REPORT.md                      # Full findings report
    ├── metrics.json                   # Machine-readable results for all phases
    ├── false_positives.csv            # Test-set false positives (2 messages)
    ├── false_negatives.csv            # Test-set false negatives (9 messages)
    └── figures/                       # 14 evaluation figures (PNG)
```

---

## Data Sources & Deduplication

### Raw Sources

| Source | Rows | Labels |
| --- | --- | --- |
| UCI `spam.csv` (latin-1) | 5,572 | ham 4,825 / spam 747 |
| Mishra `Dataset_5971.csv` (from zip) | 5,971 | ham 4,844 / spam 489 / smishing 638 |

### Target Mapping

- **Binary (primary):** `ham → legit (0)`, `spam + smishing → malicious (1)`
- **3-class (secondary):** `ham (0)`, `spam (1)`, `smishing (2)`

### Deduplication (the #1 risk)

The two corpora overlap heavily — without cross-source dedup, the same message lands on
both sides of a split and inflates every metric.

| Step | Count |
| --- | --- |
| Combined (pre-dedup) | 11,543 |
| Exact raw duplicates removed | 4,735 |
| Near-duplicates removed (normalized: lowercase, strip punctuation, **drop digits**) | 909 |
| Cross-dataset overlap rows | 1,498 |
| Label-conflict groups | 203 |
| **Final unique messages** | **5,895** (4,988 legit / 907 malicious) |

The digit-stripping normalization collapses templated scams differing only by phone/amount
to prevent template leakage across splits.

---

## Feature Engineering

Defined in `src/features_lib.py`:

1. **Word TF-IDF:** 1–2 grams, `min_df=2`, `sublinear_tf=True`
2. **Char TF-IDF:** `char_wb` 2–5 grams, `min_df=3`, `sublinear_tf=True` (catches
   obfuscation like `fr€e`, `w1n`)
3. **11 Engineered Features** (via `EngineeredFeatures` transformer + `MaxAbsScaler`):

| Feature | Correlation with Malicious |
| --- | --- |
| `has_phone` | +0.84 |
| `digit_ratio` | +0.78 |
| `n_scam_keywords` | +0.70 |
| `has_currency` | +0.51 |
| `has_url` | +0.42 |
| `n_chars`, `n_words`, `avg_word_len` | moderate |
| `upper_ratio`, `punct_ratio`, `has_email` | weak |

---

## Pipeline Steps

```bash
source venv/bin/activate

python src/01_load_harmonize.py     # Load, harmonize, dedup → combined_clean.parquet
python src/02_eda.py                # EDA figures + stats
python src/03_features.py           # Stratified split + feature separability
python src/04_baselines.py          # TF-IDF + LogReg / SVM / NB (CV + val)
python src/05_transformer.py        # Fine-tune DistilBERT (optional; ~2-3 min MPS)
python src/06_evaluate.py           # Sacred test-set eval, threshold, deployment.json
python src/07_error_analysis.py     # FP/FN inspection for deployed model
```

Each script is runnable independently once the ones it depends on have produced their
artifacts. All persisted under `data/processed/` and `models/`.

---

## Models

### Binary Classifier Comparison (Sacred Test Set)

| Model | Threshold | FPR | Mal. Recall | Macro-F1 | ROC-AUC | PR-AUC |
| --- | --- | --- | --- | --- | --- | --- |
| **Linear SVM (deployed)** | **0.505** | **0.27%** | **93.4%** | **0.976** | **0.998** | **0.993** |
| Logistic Regression | 0.540 | 0.27% | 93.4% | 0.976 | 0.997 | 0.990 |
| Multinomial NB | 0.740 | 0.53% | 95.6% | 0.978 | 0.989 | 0.978 |
| Complement NB | 0.940 | 0.53% | 95.6% | 0.978 | 0.989 | 0.978 |
| DistilBERT (fine-tuned) | 0.950 | 0.40% | 93.4% | 0.974 | 0.996 | 0.987 |

**Why Linear SVM:** Lowest FPR (0.27%) alongside LogReg, highest validation ROC-AUC,
smallest and fastest model. One caveat: `LinearSVC` has no native probabilities — the score
is a sigmoid of the SVM margin, monotonic but uncalibrated.

### 3-Class Results

| Model | Macro-F1 | Smishing Recall | Spam Recall |
| --- | --- | --- | --- |
| Linear SVM | 0.788 | 44% | 86% |
| Logistic Regression | 0.771 | 44% | 83% |

**Product implication:** Use the binary model. It catches smishing *as malicious* at >93%
recall. The specific "smishing vs spam" label is unreliable with only 178 unique smishing
examples.

---

## Evaluation Results

### Error Analysis (Deployed Linear SVM, threshold 0.505)

- **False positives (2):** A "guess the number" chain-game message full of digits, and a
  prepaid refill notification with currency. Both trip the digit/currency features.
- **False negatives (9):** All 9 are conversational-style **spam** (no links, no phone
  numbers) — the model keys on surface markers. **Zero smishing was missed.**

---

## Inference API

```python
from predict import classify

result = classify("Your KYC expires today. Click http://bit.ly/kyc to avoid blocking.")
# → {"label": "malicious", "malicious_probability": 0.73, "threshold": 0.505}

result = classify("Hey, are you coming to dinner tonight?")
# → {"label": "legit", "malicious_probability": 0.02, "threshold": 0.505}
```

The `classify()` function caches the model on first call (`@lru_cache`), maps the SVM
decision function through a sigmoid, and compares against the deployed threshold.

---

## Setup & Run

```bash
cd sms_classifier
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the full pipeline (in order)
python src/01_load_harmonize.py
python src/02_eda.py
python src/03_features.py
python src/04_baselines.py
python src/05_transformer.py       # Optional — skip if no GPU/MPS
python src/06_evaluate.py
python src/07_error_analysis.py

# Test inference
python src/predict.py
```

Python 3.11–3.13. The transformer stack is only needed for `05_transformer.py`; the rest
runs without it, and `06_evaluate.py` simply skips the transformer if its model is absent.

---

## Limitations

1. **Small effective smishing set.** Leakage-safe dedup leaves only 178 unique smishing
   messages. The 3-class smishing head is weak; its metrics are high-variance.
2. **Small test set.** 885 rows means each false positive moves FPR by ~0.13%. Top model
   differences are within noise.
3. **Domain shift.** Both corpora are older UK/India-flavoured English. Real deployment
   traffic (current scams, Hindi/Hinglish, regional languages) will differ.
4. **Uncalibrated SVM score.** The deployed "probability" is a sigmoid of the SVM margin,
   not calibrated. Use Logistic Regression as a drop-in replacement if calibrated
   probabilities matter.

---

## Notes

- **Reproducible:** `RANDOM_SEED = 42` everywhere; library versions pinned in
  `requirements.txt`.
- All plots written to `reports/figures/` (headless matplotlib); nothing shown interactively.
- No environment variables required. No network calls.
- **Read `reports/REPORT.md` for the full findings** (summary, comparison table, chosen
  model + threshold + rationale, error analysis, limitations).

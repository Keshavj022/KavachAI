# SMS Spam / Smishing Classifier — Findings

## Executive summary

Two public SMS corpora (UCI SMS Spam Collection and the Mishra & Soni SMS
phishing set) were combined, harmonized, and **deduplicated across sources
before any split** — the single most important step here, because the two sets
overlap heavily. Of **11,543** combined messages, **5,644 (49%) were
duplicates** (4,735 exact + 909 near-duplicate/templated), leaving **5,895
unique messages** (4,988 legit / 907 malicious; 15.4% malicious).

The product goal is to flag scam SMS, and the cost of a false positive on a
legitimate message is high, so **false-positive rate (FPR) is the headline
metric**, not accuracy.

**Deployed model: TF-IDF (word + char n-grams) + engineered features → Linear
SVM**, operating threshold **0.505** (chosen on validation, not test).

| Metric (sacred test set) | Value |
| --- | --- |
| **False-positive rate (legit → malicious)** | **0.27%** (2 / 749 legit) |
| Malicious recall | 93.4% |
| Malicious precision | 98.6% |
| Macro-F1 | 0.976 |
| ROC-AUC / PR-AUC | 0.998 / 0.993 |
| Accuracy | 0.988 |

A fine-tuned DistilBERT was trained head-to-head and is competitive but **did
not beat the TF-IDF baselines** on this data, at far higher compute cost — so
the tiny, fast classical model is the recommended choice.

**Key limitation:** after leakage-safe deduplication only **178 unique smishing
messages** remain, so the 3-class (ham/spam/smishing) model catches smishing
specifically at only ~44% recall. The **binary** model, however, catches
smishing *as malicious* with high recall — so the product should use the binary
model and treat fine-grained smishing-vs-spam as unreliable on current data.

---

## 1. Data, harmonization, and the leakage problem

| Source | Rows loaded | Labels |
| --- | --- | --- |
| UCI `spam.csv` (latin-1, junk cols dropped) | 5,572 | ham 4,825 / spam 747 |
| Mishra `Dataset_5971.csv` (from zip) | 5,971 | ham 4,844 / spam 489 / smishing 638 |

**Targets.** Primary = binary `legit(0)` vs `malicious(1)` (`ham→legit`,
`spam`+`smishing`→`malicious`). Secondary = 3-class `ham/spam/smishing`.

**Deduplication (the #1 risk).** The two corpora reuse messages, so without
cross-source dedup the same message can land on both sides of a split and
inflate every metric. Dedup was done on the **combined** data **before**
splitting:

| Step | Count |
| --- | --- |
| Combined (pre-dedup) | 11,543 |
| Exact raw duplicates removed | 4,735 |
| Near-duplicates removed (normalized: lowercase, punctuation-stripped, whitespace-collapsed, **digits removed** so templated scams differing only by a number/amount collapse) | 909 |
| Cross-dataset overlap rows | 1,498 |
| Label-conflict groups (same normalized text, different label) | 203 |
| **Final unique messages** | **5,895** |

The aggressive digit-stripping normalization is deliberate: mass smishing
campaigns reuse a template and vary only the phone number or amount, and keeping
those as distinct rows would leak template knowledge across the split. The cost
is that smishing collapses from 638 raw to 178 unique — a real reduction that is
reported honestly rather than hidden (see Limitations). See
`figures/07_duplicate_analysis.png`.

Final distribution: **legit 4,988 / malicious 907** (binary); **ham 4,988 /
spam 729 / smishing 178** (3-class). By source after dedup: uci 5,083 / mishra
812 — i.e. most of the Mishra rows were duplicates of UCI content.

---

## 2. EDA takeaways (figures 01–08)

- **Imbalance (fig 01).** Malicious prevalence is 15.4%, so accuracy is
  misleading — a "everything is legit" model scores 84.6%. This is why FPR and
  macro-F1 lead the reporting.
- **Length (fig 02).** Legit messages are short (median 53 chars); spam and
  smishing are long (median 147 / 139 chars). Length alone is a strong signal.
- **Engineered features (fig 03, 08).** The strongest single predictors of
  malicious, by point-biserial correlation, are `has_phone` (r=+0.84),
  `digit_ratio` (+0.78), `n_scam_keywords` (+0.70), `has_currency` (+0.51) and
  `has_url` (+0.42). The classes are highly separable, which is why simple
  models do so well.
- **Attribute presence (fig 04).** URLs appear in 0.3% of ham, 20% of spam and
  32% of smishing — URL presence is a smishing-leaning signal but far from
  sufficient on its own.
- **Vocabulary (figs 05, 06).** Top ham tokens are conversational ("just",
  "like", "good", "come"); spam/smishing are dominated by "free", "call",
  "txt", "claim", "won", "prize", "urgent" — classic marketing/scam vocabulary.

---

## 3. Protocol

Stratified **70 / 15 / 15** train / val / test split on the deduped data,
stratified on the 3-class label (which also preserves the binary balance and
guarantees the rare smishing class appears in every split). Sizes: train 4,125
/ val 885 / test 885. The split is saved (`data/processed/splits.parquet`) and
the **test set is untouched** until final evaluation. Classical model selection
uses 5-fold stratified CV on the training split; the transformer uses the
validation split for early stopping. All vectorizers/scalers are fit on the
training split only, inside pipelines.

---

## 4. Model comparison (binary, sacred test set)

Every model's operating threshold was chosen on **validation** to keep malicious
recall ≥ 0.90, then evaluated on **test**:

| Model | Thr | **FPR** | Mal. recall | Macro-F1 | ROC-AUC | PR-AUC | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Linear SVM (deployed)** | 0.51 | **0.0027** | 0.934 | 0.976 | **0.998** | **0.993** | tiny, fastest, best ranking |
| Logistic Regression | 0.54 | 0.0027 | 0.934 | 0.976 | 0.997 | 0.990 | calibrated probs |
| Multinomial NB | 0.74 | 0.0053 | 0.956 | 0.978 | 0.989 | 0.978 | highest recall |
| Complement NB | 0.94 | 0.0053 | 0.956 | 0.978 | 0.989 | 0.978 | highest recall |
| DistilBERT (fine-tuned) | 0.95 | 0.0040 | 0.934 | 0.974 | 0.996 | 0.987 | 2.4 min on MPS |

Figures: confusion matrices `cm_binary_*.png`, `figures/11_roc_curves.png`,
`figures/12_pr_curves.png`, `figures/14_model_comparison.png`.

**Why Linear SVM is deployed.** All top models are statistically near-tied — on
749 legit test messages the FPR differences are 2 vs 4 false positives, i.e.
noise. The selection criterion was pre-registered and uses **validation only**:
lowest validation FPR (at the recall floor), and among models within a small FPR
tolerance, the highest validation ROC-AUC (the most robust ranker if the
threshold is later moved). Linear SVM wins on both counts, is the smallest and
fastest model, and produces the lowest test FPR. Its one caveat: `LinearSVC`
has no native probabilities, so `predict.py` maps its decision function through
a sigmoid — a **monotonic, uncalibrated** score, fine for a fixed threshold but
not a true probability. If calibrated probabilities are required, Logistic
Regression is an equally-performing drop-in.

**DistilBERT.** Fine-tuned for 3 epochs (early-stopped) on Apple MPS in 2.4
minutes with class-weighted loss (`figures/09_transformer_training_curves.png`).
It matches but does not beat the linear models here — unsurprising: TF-IDF is
extremely strong on short, keyword-driven SMS, and 4,125 training rows is small
for a transformer's advantage to show. Given ~100× the model size and inference
cost, it is not the practical choice for this task or for on-device use.

---

## 5. Threshold analysis (fig 13)

At the default 0.5 threshold the linear models already sit at ~0.4–0.5% FPR.
Sweeping the threshold on validation (`figures/13_threshold_analysis.png`) shows
FPR falls steeply as the threshold rises while malicious recall stays flat until
~0.6, giving a comfortable operating window. The deployed threshold **0.505**
keeps malicious recall ≥ 0.90 while holding FPR at 0.27% on test. The threshold
is a single tunable knob the product can move: raising it trades a little recall
for an even lower FPR if user-trust incidents demand it.

---

## 6. 3-class results and the smishing problem

| Model | Macro-F1 | Smishing recall | Smishing precision | Spam recall |
| --- | --- | --- | --- | --- |
| Linear SVM | 0.788 | 0.44 | 0.60 | 0.86 |
| Logistic Regression | 0.771 | 0.44 | 0.52 | 0.83 |
| Multinomial NB | 0.739 | 0.22 | 0.75 | 0.95 |
| Complement NB | 0.696 | 0.15 | 0.67 | 0.95 |

Confusion matrix: `figures/10_confusion_multiclass.png`. Smishing recall tops
out at 44% — the models frequently read smishing as ordinary spam. This is a
**data limitation, not just a model one**: only 178 unique smishing messages
survive dedup (124 in train), and smishing and spam share most surface features
(links, urgency, money). **Product implication:** rely on the binary model,
which catches smishing *as malicious* at high recall, and treat the specific
"smishing vs spam" label as advisory only until more distinct smishing data is
collected.

---

## 7. Error analysis (deployed Linear SVM)

At threshold 0.505 on the test set: **2 false positives**, **9 false
negatives** (`reports/false_positives.csv`, `reports/false_negatives.csv`).

- **False positives (legit flagged, the costly error).** Both are legit
  messages that mimic spam surface form: a "guess the number" chain-game full of
  digits, and a prepaid account-refill notification (transactional + currency +
  digits). These trip the digit/currency features. Median length 34 chars — they
  are short, ambiguous messages.
- **False negatives (malicious missed).** Median length 120 chars; all 9 are
  **spam, not smishing**, and read like normal prose ("Do you realize that in
  about 40 years…", a dating-service message, a "Sunshine Hols" holiday offer
  with no link). They lack the URL/phone/keyword markers the model leans on, so
  they look conversational. Reassuringly, the model missed **no smishing** in the
  test set — the fraud-relevant class is caught.

The failure modes are coherent: the model keys on links, phone numbers, money
and urgency vocabulary, so it errs on legit messages that happen to look
transactional and on spam that is written to sound personal.

---

## 8. Model size / latency

Linear SVM + TF-IDF is a few MB and classifies a message in well under a
millisecond on CPU — trivially deployable, including on-device. DistilBERT is
~250 MB and ~100× slower per message. For equal-or-better accuracy the classical
model is the clear engineering choice; this is exactly the accuracy-vs-size
tradeoff the product should weigh, and it favours the baseline here.

---

## 9. Limitations & honest caveats

1. **Small effective smishing set.** Leakage-safe dedup leaves 178 unique
   smishing messages; the 3-class smishing head is therefore weak and its
   metrics are high-variance. More distinct smishing data is the top priority
   for improvement.
2. **Small test set.** 885 rows / 749 legit means each false positive moves the
   FPR by ~0.13%; the sub-0.5% FPR differences between the top models are within
   noise. Conclusions about *which* top model is best should be re-checked on a
   larger held-out set before over-committing.
3. **Dedup is a modelling decision.** Aggressive digit-stripping prevents
   leakage but merges some genuinely distinct messages; a milder scheme would
   retain more rows at the cost of some leakage. A handful of near-duplicate
   pairs (e.g. two "Sunshine Hols" variants) still slipped through — both landed
   in test, so they do not cause train/test leakage, but they show the
   normalization is not perfect.
4. **Domain shift.** Both corpora are older and UK/India-flavoured English.
   Real deployment traffic (current scams, other languages, transliterated
   Hindi/Hinglish) will differ, and the model will need retraining on in-domain
   data.
5. **Uncalibrated SVM score.** The deployed model's "probability" is a sigmoid
   of the SVM margin, not calibrated. Use Logistic Regression if calibrated
   probabilities matter downstream.

---

## 10. Reproducing

`RANDOM_SEED = 42` throughout; versions pinned in `requirements.txt`; splits and
config saved under `data/processed/`. Run `src/01…07` in order, then
`src/predict.py`. See `README.md`. Machine-readable results for every model are
in `reports/metrics.json`.

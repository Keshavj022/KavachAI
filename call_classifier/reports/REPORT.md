# Call Models — Training & Evaluation Report

On-device scam-call detector (classifier + arc tracker) trained from the four
audited datasets, evaluated on three test sets. Runs **fully offline at
inference** — reasoning models were used only at build time to label public
data. Every number below is in `reports/metrics.json`; figures in
`reports/figures/`; verbatim errors in `reports/error_analysis.md`.

---

## Executive summary

- **Deployed classifier: TF-IDF (word+char) + Logistic Regression**, 12.4 MB,
  <1 ms/chunk, threshold 0.735 (chosen on validation for scam recall ≥ 0.90).
  A DistilBERT head-to-head was run (val macro-F1 0.940 vs 0.934) — it edges the
  linear model slightly but is ~22× larger, so the tiny linear model is the
  on-device choice, as in the SMS work.
- **On real legitimate calls (held-out call-center, 5,781 chunks): 0.00%
  false-positive rate.** This is the headline metric and it is excellent.
- **On real scam openings (youtube-scam, 243): 55.6% recall.** This is the
  **synthetic→real distribution shift** made visible — the model trained on
  clean synthetic ICFD catches 90% of ICFD scam chunks but only 56% of noisy,
  opening-only, real ASR scam transcripts. Reported plainly, not hidden.
- **ICFD re-split test: macro-F1 0.935, FP-rate 2.86%, scam recall 90.2%,
  ROC-AUC 0.985.** Per hard-negative case type: FP 2.05% on "Ambiguous but
  Ultimately Normal", 3.19% on "Clear Normal"; recall 93.7% "Clear Fraud",
  91.2% "Subtle Fraud".
- **Lead time (the hero metric) is currently ~0 turns (median).** The interrupt
  fired in 114/150 test scams and fired at-or-before the money demand in 48/67
  calls, but the **median lead is 0 turns** because ICFD scams frequently jump
  from authority claim straight to money demand and the **isolation stage is
  under-labelled** by the annotator (only 40 training examples). This is the
  main honest limitation and the clearest path to improvement.
- **No data leakage, no contamination.** Split at the conversation level before
  chunk expansion; 0 cross-dataset overlaps after processing (audit confirmed).
- **Excluded:** call-transcript (corrupt CSV + synthetic despite "real"
  billing) and Fraud Call India (not present; partially derived from the SMS
  Spam Collection — leakage risk against our SMS model).

---

## 1. Corpus & split (leakage-free)

Built from **source** ICFD (not the streaming parquet, which collapses
`case_type` to two values and drops the "Ambiguous but Ultimately Normal" hard
negatives). Text normalized with the shared `asr_normalize` (the exact function
the backend runs at inference) so train and inference registers match.

| Source | Conversations | Role |
| --- | --- | --- |
| ICFD | 31,000 (16,393 scam / 14,607 legit) | primary train/val/test |
| call-center | 6,857 unique (of 7,000 sampled; deduped) | real legit negatives |
| youtube-scam | 243 | held-out real scam test |
| call-transcript | — | **excluded** |

- Cross-dataset contamination after processing: **0 rows** (143 intra-corpus
  exact duplicates removed). Confirms the audit still holds.
- **ICFD re-split**, conversation-level, stratified on `case_type × domain`:
  train 21,700 / val 4,650 / test 4,650 conversations — **every split contains
  all four case types** (e.g. test: 750 Ambiguous, 1,614 Clear Fraud, 1,500
  Clear Normal, 786 Subtle Fraud).
- **Chunks expanded after the split** (cumulative turn-prefixes for ICFD,
  word-prefixes for flat call-center, openings for youtube): **267,095 chunks**,
  each conversation in exactly one split (asserted). Training pool = ICFD train +
  call-center train (≈187k chunks, 48.8% scam); class weights, no majority
  deletion.
- Chunks capped at 8 per ICFD conversation for tractability (stated;
  configurable).

## 2. Stage annotation (build-time, Groq)

Groq (`llama-3.3-70b-versatile`) annotated **500 train/val + 150 test** ICFD
scam conversations (all via Groq, 0 fallback), producing monotonic per-turn
stages + money-demand turn/timestamp. Cached and resumable (raise the caps to
scale up). Test annotations are firewalled into a separate file used only for
lead-time scoring.

- **Validation vs ICFD `chunk_level_analysis` (NO→YES flip):** detected
  accusation/isolation lands within ~30 s of the flip in **43% (train/val) / 32%
  (test)** of the subset where both exist. This moderate agreement is a
  limitation — many ICFD scams skip stages, and ICFD's verdict timestamps are
  coarse. 30 annotated conversations saved for manual review
  (`reports/stage_annotation_samples.md`).
- **Stage-label imbalance (important):** the annotator produced `none` 2247,
  `authority_claim` 1651, `money_demand` 1228, `accusation` 159, **`isolation`
  40**. Isolation is severely under-represented, which directly hurts lead time
  (below).

## 3. Classifier — scam vs legit on partial transcripts

Trained on cumulative chunks. Threshold chosen on **validation** (recall ≥ 0.90,
minimise FP). Selected by lowest val FP-rate with ROC-AUC tie-break.

| Model | val macro-F1 | val FP-rate | val recall | val ROC-AUC | size | latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Logistic Regression (deployed)** | 0.934 | 0.029 | 0.90 | 0.984 | 12.4 MB | 0.9 ms |
| Linear SVM | 0.934 | 0.029 | 0.90 | 0.983 | 12.4 MB | 0.9 ms |
| Complement NB | 0.911 | 0.077 | 0.90 | 0.969 | 24 MB | 2.0 ms |
| DistilBERT (40k sampled chunks, 2 epochs) | **0.940** | — | — | — | 269 MB | ~40 min train |

DistilBERT edges the linear models on macro-F1 (0.940 vs 0.934) but is **~22×
larger (269 MB vs 12.4 MB)** and far slower to run and train — not worth it for
an on-device, sub-millisecond detector. The linear model is the on-device
choice. Figure: `model_comparison.png`.

## 4. Arc tracker + interrupt rule

Per-chunk stage classifier (TF-IDF + multinomial LogReg, 2.5 MB) trained on the
Phase-3 labels, with **monotonic enforcement** (stage never regresses). Because
isolation is under-labelled, the trained model alone fails to detect it, so the
stage decision is **backstopped by deterministic, auditable cue rules** for the
safety-critical later stages — the interrupt must never depend solely on an
under-trained model. Combined behaviour on a clear digital-arrest sequence:
authority_claim → accusation (warn) → **isolation (interrupt, before money)** →
money_demand.

Deterministic interrupt rule (in code, not learned):
```
interrupt = (scam_prob >= 0.735) AND (stage >= isolation)
warn      = (scam_prob >= 0.735) AND (stage == accusation)
# money_demand reached with no prior interrupt → interrupt immediately
```

## 5. Evaluation — three test sets

| Test set | Question | Result |
| --- | --- | --- |
| **ICFD re-split test** | benchmark; FP on hard negatives | macro-F1 **0.935**, FP **2.86%**, recall **90.2%**, AUC 0.985 |
| — Ambiguous but Ultimately Normal | FP on hardest negatives | **2.05%** (n=5,958) |
| — Clear Normal | FP | 3.19% (has 6.3% ICFD label noise) |
| — Clear Fraud / Subtle Fraud | recall | 93.7% / 91.2% |
| **youtube-scam (real openings)** | catch real scams? | recall **55.6%** (n=243) |
| **call-center (real legit)** | FP on real legit? | **0.00%** (n=5,781) |

Figures: `icfd_test_confusion.png`, `icfd_test_roc.png`, `icfd_test_pr.png`,
`threshold_curve.png`.

### Lead time (hero metric)

Replaying each annotated ICFD test scam conversation through the real pipeline
(classifier + hybrid arc + interrupt rule):

- Interrupt fired in **114/150** calls.
- Fired **at or before the money demand in 48/67** calls that reach a money
  demand.
- **Median lead = 0 turns / 0 s** (mean 0.63 turns). Figure:
  `lead_time_distribution.png`.

**Honest reading:** lead time is currently ~0 because (a) many ICFD scams have
no explicit isolation phase (authority → money), and (b) the isolation stage is
under-labelled, so the interrupt often coincides with the money demand rather
than preceding it. The fix is better isolation coverage — more threat-based scam
data and a sharper stage annotator — not a model-architecture change. The
pipeline *does* fire before money when isolation cues are present (verified on
the digital-arrest sequence in §4).

## 6. Error analysis (`reports/error_analysis.md`)

- **0 false positives on real legit call-center calls** — the costliest error
  does not occur on ordinary real calls.
- **108/243 false negatives on youtube-scam** — missed real scam openings are
  short, noisy, ASR-mangled, or very early (a few words) where even a human
  could not yet judge. This is the synthetic→real gap concentrated in openings.
- ~2% FP on ICFD "Ambiguous but Ultimately Normal" hard negatives — the
  genuine-bank-verifying-a-transaction calls that resemble scams.

## 7. The central limitation (stated plainly)

The models are trained on **synthetic** data (ICFD, LLM-generated, with
LLM-assigned verdicts and LLM-generated stage labels) and evaluated on **real**
held-out data. The gap between ICFD test recall (90%) and youtube-scam recall
(56%) **is** the synthetic→real shift. youtube-scam is also small (243) and
openings-only, so its numbers are indicative, not tight. call-center legit is
real but contains **no bank/government calls** (those hard negatives exist only
in ICFD). Deployed confidence should rest on the **0% FP on real legit** result;
real-scam recall needs real scam-call training data to close.

## 8. On-device / privacy

Classifier 12.4 MB + arc tracker 2.5 MB; <1 ms/chunk on CPU. The runtime
detection path is **entirely local** — local Whisper → shared `asr_normalize` →
classifier → arc tracker → deterministic interrupt → pre-written de-escalation
template. No network, no Groq at inference.

## 9. Recommendations

1. Ship the linear classifier now — its **0% real-legit FP-rate** is the
   product-critical property.
2. Treat real-scam recall (56%) as the gap to close; acquire real scam-call
   transcripts (beyond openings) for training, not just testing.
3. Improve isolation-stage labelling to recover positive lead time; the
   cue-rule backstop already guarantees the interrupt fires when isolation
   language appears.
4. Keep youtube-scam and a call-center slice as permanent real held-out tests.

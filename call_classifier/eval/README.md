# Call-detector evaluation harness

Measures whether the Groq few-shot call detector is good enough to ship. It
imports the **same** prompt and detector the product uses
(`backend/app/prompts/call_detection.py`, `backend/app/services/call_detector.py`),
so it evaluates exactly what runs in the app.

## What it reports

1. **Fraud Call India Dataset** (scam vs legit): accuracy, precision/recall/F1,
   confusion matrix, and the headline **false-positive rate on legitimate
   calls** (must be low).
2. **Held-out real digital-arrest transcripts**, fed turn by turn: whether each
   was flagged as a scam, whether detected stages appear in order, and the
   **lead time** — how many turns before the `[MONEY DEMAND]` marker the
   interrupt fired.

Outputs: `REPORT.md`, `metrics.json`, `confusion_fraud_call.png`.

## Run it

Run from the backend virtualenv (the harness imports the backend `app` package)
with `matplotlib` added for the confusion figure:

```bash
cd backend
source venv/bin/activate
pip install matplotlib

# Real evaluation (set GROQ_API_KEY in .env first to test the shipping LLM path):
python ../call_classifier/eval/run_eval.py \
    --fraud-csv /path/to/fraud_call_india.csv --sample 300 --sleep 0.2
```

- `--fraud-csv` — path to the Fraud Call India CSV. Column names are
  auto-detected (transcript/label); override with `--text-col` / `--label-col`.
  Omit the flag to skip that section.
- `--sample N` — cap the number of fraud-call rows (respect Groq rate limits).
- `--sleep S` — delay between detector calls (rate limiting).
- `--held-out-dir` — defaults to
  `call_classifier/data/real_calls/test_held_out/`. Place annotated real
  transcripts there (see that folder's README for the marker format).

If `GROQ_API_KEY` is unset, the harness runs the **local rule-based fallback**
detector and the report says so — useful for a mechanics smoke test, but the
numbers are illustrative only.

## Smoke test (no data or key needed)

Synthetic fixtures are included to verify the harness end to end:

```bash
python ../call_classifier/eval/run_eval.py \
    --fraud-csv ../call_classifier/eval/sample_data/fraud_sample.csv \
    --held-out-dir ../call_classifier/eval/sample_data/held_out --sample 20
```

The `sample_data/` transcripts are synthetic and are **not** the real held-out
test pot and are **not** used in the detector prompt.

# Call Detector — Evaluation Report

- Detector: **fallback** (prompt `call-detect-v1`, model `rule-based`)
- Generated: 2026-07-09 17:39:01

> NOTE: `GROQ_API_KEY` was not set, so these numbers come from the local **rule-based fallback**, not the Groq few-shot model. Set the key and re-run to evaluate the shipping LLM path.

## 1. Fraud Call India (scam vs legit)

_Skipped — no `--fraud-csv` provided._

## 2. Held-out real digital-arrest transcripts (arc lead time)

_No transcripts found. Place annotated real transcripts (with inline `[AUTHORITY CLAIM]` / `[ACCUSATION]` / `[ISOLATION]` / `[MONEY DEMAND]` markers) in `call_classifier/data/real_calls/test_held_out/`._

## Caveats

- The real held-out set is small — treat these as **illustrative, not statistically tight**. Do not over-claim precision on a few dozen samples.
- Lead time is measured in conversational turns relative to the annotated `[MONEY DEMAND]` marker; a positive value means the interrupt fired before the money was demanded, which is the design goal.

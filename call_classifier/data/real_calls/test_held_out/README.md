# Held-out real digital-arrest transcripts (test pot)

Place the transcribed **real** digital-arrest call transcripts here, one call
per `.txt` file. These are the held-out evaluation set.

**Do not** let anything in this folder appear in the detector's few-shot prompt
(`backend/app/prompts/call_detection.py`). The prompt uses only synthetic
examples so the evaluation stays honest. The eval harness reads these files;
the product never sees them.

## Annotation format

Write the transcript one turn per line. Mark the turn where each scam-arc stage
begins with an inline tag in square brackets. The harness strips the tags before
feeding the text to the detector and uses them as ground truth for arc order and
lead-time measurement.

Recognized markers: `[AUTHORITY CLAIM]`, `[ACCUSATION]`, `[ISOLATION]`,
`[MONEY DEMAND]`.

Example:

```
Caller: This is Inspector ... from the CBI cyber cell. [AUTHORITY CLAIM]
Caller: A parcel in your name had illegal items ...
Caller: Your Aadhaar is in a money laundering case, a warrant is issued. [ACCUSATION]
Caller: Do not disconnect, do not tell anyone, you are under digital arrest. [ISOLATION]
Caller: Transfer your funds to this safe account to verify them. [MONEY DEMAND]
```

The key metric is **lead time**: how many turns before the `[MONEY DEMAND]`
line the interrupt rule fires. A positive lead time means Kavach would have
warned the victim before any money was requested.

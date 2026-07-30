# Call-Dataset Intake Audit

A read-only audit of four call/conversation datasets for a real-time scam-call
detector. No source data was modified. Every claim below is backed by a number
in `stats.json`, a figure in `figures/`, or a verbatim example in `samples/`.
Scripts that produced everything are in `scripts/` (run in order 01→07).

---

## 1. Executive summary — the 10 findings that matter

1. **No dataset has a clean 4-stage arc label** (`authority_claim → accusation →
   isolation → money_demand`). The closest thing is **ICFD's
   `chunk_level_analysis`**: a per-timestamp `verdict_at_chunk` (YES/NO) plus a
   free-text `rationale_at_chunk`. That gives us *when the call becomes
   detectable* (great for lead-time) and weak, derivable stage signal, but not
   the categorical arc. **Conclusion: the arc/stage scorer must be trained on
   LLM-generated stage labels; it cannot be supervised directly from any of
   these datasets.** (See §2.1-C, `samples/icfd_streaming_walkthrough.md`.)

2. **No cross-dataset contamination.** Normalized exact-match overlap is **0 for
   all six dataset pairs**; shingle near-duplicate max Jaccard is ≤ 0.09 with
   zero pairs above threshold. ICFD (synthetic) was **not** seeded from the real
   sets; youtube-scam and call-transcript do **not** share content. This is the
   good news the brief was worried about. (See §3, `stats.json:cross_dataset`.)

3. **None of the four is SMS-in-disguise.** Median words per record: youtube 154,
   call-transcript 213, ICFD 274, call-center 742 — all conversation-length. The
   Fraud Call India failure mode is absent here.

4. **ICFD's official splits are label-skewed and cannot measure false-positive
   rate as-is.** Legitimate calls live almost entirely in **train** (14,519 NO /
   6,481 YES), while **validation, test and cross_domain are ~99-100% scam**
   (test = 4,477 YES / 23 NO). FP-rate — our headline metric — needs legit
   examples in the test set, so ICFD **must be re-split**. (Figure
   `icfd_verdict_per_split.png`.)

5. **ICFD is the only rich, multi-turn, speaker-attributed dataset that contains
   BOTH scam and legit — including the hardest negatives.** Its `case_type` has
   four values; the **"Ambiguous but Ultimately Normal"** class (5,000 convs,
   train-only) is exactly the hard-negative kind a low-FP model needs (e.g. a
   genuine bank calling to verify a transaction). It also covers **bank/financial
   and government domains** and **Hinglish**. But it is **synthetic** (LLM-
   generated with personas/scenarios). (Figure `icfd_case_type_per_split.png`.)

6. **ICFD streaming chunks are CUMULATIVE at a 3-second cadence** — confirmed by
   the `cumulative_text` column, length-monotonic + prefix-growing checks, and a
   3s inter-chunk delta (93,164 of 93,166 sampled gaps). Median ~39 chunks per
   conversation. **Lead-time is measurable** from these chunks + the source
   per-timestamp verdict. (Figures `icfd_chunks_per_conversation.png`.)

7. **call-center is our legit-negative workhorse but has real gaps.** ~**181,637
   unique** transcripts (the archives sum to 191,777 files — **~2× the advertised
   91,706**, with duplicate re-uploaded archives). All English, flat text with
   word timestamps, **no usable speaker labels** (`speaker` is null in 0/11,050
   sampled words), and **no bank / police / government fraud-desk calls** — the
   hardest negatives are absent here (they exist only in ICFD).

8. **call-transcript (BETTER30.csv) is small, messy, and looks synthetic — not
   the "60 real transcripts" expected.** 65 conversations / 650 turn-rows with
   per-turn `LABEL`/`CONTEXT`/`FEATURES`/`ANNOTATIONS`, but the CSV is
   **corrupted** (unescaped commas leak field fragments into `LABEL`, e.g.
   `' citing urgency"'`) and the text carries generation artifacts (`[Your
   Name]`, inline `[Step: N]` markers). Useful as a small labeled probe, not a
   trustworthy real test set.

9. **youtube-scam is a clean, all-scam, real early-detection test set — but
   flat.** 243 ASR transcripts of real scam-call *openings* (scambaiter YouTube/
   Patreon; 96% have Source URLs), English, no labels (all scam), **no turn
   structure or speaker attribution** (single flat text field, 0 newlines/
   record). No duplicates.

10. **Two datasets are real scam (youtube-scam, call-transcript-ish), one is
    real legit (call-center), one is synthetic-both (ICFD).** A model trained on
    ICFD will face a **synthetic→real distribution shift** at test time (ICFD is
    clean, structured, Hinglish; youtube-scam is noisy, flat, lowercase ASR).
    That gap is the central risk and is why the real sets must be held out.

---

## 2. Per-dataset findings

### 2.1 ICFD-31k (`icfd/`) — synthetic Indian conversational fraud

**A. Inventory.** 265 files, 64.7 MB (of which ~62 MB is data; the rest is a
`.cache/huggingface/` download cache of `.lock`/`.metadata` pointer files — not
dataset content). `source_conversations/` = 15 `*.jsonl.zst` shards;
`streaming_chunks/` = 68 `*.parquet` shards; plus `dataset_manifest.jsonl`,
`checksums.sha256`, `release_summary.json`, `README.md`. **All 83 shipped
checksums verified PASS** (0 failed, 0 missing). Encodings utf-8.

**B. Schema (source conversation).** A JSON record per conversation with keys:
`transcript` (list of `{speaker: "Agent"|"Customer", text}` — **multi-turn with
speaker attribution**), `multimodal_analysis` (`dominant_emotion`,
`secondary_emotion`, `pace`, `confidence_score`), `key_entities`
(`organization`, `product`, `pii_requested`…), `chunk_level_analysis` (list of
`{timestamp, verdict_at_chunk, rationale_at_chunk}`), `final_slow_thinking_
rationale`, `final_verdict` (**YES/NO — the scam label**), `violated_policies`,
`scam_outcome`, `agent_persona`, `customer_persona`, `scenario`
(`scenario_id`, `case_type`, `description`), `session_id`, `generation_metadata`,
`release_metadata` (`split`, `domain`). Full schema in
`schemas/icfd_schema.json`; full record example in `samples/icfd_examples.md`.

- **Stage/phase field?** No explicit arc field. `chunk_level_analysis`
  (median 5 entries/conv) gives a coarse per-timestamp YES/NO verdict with a
  rationale that *describes* the stage ("Introduction to the issue" → "Policy
  violation detected"). This is the single most useful stage-adjacent signal
  across all four datasets — see the worked table in
  `samples/icfd_streaming_walkthrough.md`.
- **Speaker attribution?** Yes — every turn tagged `Agent`/`Customer`.
- **Multi-turn?** Yes, structured list of turns.
- **Real or synthetic?** Synthetic — LLM-generated from personas + scenarios
  (`agent_persona: "The Urgent Authority…"`, `scenario.description`).

**C. Streaming chunks (parquet).** Columns include `conversation_uid`,
`chunk_timestamp` (seconds), `cumulative_text`, `cumulative_transcript_json`,
`final_verdict`, `slow_thinking_rationale`, `domain`, `case_type`, `split`.
- **Cumulative, not incremental** — the column is literally `cumulative_text`;
  length is monotonic and each chunk is a prefix-superset of the last (verified).
- **3-second cadence** (inter-chunk Δ = 3s overwhelmingly).
- **~39 chunks/conversation** (median; p95 ≈ 104 → ~5-minute calls).
- **Per-chunk label is the FINAL verdict repeated** (`final_verdict` is constant
  within a conversation). The *time-varying* verdict is in the **source**
  `chunk_level_analysis.verdict_at_chunk` (NO→YES transition = detection point).
- **Lead-time feasibility: YES.** Detection latency = timestamp of the first
  `verdict_at_chunk == YES`. Note there is **no explicit `money_demand`
  timestamp**; "lead time before money demand" must be derived (from rationale
  text / `key_entities.pii_requested` / `violated_policies`), whereas "lead time
  = detection latency" is directly available.

**C. Labels.** `final_verdict` YES/NO. Split counts match the published card
exactly (train 21,000 / validation 4,500 / test 4,500 / cross_domain 1,000).
Verdict per split (the critical skew):

| split | YES (scam) | NO (legit) | scam % |
| --- | --- | --- | --- |
| train | 6,481 | 14,519 | 31% |
| validation | 4,474 | 26 | 99.4% |
| test | 4,477 | 23 | 99.5% |
| cross_domain | 961 | 39 | 96.1% |

`case_type` (richer than binary): train = Clear Normal 10,000 / Ambiguous but
Ultimately Normal 5,000 / Subtle Fraud 4,000 / Clear Fraud 2,000; val = Clear
Fraud 3,500 / Subtle Fraud 1,000; test = Clear Fraud 4,500; cross_domain =
Clear/Subtle Fraud only. 10 fraud domains (bank_payment_fraud,
government_impersonation, tech_support_account, loan_shark_harassment,
travel_lottery, …).

**D. Content stats.** Median chars: scam 1,375 / legit 1,131; median turns:
scam 13 / legit 11. Language (heuristic sample): mostly English with a Hinglish
minority (e.g. "Namaste Sir, ji, … Achha, Thik hai"). Figures:
`icfd_turns_by_verdict.png`, `icfd_chunks_per_conversation.png`,
`language_mix_by_dataset.png`.

**E. Examples.** Five full conversations + a full cumulative-chunk walkthrough
in `samples/icfd_examples.md` and `samples/icfd_streaming_walkthrough.md`.

**F. Quality.** Clean and checksum-verified. Main caveat is that it is
synthetic; also the coarse `chunk_level_analysis` (~5 points) is a different,
coarser granularity than the 3s `streaming_chunks` — don't conflate them.

---

### 2.2 call-center (`call-center/`) — real legit call-center transcripts (negatives)

**A. Inventory.** 11 `.zip` archives, 1.4 GB. Not extracted (read in memory from
the zips; nothing written to the source dir). Archives hold **191,777 JSON
files** total. Encodings utf-8.

**B. Schema (per transcript JSON).** `text` (flat full-call transcript, PII
bracket-redacted), `confidence` (call-level ASR confidence float),
`audio_duration` (s), `words` (list of `{text, start(ms), end(ms), confidence,
speaker}`), `redacted_pii_policies`. `schemas/call-center_schema.json`.
- **Stage field?** None. **Speaker?** Field exists but is **null in 0/11,050
  sampled words** — effectively no diarization. **Multi-turn?** No turn
  structure; a single flat `text` blob (word timestamps only).

**C. Labels.** None — **all legitimate** (these are the negatives).

**D. Content stats.** Median 742 words/call; median ASR confidence 0.945;
long real calls. 100% English (sample). Redaction tokens: `[PERSON_NAME]`,
`[ORGANIZATION]`, `[LOCATION]`, `[MONEY_AMOUNT]`, `[DATE]`, `[PHONE_NUMBER]`,
`[EMAIL_ADDRESS]`.

**E. Examples.** `samples/callcenter_examples.md`.

**F. Quality — two loud problems.**
- **Count ~2× the advertised 91,706** (191,777 files; 181,637 unique
  basenames). `medicare_inbound.zip` alone has 123,010 files — larger than the
  whole advertised dataset.
- **Duplicate archives** (filename-Jaccard): `(reupload)PII_redacted_auto_
  insurance_script.zip` ≡ `auto_insurance_customer_service_inbound.zip`
  (**Jaccard 1.000**, 3,498 identical files); `(re-uploaded)…automotive-stereo`
  is fully contained in `automotive_inbound.zip`; the auto-insurance set is also
  inside `automotive_inbound.zip`. ~10,140 cross-archive duplicate files.
- **Domain gap:** automotive, auto/health insurance, customer service, home
  service, telecom, medical equipment, medicare. **No bank / police / government
  fraud-desk calls** — the hardest negatives are absent here.

---

### 2.3 call-transcript (`call-transcript/BETTER30.csv`) — small labeled probe

**A. Inventory.** One CSV, 0.17 MB, utf-8.

**B. Schema.** Columns `CONVERSATION_ID, CONVERSATION_STEP, TEXT, CONTEXT,
LABEL, FEATURES, ANNOTATIONS`. 650 rows = **65 conversations × 3-17 turn-rows**
(median 9). `CONVERSATION_STEP` is a 1-based turn index. `TEXT` embeds *both*
speakers as `"<customer line> … [Step: N] <agent line>"` — speaker structure is
semi-encoded, not clean fields. `schemas/call-transcript_schema.json`,
`samples/calltranscript_examples.md`.
- **Stage field?** **Partial and messy.** There is a **per-turn `LABEL`** (scam/
  neutral/legitimate/suspicious/…) and `FEATURES`/`CONTEXT`/`ANNOTATIONS` carry
  tactic/tone/intent tags (`authority_figure`, `urgency`, `citing urgency`).
  Term scan of `FEATURES`: urgency 48, authority 10, isolation 2, accusation 1.
  So there is *tactic-level* annotation but **not** a clean 4-stage arc, and it
  is not consistently structured.

**C. Labels.** Per-turn `LABEL`, with **serious noise**: leading-space variants
(`' scam'` vs `'scam'`), casing (`'Scam'`), and **CSV-corruption fragments**
(`' citing urgency"'`, `' emphasizing security and compliance"'`,
`'standard_opening, identification_request'`) that are `FEATURES`/`ANNOTATIONS`
values leaked into `LABEL` by unescaped commas. Per-conversation majority label:
neutral 19, scam(+variants) ~34, legitimate ~7, suspicious 4.

**D. Content.** Median 213 words/conversation. English. Reads **synthetic/
templated** (`[Your Name]`, `[Step: N]`, assistant-style replies) — its billing
as "60 transcripts of real calls" is **not supported** by the content.

**F. Quality.** Malformed CSV, inconsistent labels, likely synthetic. Small.

---

### 2.4 youtube-scam (`youtube-scam/FullTranscriptData.csv`) — real scam openings

**A. Inventory.** One CSV, 0.2 MB, utf-8.

**B. Schema.** `ID, Source, Content, Char_Len`. `Source` = URL (96.3%; YouTube/
Patreon, mostly the "JimBrowning" scambaiter channel + FTC). `Content` = flat
transcript. `Char_Len` matches computed length exactly (0 mismatches).
`schemas/youtube-scam_schema.json`, `samples/youtubescam_examples.md`.
- **Stage field?** None. **Speaker?** None (0 speaker prefixes, 0 newlines/
  record → single flat blob). **Multi-turn?** No.

**C. Labels.** **None — all rows are scam** (no label column, by design).

**D. Content.** 243 records, median 767 chars / 154 words. 100% English (noisy
ASR: lowercase, run-on, no punctuation). These are the *beginnings* of scam
calls (tech-support, Interpol, Amazon, BT).

**F. Quality.** Clean: 0 exact/near duplicates, 0 empty. The advertised PII
removal is not visible as tokens (no `[NAME]`-style redaction) — names appear
simply absent, so redaction convention is "silently removed", not tagged.

---

## 3. Cross-dataset analysis

**G. Contamination — none found.**
- **Exact normalized overlap = 0** for all six pairs (samples: ICFD 3,000,
  call-center 826, call-transcript 65 conv, youtube-scam 243).
- **Near-duplicate (5-gram shingle Jaccard):** youtube×call-transcript 0.01,
  ICFD×youtube 0.01, ICFD×call-transcript 0.015, youtube×call-center 0.088 —
  **no pairs above threshold**. ICFD was not seeded from the real sets;
  youtube-scam and call-transcript do not share sources (call-transcript has no
  Source-URL column to compare, and its text does not match youtube's).
- **SMS check:** none looks like SMS (median words 154-742).
- Within call-center: the duplicate *archives* noted in §2.2 are the only
  duplication issue.

**H. Comparability & unified schema.** The four are **structurally normalizable**
into a common schema, with clear per-dataset gaps:

```
{ conversation_id, source_dataset, split, label,           // label may be null
  turns: [ {speaker, text} ],                              // may be empty
  full_text, meta: { domain, case_type, is_synthetic, ... } }
```

| field | ICFD | call-center | call-transcript | youtube-scam |
| --- | --- | --- | --- | --- |
| turns[speaker,text] | ✅ Agent/Customer | ⚠️ flat (no speaker) | ⚠️ semi (`[Step:N]`) | ❌ flat |
| full_text | ✅ | ✅ | ✅ | ✅ |
| label (scam/legit) | ✅ final_verdict | legit (implicit) | ⚠️ per-turn, noisy | scam (implicit) |
| split | ✅ | ❌ | ❌ | ❌ |
| stage/arc | ⚠️ per-timestamp verdict | ❌ | ⚠️ tactic tags | ❌ |
| real vs synthetic | synthetic | real | ~synthetic | real |

**Register comparison** (`cross_length_by_dataset.png`): ICFD is clean,
structured, moderate length, some Hinglish; call-center is long, clean, English,
formal; youtube-scam is short, flat, noisy lowercase ASR; call-transcript is
short, templated. **The synthetic ICFD does not look like the real youtube-scam
transcripts** (structure, casing, ASR noise, code-mixing all differ) — a model
trained on ICFD should be expected to lose accuracy on real calls.

**Legit-vs-legit:** call-center legit and call-transcript "legitimate" are
different in kind — call-center is real long customer-service calls; the
call-transcript legits are short synthetic role-plays. They are **not**
interchangeable negatives.

**Domain gap (important):** the hardest negatives — real **bank / police /
government** calls that *sound* like scams — exist **only in ICFD** (its
"Ambiguous but Ultimately Normal" bank/government-domain conversations).
call-center has none.

---

## 4. Data-quality issues (consolidated)

1. **call-center count discrepancy:** 191,777 files vs advertised 91,706; ~2×.
2. **call-center duplicate archives:** one exact-duplicate pair (Jaccard 1.0) and
   several subset duplicates; ~10k cross-archive duplicate files.
3. **call-center no speaker labels** (null everywhere sampled) and **no bank/gov
   domain**.
4. **call-transcript CSV is corrupted** (unescaped commas/quotes leak field
   fragments into `LABEL`) and labels are inconsistently cased/spaced.
5. **call-transcript is likely synthetic**, contradicting its "real calls"
   billing.
6. **ICFD split label skew** (val/test/cross ~all scam) — unusable for FP-rate
   without re-splitting.
7. **ICFD per-chunk parquet label = final verdict repeated** (not a live
   verdict) — use the source `chunk_level_analysis` for time-varying verdicts.
8. **youtube-scam / ICFD language heuristic is approximate** (langdetect is weak
   on short, code-mixed, ASR-noisy text) — the Hinglish fraction is indicative
   only.
9. **No stage labels anywhere** — the arc scorer has no direct supervision.

---

## 5. Recommendations

**Scam/legit classifier — train on ICFD, re-split it.** ICFD is the only source
with multi-turn, speaker-attributed, both-class data including hard negatives.
Do **not** use the official splits (val/test have almost no legit). Instead:
pool all 31k, then make a fresh **stratified** split on `case_type` × `domain`
so every split has Clear Fraud, Subtle Fraud, Clear Normal, and — crucially —
**Ambiguous but Ultimately Normal** negatives. Keep ICFD's 3s cumulative chunks
as the training unit if you want the model to work on partial transcripts.

**Negatives:** use ICFD's normals (incl. the ambiguous bank/gov ones) as the
*hard* negatives, and **call-center** as *easy, real, long* negatives to lower
FP-rate on ordinary calls — but weight/expect the domain gap (no bank/gov in
call-center; those come from ICFD). Deduplicate call-center archives first.

**Arc/stage scorer:** **no dataset gives clean stage labels**, so generate them
with an LLM. ICFD is the best substrate because its `chunk_level_analysis`
rationales and cumulative chunks let you align generated stage labels to
timestamps and validate them against the YES-transition point.

**Lead-time:** measurable from ICFD. Use the source `chunk_level_analysis`
NO→YES transition (detection latency) on the 3s cumulative chunks; for "lead
before money demand" specifically, derive the money-demand time from rationale/
`pii_requested`/`violated_policies` (there is no explicit marker).

**Held-out real test sets (do not train on these):** **youtube-scam** (243 real
scam openings → real early-detection test) and, cautiously, **call-transcript**
(small, messy, semi-synthetic — use only after cleaning the CSV, and treat as a
weak probe, not a headline benchmark). These are the only real *scam* audio-
derived transcripts, so reserving them is the only way to measure real-world
transfer. Also hold out a slice of **call-center** as a real-legit FP-rate test.

**Class balance:** ICFD pooled is roughly balanced (16,393 YES / 14,607 NO). Use
**class weights**, not deletion of majority data; keep the **test set at
realistic proportions** (real traffic is overwhelmingly legit, so a realistic
low-scam-prevalence test is what makes the FP-rate meaningful).

**Exclude / demote:** treat **call-transcript** as low-trust (synthetic + corrupt
CSV); do not build the primary benchmark on it. Everything else stays, with the
caveats above.

---

## 6. Open questions

- **What exactly does ICFD `final_verdict = NO` guarantee?** It aligns with
  `case_type ∈ {Clear Normal, Ambiguous but Ultimately Normal}` and
  `scam_outcome = N/A`, so it reads as "legitimate", but the label was
  LLM-assigned — spot-check a sample before trusting it as ground truth.
- **Why is call-center ~2× its advertised size?** Is `medicare_inbound`
  (123k files) an intended part of this release or a superset added later? The
  paper says 91,706.
- **Is any call-center subset stereo/diarized?** The `speaker` field exists but
  was null everywhere sampled; the "stereo" archive name hints some calls may
  carry channel/speaker info not seen in the sample.
- **call-transcript provenance:** is BETTER30 a known benchmark? Its structure
  (`[Step: N]`, `[Your Name]`) strongly suggests generated data; confirming the
  source would settle whether it can be called "real".
- **ICFD Hinglish fraction:** the heuristic can't quantify code-mixing reliably;
  a proper measure needs a code-mixing detector.

---

*Artifacts: `stats.json` (all machine-readable numbers), `schemas/` (per-dataset
schema dumps), `samples/` (verbatim examples + ICFD streaming walkthrough),
`figures/` (7 plots), `scripts/` (01-07, runnable, commented). Reproduce with
the venv at `call-data-exploration/venv` — see `scripts/` imports.*

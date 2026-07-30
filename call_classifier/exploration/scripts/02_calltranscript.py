"""call-transcript/ (BETTER30.csv) deep dive.

Critical question: do the FEATURES / ANNOTATIONS / CONVERSATION_STEP columns
encode per-utterance scam STAGE / phase / tactic labels? Investigate and show
verbatim examples.

Read-only. Writes stats['call_transcript'], schema, and samples.
"""

from __future__ import annotations

import json
from collections import Counter

import pandas as pd

import common as c

CSV = c.DATASETS["call-transcript"] / "BETTER30.csv"


def main() -> None:
    print("=== call-transcript / BETTER30.csv ===")
    df = pd.read_csv(CSV, encoding="utf-8", dtype=str, keep_default_na=False)
    print(f"rows: {len(df)}  columns: {list(df.columns)}")

    # --- Schema: dtype + example values per column ---
    schema = {"file": "BETTER30.csv", "n_rows": len(df), "columns": {}}
    for col in df.columns:
        non_empty = df[col][df[col].str.strip() != ""]
        examples = [c.truncate(v, 400) for v in non_empty.head(4).tolist()]
        schema["columns"][col] = {
            "dtype": "str(csv)",
            "n_non_empty": int(len(non_empty)),
            "n_unique": int(df[col].nunique()),
            "examples": examples,
        }
    c.write_schema("call-transcript", schema)

    # --- Conversation structure ---
    n_conv = df["CONVERSATION_ID"].nunique()
    steps_per_conv = df.groupby("CONVERSATION_ID").size()
    print(f"\nconversations: {n_conv}")
    print(f"steps/rows per conversation: min={steps_per_conv.min()} "
          f"median={steps_per_conv.median()} max={steps_per_conv.max()}")
    print("CONVERSATION_STEP sample values:",
          df["CONVERSATION_STEP"].head(8).tolist())

    # --- LABEL analysis (per row and per conversation) ---
    label_rows = df["LABEL"].value_counts().to_dict()
    conv_label = df.groupby("CONVERSATION_ID")["LABEL"].agg(
        lambda s: s.value_counts().index[0]
    )
    label_conv = conv_label.value_counts().to_dict()
    print(f"\nLABEL (per row): {label_rows}")
    print(f"LABEL (per conversation, majority): {label_conv}")

    # --- THE stage-label question: FEATURES + ANNOTATIONS ---
    print("\n=== FEATURES column — full unique-ish examples ===")
    feat_examples = []
    for v in df["FEATURES"][df["FEATURES"].str.strip() != ""].head(6):
        print("  FEATURE:", c.truncate(v, 500))
        feat_examples.append(c.truncate(v, 800))

    print("\n=== ANNOTATIONS column — full examples ===")
    ann_examples = []
    ann_keys: Counter[str] = Counter()
    for v in df["ANNOTATIONS"][df["ANNOTATIONS"].str.strip() != ""].head(10):
        ann_examples.append(c.truncate(v, 800))
        # Try to parse as JSON to enumerate keys (stage/phase/tactic?).
        try:
            obj = json.loads(v)
            if isinstance(obj, dict):
                ann_keys.update(obj.keys())
            elif isinstance(obj, list):
                for it in obj:
                    if isinstance(it, dict):
                        ann_keys.update(it.keys())
        except Exception:
            pass
    for v in ann_examples[:6]:
        print("  ANNOTATION:", v)
    print(f"\nANNOTATIONS parsed JSON keys (if any): {dict(ann_keys)}")

    # Search all text columns for stage/phase/tactic vocabulary.
    stage_terms = ["stage", "phase", "step", "tactic", "intent", "authority",
                   "isolation", "money", "accusation", "urgency", "arc"]
    hits = {}
    for col in ["FEATURES", "ANNOTATIONS", "CONTEXT", "CONVERSATION_STEP"]:
        blob = " ".join(df[col].tolist()).lower()
        hits[col] = {t: blob.count(t) for t in stage_terms if t in blob}
    print(f"\nstage/phase/tactic term hits by column: {json.dumps(hits, indent=1)}")

    # --- Length stats ---
    df["chars"] = df["TEXT"].str.len()
    df["words"] = df["TEXT"].str.split().map(len)
    length = {"chars": c.percentiles(df["chars"].tolist()),
              "words": c.percentiles(df["words"].tolist())}

    # --- Speaker attribution check ---
    sample_text = df["TEXT"].head(20).tolist()
    speaker_prefix = sum(1 for t in sample_text if ":" in t[:25])
    print(f"\nTEXT rows with a ':' in first 25 chars (speaker prefix?): "
          f"{speaker_prefix}/20")

    # --- Save one full conversation verbatim to samples ---
    first_conv_id = df["CONVERSATION_ID"].iloc[0]
    conv = df[df["CONVERSATION_ID"] == first_conv_id]
    lines = [f"# call-transcript — one full conversation (verbatim)\n",
             f"CONVERSATION_ID = {first_conv_id}",
             f"LABEL = {conv['LABEL'].iloc[0]}",
             f"rows/steps = {len(conv)}\n", "---\n"]
    for _, r in conv.iterrows():
        lines.append(f"STEP {r['CONVERSATION_STEP']}: {r['TEXT']}")
        if r["ANNOTATIONS"].strip():
            lines.append(f"    ANNOTATIONS: {c.truncate(r['ANNOTATIONS'], 600)}")
        if r["FEATURES"].strip():
            lines.append(f"    FEATURES: {c.truncate(r['FEATURES'], 600)}")
        lines.append("")

    # A few full scam + legit examples (whole conversations).
    def conv_block(cid: str) -> str:
        sub = df[df["CONVERSATION_ID"] == cid]
        txt = "\n".join(f"  STEP {r['CONVERSATION_STEP']}: {r['TEXT']}"
                        for _, r in sub.iterrows())
        return (f"### {cid}  (LABEL={sub['LABEL'].iloc[0]}, steps={len(sub)})\n"
                f"{c.truncate(txt, 2000)}\n")

    scam_cids = conv_label[conv_label.str.lower().str.contains("scam|fraud", na=False)].index[:5]
    legit_cids = conv_label[~conv_label.str.lower().str.contains("scam|fraud", na=False)].index[:5]
    ex_lines = ["# call-transcript — full example conversations\n",
                f"## Scam ({len(scam_cids)} shown)\n"]
    ex_lines += [conv_block(cid) for cid in scam_cids]
    ex_lines += [f"\n## Legitimate ({len(legit_cids)} shown)\n"]
    ex_lines += [conv_block(cid) for cid in legit_cids]
    c.write_samples("calltranscript_examples.md",
                    "\n".join(lines) + "\n\n" + "\n".join(ex_lines))

    c.save_stats("call_transcript", {
        "n_rows": len(df),
        "n_conversations": int(n_conv),
        "steps_per_conversation": c.percentiles(steps_per_conv.tolist()),
        "label_per_row": label_rows,
        "label_per_conversation": label_conv,
        "length": length,
        "annotations_json_keys": dict(ann_keys),
        "stage_term_hits": hits,
        "features_examples": feat_examples,
        "annotations_examples": ann_examples[:6],
        "speaker_prefix_in_20": speaker_prefix,
        "columns": list(df.columns),
    })


if __name__ == "__main__":
    main()

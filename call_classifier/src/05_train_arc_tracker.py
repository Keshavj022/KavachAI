"""Phase 4b — Train the arc/stage tracker.

Input: a cumulative (partial) transcript. Output: the current scam-arc stage
(none / authority_claim / accusation / isolation / money_demand). Trained on the
Phase-3 Groq stage labels. Deliberately the simplest interpretable model — a
TF-IDF + multinomial Logistic Regression per-chunk stage classifier — with
**monotonic enforcement applied at inference** (a stage never regresses within a
call), which is what makes the interrupt auditable. Small and fast for on-device.

Training data: for each annotated conversation, every cumulative turn-prefix is
labelled with the (monotonic) stage in force at its last turn.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from app.services.asr_norm import asr_normalize  # noqa: E402


def build_examples(label_path: Path, turns_map: dict) -> pd.DataFrame:
    rows = []
    for line in label_path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        turns = json.loads(turns_map.get(rec["conversation_id"], "[]"))
        stages = rec["stages"]
        if len(turns) != len(stages):
            continue
        # Cumulative prefix at each turn → the stage in force there.
        for k in range(len(turns)):
            raw = "\n".join(f"{t['speaker']}: {t['text']}" for t in turns[: k + 1])
            rows.append({
                "conversation_id": rec["conversation_id"],
                "split": rec["split"],
                "text_norm": asr_normalize(raw),
                "stage": stages[k],
            })
    return pd.DataFrame(rows)


def main() -> None:
    config.set_global_seed()
    print("=== Phase 4b: train arc tracker ===")
    label_path = config.STAGE_LABELS_DIR / "train_val.jsonl"
    if not label_path.exists():
        print("  no stage labels — run 03_annotate_stages.py first. Skipping.")
        return

    corpus = pd.read_parquet(config.CORPUS_PARQUET)[["conversation_id", "turns_json"]]
    turns_map = dict(zip(corpus.conversation_id, corpus.turns_json))

    df = build_examples(label_path, turns_map)
    train = df[df.split == "train"]
    val = df[df.split == "val"]
    print(f"  arc examples: {len(df)} (train {len(train)}, val {len(val)})")
    print("  stage distribution (train):")
    print(train["stage"].value_counts().to_string())

    pipe = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced",
                                   multi_class="multinomial", C=4.0,
                                   random_state=config.RANDOM_SEED)),
    ])
    pipe.fit(train["text_norm"], train["stage"])

    if len(val):
        pred = pipe.predict(val["text_norm"])
        print("\n  per-chunk stage report (val, before monotonic enforcement):")
        print(classification_report(val["stage"], pred, zero_division=0,
                                    labels=config.STAGES))

    path = config.ARTIFACTS / "call_arc_tracker.joblib"
    joblib.dump(pipe, path)
    meta = {"stages": config.STAGES, "model": "tfidf+logreg multinomial",
            "monotonic_enforced_at_inference": True,
            "n_train_examples": len(train),
            "model_size_mb": round(path.stat().st_size / 1e6, 2),
            "note": "Per-chunk stage classifier; the backend enforces monotonicity "
            "across a call (stage never regresses)."}
    with open(config.ARTIFACTS / "arc_tracker_meta.json", "w") as fh:
        json.dump(meta, fh, indent=2)

    m = json.load(open(config.METRICS_JSON)) if config.METRICS_JSON.exists() else {}
    m["arc_tracker"] = meta
    json.dump(m, open(config.METRICS_JSON, "w"), indent=2, default=str)
    print(f"\n  saved arc tracker ({meta['model_size_mb']}MB)")


if __name__ == "__main__":
    main()

"""Phase 4a — Train the scam-vs-legit classifier on cumulative chunks.

Training unit = a cumulative (partial) transcript, so the model judges a call in
progress. TF-IDF (word + char) linear baselines first (the SMS work showed these
beat DistilBERT at a fraction of size/latency); an optional DistilBERT head-to-
head runs only if torch is installed. Threshold is chosen on VALIDATION to keep
scam recall >= 0.90 while minimising FP-rate. Model size + latency are recorded.

Trains on {train, cc_train}; selects on {val}. TEST is never touched here.
Text is already ASR-normalized (``text_norm``) upstream via the shared function.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def _features() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=5, sublinear_tf=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5),
                                 min_df=10, sublinear_tf=True)),
    ])


def build_models() -> dict[str, Pipeline]:
    seed = config.RANDOM_SEED
    return {
        "linear_svm": Pipeline([("feats", _features()),
                                ("clf", LinearSVC(class_weight="balanced", C=1.0,
                                                  random_state=seed))]),
        "logreg": Pipeline([("feats", _features()),
                            ("clf", LogisticRegression(max_iter=2000, C=6.0,
                             class_weight="balanced", random_state=seed))]),
        "complement_nb": Pipeline([("feats", _features()),
                                   ("clf", ComplementNB(alpha=0.2))]),
    }


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def scam_scores(pipe, X):
    if hasattr(pipe, "predict_proba"):
        return pipe.predict_proba(X)[:, 1], True
    return _sigmoid(pipe.decision_function(X)), False


def fp_rate(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    legit = y_true == 0
    n = int(legit.sum())
    return float(((y_pred == 1) & legit).sum() / n) if n else float("nan")


def choose_threshold(y_val, s_val) -> float:
    """Highest threshold (lowest FP) keeping scam recall >= floor, on val."""
    best_t = 0.5
    for t in np.linspace(0.05, 0.95, 181):
        pred = (s_val >= t).astype(int)
        pos = (y_val == 1).sum()
        recall = ((pred == 1) & (y_val == 1)).sum() / max(pos, 1)
        if recall >= config.SCAM_RECALL_FLOOR:
            best_t = t
        else:
            break
    return float(best_t)


def latency_ms(pipe, texts) -> float:
    sample = list(texts[:200])
    t0 = time.time()
    for s in sample:
        scam_scores(pipe, [s])
    return round((time.time() - t0) / len(sample) * 1000, 3)


def main() -> None:
    config.set_global_seed()
    print("=== Phase 4a: train classifier ===")
    df = pd.read_parquet(config.CHUNKS_PARQUET)
    train = df[df.split.isin(["train", "cc_train"])]
    val = df[df.split == "val"]
    Xtr, ytr = train["text_norm"].tolist(), train["label"].to_numpy()
    Xva, yva = val["text_norm"].tolist(), val["label"].to_numpy()
    print(f"  train chunks: {len(Xtr)} ({ytr.mean():.2%} scam) | val: {len(Xva)}")

    results, thresholds, val_scores, calib = {}, {}, {}, {}
    for name, pipe in build_models().items():
        t0 = time.time()
        pipe.fit(Xtr, ytr)
        s_val, is_prob = scam_scores(pipe, Xva)
        t = choose_threshold(yva, s_val)
        pred = (s_val >= t).astype(int)
        path = config.ARTIFACTS / f"call_baseline_{name}.joblib"
        joblib.dump(pipe, path)
        size_mb = round(path.stat().st_size / 1e6, 2)
        block = {
            "val_macro_f1": round(f1_score(yva, pred, average="macro"), 4),
            "val_scam_recall": round(float(((pred == 1) & (yva == 1)).sum()
                                           / max((yva == 1).sum(), 1)), 4),
            "val_fp_rate": round(fp_rate(yva, pred), 4),
            "val_roc_auc": round(float(roc_auc_score(yva, s_val)), 4),
            "threshold": round(t, 4),
            "calibrated_prob": is_prob,
            "model_size_mb": size_mb,
            "latency_ms_per_chunk": latency_ms(pipe, Xva),
            "fit_seconds": round(time.time() - t0, 1),
        }
        results[name], thresholds[name] = block, t
        val_scores[name], calib[name] = s_val, is_prob
        print(f"  {name:14s} macroF1={block['val_macro_f1']:.4f} "
              f"FPR={block['val_fp_rate']:.4f} recall={block['val_scam_recall']:.4f} "
              f"AUC={block['val_roc_auc']:.4f} {size_mb}MB {block['latency_ms_per_chunk']}ms")

    # Optional DistilBERT head-to-head (only if torch present).
    try:
        results["distilbert"] = _train_transformer(train, val)
    except ImportError:
        print("  (torch/transformers not installed — skipping DistilBERT head-to-head)")
        results["distilbert"] = {"skipped": "torch not installed"}

    # Winner: lowest val FP-rate within a small tolerance, best AUC as tie-break.
    proba_names = [n for n in val_scores]
    best_fpr = min(results[n]["val_fp_rate"] for n in proba_names)
    near = [n for n in proba_names if results[n]["val_fp_rate"] <= best_fpr + 0.01]
    winner = max(near, key=lambda n: results[n]["val_roc_auc"])
    deploy = {
        "winner": winner,
        "artifact": f"call_baseline_{winner}.joblib",
        "threshold": thresholds[winner],
        "calibrated_probability": calib[winner],
        "val_metrics": results[winner],
    }
    with open(config.ARTIFACTS / "call_deployment.json", "w") as fh:
        json.dump(deploy, fh, indent=2)
    joblib.dump(joblib.load(config.ARTIFACTS / f"call_baseline_{winner}.joblib"),
                config.ARTIFACTS / "call_classifier.joblib")

    _merge_metrics("classifier", {"models": results, "deployed": deploy})
    print(f"\n  deployed: {winner} @ threshold {thresholds[winner]:.3f} "
          f"(val FPR {results[winner]['val_fp_rate']}, recall {results[winner]['val_scam_recall']})")


def _train_transformer(train, val) -> dict:
    import torch  # noqa: F401
    from datasets import Dataset
    from sklearn.metrics import accuracy_score
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              Trainer, TrainingArguments)

    # Sample chunks for tractability (stated in the report).
    tr = train.sample(min(len(train), config.TRANSFORMER_TRAIN_SAMPLE),
                      random_state=config.RANDOM_SEED)
    tok = AutoTokenizer.from_pretrained(config.TRANSFORMER_MODEL)

    def to_ds(d):
        ds = Dataset.from_dict({"text": d["text_norm"].tolist(),
                                "labels": d["label"].tolist()})
        return ds.map(lambda b: tok(b["text"], truncation=True, padding="max_length",
                                    max_length=config.TRANSFORMER_MAX_LEN), batched=True)

    import numpy as _np
    counts = _np.bincount(tr["label"].to_numpy(), minlength=2)
    weights = torch.tensor(counts.sum() / (2.0 * counts), dtype=torch.float32)

    class WTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kw):
            labels = inputs.pop("labels")
            out = model(**inputs)
            loss = torch.nn.functional.cross_entropy(
                out.logits, labels, weight=weights.to(out.logits.device))
            return (loss, out) if return_outputs else loss

    def metrics(p):
        preds = _np.argmax(p[0], axis=-1)
        return {"macro_f1": f1_score(p[1], preds, average="macro"),
                "accuracy": accuracy_score(p[1], preds)}

    model = AutoModelForSequenceClassification.from_pretrained(
        config.TRANSFORMER_MODEL, num_labels=2)
    args = TrainingArguments(
        output_dir=str(config.ARTIFACTS / "_bert_ckpt"),
        num_train_epochs=config.TRANSFORMER_EPOCHS, per_device_train_batch_size=16,
        per_device_eval_batch_size=32, eval_strategy="epoch", save_strategy="no",
        logging_strategy="epoch", report_to=[], seed=config.RANDOM_SEED,
        use_cpu=not torch.backends.mps.is_available(), dataloader_pin_memory=False)
    trainer = WTrainer(model=model, args=args, train_dataset=to_ds(tr),
                       eval_dataset=to_ds(val), compute_metrics=metrics)
    t0 = time.time()
    trainer.train()
    ev = trainer.evaluate()
    (config.ARTIFACTS / "call_transformer").mkdir(exist_ok=True)
    trainer.save_model(str(config.ARTIFACTS / "call_transformer"))
    tok.save_pretrained(str(config.ARTIFACTS / "call_transformer"))
    size = sum(p.stat().st_size for p in (config.ARTIFACTS / "call_transformer").glob("*")) / 1e6
    return {"val_macro_f1": round(float(ev["eval_macro_f1"]), 4),
            "train_minutes": round((time.time() - t0) / 60, 2),
            "model_size_mb": round(size, 1),
            "note": f"trained on {len(tr)} sampled chunks"}


def _merge_metrics(section, payload):
    m = {}
    if config.METRICS_JSON.exists():
        m = json.load(open(config.METRICS_JSON))
    m[section] = payload
    json.dump(m, open(config.METRICS_JSON, "w"), indent=2, default=str)


if __name__ == "__main__":
    main()

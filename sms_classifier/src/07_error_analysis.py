"""Phase 8 — Error analysis for the deployed model.

Pulls concrete false positives (legit flagged malicious) and false negatives
(malicious missed) on the sacred test set at the deployed operating threshold,
saves them to CSV, and characterizes the failure modes with a short breakdown.
This is what shows the model is understood, not just scored.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

import utils
import config
from features_lib import engineered_features

DEPLOY_JSON = config.MODELS_DIR / "deployment.json"


def _scores_for_test(winner: str, X_test) -> np.ndarray:
    if winner == "distilbert":
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model_dir = config.MODELS_DIR / "transformer_binary"
        tok = AutoTokenizer.from_pretrained(str(model_dir))
        model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        model.eval()
        out = []
        texts = list(X_test)
        for i in range(0, len(texts), 64):
            enc = tok(texts[i:i + 64], truncation=True,
                      max_length=config.TRANSFORMER_MAX_LEN, padding=True,
                      return_tensors="pt")
            with torch.no_grad():
                logits = model(**enc).logits
            out.append(torch.softmax(logits, dim=-1)[:, 1].numpy())
        return np.concatenate(out)

    pipe = joblib.load(config.MODELS_DIR / f"baseline_{winner}_binary.joblib")
    if hasattr(pipe, "predict_proba"):
        return pipe.predict_proba(X_test)[:, 1]
    return 1.0 / (1.0 + np.exp(-pipe.decision_function(X_test)))


def main() -> None:
    config.set_global_seed()
    print("=== Phase 8: error analysis ===")
    with open(DEPLOY_JSON) as fh:
        deploy = json.load(fh)
    winner, threshold = deploy["winner"], float(deploy["threshold"])

    _train, _val, test = utils.split_frames()
    scores = _scores_for_test(winner, test["text"])
    pred = (scores >= threshold).astype(int)
    y = test["y_binary"].values

    test = test.copy()
    test["score"] = scores
    test["pred"] = pred

    fp = test[(y == 0) & (pred == 1)].sort_values("score", ascending=False)
    fn = test[(y == 1) & (pred == 0)].sort_values("score")

    print(f"  model={winner} threshold={threshold:.3f}")
    print(f"  false positives (legit→malicious): {len(fp)}")
    print(f"  false negatives (missed malicious): {len(fn)}")

    cols = ["text", "label", "source", "score"]
    fp[cols].to_csv(config.REPORTS_DIR / "false_positives.csv", index=False)
    fn[cols].to_csv(config.REPORTS_DIR / "false_negatives.csv", index=False)

    # Characterize failures with engineered features.
    def characterize(sub: pd.DataFrame) -> dict:
        if len(sub) == 0:
            return {"count": 0}
        feats = engineered_features(sub["text"])
        return {
            "count": int(len(sub)),
            "median_chars": float(sub["text"].str.len().median()),
            "has_url_rate": round(float(feats["has_url"].mean()), 3),
            "has_phone_rate": round(float(feats["has_phone"].mean()), 3),
            "by_source": sub["source"].value_counts().to_dict(),
            "by_label": sub["label"].value_counts().to_dict(),
        }

    fp_char, fn_char = characterize(fp), characterize(fn)

    print("\n  --- False positives (legit wrongly flagged) ---")
    for _, r in fp.head(6).iterrows():
        print(f"   p={r['score']:.2f} [{r['source']}] {r['text'][:90]}")
    print("\n  --- False negatives (malicious missed) ---")
    for _, r in fn.head(6).iterrows():
        print(f"   p={r['score']:.2f} [{r['label']}/{r['source']}] {r['text'][:90]}")

    utils.update_metrics("error_analysis", {
        "model": winner, "threshold": threshold,
        "false_positives": fp_char, "false_negatives": fn_char,
        "example_false_positives": fp["text"].head(8).tolist(),
        "example_false_negatives": fn["text"].head(8).tolist(),
    })
    print(f"\n  saved false_positives.csv / false_negatives.csv to reports/")


if __name__ == "__main__":
    main()

"""Inference interface — the entry point the product backend will call.

Loads the deployed winner (chosen in phase 7) and its decision threshold, and
scores a raw SMS string. Works for either a classical joblib pipeline or the
fine-tuned transformer, transparently.

    from predict import classify
    classify("URGENT! You have won a prize. Reply WIN to claim.")
    -> {"label": "malicious", "malicious_probability": 0.98, "threshold": 0.62}
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

import utils  # noqa: F401  (bootstraps sys.path)
import config

DEPLOY_JSON = config.MODELS_DIR / "deployment.json"


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


@lru_cache(maxsize=1)
def _load():
    """Load the deployment config and the winning artifact once."""
    if not DEPLOY_JSON.exists():
        raise FileNotFoundError(
            "No deployment.json — run 06_evaluate.py to select and persist a model."
        )
    with open(DEPLOY_JSON) as fh:
        deploy = json.load(fh)

    winner = deploy["winner"]
    threshold = float(deploy["threshold"])

    if winner == "distilbert":
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model_dir = config.MODELS_DIR / "transformer_binary"
        tok = AutoTokenizer.from_pretrained(str(model_dir))
        model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        model.eval()

        def score(text: str) -> float:
            enc = tok([text], truncation=True, max_length=config.TRANSFORMER_MAX_LEN,
                      return_tensors="pt")
            with torch.no_grad():
                logits = model(**enc).logits
            return float(torch.softmax(logits, dim=-1)[0, 1].item())

        return score, threshold

    # Classical joblib pipeline.
    import joblib

    pipe = joblib.load(config.MODELS_DIR / deploy["artifact"])
    has_proba = hasattr(pipe, "predict_proba")

    def score(text: str) -> float:
        if has_proba:
            return float(pipe.predict_proba([text])[0, 1])
        return _sigmoid(float(pipe.decision_function([text])[0]))

    return score, threshold


def classify(text: str) -> dict:
    """Classify a raw SMS message.

    Returns the label, the malicious probability, and the operating threshold.
    """
    score_fn, threshold = _load()
    prob = score_fn(text if isinstance(text, str) else str(text))
    label = "malicious" if prob >= threshold else "legit"
    return {
        "label": label,
        "malicious_probability": round(prob, 4),
        "threshold": round(threshold, 4),
    }


if __name__ == "__main__":
    examples = [
        "Hey, are we still meeting for coffee at 5?",
        "URGENT! Your account has been suspended. Verify now: http://sbi-verify.xyz/login",
        "Congratulations! You have WON a 50,00,000 prize. Send your bank details to claim.",
        "Can you pick up milk on the way home?",
        "Your KYC will expire today. Click http://bit.ly/kyc-update to avoid blocking.",
    ]
    for ex in examples:
        r = classify(ex)
        print(f"[{r['label']:9s} p={r['malicious_probability']:.3f}] {ex[:60]}")

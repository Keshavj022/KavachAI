"""Fine-tune a small transformer scam classifier (optional).

Run with: ``python -m app.ml.train_classifier`` (requires ``torch`` and
``transformers``; install the pins noted in ``requirements.txt``).

Reads ``app/ml/data/dataset.jsonl`` (produced by ``generate_synthetic.py``)
and fine-tunes ``distilbert-base-uncased`` into a binary scam classifier saved
under ``app/ml/models/classifier``. If those weights exist, ``services/
classifier.py`` loads them automatically; if training is skipped, the rule
fallback runs instead. The app never requires this step.
"""

from __future__ import annotations

import json
import os
import sys

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "dataset.jsonl")
_MODEL_OUT = os.path.join(os.path.dirname(__file__), "models", "classifier")
_BASE_MODEL = "distilbert-base-uncased"


def _load_rows() -> list[dict]:
    if not os.path.exists(_DATA_PATH):
        print(
            f"Dataset not found at {_DATA_PATH}.\n"
            "Run: python -m app.ml.generate_synthetic",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(_DATA_PATH, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> None:
    try:
        import numpy as np
        import torch  # noqa: F401
        from datasets import Dataset
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        print(
            f"Missing training dependency ({exc}).\n"
            "Install torch, transformers and datasets to train. The app runs "
            "without this — it falls back to the rule-based classifier.",
            file=sys.stderr,
        )
        sys.exit(1)

    rows = _load_rows()
    split = int(len(rows) * 0.9)
    train_rows, eval_rows = rows[:split], rows[split:]

    tokenizer = AutoTokenizer.from_pretrained(_BASE_MODEL)

    def _tok(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=128)

    train_ds = Dataset.from_list(train_rows).map(_tok, batched=True)
    eval_ds = Dataset.from_list(eval_rows).map(_tok, batched=True)

    model = AutoModelForSequenceClassification.from_pretrained(_BASE_MODEL, num_labels=2)

    def _metrics(pred):
        logits, labels = pred
        preds = np.argmax(logits, axis=-1)
        acc = (preds == labels).mean()
        return {"accuracy": float(acc)}

    args = TrainingArguments(
        output_dir=os.path.join(os.path.dirname(_MODEL_OUT), "_train_tmp"),
        num_train_epochs=2,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        eval_strategy="epoch",
        logging_steps=20,
        save_strategy="no",
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=_metrics,
    )
    trainer.train()
    print("Eval:", trainer.evaluate())

    os.makedirs(_MODEL_OUT, exist_ok=True)
    model.save_pretrained(_MODEL_OUT)
    tokenizer.save_pretrained(_MODEL_OUT)
    print(f"Saved fine-tuned classifier to {_MODEL_OUT}")


if __name__ == "__main__":
    main()

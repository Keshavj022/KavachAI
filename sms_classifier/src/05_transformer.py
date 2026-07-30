"""Phase 6 — Fine-tune DistilBERT on the binary target.

Trains `distilbert-base-uncased` to classify legit vs malicious, with:
  * class-weighted cross-entropy (handles the ~15% malicious imbalance),
  * early stopping on validation macro-F1,
  * saved training/validation loss curves.

The TEST split is never touched here — the model is saved and phase 7 loads it
to score the sacred test set. Runs on MPS (Apple GPU) if available, else CPU;
the device and wall-clock time are recorded so the accuracy-vs-compute tradeoff
is visible.
"""

from __future__ import annotations

import time

import numpy as np
import torch
import torch.nn.functional as F
from datasets import Dataset
from sklearn.metrics import accuracy_score, f1_score
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

import utils
import config

MODEL_OUT = config.MODELS_DIR / "transformer_binary"


def _device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class WeightedTrainer(Trainer):
    """Trainer with class-weighted cross-entropy for the imbalance."""

    def __init__(self, class_weights: torch.Tensor, **kwargs):
        super().__init__(**kwargs)
        self._class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = F.cross_entropy(
            outputs.logits, labels, weight=self._class_weights.to(outputs.logits.device)
        )
        return (loss, outputs) if return_outputs else loss


def _compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "macro_f1": f1_score(labels, preds, average="macro"),
        "fp_rate": utils.false_positive_rate(labels, preds),
    }


def _loss_curve(log_history: list[dict]) -> None:
    train_x, train_y, val_x, val_y, f1_x, f1_y = [], [], [], [], [], []
    for e in log_history:
        if "loss" in e and "epoch" in e:
            train_x.append(e["epoch"]); train_y.append(e["loss"])
        if "eval_loss" in e:
            val_x.append(e["epoch"]); val_y.append(e["eval_loss"])
        if "eval_macro_f1" in e:
            f1_x.append(e["epoch"]); f1_y.append(e["eval_macro_f1"])

    fig, ax1 = utils.plt.subplots(figsize=(8, 5))
    ax1.plot(train_x, train_y, "-o", color="#1565C0", label="train loss")
    ax1.plot(val_x, val_y, "-s", color="#C62828", label="val loss")
    ax1.set_xlabel("epoch"); ax1.set_ylabel("loss"); ax1.legend(loc="upper right")
    ax2 = ax1.twinx()
    ax2.plot(f1_x, f1_y, "-^", color="#2E7D32", label="val macro-F1")
    ax2.set_ylabel("val macro-F1"); ax2.legend(loc="lower right")
    ax1.set_title("DistilBERT fine-tuning curves", fontsize=12, fontweight="bold")
    utils.savefig(fig, "09_transformer_training_curves.png")


def main() -> None:
    config.set_global_seed()
    device = _device()
    print(f"=== Phase 6: DistilBERT fine-tuning (device={device}) ===")

    train, val, _test = utils.split_frames()
    tokenizer = AutoTokenizer.from_pretrained(config.TRANSFORMER_MODEL)

    def to_ds(df):
        ds = Dataset.from_dict({"text": df["text"].tolist(),
                                "labels": df["y_binary"].tolist()})
        return ds.map(
            lambda b: tokenizer(b["text"], truncation=True,
                                max_length=config.TRANSFORMER_MAX_LEN),
            batched=True,
        )

    train_ds, val_ds = to_ds(train), to_ds(val)

    # Class weights inversely proportional to frequency.
    counts = np.bincount(train["y_binary"].values, minlength=2)
    weights = counts.sum() / (2.0 * counts)
    class_weights = torch.tensor(weights, dtype=torch.float32)
    print(f"  class counts={counts.tolist()}  weights={weights.round(3).tolist()}")

    model = AutoModelForSequenceClassification.from_pretrained(
        config.TRANSFORMER_MODEL, num_labels=2
    )

    args = TrainingArguments(
        output_dir=str(config.MODELS_DIR / "_transformer_ckpt"),
        num_train_epochs=config.TRANSFORMER_EPOCHS,
        per_device_train_batch_size=config.TRANSFORMER_BATCH,
        per_device_eval_batch_size=32,
        learning_rate=config.TRANSFORMER_LR,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=1,
        seed=config.RANDOM_SEED,
        report_to=[],
        use_cpu=(device == "cpu"),
        dataloader_pin_memory=False,
    )

    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        compute_metrics=_compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    val_metrics = trainer.evaluate()

    MODEL_OUT.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(MODEL_OUT))
    tokenizer.save_pretrained(str(MODEL_OUT))
    _loss_curve(trainer.state.log_history)

    result = {
        "device": device,
        "train_minutes": round(elapsed / 60, 2),
        "epochs_run": trainer.state.epoch,
        "val_macro_f1": round(float(val_metrics["eval_macro_f1"]), 4),
        "val_fp_rate": round(float(val_metrics["eval_fp_rate"]), 4),
        "val_accuracy": round(float(val_metrics["eval_accuracy"]), 4),
        "model_dir": str(MODEL_OUT.relative_to(config.ROOT)),
    }
    utils.update_metrics("transformer", result)
    print(f"\nDone in {result['train_minutes']} min. "
          f"val macroF1={result['val_macro_f1']} val_fpr={result['val_fp_rate']}")


if __name__ == "__main__":
    main()

"""Phase 7 — Unified evaluation on the sacred test set.

For every model reports accuracy, precision/recall/F1 (per-class, macro,
weighted), the confusion matrix, ROC-AUC and PR-AUC, and — the headline —
the false-positive rate on legitimate messages. Then does a deliberate
threshold analysis: the operating threshold is chosen on the VALIDATION set
(never the test set) to drive FP-rate low while keeping malicious recall
acceptable, and the resulting operating point is reported on TEST.

The transformer is optional: if its saved model is absent this script still
runs on the classical models.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

import utils
import config

plt = utils.plt

BINARY_MODELS = ["logreg", "linear_svm", "multinomial_nb", "complement_nb"]
DEPLOY_JSON = config.MODELS_DIR / "deployment.json"
TARGET_MALICIOUS_RECALL = 0.90  # threshold chosen on val must keep >= this


# --------------------------------------------------------------------------
# Scoring helpers
# --------------------------------------------------------------------------
def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def baseline_scores(name: str, X_val, X_test):
    """Return P(malicious) on val and test for a saved binary baseline."""
    pipe = joblib.load(config.MODELS_DIR / f"baseline_{name}_binary.joblib")
    if hasattr(pipe, "predict_proba"):
        return pipe.predict_proba(X_val)[:, 1], pipe.predict_proba(X_test)[:, 1], True
    # LinearSVC: map decision_function through a sigmoid (monotonic → AUC exact;
    # the resulting score is uncalibrated, noted in the report).
    return _sigmoid(pipe.decision_function(X_val)), _sigmoid(pipe.decision_function(X_test)), False


def transformer_scores(X_val, X_test):
    """Return P(malicious) on val and test from the fine-tuned DistilBERT."""
    model_dir = config.MODELS_DIR / "transformer_binary"
    if not model_dir.exists():
        return None
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.eval()

    def infer(texts):
        probs = []
        for i in range(0, len(texts), 64):
            batch = list(texts[i:i + 64])
            enc = tok(batch, truncation=True, max_length=config.TRANSFORMER_MAX_LEN,
                      padding=True, return_tensors="pt")
            with torch.no_grad():
                logits = model(**enc).logits
            probs.append(torch.softmax(logits, dim=-1)[:, 1].numpy())
        return np.concatenate(probs)

    return infer(list(X_val)), infer(list(X_test)), True


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def binary_metrics(y_true, y_score, threshold: float) -> dict:
    y_pred = (y_score >= threshold).astype(int)
    rep = classification_report(
        y_true, y_pred, target_names=["legit", "malicious"],
        output_dict=True, zero_division=0,
    )
    return {
        "threshold": round(float(threshold), 4),
        "accuracy": round(rep["accuracy"], 4),
        "macro_f1": round(rep["macro avg"]["f1-score"], 4),
        "weighted_f1": round(rep["weighted avg"]["f1-score"], 4),
        "malicious_precision": round(rep["malicious"]["precision"], 4),
        "malicious_recall": round(rep["malicious"]["recall"], 4),
        "malicious_f1": round(rep["malicious"]["f1-score"], 4),
        "fp_rate": round(utils.false_positive_rate(y_true, y_pred), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_score)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_score)), 4),
    }


def confusion_fig(y_true, y_pred, labels, names, title, fname):
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_yticks(range(len(names))); ax.set_yticklabels(names)
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    thresh = cm.max() / 2 if cm.max() else 0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center",
                    color="white" if cm[i, j] > thresh else "black")
    ax.set_title(title, fontsize=11, fontweight="bold")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    utils.savefig(fig, fname)


# --------------------------------------------------------------------------
# Threshold analysis (on validation)
# --------------------------------------------------------------------------
def choose_threshold(y_val, s_val) -> float:
    """Pick the highest threshold (lowest FP-rate) that still keeps malicious
    recall >= target on the validation set."""
    thresholds = np.linspace(0.05, 0.95, 181)
    best_t = 0.5
    for t in thresholds:
        pred = (s_val >= t).astype(int)
        recall = ((pred == 1) & (y_val == 1)).sum() / max((y_val == 1).sum(), 1)
        if recall >= TARGET_MALICIOUS_RECALL:
            best_t = t  # keep raising t while recall holds → lowers FP-rate
        else:
            break
    return float(best_t)


def threshold_curve_fig(y_val, s_val, chosen_t, model_name):
    thresholds = np.linspace(0.02, 0.98, 97)
    prec, rec, fpr = [], [], []
    for t in thresholds:
        pred = (s_val >= t).astype(int)
        tp = ((pred == 1) & (y_val == 1)).sum()
        fp = ((pred == 1) & (y_val == 0)).sum()
        pos = (y_val == 1).sum()
        prec.append(tp / max(tp + fp, 1))
        rec.append(tp / max(pos, 1))
        fpr.append(utils.false_positive_rate(y_val, pred))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thresholds, prec, label="precision (malicious)", color="#1565C0")
    ax.plot(thresholds, rec, label="recall (malicious)", color="#2E7D32")
    ax.plot(thresholds, fpr, label="FP-rate (legit→malicious)", color="#C62828")
    ax.axvline(chosen_t, ls="--", color="#444",
               label=f"chosen threshold = {chosen_t:.2f}")
    ax.set_xlabel("decision threshold"); ax.set_ylabel("rate")
    ax.set_title(f"Threshold analysis on validation — {model_name}",
                 fontsize=12, fontweight="bold")
    ax.legend()
    utils.savefig(fig, "13_threshold_analysis.png")


# --------------------------------------------------------------------------
# Overlays + comparison
# --------------------------------------------------------------------------
def roc_pr_overlays(y_test, scores: dict):
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    for name, s in scores.items():
        fpr, tpr, _ = roc_curve(y_test, s)
        ax.plot(fpr, tpr, label=f"{name} (AUC={roc_auc_score(y_test, s):.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.7)
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("ROC curves (test)", fontsize=12, fontweight="bold"); ax.legend()
    utils.savefig(fig, "11_roc_curves.png")

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    for name, s in scores.items():
        prec, rec, _ = precision_recall_curve(y_test, s)
        ax.plot(rec, prec, label=f"{name} (AP={average_precision_score(y_test, s):.3f})")
    ax.set_xlabel("recall"); ax.set_ylabel("precision")
    ax.set_title("Precision-Recall curves (test)", fontsize=12, fontweight="bold")
    ax.legend()
    utils.savefig(fig, "12_pr_curves.png")


def comparison_fig(results: dict):
    names = list(results)
    macro = [results[n]["macro_f1"] for n in names]
    fpr = [results[n]["fp_rate"] for n in names]
    x = np.arange(len(names))
    fig, ax1 = plt.subplots(figsize=(9, 5))
    b1 = ax1.bar(x - 0.2, macro, 0.4, label="macro-F1", color="#1565C0")
    ax1.set_ylabel("macro-F1"); ax1.set_ylim(0, 1)
    ax2 = ax1.twinx()
    b2 = ax2.bar(x + 0.2, fpr, 0.4, label="FP-rate", color="#C62828")
    ax2.set_ylabel("FP-rate (lower is better)")
    ax1.set_xticks(x); ax1.set_xticklabels(names, rotation=20, ha="right")
    ax1.set_title("Binary model comparison on test (at chosen thresholds)",
                  fontsize=12, fontweight="bold")
    ax1.legend(handles=[b1, b2], loc="center right")
    utils.savefig(fig, "14_model_comparison.png")


def eval_multiclass_on_test(test):
    """Report the 3-class baselines on test (smishing recall matters)."""
    from sklearn.metrics import f1_score

    X_test, y_test = test["text"], test["y_multiclass"].values
    out = {}
    for name in BINARY_MODELS:
        pipe = joblib.load(config.MODELS_DIR / f"baseline_{name}_multiclass.joblib")
        pred = pipe.predict(X_test)
        rep = classification_report(
            y_test, pred, target_names=["ham", "spam", "smishing"],
            output_dict=True, zero_division=0,
        )
        out[name] = {
            "macro_f1": round(rep["macro avg"]["f1-score"], 4),
            "smishing_recall": round(rep["smishing"]["recall"], 4),
            "smishing_precision": round(rep["smishing"]["precision"], 4),
            "spam_recall": round(rep["spam"]["recall"], 4),
        }
    best = max(out, key=lambda n: out[n]["macro_f1"])
    pipe = joblib.load(config.MODELS_DIR / f"baseline_{best}_multiclass.joblib")
    # y_multiclass is integer-coded (0=ham,1=spam,2=smishing); pass integer
    # labels with human names for the axes.
    confusion_fig(y_test, pipe.predict(X_test), [0, 1, 2],
                  ["ham", "spam", "smishing"],
                  f"3-class confusion (test) — {best}", "10_confusion_multiclass.png")
    return out, best


# --------------------------------------------------------------------------
def main() -> None:
    config.set_global_seed()
    print("=== Phase 7: unified evaluation (sacred test set) ===")
    _train, val, test = utils.split_frames()
    y_val, y_test = val["y_binary"].values, test["y_binary"].values

    # Gather malicious scores for every binary model.
    scores_test, scores_val, calibrated = {}, {}, {}
    for name in BINARY_MODELS:
        sv, st, cal = baseline_scores(name, val["text"], test["text"])
        scores_val[name], scores_test[name], calibrated[name] = sv, st, cal
    tr = transformer_scores(val["text"], test["text"])
    if tr is not None:
        scores_val["distilbert"], scores_test["distilbert"], calibrated["distilbert"] = tr
        print("  transformer loaded and scored.")
    else:
        print("  transformer model not found — evaluating classical models only.")

    # Default-threshold metrics for every model + confusion matrices.
    default_results = {}
    for name, s_test in scores_test.items():
        m = binary_metrics(y_test, s_test, threshold=0.5)
        m["calibrated_prob"] = calibrated[name]
        default_results[name] = m
        confusion_fig(y_test, (s_test >= 0.5).astype(int), [0, 1],
                      ["legit", "malicious"],
                      f"Binary confusion (test) — {name}",
                      f"cm_binary_{name}.png")
        print(f"  {name:14s} macroF1={m['macro_f1']:.4f} FPR={m['fp_rate']:.4f} "
              f"malRecall={m['malicious_recall']:.4f} ROC-AUC={m['roc_auc']:.4f}")

    roc_pr_overlays(y_test, scores_test)

    # --- Operating-point selection: FP-rate FIRST (the product's headline). ---
    # For every model, choose a threshold on VALIDATION that keeps malicious
    # recall >= target, then evaluate that operating point on TEST. Select the
    # model with the lowest validation FP-rate (tie-break: higher macro-F1).
    from sklearn.metrics import f1_score

    tuned_results, chosen_thresholds, val_fprs, val_rocs = {}, {}, {}, {}
    for name, s_test in scores_test.items():
        t = choose_threshold(y_val, scores_val[name])
        chosen_thresholds[name] = t
        val_pred = (scores_val[name] >= t).astype(int)
        val_fprs[name] = utils.false_positive_rate(y_val, val_pred)
        val_rocs[name] = float(roc_auc_score(y_val, scores_val[name]))
        m = binary_metrics(y_test, s_test, threshold=t)
        m["calibrated_prob"] = calibrated[name]
        m["val_fp_rate"] = round(val_fprs[name], 4)
        m["val_roc_auc"] = round(val_rocs[name], 4)
        m["val_macro_f1"] = round(float(f1_score(y_val, val_pred, average="macro")), 4)
        tuned_results[name] = m

    # FP-rate first, but treat FP-rates within ~2 messages/749 as a tie (the
    # test/val sets are small, so sub-0.3% FP differences are noise). Among the
    # near-lowest-FP models, deploy the best-ranking one (highest val ROC-AUC)
    # — a robustness choice made purely on validation data, never on test.
    best_fpr = min(val_fprs.values())
    FP_TIE_TOL = 0.003
    near_best = [n for n in scores_test if val_fprs[n] <= best_fpr + FP_TIE_TOL]
    winner = max(near_best, key=lambda n: val_rocs[n])
    chosen_t = chosen_thresholds[winner]
    threshold_curve_fig(y_val, scores_val[winner], chosen_t, winner)
    tuned = tuned_results[winner]

    print("\nOperating points (threshold chosen on val, evaluated on test):")
    for name in scores_test:
        r = tuned_results[name]
        star = "  <== deployed" if name == winner else ""
        print(f"  {name:14s} t={r['threshold']:.2f} FPR={r['fp_rate']:.4f} "
              f"malRecall={r['malicious_recall']:.4f} macroF1={r['macro_f1']:.4f}{star}")

    print(f"\nDeployed model: {winner} | threshold (chosen on val) = {chosen_t:.3f}")
    print(f"  TEST @ threshold: FPR={tuned['fp_rate']} malRecall={tuned['malicious_recall']} "
          f"macroF1={tuned['macro_f1']}")

    # Comparison chart uses each model's tuned operating point.
    comparison_fig(tuned_results)

    # 3-class report on test.
    mc, mc_best = eval_multiclass_on_test(test)
    print(f"\n3-class best on test: {mc_best} "
          f"(macroF1={mc[mc_best]['macro_f1']}, smishing_recall={mc[mc_best]['smishing_recall']})")

    # Persist deployment decision.
    deploy = {
        "winner": winner,
        "artifact": (f"baseline_{winner}_binary.joblib" if winner != "distilbert"
                     else "transformer_binary"),
        "threshold": round(chosen_t, 4),
        "calibrated_probability": calibrated[winner],
        "test_operating_point": tuned,
    }
    with open(DEPLOY_JSON, "w") as fh:
        json.dump(deploy, fh, indent=2)

    utils.update_metrics("evaluation", {
        "binary_default_threshold": default_results,
        "binary_tuned_operating_point": tuned_results,
        "deployed": deploy,
        "multiclass_test": mc,
        "multiclass_best": mc_best,
    })
    print(f"\nSaved deployment decision -> {DEPLOY_JSON.name}")


if __name__ == "__main__":
    main()

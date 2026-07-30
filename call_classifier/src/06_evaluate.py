"""Phase 5 — Evaluate on three test sets + the hero lead-time metric.

  1. ICFD re-split test — benchmark; FP-rate on HARD negatives, per case_type.
  2. youtube-scam (243 real openings) — recall (all scam).
  3. held-out call-center (~2k real legit) — FP-rate on real legit calls.

Plus LEAD TIME: replay each annotated ICFD test scam conversation chunk by
chunk through the real pipeline (classifier + hybrid arc tracker + interrupt
rule) and record when the interrupt fires vs the annotated money_demand turn.

Central caveat reported plainly: trained on SYNTHETIC ICFD, tested on REAL
held-out data — any drop is the synthetic→real shift.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sklearn.metrics import (average_precision_score, confusion_matrix,  # noqa: E402
                             f1_score, precision_recall_curve, roc_auc_score,
                             roc_curve)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
from predict import CallDetector  # noqa: E402


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def scores(clf, X):
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(X)[:, 1]
    return _sigmoid(clf.decision_function(X))


def savefig(fig, name):
    fig.savefig(config.FIGURES / name, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print(f"  [fig] {name}")


def fp_rate(y, p):
    y, p = np.asarray(y), np.asarray(p)
    legit = y == 0
    return float(((p == 1) & legit).sum() / max(int(legit.sum()), 1))


def main() -> None:
    config.set_global_seed()
    print("=== Phase 5: evaluation ===")
    df = pd.read_parquet(config.CHUNKS_PARQUET)
    deploy = json.load(open(config.ARTIFACTS / "call_deployment.json"))
    clf = joblib.load(config.ARTIFACTS / "call_classifier.joblib")
    T = float(deploy["threshold"])
    print(f"  deployed classifier: {deploy['winner']} @ threshold {T:.3f}")

    metrics = {"deployed": deploy["winner"], "threshold": T, "test_sets": {}}

    # --- 1. ICFD re-split test ---
    icfd_test = df[df.split == "test"]
    s = scores(clf, icfd_test["text_norm"].tolist())
    y = icfd_test["label"].to_numpy()
    pred = (s >= T).astype(int)
    icfd_res = {
        "n_chunks": int(len(y)),
        "macro_f1": round(f1_score(y, pred, average="macro"), 4),
        "scam_recall": round(float(((pred == 1) & (y == 1)).sum() / (y == 1).sum()), 4),
        "fp_rate": round(fp_rate(y, pred), 4),
        "roc_auc": round(float(roc_auc_score(y, s)), 4),
        "pr_auc": round(float(average_precision_score(y, s)), 4),
        "per_case_type": {},
    }
    for ct, grp in icfd_test.groupby("case_type"):
        gs = scores(clf, grp["text_norm"].tolist())
        gp = (gs >= T).astype(int)
        gy = grp["label"].to_numpy()
        # Case type is legit if the majority of its conversations are legit
        # (ICFD has slight label noise, so use majority, not == 0).
        if gy.mean() < 0.5:  # legit case type → FP-rate (fraction predicted scam)
            icfd_res["per_case_type"][ct] = {
                "kind": "legit", "n": int(len(gy)), "scam_prevalence": round(float(gy.mean()), 4),
                "fp_rate": round(float((gp == 1).mean()), 4)}
        else:  # scam case type → recall
            icfd_res["per_case_type"][ct] = {
                "kind": "scam", "n": int(len(gy)),
                "recall": round(float((gp[gy == 1] == 1).mean()), 4)}
    metrics["test_sets"]["icfd_test"] = icfd_res
    print(f"  [ICFD test] macroF1={icfd_res['macro_f1']} FPR={icfd_res['fp_rate']} "
          f"recall={icfd_res['scam_recall']} AUC={icfd_res['roc_auc']}")
    for ct, r in icfd_res["per_case_type"].items():
        print(f"     {ct:34s} {r}")

    # Confusion + ROC + PR + threshold curve on ICFD test.
    _confusion(y, pred, "icfd_test_confusion.png", "ICFD test")
    _roc_pr(y, s, "icfd_test")
    _threshold_curve(y, s, T)

    # --- 2. youtube-scam (all scam → recall) ---
    yt = df[df.split == "yt_test"]
    ys = scores(clf, yt["text_norm"].tolist())
    yt_recall = float((ys >= T).mean())
    metrics["test_sets"]["youtube_scam"] = {"n": int(len(yt)), "all_scam": True,
                                            "recall": round(yt_recall, 4)}
    print(f"  [youtube-scam REAL] recall={yt_recall:.4f} (n={len(yt)})")

    # --- 3. held-out call-center (all legit → FP-rate) ---
    cc = df[df.split == "cc_test"]
    cs = scores(clf, cc["text_norm"].tolist())
    cc_fpr = float((cs >= T).mean())
    metrics["test_sets"]["call_center_test"] = {"n": int(len(cc)), "all_legit": True,
                                               "fp_rate": round(cc_fpr, 4)}
    print(f"  [call-center REAL legit] FP-rate={cc_fpr:.4f} (n={len(cc)})")

    # --- Latency / size (from training metrics) ---
    train_metrics = json.load(open(config.METRICS_JSON)).get("classifier", {})
    metrics["model_comparison"] = {
        k: {mk: v.get(mk) for mk in ("val_macro_f1", "val_fp_rate", "val_roc_auc",
                                     "model_size_mb", "latency_ms_per_chunk")}
        for k, v in train_metrics.get("models", {}).items() if isinstance(v, dict)
    }

    # --- HERO: lead time ---
    metrics["lead_time"] = lead_time_eval()

    # Save + comparison figure.
    _comparison_fig(metrics)
    m = json.load(open(config.METRICS_JSON)) if config.METRICS_JSON.exists() else {}
    m["evaluation"] = metrics
    json.dump(m, open(config.METRICS_JSON, "w"), indent=2, default=str)
    print("\n  saved evaluation metrics.")


def lead_time_eval() -> dict:
    """Replay annotated ICFD test scam conversations; measure interrupt lead."""
    label_path = config.STAGE_LABELS_DIR / "test.jsonl"
    if not label_path.exists():
        return {"note": "no test stage annotations"}
    corpus = pd.read_parquet(config.CORPUS_PARQUET)[["conversation_id", "turns_json"]]
    tmap = dict(zip(corpus.conversation_id, corpus.turns_json))

    leads_turns, leads_secs = [], []
    fired = fired_before = with_money = total = 0
    for line in label_path.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        turns = json.loads(tmap.get(rec["conversation_id"], "[]"))
        if not turns:
            continue
        total += 1
        det = CallDetector()  # fresh per-call state
        interrupt_turn = None
        t = ""
        for k, turn in enumerate(turns):
            t = (t + "\n" + f"{turn['speaker']}: {turn['text']}").strip()
            r = det.analyze(t)
            if r["interrupt"]:
                interrupt_turn = k
                break
        if interrupt_turn is not None:
            fired += 1
        md_turn = rec.get("money_demand_turn")
        if md_turn is not None:
            with_money += 1
            if interrupt_turn is not None:
                lead = md_turn - interrupt_turn
                leads_turns.append(lead)
                its = turns[interrupt_turn].get("ts")
                mts = rec.get("money_demand_timestamp")
                if its is not None and mts is not None:
                    leads_secs.append(mts - its)
                if lead >= 0:
                    fired_before += 1

    out = {
        "n_calls": total, "interrupt_fired": fired,
        "calls_with_money_demand": with_money,
        "fired_before_money_demand": fired_before,
        "median_lead_turns": float(np.median(leads_turns)) if leads_turns else None,
        "mean_lead_turns": round(float(np.mean(leads_turns)), 2) if leads_turns else None,
        "median_lead_seconds": float(np.median(leads_secs)) if leads_secs else None,
    }
    print(f"  [LEAD TIME] fired {fired}/{total}; before money demand "
          f"{fired_before}/{with_money}; median lead "
          f"{out['median_lead_turns']} turns / {out['median_lead_seconds']}s")
    if leads_turns:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.hist(leads_turns, bins=range(min(leads_turns) - 1, max(leads_turns) + 2),
                color="#0B6E7A")
        ax.axvline(0, color="#C62828", ls="--", label="money demand")
        ax.set_xlabel("lead (turns before money demand; >0 = fired earlier)")
        ax.set_ylabel("calls")
        ax.set_title("Interrupt lead time before money demand (ICFD test)",
                     fontsize=11, fontweight="bold")
        ax.legend()
        savefig(fig, "lead_time_distribution.png")
    return out


def _confusion(y, pred, name, title):
    cm = confusion_matrix(y, pred)
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["legit", "scam"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["legit", "scam"])
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_title(f"Confusion — {title}", fontsize=11, fontweight="bold")
    savefig(fig, name)


def _roc_pr(y, s, prefix):
    fpr, tpr, _ = roc_curve(y, s)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(fpr, tpr, label=f"AUC={roc_auc_score(y, s):.3f}")
    ax.plot([0, 1], [0, 1], "k--", lw=0.7)
    ax.set_xlabel("FP rate"); ax.set_ylabel("TP rate")
    ax.set_title(f"ROC — {prefix}", fontsize=11, fontweight="bold"); ax.legend()
    savefig(fig, f"{prefix}_roc.png")
    prec, rec, _ = precision_recall_curve(y, s)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(rec, prec, label=f"AP={average_precision_score(y, s):.3f}")
    ax.set_xlabel("recall"); ax.set_ylabel("precision")
    ax.set_title(f"PR — {prefix}", fontsize=11, fontweight="bold"); ax.legend()
    savefig(fig, f"{prefix}_pr.png")


def _threshold_curve(y, s, chosen):
    ts = np.linspace(0.05, 0.95, 91)
    fprs, recs = [], []
    for t in ts:
        p = (s >= t).astype(int)
        fprs.append(fp_rate(y, p))
        recs.append(float(((p == 1) & (y == 1)).sum() / (y == 1).sum()))
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.plot(ts, fprs, label="FP-rate", color="#C62828")
    ax.plot(ts, recs, label="scam recall", color="#2E7D32")
    ax.axvline(chosen, ls="--", color="#444", label=f"chosen={chosen:.2f}")
    ax.set_xlabel("threshold"); ax.set_ylabel("rate")
    ax.set_title("Threshold vs FP-rate / recall (ICFD test)", fontsize=11, fontweight="bold")
    ax.legend()
    savefig(fig, "threshold_curve.png")


def _comparison_fig(metrics):
    mc = metrics.get("model_comparison", {})
    names = [k for k in mc if mc[k].get("val_macro_f1") is not None]
    if not names:
        return
    f1 = [mc[n]["val_macro_f1"] for n in names]
    fpr = [mc[n]["val_fp_rate"] for n in names]
    x = np.arange(len(names))
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.bar(x - 0.2, f1, 0.4, label="val macro-F1", color="#1565C0")
    ax1.set_ylabel("macro-F1"); ax1.set_ylim(0, 1)
    ax2 = ax1.twinx()
    ax2.bar(x + 0.2, fpr, 0.4, label="val FP-rate", color="#C62828")
    ax2.set_ylabel("FP-rate")
    ax1.set_xticks(x); ax1.set_xticklabels(names, rotation=15)
    ax1.set_title("Model comparison (validation)", fontsize=11, fontweight="bold")
    savefig(fig, "model_comparison.png")


if __name__ == "__main__":
    main()

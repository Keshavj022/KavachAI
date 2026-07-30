"""Evaluation harness for the call-scam LLM detector.

Measures whether the LLM few-shot approach (the same prompt + detector that
ships — imported from the backend, not re-implemented) is good enough:

  1. Fraud Call India Dataset (transcript-level, scam vs legit): accuracy,
     precision/recall/F1, and the headline FALSE-POSITIVE RATE on legit calls.
  2. Held-out real digital-arrest transcripts, fed turn by turn to simulate a
     live call: did it flag the scam, did stages appear in order, and — the key
     metric — the LEAD TIME (how many turns before the `[MONEY DEMAND]` marker
     the deterministic interrupt fired).

Outputs `REPORT.md` + `metrics.json` + a confusion-matrix figure.

Run from the backend virtualenv (it imports the backend `app` package):

    cd backend && source venv/bin/activate && pip install matplotlib
    python ../call_classifier/eval/run_eval.py \
        --fraud-csv /path/to/fraud_call_india.csv --sample 300

Without `--fraud-csv` the Fraud-Call section is skipped. Held-out transcripts
are read from `call_classifier/data/real_calls/test_held_out/` by default.
If `GROQ_API_KEY` is unset the local rule-based fallback detector is used, and
the report says so — the numbers are then illustrative of mechanics only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# --- Import the SHIPPING detector + prompt from the backend. ----------------
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

from app.config import settings  # noqa: E402
from app.models.enums import STAGE_ORDER, ScamStage  # noqa: E402
from app.services.call_detector import (  # noqa: E402
    CallDetectionState,
    detect,
    prompt_version,
)

OUT_DIR = _HERE
DEFAULT_HELD_OUT = _ROOT / "call_classifier" / "data" / "real_calls" / "test_held_out"

_SCAM_LABELS = {"scam", "fraud", "fraudulent", "spam", "smishing", "1", "yes", "true"}
_LEGIT_LABELS = {"legit", "legitimate", "normal", "ham", "genuine", "0", "no", "false"}
_STAGE_MARKER_RE = re.compile(r"\[([A-Za-z _]+)\]")

_MARKER_TO_STAGE = {
    "AUTHORITY CLAIM": ScamStage.authority_claim,
    "ACCUSATION": ScamStage.accusation,
    "ISOLATION": ScamStage.isolation,
    "MONEY DEMAND": ScamStage.money_demand,
}


# ==========================================================================
# 1. Fraud Call India — scam vs legit
# ==========================================================================
def _label_to_binary(raw: str) -> int | None:
    v = str(raw).strip().lower()
    if v in _SCAM_LABELS:
        return 1
    if v in _LEGIT_LABELS:
        return 0
    return None


def _guess_columns(fieldnames: list[str]) -> tuple[str | None, str | None]:
    text_col = label_col = None
    for f in fieldnames:
        lf = f.lower()
        if text_col is None and lf in {"transcript", "text", "message", "content", "conversation"}:
            text_col = f
        if label_col is None and lf in {"label", "class", "target", "type", "category"}:
            label_col = f
    return text_col, label_col


def eval_fraud_call(csv_path: str, text_col: str | None, label_col: str | None,
                    sample: int, sleep: float) -> dict:
    rows = []
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        gt, gl = _guess_columns(fieldnames)
        text_col = text_col or gt
        label_col = label_col or gl
        if not text_col or not label_col:
            raise SystemExit(
                f"Could not identify text/label columns in {fieldnames}. "
                "Pass --text-col and --label-col."
            )
        for r in reader:
            y = _label_to_binary(r.get(label_col, ""))
            txt = (r.get(text_col) or "").strip()
            if y is not None and txt:
                rows.append((txt, y))

    if sample and len(rows) > sample:
        # Deterministic stratified-ish sample: keep order, take first N of each.
        scam = [r for r in rows if r[1] == 1][: sample // 2]
        legit = [r for r in rows if r[1] == 0][: sample - len(scam)]
        rows = scam + legit

    tp = fp = tn = fn = 0
    for i, (txt, y) in enumerate(rows):
        pred = 1 if detect(txt).scam_type != "legitimate" else 0
        if y == 1 and pred == 1:
            tp += 1
        elif y == 1 and pred == 0:
            fn += 1
        elif y == 0 and pred == 1:
            fp += 1
        else:
            tn += 1
        if sleep:
            time.sleep(sleep)
        if (i + 1) % 25 == 0:
            print(f"  fraud-call: {i + 1}/{len(rows)}")

    n = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    result = {
        "n": n, "n_scam": tp + fn, "n_legit": fp + tn,
        "accuracy": round((tp + tn) / n, 4) if n else 0.0,
        "precision_scam": round(precision, 4),
        "recall_scam": round(recall, 4),
        "f1_scam": round(f1, 4),
        "false_positive_rate_legit": round(fpr, 4),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }
    _confusion_fig(tp, fp, tn, fn)
    return result


def _confusion_fig(tp, fp, tn, fn) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  (matplotlib not installed — skipping confusion figure)")
        return
    cm = [[tn, fp], [fn, tp]]
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["legit", "scam"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["legit", "scam"])
    ax.set_xlabel("predicted"); ax.set_ylabel("true")
    mx = max(max(row) for row in cm) or 1
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i][j]), ha="center",
                    color="white" if cm[i][j] > mx / 2 else "black")
    ax.set_title("Fraud Call India — confusion", fontsize=11, fontweight="bold")
    fig.colorbar(im, fraction=0.046, pad=0.04)
    fig.savefig(OUT_DIR / "confusion_fraud_call.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("  saved confusion_fraud_call.png")


# ==========================================================================
# 2. Held-out real digital-arrest transcripts — turn by turn
# ==========================================================================
@dataclass
class CallResult:
    name: str
    turns: int
    classified_scam: bool
    interrupt_turn: int | None
    money_demand_turn: int | None
    lead_turns: int | None  # turns before money demand the interrupt fired
    fired_before_money: bool
    stages_in_order: bool


def _parse_transcript(path: Path) -> tuple[list[str], dict[int, ScamStage]]:
    """Return (cleaned turns, {turn_index: annotated stage})."""
    turns: list[str] = []
    markers: dict[int, ScamStage] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        for m in _STAGE_MARKER_RE.findall(line):
            key = m.strip().upper()
            if key in _MARKER_TO_STAGE:
                markers[len(turns)] = _MARKER_TO_STAGE[key]
        clean = _STAGE_MARKER_RE.sub("", line).strip()
        if clean:
            turns.append(clean)
    return turns, markers


def eval_held_out(dir_path: Path, limit: int, sleep: float) -> tuple[list[dict], dict]:
    files = sorted(dir_path.glob("*.txt")) + sorted(dir_path.glob("*.md"))
    # A README in the data folder documents the format — it is not a transcript.
    files = [p for p in files if p.name.lower() != "readme.md"]
    if limit:
        files = files[:limit]
    per_call: list[CallResult] = []

    for path in files:
        turns, markers = _parse_transcript(path)
        if not turns:
            continue
        money_turn = next(
            (i for i, s in markers.items() if s == ScamStage.money_demand), None
        )
        state = CallDetectionState()
        transcript = ""
        interrupt_turn = None
        classified_scam = False
        detected_stage_seq: list[int] = []

        for i, turn in enumerate(turns):
            transcript = f"{transcript}\n{turn}".strip()
            result = detect(transcript)
            decision = state.update(result)
            detected_stage_seq.append(STAGE_ORDER[result.stage.value])
            if result.scam_type != "legitimate" and result.confidence >= 0.5:
                classified_scam = True
            if decision.interrupt and interrupt_turn is None:
                interrupt_turn = i
            if sleep:
                time.sleep(sleep)

        lead = (money_turn - interrupt_turn) if (money_turn is not None and interrupt_turn is not None) else None
        fired_before = bool(lead is not None and lead >= 0)
        # Stages appear in order if the detected-stage sequence never regresses.
        in_order = all(
            detected_stage_seq[i] >= detected_stage_seq[i - 1]
            for i in range(1, len(detected_stage_seq))
        )
        per_call.append(CallResult(
            name=path.name, turns=len(turns), classified_scam=classified_scam,
            interrupt_turn=interrupt_turn, money_demand_turn=money_turn,
            lead_turns=lead, fired_before_money=fired_before, stages_in_order=in_order,
        ))
        print(f"  {path.name}: scam={classified_scam} interrupt@{interrupt_turn} "
              f"money@{money_turn} lead={lead}")

    leads = [c.lead_turns for c in per_call if c.lead_turns is not None]
    agg = {
        "n_calls": len(per_call),
        "classified_scam": sum(c.classified_scam for c in per_call),
        "fired_before_money_demand": sum(c.fired_before_money for c in per_call),
        "calls_with_money_marker": sum(c.money_demand_turn is not None for c in per_call),
        "median_lead_turns": round(statistics.median(leads), 2) if leads else None,
        "mean_lead_turns": round(statistics.mean(leads), 2) if leads else None,
        "stages_in_order": sum(c.stages_in_order for c in per_call),
    }
    return [asdict(c) for c in per_call], agg


# ==========================================================================
def write_report(metrics: dict) -> None:
    with open(OUT_DIR / "metrics.json", "w") as fh:
        json.dump(metrics, fh, indent=2)

    fc = metrics.get("fraud_call")
    ho = metrics.get("held_out", {}).get("aggregate")
    detector = metrics["run"]["detector"]
    lines = [
        "# Call Detector — Evaluation Report",
        "",
        f"- Detector: **{detector}** (prompt `{metrics['run']['prompt_version']}`, "
        f"model `{metrics['run']['model']}`)",
        f"- Generated: {metrics['run']['timestamp']}",
        "",
    ]
    if detector != "groq":
        lines += [
            "> NOTE: `GROQ_API_KEY` was not set, so these numbers come from the "
            "local **rule-based fallback**, not the Groq few-shot model. Set the "
            "key and re-run to evaluate the shipping LLM path.",
            "",
        ]

    lines += ["## 1. Fraud Call India (scam vs legit)", ""]
    if fc:
        lines += [
            f"Sample: **{fc['n']}** calls ({fc['n_scam']} scam / {fc['n_legit']} legit).",
            "",
            "| Metric | Value |",
            "| --- | --- |",
            f"| **False-positive rate (legit → scam)** | **{fc['false_positive_rate_legit']:.3f}** |",
            f"| Accuracy | {fc['accuracy']:.3f} |",
            f"| Precision (scam) | {fc['precision_scam']:.3f} |",
            f"| Recall (scam) | {fc['recall_scam']:.3f} |",
            f"| F1 (scam) | {fc['f1_scam']:.3f} |",
            "",
            f"Confusion — TP {fc['confusion']['tp']}, FP {fc['confusion']['fp']}, "
            f"TN {fc['confusion']['tn']}, FN {fc['confusion']['fn']} "
            "(see `confusion_fraud_call.png`).",
            "",
        ]
    else:
        lines += ["_Skipped — no `--fraud-csv` provided._", ""]

    lines += ["## 2. Held-out real digital-arrest transcripts (arc lead time)", ""]
    if ho and ho["n_calls"]:
        lines += [
            f"Fed **{ho['n_calls']}** transcripts turn by turn.",
            "",
            f"- Classified as scam: **{ho['classified_scam']}/{ho['n_calls']}**",
            f"- Interrupt fired **before** the money demand: "
            f"**{ho['fired_before_money_demand']}/{ho['calls_with_money_marker']}** "
            "(of calls with a money-demand marker)",
            f"- Median lead time: **{ho['median_lead_turns']} turns** before the money "
            f"demand (mean {ho['mean_lead_turns']})",
            f"- Detected stages appeared in non-regressing order: "
            f"{ho['stages_in_order']}/{ho['n_calls']}",
            "",
            "Per-call detail is in `metrics.json`.",
            "",
        ]
    else:
        lines += [
            "_No transcripts found. Place annotated real transcripts (with inline "
            "`[AUTHORITY CLAIM]` / `[ACCUSATION]` / `[ISOLATION]` / `[MONEY DEMAND]` "
            "markers) in `call_classifier/data/real_calls/test_held_out/`._",
            "",
        ]

    lines += [
        "## Caveats",
        "",
        "- The real held-out set is small — treat these as **illustrative, not "
        "statistically tight**. Do not over-claim precision on a few dozen samples.",
        "- Lead time is measured in conversational turns relative to the annotated "
        "`[MONEY DEMAND]` marker; a positive value means the interrupt fired before "
        "the money was demanded, which is the design goal.",
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'REPORT.md'} and metrics.json")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate the call-scam LLM detector.")
    ap.add_argument("--fraud-csv", default=None, help="Path to Fraud Call India CSV.")
    ap.add_argument("--text-col", default=None)
    ap.add_argument("--label-col", default=None)
    ap.add_argument("--sample", type=int, default=300, help="Max fraud-call rows.")
    ap.add_argument("--held-out-dir", default=str(DEFAULT_HELD_OUT))
    ap.add_argument("--limit-heldout", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.0, help="Delay between calls (rate limits).")
    args = ap.parse_args()

    # DEPRECATED: this harness scored the earlier Groq few-shot detector, which
    # has been replaced by the on-device trained models. Use
    # ``call_classifier/src/06_evaluate.py`` instead. Kept for its prior report.
    detector = "on_device_or_fallback"
    print(f"=== Call detector evaluation (detector={detector}) — DEPRECATED, "
          f"see src/06_evaluate.py ===")

    metrics: dict = {
        "run": {
            "detector": detector,
            "model": "on-device",
            "prompt_version": prompt_version(),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    }

    if args.fraud_csv and os.path.exists(args.fraud_csv):
        print("\n[1] Fraud Call India")
        metrics["fraud_call"] = eval_fraud_call(
            args.fraud_csv, args.text_col, args.label_col, args.sample, args.sleep
        )
    else:
        if args.fraud_csv:
            print(f"  fraud-csv not found: {args.fraud_csv} — skipping.")
        metrics["fraud_call"] = None

    print("\n[2] Held-out digital-arrest transcripts")
    held_dir = Path(args.held_out_dir)
    if held_dir.is_dir():
        per_call, agg = eval_held_out(held_dir, args.limit_heldout, args.sleep)
        metrics["held_out"] = {"aggregate": agg, "per_call": per_call}
    else:
        print(f"  held-out dir not found: {held_dir}")
        metrics["held_out"] = {"aggregate": {"n_calls": 0}, "per_call": []}

    write_report(metrics)


if __name__ == "__main__":
    main()

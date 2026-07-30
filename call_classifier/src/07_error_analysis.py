"""Phase 5b — Error analysis on each test set (verbatim examples).

Focus on the costliest error: false positives on REAL legitimate calls
(call-center). Also dumps false negatives on the real scam openings
(youtube-scam), which is where the synthetic→real shift bites.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def scores(clf, X):
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(X)[:, 1]
    return _sigmoid(clf.decision_function(X))


def main() -> None:
    config.set_global_seed()
    print("=== Phase 5b: error analysis ===")
    df = pd.read_parquet(config.CHUNKS_PARQUET)
    corpus = pd.read_parquet(config.CORPUS_PARQUET)[["conversation_id", "full_text_raw"]]
    raw_map = dict(zip(corpus.conversation_id, corpus.full_text_raw))
    deploy = json.load(open(config.ARTIFACTS / "call_deployment.json"))
    clf = joblib.load(config.ARTIFACTS / "call_classifier.joblib")
    T = float(deploy["threshold"])

    lines = ["# Call classifier — error analysis\n",
             f"Deployed: {deploy['winner']} @ threshold {T:.3f}\n"]

    # False positives on REAL legit (call-center) — the costliest error.
    cc = df[df.split == "cc_test"].copy()
    cc["s"] = scores(clf, cc["text_norm"].tolist())
    cc_fp = cc[cc.s >= T].sort_values("s", ascending=False)
    lines.append(f"## False positives on REAL legit call-center ({len(cc_fp)} of {len(cc)})\n")
    for _, r in cc_fp.head(10).iterrows():
        lines.append(f"- p={r['s']:.3f} :: {raw_map.get(r['conversation_id'], r['text_norm'])[:400]}")
    if len(cc_fp) == 0:
        lines.append("_None — zero false positives on real legitimate calls._")

    # False negatives on REAL scam openings (youtube-scam).
    yt = df[df.split == "yt_test"].copy()
    yt["s"] = scores(clf, yt["text_norm"].tolist())
    yt_fn = yt[yt.s < T].sort_values("s")
    lines.append(f"\n## False negatives on REAL scam openings youtube-scam "
                 f"({len(yt_fn)} of {len(yt)})\n")
    for _, r in yt_fn.head(12).iterrows():
        lines.append(f"- p={r['s']:.3f} :: {raw_map.get(r['conversation_id'], r['text_norm'])[:400]}")

    # ICFD test hard-negative FPs (Ambiguous but Ultimately Normal).
    amb = df[(df.split == "test") & (df.case_type == "Ambiguous but Ultimately Normal")
             & (df.label == 0)].copy()
    amb["s"] = scores(clf, amb["text_norm"].tolist())
    amb_fp = amb[amb.s >= T].sort_values("s", ascending=False)
    lines.append(f"\n## False positives on ICFD hard negatives "
                 f"'Ambiguous but Ultimately Normal' ({len(amb_fp)} of {len(amb)})\n")
    for _, r in amb_fp.head(8).iterrows():
        lines.append(f"- p={r['s']:.3f} :: {raw_map.get(r['conversation_id'], r['text_norm'])[:400]}")

    (config.REPORTS / "error_analysis.md").write_text("\n".join(lines))
    print(f"  call-center FPs: {len(cc_fp)} | youtube FNs: {len(yt_fn)} | "
          f"ICFD ambiguous FPs: {len(amb_fp)}")
    print("  saved reports/error_analysis.md")


if __name__ == "__main__":
    main()

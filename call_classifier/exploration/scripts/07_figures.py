"""Generate the headline figures from stats.json (+ a light reload for ICFD
chunk sizes). Read-only."""

from __future__ import annotations

import glob
import json

import matplotlib.pyplot as plt
import numpy as np
import pyarrow.parquet as pq

import common as c

STATS = json.load(open(c.STATS_JSON))


def fig_icfd_verdict_per_split() -> None:
    d = STATS["icfd"]["source"]["per_split_verdict"]
    splits = ["train", "validation", "test", "cross_domain"]
    yes = [d.get(s, {}).get("YES", 0) for s in splits]
    no = [d.get(s, {}).get("NO", 0) for s in splits]
    x = np.arange(len(splits))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, no, label="NO (legitimate)", color="#2E7D32")
    ax.bar(x, yes, bottom=no, label="YES (scam)", color="#C62828")
    ax.set_xticks(x); ax.set_xticklabels(splits)
    ax.set_ylabel("conversations")
    ax.set_title("ICFD final_verdict per split — legit lives in TRAIN; "
                 "val/test/cross are ~all scam", fontsize=10, fontweight="bold")
    for i, s in enumerate(splits):
        tot = yes[i] + no[i]
        ax.text(i, tot, f"{yes[i]}/{no[i]}", ha="center", va="bottom", fontsize=9)
    ax.legend()
    c.savefig(fig, "icfd_verdict_per_split.png")


def fig_icfd_case_type() -> None:
    d = STATS["icfd"]["source"]["per_split_case_type"]
    cats = ["Clear Normal", "Ambiguous but Ultimately Normal", "Subtle Fraud",
            "Clear Fraud"]
    def norm(k):  # unify spacing/underscore variants
        return k.replace("_", " ")
    splits = ["train", "validation", "test", "cross_domain"]
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = np.zeros(len(splits))
    colors = {"Clear Normal": "#2E7D32", "Ambiguous but Ultimately Normal": "#7CB342",
              "Subtle Fraud": "#F9A825", "Clear Fraud": "#C62828"}
    for cat in cats:
        vals = []
        for s in splits:
            counts = {norm(k): v for k, v in d.get(s, {}).items()}
            vals.append(counts.get(cat, 0))
        ax.bar(splits, vals, bottom=bottom, label=cat, color=colors[cat])
        bottom += np.array(vals)
    ax.set_ylabel("conversations")
    ax.set_title("ICFD case_type per split (the 'Ambiguous but Ultimately Normal' "
                 "hard negatives are TRAIN-only)", fontsize=9.5, fontweight="bold")
    ax.legend(fontsize=8)
    c.savefig(fig, "icfd_case_type_per_split.png")


def fig_dataset_roles() -> None:
    # A simple qualitative matrix: scam / legit availability + structure.
    rows = ["icfd", "call-center", "call-transcript", "youtube-scam"]
    scam = [1, 0, 1, 1]      # provides scam examples
    legit = [1, 1, 1, 0]     # provides legit examples
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x = np.arange(len(rows))
    ax.bar(x - 0.2, scam, 0.4, label="has scam", color="#C62828")
    ax.bar(x + 0.2, legit, 0.4, label="has legit", color="#2E7D32")
    ax.set_xticks(x); ax.set_xticklabels(rows)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["no", "yes"])
    ax.set_title("Which dataset provides scam vs legitimate examples",
                 fontsize=10, fontweight="bold")
    ax.legend()
    c.savefig(fig, "dataset_scam_legit_roles.png")


def fig_icfd_chunks_hist() -> None:
    # Light reload: one train shard for a chunks-per-conversation histogram.
    shard = sorted(glob.glob(str(c.DATASETS["icfd"] / "streaming_chunks" / "train-*.parquet")))[0]
    df = pq.read_table(shard, columns=["conversation_uid", "chunk_timestamp"]).to_pandas()
    sizes = df.groupby("conversation_uid").size().values
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.hist(sizes, bins=40, color="#22808a")
    ax.set_xlabel("streaming chunks per conversation (one train shard)")
    ax.set_ylabel("conversations")
    ax.set_title(f"ICFD chunks/conversation — 3s cadence, median "
                 f"{int(np.median(sizes))} (~{int(np.median(sizes))*3}s calls)",
                 fontsize=10, fontweight="bold")
    c.savefig(fig, "icfd_chunks_per_conversation.png")


def fig_language_mix() -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    datasets = {
        "icfd (sample)": STATS["icfd"]["source"]["language_sample"],
        "call-center (sample)": STATS["call_center"]["language_sample"],
        "youtube-scam": STATS["youtube_scam"]["language_buckets"],
    }
    buckets = ["english", "hinglish", "hindi_script", "other"]
    x = np.arange(len(datasets))
    bottom = np.zeros(len(datasets))
    colors = {"english": "#1565C0", "hinglish": "#E0A020",
              "hindi_script": "#C62828", "other": "#999999"}
    for b in buckets:
        vals = []
        for dd in datasets.values():
            tot = sum(dd.values()) or 1
            vals.append(dd.get(b, 0) / tot)
        ax.bar(list(datasets.keys()), vals, bottom=bottom, label=b, color=colors[b])
        bottom += np.array(vals)
    ax.set_ylabel("fraction (heuristic, sampled)")
    ax.set_title("Language mix by dataset (heuristic — see method/limits)",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=8)
    c.savefig(fig, "language_mix_by_dataset.png")


def main() -> None:
    print("=== figures ===")
    fig_icfd_verdict_per_split()
    fig_icfd_case_type()
    fig_dataset_roles()
    fig_icfd_chunks_hist()
    fig_language_mix()


if __name__ == "__main__":
    main()

"""Phase 2 — Exploratory data analysis.

Every figure is saved to reports/figures/ (numbered). Prints stats used in the
written takeaways in REPORT.md. Operates on the deduped combined dataset so the
EDA reflects the data actually modelled.
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pandas as pd

import utils
import config
from features_lib import clean_for_tfidf, engineered_features, ENGINEERED_COLUMNS

plt = utils.plt

CLASS_COLORS = {"ham": "#2E7D32", "spam": "#F9A825", "smishing": "#C62828"}
BIN_COLORS = {"legit": "#2E7D32", "malicious": "#C62828"}


def _binlabel(df):
    return df["label"].map(config.BINARY_MAP).map(config.BINARY_NAMES)


def fig_class_distribution(df: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    # Binary combined.
    b = _binlabel(df).value_counts().reindex(["legit", "malicious"])
    axes[0].bar(b.index, b.values, color=[BIN_COLORS[x] for x in b.index])
    axes[0].set_title("Binary target (combined)")
    axes[0].set_ylabel("messages")
    for i, v in enumerate(b.values):
        axes[0].text(i, v, str(v), ha="center", va="bottom")

    # 3-class combined.
    c = df["label"].value_counts().reindex(["ham", "spam", "smishing"])
    axes[1].bar(c.index, c.values, color=[CLASS_COLORS[x] for x in c.index])
    axes[1].set_title("3-class target (combined)")
    for i, v in enumerate(c.values):
        axes[1].text(i, v, str(v), ha="center", va="bottom")

    # By source (3-class).
    piv = df.groupby(["source", "label"]).size().unstack(fill_value=0)
    piv = piv.reindex(columns=["ham", "spam", "smishing"], fill_value=0)
    piv.plot(kind="bar", stacked=True, ax=axes[2],
             color=[CLASS_COLORS[x] for x in piv.columns])
    axes[2].set_title("Class by source")
    axes[2].set_xlabel("")
    axes[2].tick_params(axis="x", rotation=0)

    fig.suptitle("Class distributions", fontsize=14, fontweight="bold")
    utils.savefig(fig, "01_class_distribution.png")
    return {
        "binary": b.to_dict(),
        "multiclass": c.to_dict(),
        "by_source": piv.to_dict(),
        "malicious_prevalence": round(float((df["label"] != "ham").mean()), 4),
    }


def fig_length_distributions(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["n_chars"] = df["text"].str.len()
    df["n_words"] = df["text"].str.split().map(len)

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    for cls in ["ham", "spam", "smishing"]:
        sub = df[df["label"] == cls]
        axes[0].hist(sub["n_chars"], bins=40, range=(0, 320), alpha=0.6,
                     label=cls, color=CLASS_COLORS[cls], density=True)
        axes[1].hist(sub["n_words"], bins=30, range=(0, 60), alpha=0.6,
                     label=cls, color=CLASS_COLORS[cls], density=True)
    axes[0].set_title("Message length (characters)")
    axes[0].set_xlabel("characters"); axes[0].set_ylabel("density"); axes[0].legend()
    axes[1].set_title("Message length (words)")
    axes[1].set_xlabel("words"); axes[1].legend()
    fig.suptitle("Message-length distributions by class", fontsize=14, fontweight="bold")
    utils.savefig(fig, "02_length_distributions.png")

    return {
        cls: {
            "median_chars": float(df[df.label == cls]["n_chars"].median()),
            "median_words": float(df[df.label == cls]["n_words"].median()),
        }
        for cls in ["ham", "spam", "smishing"]
    }


def fig_engineered_distributions(df: pd.DataFrame, feats: pd.DataFrame) -> dict:
    cols = ["digit_ratio", "upper_ratio", "punct_ratio", "n_scam_keywords"]
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2))
    for ax, col in zip(axes, cols):
        data = [feats.loc[df["label"].values == cls, col].values
                for cls in ["ham", "spam", "smishing"]]
        bp = ax.boxplot(data, tick_labels=["ham", "spam", "smish"],
                        showfliers=False, patch_artist=True)
        for patch, cls in zip(bp["boxes"], ["ham", "spam", "smishing"]):
            patch.set_facecolor(CLASS_COLORS[cls]); patch.set_alpha(0.7)
        ax.set_title(col)
    fig.suptitle("Engineered numeric features by class", fontsize=14, fontweight="bold")
    utils.savefig(fig, "03_engineered_distributions.png")

    summary = {}
    for cls in ["ham", "spam", "smishing"]:
        m = feats.loc[df["label"].values == cls]
        summary[cls] = {c: round(float(m[c].mean()), 3) for c in cols}
    return summary


def fig_attribute_presence(df: pd.DataFrame, feats: pd.DataFrame) -> dict:
    attrs = ["has_url", "has_phone", "has_email", "has_currency"]
    classes = ["ham", "spam", "smishing"]
    rates = {a: [] for a in attrs}
    for cls in classes:
        m = feats.loc[df["label"].values == cls]
        for a in attrs:
            rates[a].append(float(m[a].mean()))

    x = np.arange(len(classes)); width = 0.2
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, a in enumerate(attrs):
        ax.bar(x + (i - 1.5) * width, rates[a], width, label=a)
    ax.set_xticks(x); ax.set_xticklabels(classes)
    ax.set_ylabel("presence rate"); ax.set_ylim(0, 1)
    ax.set_title("URL / phone / email / currency presence by class",
                 fontsize=13, fontweight="bold")
    ax.legend()
    utils.savefig(fig, "04_attribute_presence.png")
    return {a: dict(zip(classes, [round(r, 3) for r in rates[a]])) for a in attrs}


def fig_top_tokens(df: pd.DataFrame) -> dict:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    def top_for(cls, n=15):
        counter: Counter = Counter()
        for t in df[df["label"] == cls]["text"]:
            for w in clean_for_tfidf(t).split():
                if len(w) > 2 and w not in ENGLISH_STOP_WORDS and w.isalpha():
                    counter[w] += 1
        return counter.most_common(n)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    result = {}
    for ax, cls in zip(axes, ["ham", "spam", "smishing"]):
        top = top_for(cls)
        result[cls] = top
        words = [w for w, _ in top][::-1]
        counts = [c for _, c in top][::-1]
        ax.barh(words, counts, color=CLASS_COLORS[cls], alpha=0.8)
        ax.set_title(f"Top tokens — {cls}")
    fig.suptitle("Most frequent content tokens per class", fontsize=14, fontweight="bold")
    utils.savefig(fig, "05_top_tokens.png")
    return {k: [w for w, _ in v] for k, v in result.items()}


def fig_wordclouds(df: pd.DataFrame) -> None:
    try:
        from wordcloud import WordCloud
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    except ImportError:
        print("  wordcloud not available; skipping word clouds.")
        return
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, cls in zip(axes, ["ham", "spam", "smishing"]):
        text = " ".join(clean_for_tfidf(t) for t in df[df["label"] == cls]["text"])
        wc = WordCloud(width=500, height=350, background_color="white",
                       stopwords=set(ENGLISH_STOP_WORDS), colormap="viridis").generate(text)
        ax.imshow(wc, interpolation="bilinear"); ax.axis("off")
        ax.set_title(f"{cls}", fontsize=12)
    fig.suptitle("Word clouds per class", fontsize=14, fontweight="bold")
    utils.savefig(fig, "06_wordclouds.png")


def fig_duplicate_analysis() -> None:
    with open(config.DEDUP_REPORT_JSON) as fh:
        rep = json.load(fh)
    labels = ["exact\nraw", "near\n(templated)", "kept"]
    vals = [rep["exact_raw_duplicates_removed"],
            rep["near_duplicates_removed"], rep["rows_after_dedup"]]
    colors = ["#C62828", "#F9A825", "#2E7D32"]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, vals, color=colors, alpha=0.85)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom")
    ax.set_ylabel("messages")
    ax.set_title(
        f"Deduplication: {rep['rows_before_dedup']} combined → "
        f"{rep['rows_after_dedup']} unique\n"
        f"({rep['cross_dataset_overlap_rows']} cross-dataset overlap rows, "
        f"{rep['label_conflict_groups']} label-conflict groups)",
        fontsize=12, fontweight="bold",
    )
    utils.savefig(fig, "07_duplicate_analysis.png")


def main() -> None:
    config.set_global_seed()
    print("=== Phase 2: EDA ===")
    df = utils.load_combined()
    feats = engineered_features(df["text"])

    eda = {}
    eda["class_distribution"] = fig_class_distribution(df)
    eda["length"] = fig_length_distributions(df)
    eda["engineered"] = fig_engineered_distributions(df, feats)
    eda["attribute_presence"] = fig_attribute_presence(df, feats)
    eda["top_tokens"] = fig_top_tokens(df)
    fig_wordclouds(df)
    fig_duplicate_analysis()

    utils.update_metrics("eda", eda)
    print("\nEDA complete. Key numbers:")
    print(f"  malicious prevalence: {eda['class_distribution']['malicious_prevalence']:.1%}")
    print(f"  median chars ham/spam/smish: "
          f"{eda['length']['ham']['median_chars']:.0f}/"
          f"{eda['length']['spam']['median_chars']:.0f}/"
          f"{eda['length']['smishing']['median_chars']:.0f}")
    print(f"  has_url rate ham/spam/smish: "
          f"{eda['attribute_presence']['has_url']['ham']:.2f}/"
          f"{eda['attribute_presence']['has_url']['spam']:.2f}/"
          f"{eda['attribute_presence']['has_url']['smishing']:.2f}")


if __name__ == "__main__":
    main()

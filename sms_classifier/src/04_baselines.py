"""Phase 5 — Classical baselines.

TF-IDF (word + char n-grams) + engineered features feeding Logistic Regression
and Linear SVM; TF-IDF-only feeding Multinomial/Complement Naive Bayes (NB needs
non-negative inputs). All with balanced class weighting for the imbalance.

Model selection uses stratified k-fold CV on the TRAINING split only; the
validation split is reported for a held-out read; the TEST split is never
touched here (that is phase 7). Every fitted pipeline is saved so phase 7 can
score them on the sacred test set. Both the binary and 3-class targets are run.
"""

from __future__ import annotations

import time

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import ComplementNB, MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MaxAbsScaler
from sklearn.svm import LinearSVC

import utils
import config
from features_lib import (
    EngineeredFeatures,
    build_char_vectorizer,
    build_word_vectorizer,
)


def _tfidf_union() -> FeatureUnion:
    """Word + char TF-IDF only (non-negative → safe for Naive Bayes)."""
    return FeatureUnion([
        ("word", build_word_vectorizer()),
        ("char", build_char_vectorizer()),
    ])


def _full_union() -> FeatureUnion:
    """Word + char TF-IDF + scaled engineered features (for LogReg / SVM)."""
    return FeatureUnion([
        ("word", build_word_vectorizer()),
        ("char", build_char_vectorizer()),
        ("eng", Pipeline([("feat", EngineeredFeatures()), ("scale", MaxAbsScaler())])),
    ])


def build_models() -> dict[str, Pipeline]:
    """Return the candidate baseline pipelines."""
    seed = config.RANDOM_SEED
    return {
        "logreg": Pipeline([
            ("feats", _full_union()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced",
                                       C=4.0, random_state=seed)),
        ]),
        "linear_svm": Pipeline([
            ("feats", _full_union()),
            ("clf", LinearSVC(class_weight="balanced", C=1.0, random_state=seed)),
        ]),
        "multinomial_nb": Pipeline([
            ("feats", _tfidf_union()),
            ("clf", MultinomialNB(alpha=0.1)),
        ]),
        "complement_nb": Pipeline([
            ("feats", _tfidf_union()),
            ("clf", ComplementNB(alpha=0.1)),
        ]),
    }


def evaluate_target(target: str, name_suffix: str) -> dict:
    """Run CV + validation reporting for all baselines on one target."""
    train, val, _test = utils.split_frames()
    X_train, y_train = train["text"], train[target].values
    X_val, y_val = val["text"], val[target].values

    skf = StratifiedKFold(n_splits=config.CV_FOLDS, shuffle=True,
                          random_state=config.RANDOM_SEED)
    results = {}

    for name, pipe in build_models().items():
        t0 = time.time()
        # Cross-validated out-of-fold predictions on TRAIN for honest CV metrics.
        # n_jobs=1: data is small so CV is fast, and single-process avoids a
        # noisy loky/multiprocessing shutdown warning on some Python builds.
        cv_pred = cross_val_predict(pipe, X_train, y_train, cv=skf, n_jobs=1)
        cv_macro_f1 = f1_score(y_train, cv_pred, average="macro")

        # Fit on full train, report on validation, and persist.
        pipe.fit(X_train, y_train)
        val_pred = pipe.predict(X_val)
        val_macro_f1 = f1_score(y_val, val_pred, average="macro")
        elapsed = time.time() - t0

        block = {
            "cv_macro_f1": round(float(cv_macro_f1), 4),
            "val_macro_f1": round(float(val_macro_f1), 4),
            "fit_seconds": round(elapsed, 1),
        }
        if target == "y_binary":
            block["cv_fp_rate"] = round(utils.false_positive_rate(y_train, cv_pred), 4)
            block["val_fp_rate"] = round(utils.false_positive_rate(y_val, val_pred), 4)
        results[name] = block

        model_path = config.MODELS_DIR / f"baseline_{name}_{name_suffix}.joblib"
        joblib.dump(pipe, model_path)

        extra = f" cv_fpr={block.get('cv_fp_rate', '—')}" if target == "y_binary" else ""
        print(f"  {name:16s} cv_macroF1={block['cv_macro_f1']:.4f} "
              f"val_macroF1={block['val_macro_f1']:.4f}{extra} ({block['fit_seconds']}s)")

    return results


def main() -> None:
    config.set_global_seed()
    print("=== Phase 5: classical baselines ===")

    print("\n[binary target: legit vs malicious]")
    binary = evaluate_target("y_binary", "binary")

    print("\n[3-class target: ham / spam / smishing]")
    multiclass = evaluate_target("y_multiclass", "multiclass")

    utils.update_metrics("baselines", {"binary": binary, "multiclass": multiclass})

    best = min(binary.items(), key=lambda kv: (kv[1]["cv_fp_rate"], -kv[1]["cv_macro_f1"]))
    print(f"\nLowest-FP binary baseline (CV): {best[0]} "
          f"(fpr={best[1]['cv_fp_rate']}, macroF1={best[1]['cv_macro_f1']})")


if __name__ == "__main__":
    main()

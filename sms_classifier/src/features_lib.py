"""Reusable text normalization and engineered-feature logic.

Two consumers:
  * classical models — use `normalize_for_dedup`, the engineered numeric
    features, and the TF-IDF vectorizer builders here.
  * the transformer — uses raw text (casing/punctuation preserved); only the
    dedup normalization is shared.

Attribute logic (URL / EMAIL / PHONE presence) mirrors the intent of the
Mishra/Soni attribute-extraction scripts, re-implemented here as features.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# --- Regexes for engineered features ---------------------------------------
_URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|co|in|ly|info|xyz|link)\b)", re.I)
_EMAIL_RE = re.compile(r"\b[\w.\-]+@[\w.\-]+\.\w+\b")
# UK/US/India-ish phone-like runs: long digit strings or short-code style.
_PHONE_RE = re.compile(r"(?:\+?\d[\d\-\s]{7,}\d)|\b\d{5,}\b")
_CURRENCY_RE = re.compile(r"[£$€₹]|\b(?:gbp|usd|inr|rs|rupees|pounds?)\b", re.I)
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")

# Words that recur in scam/marketing SMS — used only as an interpretable flag,
# not as the model itself.
_SCAM_KEYWORDS = [
    "free", "win", "winner", "won", "prize", "claim", "urgent", "cash",
    "txt", "text", "reply", "call", "click", "verify", "account", "bank",
    "otp", "code", "offer", "guaranteed", "congratulations", "selected",
    "customer", "service", "award", "voucher", "gift",
]


def normalize_for_dedup(text: str) -> str:
    """Aggressive normalization for duplicate detection.

    Lowercase, strip punctuation, collapse whitespace, drop digits so that
    templated scams that differ only by a phone number / amount collapse to the
    same key (near-duplicate detection).
    """
    if not isinstance(text, str):
        return ""
    t = text.lower()
    t = _URL_RE.sub(" url ", t)
    t = re.sub(r"\d+", " ", t)  # remove digits so templated variants collapse
    t = _NON_ALNUM.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t


def clean_for_tfidf(text: str) -> str:
    """Light cleaning for classical TF-IDF: lowercase + collapse whitespace.

    Casing is dropped (classical models don't benefit much and it reduces
    sparsity) but punctuation is kept minimally via the vectorizer's own
    tokenization; char n-grams handle obfuscation.
    """
    if not isinstance(text, str):
        return ""
    return _WS.sub(" ", text.lower()).strip()


def engineered_features(texts: "pd.Series | list[str]") -> pd.DataFrame:
    """Compute interpretable numeric features for each message."""
    rows = []
    for t in texts:
        s = t if isinstance(t, str) else ""
        n_chars = len(s)
        words = s.split()
        n_words = len(words)
        n_digits = sum(c.isdigit() for c in s)
        n_upper = sum(c.isupper() for c in s)
        n_alpha = sum(c.isalpha() for c in s)
        n_punct = sum(not c.isalnum() and not c.isspace() for c in s)
        rows.append(
            {
                "n_chars": n_chars,
                "n_words": n_words,
                "avg_word_len": (n_chars / n_words) if n_words else 0.0,
                "digit_ratio": (n_digits / n_chars) if n_chars else 0.0,
                "upper_ratio": (n_upper / n_alpha) if n_alpha else 0.0,
                "punct_ratio": (n_punct / n_chars) if n_chars else 0.0,
                "has_url": int(bool(_URL_RE.search(s))),
                "has_email": int(bool(_EMAIL_RE.search(s))),
                "has_phone": int(bool(_PHONE_RE.search(s))),
                "has_currency": int(bool(_CURRENCY_RE.search(s))),
                "n_scam_keywords": sum(
                    1 for kw in _SCAM_KEYWORDS if re.search(rf"\b{kw}\b", s, re.I)
                ),
            }
        )
    return pd.DataFrame(rows).astype(float)


ENGINEERED_COLUMNS = [
    "n_chars", "n_words", "avg_word_len", "digit_ratio", "upper_ratio",
    "punct_ratio", "has_url", "has_email", "has_phone", "has_currency",
    "n_scam_keywords",
]


def build_word_vectorizer():
    """TF-IDF over word 1–2 grams."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    return TfidfVectorizer(
        preprocessor=clean_for_tfidf,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        strip_accents="unicode",
    )


def build_char_vectorizer():
    """TF-IDF over char 2–5 grams (catches obfuscation like 'fr€e', 'w1n')."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    return TfidfVectorizer(
        preprocessor=clean_for_tfidf,
        analyzer="char_wb",
        ngram_range=(2, 5),
        min_df=3,
        sublinear_tf=True,
    )


try:
    from sklearn.base import BaseEstimator, TransformerMixin

    class EngineeredFeatures(BaseEstimator, TransformerMixin):
        """sklearn transformer wrapping `engineered_features`.

        Stateless (no fit needed) so it is safe inside a Pipeline/FeatureUnion;
        scaling is applied by a following scaler that IS fit on train only.
        """

        def fit(self, X, y=None):  # noqa: D401
            return self

        def transform(self, X):
            import pandas as pd

            series = X if isinstance(X, pd.Series) else pd.Series(list(X))
            return engineered_features(series).values

        def get_feature_names_out(self, input_features=None):
            return list(ENGINEERED_COLUMNS)
except ImportError:  # sklearn always present in this project, but stay safe
    EngineeredFeatures = None  # type: ignore

"""Retrieval-augmented grounding for verdicts.

Attaches a cited advisory source to a verdict so it is grounded, not asserted.
Two backends, selected at runtime:

  * Vector search over ChromaDB with sentence-transformers embeddings, if
    those libraries are installed and a collection has been built.
  * A dependency-free keyword-overlap fallback over a small built-in advisory
    corpus, so grounding works on a fresh clone with nothing installed.

The built-in advisories mirror the files in ``backend/rag_corpus`` and are
drawn from public advisories (I4C / RBI / DoT). Keeping a copy in code means
the fallback never depends on the corpus files being present.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from app.schemas.detection import Source

logger = logging.getLogger("kavach.rag")

_CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "rag_corpus")
_CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_store")


@dataclass(frozen=True)
class Advisory:
    title: str
    text: str
    ref: str


# --- Built-in advisory corpus (fallback) -----------------------------------
_ADVISORIES: list[Advisory] = [
    Advisory(
        title="There is no such thing as a 'digital arrest'",
        text=(
            "Police, CBI, ED, customs and TRAI never arrest anyone over a phone "
            "or video call, never keep you on a call for hours, and never ask you "
            "to transfer money to a 'safe account' to prove your innocence. Any "
            "such call is a scam. Disconnect and call 1930."
        ),
        ref="I4C / MHA advisory on digital arrest scams",
    ),
    Advisory(
        title="Agencies do not demand money to drop a case",
        text=(
            "A real investigation is never settled by moving your savings to an "
            "account a caller gives you. Demands for RTGS/UPI transfers, 'security "
            "deposits' or 'bail' over a call are hallmarks of fraud."
        ),
        ref="RBI customer-awareness guidance",
    ),
    Advisory(
        title="Banks never ask for KYC via links or OTPs on a call",
        text=(
            "Your bank will not call or SMS you to 'update KYC' through a link, "
            "nor ask for OTPs, PIN, card numbers or account passwords. Messages "
            "threatening that your account will be blocked today are a scam."
        ),
        ref="RBI / bank KYC-fraud advisory",
    ),
    Advisory(
        title="Guaranteed-return investment and task jobs are traps",
        text=(
            "Offers of guaranteed high returns, paid online 'tasks', or "
            "prepaid-then-refunded jobs are investment scams. Money sent to join "
            "or to 'unlock' earnings is not recoverable."
        ),
        ref="I4C investment-fraud advisory",
    ),
    Advisory(
        title="Isolation is a manipulation tactic — break it",
        text=(
            "Scammers tell victims to stay on the line and tell no one precisely "
            "because a family member would spot the fraud. If a caller forbids you "
            "from talking to anyone, that alone is proof it is a scam. Hang up and "
            "talk to someone you trust."
        ),
        ref="Kavach guardian guidance",
    ),
    Advisory(
        title="Report fraud to 1930 and cybercrime.gov.in",
        text=(
            "If you have been contacted or have lost money, call the cyber-crime "
            "helpline 1930 or file at cybercrime.gov.in immediately. Fast reporting "
            "improves the chance of freezing the transfer."
        ),
        ref="National Cyber Crime Reporting Portal",
    ),
]

_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "is", "are", "you", "your",
    "this", "that", "on", "in", "for", "it", "be", "will", "not", "do",
}


def _tokenise(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS and len(w) > 2
    }


# --- Optional vector backend ------------------------------------------------
_vector_backend: "_ChromaBackend | None" = None
_vector_tried = False


class _ChromaBackend:
    """Lazy ChromaDB + sentence-transformers retrieval, if available."""

    def __init__(self) -> None:
        import chromadb  # type: ignore
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._client = chromadb.PersistentClient(path=os.path.abspath(_CHROMA_DIR))
        self._collection = self._client.get_or_create_collection("kavach_advisories")
        if self._collection.count() == 0:
            self._index_corpus()

    def _index_corpus(self) -> None:
        docs = _load_corpus_documents()
        if not docs:
            docs = [(a.title, a.text, a.ref) for a in _ADVISORIES]
        embeddings = self._embedder.encode([d[1] for d in docs]).tolist()
        self._collection.add(
            ids=[str(i) for i in range(len(docs))],
            documents=[d[1] for d in docs],
            embeddings=embeddings,
            metadatas=[{"title": d[0], "ref": d[2]} for d in docs],
        )

    def retrieve(self, query: str, k: int) -> list[Source]:
        emb = self._embedder.encode([query]).tolist()
        res = self._collection.query(query_embeddings=emb, n_results=k)
        sources: list[Source] = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        for doc, meta in zip(docs, metas):
            sources.append(
                Source(
                    title=str(meta.get("title", "Advisory")),
                    snippet=_snippet(doc),
                    ref=str(meta.get("ref", "")),
                )
            )
        return sources


def _load_corpus_documents() -> list[tuple[str, str, str]]:
    """Load advisory docs from rag_corpus/*.md as (title, text, ref)."""
    docs: list[tuple[str, str, str]] = []
    corpus = os.path.abspath(_CORPUS_DIR)
    if not os.path.isdir(corpus):
        return docs
    for name in sorted(os.listdir(corpus)):
        if not name.endswith((".md", ".txt")):
            continue
        path = os.path.join(corpus, name)
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read().strip()
        except OSError:
            continue
        # First heading/line is the title; a trailing "Source:" line is the ref.
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0].lstrip("# ").strip()
        ref = ""
        body_lines = lines[1:]
        if body_lines and body_lines[-1].lower().startswith("source:"):
            ref = body_lines[-1][len("source:"):].strip()
            body_lines = body_lines[:-1]
        docs.append((title, " ".join(body_lines), ref))
    return docs


def _snippet(text: str, limit: int = 240) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def _get_vector_backend() -> "_ChromaBackend | None":
    global _vector_backend, _vector_tried
    if _vector_tried:
        return _vector_backend
    _vector_tried = True
    try:
        _vector_backend = _ChromaBackend()
        logger.info("RAG: using ChromaDB vector backend.")
    except Exception as exc:
        logger.info("RAG: vector backend unavailable (%s); using keyword fallback.", exc)
        _vector_backend = None
    return _vector_backend


def _keyword_retrieve(query: str, k: int) -> list[Source]:
    """Dependency-free retrieval by token overlap over the built-in corpus."""
    q_tokens = _tokenise(query)
    if not q_tokens:
        return []
    scored: list[tuple[int, Advisory]] = []
    for adv in _ADVISORIES:
        overlap = len(q_tokens & _tokenise(adv.title + " " + adv.text))
        if overlap:
            scored.append((overlap, adv))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        Source(title=adv.title, snippet=_snippet(adv.text), ref=adv.ref)
        for _, adv in scored[:k]
    ]


def retrieve_sources(query: str, k: int = 1) -> list[Source]:
    """Return up to ``k`` cited advisory sources relevant to ``query``."""
    backend = _get_vector_backend()
    if backend is not None:
        try:
            hits = backend.retrieve(query, k)
            if hits:
                return hits
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("RAG vector query failed (%s); falling back.", exc)

    hits = _keyword_retrieve(query, k)
    if hits:
        return hits
    # Always ground a scam-shaped query with the general advisory as a floor.
    return [
        Source(
            title=_ADVISORIES[0].title,
            snippet=_snippet(_ADVISORIES[0].text),
            ref=_ADVISORIES[0].ref,
        )
    ]

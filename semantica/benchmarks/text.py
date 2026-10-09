"""Tiny text helpers shared by the reference systems.

Kept dependency-free on purpose: the point of a benchmark harness is that its
scaffolding does not drag in a tokenizer, a model, or a service.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens."""
    return _TOKEN_RE.findall(str(text).lower())


def split_sentences(text: str) -> List[str]:
    """Split on sentence-final punctuation, dropping empties."""
    return [s.strip() for s in _SENTENCE_RE.split(str(text)) if s.strip()]


def overlap_score(question: str, candidate: str) -> float:
    """Share of the question's distinct content words present in ``candidate``.

    A cheap, deterministic proxy for relevance — good enough to pick the least
    bad sentence out of retrieved passages as an extractive answer.
    """
    q = set(tokenize(question))
    if not q:
        return 0.0
    c = set(tokenize(candidate))
    return len(q & c) / len(q)


def best_sentence(question: str, passages: Sequence[str]) -> str:
    """Return the sentence with the most question overlap, else ``""``.

    This is the default extractive "reader": no model, no labels, just the
    sentence that shares the most words with the question. Every system in the
    harness can fall back to it, which keeps the *retrieval* layer the only
    thing that differs between systems unless a real reader is supplied.
    """
    best, best_score = "", 0.0
    for passage in passages:
        for sentence in split_sentences(passage) or [str(passage)]:
            score = overlap_score(question, sentence)
            if score > best_score:
                best, best_score = sentence, score
    return best


class BM25:
    """Small in-memory BM25 index (k1=1.2, b=0.75).

    Only ever used by the dependency-free reference system; it is not part of
    semantica's production retrieval path.
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._texts: List[str] = []
        self._docs: List[List[str]] = []
        self._df: Counter = Counter()
        self._avgdl: float = 0.0

    def __len__(self) -> int:
        return len(self._docs)

    def add(self, texts: Sequence[str]) -> None:
        for text in texts:
            self._texts.append(str(text))
            tokens = tokenize(text)
            self._docs.append(tokens)
            self._df.update(set(tokens))
        total = sum(len(d) for d in self._docs)
        self._avgdl = (total / len(self._docs)) if self._docs else 0.0

    def clear(self) -> None:
        self._texts.clear()
        self._docs.clear()
        self._df.clear()
        self._avgdl = 0.0

    def _idf(self, term: str) -> float:
        n = len(self._docs)
        df = self._df.get(term, 0)
        return math.log((n - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, top_k: int = 5) -> List[str]:
        """Return the top ``top_k`` documents by BM25 score."""
        if not self._docs:
            return []
        scores: Dict[int, float] = {}
        for term in set(tokenize(query)):
            idf = self._idf(term)
            for index, doc in enumerate(self._docs):
                tf = doc.count(term)
                if not tf:
                    continue
                norm = self.k1 * (1 - self.b + self.b * len(doc) / (self._avgdl or 1))
                numerator = idf * tf * (self.k1 + 1)
                scores[index] = scores.get(index, 0.0) + numerator / (tf + norm)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [self._texts[i] for i, _ in ranked[:top_k]]

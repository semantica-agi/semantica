"""A dependency-free reference system (BM25 retrieval + extractive answer).

This is **not** a memory system and its numbers are not a claim about memory
quality — it is the floor. It exists so that (a) the harness has a system that
always runs, with no API key, no service and no model, and (b) every published
number has a cheap baseline next to it. If a real memory backend cannot beat
BM25-over-the-same-passages on HotPotQA/MuSiQue, that is worth knowing.

``reset`` drops the index, so per-case datasets give it a clean slate while
corpus datasets hand it the whole conversation at once.
"""

from typing import List, Sequence

from ..text import BM25, best_sentence
from .base import register_system


class LexicalMemory:
    """BM25 index over ingested passages, answered extractively."""

    name = "lexical"

    def __init__(self, top_k: int = 5, reader=None):
        self.top_k = int(top_k)
        self._reader = reader
        self._index = BM25()
        self.last_retrieved: List[str] = []

    def reset(self) -> None:
        self._index.clear()
        self.last_retrieved = []

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        texts = [str(p) for p in passages if str(p).strip()]
        if texts:
            self._index.add(texts)

    def answer(self, question: str, *, case_id: str = "") -> str:
        retrieved = self._index.search(question, top_k=self.top_k)
        self.last_retrieved = list(retrieved)
        if not retrieved:
            return ""
        if self._reader is not None:
            return self._reader(question, retrieved)
        return best_sentence(question, retrieved)


register_system("lexical", LexicalMemory)

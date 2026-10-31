"""semantica's own memory layer, adapted to the benchmark protocol.

Wraps :class:`semantica.context.AgentMemory`:

``ingest``  -> ``AgentMemory.store(passage)``
``answer``  -> ``AgentMemory.retrieve(question)`` then read the hits

The read step is pluggable. By default the harness answers *extractively* from
the retrieved passages (see :func:`semantica.benchmarks.text.best_sentence`) so
that every system is compared on the same reader and the only thing that varies
is memory. Pass ``reader=callable(question, passages) -> str`` to plug in an
LLM reader and measure end-to-end QA quality instead.

Configuration is passed straight through, so a caller can hand in a fully built
memory object (``memory=...``) or let the adapter build the default one. The
import of ``AgentMemory`` is deferred to construction time, so importing this
module never pulls the memory stack into a process that only wants to list
systems.
"""

from typing import Any, Dict, List, Optional, Sequence

from ..text import best_sentence
from .base import SystemUnavailable, register_system


class SemanticaMemory:
    """Adapter from ``AgentMemory`` to the harness protocol."""

    name = "semantica"

    def __init__(
        self,
        memory: Optional[Any] = None,
        top_k: int = 5,
        reader=None,
        **memory_options: Any,
    ):
        self.top_k = int(top_k)
        self._reader = reader
        if memory is None:
            try:
                from semantica.context.agent_memory import AgentMemory
            except ImportError as exc:  # pragma: no cover - env dependent
                raise SystemUnavailable(
                    f"semantica memory layer unavailable: {exc}"
                ) from exc
            memory = AgentMemory(**memory_options) if memory_options else AgentMemory()
        self._memory = memory
        self.last_retrieved: List[str] = []

    def reset(self) -> None:
        clear = getattr(self._memory, "clear", None)
        if clear is None:
            raise SystemUnavailable("AgentMemory has no clear(); cannot reset")
        clear()
        self.last_retrieved = []

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        metadata: Optional[Dict[str, Any]] = {"case_id": case_id} if case_id else None
        for passage in passages:
            text = str(passage).strip()
            if text:
                self._memory.store(text, metadata=metadata)

    def answer(self, question: str, *, case_id: str = "") -> str:
        hits: List[Dict[str, Any]] = self._memory.retrieve(
            question, max_results=self.top_k
        )
        passages = [str(hit.get("content", "")) for hit in hits if hit.get("content")]
        self.last_retrieved = list(passages)
        if not passages:
            return ""
        if self._reader is not None:
            return self._reader(question, passages)
        return best_sentence(question, passages)


register_system("semantica", SemanticaMemory)

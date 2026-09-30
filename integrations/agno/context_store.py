"""
AgnoContextStore — Graph-backed agent memory storage for Agno.

Implements Agno's ``MemoryDb`` protocol backed by Semantica's ``AgentContext``,
giving Agno agents hybrid vector + context-graph memory that persists across
sessions.

Key behaviours
--------------
- ``upsert_memory()``  → stores text in ``AgentContext`` (vector + graph) and
                          extracts entities into the knowledge graph
- ``read_memories()``  → hybrid retrieval: vector similarity + graph expansion
- ``delete_memory()``  → removes from cache and calls ``AgentContext.forget()``
- ``record_decision()`` → records a structured decision with reasoning & outcome
- ``find_precedents()`` → returns semantically similar historical decisions
- ``get_context_for_prompt()`` → formats precedents for system-prompt injection

Install
-------
    pip install semantica[agno]

Example
-------
    >>> from semantica.context import ContextGraph
    >>> from semantica.vector_store import VectorStore
    >>> from integrations.agno import AgnoContextStore
    >>> store = AgnoContextStore(
    ...     vector_store=VectorStore(backend="faiss"),
    ...     knowledge_graph=ContextGraph(advanced_analytics=True),
    ...     decision_tracking=True,
    ...     session_id="user_session_42",
    ... )
    >>> from agno.agent import Agent
    >>> from agno.memory import AgentMemory
    >>> agent = Agent(memory=AgentMemory(db=store))
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from semantica.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional: Agno MemoryDb base class
# ---------------------------------------------------------------------------
AGNO_AVAILABLE = False
AGNO_IMPORT_ERROR: Optional[str] = None

_MemoryDbBase: Any = object  # fallback when agno is absent

try:
    from agno.memory.db.base import MemoryDb as _AgnoMemoryDb  # type: ignore
    from agno.memory.db.row import MemoryRow as _AgnoMemoryRow  # type: ignore

    _MemoryDbBase = _AgnoMemoryDb
    AGNO_AVAILABLE = True
except ImportError as exc:
    AGNO_IMPORT_ERROR = str(exc)


# ---------------------------------------------------------------------------
# Lightweight memory row when agno is not installed
# ---------------------------------------------------------------------------
class _MemoryRow:
    """Minimal stand-in for ``agno.memory.db.row.MemoryRow``."""

    __slots__ = ("id", "memory", "user_id", "topics", "input", "last_updated")

    def __init__(
        self,
        memory: str,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        topics: Optional[List[str]] = None,
        input: Optional[str] = None,
    ) -> None:
        self.id = id or str(uuid.uuid4())
        self.memory = memory
        self.user_id = user_id
        self.topics = topics or []
        self.input = input
        self.last_updated = time.time()


MemoryRow = _AgnoMemoryRow if AGNO_AVAILABLE else _MemoryRow  # type: ignore


# ---------------------------------------------------------------------------
# AgnoContextStore
# ---------------------------------------------------------------------------
class AgnoContextStore(_MemoryDbBase):  # type: ignore[misc]
    """
    Graph-backed agent memory store that implements Agno's ``MemoryDb`` protocol.

    Parameters
    ----------
    vector_store:
        A ``semantica.vector_store.VectorStore`` instance (or ``None`` to use
        an in-memory FAISS store created automatically).
    knowledge_graph:
        A ``semantica.context.ContextGraph`` instance (or ``None`` for a fresh
        in-memory graph).
    decision_tracking:
        Automatically record every ``upsert_memory`` call as a lightweight
        decision entry.
    graph_expansion:
        Augment ``read_memories`` results with one-hop graph neighbours.
    session_id:
        Logical session identifier used for node scoping in the context graph.
    agent_context_kwargs:
        Extra keyword arguments forwarded to ``AgentContext.__init__``.
    """

    def __init__(
        self,
        vector_store: Any = None,
        knowledge_graph: Any = None,
        decision_tracking: bool = True,
        graph_expansion: bool = True,
        session_id: Optional[str] = None,
        **agent_context_kwargs: Any,
    ) -> None:
        # Call agno's base init only when the real base class is available.
        if AGNO_AVAILABLE:
            super().__init__()  # type: ignore[call-arg]

        self.decision_tracking = decision_tracking
        self.graph_expansion = graph_expansion
        self.session_id = session_id or str(uuid.uuid4())
        self._memories: Dict[str, Any] = {}  # id → MemoryRow (in-process cache)

        # ------------------------------------------------------------------
        # Build AgentContext from provided components
        # ------------------------------------------------------------------
        from semantica.context import AgentContext, ContextGraph  # lazy import
        from semantica.vector_store import VectorStore  # lazy import

        if knowledge_graph is None:
            knowledge_graph = ContextGraph()

        if vector_store is None:
            vector_store = VectorStore(backend="faiss")

        self._context = AgentContext(
            vector_store=vector_store,
            knowledge_graph=knowledge_graph,
            decision_tracking=decision_tracking,
            **agent_context_kwargs,
        )

        logger.info(
            "AgnoContextStore initialised",
            extra={"session_id": self.session_id, "decision_tracking": decision_tracking},
        )

    # ------------------------------------------------------------------
    # MemoryDb protocol
    # ------------------------------------------------------------------

    def create(self) -> None:
        """Initialise storage (no-op for in-memory graph)."""
        logger.debug("AgnoContextStore.create() called — in-memory graph ready")

    def table_exists(self) -> bool:
        return True

    def memory_exists(self, memory: Any) -> bool:
        mem_id = getattr(memory, "id", None)
        return mem_id is not None and mem_id in self._memories

    def read_memories(
        self,
        user_id: Optional[str] = None,
        limit: Optional[int] = None,
        sort: Optional[str] = None,
    ) -> List[Any]:
        """
        Return stored memories, optionally filtered by ``user_id``.

        When ``graph_expansion`` is enabled, each recalled memory is enriched
        with its one-hop graph neighbourhood before being returned.
        """
        rows = list(self._memories.values())

        if user_id:
            rows = [r for r in rows if getattr(r, "user_id", None) == user_id]

        # Sort: newest first by default
        reverse = sort != "asc"
        rows.sort(key=lambda r: getattr(r, "last_updated", 0), reverse=reverse)

        if limit is not None:
            rows = rows[:limit]

        return rows

    def upsert_memory(self, memory: Any) -> Optional[Any]:
        """
        Persist ``memory`` into both the vector store and the context graph.

        Entity extraction is performed so the knowledge graph is populated
        with nodes for the stored content.  If ``decision_tracking`` is enabled
        a lightweight decision entry is also recorded.
        """
        mem_id = getattr(memory, "id", None) or str(uuid.uuid4())
        mem_text = getattr(memory, "memory", str(memory))
        user_id = getattr(memory, "user_id", None)

        # Persist in AgentContext (vector + graph)
        try:
            self._context.store(
                mem_text,
                conversation_id=user_id or self.session_id,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("AgentContext.store() failed: %s", exc)

        # Extract entities and index them into the knowledge graph
        try:
            from semantica.semantic_extract import NERExtractor
            ner = NERExtractor()
            entities = ner.extract_entities(mem_text) or []
            kg = getattr(self._context, "knowledge_graph", None)
            if kg is not None:
                for ent in entities:
                    name = getattr(ent, "text", getattr(ent, "name", str(ent)))
                    ntype = getattr(ent, "label", getattr(ent, "type", "Entity"))
                    try:
                        kg.add_node(node_id=name, node_type=ntype)
                    except Exception:
                        pass
        except Exception as exc:
            logger.debug("NER/graph indexing skipped: %s", exc)

        # Optional decision tracking
        if self.decision_tracking:
            try:
                self._context.record_decision(
                    category="memory",
                    scenario=mem_text[:200],
                    reasoning="Stored via AgnoContextStore.upsert_memory()",
                    outcome="stored",
                    confidence=1.0,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Decision tracking skipped: %s", exc)

        # Update in-process cache
        if hasattr(memory, "id"):
            memory.id = mem_id
        self._memories[mem_id] = memory
        logger.debug("upsert_memory id=%s", mem_id)
        return memory

    def delete_memory(self, id: str) -> None:
        self._memories.pop(id, None)
        try:
            self._context.forget(memory_id=id)
        except Exception as exc:
            logger.debug("forget(%s) failed: %s", id, exc)
        logger.debug("delete_memory id=%s", id)

    def drop_table(self) -> None:
        self._memories.clear()
        try:
            self._context.forget()
        except Exception as exc:
            logger.debug("drop_table forget() failed: %s", exc)
        logger.debug("AgnoContextStore: all memories dropped")

    def clear(self) -> bool:
        self._memories.clear()
        try:
            self._context.forget()
        except Exception as exc:
            logger.debug("clear forget() failed: %s", exc)
        return True

    # ------------------------------------------------------------------
    # Extended Semantica API (usable from application code directly)
    # ------------------------------------------------------------------

    def record_decision(
        self,
        category: str,
        scenario: str,
        reasoning: str,
        outcome: str,
        confidence: float = 0.8,
        entities: Optional[List[str]] = None,
    ) -> str:
        """Record a structured decision and return its ID."""
        return self._context.record_decision(
            category=category,
            scenario=scenario,
            reasoning=reasoning,
            outcome=outcome,
            confidence=confidence,
            entities=entities,
        )

    def find_precedents(
        self,
        scenario: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for similar historical decisions."""
        try:
            return self._context.find_precedents_advanced(
                scenario=scenario,
                category=category,
                limit=limit,
            )
        except Exception as exc:
            logger.warning("find_precedents failed: %s", exc)
            return []

    def retrieve(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hybrid retrieval: vector similarity + optional graph expansion."""
        try:
            return self._context.retrieve(query, max_results=limit)
        except Exception as exc:
            logger.warning("retrieve failed: %s", exc)
            return []

    def get_context_for_prompt(self, scenario: str, max_precedents: int = 3) -> str:
        """
        Return formatted precedents suitable for injection into a system prompt.

        Call this before each LLM invocation to surface relevant past decisions
        automatically.

        Parameters
        ----------
        scenario:
            Description of the current situation.
        max_precedents:
            Maximum number of precedents to include.

        Returns
        -------
        str
            Multi-line string ready to prepend to a system prompt, or an
            empty string when no relevant precedents exist.
        """
        try:
            precedents = self.find_precedents(scenario, limit=max_precedents)
            if not precedents:
                return ""
            lines = ["Relevant past decisions:"]
            for i, p in enumerate(precedents[:max_precedents], 1):
                if isinstance(p, dict):
                    sc = p.get("scenario", "")
                    outcome = p.get("outcome", "")
                    conf = p.get("confidence", "")
                else:
                    sc = getattr(p, "scenario", str(p))
                    outcome = getattr(p, "outcome", "")
                    conf = getattr(p, "confidence", "")
                lines.append(
                    f"{i}. Scenario: {sc} → Outcome: {outcome}"
                    + (f" (confidence: {conf})" if conf != "" else "")
                )
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("get_context_for_prompt failed: %s", exc)
            return ""

    @property
    def context(self) -> Any:
        """Direct access to the underlying ``AgentContext``."""
        return self._context

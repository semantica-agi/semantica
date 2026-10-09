"""Adapters for third-party memory systems: Mem0, Graphiti (Zep), Cognee.

Each adapter is a thin translation from the vendor's own client to the
:class:`~semantica.benchmarks.systems.base.MemorySystem` protocol. Two rules
shape them:

1. **Nothing is imported until a run selects the system.** The vendors' SDKs are
   optional dependencies, so the import lives inside the factory and a missing
   package surfaces as :class:`SystemUnavailable` rather than an ImportError at
   package import.
2. **A ready client can always be injected** (``client=...``). Hosted graph
   services need credentials and, for Graphiti, a running Neo4j; rather than
   guessing at a connection recipe, the adapter accepts a client the caller has
   already configured, and only tries to build a default when none is given.

Status: these three adapters are **not exercised in CI** — they need network
access, API keys and (Graphiti) a database, none of which a test runner should
assume. They are written against each vendor's documented public API; any run
that uses them prints a reminder that the numbers are only meaningful once the
backend is reachable.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence
from uuid import uuid4

from ..text import best_sentence
from .base import SystemUnavailable, register_system


def _run(coro):
    """Run a coroutine from sync code, refusing to nest inside a live loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise SystemUnavailable(
        "this adapter calls an async client; run the benchmark from sync code "
        "(do not call it from inside an active event loop)"
    )


def _texts_from(results: Any, *keys: str) -> List[str]:
    """Best-effort extraction of answer texts from a vendor's result objects."""
    texts: List[str] = []
    for item in results or []:
        if isinstance(item, str):
            texts.append(item)
            continue
        for key in keys:
            if isinstance(item, dict):
                value = item.get(key)
            else:
                value = getattr(item, key, None)
            if value:
                texts.append(str(value))
                break
        else:
            texts.append(str(item))
    return texts


# --------------------------------------------------------------------------- mem0


class Mem0Memory:
    """Mem0's OSS memory layer (``pip install mem0ai``)."""

    name = "mem0"

    def __init__(
        self,
        client: Optional[Any] = None,
        config: Optional[dict] = None,
        user_id: str = "semantica-bench",
        top_k: int = 5,
        reader=None,
    ):
        self.user_id = user_id
        self.top_k = int(top_k)
        self._reader = reader
        self.last_retrieved: List[str] = []
        if client is None:
            try:
                from mem0 import Memory
            except ImportError as exc:
                raise SystemUnavailable(
                    "mem0 is not installed (pip install mem0ai); mem0 also needs "
                    "an LLM and embedder configured before it can be benchmarked"
                ) from exc
            client = Memory.from_config(config) if config else Memory()
        self._client = client

    def reset(self) -> None:
        self.last_retrieved = []
        reset = getattr(self._client, "reset", None)
        if reset is None:
            raise SystemUnavailable(
                "mem0 client exposes no reset(); cannot isolate runs"
            )
        reset()

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        for passage in passages:
            text = str(passage).strip()
            if text:
                self._client.add(text, user_id=self.user_id)

    def answer(self, question: str, *, case_id: str = "") -> str:
        results = self._client.search(question, user_id=self.user_id, limit=self.top_k)
        passages = _texts_from(results, "memory", "text", "content")
        self.last_retrieved = list(passages)
        if not passages:
            return ""
        if self._reader is not None:
            return self._reader(question, passages)
        return best_sentence(question, passages)


# ------------------------------------------------------------------------ graphiti


class GraphitiMemory:
    """Graphiti / Zep temporal knowledge graph (``pip install graphiti-core``).

    Graphiti has no cheap "wipe everything" call, so runs are isolated by
    ``group_id`` instead: :meth:`reset` rotates to a fresh group. Supply a
    ``client`` you have already pointed at Neo4j (or another supported driver).
    """

    name = "graphiti"

    def __init__(
        self,
        client: Optional[Any] = None,
        top_k: int = 5,
        reader=None,
        group_id: Optional[str] = None,
        **client_options: Any,
    ):
        self.top_k = int(top_k)
        self._reader = reader
        self.last_retrieved: List[str] = []
        self.group_id = group_id or "semantica-bench"
        if client is None:
            if not client_options:
                raise SystemUnavailable(
                    "graphiti needs a configured client (Neo4j or another driver, "
                    "plus LLM credentials). Build one and pass client=..., or pass "
                    "client_options for your setup."
                )
            try:
                from graphiti_core import Graphiti
            except ImportError as exc:
                raise SystemUnavailable(
                    "graphiti-core is not installed (pip install graphiti-core)"
                ) from exc
            client = Graphiti(**client_options)
        self._client = client

    def reset(self) -> None:
        # Rotating the group id is the only isolation Graphiti can offer cheaply;
        # it is also the safest, since it never deletes a user's real graph.
        self.last_retrieved = []
        self.group_id = f"semantica-bench-{uuid4().hex[:8]}"

    def _episode_type(self):
        try:
            from graphiti_core.nodes import EpisodeType

            return EpisodeType.text
        except Exception:  # noqa: BLE001 - version drift between graphiti releases
            return "text"

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        for index, passage in enumerate(passages):
            text = str(passage).strip()
            if not text:
                continue
            _run(
                self._client.add_episode(
                    name=f"{case_id or 'passage'}-{index}",
                    episode_body=text,
                    source=self._episode_type(),
                    source_description="semantica benchmark passage",
                    reference_time=datetime.now(timezone.utc),
                    group_id=self.group_id,
                )
            )

    def answer(self, question: str, *, case_id: str = "") -> str:
        results = _run(
            self._client.search(query=question, group_ids=[self.group_id])
        )
        passages = _texts_from(results, "fact", "content", "name")
        self.last_retrieved = list(passages)
        if not passages:
            return ""
        if self._reader is not None:
            return self._reader(question, passages)
        return best_sentence(question, passages)


# -------------------------------------------------------------------------- cognee


class CogneeMemory:
    """Cognee's memory/graph pipeline (``pip install cognee``)."""

    name = "cognee"

    def __init__(
        self,
        client: Optional[Any] = None,
        top_k: int = 5,
        reader=None,
    ):
        self.top_k = int(top_k)
        self._reader = reader
        self.last_retrieved: List[str] = []
        if client is None:
            try:
                import cognee
            except ImportError as exc:
                raise SystemUnavailable(
                    "cognee is not installed (pip install cognee)"
                ) from exc
            client = cognee
        self._client = client

    def reset(self) -> None:
        """Prune cognee's store, failing loudly if the version has no prune API.

        A silent no-op here would let one dataset's content leak into the next
        and quietly corrupt every number in the run, so an unrecognised prune
        surface is an error rather than a warning.
        """
        self.last_retrieved = []
        prune = getattr(self._client, "prune", None)
        for name in ("prune_all", "prune_data"):
            fn = getattr(prune, name, None)
            if callable(fn):
                _run(fn())
                return
        raise SystemUnavailable(
            "could not find cognee.prune.prune_all/prune_data in this version; "
            "reset cognee manually before benchmarking so runs stay isolated"
        )

    def ingest(self, passages: Sequence[str], *, case_id: str = "") -> None:
        texts = [str(p).strip() for p in passages if str(p).strip()]
        if not texts:
            return
        _run(self._client.add("\n".join(texts)))
        _run(self._client.cognify())

    def answer(self, question: str, *, case_id: str = "") -> str:
        results = _run(self._client.search(question))
        passages = _texts_from(results, "text", "content", "answer")
        self.last_retrieved = list(passages)
        if not passages:
            return ""
        if self._reader is not None:
            return self._reader(question, passages)
        return best_sentence(question, passages)


register_system("mem0", Mem0Memory)
register_system("graphiti", GraphitiMemory)
register_system("cognee", CogneeMemory)

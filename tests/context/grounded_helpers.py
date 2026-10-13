"""Shared construction helpers for grounded context tests."""

from copy import deepcopy

from semantica.context.context_retriever import ContextRetriever
from semantica.context.grounded_context_types import (
    ContextDependencies,
    GroundedArtifact,
)


def artifact(
    view,
    artifact_id="summary-v1",
    *,
    content="A applies to x",
    kind="summary",
    facts=("A(x)",),
    supports=(),
    policy="snapshot",
    citations=(),
):
    """Build a registered-content artifact stamped from ``view``."""

    return GroundedArtifact(
        artifact_id=artifact_id,
        kind=kind,
        content=content,
        dependencies=ContextDependencies(frozenset(facts), frozenset(supports)),
        built_from=view.stamp,
        validity_policy=policy,
        citation_ids=tuple(citations),
    )


def stored_row(record, *, score=0.9):
    """Project an artifact into the row shape used by the vector store."""

    return {
        "id": record.artifact_id,
        "content": record.content,
        "score": score,
        "metadata": {
            "grounded_artifact_id": record.artifact_id,
            "truth_maintenance": {
                "schema_version": 1,
                "session_id": record.built_from.namespace,
                "required_facts": sorted(record.dependencies.required_facts),
                "required_support_ids": sorted(
                    record.dependencies.required_support_ids
                ),
            },
        },
    }


class StaticVectorStore:
    """Minimal in-memory store that records every search call."""

    def __init__(self, rows, on_search=None):
        self.rows = deepcopy(rows)
        self.calls = 0
        self.on_search = on_search

    def search(self, *, query, limit):
        self.calls += 1
        result = deepcopy(self.rows[:limit])
        if self.on_search is not None:
            self.on_search()
        return result


def retriever(rows, on_search=None):
    """Build a local-only ContextRetriever over static rows."""

    return ContextRetriever(
        vector_store=StaticVectorStore(rows, on_search),
        use_graph_expansion=False,
    )

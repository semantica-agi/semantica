"""Cypher causal traversals must use the same vocabulary as ContextGraph.

The in-memory traversal accepts canonical causal types and their present-tense
aliases. The Cypher paths used to interpolate a hardcoded canonical-only list,
so edges written as ``causes``/``supports`` were invisible on external graph
stores even though the same graph traversed them in memory.
"""

import pytest

from semantica.context.causal_analyzer import (
    CausalChainAnalyzer,
    _causal_rel_pattern,
)
from semantica.context.context_graph import _CAUSAL_TRAVERSAL_TYPES


class _QueryCaptureStore:
    """Minimal GraphStore-shaped object that records issued Cypher queries."""

    def __init__(self):
        self.queries = []

    def execute_query(self, query, params=None):
        self.queries.append((query, params or {}))
        return []


def test_cypher_pattern_uses_the_shared_causal_vocabulary():
    for direction, prefix, suffix in (
        ("upstream", "<-[:", "]-"),
        ("downstream", "-[:", "]->"),
    ):
        pattern = _causal_rel_pattern(direction)
        assert pattern.startswith(prefix)
        assert pattern.endswith(suffix)
        for edge_type in _CAUSAL_TRAVERSAL_TYPES:
            assert edge_type in pattern
            assert edge_type.lower() in pattern

    assert _causal_rel_pattern("upstream", rel_var="rel").startswith("<-[rel:")


def test_get_causal_chain_cypher_query_includes_alias_types():
    store = _QueryCaptureStore()
    analyzer = CausalChainAnalyzer(graph_store=store)

    assert analyzer.get_causal_chain("decision_1", "upstream", max_depth=3) == []

    query = store.queries[0][0]
    assert "<-[:" in query
    for edge_type in ("CAUSES", "INFLUENCES", "LEADS_TO", "SUPPORTS"):
        assert edge_type in query
    for edge_type in ("causes", "influences", "leads_to", "supports"):
        assert edge_type in query


def test_trace_at_time_cypher_query_includes_alias_types():
    store = _QueryCaptureStore()
    analyzer = CausalChainAnalyzer(graph_store=store)

    assert analyzer.trace_at_time("decision_1", "2024-01-01T00:00:00") == []

    query, params = store.queries[0]
    assert "<-[rel:" in query
    assert "recorded_at" in query
    assert params["decision_id"] == "decision_1"
    for edge_type in ("CAUSES", "INFLUENCES", "LEADS_TO", "SUPPORTS"):
        assert edge_type in query
    for edge_type in ("causes", "influences", "leads_to", "supports"):
        assert edge_type in query


def test_causal_rel_pattern_rejects_an_unknown_direction():
    """The helper mirrors the two directions the callers validate."""
    with pytest.raises(ValueError, match="upstream.*downstream"):
        _causal_rel_pattern("sideways")

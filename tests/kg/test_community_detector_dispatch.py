"""Regression tests for the CommunityDetector.detect_communities dispatcher.

``label_propagation`` is implemented and reachable through
``detect_communities_label_propagation()``, but the dispatcher never listed it.
``algorithm="label_propagation"`` raised ``ValueError: Unsupported algorithm``,
and ``method="label_propagation"`` matched none of the dispatched names and fell
through to ``"louvain"``, so callers silently got Louvain results back.

Routing it exposed a second problem. Existing callers pass a graph dictionary
(``{"nodes": [...], "edges": [...]}``) and used to land on Louvain, which
normalizes that shape through ``build_adjacency()``. Label propagation resolved
node ids straight off ``graph.nodes``, found none, and the dispatched calls came
back with ``No nodes found matching the specified criteria``.
"""

import pytest

from semantica.context.context_graph import ContextGraph
from semantica.kg.community_detector import CommunityDetector


def _context_graph():
    graph = ContextGraph()
    for node in ("a", "b", "c", "d", "e", "f"):
        graph.add_node(node, "person", node)
    for source, target in (
        ("a", "b"),
        ("b", "c"),
        ("c", "a"),
        ("d", "e"),
        ("e", "f"),
        ("f", "d"),
        ("c", "d"),
    ):
        graph.add_edge(source, target, "knows")
    return graph


def _graph_dict():
    return {
        "nodes": ["a", "b", "c", "d", "e", "f"],
        "edges": [
            ("a", "b"),
            ("b", "c"),
            ("c", "a"),
            ("d", "e"),
            ("e", "f"),
            ("f", "d"),
            ("c", "d"),
        ],
    }


def _spy_on_label_propagation(monkeypatch):
    """Return a detector whose label propagation method records its calls."""
    detector = CommunityDetector()
    calls = []
    original = detector.detect_communities_label_propagation

    def spy(graph, **options):
        calls.append(options)
        return original(graph, **options)

    monkeypatch.setattr(detector, "detect_communities_label_propagation", spy)
    return detector, calls


def test_algorithm_name_reaches_label_propagation(monkeypatch):
    detector, calls = _spy_on_label_propagation(monkeypatch)

    result = detector.detect_communities(
        _context_graph(), algorithm="label_propagation"
    )

    assert calls, "the dispatcher did not call detect_communities_label_propagation"
    assert result["algorithm"] == "label_propagation"


def test_method_alias_reaches_label_propagation(monkeypatch):
    detector, calls = _spy_on_label_propagation(monkeypatch)

    result = detector.detect_communities(_context_graph(), method="label_propagation")

    assert calls, "the method alias fell back to another algorithm"
    # The default algorithm="louvain" must not shadow the requested method.
    assert result["algorithm"] == "label_propagation"
    assert "modularity" not in result


def test_result_is_not_louvain_output():
    result = CommunityDetector().detect_communities(
        _context_graph(), algorithm="label_propagation"
    )

    # Louvain reports modularity and has no iteration count.
    assert set(result) == {"communities", "node_assignments", "algorithm", "iterations"}
    assert "iterations" in result


def test_graph_dict_reaches_label_propagation():
    result = CommunityDetector().detect_communities(
        _graph_dict(), method="label_propagation", random_seed=7
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(result["node_assignments"]) == ["a", "b", "c", "d", "e", "f"]


def test_label_propagation_runs_on_a_context_graph():
    result = CommunityDetector().detect_communities(
        _context_graph(), method="label_propagation", random_seed=7
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(result["node_assignments"]) == ["a", "b", "c", "d", "e", "f"]


def test_other_algorithms_keep_their_dispatch():
    for name in ("louvain", "leiden", "overlapping"):
        result = CommunityDetector().detect_communities(_graph_dict(), method=name)

        assert result["algorithm"] == name


def test_unknown_algorithm_still_raises():
    with pytest.raises(ValueError, match="Unsupported algorithm: nope"):
        CommunityDetector().detect_communities(_graph_dict(), algorithm="nope")


def test_unknown_method_keeps_the_algorithm_argument():
    # An unrecognised alias is ignored instead of being rewritten to Louvain.
    result = CommunityDetector().detect_communities(
        _graph_dict(), algorithm="leiden", method="nope"
    )

    assert result["algorithm"] == "leiden"


def test_graph_dict_keeps_both_cliques_under_a_relationship_filter():
    # A graph dictionary carries no edge types, and Louvain ignores the filter
    # for that shape. Label propagation has to do the same instead of dropping
    # every edge and returning one singleton per node.
    result = CommunityDetector().detect_communities(
        _graph_dict(),
        method="label_propagation",
        relationship_types=["knows"],
        random_seed=7,
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(sorted(c) for c in result["communities"]) == [
        ["a", "b", "c"],
        ["d", "e", "f"],
    ]


def test_graph_dict_works_without_networkx():
    # The graph-dictionary path goes through build_graph_view/build_adjacency
    # rather than a NetworkX rebuild, so it must not need networkx.
    detector = CommunityDetector()
    detector.nx = None
    detector.use_networkx = False

    result = detector.detect_communities(
        _graph_dict(), method="label_propagation", random_seed=7
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(sorted(c) for c in result["communities"]) == [
        ["a", "b", "c"],
        ["d", "e", "f"],
    ]

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

import networkx as nx
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


def test_graph_dict_honours_the_filter_when_its_edges_declare_types():
    # A dictionary edge record may carry its own type. Those records can answer
    # the filter, so the excluded "works_at" edge must not hold the two pairs
    # together.
    graph = {
        "nodes": ["a", "b", "c", "d"],
        "edges": [
            {"source": "a", "target": "b", "type": "knows"},
            {"source": "c", "target": "d", "type": "knows"},
            {"source": "b", "target": "c", "type": "works_at"},
        ],
    }

    result = CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        relationship_types=["knows"],
        random_seed=7,
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(sorted(c) for c in result["communities"]) == [
        ["a", "b"],
        ["c", "d"],
    ]


def test_graph_dict_labels_filter_the_nodes():
    # A graph dictionary carries its node labels on the node records. The
    # filter used to read ``graph.nodes[node]``, an attribute a dict does not
    # have, so every filtered call on a dictionary raised
    # "Community detection failed: 'dict' object has no attribute 'nodes'"
    # instead of matching the requested label.
    graph = {
        "nodes": [
            {"id": "a", "label": "person"},
            {"id": "b", "label": "person"},
            {"id": "c", "label": "company"},
            {"id": "d", "label": "company"},
        ],
        "edges": [("a", "b"), ("c", "d")],
    }

    result = CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        node_labels=["person"],
        random_seed=7,
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(result["node_assignments"]) == ["a", "b"]


def test_graph_dict_entities_are_read_through_the_shared_node_aliases():
    # The same records may sit under "entities" and name their node through
    # "node_id" while typing it through "type". The label lookup has to speak
    # the aliases build_graph_view() already accepts, not just "id"/"label".
    graph = {
        "entities": [
            {"node_id": "a", "type": "person"},
            {"node_id": "b", "type": "person"},
            {"node_id": "c", "type": "company"},
        ],
        "relationships": [("a", "b"), ("a", "c")],
    }

    result = CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        node_labels=["company"],
        random_seed=7,
    )

    assert result["algorithm"] == "label_propagation"
    assert sorted(result["node_assignments"]) == ["c"]


def test_graph_dict_without_labels_still_reports_no_match():
    # Labels are read from the records the dictionary declares. When none of
    # them can be matched, the call keeps reporting the same "no match" it
    # always did rather than failing on the missing ``nodes`` attribute.
    graph = {
        "nodes": ["a", "b"],
        "edges": [("a", "b")],
    }

    with pytest.raises(
        RuntimeError, match="No nodes found matching the specified criteria"
    ):
        CommunityDetector().detect_communities(
            graph,
            method="label_propagation",
            node_labels=["person"],
            random_seed=7,
        )


def test_chunked_label_propagation_reports_the_requested_algorithm():
    # Chunking is an execution detail. A caller that asked for label
    # propagation must get that name back, whatever the graph size.
    nodes = ["n%d" % i for i in range(6)]
    graph = {
        "nodes": nodes,
        "edges": list(zip(nodes, nodes[1:])),
    }

    result = CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        chunk_size=2,
        random_seed=7,
    )

    assert result["algorithm"] == "label_propagation"


def _partition(result):
    return sorted(sorted(community) for community in result["communities"])


def test_chunked_label_propagation_keeps_the_edges_between_chunks():
    # Chunking is an execution detail: an edge that joins two chunks has to
    # still make its two endpoints neighbours. A complete graph is a single
    # community whether it is walked whole or a few nodes at a time.
    graph = nx.complete_graph(6)

    whole = CommunityDetector().detect_communities(
        graph, method="label_propagation", random_seed=7
    )
    chunked = CommunityDetector().detect_communities(
        graph, method="label_propagation", chunk_size=3, random_seed=7
    )

    assert _partition(whole) == [[0, 1, 2, 3, 4, 5]]
    assert _partition(chunked) == _partition(whole)


def test_chunked_adjacency_keeps_a_neighbour_from_another_chunk():
    # A chunk's rows are built against the whole node set, so a neighbour
    # that sits in the next chunk is still returned as a neighbour.
    graph = nx.path_graph(4)
    detector = CommunityDetector()

    chunked = detector._build_filtered_adjacency(
        graph, [0, 1, 2, 3], None, iterate=[0, 1]
    )

    assert sorted(chunked[0]) == [1]
    assert sorted(chunked[1]) == [0, 2]

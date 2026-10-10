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

import logging

import networkx as nx
import pytest

from semantica.context.context_graph import ContextGraph
from semantica.kg import _graph_view, community_detector
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


@pytest.mark.parametrize("method", [["louvain"], {"k": 1}, 0, False, b"louvain"])
def test_non_string_method_is_rejected(method):
    # A non-string alias used to be ignored, or to raise "unhashable type"
    # from the handler lookup. It now gets one clear error naming its type.
    with pytest.raises(TypeError, match="method must be a string or None, got"):
        CommunityDetector().detect_communities(_graph_dict(), method=method)


@pytest.mark.parametrize("algorithm", [["louvain"], None, 0])
def test_non_string_algorithm_is_rejected(algorithm):
    with pytest.raises(TypeError, match="algorithm must be a string, got"):
        CommunityDetector().detect_communities(_graph_dict(), algorithm=algorithm)


def test_label_propagation_ignores_louvain_options_with_a_warning(caplog):
    # Louvain, Leiden and overlapping accept options they do not use. Label
    # propagation now does the same instead of raising "unexpected keyword
    # argument", but says which options it ignored.
    with caplog.at_level(logging.WARNING, logger="semantica.community_detector"):
        result = CommunityDetector().detect_communities(
            _graph_dict(),
            method="label_propagation",
            resolution=1.0,
            max_iter=5,
            random_seed=7,
        )

    assert result["algorithm"] == "label_propagation"
    assert sorted(sorted(c) for c in result["communities"]) == [
        ["a", "b", "c"],
        ["d", "e", "f"],
    ]
    assert any(
        "ignores unsupported options: max_iter, resolution" in record.message
        for record in caplog.records
    )


def test_label_propagation_options_raise_no_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="semantica.community_detector"):
        CommunityDetector().detect_communities(
            _graph_dict(),
            method="label_propagation",
            max_iterations=50,
            random_seed=7,
        )

    assert not any(
        "ignores unsupported options" in record.message for record in caplog.records
    )


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


def test_graph_dict_keeps_an_untyped_edge_beside_typed_ones():
    # Whether an edge is classifiable is decided per edge. One typed record
    # must not turn every untyped edge in the same graph into a dropped link.
    graph = {
        "nodes": ["a", "b", "c", "d", "e"],
        "edges": [
            {"source": "a", "target": "b", "type": "knows"},
            {"source": "b", "target": "c", "type": "works_at"},
            {"source": "c", "target": "d"},
            {"source": "d", "target": "e"},
            {"source": "e", "target": "c"},
        ],
    }

    result = CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        relationship_types=["knows"],
        random_seed=7,
    )

    assert sorted(sorted(c) for c in result["communities"]) == [
        ["a", "b"],
        ["c", "d", "e"],
    ]


def test_graph_dict_filter_reads_the_edge_types_once(monkeypatch):
    # The relationship filter used to rescan every edge record for every
    # neighbour it classified, which made filtering O(E^2). The number of
    # scans must not grow with the graph.
    calls = []
    real = _graph_view._extract_edges

    def counting(graph):
        calls.append(graph)
        return real(graph)

    monkeypatch.setattr(_graph_view, "_extract_edges", counting)

    scans = []
    for n in (10, 40):
        nodes = ["n%d" % i for i in range(n)]
        graph = {
            "nodes": nodes,
            "edges": [
                {"source": a, "target": b, "type": "next"}
                for a, b in zip(nodes, nodes[1:])
            ],
        }
        calls.clear()
        CommunityDetector().detect_communities(
            graph,
            method="label_propagation",
            relationship_types=["next"],
            random_seed=7,
        )
        scans.append(len(calls))

    assert scans[0] == scans[1]


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

    # Louvain also returns one community here and ignores chunk_size, so
    # without this the test would pass even if the call never reached label
    # propagation.
    assert chunked["algorithm"] == "label_propagation"
    assert _partition(whole) == [[0, 1, 2, 3, 4, 5]]
    assert _partition(chunked) == _partition(whole)


def test_chunked_label_propagation_builds_the_adjacency_once(monkeypatch):
    # The chunks only split the label updates. Rebuilding the whole graph's
    # adjacency and edge-type index for every chunk cost O(N / chunk_size)
    # passes over the graph and produced the same rows.
    adjacency_calls = []
    index_calls = []
    real_adjacency = community_detector.build_adjacency
    real_index = community_detector.build_edge_type_index

    def counting_adjacency(graph, directed=False):
        adjacency_calls.append(graph)
        return real_adjacency(graph, directed=directed)

    def counting_index(graph):
        index_calls.append(graph)
        return real_index(graph)

    monkeypatch.setattr(community_detector, "build_adjacency", counting_adjacency)
    monkeypatch.setattr(community_detector, "build_edge_type_index", counting_index)

    nodes = ["n%d" % i for i in range(6)]
    graph = {
        "nodes": nodes,
        "edges": [
            {"source": a, "target": b, "type": "next"}
            for a, b in zip(nodes, nodes[1:])
        ],
    }

    CommunityDetector().detect_communities(
        graph,
        method="label_propagation",
        relationship_types=["next"],
        chunk_size=2,
        random_seed=7,
    )

    assert len(adjacency_calls) == 1
    assert len(index_calls) == 1


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


def test_detect_communities_method_casing_and_separator_variations(monkeypatch):
    """Verify that casing, dashes, and condensed names correctly route without falling back."""
    called_methods = []

    def mock_lp(self, graph, **kwargs):
        called_methods.append("label_propagation")
        return {"communities": []}

    monkeypatch.setattr(CommunityDetector, "detect_communities_label_propagation", mock_lp)

    detector = CommunityDetector()
    graph = nx.path_graph(4)

    # Test all variations mentioned in issue #1925
    variations = ["Label_Propagation", "label-propagation", "labelpropagation", "LABEL_PROPAGATION"]
    for variant in variations:
        called_methods.clear()
        detector.detect_communities(graph, method=variant)
        assert called_methods == ["label_propagation"], f"Failed for method variant: {variant}"


def test_detect_communities_unrecognized_method_logs_warning_and_falls_back(caplog, monkeypatch):
    """Verify that an unrecognized method logs a warning and falls back to running louvain."""
    called = []

    def mock_louvain(self, graph, **kwargs):
        called.append("louvain")
        return {"communities": [[0, 1], [2, 3]]}

    monkeypatch.setattr(CommunityDetector, "detect_communities_louvain", mock_louvain)

    detector = CommunityDetector()
    graph = nx.path_graph(4)

    with caplog.at_level("WARNING"):
        result = detector.detect_communities(graph, method="unknown_typo_method")

    assert called == ["louvain"], "Expected fallback to Louvain algorithm"
    assert "communities" in result
    assert any(
        "Unrecognized community detection method 'unknown_typo_method'" in record.message
        for record in caplog.records
    ), "Expected warning was not logged for unrecognized method"


def test_detect_communities_algorithm_casing_parity(monkeypatch):
    """Verify that algorithm parameter handles casing variations consistently."""
    called_methods = []

    def mock_lp(self, graph, **kwargs):
        called_methods.append("label_propagation")
        return {"communities": []}

    monkeypatch.setattr(CommunityDetector, "detect_communities_label_propagation", mock_lp)

    detector = CommunityDetector()
    graph = nx.path_graph(4)

    detector.detect_communities(graph, algorithm="Label_Propagation")
    assert called_methods == ["label_propagation"]

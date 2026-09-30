"""Regression tests for PageRank node-label filtering on a ContextGraph.

``CentralityCalculator._filter_nodes_by_labels`` called ``graph.nodes()``, the
NetworkX shape, so a ``ContextGraph`` — whose ``nodes`` is a mapping — raised
``TypeError: 'dict' object is not callable``. Fixing the call alone was not
enough: the filter also expected ``graph.nodes[node]`` to be an attribute dict,
while a ContextGraph stores a ``ContextNode`` dataclass, and its fallback branch
then included every node instead of filtering by ``node_type``.
"""

import networkx as nx
import pytest

from semantica.context.context_graph import ContextGraph
from semantica.kg import CentralityCalculator


def _context_graph():
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "person", "Bob")
    graph.add_node("acme", "organization", "Acme")
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("bob", "acme", "works_at")
    return graph


def test_pagerank_runs_on_a_context_graph():
    result = CentralityCalculator().calculate_pagerank(_context_graph())

    assert set(result["centrality"]) == {"alice", "bob", "acme"}


def test_node_labels_restrict_the_context_graph_calculation():
    result = CentralityCalculator().calculate_pagerank(
        _context_graph(), node_labels=["person"]
    )

    assert set(result["centrality"]) == {"alice", "bob"}


def test_node_labels_pick_the_other_type_too():
    result = CentralityCalculator().calculate_pagerank(
        _context_graph(), node_labels=["organization"]
    )

    assert set(result["centrality"]) == {"acme"}


def test_unmatched_node_labels_raise():
    with pytest.raises(RuntimeError, match="No nodes found matching"):
        CentralityCalculator().calculate_pagerank(
            _context_graph(), node_labels=["nowhere"]
        )


def test_filter_reads_context_node_types():
    nodes = CentralityCalculator()._filter_nodes_by_labels(_context_graph(), ["person"])

    assert sorted(nodes) == ["alice", "bob"]


def test_an_untyped_node_is_not_swept_in():
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("ghost", "", "Ghost")

    nodes = CentralityCalculator()._filter_nodes_by_labels(graph, ["person"])

    assert nodes == ["alice"]


def test_filter_returns_every_node_without_labels():
    nodes = CentralityCalculator()._filter_nodes_by_labels(_context_graph(), None)

    assert sorted(nodes) == ["acme", "alice", "bob"]


def test_networkx_node_labels_are_unchanged():
    graph = nx.Graph()
    graph.add_node("alice", label="person")
    graph.add_node("acme", label="organization")
    graph.add_edge("alice", "acme")

    calculator = CentralityCalculator()

    assert set(calculator.calculate_pagerank(graph)["centrality"]) == {
        "alice",
        "acme",
    }
    filtered = calculator.calculate_pagerank(graph, node_labels=["person"])
    assert set(filtered["centrality"]) == {"alice"}


def test_networkx_type_attribute_is_still_read():
    graph = nx.Graph()
    graph.add_node("alice", type="person")
    graph.add_node("acme", type="organization")
    graph.add_edge("alice", "acme")

    filtered = CentralityCalculator().calculate_pagerank(graph, node_labels=["person"])

    assert set(filtered["centrality"]) == {"alice"}


def _parallel_edge_graph():
    """Alice and Bob joined twice, so one of the two types is not the first."""
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "person", "Bob")
    graph.add_node("acme", "organization", "Acme")
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("alice", "bob", "works_with")
    graph.add_edge("bob", "acme", "works_at")
    return graph


def test_relationship_filter_reads_every_parallel_edge():
    """Both types of a pair match, not only the first edge inserted.

    ``ContextGraph.get_edge_data()`` returns the first parallel edge alone, so
    reading the type through it dropped the link whenever the requested type sat
    on the second edge (#1760).
    """
    graph = _parallel_edge_graph()
    calculator = CentralityCalculator()

    assert calculator._get_filtered_neighbors(graph, "alice", ["works_with"]) == ["bob"]
    assert calculator._get_filtered_neighbors(graph, "alice", ["knows"]) == ["bob"]
    assert calculator._get_filtered_neighbors(graph, "alice", ["mentors"]) == []


def test_pagerank_keeps_the_link_the_filter_asked_for():
    graph = _parallel_edge_graph()

    ranked = CentralityCalculator().calculate_pagerank(
        graph, relationship_types=["works_with"]
    )

    # Only alice→bob survives, so bob still receives score from alice. Dropping
    # that link leaves every node on the same base score instead.
    assert ranked["centrality"]["bob"] > ranked["centrality"]["alice"]


def _opposite_direction_graph():
    """Alice links to Bob one way, Bob links back with another type.

    ``ContextGraph._adjacency`` is outgoing-only, so the two edges are two
    separate neighbours in two separate directions, not one symmetric pair.
    """
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "person", "Bob")
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("bob", "alice", "responds_to")
    return graph


def test_relationship_filter_is_direction_aware():
    """A reverse edge of another type never matches the requested type.

    The edge-list lookup used to read the pair symmetrically, so
    ``bob→alice responds_to`` matched ``alice→bob knows`` and Bob kept a link he
    does not follow. On an outgoing adjacency walk only ``alice→bob`` counts.
    """
    graph = _opposite_direction_graph()
    calculator = CentralityCalculator()

    assert calculator._get_filtered_neighbors(graph, "alice", ["knows"]) == ["bob"]
    assert calculator._get_filtered_neighbors(graph, "bob", ["knows"]) == []


def test_pagerank_direction_is_respected_by_relationship_filter():
    graph = _opposite_direction_graph()

    ranked = CentralityCalculator().calculate_pagerank(
        graph, relationship_types=["knows"]
    )

    # Only alice→bob carries "knows", so Bob keeps the score he receives and
    # Alice does not get a phantom link back from Bob's "responds_to" edge.
    assert ranked["centrality"]["bob"] > ranked["centrality"]["alice"]


def _graph_dict():
    """``_context_graph()`` in its plain-dictionary shape."""
    return {
        "entities": [
            {"id": "alice", "type": "person"},
            {"id": "bob", "type": "person"},
            {"id": "acme", "type": "organization"},
        ],
        "relationships": [
            {"source_id": "alice", "target_id": "bob", "type": "knows"},
            {"source_id": "bob", "target_id": "acme", "type": "works_at"},
        ],
    }


def test_pagerank_reads_a_plain_graph_dict():
    """A ``{"entities": ..., "relationships": ...}`` mapping stays a valid input.

    ``graph_node_ids``, ``graph_node_label`` and ``edge_types_between`` only
    understood ``graph.nodes``/``graph.edges``, so the dictionary shape that
    ``build_graph_view`` has always handled raised
    ``RuntimeError: No nodes found matching the specified criteria`` (#1835).
    """
    calculator = CentralityCalculator()

    dict_scores = calculator.calculate_pagerank(_graph_dict())["centrality"]
    context_scores = calculator.calculate_pagerank(_context_graph())["centrality"]

    assert set(dict_scores) == {"alice", "bob", "acme"}
    assert dict_scores == pytest.approx(context_scores)


def test_node_labels_filter_a_plain_graph_dict():
    result = CentralityCalculator().calculate_pagerank(
        _graph_dict(), node_labels=["person"]
    )

    assert set(result["centrality"]) == {"alice", "bob"}


def test_a_dict_entity_without_a_label_is_not_swept_in():
    graph = _graph_dict()
    graph["entities"].append({"id": "ghost"})

    result = CentralityCalculator().calculate_pagerank(graph, node_labels=["person"])

    assert set(result["centrality"]) == {"alice", "bob"}


def test_dict_neighbour_walk_is_direction_aware():
    calculator = CentralityCalculator()

    assert calculator._get_filtered_neighbors(_graph_dict(), "alice", None) == ["bob"]
    assert calculator._get_filtered_neighbors(_graph_dict(), "acme", None) == []


def test_relationship_types_filter_a_plain_graph_dict():
    """The dict's edge types are read, not silently dropped.

    Reading the types through a NetworkX conversion strips them, and every
    neighbour then falls to the same base score — a uniform, plausible-looking
    result instead of the link the filter asked for.
    """
    ranked = CentralityCalculator().calculate_pagerank(
        _graph_dict(), relationship_types=["knows"]
    )

    scores = ranked["centrality"]
    assert scores["bob"] > scores["alice"]
    assert scores["bob"] > scores["acme"]

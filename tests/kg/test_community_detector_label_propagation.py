"""Regression tests for CommunityDetector.detect_communities_label_propagation.

Every call used to raise ``RuntimeError: Community detection failed: 'dict'
object is not callable`` on a ContextGraph, because ``_filter_nodes_by_labels``
took the graph's ``nodes`` mapping for a callable. Fixing that alone was not
enough: the ``node_labels`` filter still returned every node, because a
ContextGraph stores a ``ContextNode`` dataclass in ``nodes`` while the filter
only understood plain dicts.
"""

import networkx as nx

from semantica.context.context_graph import ContextGraph
from semantica.kg.community_detector import CommunityDetector


def _context_graph():
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "org", "Bob")
    graph.add_node("carol", "person", "Carol")
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("bob", "carol", "knows")
    return graph


def test_runs_on_a_context_graph():
    result = CommunityDetector().detect_communities_label_propagation(_context_graph())

    assert set(result) == {"communities", "node_assignments", "algorithm", "iterations"}
    assert set(result["node_assignments"]) == {"alice", "bob", "carol"}
    assert result["algorithm"] == "label_propagation"


def test_filters_by_node_labels_on_a_context_graph():
    detector = CommunityDetector()

    people = detector.detect_communities_label_propagation(
        _context_graph(), node_labels=["person"]
    )
    orgs = detector.detect_communities_label_propagation(
        _context_graph(), node_labels=["org"]
    )

    assert set(people["node_assignments"]) == {"alice", "carol"}
    assert set(orgs["node_assignments"]) == {"bob"}


def test_keeps_networkx_node_labels_behaviour():
    graph = nx.Graph()
    graph.add_node("a", label="person")
    graph.add_node("b", label="org")
    graph.add_edge("a", "b")

    detector = CommunityDetector()

    assert set(
        detector.detect_communities_label_propagation(graph)["node_assignments"]
    ) == {"a", "b"}
    filtered = detector.detect_communities_label_propagation(graph, node_labels=["org"])
    assert set(filtered["node_assignments"]) == {"b"}


def test_runs_on_a_context_graph_with_relationship_types():
    result = CommunityDetector().detect_communities_label_propagation(
        _context_graph(), relationship_types=["knows"]
    )

    assert set(result["node_assignments"]) == {"alice", "bob", "carol"}


def test_relationship_filter_sees_parallel_edges_on_a_context_graph():
    graph = ContextGraph()
    graph.add_node("alice", "person", "Alice")
    graph.add_node("bob", "person", "Bob")
    graph.add_node("carol", "person", "Carol")
    # alice - bob carries two edges. The first one does not match the filter,
    # so a lookup that reads only the first stored edge drops the pair and
    # leaves alice isolated.
    graph.add_edge("alice", "bob", "knows")
    graph.add_edge("alice", "bob", "mentors")
    graph.add_edge("carol", "bob", "knows")

    result = CommunityDetector().detect_communities_label_propagation(
        graph, relationship_types=["mentors"]
    )

    assignments = result["node_assignments"]
    assert assignments["alice"] == assignments["bob"]
    assert assignments["carol"] != assignments["bob"]


def test_relationship_filter_sees_parallel_edges_on_a_multigraph():
    graph = nx.MultiGraph()
    graph.add_node("a", label="person")
    graph.add_node("b", label="person")
    graph.add_node("c", label="person")
    graph.add_edge("a", "b", type="knows")
    graph.add_edge("a", "b", type="mentors")
    graph.add_edge("c", "b", type="knows")

    result = CommunityDetector().detect_communities_label_propagation(
        graph, relationship_types=["mentors"]
    )

    assignments = result["node_assignments"]
    assert assignments["a"] == assignments["b"]
    assert assignments["c"] != assignments["b"]

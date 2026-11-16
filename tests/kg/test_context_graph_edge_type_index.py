"""Relationship filtering on a ContextGraph reads its edge list once.

``edge_types_between`` scanned the whole edge list for every (node, neighbour)
pair it classified, so filtering on ``relationship_types`` was O(E^2) for label
propagation and PageRank on a ContextGraph (#1927).
"""

import pytest

from semantica.context.context_graph import ContextGraph
from semantica.kg import CentralityCalculator
from semantica.kg._graph_view import build_edge_type_index, edge_types_between
from semantica.kg.community_detector import CommunityDetector


class _CountingEdges(list):
    """An edge list that counts how many edges are read from it."""

    reads = 0

    def __iter__(self):
        for edge in super().__iter__():
            self.reads += 1
            yield edge


def _ring(n=40):
    graph = ContextGraph()
    for i in range(n):
        graph.add_node(f"n{i}", "thing")
    for i in range(n):
        graph.add_edge(f"n{i}", f"n{(i + 1) % n}", "next")
    graph.edges = _CountingEdges(graph.edges)
    return graph


def _mixed_graph():
    """Parallel edges of two types, a reverse edge and an unrelated pair."""
    graph = ContextGraph()
    for node in ("a", "b", "c"):
        graph.add_node(node, "thing")
    graph.add_edge("a", "b", "knows")
    graph.add_edge("a", "b", "likes")
    graph.add_edge("b", "a", "follows")
    graph.add_edge("b", "c", "knows")
    return graph


@pytest.mark.parametrize(
    "source, target, directed, expected",
    [
        ("a", "b", True, {"knows", "likes"}),
        ("a", "b", False, {"knows", "likes", "follows"}),
        ("b", "a", True, {"follows"}),
        ("c", "b", True, set()),
        ("c", "b", False, {"knows"}),
        ("a", "c", False, set()),
    ],
)
def test_index_gives_the_per_pair_answers(source, target, directed, expected):
    graph = _mixed_graph()
    index = build_edge_type_index(graph)

    assert index is not None
    assert edge_types_between(graph, source, target, directed, index) == expected
    assert edge_types_between(graph, source, target, directed) == expected


def test_label_propagation_reads_the_edge_list_once():
    graph = _ring()

    result = CommunityDetector().detect_communities_label_propagation(
        graph, relationship_types=["next"], random_seed=0
    )

    assert set(result["node_assignments"]) == set(graph.nodes)
    assert graph.edges.reads < 2 * len(graph.edges)


def test_pagerank_reads_the_edge_list_once():
    graph = _ring()

    scores = CentralityCalculator().calculate_pagerank(
        graph, relationship_types=["next"]
    )["centrality"]

    # Every node of a directed ring has the same rank.
    assert scores == {node: pytest.approx(1 / len(graph.nodes)) for node in graph.nodes}
    assert graph.edges.reads < 2 * len(graph.edges)

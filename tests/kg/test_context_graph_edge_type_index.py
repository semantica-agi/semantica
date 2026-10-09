"""Relationship filtering on a ContextGraph reads its edge list once.

``edge_types_between`` scanned the whole edge list for every (node, neighbour)
pair it classified, so filtering on ``relationship_types`` was O(E^2) for label
propagation and PageRank on a ContextGraph (#1927).
"""

from semantica.context.context_graph import ContextGraph
from semantica.kg import CentralityCalculator
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

    assert set(scores) == set(graph.nodes)
    assert graph.edges.reads < 2 * len(graph.edges)

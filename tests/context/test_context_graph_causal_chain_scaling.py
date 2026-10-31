"""Causal-chain traversal must not rescan the whole edge list per decision.

``ContextGraph.get_causal_chain`` used to loop over ``self.edges`` for every
node it dequeued.  A wide causal graph (one decision with many direct causes
or effects) therefore cost O(V * E); one pass over the edge list is enough.
"""

from types import SimpleNamespace

import pytest

from semantica.context.context_graph import ContextGraph


class _CountingEdgeList(list):
    """A list that records how many times it is fully iterated."""

    def __init__(self, edges):
        super().__init__(edges)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


def _decision(graph: ContextGraph, node_id: str) -> None:
    graph.add_node(
        node_id=node_id,
        node_type="decision",
        content=f"scenario for {node_id}",
        properties={
            "category": "test",
            "scenario": f"scenario for {node_id}",
            "reasoning": "reasoning",
            "outcome": "approved",
            "confidence": 0.9,
        },
    )


def _star_graph(width: int, direction: str) -> ContextGraph:
    """A star with ``width`` spokes around ``root`` in ``direction``."""
    graph = ContextGraph()
    _decision(graph, "root")
    for i in range(width):
        node_id = f"spoke_{i}"
        _decision(graph, node_id)
        if direction == "upstream":
            # spoke -> root, so every spoke is an upstream cause of root.
            graph.add_edge(source_id=node_id, target_id="root", edge_type="CAUSED")
        else:
            # root -> spoke, so every spoke is a downstream effect of root.
            graph.add_edge(source_id="root", target_id=node_id, edge_type="CAUSED")
    return graph


@pytest.mark.parametrize("direction", ["upstream", "downstream"])
def test_causal_chain_does_not_rescan_edges_per_visited_node(direction):
    scans = []
    for width in (10, 40):
        graph = _star_graph(width, direction)
        counted_edges = _CountingEdgeList(graph.edges)
        graph.edges = counted_edges

        chain = graph.get_causal_chain("root", direction=direction, max_depth=5)

        assert {
            decision.decision_id: decision.metadata["causal_distance"]
            for decision in chain
        } == {f"spoke_{i}": 1 for i in range(width)}
        scans.append(counted_edges.iterations)

    # The number of full edge-list scans must not grow with the graph.  Before
    # the fix this was width + 1 (one scan for root and one per spoke).
    assert scans[0] == scans[1]
    assert scans[0] <= 1


def test_unrelated_malformed_edges_do_not_break_causal_chain():
    """A non-string edge type on an unrelated edge must not abort traversal.

    ``edges`` is a public, mutable list.  The old per-node scan only touched
    ``edge_type`` after the endpoint matched, so an unrelated malformed edge
    was tolerated; building the adjacency up front must preserve that.
    """
    graph = _star_graph(3, "upstream")
    graph.edges.append(
        SimpleNamespace(source_id="unrelated", target_id="elsewhere", edge_type=None)
    )
    graph.edges.append(
        SimpleNamespace(source_id="unrelated", target_id="elsewhere", edge_type=42)
    )

    chain = graph.get_causal_chain("root", direction="upstream", max_depth=5)

    assert {decision.decision_id for decision in chain} == {
        "spoke_0",
        "spoke_1",
        "spoke_2",
    }

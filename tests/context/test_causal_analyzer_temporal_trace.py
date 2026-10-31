"""Temporal causal tracing must index time-eligible edges once.

``CausalChainAnalyzer.trace_at_time()`` filtered the causal edge list once and
then scanned that whole list for every visited decision.  A wide temporal
causal graph therefore cost O(V * E).  It also matched only the canonical
uppercase causal types, so edges recorded with the analyzer vocabulary
(``causes``/``influences``) were invisible.
"""

from semantica.context import ContextGraph
from semantica.context.causal_analyzer import CausalChainAnalyzer


class _AccessCountingEdge:
    """Proxy that counts reads of the two endpoint fields."""

    def __init__(self, edge):
        self._edge = edge
        self.source_reads = 0
        self.target_reads = 0

    @property
    def source_id(self):
        self.source_reads += 1
        return self._edge.source_id

    @property
    def target_id(self):
        self.target_reads += 1
        return self._edge.target_id

    def __getattr__(self, name):
        return getattr(self._edge, name)


def _decision(graph: ContextGraph, node_id: str) -> None:
    graph.add_node(
        node_id=node_id,
        node_type="decision",
        content=node_id,
        properties={
            "category": "test",
            "scenario": node_id,
            "reasoning": "reasoning",
            "outcome": "approved",
            "confidence": 0.9,
        },
    )


def _star_graph(width: int) -> ContextGraph:
    graph = ContextGraph()
    _decision(graph, "root")
    for i in range(width):
        node_id = f"spoke_{i}"
        _decision(graph, node_id)
        graph.add_edge(
            source_id=node_id,
            target_id="root",
            edge_type="CAUSED",
            recorded_at="2024-01-01T00:00:00",
        )
        graph.add_edge(
            source_id=node_id,
            target_id=f"spoke_{(i + 1) % width}",
            edge_type="RELATED",
            recorded_at="2024-01-01T00:00:00",
        )
    return graph


def test_trace_at_time_does_not_rescan_eligible_edges_per_visited_decision():
    endpoint_reads = []
    for width in (10, 40):
        graph = _star_graph(width)
        wrappers = [_AccessCountingEdge(edge) for edge in graph.edges]
        graph.edges = wrappers

        chain = CausalChainAnalyzer(graph_store=graph).trace_at_time(
            "root", "2024-02-01T00:00:00", direction="upstream", max_depth=5
        )

        assert {decision.decision_id for decision in chain} == {
            f"spoke_{i}" for i in range(width)
        }
        endpoint_reads.append(
            sum(wrapper.source_reads + wrapper.target_reads for wrapper in wrappers)
        )

    # Before the fix, each visited decision scanned every eligible edge, so
    # endpoint reads grew quadratically with width.  The one-time adjacency
    # build is O(E), so the per-edge read count stays constant.
    assert endpoint_reads[0] * 40 == endpoint_reads[1] * 10


def test_trace_at_time_accepts_alias_causal_edge_types():
    graph = ContextGraph()
    _decision(graph, "cause")
    _decision(graph, "effect")
    graph.add_edge(
        source_id="cause",
        target_id="effect",
        edge_type="causes",
        recorded_at="2024-01-01T00:00:00",
    )

    chain = CausalChainAnalyzer(graph_store=graph).trace_at_time(
        "effect", "2024-02-01T00:00:00", direction="upstream"
    )

    assert [decision.decision_id for decision in chain] == ["cause"]


def test_trace_at_time_still_honours_the_recorded_at_cutoff():
    graph = ContextGraph()
    _decision(graph, "cause")
    _decision(graph, "effect")
    graph.add_edge(
        source_id="cause",
        target_id="effect",
        edge_type="causes",
        recorded_at="2024-02-01T00:00:00",
    )

    analyzer = CausalChainAnalyzer(graph_store=graph)

    assert analyzer.trace_at_time("effect", "2024-01-01T00:00:00") == []
    assert [
        decision.decision_id
        for decision in analyzer.trace_at_time("effect", "2024-03-01T00:00:00")
    ] == ["cause"]

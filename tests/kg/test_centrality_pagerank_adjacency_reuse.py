"""PageRank on a plain graph dictionary builds the adjacency once, not per node.

``_get_filtered_neighbors`` called ``build_adjacency(graph, directed=True)`` for
every node, so neighbour resolution cost O(N * (N + E)) instead of O(N + E).
"""

from semantica.kg import CentralityCalculator, _graph_view, centrality_calculator


def _graph_dict(n=30):
    return {
        "entities": [{"id": f"n{i}", "type": "thing"} for i in range(n)],
        "relationships": [
            {"source": f"n{i}", "target": f"n{(i + 1) % n}", "type": "next"}
            for i in range(n)
        ],
    }


def test_pagerank_builds_the_adjacency_once_for_a_graph_dict(monkeypatch):
    calls = []
    real = centrality_calculator.build_adjacency

    def counting(graph, directed=False):
        calls.append(directed)
        return real(graph, directed=directed)

    monkeypatch.setattr(centrality_calculator, "build_adjacency", counting)

    CentralityCalculator().calculate_pagerank(_graph_dict())

    assert len(calls) == 1


def test_pagerank_reads_a_graph_dicts_edge_types_once(monkeypatch):
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
        calls.clear()
        CentralityCalculator().calculate_pagerank(
            _graph_dict(n), relationship_types=["next"]
        )
        scans.append(len(calls))

    assert scans[0] == scans[1]


def test_pagerank_scores_are_unchanged_by_adjacency_reuse():
    graph = _graph_dict(5)
    graph["relationships"].append({"source": "n0", "target": "n2", "type": "skip"})

    plain = CentralityCalculator().calculate_pagerank(graph)["centrality"]
    typed = CentralityCalculator().calculate_pagerank(
        graph, relationship_types=["next"]
    )["centrality"]

    assert abs(sum(plain.values()) - 1.0) < 1e-6
    assert plain["n2"] > plain["n3"]
    assert set(typed) == set(plain)

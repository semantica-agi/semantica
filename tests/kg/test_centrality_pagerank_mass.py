"""PageRank is a probability distribution: the scores must sum to 1.

Regression tests for #1759. Part of the mass used to be dropped whenever a
column of the transition matrix was left empty, which happens when a node
filter removes every outgoing neighbour of a node, or when a node simply has
no outgoing edge inside the current node set. The scores then drift below 1
and are no longer comparable across runs.
"""

import networkx as nx
import pytest

from semantica.kg import CentralityCalculator


@pytest.fixture
def calculator():
    return CentralityCalculator()


def _scores(result):
    return result["centrality"]


def test_pagerank_sums_to_one_on_a_directed_graph(calculator):
    """A node with no outgoing edge must not swallow its share of the mass."""
    graph = nx.DiGraph([("alice", "acme"), ("bob", "acme"), ("alice", "bob")])

    scores = _scores(calculator.calculate_pagerank(graph))

    assert sum(scores.values()) == pytest.approx(1.0)
    assert scores == pytest.approx(nx.pagerank(graph))


def test_pagerank_keeps_mass_when_node_filter_drops_a_neighbour(calculator):
    """The weight must be spread over the retained neighbours only (#1759)."""
    graph = nx.Graph()
    graph.add_node("alice", label="person")
    graph.add_node("bob", label="person")
    graph.add_node("acme", label="organization")
    graph.add_edge("alice", "bob")
    graph.add_edge("alice", "acme")

    scores = _scores(calculator.calculate_pagerank(graph, node_labels=["person"]))

    assert sum(scores.values()) == pytest.approx(1.0)
    # Dropping a node has to agree with never adding it (#1759, Expected).
    without = nx.Graph([("alice", "bob")])
    assert scores == pytest.approx(nx.pagerank(without))


def test_pagerank_keeps_mass_when_relationship_filter_drops_edges(calculator):
    graph = nx.Graph()
    for name, label in (("alice", "person"), ("bob", "person"), ("acme", "org")):
        graph.add_node(name, label=label)
    graph.add_edge("alice", "acme", type="works_for")
    graph.add_edge("bob", "acme", type="works_for")
    graph.add_edge("alice", "bob", type="knows")

    scores = _scores(calculator.calculate_pagerank(graph, relationship_types=["knows"]))

    assert sum(scores.values()) == pytest.approx(1.0)
    # alice and bob stay symmetric and keep the only retained edge; acme is
    # dangling once the 'works_for' edges are filtered out. Fixed point for
    # the 3-node, d=0.85 walk: alice = bob = 0.4651, acme = 0.0698. Pinning the
    # values (not just the sum) is what catches a wrong-but-normalised result.
    assert scores["alice"] == pytest.approx(scores["bob"])
    assert scores["alice"] == pytest.approx(0.4651, abs=1e-3)
    assert scores["acme"] == pytest.approx(0.0698, abs=1e-3)


@pytest.mark.parametrize("factory", [nx.Graph, nx.DiGraph])
def test_pagerank_matches_networkx(calculator, factory):
    graph = factory([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")])

    # The default cap is 100, but this graph is small and the comparison wants
    # a wide margin over the calculator's own 1e-6 convergence tolerance, so
    # spell the cap out here.
    scores = _scores(calculator.calculate_pagerank(graph, max_iterations=200))

    assert scores == pytest.approx(nx.pagerank(graph), abs=1e-5)


def test_default_iterations_converge_on_a_directed_chain(calculator):
    """A directed graph must settle on the default cap, not just sum to 1.

    Every node but the last has a single successor, so a 10-node chain needs
    ~33 power steps at tolerance=1e-6 -- more than the old default of 20. The
    default is now 100, so the caller gets the fixed point without raising it.
    """
    graph = nx.DiGraph((str(i), str(i + 1)) for i in range(10))

    scores = _scores(calculator.calculate_pagerank(graph))

    assert sum(scores.values()) == pytest.approx(1.0)
    assert scores == pytest.approx(nx.pagerank(graph), abs=1e-5)

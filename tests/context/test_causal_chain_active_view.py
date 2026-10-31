"""The current causal chain must not include retracted or not-yet-valid facts.

Retraction closes a validity window instead of deleting the record, so the
activity-aware views (``state_at()``, ``find_active_nodes()``) hide it while
history remains available. ``get_causal_chain()`` is the current audit view;
before this fix it walked the retained edge/node records as if still active.
"""

from semantica.context import ContextGraph


def _linked_decisions():
    graph = ContextGraph()
    cause = graph.record_decision(
        category="ops",
        scenario="cause",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
    )
    effect = graph.record_decision(
        category="ops",
        scenario="effect",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
    )
    graph.add_causal_relationship(cause, effect, "CAUSED")
    causal_edge = next(edge for edge in graph.edges if edge.edge_type == "CAUSED")
    return graph, cause, effect, causal_edge


def _ids(chain):
    return [decision.decision_id for decision in chain]


def test_retracted_causal_edge_is_not_in_the_current_chain():
    graph, cause, effect, causal_edge = _linked_decisions()
    assert graph.retract_edge(
        causal_edge.edge_id, reason="wrong extraction", at="2024-01-01T00:00:00"
    )

    assert _ids(graph.get_causal_chain(effect, "upstream")) == []
    assert _ids(graph.get_causal_chain(effect, "upstream", include_inactive=True)) == [
        cause
    ]


def test_retracted_cause_node_is_not_in_the_current_chain():
    graph, cause, effect, _ = _linked_decisions()
    # cascade=False keeps the edge active so this isolates the node check.
    assert graph.retract_node(
        cause, reason="superseded", at="2024-01-01T00:00:00", cascade=False
    )

    assert _ids(graph.get_causal_chain(effect, "upstream")) == []
    assert _ids(graph.get_causal_chain(effect, "upstream", include_inactive=True)) == [
        cause
    ]


def test_future_causal_edge_is_not_in_the_current_chain():
    graph = ContextGraph()
    cause = graph.record_decision(
        category="ops",
        scenario="cause",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
    )
    effect = graph.record_decision(
        category="ops",
        scenario="effect",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
    )
    graph.add_edge(cause, effect, "CAUSED", valid_from="2999-01-01T00:00:00")

    assert _ids(graph.get_causal_chain(effect, "upstream")) == []
    assert _ids(graph.get_causal_chain(effect, "upstream", include_inactive=True)) == [
        cause
    ]


def test_both_direction_forwards_include_inactive():
    graph, cause, effect, causal_edge = _linked_decisions()
    graph.retract_edge(
        causal_edge.edge_id, reason="wrong extraction", at="2024-01-01T00:00:00"
    )

    assert _ids(graph.get_causal_chain(effect, "both")) == []
    both = graph.get_causal_chain(effect, "both", include_inactive=True)
    assert _ids(both) == [cause]
    assert both[0].metadata["causal_direction"] == "upstream"


def test_inactive_start_decision_returns_no_current_chain():
    graph, cause, effect, _ = _linked_decisions()
    # Keep the causal edge active; only the requested decision is inactive.
    assert graph.retract_node(
        effect, reason="superseded", at="2024-01-01T00:00:00", cascade=False
    )

    assert _ids(graph.get_causal_chain(effect, "upstream")) == []
    assert _ids(graph.get_causal_chain(effect, "upstream", include_inactive=True)) == [
        cause
    ]


def test_future_start_decision_returns_no_current_chain():
    graph, cause, effect, _ = _linked_decisions()
    graph.nodes[effect].valid_from = "2999-01-01T00:00:00"

    assert _ids(graph.get_causal_chain(effect, "upstream")) == []
    assert _ids(graph.get_causal_chain(effect, "upstream", include_inactive=True)) == [
        cause
    ]

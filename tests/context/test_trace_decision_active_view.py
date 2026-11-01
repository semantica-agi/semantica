"""Decision causality traces must reflect the active graph by default.

Retraction closes a validity window while retaining the record for
``state_at()``/``trace_at_time()``. ``trace_decision_causality()`` used the
retained edge/decision indexes directly, so a current audit trace could still
show a retracted cause. ``include_inactive=True`` keeps the retained-history
view available.
"""

from semantica.context import ContextGraph


def _linked_decisions(entities=None):
    graph = ContextGraph()
    cause = graph.record_decision(
        category="ops",
        scenario="cause",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
        entities=entities,
    )
    effect = graph.record_decision(
        category="ops",
        scenario="effect",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
        entities=entities,
    )
    graph.add_causal_relationship(cause, effect, "CAUSED")
    causal_edge = next(edge for edge in graph.edges if edge.edge_type == "CAUSED")
    return graph, cause, effect, causal_edge


def _hops(chains):
    return [hop for chain in chains for hop in chain["hops"]]


def test_retracted_causal_edge_is_not_in_the_current_trace():
    graph, cause, effect, causal_edge = _linked_decisions()
    graph.retract_edge(
        causal_edge.edge_id, reason="wrong extraction", at="2024-01-01T00:00:00"
    )

    assert graph.trace_decision_chain(effect) == []
    retained = graph.trace_decision_chain(effect, include_inactive=True)
    assert [hop["from"] for hop in _hops(retained)] == [cause]


def test_retracted_cause_node_is_not_in_the_current_trace():
    graph, cause, effect, _ = _linked_decisions()
    graph.retract_node(
        cause, reason="superseded", at="2024-01-01T00:00:00", cascade=False
    )

    assert graph.trace_decision_chain(effect) == []
    retained = graph.trace_decision_chain(effect, include_inactive=True)
    assert [hop["from"] for hop in _hops(retained)] == [cause]


def test_inactive_start_decision_has_no_current_trace():
    graph, cause, effect, _ = _linked_decisions()
    graph.retract_node(
        effect, reason="superseded", at="2024-01-01T00:00:00", cascade=False
    )

    assert graph.trace_decision_causality(effect) == []
    retained = graph.trace_decision_causality(effect, include_inactive=True)
    assert [hop["from"] for hop in _hops(retained)] == [cause]


def test_future_causal_edge_is_not_in_the_current_trace():
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

    assert graph.trace_decision_chain(effect) == []
    retained = graph.trace_decision_chain(effect, include_inactive=True)
    assert [hop["from"] for hop in _hops(retained)] == [cause]


def test_retracted_heuristic_cause_is_not_in_the_current_trace():
    graph = ContextGraph()
    cause = graph.record_decision(
        category="ops",
        scenario="cause",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
        entities=["shared-entity"],
    )
    effect = graph.record_decision(
        category="ops",
        scenario="effect",
        reasoning="reasoning",
        outcome="approved",
        confidence=0.9,
        entities=["shared-entity"],
    )
    # The heuristic only considers an older decision as a potential cause;
    # make the ordering explicit so the same-clock recording is deterministic.
    graph._decisions[cause]["timestamp"] = 1.0
    graph._decisions[effect]["timestamp"] = 2.0
    graph.retract_node(
        cause, reason="superseded", at="2024-01-01T00:00:00", cascade=False
    )

    assert graph.trace_decision_chain(effect) == []
    retained = graph.trace_decision_chain(effect, include_inactive=True)
    assert [hop["from"] for hop in _hops(retained)] == [cause]
    assert all(hop["type"] == "influences" for hop in _hops(retained))

"""Regression tests for issue #1954.

``ContextGraph.add_decision(Decision(...))`` stored a ``Decision`` node but
never registered it in the decision indexes, so precedent search, influence
analysis, causality tracing and insights all behaved as if the decision did
not exist until the graph was round-tripped through ``to_dict``/``from_dict``.
"""

from datetime import datetime, timezone

import pytest

from semantica.context import ContextGraph
from semantica.context.decision_models import Decision

SCENARIO = "extend payment terms for expansion"


def _decision(decision_id="D1", ts=datetime(2026, 4, 1), category="terms"):
    return Decision(
        decision_id=decision_id,
        category=category,
        scenario=SCENARIO,
        reasoning="r",
        outcome="o",
        confidence=1.0,
        timestamp=ts,
        decision_maker="cfo",
    )


def _precedent_ids(graph):
    results = graph.find_precedents_by_scenario(SCENARIO, similarity_threshold=0.0)
    return {r["decision"]["id"] for r in results}


def test_decision_object_visible_to_precedent_search():
    g = ContextGraph()
    g.add_decision(_decision())
    assert "D1" in _precedent_ids(g)


def test_decision_object_counted_by_insights():
    g = ContextGraph()
    g.add_decision(_decision())
    insights = g.get_decision_insights()
    assert insights.get("message") != "No decisions recorded yet"
    assert insights["total_decisions"] == 1


def test_decision_object_accepted_by_influence_and_causality():
    g = ContextGraph()
    g.add_decision(_decision())
    g.analyze_decision_influence("D1")
    g.trace_decision_causality("D1")


def test_decision_object_category_index():
    g = ContextGraph()
    g.add_decision(_decision())
    assert "D1" in g._decision_index["terms"]


def test_iso_timestamps_ordered_in_temporal_index():
    g = ContextGraph()
    g.add_decision(_decision("OLD", ts=datetime(2025, 1, 1)))
    g.add_decision(_decision("NEW", ts=datetime(2026, 1, 1)))
    ordered = [nid for nid, _ in g._temporal_index]
    assert ordered == ["NEW", "OLD"]
    assert all(ts > 0 for _, ts in g._temporal_index)


def test_readding_same_id_does_not_duplicate_index_entries():
    g = ContextGraph()
    g.add_decision(_decision())
    g.add_decision(_decision(category="pricing"))
    assert [nid for nid, _ in g._temporal_index] == ["D1"]
    assert "D1" not in g._decision_index["terms"]
    assert "D1" in g._decision_index["pricing"]


@pytest.mark.parametrize("path", ["object", "kwargs"])
def test_every_public_add_path_is_searchable(path):
    g = ContextGraph()
    if path == "object":
        did = g.add_decision(_decision())
    else:
        did = g.add_decision(
            category="terms", scenario=SCENARIO, reasoning="r",
            outcome="o", confidence=1.0,
        )
    assert did in _precedent_ids(g)


def test_indexes_match_round_trip():
    g = ContextGraph()
    g.add_decision(_decision())
    before = _precedent_ids(g)
    g2 = ContextGraph()
    g2.from_dict(g.to_dict())
    assert before == _precedent_ids(g2)


# --- Review follow-ups -------------------------------------------------------


def test_influence_score_with_two_object_decisions():
    g = ContextGraph()
    g.add_decision(_decision("A", ts=datetime(2026, 4, 1)))
    g.add_decision(_decision("B", ts=datetime(2026, 4, 2)))
    score = g._calculate_decision_influence_score("A", "B")
    assert score["category_score"] == 1.0
    assert score["time_score"] == pytest.approx(1.0 - 1 / 30)
    assert score["score"] > 0


def test_influence_score_with_mixed_add_paths():
    g = ContextGraph()
    g.add_decision(_decision("A", ts=datetime.now()))
    kw_id = g.add_decision(
        category="terms", scenario=SCENARIO, reasoning="r",
        outcome="o", confidence=1.0,
    )
    score = g._calculate_decision_influence_score("A", kw_id)
    assert score["category_score"] == 1.0
    assert score["time_score"] > 0.9


def test_causality_compares_iso_and_epoch_timestamps():
    g = ContextGraph()
    old = _decision("OLD", ts=datetime(2025, 1, 1))
    old.metadata = {"entities": ["acme"]}
    g.add_decision(old)
    new_id = g.add_decision(
        category="terms", scenario=SCENARIO, reasoning="r",
        outcome="o", confidence=1.0, entities=["acme"],
    )
    g.trace_decision_causality(new_id)


def test_metadata_cannot_override_core_fields():
    g = ContextGraph()
    d = _decision()
    d.metadata = {"confidence": "high", "category": ["x"], "note": "kept"}
    g.add_decision(d)
    props = g.nodes["D1"].properties
    assert props["confidence"] == 1.0
    assert props["category"] == "terms"
    assert props["note"] == "kept"
    assert "D1" in g._decision_index["terms"]


def test_invalid_values_rejected_before_graph_mutation():
    g = ContextGraph()
    d = _decision()
    d.metadata = {"entities": [["unhashable"]]}
    with pytest.raises(ValueError):
        g.add_decision(d)
    assert "D1" not in g.nodes
    assert "D1" not in getattr(g, "_decisions", {})

    d = _decision()
    d.category = ["unhashable"]
    with pytest.raises(ValueError):
        g.add_decision(d)
    assert "D1" not in g.nodes


def test_utc_marker_is_timezone_independent():
    utc = ContextGraph._decision_sort_ts("2026-04-01T00:00:00Z")
    offset = ContextGraph._decision_sort_ts("2026-04-01T00:00:00+00:00")
    expected = datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()
    assert utc == offset == expected


def test_agent_context_precedents_with_mixed_add_paths():
    from unittest.mock import Mock

    from semantica.context.agent_context import AgentContext

    g = ContextGraph()
    g.add_decision(_decision("OBJ", ts=datetime(2026, 4, 1)))
    kw_id = g.add_decision(
        category="terms", scenario=SCENARIO, reasoning="r",
        outcome="o", confidence=1.0,
    )
    ctx = AgentContext(
        vector_store=Mock(), knowledge_graph=g, decision_tracking=True
    )
    precedents = ctx.find_precedents(SCENARIO, use_hybrid_search=False)
    by_id = {d.decision_id: d for d in precedents}
    assert set(by_id) == {"OBJ", kw_id}
    assert by_id["OBJ"].timestamp == datetime(2026, 4, 1)
    assert by_id[kw_id].timestamp == datetime.fromtimestamp(
        g._decisions[kw_id]["timestamp"]
    )


def test_utc_marker_kept_on_add_decision_path():
    g = ContextGraph()
    g.add_decision(_decision("Z1", ts="2026-04-01T00:00:00Z"))
    expected = datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp()
    assert g.nodes["Z1"].properties["timestamp"] == "2026-04-01T00:00:00+00:00"
    assert g._temporal_index == [("Z1", expected)]

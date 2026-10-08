"""Regression tests for issue #1954.

``ContextGraph.add_decision(Decision(...))`` stored a ``Decision`` node but
never registered it in the decision indexes, so precedent search, influence
analysis, causality tracing and insights all behaved as if the decision did
not exist until the graph was round-tripped through ``to_dict``/``from_dict``.
"""

from datetime import datetime

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

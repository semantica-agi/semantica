"""Temporal update sequences checked against integer-time selection + full closure.

The oracle never calls production temporal parsers/interval predicates. PR1's
independent inference oracle is tested separately; here a fresh PR1 session
checks that each projected update equals full recomputation for that slice.
"""

import random
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from semantica.reasoning import (
    FactSupport,
    Rule,
    TemporalTruthMaintenanceAdapter,
    TruthMaintenanceSession,
)

EPOCH = datetime(2026, 9, 1, tzinfo=timezone.utc)


def moment(day):
    return EPOCH + timedelta(days=day)


def source_graph(rows):
    return {
        "entities": [
            {"id": "person", "valid_from": moment(0), "valid_until": moment(25)},
            {"id": "org", "recorded_at": moment(0)},
        ],
        "relationships": [
            {
                "source": "person",
                "target": "org",
                "type": "ASSERTS",
                "valid_from": moment(row["start"]),
                "valid_until": moment(row["end"]),
                "recorded_at": moment(row["known"]),
                "superseded_at": (
                    None if row["closed"] is None else moment(row["closed"])
                ),
                "metadata": {
                    "truth_maintenance": {
                        "support_id": row["id"],
                        "fact": row["fact"],
                    }
                },
            }
            for row in rows
        ],
    }


def oracle(rows, rules, valid, known):
    selected = {
        row["id"]: FactSupport(row["id"], row["fact"])
        for row in rows
        if 0 <= valid < 25
        and known >= 0
        and row["start"] <= valid < row["end"]
        and row["known"] <= known
        and (row["closed"] is None or known < row["closed"])
    }
    rebuilt = TruthMaintenanceSession(rules=rules)
    rebuilt.apply(assertions=selected.values())
    return selected, rebuilt


@pytest.mark.parametrize("seed", range(12))
def test_live_and_historical_closures_match_independent_time_selection(seed):
    rng = random.Random(seed)
    rules = [
        Rule("ad", "ad", ["A(?x)"], "D(?x)"),
        Rule("bcd", "bcd", ["B(?x)", "C(?x)"], "D(?x)"),
        Rule("de", "de", ["D(?x)"], "E(?x)"),
    ]
    managed = TemporalTruthMaintenanceAdapter(rules=rules)
    rows = []
    old_supports, old_facts = {}, frozenset()
    version = 0
    for step in range(1, 31):
        # Some transactions close a retained record and introduce a revision;
        # others add independent evidence or only move the live coordinates.
        closable = [
            row for row in rows if row["closed"] is None and row["known"] < step
        ]
        if closable and rng.random() < 0.5:
            rng.choice(closable)["closed"] = step
        if not rows or rng.random() < 0.75:
            start = rng.randrange(0, 23)
            rows.append(
                {
                    "id": f"s{step}",
                    "fact": f"{rng.choice('ABCD')}({rng.choice('xy')})",
                    "start": start,
                    "end": start + rng.randrange(1, 12),
                    "known": step,
                    "closed": None,
                }
            )
        valid = rng.randrange(0, 35)
        source = source_graph(rows)
        unchanged_source = deepcopy(source)
        delta = managed.sync(source, valid_at=moment(valid), known_at=moment(step))
        expected_supports, rebuilt = oracle(rows, rules, valid, step)
        if old_supports != expected_supports:
            version += 1
        assert delta.version == managed.version == version, (seed, step)
        assert managed.facts == rebuilt.facts, (seed, step)
        assert delta.added_facts == rebuilt.facts - old_facts
        assert delta.removed_facts == old_facts - rebuilt.facts
        assert set(delta.added_supports) == set(expected_supports.values()) - set(
            old_supports.values()
        )
        assert set(delta.removed_supports) == set(old_supports.values()) - set(
            expected_supports.values()
        )
        for fact in managed.facts:
            assert managed.explain(fact) == rebuilt.explain(fact)
        assert source == unchanged_source

        historical_valid, historical_known = rng.randrange(0, 35), rng.randrange(
            0, step + 1
        )
        historical = managed.query_at(
            valid_at=moment(historical_valid), known_at=moment(historical_known)
        )
        expected_history, history_rebuilt = oracle(
            rows, rules, historical_valid, historical_known
        )
        assert historical.facts == history_rebuilt.facts
        assert set(historical.active_supports) == set(expected_history.values())
        for fact in historical.facts:
            assert historical.explain(fact) == history_rebuilt.explain(fact)
        assert managed.facts == rebuilt.facts
        assert managed.version == version
        assert managed.valid_at == moment(valid)
        assert managed.known_at == moment(step)
        old_supports, old_facts = expected_supports, rebuilt.facts

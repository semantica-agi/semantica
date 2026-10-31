"""Public checkpoint export and restore tests for TruthMaintenanceSession."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

import semantica
from semantica.reasoning import (
    Derivation,
    FactSupport,
    Rule,
    TruthMaintenanceSession,
    TruthMaintenanceSnapshot,
)
from semantica.utils.exceptions import ProcessingError, ValidationError

CHECKPOINT_V1_JSON = """{
  "format_version": 1,
  "session_version": 4,
  "rules": [
    {
      "rule_id": "employment-eligibility",
      "conditions": ["Employed(?x)"],
      "conclusion": "Eligible(?x)"
    }
  ],
  "support_catalog": [
    {"support_id": "document-v1", "fact": "Employed(Alice)"},
    {"support_id": "document-v2", "fact": "Employed(Alice)"}
  ],
  "active_support_ids": ["document-v2"]
}"""

REPO_ROOT = Path(__file__).resolve().parents[2]

SUBPROCESS_CHILD_CODE = r"""
import json
import os
import sys
from dataclasses import asdict

from semantica.reasoning import FactSupport, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError

ROOT = __ROOT__
import semantica

if not semantica.__file__.startswith(ROOT):
    raise AssertionError(semantica.__file__)

payload = json.load(sys.stdin)
session = TruthMaintenanceSession.from_checkpoint(payload)


def snapshot():
    value = session.snapshot()
    return {
        "version": value.version,
        "facts": sorted(value.facts),
        "active_supports": [asdict(support) for support in value.active_supports],
    }


def explanations():
    return {
        fact: asdict(session.explain(fact))
        for fact in ("Employed(Alice)", "Eligible(Alice)", "Q(a)")
    }


def delta(value):
    return {
        "version": value.version,
        "added_facts": sorted(value.added_facts),
        "removed_facts": sorted(value.removed_facts),
        "added_supports": [asdict(support) for support in value.added_supports],
        "removed_supports": [asdict(support) for support in value.removed_supports],
    }


def rejected(assertion):
    before = snapshot()
    try:
        session.apply(assertions=[FactSupport(*assertion)])
    except ValidationError:
        return {
            "error": "ValidationError",
            "before": before,
            "after": snapshot(),
            "explanations": explanations(),
        }
    raise AssertionError("expected ValidationError")


steps = []
steps.append({"reject-rebind": rejected(("retired", "Q(b)"))})
value = session.apply(assertions=[FactSupport("retired", "Q(a)")])
steps.append({
    "reactivate": {
        "delta": delta(value),
        "state": snapshot(),
        "explanations": explanations(),
    }
})
value = session.apply(retractions=["doc-1"])
steps.append({
    "withdraw-first": {
        "delta": delta(value),
        "state": snapshot(),
        "explanations": explanations(),
    }
})
value = session.apply(retractions=["doc-2"])
steps.append({
    "withdraw-second": {
        "delta": delta(value),
        "state": snapshot(),
        "explanations": explanations(),
    }
})
steps.append({"reject-arity": rejected(("new-id", "Q(a, b)"))})
value = session.apply()
steps.append({
    "noop": {
        "delta": delta(value),
        "state": snapshot(),
        "explanations": explanations(),
    }
})

print(json.dumps({
    "module_path": semantica.__file__,
    "hash_seed": os.environ["PYTHONHASHSEED"],
    "initial": {"state": snapshot(), "explanations": explanations()},
    "steps": steps,
}, sort_keys=True))
""".replace("__ROOT__", repr(str(REPO_ROOT)))

NORMALIZED_CHECKPOINT_V1 = {
    "format_version": 1,
    "session_version": 4,
    "rules": [
        {
            "rule_id": "employment-eligibility",
            "conditions": ["Employed(?x)"],
            "conclusion": "Eligible(?x)",
        }
    ],
    "support_catalog": [
        {"support_id": "document-v1", "fact": "Employed(Alice)"},
        {"support_id": "document-v2", "fact": "Employed(Alice)"},
    ],
    "active_support_ids": ["document-v2"],
}


def checkpoint_payload(rules, catalog, active, session_version):
    return {
        "format_version": 1,
        "session_version": session_version,
        "rules": [
            {
                "rule_id": rule_id,
                "conditions": list(conditions),
                "conclusion": conclusion,
            }
            for rule_id, conditions, conclusion in rules
        ],
        "support_catalog": [
            {"support_id": support_id, "fact": fact}
            for support_id, fact in sorted(catalog.items())
        ],
        "active_support_ids": sorted(active),
    }


def assert_sessions_continue_identically(original, restored, *, operation, facts=()):
    original_delta = operation(original)
    restored_delta = operation(restored)
    assert restored_delta == original_delta
    assert original.snapshot() == restored.snapshot()
    assert original.to_checkpoint() == restored.to_checkpoint()
    for fact in facts:
        assert original.explain(fact) == restored.explain(fact)
    return original_delta


def assert_rejected_without_state_change(original, restored, operation):
    original_before = (
        original.snapshot(),
        original.to_checkpoint(),
        original.version,
    )
    restored_before = (
        restored.snapshot(),
        restored.to_checkpoint(),
        restored.version,
    )
    with pytest.raises(ValidationError):
        operation(original)
    with pytest.raises(ValidationError):
        operation(restored)
    assert (
        original.snapshot(),
        original.to_checkpoint(),
        original.version,
    ) == original_before
    assert (
        restored.snapshot(),
        restored.to_checkpoint(),
        restored.version,
    ) == restored_before


def alternative_derivation_session():
    session = TruthMaintenanceSession(
        rules=[
            Rule("ac", "AC", ["A(?x)"], "C(?x)"),
            Rule("bc", "BC", ["B(?x)"], "C(?x)"),
        ]
    )
    session.apply(
        assertions=[
            FactSupport("a1", "A(a)"),
            FactSupport("a2", "A(b)"),
            FactSupport("b", "B(a)"),
            FactSupport("c", "C(a)"),
        ]
    )
    return session


def compare_withdrawal_order(session, restored, first_source):
    relevant_facts = ("A(a)", "A(b)", "B(a)", "C(a)", "C(b)")
    first_fact = session_snapshot_fact(session, first_source)
    first = assert_sessions_continue_identically(
        session,
        restored,
        operation=lambda item: item.apply(retractions=[first_source]),
        facts=relevant_facts,
    )
    assert first.removed_supports == (FactSupport(first_source, first_fact),)

    second_source = "b" if first_source == "a1" else "a1"
    second_fact = session_snapshot_fact(session, second_source)
    second = assert_sessions_continue_identically(
        session,
        restored,
        operation=lambda item: item.apply(retractions=[second_source]),
        facts=relevant_facts,
    )
    assert second.removed_supports == (FactSupport(second_source, second_fact),)


def session_snapshot_fact(session, support_id):
    for support in session.snapshot().active_supports:
        if support.support_id == support_id:
            return support.fact
    raise AssertionError(f"missing active support {support_id}")


def test_alternative_derivations_and_multiple_matches_survive_restore():
    original_a_first = alternative_derivation_session()
    original_b_first = alternative_derivation_session()
    restored_a_first = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original_a_first.to_checkpoint()))
    )
    restored_b_first = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original_b_first.to_checkpoint()))
    )

    assert original_a_first.explain("C(a)").derivations == (
        Derivation("ac", "C(a)", ("A(a)",), (("?x", "a"),)),
        Derivation("bc", "C(a)", ("B(a)",), (("?x", "a"),)),
    )
    assert original_a_first.explain("C(a)").explicit_support_ids == ("c",)

    compare_withdrawal_order(original_a_first, restored_a_first, "a1")
    compare_withdrawal_order(original_b_first, restored_b_first, "b")

    assert original_a_first.snapshot() == original_b_first.snapshot()
    assert original_a_first.to_checkpoint() == original_b_first.to_checkpoint()


def test_replacement_and_noop_semantics_survive_restore():
    original = TruthMaintenanceSession(rules=[])
    original.apply(assertions=[FactSupport("old", "A(x)")])
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original.to_checkpoint()))
    )

    empty = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(),
        facts=("A(x)",),
    )
    assert empty.version == 1
    assert empty.added_facts == empty.removed_facts == frozenset()

    duplicate = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(
            assertions=[FactSupport("old", "A(x)"), FactSupport("old", "A(x)")]
        ),
        facts=("A(x)",),
    )
    assert duplicate.version == 1

    unknown = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(retractions=["unknown"]),
        facts=("A(x)",),
    )
    assert unknown.version == 1

    retired = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(assertions=[FactSupport("retired", "R(a)")]),
        facts=("A(x)", "R(a)"),
    )
    assert retired.version == 2
    assert retired.added_supports == (FactSupport("retired", "R(a)"),)

    assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(retractions=["retired"]),
        facts=("A(x)", "R(a)"),
    )
    inactive = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(retractions=["retired"]),
        facts=("A(x)",),
    )
    assert inactive.version == 3

    replacement = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(
            assertions=[FactSupport("new", "A(x)")],
            retractions=["old"],
        ),
        facts=("A(x)",),
    )
    assert replacement.version == 4
    assert replacement.added_supports == (FactSupport("new", "A(x)"),)
    assert replacement.removed_supports == (FactSupport("old", "A(x)"),)
    assert original.facts == frozenset({"A(x)"})

    assert_rejected_without_state_change(
        original,
        restored,
        operation=lambda item: item.apply(
            assertions=[FactSupport("new", "A(y)")],
            retractions=["new"],
        ),
    )

    assert_rejected_without_state_change(
        original,
        restored,
        operation=lambda item: item.apply(
            assertions=[
                FactSupport("ghost", "Z(a)"),
                FactSupport("new", "A(y)"),
            ]
        ),
    )
    valid_ghost = assert_sessions_continue_identically(
        original,
        restored,
        operation=lambda item: item.apply(assertions=[FactSupport("ghost", "Z(a, b)")]),
        facts=("A(x)", "Z(a, b)"),
    )
    assert valid_ghost.version == 5
    assert valid_ghost.added_facts == frozenset({"Z(a, b)"})


def test_condition_order_duplicate_conditions_and_whitespace_binding():
    original = TruthMaintenanceSession(
        rules=[
            Rule("ba", "BA", ["B(?x)", "A(?y)"], "C(?x, ?y)"),
            Rule("duplicate", "Duplicate", ["A(?x)", "A(?x)"], "D(?x)"),
        ]
    )
    original.apply(
        assertions=[
            FactSupport("b", "B(w)"),
            FactSupport("a", "A(v)"),
            FactSupport("a-ground", "A(a)"),
        ]
    )
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original.to_checkpoint()))
    )

    assert (
        restored.explain("C(w, v)").derivations
        == original.explain("C(w, v)").derivations
    )
    assert restored.explain("C(w, v)").derivations == (
        Derivation(
            rule_id="ba",
            conclusion="C(w, v)",
            premises=("B(w)", "A(v)"),
            bindings=(("?x", "w"), ("?y", "v")),
        ),
    )
    assert restored.explain("D(a)").derivations == (
        Derivation(
            rule_id="duplicate",
            conclusion="D(a)",
            premises=("A(a)", "A(a)"),
            bindings=(("?x", "a"),),
        ),
    )

    whitespace_session = TruthMaintenanceSession(rules=[])
    whitespace_session.apply(assertions=[FactSupport("source", "A( a )")])
    whitespace_session.apply(retractions=["source"])
    whitespace_restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(whitespace_session.to_checkpoint()))
    )
    delta = whitespace_restored.apply(assertions=[FactSupport("source", "A( a )")])
    assert delta.added_facts == frozenset({"A(a)"})
    assert whitespace_restored.snapshot().active_supports == (
        FactSupport("source", "A(a)"),
    )


def test_restore_preserves_two_source_withdrawals():
    original = TruthMaintenanceSession(
        rules=[Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]
    )
    original.apply(
        assertions=[
            FactSupport("doc-1", "Employed(Alice)"),
            FactSupport("doc-2", "Employed(Alice)"),
        ]
    )
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original.to_checkpoint()))
    )

    assert restored.snapshot() == original.snapshot()
    assert restored.explain("Eligible(Alice)") == original.explain("Eligible(Alice)")
    for source in ("doc-1", "doc-2"):
        assert restored.apply(retractions=[source]) == original.apply(
            retractions=[source]
        )
        assert restored.snapshot() == original.snapshot()
        assert restored.explain("Eligible(Alice)") == original.explain(
            "Eligible(Alice)"
        )
    assert restored.facts == frozenset()


def test_checkpoint_survives_repeated_json_round_trips():
    original = TruthMaintenanceSession(
        rules=[Rule("employment", "Employment", ["Employed(?x)"], "Eligible(?x)")]
    )
    original.apply(
        assertions=[
            FactSupport("doc-1", "Employed(Alice)"),
            FactSupport("doc-2", "Employed(Alice)"),
        ]
    )
    payload = original.to_checkpoint()

    for _ in range(3):
        restored = TruthMaintenanceSession.from_checkpoint(
            json.loads(json.dumps(payload))
        )
        assert restored.snapshot() == original.snapshot()
        assert restored.explain("Eligible(Alice)") == original.explain(
            "Eligible(Alice)"
        )
        assert restored.to_checkpoint() == payload


def test_fixed_v1_fixture_restores_and_reexports_normalized_payload():
    restored = TruthMaintenanceSession.from_checkpoint(json.loads(CHECKPOINT_V1_JSON))

    assert restored.version == 4
    assert restored.snapshot() == TruthMaintenanceSnapshot(
        version=4,
        facts=frozenset({"Employed(Alice)", "Eligible(Alice)"}),
        active_supports=(FactSupport("document-v2", "Employed(Alice)"),),
    )
    assert restored.explain("Eligible(Alice)").derivations == (
        Derivation(
            rule_id="employment-eligibility",
            conclusion="Eligible(Alice)",
            premises=("Employed(Alice)",),
            bindings=(("?x", "Alice"),),
        ),
    )
    assert restored.to_checkpoint() == NORMALIZED_CHECKPOINT_V1


def test_empty_sessions_restore_with_version_zero():
    no_rules = TruthMaintenanceSession.from_checkpoint(
        {
            "format_version": 1,
            "session_version": 0,
            "rules": [],
            "support_catalog": [],
            "active_support_ids": [],
        }
    )
    assert no_rules.snapshot().version == 0
    assert no_rules.facts == frozenset()
    assert no_rules.to_checkpoint() == {
        "format_version": 1,
        "session_version": 0,
        "rules": [],
        "support_catalog": [],
        "active_support_ids": [],
    }

    rules_only = TruthMaintenanceSession.from_checkpoint(
        checkpoint_payload(
            rules=[("ab", ["A(?x)"], "B(?x)")],
            catalog={},
            active=[],
            session_version=0,
        )
    )
    assert rules_only.snapshot().version == 0
    assert rules_only.facts == frozenset()
    assert rules_only.to_checkpoint()["rules"] == [
        {"rule_id": "ab", "conditions": ["A(?x)"], "conclusion": "B(?x)"}
    ]


def test_all_supports_withdrawn_restores_catalog_and_positive_version():
    original = TruthMaintenanceSession(rules=[])
    original.apply(assertions=[FactSupport("retired", "Archived(Alice)")])
    original.apply(retractions=["retired"])
    payload = original.to_checkpoint()

    restored = TruthMaintenanceSession.from_checkpoint(copy.deepcopy(payload))

    assert restored.snapshot() == TruthMaintenanceSnapshot(
        version=2,
        facts=frozenset(),
        active_supports=(),
    )
    assert restored.to_checkpoint() == payload
    assert restored.to_checkpoint()["support_catalog"] == [
        {"support_id": "retired", "fact": "Archived(Alice)"}
    ]


def test_retired_support_binding_and_arity_survive_restore():
    original = TruthMaintenanceSession(rules=[])
    original.apply(assertions=[FactSupport("retired", "Q(a)")])
    original.apply(retractions=["retired"])
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original.to_checkpoint()))
    )

    for invalid_support in (
        FactSupport("retired", "Q(b)"),
        FactSupport("new-id", "Q(a, b)"),
    ):
        with pytest.raises(ValidationError):
            restored.apply(assertions=[invalid_support])

    assert restored.apply(
        assertions=[FactSupport("retired", "Q(a)")]
    ) == original.apply(assertions=[FactSupport("retired", "Q(a)")])
    assert restored.facts == frozenset({"Q(a)"})


def test_zero_arity_predicates_survive_restore():
    original = TruthMaintenanceSession(rules=[Rule("go", "Go", ["Ready()"], "Go()")])
    original.apply(assertions=[FactSupport("ready", "Ready()")])
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(json.dumps(original.to_checkpoint()))
    )

    assert restored.snapshot() == original.snapshot()
    assert restored.explain("Go()") == original.explain("Go()")
    with pytest.raises(ValidationError):
        restored.apply(assertions=[FactSupport("bad", "Go(a)")])
    assert restored.apply(assertions=[FactSupport("go", "Go()")]) == original.apply(
        assertions=[FactSupport("go", "Go()")]
    )


def test_rule_only_predicate_arity_survives_restore_without_catalog_facts():
    original = TruthMaintenanceSession(rules=[Rule("ab", "AB", ["A(?x)"], "B(?x)")])
    restored = TruthMaintenanceSession.from_checkpoint(original.to_checkpoint())

    with pytest.raises(ValidationError):
        restored.apply(assertions=[FactSupport("bad-head", "B(a, b)")])
    with pytest.raises(ValidationError):
        restored.apply(assertions=[FactSupport("bad-body", "A(a, b)")])

    restored.apply(assertions=[FactSupport("source", "A(a)")])
    assert restored.facts == frozenset({"A(a)", "B(a)"})


@pytest.mark.parametrize(
    "payload",
    [
        checkpoint_payload(
            rules=[("bad", ["Not an atom"], "B(?x)")],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[("bad", ["A(?x)"], "Not an atom")],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[],
            catalog={"source": "Not an atom"},
            active=["source"],
            session_version=1,
        ),
        checkpoint_payload(
            rules=[],
            catalog={"source": "A(?x)"},
            active=["source"],
            session_version=1,
        ),
        checkpoint_payload(
            rules=[("unbound", ["A(?x)"], "B(?y)")],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[
                ("ab", ["A(?x)"], "B(?x)"),
                ("ba", ["B(?x)"], "A(?x)"),
            ],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[
                ("ab", ["A(?x)"], "B(?x)"),
                ("bc", ["B(?x)"], "C(?x)"),
                ("ca", ["C(?x)"], "A(?x)"),
            ],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[
                ("a1", ["A(?x)"], "B(?x)"),
                ("a2", ["A(?x, ?y)"], "C(?x, ?y)"),
            ],
            catalog={},
            active=[],
            session_version=0,
        ),
        checkpoint_payload(
            rules=[("ab", ["A(?x)"], "B(?x)")],
            catalog={"active": "A(a)", "inactive": "A(a, b)"},
            active=["active"],
            session_version=1,
        ),
        checkpoint_payload(
            rules=[],
            catalog={},
            active=[],
            session_version=1,
        ),
        checkpoint_payload(
            rules=[],
            catalog={"source": "A(a)"},
            active=[],
            session_version=1,
        ),
    ],
    ids=[
        "invalid-condition",
        "invalid-conclusion",
        "invalid-fact",
        "variable-fact",
        "unbound-head-variable",
        "direct-cycle",
        "indirect-cycle",
        "rule-arity-conflict",
        "inactive-fact-arity-conflict",
        "positive-version-empty-catalog",
        "single-commit-all-supports-inactive",
    ],
)
def test_semantic_rejection_leaves_payload_unchanged(payload):
    before = copy.deepcopy(payload)
    with pytest.raises(ValidationError):
        TruthMaintenanceSession.from_checkpoint(payload)
    assert payload == before


@pytest.mark.parametrize(
    "record",
    [
        lambda payload: payload,
        lambda payload: payload["rules"][0],
        lambda payload: payload["support_catalog"][0],
    ],
    ids=["top-level", "rule-record", "catalog-record"],
)
def test_non_string_field_names_raise_validation_error(record):
    payload = json.loads(CHECKPOINT_V1_JSON)
    record(payload)[42] = "invalid"

    with pytest.raises(ValidationError):
        TruthMaintenanceSession.from_checkpoint(payload)


def test_export_uses_captured_rules_not_caller_rule_mutation():
    caller_rule = Rule("captured", "Captured", ["A(?x)"], "B(?x)")
    session = TruthMaintenanceSession(rules=[caller_rule])

    caller_rule.rule_id = "mutated-id"
    caller_rule.name = "Mutated"
    caller_rule.conditions = ["Changed(?x)"]
    caller_rule.conclusion = "Changed(?x)"

    payload = session.to_checkpoint()
    assert payload["rules"] == [
        {"rule_id": "captured", "conditions": ["A(?x)"], "conclusion": "B(?x)"}
    ]

    restored = TruthMaintenanceSession.from_checkpoint(payload)
    restored.apply(assertions=[FactSupport("source", "A(a)")])
    assert restored.facts == frozenset({"A(a)", "B(a)"})


def test_payload_and_restored_session_are_isolated_in_both_directions():
    original = TruthMaintenanceSession(rules=[Rule("ab", "AB", ["A(?x)"], "B(?x)")])
    original.apply(assertions=[FactSupport("source", "A(a)")])
    expected_payload = original.to_checkpoint()
    before_snapshot = original.snapshot()
    payload = copy.deepcopy(expected_payload)
    restored = TruthMaintenanceSession.from_checkpoint(payload)

    payload["rules"][0]["rule_id"] = "mutated"
    payload["rules"][0]["conditions"].append("Injected(?x)")
    payload["support_catalog"][0]["fact"] = "Injected(a)"
    payload["active_support_ids"].append("source")

    assert original.to_checkpoint() == expected_payload
    assert original.snapshot() == before_snapshot
    assert restored.to_checkpoint() == expected_payload
    assert restored.snapshot() == before_snapshot

    restored.apply(assertions=[FactSupport("second", "A(b)")])
    assert payload == {
        "format_version": 1,
        "session_version": 1,
        "rules": [
            {
                "rule_id": "mutated",
                "conditions": ["A(?x)", "Injected(?x)"],
                "conclusion": "B(?x)",
            }
        ],
        "support_catalog": [
            {"support_id": "source", "fact": "Injected(a)"},
        ],
        "active_support_ids": ["source", "source"],
    }


def test_matcher_failure_is_wrapped_without_mutating_input_or_source(
    monkeypatch,
):
    original = TruthMaintenanceSession(rules=[Rule("ab", "AB", ["A(?x)"], "B(?x)")])
    original.apply(assertions=[FactSupport("source", "A(a)")])
    before_snapshot = original.snapshot()
    payload = original.to_checkpoint()
    before_payload = copy.deepcopy(payload)

    def fail_matcher(*args, **kwargs):
        raise RuntimeError("matcher unavailable")

    monkeypatch.setattr(TruthMaintenanceSession, "_match_rule", fail_matcher)

    assert original.to_checkpoint() == before_payload
    with pytest.raises(ProcessingError) as error:
        TruthMaintenanceSession.from_checkpoint(copy.deepcopy(payload))

    assert isinstance(error.value.__cause__, RuntimeError)
    assert str(error.value.__cause__) == "matcher unavailable"
    assert original.to_checkpoint() == before_payload
    assert original.snapshot() == before_snapshot
    assert payload == before_payload

    monkeypatch.undo()
    restored = TruthMaintenanceSession.from_checkpoint(payload)
    assert restored.snapshot() == before_snapshot


def test_payload_nested_modification_never_reaches_sessions_after_apply():
    original = TruthMaintenanceSession(rules=[Rule("ab", "AB", ["A(?x)"], "B(?x)")])
    original.apply(assertions=[FactSupport("source", "A(a)")])
    expected_payload = original.to_checkpoint()
    payload = copy.deepcopy(expected_payload)
    restored = TruthMaintenanceSession.from_checkpoint(payload)

    payload["rules"][0]["rule_id"] = "mutated"
    payload["rules"][0]["conditions"].append("Injected(?x)")
    payload["support_catalog"][0]["fact"] = "Injected(a)"
    payload["active_support_ids"].append("source")

    original_delta = original.apply(assertions=[FactSupport("second", "A(b)")])
    restored_delta = restored.apply(assertions=[FactSupport("second", "A(b)")])
    assert original_delta == restored_delta
    assert original.to_checkpoint()["rules"] == expected_payload["rules"]
    assert restored.to_checkpoint()["rules"] == expected_payload["rules"]
    assert payload == {
        "format_version": 1,
        "session_version": 1,
        "rules": [
            {
                "rule_id": "mutated",
                "conditions": ["A(?x)", "Injected(?x)"],
                "conclusion": "B(?x)",
            }
        ],
        "support_catalog": [
            {"support_id": "source", "fact": "Injected(a)"},
        ],
        "active_support_ids": ["source", "source"],
    }


def test_checkpoint_continues_in_a_fresh_process():
    original = TruthMaintenanceSession(
        rules=[Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")]
    )
    original.apply(
        assertions=[
            FactSupport("doc-1", "Employed(Alice)"),
            FactSupport("doc-2", "Employed(Alice)"),
        ]
    )
    original.apply(assertions=[FactSupport("retired", "Q(a)")])
    original.apply(retractions=["retired"])
    payload = original.to_checkpoint()

    def snapshot(session):
        value = session.snapshot()
        return {
            "version": value.version,
            "facts": sorted(value.facts),
            "active_supports": [asdict(support) for support in value.active_supports],
        }

    def explanations(session):
        return {
            fact: asdict(session.explain(fact))
            for fact in ("Employed(Alice)", "Eligible(Alice)", "Q(a)")
        }

    def delta(value):
        return {
            "version": value.version,
            "added_facts": sorted(value.added_facts),
            "removed_facts": sorted(value.removed_facts),
            "added_supports": [asdict(support) for support in value.added_supports],
            "removed_supports": [asdict(support) for support in value.removed_supports],
        }

    def rejected(session, support_id, fact):
        before = snapshot(session)
        with pytest.raises(ValidationError):
            session.apply(assertions=[FactSupport(support_id, fact)])
        return {
            "error": "ValidationError",
            "before": before,
            "after": snapshot(session),
            "explanations": explanations(session),
        }

    def expected_output():
        steps = [{"reject-rebind": rejected(original, "retired", "Q(b)")}]
        value = original.apply(assertions=[FactSupport("retired", "Q(a)")])
        steps.append(
            {
                "reactivate": {
                    "delta": delta(value),
                    "state": snapshot(original),
                    "explanations": explanations(original),
                }
            }
        )
        value = original.apply(retractions=["doc-1"])
        steps.append(
            {
                "withdraw-first": {
                    "delta": delta(value),
                    "state": snapshot(original),
                    "explanations": explanations(original),
                }
            }
        )
        value = original.apply(retractions=["doc-2"])
        steps.append(
            {
                "withdraw-second": {
                    "delta": delta(value),
                    "state": snapshot(original),
                    "explanations": explanations(original),
                }
            }
        )
        steps.append({"reject-arity": rejected(original, "new-id", "Q(a, b)")})
        value = original.apply()
        steps.append(
            {
                "noop": {
                    "delta": delta(value),
                    "state": snapshot(original),
                    "explanations": explanations(original),
                }
            }
        )
        return {
            "module_path": semantica.__file__,
            "hash_seed": "17",
            "initial": {
                "state": snapshot(original),
                "explanations": explanations(original),
            },
            "steps": steps,
        }

    expected = expected_output()
    env = dict(os.environ, PYTHONHASHSEED="17", PYTHONPATH=str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", SUBPROCESS_CHILD_CODE],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
        cwd=REPO_ROOT,
        env=env,
    )
    child = json.loads(result.stdout)
    assert child == json.loads(json.dumps(expected))

"""Public behavior tests for TruthMaintenanceSession (PR1 Task 2).

Covers the acceptance scenarios from the implementation plan: multi-support
retraction, alternative derivations, net replacement, explicit vs derived
support, cycle rejection, atomic failed batches, and the full input
validation matrix.
"""

from typing import FrozenSet, get_type_hints

import pytest

from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError


def rule(rid, conditions, conclusion):
    return Rule(rid, rid, conditions, conclusion)


def test_chain_retraction():
    session = TruthMaintenanceSession(rules=[
        rule("ab", ["A(?x)"], "B(?x)"),
        rule("bc", ["B(?x)"], "C(?x)"),
    ])
    session.apply(assertions=[FactSupport("s1", "A(a)")])
    assert session.facts == frozenset({"A(a)", "B(a)", "C(a)"})
    delta = session.apply(retractions=["s1"])
    assert delta.removed_facts == frozenset({"A(a)", "B(a)", "C(a)"})
    assert not session.facts


def test_alternative_derivation_is_retained():
    session = TruthMaintenanceSession(rules=[
        rule("ac", ["A(?x)"], "C(?x)"),
        rule("bc", ["B(?x)"], "C(?x)"),
    ])
    session.apply(assertions=[FactSupport("a", "A(x)")])
    session.apply(assertions=[FactSupport("b", "B(x)")])
    assert len(session.explain("C(x)").derivations) == 2
    session.apply(retractions=["a"])
    assert session.facts == frozenset({"B(x)", "C(x)"})
    assert len(session.explain("C(x)").derivations) == 1
    session.apply(retractions=["b"])
    assert not session.facts


def test_multi_source_and_net_replacement():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("v1", "A(x)")])
    old = session.version
    delta = session.apply(
        assertions=[FactSupport("v2", "A(x)")], retractions=["v1"],
    )
    assert delta.version == old + 1
    assert not delta.added_facts and not delta.removed_facts
    assert delta.removed_supports == (FactSupport("v1", "A(x)"),)
    assert delta.added_supports == (FactSupport("v2", "A(x)"),)
    session.apply(assertions=[FactSupport("v3", "A(x)")])
    session.apply(retractions=["v2"])
    assert session.explain("A(x)").explicit_support_ids == ("v3",)
    assert "B(x)" in session.facts


def test_explicit_and_derived_support():
    session = TruthMaintenanceSession(rules=[rule("ac", ["A(?x)"], "C(?x)")])
    session.apply(assertions=[FactSupport("a", "A(x)"), FactSupport("c", "C(x)")])
    session.apply(retractions=["a"])
    assert session.facts == frozenset({"C(x)"})
    session.apply(retractions=["c"])
    assert not session.facts


def test_unsupported_cycle_rejected():
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            rule("ab", ["A(?x)"], "B(?x)"),
            rule("ba", ["B(?x)"], "A(?x)"),
        ])


def test_failed_batch_is_atomic():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(x)")])
    before = (session.version, session.facts, session.explain("B(x)"))
    with pytest.raises(ValidationError):
        session.apply(assertions=[
            FactSupport("new", "A(y)"), FactSupport("s", "A(z)"),
        ])
    assert (session.version, session.facts, session.explain("B(x)")) == before
    # A failed batch must not reserve the new support ID in the catalog.
    session.apply(assertions=[FactSupport("new", "A(z)")])
    assert "B(z)" in session.facts


# ---------------------------------------------------------------------------
# Validation matrix
# ---------------------------------------------------------------------------


def test_whitespace_normalization():
    session = TruthMaintenanceSession(
        rules=[rule("ab", ["A(?x, ?y)"], "B(?x, ?y)")]
    )
    session.apply(assertions=[FactSupport("s", "A( a , b )")])
    assert session.facts == frozenset({"A(a, b)", "B(a, b)"})


def test_zero_arity_facts():
    session = TruthMaintenanceSession(rules=[
        rule("rg", ["Ready()"], "Go()"),
    ])
    session.apply(assertions=[FactSupport("r", "Ready()"), FactSupport("g", "Go()")])
    assert session.facts == frozenset({"Ready()", "Go()"})


def test_repeated_variable_requires_equal_values():
    session = TruthMaintenanceSession(rules=[
        rule("p", ["Pair(?x, ?x)"], "Same(?x)"),
    ])
    session.apply(assertions=[FactSupport("s", "Pair(a, b)")])
    assert session.facts == frozenset({"Pair(a, b)"})
    session.apply(assertions=[FactSupport("t", "Pair(c, c)")])
    assert session.facts == frozenset({"Pair(a, b)", "Pair(c, c)", "Same(c)"})


def test_duplicate_premise_rule_single_derivation():
    session = TruthMaintenanceSession(rules=[
        rule("r", ["A(?x)", "A(?x)"], "B(?x)"),
    ])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    assert len(session.explain("B(a)").derivations) == 1
    session.apply(retractions=["s"])
    assert not session.facts


def test_two_premise_matches_keep_both_derivations():
    session = TruthMaintenanceSession(rules=[
        rule("r", ["A(?x, ?y)"], "B(?x)"),
    ])
    session.apply(assertions=[
        FactSupport("s1", "A(a, b)"),
        FactSupport("s2", "A(a, c)"),
    ])
    assert len(session.explain("B(a)").derivations) == 2
    session.apply(retractions=["s1"])
    assert "B(a)" in session.facts
    assert len(session.explain("B(a)").derivations) == 1


def test_head_variable_must_be_bound():
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[rule("r", ["A(?x)"], "B(?y)")])


def test_fixed_arity():
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            rule("r1", ["A(?x)"], "B(?x)"),
            rule("r2", ["A(?x, ?y)"], "C(?x)"),
        ])
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    with pytest.raises(ValidationError):
        session.apply(assertions=[FactSupport("t", "A(a, b)")])


def test_asserted_predicate_arity_persists_across_batches():
    # Predicates first introduced by an assertion must keep that arity for
    # the session lifetime; a later batch cannot widen or narrow it.
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "Q(alice)")])
    with pytest.raises(ValidationError):
        session.apply(assertions=[FactSupport("s2", "Q(alice, bob)")])
    # Same-arity re-assertion of the already-registered predicate is fine.
    session.apply(assertions=[FactSupport("s3", "Q(bob)")])
    assert session.facts == frozenset({"Q(alice)", "Q(bob)"})


def test_rule_feature_restrictions():
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            Rule("r", "r", ["A(?x)"], "B(?x)", rule_type=__import__(
                "semantica.reasoning", fromlist=["RuleType"]
            ).RuleType.EQUIVALENCE),
        ])
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            Rule("r", "r", ["A(?x)"], "B(?x)", confidence=0.5),
        ])
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            Rule("r", "r", ["A(?x)"], "B(?x)", handler=lambda x: x),
        ])
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            Rule("r", "r", ["A(?x)"], "B(?x)", actions=[object()]),
        ])


def test_rule_snapshot_is_isolated_from_mutation():
    r = rule("ab", ["A(?x)"], "B(?x)")
    session = TruthMaintenanceSession(rules=[r])
    r.conditions.append("ZZZ(?x)")
    r.conclusion = "Hacked(?x)"
    session.apply(assertions=[FactSupport("s", "A(a)")])
    assert session.facts == frozenset({"A(a)", "B(a)"})


def test_returned_snapshots_are_immutable():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    delta = session.apply(assertions=[FactSupport("s", "A(a)")])
    facts = session.facts
    explanation = session.explain("A(a)")
    session.apply(retractions=["s"])
    assert facts == frozenset({"A(a)", "B(a)"})
    assert explanation.explicit_support_ids == ("s",)
    assert delta.added_facts == frozenset({"A(a)", "B(a)"})


def test_duplicate_noop_batches():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    version = session.version
    delta = session.apply(assertions=[FactSupport("s", "A(a)")])
    assert delta.version == version
    assert not delta.added_facts and not delta.removed_facts
    assert not delta.added_supports and not delta.removed_supports
    delta = session.apply(retractions=["unknown-id"])
    assert delta.version == version
    assert not delta.removed_facts
    delta = session.apply()
    assert delta.version == version


def test_duplicate_retraction_ids_are_idempotent():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    delta = session.apply(retractions=["s", "s"])
    assert delta.removed_facts == frozenset({"A(a)", "B(a)"})
    assert delta.removed_supports == (FactSupport("s", "A(a)"),)
    assert not session.facts


def test_duplicate_retraction_with_mixed_ids():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s1", "A(a)"), FactSupport("s2", "A(b)")])
    session.apply(retractions=["s2", "s1", "s2", "unknown-id"])
    assert session.facts == frozenset()


def test_facts_annotation_resolvable_at_runtime():
    hints = get_type_hints(TruthMaintenanceSession.facts.fget)
    assert hints["return"] == FrozenSet[str]


def test_retracted_id_can_reassert_same_fact_only():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    session.apply(retractions=["s"])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    assert session.facts == frozenset({"A(a)", "B(a)"})
    session.apply(retractions=["s"])
    with pytest.raises(ValidationError):
        session.apply(assertions=[FactSupport("s", "A(b)")])


def test_same_id_in_assertions_and_retractions():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("s", "A(a)")])
    before = (session.version, session.facts)
    with pytest.raises(ValidationError):
        session.apply(
            assertions=[FactSupport("s", "A(a)")], retractions=["s"],
        )
    assert (session.version, session.facts) == before


def test_generator_inputs():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    gen = (FactSupport(f"s{i}", f"A(c{i})") for i in range(3))
    session.apply(assertions=gen)
    assert session.facts == frozenset(
        {"A(c0)", "A(c1)", "A(c2)", "B(c0)", "B(c1)", "B(c2)"}
    )
    session.apply(retractions=iter(["s0", "s1"]))
    assert "B(c0)" not in session.facts
    assert "B(c2)" in session.facts


def test_string_iterable_rejected():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    with pytest.raises(ValidationError):
        session.apply(assertions="abc")
    with pytest.raises(ValidationError):
        session.apply(retractions="abc")


# ---------------------------------------------------------------------------
# Syntax validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_fact", [
    "A",                 # not an atom
    'P("Alice Smith")',  # quoted constant
    "P(f(a))",           # nested term
    "P(?x)",             # variable as fact argument
    "P(a,)",             # trailing comma
    "P(,a)",             # leading comma
    "P(a,,b)",           # empty argument
    "1P(a)",             # identifier must start with letter/underscore
    "P(a b)",            # whitespace inside constant
])
def test_invalid_fact_syntax_rejected(bad_fact):
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    with pytest.raises(ValidationError):
        session.apply(assertions=[FactSupport("s", bad_fact)])


@pytest.mark.parametrize("bad_rule", [
    (["A(?x)"], "B"),            # head not an atom
    (["A(?x)"], "B(?x)(?y)"),    # malformed head
    ([], "B(?x)"),               # empty body
])
def test_invalid_rule_syntax_rejected(bad_rule):
    conditions, conclusion = bad_rule
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[rule("r", conditions, conclusion)])


def test_duplicate_rule_id_rejected():
    with pytest.raises(ValidationError):
        TruthMaintenanceSession(rules=[
            rule("r", ["A(?x)"], "B(?x)"),
            rule("r", ["A(?x)"], "C(?x)"),
        ])


def test_explain_unknown_fact():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    explanation = session.explain("Unknown(a)")
    assert explanation.active is False
    assert explanation.explicit_support_ids == ()
    assert explanation.derivations == ()


def test_initial_session_state():
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    assert session.version == 0
    assert session.facts == frozenset()


def test_bindings_sorted_and_premises_ordered():
    session = TruthMaintenanceSession(rules=[
        rule("r", ["A(?y)", "B(?x)"], "C(?x, ?y)"),
    ])
    session.apply(assertions=[
        FactSupport("a1", "A(v)"), FactSupport("b1", "B(w)"),
    ])
    derivations = session.explain("C(w, v)").derivations
    assert len(derivations) == 1
    d = derivations[0]
    assert d.rule_id == "r"


# -- Task 3: processing failure atomicity and targeted maintenance ------------


def test_processing_failure_rolls_back(monkeypatch):
    from semantica.utils.exceptions import ProcessingError

    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[FactSupport("old", "A(x)")])
    before = (session.version, session.facts, session.explain("B(x)"))
    real_matcher = session._match_rule

    def fail(*args, **kwargs):
        raise RuntimeError("injected evaluator failure")

    monkeypatch.setattr(session, "_match_rule", fail)
    with pytest.raises(ProcessingError) as error:
        session.apply(
            assertions=[FactSupport("new", "A(y)")], retractions=["old"]
        )
    assert isinstance(error.value.__cause__, RuntimeError)
    assert (session.version, session.facts, session.explain("B(x)")) == before
    monkeypatch.setattr(session, "_match_rule", real_matcher)
    session.apply(assertions=[FactSupport("new", "A(y)")], retractions=["old"])
    assert session.facts == frozenset({"A(y)", "B(y)"})


def test_retraction_without_fact_change_skips_matching(monkeypatch):
    session = TruthMaintenanceSession(rules=[rule("ab", ["A(?x)"], "B(?x)")])
    session.apply(assertions=[
        FactSupport("s1", "A(x)"), FactSupport("s2", "A(x)"),
    ])
    calls = []
    real_matcher = session._match_rule

    def counting(*args, **kwargs):
        calls.append(args[0].rule_id)
        return real_matcher(*args, **kwargs)

    monkeypatch.setattr(session, "_match_rule", counting)
    delta = session.apply(retractions=["s1"])
    assert not calls
    assert not delta.added_facts and not delta.removed_facts
    assert delta.removed_supports == (FactSupport("s1", "A(x)"),)
    assert session.facts == frozenset({"A(x)", "B(x)"})
    explanation = session.explain("B(x)")
    assert explanation.active is True
    assert len(explanation.derivations) == 1


def test_assertion_rematches_only_dependent_rule_closure(monkeypatch):
    session = TruthMaintenanceSession(rules=[
        rule("ab", ["A(?x)"], "B(?x)"),
        rule("bc", ["B(?x)"], "C(?x)"),
        rule("zw", ["Z(?x)"], "W(?x)"),
    ])
    session.apply(assertions=[FactSupport("z", "Z(q)")])
    calls = []
    real_matcher = session._match_rule

    def counting(snapshot, facts):
        calls.append(snapshot.rule_id)
        return real_matcher(snapshot, facts)

    monkeypatch.setattr(session, "_match_rule", counting)
    session.apply(assertions=[FactSupport("a", "A(x)")])
    assert calls == ["ab", "bc"]
    assert "zw" not in calls
    assert session.facts == frozenset({"A(x)", "B(x)", "C(x)", "Z(q)", "W(q)"})
    explanation = session.explain("C(x)")
    assert explanation.active is True
    assert len(explanation.derivations) == 1
    assert explanation.derivations[0].rule_id == "bc"
    assert session.explain("W(q)").derivations[0].rule_id == "zw"
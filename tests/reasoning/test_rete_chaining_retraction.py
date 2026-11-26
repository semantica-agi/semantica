"""ReteEngine binds clean values, ignores duplicate facts, retracts, and chains.

Before: a condition "T(?v,?p)" bound p to " P1" (leading space, because the match
ran on the rendered fact string); the same fact asserted twice fired the rule twice;
there was no way to withdraw a fact; and conclusions were never fed back, so a rule
over another rule's conclusion never fired.
"""

import random

from semantica.reasoning import Reasoner, ReteEngine
from semantica.reasoning._rule_matching import canonical_atom
from semantica.reasoning.reasoner import Fact

R1 = (
    "IF TechnicalCheckPassed(?v,?p) AND RegionalCheckPassed(?v,?p) "
    "THEN PotentiallyEligible(?v,?p)"
)
R2 = "IF PotentiallyEligible(?v,?p) THEN ReviewApplication(?v,?p)"


def engine(rules=(R1, R2)):
    r = Reasoner()
    e = ReteEngine()
    e.build_network([r.add_rule(x) for x in rules])
    return e


def F(i, text):
    pred, rest = text.split("(", 1)
    return Fact(f"f{i}", pred, [a.strip() for a in rest[:-1].split(",")])


def test_bindings_carry_no_spacing():
    e = engine()
    matches = e.match_patterns(
        [F(1, "TechnicalCheckPassed(V1, P1)"), F(2, "RegionalCheckPassed(V1, P1)")]
    )
    assert [m.bindings for m in matches] == [{"v": "V1", "p": "P1"}]
    assert e.execute_matches(matches) == ["PotentiallyEligible(V1,P1)"]


def test_a_duplicate_fact_does_not_fire_twice():
    e = engine()
    e.match_patterns(
        [
            F(1, "TechnicalCheckPassed(V1, P1)"),
            F(2, "RegionalCheckPassed(V1, P1)"),
            F(3, "RegionalCheckPassed(V1, P1)"),
        ]
    )
    assert len(e.match_patterns()) == 1
    assert len(e.facts) == 2


def test_run_chains_conclusions_to_a_fixpoint():
    e = engine()
    out = e.run(
        [
            F(1, "TechnicalCheckPassed(V1, P1)"),
            F(2, "RegionalCheckPassed(V1, P1)"),
            F(3, "RegionalCheckPassed(V2, P1)"),
        ]
    )
    assert out == ["PotentiallyEligible(V1, P1)", "ReviewApplication(V1, P1)"]
    assert e.last_run_complete is True
    assert e.run() == []  # nothing new on a second run


def test_run_reports_an_incomplete_run():
    e = engine(
        [
            "IF Link(?x, ?y) THEN Reach(?x, ?y)",
            "IF Reach(?x, ?z) AND Link(?z, ?y) THEN Reach(?x, ?y)",
        ]
    )
    e.run([F(i, f"Link(n{i}, n{i + 1})") for i in range(20)], max_iterations=3)
    assert e.last_run_complete is False


def test_removing_a_fact_withdraws_what_rested_on_it():
    e = engine()
    e.run([F(1, "TechnicalCheckPassed(V1, P1)"), F(2, "RegionalCheckPassed(V1, P1)")])
    assert e.remove_fact(F(9, "RegionalCheckPassed(V1, P1)")) is True
    assert e.match_patterns() == [] or all(
        "RegionalCheckPassed" not in str(f) for m in e.match_patterns() for f in m.facts
    )
    assert "PotentiallyEligible(V1, P1)" not in [str(f) for f in e.facts]
    assert "ReviewApplication(V1, P1)" not in [str(f) for f in e.facts]
    assert e.remove_fact(F(9, "RegionalCheckPassed(V1, P1)")) is False
    assert e.run([F(2, "RegionalCheckPassed(V1, P1)")]) == [
        "PotentiallyEligible(V1, P1)",
        "ReviewApplication(V1, P1)",
    ]


def test_run_reaches_the_same_closure_as_reasoner():
    rules = [
        "IF Supplies(?s, ?x) AND Supplies(?s, ?z) AND Competes(?z, ?x) "
        "THEN SharesSupplier(?x, ?z, ?s)",
        "IF Owns(?g, ?y) AND Operates(?y, ?s) AND LocatedIn(?s, ?c) "
        "THEN PresentThrough(?g, ?c, ?y, ?s)",
        "IF SharesSupplier(?x, ?z, ?s) AND Owns(?g, ?x) THEN GroupExposed(?g, ?z, ?s)",
    ]
    rng = random.Random(7)
    names = [f"e{i}" for i in range(12)]
    preds = ["Supplies", "Competes", "Owns", "Operates", "LocatedIn"]
    facts = sorted(
        {
            f"{rng.choice(preds)}({rng.choice(names)}, {rng.choice(names)})"
            for _ in range(160)
        }
    )
    r = Reasoner()
    for x in rules:
        r.add_rule(x)
    for f in facts:
        r.add_fact(f)
    expected = {canonical_atom(x.conclusion) for x in r.forward_chain()}
    e = engine(rules)
    got = set(e.run([F(i, f) for i, f in enumerate(facts)]))
    assert got == expected and len(expected) > 5

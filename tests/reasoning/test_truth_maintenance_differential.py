"""Differential tests comparing incremental session updates with an independent oracle.

The oracle here is intentionally naive: it re-computes the full closure from
scratch by enumerating every substitution over the constant domain, using only
structured tuple atoms built inside this file. It never touches the session
parser, matcher, dependency index, or ``Reasoner.forward_chain()``.

Randomized workload (seeds 0..19):
- 12 acyclic rules over predicates P0..P5 (arity 2, head index > body indices)
- 15 initial external supports, then 60 update batches (0..3 assertions and
  0..3 retractions per batch; support ids never cross within a batch)
- support ids are permanently bound to their atom; retired ids may be
  re-activated later with the same atom, and duplicate sources are allowed
- random invalid inputs (re-binding a support id to a different fact) must be
  rejected atomically without state changes

Each batch compares facts, per-fact direct derivations, explicit supports,
version, and the net delta. On failure the assertion message carries the seed,
the rules, the completed events, and the failing batch.

Metamorphic checks:
- reordering rules and initial supports yields the same facts and derivations
- asserting a support and then retracting it restores the logical state
"""

import itertools
import random

import pytest

from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError

CONSTANTS = ("a", "b", "c")
VARIABLES = ("?x", "?y")
PREDICATES = tuple(f"P{i}" for i in range(6))


# --------------------------------------------------------------------------
# Tuple-atom helpers (test-internal, independent of the session parser)
# --------------------------------------------------------------------------

def atom_text(atom):
    predicate, terms = atom
    return "{}({})".format(predicate, ", ".join(terms))


def parse_session_fact(text):
    predicate, _, rest = text.partition("(")
    return (predicate, tuple(rest.rstrip(")").split(", ")))


def rule_text(rule):
    _rule_id, body_atoms, head_atom = rule
    return "{} <- {}".format(atom_text(head_atom), ", ".join(atom_text(a) for a in body_atoms))


# --------------------------------------------------------------------------
# Independent oracle: exhaustive substitution enumeration
# --------------------------------------------------------------------------

def groundings(rule, facts):
    """Enumerate every substitution of the rule variables over the constant domain.

    Returns a list of ``(conclusion, premises, bindings)`` tuples where
    ``premises`` preserves condition order and ``bindings`` is sorted by
    variable name.
    """
    _rule_id, body_atoms, head_atom = rule
    variables = sorted(
        {term for atom in body_atoms + (head_atom,) for term in atom[1] if term.startswith("?")}
    )
    domain = set()
    for fact in facts:
        domain.update(fact[1])
    for atom in body_atoms + (head_atom,):
        domain.update(term for term in atom[1] if not term.startswith("?"))
    domain = sorted(domain)
    results = []
    for combo in itertools.product(domain, repeat=len(variables)):
        substitution = dict(zip(variables, combo))
        premises = []
        satisfied = True
        for predicate, terms in body_atoms:
            grounded = (predicate, tuple(substitution.get(term, term) for term in terms))
            if grounded not in facts:
                satisfied = False
                break
            premises.append(grounded)
        if not satisfied:
            continue
        head_predicate, head_terms = head_atom
        conclusion = (head_predicate, tuple(substitution.get(term, term) for term in head_terms))
        bindings = tuple(sorted(substitution.items()))
        results.append((conclusion, tuple(premises), bindings))
    return results


def oracle_closure(rules, support_facts):
    """Iterate all rules to a fixed point starting from the explicit facts."""
    current = set(support_facts)
    while True:
        derived = set(current)
        for rule in rules:
            for conclusion, _premises, _bindings in groundings(rule, current):
                derived.add(conclusion)
        if derived == current:
            return current
        current = derived


def all_derivations(rules, facts):
    """Enumerate every direct derivation on the final closure.

    Includes alternative derivations for conclusions that are already present.
    """
    derivations = {}
    for rule in rules:
        for conclusion, premises, bindings in groundings(rule, facts):
            derivations.setdefault(conclusion, []).append((rule[0], premises, bindings))
    for entries in derivations.values():
        entries.sort(key=lambda d: (d[0], tuple(atom_text(p) for p in d[1]), d[2]))
    return derivations


# --------------------------------------------------------------------------
# Random workload generation
# --------------------------------------------------------------------------

def generate_rules(rng):
    """12 acyclic rules: head predicate index strictly greater than body indices."""
    rules = []
    for index in range(12):
        head_index = rng.randint(1, 5)
        body_atoms = []
        body_variables = set()
        for _ in range(rng.randint(1, 3)):
            predicate = f"P{rng.randint(0, head_index - 1)}"
            terms = tuple(rng.choice(CONSTANTS + VARIABLES) for _ in range(2))
            body_variables.update(term for term in terms if term.startswith("?"))
            body_atoms.append((predicate, terms))
        head_choices = list(body_variables) + list(CONSTANTS)
        head_terms = tuple(rng.choice(head_choices) for _ in range(2))
        rules.append((f"r{index}", tuple(body_atoms), (f"P{head_index}", head_terms)))
    return tuple(rules)


def random_ground_atom(rng):
    predicate = rng.choice(PREDICATES)
    terms = tuple(rng.choice(CONSTANTS) for _ in range(2))
    return (predicate, terms)


def generate_batch(rng, catalog, supports, counter):
    """One update batch: (assertions, retractions, invalid_or_None).

    Assertions and retractions never share ids inside a batch. Retired ids may
    be re-activated, but only with their permanently bound atom.
    """
    retractions = rng.sample(sorted(supports), min(len(supports), rng.randint(0, 3)))
    assertions = []
    retired = sorted(sid for sid in catalog if sid not in supports)
    for _ in range(rng.randint(0, 3)):
        if retired and rng.random() < 0.5:
            sid = retired.pop(rng.randrange(len(retired)))
            fact = catalog[sid]
        else:
            sid = f"s{next(counter)}"
            fact = random_ground_atom(rng)
            catalog[sid] = fact
        if any(sid == existing for existing, _fact in assertions):
            continue
        assertions.append((sid, fact))
    invalid = None
    eligible = sorted(sid for sid in supports if sid not in retractions)
    if eligible and rng.random() < 0.2:
        sid = rng.choice(eligible)
        different = random_ground_atom(rng)
        while different == catalog[sid]:
            different = random_ground_atom(rng)
        invalid = (sid, different)
    return assertions, retractions, invalid


def build_session(rules):
    return TruthMaintenanceSession(
        rules=[
            Rule(rule_id, rule_id, [atom_text(a) for a in body], atom_text(head))
            for rule_id, body, head in rules
        ]
    )


def compare_session(session, rules, supports, seed, stage, events):
    """Compare the full logical state of the session against the oracle."""
    closure = oracle_closure(rules, set(supports.values()))
    session_facts = {parse_session_fact(text) for text in session.facts}
    assert session_facts == closure, (
        f"facts mismatch\nseed={seed}\nstage={stage}\nrules={[rule_text(r) for r in rules]}\nevents={events}\n"
        f"session={sorted(session_facts)}\noracle={sorted(closure)}"
    )
    derivations = all_derivations(rules, closure)
    for fact in closure:
        explanation = session.explain(atom_text(fact))
        expected = derivations.get(fact, [])
        actual = explanation.derivations
        assert len(actual) == len(expected), (
            f"derivation count mismatch for {atom_text(fact)}\nseed={seed}\nstage={stage}\nrules={[rule_text(r) for r in rules]}\nevents={events}\n"
            f"expected={expected}\nactual={[(d.rule_id, d.premises, d.bindings) for d in actual]}"
        )
        for (rule_id, premises, bindings), derivation in zip(expected, actual):
            assert derivation.rule_id == rule_id
            assert derivation.conclusion == atom_text(fact)
            assert derivation.premises == tuple(atom_text(p) for p in premises)
            assert derivation.bindings == bindings
        expected_ids = tuple(sorted(sid for sid, fact_of in supports.items() if fact_of == fact))
        assert explanation.explicit_support_ids == expected_ids, (
            f"explicit support mismatch for {atom_text(fact)}\nseed={seed}\nstage={stage}\nevents={events}"
        )


# --------------------------------------------------------------------------
# Differential loop
# --------------------------------------------------------------------------

def run_seed(seed):
    rng = random.Random(seed)
    rules = generate_rules(rng)
    session = build_session(rules)

    supports = {}
    catalog = {}
    counter = itertools.count()
    for _ in range(15):
        sid = f"s{next(counter)}"
        atom = random_ground_atom(rng)
        catalog[sid] = atom
        supports[sid] = atom
    delta = session.apply(
        assertions=[FactSupport(sid, atom_text(atom)) for sid, atom in supports.items()]
    )
    assert delta.version == 1
    assert delta.added_supports == tuple(
        FactSupport(sid, atom_text(supports[sid])) for sid in sorted(supports)
    )
    assert delta.removed_supports == ()

    events = []
    compare_session(session, rules, supports, seed, "initial", events)
    closure = oracle_closure(rules, set(supports.values()))
    version = 1

    for batch_index in range(60):
        assertions, retractions, invalid = generate_batch(rng, catalog, supports, counter)
        batch = (assertions, retractions, invalid)
        if invalid is not None:
            before = (session.version, session.facts)
            with pytest.raises(ValidationError):
                session.apply(
                    assertions=[
                        FactSupport(sid, atom_text(fact))
                        for sid, fact in assertions + [invalid]
                    ],
                    retractions=list(retractions),
                )
            assert (session.version, session.facts) == before
            events.append((batch, "rejected"))
            continue
        delta = session.apply(
            assertions=[FactSupport(sid, atom_text(fact)) for sid, fact in assertions],
            retractions=list(retractions),
        )
        new_supports = {key: value for key, value in supports.items() if key not in retractions}
        new_supports.update(assertions)
        new_closure = oracle_closure(rules, set(new_supports.values()))

        added_facts = new_closure - closure
        removed_facts = closure - new_closure
        added_support_ids = tuple(sorted(set(new_supports) - set(supports)))
        removed_support_ids = tuple(sorted(set(supports) - set(new_supports)))
        changed = bool(
            added_facts or removed_facts or added_support_ids or removed_support_ids
        )
        if changed:
            version += 1

        stage = f"batch {batch_index}"
        assert delta.version == version, (
            f"version mismatch\nseed={seed}\nstage={stage}\nevents={events}\nbatch={batch}"
        )
        assert delta.added_facts == frozenset(atom_text(fact) for fact in added_facts), (
            f"added facts mismatch\nseed={seed}\nstage={stage}\nevents={events}\nbatch={batch}"
            f"\nexpected={sorted(atom_text(fact) for fact in added_facts)}"
            f"\nactual={sorted(delta.added_facts)}"
        )
        assert delta.removed_facts == frozenset(atom_text(fact) for fact in removed_facts), (
            f"removed facts mismatch\nseed={seed}\nstage={stage}\nevents={events}\nbatch={batch}"
            f"\nexpected={sorted(atom_text(fact) for fact in removed_facts)}"
            f"\nactual={sorted(delta.removed_facts)}"
        )
        assert delta.added_supports == tuple(
            FactSupport(sid, atom_text(new_supports[sid])) for sid in added_support_ids
        ), f"added supports mismatch\nseed={seed}\nstage={stage}\nevents={events}\nbatch={batch}"
        assert delta.removed_supports == tuple(
            FactSupport(sid, atom_text(supports[sid])) for sid in removed_support_ids
        ), f"removed supports mismatch\nseed={seed}\nstage={stage}\nevents={events}\nbatch={batch}"

        supports = new_supports
        closure = new_closure
        events.append((batch, "applied"))
        compare_session(session, rules, supports, seed, stage, events)


@pytest.mark.parametrize("seed", range(20))
def test_differential_against_oracle(seed):
    run_seed(seed)


# --------------------------------------------------------------------------
# Metamorphic checks
# --------------------------------------------------------------------------

def logical_state(session):
    return (
        session.facts,
        {fact: session.explain(fact).derivations for fact in session.facts},
        {fact: session.explain(fact).explicit_support_ids for fact in session.facts},
    )


def test_metamorphic_order_independence():
    rng = random.Random(11)
    rules = generate_rules(rng)
    initial = [(f"s{index}", random_ground_atom(rng)) for index in range(10)]

    session_a = build_session(rules)
    session_a.apply(
        assertions=[FactSupport(sid, atom_text(atom)) for sid, atom in initial]
    )

    shuffler = random.Random(99)
    shuffled_rules = list(rules)
    shuffler.shuffle(shuffled_rules)
    shuffled_initial = list(initial)
    shuffler.shuffle(shuffled_initial)
    session_b = build_session(tuple(shuffled_rules))
    session_b.apply(
        assertions=[FactSupport(sid, atom_text(atom)) for sid, atom in shuffled_initial]
    )

    # Replay identical batches on both sessions.
    replay_rng = random.Random(5)
    catalog = dict(initial)
    supports = dict(initial)
    counter = itertools.count(10)
    for _ in range(15):
        assertions, retractions, _invalid = generate_batch(replay_rng, catalog, supports, counter)
        batch_assertions = [FactSupport(sid, atom_text(fact)) for sid, fact in assertions]
        session_a.apply(assertions=batch_assertions, retractions=list(retractions))
        session_b.apply(assertions=batch_assertions, retractions=list(retractions))
        supports = {key: value for key, value in supports.items() if key not in retractions}
        supports.update(assertions)

    assert session_a.facts == session_b.facts
    for fact in session_a.facts:
        assert session_a.explain(fact).derivations == session_b.explain(fact).derivations
        assert (
            session_a.explain(fact).explicit_support_ids
            == session_b.explain(fact).explicit_support_ids
        )


def test_metamorphic_add_then_retract_restores_state():
    rng = random.Random(3)
    rules = generate_rules(rng)
    session = build_session(rules)
    initial = [(f"s{index}", random_ground_atom(rng)) for index in range(8)]
    session.apply(
        assertions=[FactSupport(sid, atom_text(atom)) for sid, atom in initial]
    )

    before = logical_state(session)
    session.apply(assertions=[FactSupport("probe", atom_text(("P1", ("a", "b"))))])
    session.apply(retractions=["probe"])
    after = logical_state(session)

    assert before == after
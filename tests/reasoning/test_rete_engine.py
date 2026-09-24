"""Tests for the RETE engine pattern matching (issue #300, PR #1720).

These tests verify that ``AlphaNode._matches`` and ``BetaNode._can_join`` no
longer behave like the old always-``True`` stubs, and that the network as a
whole only fires rules whose conditions actually unify with the facts.

``TestArityMismatchRejection`` (PR #1720) specifically guards the fix for the
arity-mismatch bug where lazy ``.+?`` regex groups absorbed surplus arguments.
It exercises all three execution paths: ``unify_condition()``,
``AlphaNode._matches()``, and ``ReteEngine.add_fact()``.
"""

import itertools
import re
import unittest
from unittest import mock

from semantica.reasoning import rete_engine
from semantica.reasoning.reasoner import Fact, Rule
from semantica.reasoning.rete_engine import (
    AlphaNode,
    BetaNode,
    ReteEngine,
    unify_condition,
)


class TestUnifyCondition(unittest.TestCase):
    def test_single_variable_binds(self):
        fact = Fact("f1", "Person", ["John"])
        bindings = unify_condition("Person(?x)", fact)
        self.assertEqual(bindings, {"x": "John"})

    def test_predicate_mismatch_returns_none(self):
        fact = Fact("f1", "Company", ["Google"])
        self.assertIsNone(unify_condition("Person(?x)", fact))

    def test_two_arguments_bind(self):
        fact = Fact("f2", "Parent", ["John", "Mary"])
        bindings = unify_condition("Parent(?x, ?y)", fact)
        self.assertEqual(bindings, {"x": "John", "y": "Mary"})

    def test_literal_argument_must_match(self):
        fact = Fact("f3", "Parent", ["John", "Mary"])
        self.assertIsNone(unify_condition("Parent(Bob, ?y)", fact))
        self.assertEqual(unify_condition("Parent(John, ?y)", fact), {"y": "Mary"})

    def test_repeated_variable_requires_equal_values(self):
        loves_self = Fact("f4", "Loves", ["John", "John"])
        loves_other = Fact("f5", "Loves", ["John", "Mary"])
        self.assertEqual(unify_condition("Loves(?x, ?x)", loves_self), {"x": "John"})
        self.assertIsNone(unify_condition("Loves(?x, ?x)", loves_other))

    def test_regex_error_logs_warning_and_returns_none(self):
        """A regex compilation error is logged with context and yields None."""
        fact = Fact("f6", "Person", ["John"])
        with (
            mock.patch.object(
                rete_engine.re,
                "match",
                side_effect=re.error("bad pattern"),
            ),
            self.assertLogs("semantica.rete_engine", level="WARNING") as captured,
        ):
            result = unify_condition("Person(?x)", fact)
        self.assertIsNone(result)
        joined = "\n".join(captured.output)
        self.assertIn("Person(?x)", joined)
        self.assertIn("Person(John)", joined)
        self.assertIn("bad pattern", joined)

    def test_unexpected_error_logs_warning_and_returns_none(self):
        """An unexpected error is also logged and swallowed as None."""
        fact = Fact("f7", "Person", ["John"])
        with (
            mock.patch.object(
                rete_engine.re,
                "match",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("semantica.rete_engine", level="WARNING") as captured,
        ):
            result = unify_condition("Person(?x)", fact)
        self.assertIsNone(result)
        self.assertIn("boom", "\n".join(captured.output))


class TestAlphaNode(unittest.TestCase):
    def test_matches_stores_bindings(self):
        node = AlphaNode("a1", "Person(?x)")
        fact = Fact("f1", "Person", ["John"])
        token = node.add_fact(fact)
        self.assertIsNotNone(token)
        assert token is not None  # narrow type for the checker
        self.assertEqual(token.facts, [fact])
        self.assertEqual(token.bindings, {"x": "John"})
        self.assertIn(token, node.tokens)

    def test_non_matching_fact_rejected(self):
        node = AlphaNode("a1", "Person(?x)")
        fact = Fact("f1", "Company", ["Google"])
        self.assertIsNone(node.add_fact(fact))
        self.assertEqual(node.tokens, [])

    def test_uses_precompiled_regex(self):
        """AlphaNode compiles its condition once and reuses it per fact."""
        node = AlphaNode("a1", "Person(?x)")
        self.assertIsNotNone(node._compiled)
        # Matching goes through the compiled matcher, not unify_condition.
        with mock.patch.object(rete_engine, "unify_condition") as unify:
            fact = Fact("f1", "Person", ["John"])
            token = node.add_fact(fact)
        unify.assert_not_called()
        self.assertIsNotNone(token)
        assert token is not None
        self.assertEqual(token.bindings, {"x": "John"})

    def test_bad_condition_never_matches_and_logs(self):
        """A condition that fails to compile logs a warning and never fires."""
        with (
            mock.patch.object(
                rete_engine,
                "_build_condition_regex",
                return_value="(unbalanced",
            ),
            self.assertLogs("semantica.rete_engine", level="WARNING") as captured,
        ):
            node = AlphaNode("bad", "Person(?x)")
        self.assertIsNone(node._compiled)
        self.assertIn("failed to compile", "\n".join(captured.output))
        fact = Fact("f1", "Person", ["John"])
        self.assertIsNone(node.add_fact(fact))
        self.assertEqual(node.tokens, [])


class TestBetaNode(unittest.TestCase):
    def test_join_consistent_bindings(self):
        left = AlphaNode("a1", "Parent(?x, ?y)")
        right = AlphaNode("a2", "Person(?x)")
        beta = BetaNode("b1", left, right)

        parent = Fact("f1", "Parent", ["John", "Mary"])
        person = Fact("f2", "Person", ["John"])
        left_token = left.add_fact(parent)
        right_token = right.add_fact(person)
        assert left_token is not None and right_token is not None

        merged = beta.join(left_token, right_token)
        self.assertIsNotNone(merged)
        assert merged is not None  # narrow type for the checker
        self.assertEqual(merged.bindings, {"x": "John", "y": "Mary"})
        # Facts are concatenated left-then-right in condition order.
        self.assertEqual(merged.facts, [parent, person])

    def test_join_conflicting_bindings_rejected(self):
        left = AlphaNode("a1", "Parent(?x, ?y)")
        right = AlphaNode("a2", "Person(?x)")
        beta = BetaNode("b1", left, right)

        parent = Fact("f1", "Parent", ["John", "Mary"])
        # ?x conflicts: John vs Alice
        person = Fact("f2", "Person", ["Alice"])
        left_token = left.add_fact(parent)
        right_token = right.add_fact(person)
        assert left_token is not None and right_token is not None

        self.assertIsNone(beta.join(left_token, right_token))


class TestReteEngineEndToEnd(unittest.TestCase):
    def test_only_matching_rule_fires(self):
        engine = ReteEngine()
        rule = Rule(
            rule_id="r1",
            name="person rule",
            conditions=["Person(?x)"],
            conclusion="Mortal(?x)",
        )
        engine.build_network([rule])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Company", ["Google"]))  # should NOT fire

        matches = engine.match_patterns()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].bindings, {"x": "John"})

    def test_multi_condition_join(self):
        engine = ReteEngine()
        rule = Rule(
            rule_id="r1",
            name="child rule",
            conditions=["Person(?x)", "Parent(?x, ?y)"],
            conclusion="Child(?y, ?x)",
        )
        engine.build_network([rule])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["John", "Mary"]))
        # Unrelated parent whose ?x does not match any Person -> no activation.
        engine.add_fact(Fact("f3", "Parent", ["Bob", "Sue"]))

        matches = engine.match_patterns()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].bindings, {"x": "John", "y": "Mary"})

    def test_no_activation_when_join_inconsistent(self):
        engine = ReteEngine()
        rule = Rule(
            rule_id="r1",
            name="child rule",
            conditions=["Person(?x)", "Parent(?x, ?y)"],
            conclusion="Child(?y, ?x)",
        )
        engine.build_network([rule])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["Alice", "Mary"]))  # ?x mismatch

        matches = engine.match_patterns()
        self.assertEqual(matches, [])


class TestThreeConditionChain(unittest.TestCase):
    """Chained beta joins across three or more conditions (issue #300).

    These exercise the Token model: a token must accumulate the ordered
    facts and the consistent bindings of every condition, so that deep
    chains neither drop bindings nor duplicate facts, and a conflict on the
    third condition correctly suppresses activation.
    """

    def _three_condition_rule(self):
        return Rule(
            rule_id="r1",
            name="location chain",
            conditions=[
                "Person(?x)",
                "Parent(?x, ?y)",
                "Located(?y, ?z)",
            ],
            conclusion="LivesNear(?x, ?z)",
        )

    def test_three_condition_valid_match(self):
        engine = ReteEngine()
        engine.build_network([self._three_condition_rule()])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["John", "Mary"]))
        engine.add_fact(Fact("f3", "Located", ["Mary", "Paris"]))

        matches = engine.match_patterns()
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].bindings,
            {"x": "John", "y": "Mary", "z": "Paris"},
        )

    def test_three_condition_third_level_conflict(self):
        engine = ReteEngine()
        engine.build_network([self._three_condition_rule()])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["John", "Mary"]))
        # ?y is bound to Mary, so a Located fact about Bob must not join.
        engine.add_fact(Fact("f3", "Located", ["Bob", "Paris"]))

        matches = engine.match_patterns()
        self.assertEqual(matches, [])

    def test_fact_insertion_order_independent(self):
        # Whatever order facts arrive, the same single match must result.
        base_facts = [
            Fact("f1", "Person", ["John"]),
            Fact("f2", "Parent", ["John", "Mary"]),
            Fact("f3", "Located", ["Mary", "Paris"]),
        ]
        expected = {"x": "John", "y": "Mary", "z": "Paris"}

        for order in itertools.permutations(base_facts):
            engine = ReteEngine()
            engine.build_network([self._three_condition_rule()])
            for fact in order:
                engine.add_fact(fact)
            matches = engine.match_patterns()
            self.assertEqual(len(matches), 1, f"order={order}")
            self.assertEqual(matches[0].bindings, expected)

    def test_match_facts_complete_in_condition_order(self):
        engine = ReteEngine()
        engine.build_network([self._three_condition_rule()])

        person = Fact("f1", "Person", ["John"])
        parent = Fact("f2", "Parent", ["John", "Mary"])
        located = Fact("f3", "Located", ["Mary", "Paris"])
        engine.add_fact(person)
        engine.add_fact(parent)
        engine.add_fact(located)

        matches = engine.match_patterns()
        self.assertEqual(len(matches), 1)
        # All three facts preserved, in condition order, no duplicates.
        self.assertEqual(matches[0].facts, [person, parent, located])

    def test_multiple_left_tokens_join_one_right_fact(self):
        # Two Person/Parent chains sharing the same Located(?y, ?z) fact.
        engine = ReteEngine()
        engine.build_network([self._three_condition_rule()])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["John", "Mary"]))
        engine.add_fact(Fact("f3", "Person", ["Alice"]))
        engine.add_fact(Fact("f4", "Parent", ["Alice", "Mary"]))
        # One right fact should join with both accumulated left tokens.
        engine.add_fact(Fact("f5", "Located", ["Mary", "Paris"]))

        matches = engine.match_patterns()
        self.assertEqual(len(matches), 2)
        result = {m.bindings["x"]: m.bindings["z"] for m in matches}
        self.assertEqual(result, {"John": "Paris", "Alice": "Paris"})

    def test_matches_reasoner_match_rule(self):
        from semantica.reasoning.reasoner import Reasoner

        rule = self._three_condition_rule()
        facts = [
            Fact("f1", "Person", ["John"]),
            Fact("f2", "Parent", ["John", "Mary"]),
            Fact("f3", "Located", ["Mary", "Paris"]),
        ]

        # Reasoner works over stringified facts and returns
        # (conclusion, matched_facts, bindings) tuples from self.facts.
        reasoner = Reasoner()
        for fact in facts:
            reasoner.add_fact(str(fact))
        reasoner_matches = reasoner._match_rule(rule)

        engine = ReteEngine()
        engine.build_network([rule])
        for fact in facts:
            engine.add_fact(fact)
        rete_matches = engine.match_patterns()

        # Both engines must agree on the number of activations.
        self.assertEqual(len(rete_matches), len(reasoner_matches))
        self.assertEqual(len(rete_matches), 1)
        self.assertEqual(
            rete_matches[0].bindings,
            {"x": "John", "y": "Mary", "z": "Paris"},
        )
        # The RETE match must carry the instantiated conclusion facts too.
        conclusion, _, _ = reasoner_matches[0]
        self.assertEqual(conclusion, "LivesNear(John, Paris)")

    def test_reset_clears_all_token_memory(self):
        engine = ReteEngine()
        engine.build_network([self._three_condition_rule()])

        engine.add_fact(Fact("f1", "Person", ["John"]))
        engine.add_fact(Fact("f2", "Parent", ["John", "Mary"]))
        engine.add_fact(Fact("f3", "Located", ["Mary", "Paris"]))
        self.assertEqual(len(engine.match_patterns()), 1)

        engine.reset()

        # No stale facts, tokens or activations remain anywhere.
        self.assertEqual(engine.facts, [])
        for node in engine.network.values():
            if isinstance(node, AlphaNode):
                self.assertEqual(node.tokens, [])
            elif isinstance(node, BetaNode):
                self.assertEqual(node.left_tokens, [])
                self.assertEqual(node.right_tokens, [])
        self.assertEqual(engine.match_patterns(), [])


class TestCountPatternArity(unittest.TestCase):
    """Unit tests for the ``_count_pattern_arity`` helper (issue #1720).

    This function is the structural source-of-truth for how many arguments
    a condition pattern declares.  It must handle nested calls, zero-arg
    forms, and patterns with no parentheses without touching the rendered
    fact string.
    """

    def setUp(self):
        from semantica.reasoning.rete_engine import _count_pattern_arity

        self._arity = _count_pattern_arity

    def test_one_variable(self):
        self.assertEqual(self._arity("Person(?x)"), 1)

    def test_two_variables(self):
        self.assertEqual(self._arity("Parent(?x, ?y)"), 2)

    def test_three_variables(self):
        self.assertEqual(self._arity("Located(?x, ?y, ?z)"), 3)

    def test_mixed_literal_and_variable(self):
        self.assertEqual(self._arity("knows(Doe, John, ?y)"), 3)

    def test_all_literals(self):
        self.assertEqual(self._arity("pred(a, b, c)"), 3)

    def test_zero_args(self):
        self.assertEqual(self._arity("axiom()"), 0)

    def test_no_parens(self):
        self.assertEqual(self._arity("no_parens"), 0)

    def test_nested_call_counts_as_one_arg(self):
        """A nested call ``f(?y, ?z)`` is a single top-level argument."""
        self.assertEqual(self._arity("pred(?x, f(?y, ?z), ?w)"), 3)

    def test_double_nested(self):
        self.assertEqual(self._arity("pred(f(a, g(b, c)), d)"), 2)

    def test_repeated_variable(self):
        self.assertEqual(self._arity("Loves(?x, ?x)"), 2)


class TestArityMismatchRejection(unittest.TestCase):
    """Regression tests for the arity-mismatch bug (PR #1720 / issue #1720).

    The original bug: ``_build_condition_regex`` uses lazy ``.+?`` groups
    anchored with ``$``, so a fact with *more* arguments than the condition
    declares would still match — the last variable absorbed all surplus
    arguments as a single comma-separated string.

    These tests verify the fix at *every* layer of the Rete execution path:
      1. ``unify_condition()`` — utility function
      2. ``AlphaNode._matches()`` / ``AlphaNode.add_fact()`` — alpha filter
      3. ``ReteEngine.add_fact()`` — full network propagation
    """

    # ------------------------------------------------------------------ #
    # Required mismatch cases (must all return None / produce no match)   #
    # ------------------------------------------------------------------ #

    def test_extra_arg_via_unify_condition(self):
        """parent(?x, ?y) must not match a 3-argument fact."""
        self.assertIsNone(
            unify_condition("parent(?x, ?y)", Fact("f", "parent", ["a", "b", "c"]))
        )

    def test_extra_arg_via_alpha_node(self):
        """AlphaNode must reject the same 3-argument fact."""
        node = AlphaNode("a1", "parent(?x, ?y)")
        self.assertIsNone(node.add_fact(Fact("f", "parent", ["a", "b", "c"])))

    def test_extra_arg_via_rete_engine(self):
        """ReteEngine must not fire a rule for a fact with too many arguments."""
        engine = ReteEngine()
        engine.build_network(
            [
                Rule(
                    rule_id="r",
                    name="t",
                    conditions=["parent(?x, ?y)"],
                    conclusion="ok",
                )
            ]
        )
        engine.add_fact(Fact("f", "parent", ["a", "b", "c"]))
        self.assertEqual(engine.match_patterns(), [])

    def test_trusts_extra_arg_via_unify_condition(self):
        """trusts(?x) must not match a 2-argument fact."""
        self.assertIsNone(
            unify_condition("trusts(?x)", Fact("f", "trusts", ["a", "b"]))
        )

    def test_trusts_extra_arg_via_alpha_node(self):
        node = AlphaNode("a1", "trusts(?x)")
        self.assertIsNone(node.add_fact(Fact("f", "trusts", ["a", "b"])))

    def test_trusts_extra_arg_via_rete_engine(self):
        engine = ReteEngine()
        engine.build_network(
            [Rule(rule_id="r", name="t", conditions=["trusts(?x)"], conclusion="ok")]
        )
        engine.add_fact(Fact("f", "trusts", ["a", "b"]))
        self.assertEqual(engine.match_patterns(), [])

    def test_knows_extra_arg_via_unify_condition(self):
        """knows(?x) must not match a 2-argument fact."""
        self.assertIsNone(
            unify_condition("knows(?x)", Fact("f", "knows", ["Doe", "John"]))
        )

    def test_knows_extra_arg_via_alpha_node(self):
        node = AlphaNode("a1", "knows(?x)")
        self.assertIsNone(node.add_fact(Fact("f", "knows", ["Doe", "John"])))

    def test_knows_extra_arg_via_rete_engine(self):
        engine = ReteEngine()
        engine.build_network(
            [Rule(rule_id="r", name="t", conditions=["knows(?x)"], conclusion="ok")]
        )
        engine.add_fact(Fact("f", "knows", ["Doe", "John"]))
        self.assertEqual(engine.match_patterns(), [])

    # ------------------------------------------------------------------ #
    # Too-few-argument cases                                               #
    # ------------------------------------------------------------------ #

    def test_too_few_args_via_unify_condition(self):
        """parent(?x, ?y) must not match a 1-argument fact."""
        self.assertIsNone(unify_condition("parent(?x, ?y)", Fact("f", "parent", ["a"])))

    def test_too_few_args_via_alpha_node(self):
        node = AlphaNode("a1", "parent(?x, ?y)")
        self.assertIsNone(node.add_fact(Fact("f", "parent", ["a"])))

    def test_too_few_args_via_rete_engine(self):
        engine = ReteEngine()
        engine.build_network(
            [
                Rule(
                    rule_id="r",
                    name="t",
                    conditions=["parent(?x, ?y)"],
                    conclusion="ok",
                )
            ]
        )
        engine.add_fact(Fact("f", "parent", ["a"]))
        self.assertEqual(engine.match_patterns(), [])

    def test_zero_arg_condition_rejects_one_arg_fact(self):
        """axiom() must not fire for a fact that carries an argument."""
        node = AlphaNode("a1", "axiom()")
        self.assertIsNone(node.add_fact(Fact("f", "axiom", ["x"])))
        engine = ReteEngine()
        engine.build_network(
            [Rule(rule_id="r", name="t", conditions=["axiom()"], conclusion="ok")]
        )
        engine.add_fact(Fact("f2", "axiom", ["x"]))
        self.assertEqual(engine.match_patterns(), [])

    # ------------------------------------------------------------------ #
    # Required valid matches (must still fire after the fix)              #
    # ------------------------------------------------------------------ #

    def test_correct_arity_two_args_still_matches(self):
        """knows(?x, ?y) must still match a 2-argument fact."""
        result = unify_condition("knows(?x, ?y)", Fact("f", "knows", ["a", "b"]))
        self.assertEqual(result, {"x": "a", "y": "b"})

    def test_correct_arity_one_arg_still_matches(self):
        """person(?x) must still match a 1-argument fact."""
        result = unify_condition("person(?x)", Fact("f", "person", ["ann"]))
        self.assertEqual(result, {"x": "ann"})

    def test_correct_arity_three_args_with_literal_still_matches(self):
        """knows(Doe, John, ?y) must still match an exact 3-argument fact."""
        result = unify_condition(
            "knows(Doe, John, ?y)", Fact("f", "knows", ["Doe", "John", "x"])
        )
        self.assertEqual(result, {"y": "x"})

    def test_correct_arity_via_alpha_node(self):
        node = AlphaNode("a1", "knows(?x, ?y)")
        token = node.add_fact(Fact("f", "knows", ["a", "b"]))
        self.assertIsNotNone(token)
        self.assertEqual(token.bindings, {"x": "a", "y": "b"})

    def test_correct_arity_via_rete_engine(self):
        engine = ReteEngine()
        engine.build_network(
            [Rule(rule_id="r", name="t", conditions=["knows(?x, ?y)"], conclusion="ok")]
        )
        engine.add_fact(Fact("f", "knows", ["a", "b"]))
        matches = engine.match_patterns()
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].bindings, {"x": "a", "y": "b"})

    def test_zero_arg_condition_matches_zero_arg_fact(self):
        """axiom() must fire for a fact with no arguments."""
        engine = ReteEngine()
        engine.build_network(
            [
                Rule(
                    rule_id="r",
                    name="t",
                    conditions=["axiom()"],
                    conclusion="tautology",
                )
            ]
        )
        engine.add_fact(Fact("f", "axiom", []))
        self.assertEqual(len(engine.match_patterns()), 1)

    # ------------------------------------------------------------------ #
    # Edge cases that must survive the fix unchanged                       #
    # ------------------------------------------------------------------ #

    def test_arity_mismatch_does_not_corrupt_bindings_for_valid_fact(self):
        """A mismatched fact must not leave stale bindings that corrupt
        a subsequent valid fact's match in the same AlphaNode."""
        node = AlphaNode("a1", "knows(?x, ?y)")
        bad_fact = Fact("f1", "knows", ["only_one"])  # arity 1 — rejected
        good_fact = Fact("f2", "knows", ["alice", "bob"])  # arity 2 — accepted
        self.assertIsNone(node.add_fact(bad_fact))
        token = node.add_fact(good_fact)
        self.assertIsNotNone(token)
        self.assertEqual(token.bindings, {"x": "alice", "y": "bob"})

    def test_arity_mismatch_in_multi_condition_rule_does_not_fire(self):
        """A mismatched fact on the first condition of a multi-condition rule
        must not produce a partial match that leaks into the beta layer."""
        engine = ReteEngine()
        rule = Rule(
            rule_id="r",
            name="chain",
            conditions=["Person(?x)", "knows(?x, ?y)"],
            conclusion="met(?y)",
        )
        engine.build_network([rule])
        engine.add_fact(Fact("f1", "Person", ["alice"]))
        # This fact has 3 arguments but the condition expects 2 — must be
        # rejected before reaching the beta join.
        engine.add_fact(Fact("f2", "knows", ["alice", "bob", "carol"]))
        self.assertEqual(engine.match_patterns(), [])

    def test_arity_check_uses_fact_arguments_not_string_rendering(self):
        """A valid one-argument Fact whose rendered string contains a comma
        must not be incorrectly rejected by an arity mismatch.

        The old comma-count heuristic (``fact_str.count(',') == len(args) - 1``)
        evaluated to ``False`` for this case — the comma in the value made the
        counts disagree — so the guard was bypassed entirely, leaving the regex
        unchecked.  The structural check (``_count_pattern_arity(pattern) ==
        len(fact.arguments)``) correctly sees arity 1 on both sides and lets the
        match proceed, binding ``?x`` to the full value including the comma.
        """
        fact = Fact("f", "pred", ["hello, world"])  # 1 arg, value has a comma
        result = unify_condition("pred(?x)", fact)
        self.assertIsNotNone(result)
        self.assertEqual(result, {"x": "hello, world"})
        # AlphaNode path
        node = AlphaNode("a1", "pred(?x)")
        token = node.add_fact(fact)
        self.assertIsNotNone(token)
        self.assertEqual(token.bindings, {"x": "hello, world"})

    def test_arity_check_not_fooled_by_nested_call_in_condition(self):
        """A condition whose second argument is a nested call must count as
        two top-level arguments, not more."""
        from semantica.reasoning.rete_engine import _count_pattern_arity

        # pred(?x, f(?y, ?z)) has 2 top-level args
        self.assertEqual(_count_pattern_arity("pred(?x, f(?y, ?z))"), 2)
        # A 2-arg fact matches; a 3-arg fact is rejected
        fact2 = Fact("f", "pred", ["a", "f(b, c)"])
        fact3 = Fact("f", "pred", ["a", "b", "c"])
        self.assertIsNotNone(unify_condition("pred(?x, ?y)", fact2))
        self.assertIsNone(unify_condition("pred(?x, ?y)", fact3))


if __name__ == "__main__":
    unittest.main()

import unittest

from semantica.reasoning.reasoner import Reasoner, Rule


class TestReasoner(unittest.TestCase):
    def setUp(self):
        self.reasoner = Reasoner()

    def test_add_rule_string(self):
        rule_str = "IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)"
        rule = self.reasoner.add_rule(rule_str)
        self.assertEqual(len(self.reasoner.rules), 1)
        self.assertEqual(rule.conditions, ["Person(?x)", "Parent(?x, ?y)"])
        self.assertEqual(rule.conclusion, "Child(?y, ?x)")

    def test_add_rule_object(self):
        rule = Rule(
            rule_id="r1",
            name="Test Rule",
            conditions=["A(?x)"],
            conclusion="B(?x)",
            priority=10
        )
        self.reasoner.add_rule(rule)
        self.assertEqual(len(self.reasoner.rules), 1)
        self.assertEqual(self.reasoner.rules[0].priority, 10)

    def test_add_fact_string(self):
        self.reasoner.add_fact("Person(John)")
        self.assertIn("Person(John)", self.reasoner.facts)

    def test_add_fact_dict_entity(self):
        fact_dict = {"type": "Person", "name": "John"}
        self.reasoner.add_fact(fact_dict)
        self.assertIn("Person(John)", self.reasoner.facts)

    def test_add_fact_dict_relationship(self):
        fact_dict = {
            "type": "WorksAt",
            "source_name": "John",
            "target_name": "Google"
        }
        self.reasoner.add_fact(fact_dict)
        self.assertIn("WorksAt(John, Google)", self.reasoner.facts)

    def test_forward_chaining(self):
        self.reasoner.add_rule("IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)")
        self.reasoner.add_fact("Person(John)")
        self.reasoner.add_fact("Parent(John, Jane)")
        
        results = self.reasoner.forward_chain()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].conclusion, "Child(Jane, John)")
        self.assertIn("Child(Jane, John)", self.reasoner.facts)

    def test_backward_chaining_simple(self):
        self.reasoner.add_rule("IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)")
        self.reasoner.add_fact("Person(John)")
        self.reasoner.add_fact("Parent(John, Jane)")
        
        result = self.reasoner.backward_chain("Child(Jane, John)")
        self.assertIsNotNone(result)
        self.assertEqual(result.conclusion, "Child(Jane, John)")
        self.assertEqual(len(result.premises), 2)
        self.assertIn("Person(John)", result.premises)
        self.assertIn("Parent(John, Jane)", result.premises)

    def test_forward_chaining_premises(self):
        """Mirrors test_backward_chaining_simple: forward_chain() must attach the
        specific facts that matched the rule's conditions as premises, not leave
        them empty (regression guard for issue #733)."""
        self.reasoner.add_rule("IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)")
        self.reasoner.add_fact("Person(John)")
        self.reasoner.add_fact("Parent(John, Jane)")

        results = self.reasoner.forward_chain()
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result.conclusion, "Child(Jane, John)")
        self.assertEqual(len(result.premises), 2)
        self.assertIn("Person(John)", result.premises)
        self.assertIn("Parent(John, Jane)", result.premises)

    def test_add_rule_deduplicates_identical_rule(self):
        """Bug #732 — re-adding an identical rule string must not duplicate it,
        so re-running the same setup code (e.g. a Jupyter cell) is idempotent."""
        rule_str = "IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)"
        first = self.reasoner.add_rule(rule_str)
        second = self.reasoner.add_rule(rule_str)

        self.assertEqual(len(self.reasoner.rules), 1)
        self.assertIs(first, second)

    def test_add_rule_deduplication_is_idempotent_across_forward_chain(self):
        """Bug #732 — rerunning add_rule()+add_fact()+forward_chain() on the same
        Reasoner instance must not grow the rule count on each call."""
        def run_cell():
            self.reasoner.add_rule("IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)")
            self.reasoner.add_fact("Person(John)")
            self.reasoner.add_fact("Parent(John, Jane)")
            return self.reasoner.forward_chain()

        result1 = run_cell()
        self.assertEqual(len(self.reasoner.rules), 1)
        self.assertEqual([r.conclusion for r in result1], ["Child(Jane, John)"])

        result2 = run_cell()
        self.assertEqual(len(self.reasoner.rules), 1)
        # Nothing new to derive since the fact was already known -- this is
        # now a consistent, expected empty result rather than a symptom of
        # unbounded rule duplication.
        self.assertEqual(result2, [])

    def test_add_rule_duplicate_logs_warning(self):
        """Bug #732 follow-up — a skipped duplicate rule must be surfaced via a
        warning log, not silently swallowed at debug level."""
        rule_str = "IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)"
        self.reasoner.add_rule(rule_str)

        with self.assertLogs(self.reasoner.logger.name, level="WARNING") as cm:
            self.reasoner.add_rule(rule_str)

        self.assertTrue(any("duplicate rule" in msg for msg in cm.output))

    def test_add_rule_duplicate_with_different_confidence_logs_warning(self):
        """Re-adding an identical rule (same conditions/conclusion) with a
        different confidence must warn that the new confidence is discarded
        and the original is retained, not silently drop it."""
        rule_v1 = Rule(
            rule_id="r1", name="Rule", conditions=["A(?x)"], conclusion="B(?x)",
            confidence=0.6,
        )
        rule_v2 = Rule(
            rule_id="r2", name="Rule v2", conditions=["A(?x)"], conclusion="B(?x)",
            confidence=0.95,
        )
        self.reasoner.add_rule(rule_v1)

        with self.assertLogs(self.reasoner.logger.name, level="WARNING") as cm:
            result = self.reasoner.add_rule(rule_v2)

        self.assertIs(result, rule_v1)
        self.assertEqual(result.confidence, 0.6)
        self.assertTrue(any("different confidence" in msg for msg in cm.output))

    def test_add_rule_duplicate_with_non_string_conditions_does_not_raise(self):
        """Bug #732 follow-up — the duplicate-rule warning message building must
        not raise TypeError when Rule.conditions contains non-string entries
        (Rule.conditions is typed List[Any])."""
        rule = Rule(
            rule_id="r1",
            name="Test Rule",
            conditions=[("Person", "?x")],
            conclusion="B(?x)",
        )
        duplicate = Rule(
            rule_id="r2",
            name="Test Rule Duplicate",
            conditions=[("Person", "?x")],
            conclusion="B(?x)",
        )
        self.reasoner.add_rule(rule)
        result = self.reasoner.add_rule(duplicate)

        self.assertIs(result, rule)
        self.assertEqual(len(self.reasoner.rules), 1)

    def test_add_rule_does_not_dedupe_distinct_rules(self):
        """Rules with different conditions/conclusions must still both be added."""
        self.reasoner.add_rule("IF A(?x) THEN B(?x)")
        self.reasoner.add_rule("IF A(?x) THEN C(?x)")
        self.assertEqual(len(self.reasoner.rules), 2)

    def test_add_rule_duplicate_resorts_on_mutated_priority(self):
        """Bug #732 follow-up — Rule is a mutable dataclass, so an already-added
        rule's priority may change after it was registered; re-adding it (a
        duplicate by conditions/conclusion) must still re-sort self.rules
        rather than leaving it stale relative to the mutated priority."""
        low = Rule(rule_id="r1", name="Low", conditions=["A(?x)"], conclusion="B(?x)", priority=0)
        high = Rule(rule_id="r2", name="High", conditions=["C(?x)"], conclusion="D(?x)", priority=5)
        self.reasoner.add_rule(low)
        self.reasoner.add_rule(high)
        self.assertEqual([r.rule_id for r in self.reasoner.rules], ["r2", "r1"])

        # Mutate the already-registered low-priority rule to outrank "high",
        # then re-add it (matches by conditions/conclusion -> dedup path).
        low.priority = 10
        result = self.reasoner.add_rule(low)

        self.assertIs(result, low)
        self.assertEqual(len(self.reasoner.rules), 2)
        self.assertEqual([r.rule_id for r in self.reasoner.rules], ["r1", "r2"])

    def test_infer_facts(self):
        facts = ["Person(John)", "Parent(John, Jane)"]
        rules = ["IF Person(?x) AND Parent(?x, ?y) THEN Child(?y, ?x)"]
        
        inferred = self.reasoner.infer_facts(facts, rules)
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0], "Child(Jane, John)")

    def test_clear_reset(self):
        self.reasoner.add_fact("Fact(1)")
        self.reasoner.add_rule("IF A THEN B")
        self.reasoner.clear()
        self.assertEqual(len(self.reasoner.facts), 0)
        self.assertEqual(len(self.reasoner.rules), 0)

    # --- Bug #354: founded_by predicate inference ---

    def test_infer_facts_with_multi_word_values(self):
        """Bug #354 — _match_pattern must match facts whose values contain spaces."""
        reasoner = Reasoner()
        for f in [
            {"source_name": "Steve Jobs",    "target_name": "Apple", "type": "founded_by"},
            {"source_name": "Steve Wozniak", "target_name": "Apple", "type": "founded_by"},
            {"source_name": "Ronald Wayne",  "target_name": "Apple", "type": "founded_by"},
        ]:
            reasoner.add_fact(f)

        inferred = reasoner.infer_facts(
            [],
            rules=["IF founded_by(?person, ?org) THEN is_founder(?person, ?org)"],
        )

        self.assertEqual(len(inferred), 3)
        self.assertIn("is_founder(Steve Jobs, Apple)", inferred)
        self.assertIn("is_founder(Steve Wozniak, Apple)", inferred)
        self.assertIn("is_founder(Ronald Wayne, Apple)", inferred)

    def test_match_pattern_pre_bound_variable(self):
        """_match_pattern must enforce pre-bound variable values."""
        reasoner = Reasoner()
        bindings = {"org": "Apple"}
        result = reasoner._match_pattern(
            "founded_by(?person, ?org)",
            "founded_by(Steve Jobs, Apple)",
            bindings,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["person"], "Steve Jobs")
        self.assertEqual(result["org"], "Apple")

    def test_match_pattern_binding_conflict_returns_none(self):
        """_match_pattern must return None when a bound variable doesn't match."""
        reasoner = Reasoner()
        bindings = {"org": "Google"}
        result = reasoner._match_pattern(
            "founded_by(?person, ?org)",
            "founded_by(Steve Jobs, Apple)",
            bindings,
        )
        self.assertIsNone(result)

    def test_match_pattern_single_word_values(self):
        """_match_pattern must still work for single-word values (regression guard)."""
        reasoner = Reasoner()
        result = reasoner._match_pattern("Person(?x)", "Person(John)", {})
        self.assertIsNotNone(result)
        self.assertEqual(result["x"], "John")


# ---------------------------------------------------------------------------
# Pure rule-matching helper (Task 1 of the truth maintenance plan): legacy
# parity tests plus the dedicated helper entry points in
# semantica.reasoning._rule_matching.
# ---------------------------------------------------------------------------

class TestRuleMatchingHelpers(unittest.TestCase):
    """Legacy parity for the extracted pure matching functions."""

    def _matched(self, conditions, conclusion, facts):
        reasoner = Reasoner()
        for fact in facts:
            reasoner.add_fact(fact)
        rule = Rule(
            rule_id="r", name="r", conditions=conditions, conclusion=conclusion
        )
        return reasoner._match_rule(rule)

    def test_whitespace_constants_match(self):
        """Constants containing spaces must still match a single variable."""
        matched = self._matched(
            ["founded_by(?person, ?org)"],
            "is_founder(?person, ?org)",
            ["founded_by(Steve Jobs, Apple)"],
        )
        self.assertEqual(len(matched), 1)
        conclusion, matched_facts, bindings = matched[0]
        self.assertEqual(conclusion, "is_founder(Steve Jobs, Apple)")
        self.assertEqual(matched_facts, ["founded_by(Steve Jobs, Apple)"])
        self.assertEqual(bindings, {"person": "Steve Jobs", "org": "Apple"})

    def test_repeated_variable_requires_equal_values(self):
        """Pair(?x, ?x) must not match Pair(a, b) but must match Pair(a, a)."""
        matched = self._matched(
            ["Pair(?x, ?x)"], "Same(?x)", ["Pair(a, b)", "Pair(a, a)"]
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][0], "Same(a)")

    def test_prebound_variable_carries_across_conditions(self):
        """A variable bound in an earlier condition must constrain later ones."""
        matched = self._matched(
            ["Person(?x)", "Parent(?x, ?y)"],
            "Child(?y, ?x)",
            ["Person(John)", "Parent(John, Jane)", "Parent(Mary, Eve)"],
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][0], "Child(Jane, John)")

    def test_three_condition_chain(self):
        """Three accumulating conditions must produce full binding tuples."""
        matched = self._matched(
            ["A(?x)", "B(?x)", "C(?x, ?y)"],
            "D(?x, ?y)",
            ["A(a)", "B(a)", "C(a, b)", "B(z)"],
        )
        self.assertEqual(len(matched), 1)
        conclusion, matched_facts, bindings = matched[0]
        self.assertEqual(conclusion, "D(a, b)")
        self.assertEqual(matched_facts, ["A(a)", "B(a)", "C(a, b)"])
        self.assertEqual(bindings, {"x": "a", "y": "b"})

    def test_variable_prefix_is_token_aware(self):
        """Binding ?x must never rewrite the ?xy placeholder (prefix safety)."""
        matched = self._matched(
            ["P(?x, ?xy)"], "Q(?x, ?xy)", ["P(a, b)"]
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0][0], "Q(a, b)")
        self.assertEqual(matched[0][2], {"x": "a", "xy": "b"})

    def test_unbound_placeholders_stay_verbatim(self):
        """Substituting a subset of variables must leave others untouched."""
        reasoner = Reasoner()
        result = reasoner._substitute("Q(?x, ?xy)", {"x": "a"})
        self.assertEqual(result, "Q(a, ?xy)")

    def test_rule_without_conditions_matches_nothing(self):
        """A rule with an empty conditions list must produce no matches."""
        reasoner = Reasoner()
        rule = Rule(rule_id="r", name="r", conditions=[], conclusion="Ready()")
        self.assertEqual(reasoner._match_rule(rule), [])


from semantica.reasoning import _rule_matching


class TestPureMatchingModule(unittest.TestCase):
    """Direct entry points of the extracted pure helper module."""

    def test_substitute_variables(self):
        self.assertEqual(
            _rule_matching.substitute_variables("Q(?x, ?y)", {"x": "a", "y": "b"}),
            "Q(a, b)",
        )

    def test_substitute_variables_prefix_safe(self):
        self.assertEqual(
            _rule_matching.substitute_variables("Q(?x, ?xy)", {"x": "a"}),
            "Q(a, ?xy)",
        )

    def test_match_pattern_returns_bindings(self):
        bindings = _rule_matching.match_pattern(
            "P(?x, ?y)", "P(a, b)", {}, logger=Reasoner().logger
        )
        self.assertEqual(bindings, {"x": "a", "y": "b"})

    def test_match_pattern_binding_conflict(self):
        bindings = _rule_matching.match_pattern(
            "P(?x, ?y)", "P(a, a)", {"x": "b"}, logger=Reasoner().logger
        )
        self.assertIsNone(bindings)

    def test_match_rule_pure(self):
        matched = _rule_matching.match_rule(
            ["A(?x)", "B(?x)"],
            "C(?x)",
            ["A(a)", "B(a)", "B(z)"],
            pattern_matcher=_rule_matching.match_pattern,
            substituter=_rule_matching.substitute_variables,
        )
        self.assertEqual(len(matched), 1)
        conclusion, matched_facts, bindings = matched[0]
        self.assertEqual(conclusion, "C(a)")
        self.assertEqual(matched_facts, ["A(a)", "B(a)"])
        self.assertEqual(bindings, {"x": "a"})

    def test_match_rule_empty_conditions(self):
        matched = _rule_matching.match_rule(
            [], "C()", [], pattern_matcher=None, substituter=None
        )
        self.assertEqual(matched, [])


def test_match_rule_keeps_pattern_override(monkeypatch):
    from semantica.reasoning import Reasoner, Rule

    reasoner = Reasoner()
    reasoner.add_fact("A(a)")
    rule = Rule("r", "r", ["A(?x)"], "B(?x)")
    monkeypatch.setattr(reasoner, "_match_pattern", lambda *args: None)
    assert reasoner._match_rule(rule) == []


if __name__ == "__main__":
    unittest.main()

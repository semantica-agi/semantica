"""Tests for QA-style evaluators: token_f1 and normalized_exact_match."""
import pytest

from semantica.evals import registry as reg
from semantica.evals.qa_evaluators import normalize_answer


class TestNormalizeAnswer:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_answer("The Eiffel Tower!") == "eiffel tower"

    def test_deletes_punctuation_instead_of_spacing_it(self):
        # The official SQuAD recipe removes punctuation rather than replacing it
        # with a space, so an abbreviation collapses to a single token.
        assert normalize_answer("U.S.") == "us"
        assert normalize_answer("U.S.") == normalize_answer("US")

    def test_drops_articles(self):
        assert normalize_answer("a cat and an owl") == "cat and owl"

    def test_collapses_whitespace(self):
        assert normalize_answer("  hello   world  ") == "hello world"


class TestTokenF1:
    def _f1(self, actual, expected, config=None):
        return reg.get_evaluator("token_f1")(actual, expected, config=config)

    def test_perfect_match_scores_one(self):
        r = self._f1("Paris", "paris")
        assert r.score == pytest.approx(1.0)
        assert r.passed

    def test_partial_overlap_between_zero_and_one(self):
        r = self._f1("the quick brown fox", "quick brown fox jumps")
        # normalization drops "the": pred = 3 tokens, gold = 4, overlap = 3.
        precision, recall = 3 / 3, 3 / 4
        expected = 2 * precision * recall / (precision + recall)
        assert r.score == pytest.approx(expected)

    def test_no_overlap_is_zero(self):
        assert self._f1("apple", "orange").score == 0.0

    def test_multi_gold_takes_best(self):
        r = self._f1("Barack Obama", ["Obama", "Barack Obama"])
        assert r.score == pytest.approx(1.0)
        assert r.meta["best_gold"] == "Barack Obama"

    def test_normalization_makes_article_insensitive(self):
        assert self._f1("the Paris", "Paris").score == pytest.approx(1.0)

    def test_missing_expected_is_error(self):
        r = self._f1("x", None)
        assert r.meta.get("error")
        assert not r.passed

    def test_bad_expected_type_is_error(self):
        r = self._f1("x", 123)
        assert r.meta.get("error")

    def test_threshold_gates_pass(self):
        r = self._f1("quick brown fox", "quick brown fox", config={"threshold": 0.5})
        assert r.passed
        r2 = self._f1("apple", "orange", config={"threshold": 0.5})
        assert not r2.passed


class TestNormalizedExactMatch:
    def _em(self, actual, expected, config=None):
        evaluator = reg.get_evaluator("normalized_exact_match")
        return evaluator(actual, expected, config=config)

    def test_match_after_normalization(self):
        r = self._em("The University of Oxford.", "university of oxford")
        assert r.passed and r.score == 1.0

    def test_mismatch(self):
        r = self._em("Oxford", "Cambridge")
        assert not r.passed and r.score == 0.0

    def test_any_gold_matches(self):
        assert self._em("NYC", ["New York City", "NYC"]).passed

    def test_missing_expected_is_error(self):
        assert self._em("x", None).meta.get("error")


class TestRegistration:
    def test_both_are_registered(self):
        names = reg.list_evaluators()
        assert "token_f1" in names
        assert "normalized_exact_match" in names

    def test_runner_accepts_token_f1(self):
        from semantica.evals import evaluate

        summary = evaluate(
            [{"id": "a", "expected": ["Paris"], "actual": "the Paris"}],
            evaluators=["token_f1"],
        )
        assert summary.cases[0].status == "pass"
        assert summary.cases[0].metrics["token_f1"].score == pytest.approx(1.0)

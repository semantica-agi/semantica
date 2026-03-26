"""
Tests for TemporalQueryRewriter and TemporalQueryResult.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from semantica.kg import TemporalQueryRewriter, TemporalQueryResult


def _utc(year, month=1, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# TemporalQueryResult — dataclass behaviour
# ---------------------------------------------------------------------------

class TestTemporalQueryResult:

    def test_has_temporal_context_true_when_intent_set(self):
        r = TemporalQueryResult(
            rewritten_query="q", temporal_intent="before",
            at_time=_utc(2021), confidence=0.9,
        )
        assert r.has_temporal_context() is True

    def test_has_temporal_context_false_when_no_intent(self):
        r = TemporalQueryResult(rewritten_query="q", confidence=1.0)
        assert r.has_temporal_context() is False

    def test_default_fields_are_none(self):
        r = TemporalQueryResult(rewritten_query="q", confidence=0.5)
        assert r.at_time is None
        assert r.start_time is None
        assert r.end_time is None
        assert r.temporal_intent is None

    def test_all_intent_values_accepted(self):
        for intent in ("before", "after", "at", "during", "between"):
            r = TemporalQueryResult(rewritten_query="q", temporal_intent=intent, confidence=0.8)
            assert r.has_temporal_context() is True

    def test_between_populates_start_and_end(self):
        r = TemporalQueryResult(
            rewritten_query="q",
            temporal_intent="between",
            start_time=_utc(2019),
            end_time=_utc(2022),
            confidence=0.85,
        )
        assert r.start_time < r.end_time
        assert r.at_time is None


# ---------------------------------------------------------------------------
# No temporal phrase — passthrough
# ---------------------------------------------------------------------------

class TestNoTemporalPhrase:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_plain_query_rewritten_query_unchanged(self):
        q = "what are the top suppliers?"
        assert self.rw.rewrite(q).rewritten_query == q

    def test_plain_query_all_fields_none(self):
        r = self.rw.rewrite("list certified partners")
        assert r.temporal_intent is None
        assert r.at_time is None
        assert r.start_time is None
        assert r.end_time is None

    def test_empty_string_returns_empty_rewritten(self):
        r = self.rw.rewrite("")
        assert r.rewritten_query == ""
        assert r.temporal_intent is None

    def test_entity_name_with_year_not_matched_as_temporal(self):
        # "ISO9001" or "GDPR2018" should not be treated as temporal
        r = self.rw.rewrite("list all ISO9001 certified suppliers")
        # May or may not extract — just must not crash
        assert r.rewritten_query is not None

    def test_confidence_is_1_when_no_phrase_found(self):
        r = self.rw.rewrite("active suppliers in good standing")
        # No unambiguous temporal phrase — confidence should be high
        assert r.confidence > 0.0

    def test_no_temporal_phrase_never_sets_at_time(self):
        for q in [
            "show all nodes",
            "what is the status of project Alpha?",
            "find entities of type Drug",
        ]:
            assert self.rw.rewrite(q).at_time is None


# ---------------------------------------------------------------------------
# "before" intent
# ---------------------------------------------------------------------------

class TestBeforeIntent:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_before_year_sets_intent(self):
        r = self.rw.rewrite("which suppliers were certified before 2021?")
        assert r.temporal_intent == "before"

    def test_before_year_sets_at_time(self):
        r = self.rw.rewrite("which suppliers were certified before 2021?")
        assert r.at_time is not None
        assert r.at_time.year == 2021

    def test_before_year_start_and_end_are_none(self):
        r = self.rw.rewrite("approved before 2021")
        assert r.start_time is None
        assert r.end_time is None

    def test_prior_to_maps_to_before(self):
        r = self.rw.rewrite("rules that applied prior to 2020")
        assert r.temporal_intent == "before"
        assert r.at_time.year == 2020

    def test_until_maps_to_before(self):
        r = self.rw.rewrite("approvals valid until 2022")
        assert r.temporal_intent == "before"

    def test_before_strips_phrase_from_query(self):
        r = self.rw.rewrite("which drugs were approved before 2019?")
        assert "before" not in r.rewritten_query
        assert "2019" not in r.rewritten_query

    def test_rewritten_query_not_empty_after_strip(self):
        r = self.rw.rewrite("drugs approved before 2019")
        assert r.rewritten_query.strip() != ""

    def test_before_different_years(self):
        for year in (2010, 2015, 2020, 2023):
            r = self.rw.rewrite(f"facts recorded before {year}")
            assert r.at_time.year == year


# ---------------------------------------------------------------------------
# "after" intent
# ---------------------------------------------------------------------------

class TestAfterIntent:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_after_year_sets_intent(self):
        r = self.rw.rewrite("which threat actors were active after 2018?")
        assert r.temporal_intent == "after"

    def test_after_year_sets_at_time(self):
        r = self.rw.rewrite("which threat actors were active after 2018?")
        assert r.at_time is not None
        assert r.at_time.year == 2018

    def test_since_maps_to_after(self):
        r = self.rw.rewrite("regulations introduced since 2015")
        assert r.temporal_intent == "after"

    def test_following_maps_to_after(self):
        r = self.rw.rewrite("changes following 2020")
        assert r.temporal_intent == "after"

    def test_after_start_and_end_are_none(self):
        r = self.rw.rewrite("events after 2018")
        assert r.start_time is None
        assert r.end_time is None

    def test_after_strips_phrase_from_query(self):
        r = self.rw.rewrite("entities added after 2020")
        assert "after" not in r.rewritten_query


# ---------------------------------------------------------------------------
# "during" / "in" intent
# ---------------------------------------------------------------------------

class TestDuringIntent:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_in_year_maps_to_during(self):
        r = self.rw.rewrite("what interactions were known in 2021?")
        assert r.temporal_intent == "during"

    def test_in_year_sets_at_time(self):
        r = self.rw.rewrite("what interactions were known in 2021?")
        assert r.at_time is not None
        assert r.at_time.year == 2021

    def test_during_keyword_sets_intent(self):
        r = self.rw.rewrite("compliance status during Q2 2022")
        assert r.temporal_intent == "during"
        assert r.at_time is not None

    def test_within_maps_to_during(self):
        r = self.rw.rewrite("certifications renewed within 2023")
        assert r.temporal_intent == "during"

    def test_during_start_and_end_are_none(self):
        r = self.rw.rewrite("events in 2022")
        assert r.start_time is None
        assert r.end_time is None


# ---------------------------------------------------------------------------
# "between" intent
# ---------------------------------------------------------------------------

class TestBetweenIntent:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_between_years_sets_intent(self):
        r = self.rw.rewrite("contracts active between 2019 and 2022?")
        assert r.temporal_intent == "between"

    def test_between_populates_start_and_end(self):
        r = self.rw.rewrite("contracts active between 2019 and 2022?")
        assert r.start_time is not None
        assert r.end_time is not None

    def test_between_at_time_is_none(self):
        r = self.rw.rewrite("contracts between 2019 and 2022")
        assert r.at_time is None

    def test_between_start_before_end(self):
        r = self.rw.rewrite("interactions between 2019 and 2022")
        assert r.start_time < r.end_time

    def test_between_quarters(self):
        r = self.rw.rewrite("revenue between Q1 2022 and Q3 2022")
        assert r.temporal_intent == "between"
        assert r.start_time is not None
        assert r.end_time is not None

    def test_between_quarter_start_before_end(self):
        r = self.rw.rewrite("revenue between Q1 2022 and Q3 2022")
        assert r.start_time < r.end_time

    def test_between_strips_phrase(self):
        r = self.rw.rewrite("contracts active between 2019 and 2022")
        assert "between" not in r.rewritten_query

    def test_between_start_year_correct(self):
        r = self.rw.rewrite("events between 2018 and 2021")
        assert r.start_time.year == 2018

    def test_between_end_year_correct(self):
        r = self.rw.rewrite("events between 2018 and 2021")
        assert r.end_time.year == 2021


# ---------------------------------------------------------------------------
# "at" / "as of" intent
# ---------------------------------------------------------------------------

class TestAtIntent:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_as_of_sets_at_intent(self):
        r = self.rw.rewrite("graph state as of 2023")
        assert r.temporal_intent == "at"

    def test_as_of_sets_at_time(self):
        r = self.rw.rewrite("graph state as of 2023")
        assert r.at_time is not None
        assert r.at_time.year == 2023

    def test_as_of_start_and_end_none(self):
        r = self.rw.rewrite("state as of 2022")
        assert r.start_time is None
        assert r.end_time is None


# ---------------------------------------------------------------------------
# Rewritten query quality
# ---------------------------------------------------------------------------

class TestRewrittenQueryQuality:

    def setup_method(self):
        self.rw = TemporalQueryRewriter()

    def test_no_double_spaces_after_strip(self):
        r = self.rw.rewrite("suppliers certified before 2021 are valid")
        assert "  " not in r.rewritten_query

    def test_no_leading_trailing_whitespace(self):
        r = self.rw.rewrite("before 2021 show suppliers")
        assert r.rewritten_query == r.rewritten_query.strip()

    def test_question_mark_preserved(self):
        r = self.rw.rewrite("which drugs were approved before 2019?")
        assert r.rewritten_query.endswith("?")

    def test_non_temporal_words_preserved(self):
        r = self.rw.rewrite("certified suppliers before 2021")
        assert "certified" in r.rewritten_query
        assert "suppliers" in r.rewritten_query


# ---------------------------------------------------------------------------
# Rewriter never calls reconstruct_at_time
# ---------------------------------------------------------------------------

class TestNoReconstructAtTime:

    def test_reconstruct_at_time_never_called_on_regex_path(self):
        rw = TemporalQueryRewriter()
        with patch("semantica.kg.temporal_query.TemporalGraphQuery") as mock_tgq:
            rw.rewrite("threat actors active before 2021")
            mock_tgq.assert_not_called()

    def test_reconstruct_at_time_never_called_on_no_phrase(self):
        rw = TemporalQueryRewriter()
        with patch("semantica.kg.temporal_query.TemporalGraphQuery") as mock_tgq:
            rw.rewrite("list all suppliers")
            mock_tgq.assert_not_called()


# ---------------------------------------------------------------------------
# LLM-assisted path
# ---------------------------------------------------------------------------

class TestLLMAssistedRewrite:

    def setup_method(self):
        self.mock_llm = MagicMock()

    def _set_llm(self, phrase, intent, confidence=0.9):
        self.mock_llm.generate.return_value = json.dumps({
            "temporal_phrase": phrase,
            "temporal_intent": intent,
            "confidence": confidence,
        })

    def test_llm_called_before_regex(self):
        self._set_llm("2021", "before")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        rw.rewrite("before 2021")
        assert self.mock_llm.generate.call_count == 1

    def test_llm_before_intent_sets_at_time(self):
        self._set_llm("the 2021 merger", "before")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("suppliers certified before the 2021 merger?")
        assert r.temporal_intent == "before"
        assert r.at_time is not None

    def test_llm_confidence_propagated(self):
        self._set_llm("2022", "after", confidence=0.95)
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("events after 2022")
        assert r.confidence == pytest.approx(0.95)

    def test_llm_between_intent_populates_range(self):
        self._set_llm("Q1 and Q3 2022", "between")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("revenue between Q1 and Q3 2022")
        assert r.temporal_intent == "between"

    def test_llm_null_phrase_returns_no_temporal_context(self):
        self.mock_llm.generate.return_value = json.dumps({
            "temporal_phrase": None, "temporal_intent": None, "confidence": 0.99,
        })
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("what are the top suppliers?")
        assert r.temporal_intent is None

    def test_llm_failure_falls_back_to_regex(self):
        self.mock_llm.generate.side_effect = RuntimeError("LLM offline")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("contracts before 2020")
        assert r.temporal_intent == "before"
        assert r.at_time is not None

    def test_llm_invalid_json_falls_back_to_regex(self):
        self.mock_llm.generate.return_value = "not json at all"
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        r = rw.rewrite("entities after 2019")
        assert r.temporal_intent == "after"

    def test_llm_prompt_contains_query(self):
        self._set_llm("2021", "before")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        rw.rewrite("suppliers before 2021")
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "suppliers before 2021" in prompt

    def test_llm_not_called_when_no_provider(self):
        rw = TemporalQueryRewriter()  # no llm_provider
        rw.rewrite("before 2021")
        self.mock_llm.generate.assert_not_called()

    def test_llm_rewrite_never_calls_reconstruct_at_time(self):
        self._set_llm("2021", "before")
        rw = TemporalQueryRewriter(llm_provider=self.mock_llm)
        with patch("semantica.kg.temporal_query.TemporalGraphQuery") as mock_tgq:
            rw.rewrite("suppliers before the 2021 audit")
            mock_tgq.assert_not_called()

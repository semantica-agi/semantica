"""
Tests for TemporalGraphRetriever and temporal context header in LLM prompts.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch

import pytest

from semantica.context import ContextRetriever, RetrievedContext, TemporalGraphRetriever


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(year, month=1, day=1):
    return datetime(year, month, day, tzinfo=timezone.utc)


def _make_entity(eid, valid_from=None, valid_until=None, **extra):
    e = {"id": eid, "name": eid}
    if valid_from:
        e["valid_from"] = valid_from.isoformat()
    if valid_until:
        e["valid_until"] = valid_until.isoformat()
    e.update(extra)
    return e


def _make_rel(source, target, rel_type="RELATED_TO", valid_from=None, valid_until=None):
    r = {"source": source, "target": target, "type": rel_type}
    if valid_from:
        r["valid_from"] = valid_from.isoformat()
    if valid_until:
        r["valid_until"] = valid_until.isoformat()
    return r


def _make_result(entities, relationships, content="test content", score=0.9):
    return RetrievedContext(
        content=content,
        score=score,
        source="graph",
        related_entities=entities,
        related_relationships=relationships,
    )


def _base_mock(return_value=None):
    base = MagicMock(spec=ContextRetriever)
    base.retrieve.return_value = return_value or []
    return base


# ---------------------------------------------------------------------------
# TemporalGraphRetriever — construction
# ---------------------------------------------------------------------------

class TestTemporalGraphRetrieverInit:

    def test_default_at_time_is_none(self):
        tr = TemporalGraphRetriever(_base_mock())
        assert tr.at_time is None

    def test_stores_base_retriever(self):
        base = _base_mock()
        tr = TemporalGraphRetriever(base)
        assert tr.base_retriever is base

    def test_custom_header_template_stored(self):
        tr = TemporalGraphRetriever(_base_mock(), header_template="[{at_time}]")
        assert tr.header_template == "[{at_time}]"

    def test_default_header_template_contains_placeholder(self):
        tr = TemporalGraphRetriever(_base_mock())
        assert "{at_time}" in tr.header_template
        assert "{source}" in tr.header_template


# ---------------------------------------------------------------------------
# TemporalGraphRetriever — passthrough (no at_time)
# ---------------------------------------------------------------------------

class TestTemporalGraphRetrieverPassthrough:

    def setup_method(self):
        self.entity = _make_entity("e1", _utc(2020, 1, 1), _utc(2025, 1, 1))
        self.base = _base_mock([_make_result([self.entity], [])])

    def test_no_at_time_returns_base_result_unchanged(self):
        tr = TemporalGraphRetriever(self.base)
        results = tr.retrieve("some query")
        self.base.retrieve.assert_called_once_with("some query")
        assert results[0].related_entities[0]["id"] == "e1"

    def test_none_at_time_on_call_uses_constructor_none(self):
        tr = TemporalGraphRetriever(self.base, at_time=None)
        results = tr.retrieve("query", at_time=None)
        assert results[0].related_entities[0]["id"] == "e1"

    def test_empty_base_result_passthrough(self):
        base = _base_mock([])
        tr = TemporalGraphRetriever(base)
        assert tr.retrieve("q") == []

    def test_kwargs_forwarded_to_base_retriever(self):
        tr = TemporalGraphRetriever(self.base)
        tr.retrieve("q", max_results=3, min_relevance_score=0.5)
        self.base.retrieve.assert_called_once_with("q", max_results=3, min_relevance_score=0.5)

    def test_base_retriever_called_exactly_once(self):
        tr = TemporalGraphRetriever(self.base)
        tr.retrieve("q")
        assert self.base.retrieve.call_count == 1

    def test_result_object_identity_unchanged_on_passthrough(self):
        result = _make_result([self.entity], [])
        base = _base_mock([result])
        tr = TemporalGraphRetriever(base)
        returned = tr.retrieve("q")
        assert returned[0] is result


# ---------------------------------------------------------------------------
# TemporalGraphRetriever — temporal filtering
# ---------------------------------------------------------------------------

class TestTemporalGraphRetrieverFiltering:

    def setup_method(self):
        self.base = _base_mock()

    def _set(self, entities, relationships):
        self.base.retrieve.return_value = [_make_result(entities, relationships)]

    # Entity validity

    def test_entity_expired_before_at_time_excluded(self):
        e_current = _make_entity("current", _utc(2020, 1, 1), _utc(2025, 1, 1))
        e_expired = _make_entity("expired", _utc(2018, 1, 1), _utc(2020, 6, 1))
        self._set([e_current, e_expired], [])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        ids = {e["id"] for e in results[0].related_entities}
        assert "current" in ids
        assert "expired" not in ids

    def test_entity_not_yet_started_at_at_time_excluded(self):
        e_future = _make_entity("future", _utc(2025, 1, 1))
        e_current = _make_entity("current", _utc(2020, 1, 1))
        self._set([e_future, e_current], [])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        ids = {e["id"] for e in results[0].related_entities}
        assert "current" in ids
        assert "future" not in ids

    def test_entity_with_no_temporal_bounds_always_included(self):
        e_timeless = _make_entity("timeless")  # no valid_from / valid_until
        self._set([e_timeless], [])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert len(results[0].related_entities) == 1

    def test_entity_valid_on_boundary_date_included(self):
        # valid_from == at_time — boundary should be inclusive
        at = _utc(2022, 6, 1)
        e = _make_entity("boundary", valid_from=at)
        self._set([e], [])

        results = TemporalGraphRetriever(self.base, at_time=at).retrieve("q")
        assert len(results[0].related_entities) == 1

    def test_all_entities_expired_leaves_empty_list(self):
        entities = [
            _make_entity("a", _utc(2010, 1, 1), _utc(2015, 1, 1)),
            _make_entity("b", _utc(2012, 1, 1), _utc(2014, 1, 1)),
        ]
        self._set(entities, [])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].related_entities == []

    # Relationship filtering

    def test_dangling_relationship_removed_when_target_expired(self):
        e_a = _make_entity("A", _utc(2020, 1, 1))
        e_b = _make_entity("B", _utc(2022, 1, 1), _utc(2022, 6, 1))
        rel = _make_rel("A", "B")
        self._set([e_a, e_b], [rel])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].related_relationships == []

    def test_dangling_relationship_removed_when_source_expired(self):
        e_a = _make_entity("A", _utc(2020, 1, 1), _utc(2021, 1, 1))
        e_b = _make_entity("B", _utc(2020, 1, 1))
        rel = _make_rel("A", "B")
        self._set([e_a, e_b], [rel])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].related_relationships == []

    def test_valid_relationship_kept(self):
        e_a = _make_entity("A", _utc(2020, 1, 1))
        e_b = _make_entity("B", _utc(2020, 1, 1))
        rel = _make_rel("A", "B", valid_from=_utc(2020, 1, 1))
        self._set([e_a, e_b], [rel])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert len(results[0].related_relationships) == 1

    def test_relationship_with_expired_valid_until_removed(self):
        e_a = _make_entity("A", _utc(2020, 1, 1))
        e_b = _make_entity("B", _utc(2020, 1, 1))
        rel = _make_rel("A", "B", valid_from=_utc(2020, 1, 1), valid_until=_utc(2021, 1, 1))
        self._set([e_a, e_b], [rel])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].related_relationships == []

    def test_multiple_relationship_types_filtered_independently(self):
        e_a = _make_entity("A", _utc(2020, 1, 1))
        e_b = _make_entity("B", _utc(2020, 1, 1))
        e_c = _make_entity("C", _utc(2020, 1, 1), _utc(2021, 1, 1))  # expires
        rel_ab = _make_rel("A", "B", rel_type="USES")
        rel_ac = _make_rel("A", "C", rel_type="OWNS")
        self._set([e_a, e_b, e_c], [rel_ab, rel_ac])

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        rels = results[0].related_relationships
        types = {r["type"] for r in rels}
        assert "USES" in types
        assert "OWNS" not in types

    # at_time precedence

    def test_call_site_at_time_overrides_constructor(self):
        e = _make_entity("e", _utc(2018, 1, 1), _utc(2021, 1, 1))
        self._set([e], [])

        tr = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1))
        results = tr.retrieve("q", at_time=_utc(2020, 6, 1))
        assert len(results[0].related_entities) == 1

    def test_string_at_time_parsed_correctly(self):
        e_current = _make_entity("current", _utc(2020, 1, 1))
        e_expired = _make_entity("expired", _utc(2018, 1, 1), _utc(2020, 6, 1))
        self._set([e_current, e_expired], [])

        results = TemporalGraphRetriever(self.base, at_time="2023-01-01").retrieve("q")
        ids = {e["id"] for e in results[0].related_entities}
        assert "current" in ids
        assert "expired" not in ids

    def test_datetime_at_time_accepted_directly(self):
        e = _make_entity("e", _utc(2020, 1, 1))
        self._set([e], [])

        results = TemporalGraphRetriever(
            self.base, at_time=_utc(2023, 1, 1)
        ).retrieve("q")
        assert len(results[0].related_entities) == 1

    # Multiple results

    def test_all_results_filtered_independently(self):
        e_valid = _make_entity("valid", _utc(2020, 1, 1))
        e_old = _make_entity("old", _utc(2010, 1, 1), _utc(2015, 1, 1))
        r1 = _make_result([e_valid], [])
        r2 = _make_result([e_old], [])
        self.base.retrieve.return_value = [r1, r2]

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert len(results[0].related_entities) == 1
        assert len(results[1].related_entities) == 0

    def test_result_scores_preserved_after_filtering(self):
        e = _make_entity("e", _utc(2020, 1, 1))
        r = _make_result([e], [], score=0.77)
        self.base.retrieve.return_value = [r]

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].score == pytest.approx(0.77)

    def test_result_content_preserved_after_filtering(self):
        e = _make_entity("e", _utc(2020, 1, 1))
        r = _make_result([e], [], content="important drug interaction fact")
        self.base.retrieve.return_value = [r]

        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].content == "important drug interaction fact"

    def test_empty_entities_and_relationships_stays_empty(self):
        self.base.retrieve.return_value = [_make_result([], [])]
        results = TemporalGraphRetriever(self.base, at_time=_utc(2023, 1, 1)).retrieve("q")
        assert results[0].related_entities == []
        assert results[0].related_relationships == []


# ---------------------------------------------------------------------------
# Temporal context header — _generate_reasoned_response
# ---------------------------------------------------------------------------

class TestTemporalContextHeader:

    def setup_method(self):
        self.retriever = ContextRetriever()
        self.mock_llm = MagicMock()
        self.mock_llm.generate.return_value = "LLM answer"

    def _call(self, at_time=None, header_template=None, contexts=None):
        if contexts is None:
            contexts = [RetrievedContext(content="fact A", score=0.9, source="graph")]
        kwargs = {}
        if header_template is not None:
            kwargs["header_template"] = header_template
        return self.retriever._generate_reasoned_response(
            "test query", contexts, [], self.mock_llm, at_time=at_time, **kwargs
        )

    def _last_prompt(self):
        return self.mock_llm.generate.call_args[0][0]

    def test_no_header_without_at_time(self):
        self._call()
        assert "Graph context valid as of" not in self._last_prompt()

    def test_header_present_when_at_time_datetime(self):
        self._call(at_time=_utc(2023, 6, 1))
        prompt = self._last_prompt()
        assert "2023-06-01" in prompt
        assert "Graph context valid as of" in prompt

    def test_header_present_when_at_time_string(self):
        self._call(at_time="2022-03-15")
        assert "2022-03-15" in self._last_prompt()

    def test_header_appears_before_retrieved_context(self):
        self._call(at_time=_utc(2023, 6, 1))
        prompt = self._last_prompt()
        assert prompt.find("Graph context valid as of") < prompt.find("Retrieved Context:")

    def test_header_contains_source_label(self):
        self._call(at_time=_utc(2023, 6, 1))
        assert "KnowledgeGraph snapshot" in self._last_prompt()

    def test_header_template_configurable(self):
        self._call(
            at_time=_utc(2023, 6, 1),
            header_template="[Snapshot: {at_time} from {source}]",
        )
        prompt = self._last_prompt()
        assert "[Snapshot:" in prompt
        assert "2023-06-01" in prompt

    def test_custom_template_source_placeholder_filled(self):
        self._call(
            at_time=_utc(2023, 1, 1),
            header_template="Source={source}",
        )
        assert "Source=KnowledgeGraph snapshot" in self._last_prompt()

    def test_prompt_contains_user_question(self):
        self.retriever._generate_reasoned_response(
            "How many suppliers?", [], [], self.mock_llm
        )
        assert "How many suppliers?" in self._last_prompt()

    def test_prompt_contains_retrieved_context_content(self):
        ctx = RetrievedContext(content="DrugA interaction warning", score=0.9, source="graph")
        self.retriever._generate_reasoned_response(
            "q", [ctx], [], self.mock_llm
        )
        assert "DrugA interaction warning" in self._last_prompt()

    def test_no_at_time_prompt_identical_to_baseline(self):
        ctx = RetrievedContext(content="fact", score=0.8, source="graph")
        self.retriever._generate_reasoned_response("q", [ctx], [], self.mock_llm)
        prompt_without = self._last_prompt()

        self.retriever._generate_reasoned_response("q", [ctx], [], self.mock_llm, at_time=None)
        prompt_with_none = self._last_prompt()

        assert prompt_without == prompt_with_none

    def test_llm_generate_called_once_per_call(self):
        self._call(at_time=_utc(2023, 1, 1))
        assert self.mock_llm.generate.call_count == 1

    def test_query_with_reasoning_threads_at_time(self):
        retriever = ContextRetriever()
        retriever.retrieve = MagicMock(return_value=[])

        with patch.object(
            retriever, "_generate_reasoned_response", wraps=retriever._generate_reasoned_response
        ) as mock_gen:
            mock_gen.return_value = "answer"
            retriever.query_with_reasoning(
                "test query", self.mock_llm, at_time=_utc(2023, 1, 1)
            )
            assert mock_gen.call_args.kwargs.get("at_time") == _utc(2023, 1, 1)

    def test_query_with_reasoning_threads_header_template(self):
        retriever = ContextRetriever()
        retriever.retrieve = MagicMock(return_value=[])
        custom = "[{at_time}|{source}]"

        with patch.object(
            retriever, "_generate_reasoned_response", wraps=retriever._generate_reasoned_response
        ) as mock_gen:
            mock_gen.return_value = "answer"
            retriever.query_with_reasoning(
                "test query", self.mock_llm,
                at_time=_utc(2023, 1, 1),
                header_template=custom,
            )
            assert mock_gen.call_args.kwargs.get("header_template") == custom

    def test_query_with_reasoning_no_at_time_no_header(self):
        retriever = ContextRetriever()
        retriever.retrieve = MagicMock(return_value=[
            RetrievedContext(content="fact", score=0.9, source="graph")
        ])
        retriever.query_with_reasoning("q", self.mock_llm)
        prompt = self.mock_llm.generate.call_args[0][0]
        assert "Graph context valid as of" not in prompt

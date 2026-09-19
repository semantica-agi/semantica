"""Regression tests for LLMExtraction enhancement response parsing.

These tests would ALL FAIL against the old stub implementation because
_parse_entity_response / _parse_relation_response used to ignore the
LLM response entirely.  They pass after the fix.

Coverage
--------
Entity enhancement
  1.  LLM updates an existing entity's label
  2.  LLM updates an existing entity's confidence
  3.  LLM adds a brand-new entity; span is located in source text
  4.  LLM adds a new entity absent from the source text → span (0, 0)
  5.  Empty LLM response preserves originals without data loss
  6.  Provider failure falls back gracefully
  7.  enhanced_by / model metadata always present (updated, new, untouched)
  8.  Entities not mentioned by the LLM are preserved unchanged
  9.  Repeated mentions at different offsets are ALL updated
  10. No duplicate entities when LLM repeats the same text

Relation enhancement
  11. LLM corrects an existing relation's predicate (subject+object identity)
  12. LLM updates an existing relation's confidence
  13. LLM adds a new relation
  14. Empty LLM response preserves originals
  15. Provider failure falls back gracefully
  16. enhanced_by / model metadata always present (updated, new, untouched)
  17. Relations not mentioned by the LLM are preserved unchanged
  18. No duplicate relations when LLM repeats the same pair
  19. Multiple relations with same endpoints but different predicates are ALL updated
  20. New relation endpoint resolves to canonical entity from pool
  21. Unresolvable endpoint becomes synthetic UNKNOWN

Temperature propagation
  22. temperature=None is forwarded as-is to generate_typed
  23. Explicit temperature is forwarded correctly

Case-insensitive matching
  24. Entity text match is case-insensitive
  25. Relation subject/object match is case-insensitive
"""

import pytest
from unittest.mock import MagicMock

from semantica.semantic_extract.llm_extraction import LLMExtraction
from semantica.semantic_extract.schemas import EntitiesResponse, EntityOut, RelationsResponse, RelationOut
from semantica.semantic_extract.types import Entity, Relation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(text: str, label: str, confidence: float = 0.8,
                 start: int = 0, end: int = 0) -> Entity:
    end = end or len(text)
    return Entity(
        text=text, label=label,
        start_char=start, end_char=end,
        confidence=confidence, metadata={},
    )


def _make_relation(
    subj_text: str, pred: str, obj_text: str,
    confidence: float = 0.8,
) -> Relation:
    return Relation(
        subject=_make_entity(subj_text, "ORG"),
        predicate=pred,
        object=_make_entity(obj_text, "PERSON"),
        confidence=confidence,
        context="",
        metadata={},
    )


def _make_extractor(llm_response, *, temperature=None) -> LLMExtraction:
    """Return an LLMExtraction instance whose provider.generate_typed returns
    *llm_response* without hitting any real API."""
    extractor = LLMExtraction.__new__(LLMExtraction)
    extractor.provider_name = "openai"
    extractor.model = "gpt-4"
    extractor.temperature = temperature
    extractor.config = {}

    from semantica.utils.logging import get_logger
    extractor.logger = get_logger("test_llm_enhancement")

    from semantica.utils.progress_tracker import get_progress_tracker
    extractor.progress_tracker = get_progress_tracker()
    extractor.progress_tracker.enabled = False

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.generate_typed.return_value = llm_response
    extractor.provider = mock_provider

    return extractor


def _make_failing_extractor() -> LLMExtraction:
    extractor = LLMExtraction.__new__(LLMExtraction)
    extractor.provider_name = "openai"
    extractor.model = "gpt-4"
    extractor.temperature = None
    extractor.config = {}

    from semantica.utils.logging import get_logger
    extractor.logger = get_logger("test_llm_enhancement")
    from semantica.utils.progress_tracker import get_progress_tracker
    extractor.progress_tracker = get_progress_tracker()
    extractor.progress_tracker.enabled = False

    mock_provider = MagicMock()
    mock_provider.is_available.return_value = True
    mock_provider.generate_typed.side_effect = Exception("simulated failure")
    extractor.provider = mock_provider
    return extractor


# ---------------------------------------------------------------------------
# Entity enhancement — label and confidence updates
# ---------------------------------------------------------------------------

class TestEnhanceEntitiesLabelUpdate:
    """Test 1 – LLM corrects an existing entity's label."""

    def test_label_is_updated(self):
        original = [_make_entity("Apple Inc.", "PRODUCT")]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("Apple Inc. is a company.", original)

        assert len(result) == 1
        assert result[0].label == "ORG", "LLM-corrected label must be applied"


class TestEnhanceEntitiesConfidenceUpdate:
    """Test 2 – LLM updates an existing entity's confidence score."""

    def test_confidence_is_updated(self):
        original = [_make_entity("Steve Jobs", "PERSON", confidence=0.5)]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Steve Jobs", label="PERSON", confidence=0.99),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("Steve Jobs founded Apple.", original)

        assert result[0].confidence == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# Entity enhancement — new entity span recovery
# ---------------------------------------------------------------------------

class TestEnhanceEntitiesNewEntitySpan:
    """Tests 3–4 — new entities get a located span when the text allows it."""

    def test_new_entity_span_located_in_text(self):
        """Test 3: new entity present in source text receives correct span."""
        source = "Apple Inc. was founded by Steve Jobs in 1976."
        original = [_make_entity("Apple Inc.", "ORG", start=0, end=10)]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
            EntityOut(text="Steve Jobs", label="PERSON", confidence=0.95),  # new
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities(source, original)

        new_ent = next(e for e in result if e.text == "Steve Jobs")
        expected_start = source.find("Steve Jobs")
        assert new_ent.start_char == expected_start, (
            "New entity must be located at its actual position in the source text"
        )
        assert new_ent.end_char == expected_start + len("Steve Jobs")

    def test_new_entity_absent_from_text_gets_zero_span(self):
        """Test 4: new entity NOT in source text gets (0, 0) sentinel."""
        source = "Apple Inc. is a technology company."
        original = [_make_entity("Apple Inc.", "ORG", start=0, end=10)]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Completely Absent Corp", label="ORG", confidence=0.7),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities(source, original)

        absent = next(e for e in result if e.text == "Completely Absent Corp")
        assert absent.start_char == 0
        assert absent.end_char == 0, (
            "Entity not present in source text must get (0, 0) sentinel span"
        )

    def test_new_entity_later_in_text_gets_correct_span(self):
        """New entity that occurs later in the document (not at position 0)
        must receive the correct offset, not (0, 0)."""
        source = "The Board of Directors announced that Tim Cook will lead Apple."
        original = [_make_entity("Apple", "ORG", start=source.find("Apple"), end=source.find("Apple") + 5)]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Tim Cook", label="PERSON", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities(source, original)

        tim = next(e for e in result if e.text == "Tim Cook")
        expected = source.find("Tim Cook")
        assert tim.start_char == expected
        assert tim.end_char == expected + len("Tim Cook")


# ---------------------------------------------------------------------------
# Entity enhancement — empty response, fallback, metadata
# ---------------------------------------------------------------------------

class TestEnhanceEntitiesEmptyResponse:
    """Test 5 – Empty LLM response preserves the original list."""

    def test_empty_response_preserves_originals(self):
        original = [
            _make_entity("Apple Inc.", "ORG"),
            _make_entity("Tim Cook", "PERSON"),
        ]
        llm_resp = EntitiesResponse(entities=[])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("Apple Inc.", original)

        assert len(result) == 2
        texts = [e.text for e in result]
        assert "Apple Inc." in texts
        assert "Tim Cook" in texts


class TestEnhanceEntitiesMalformedResponse:
    """Test 6 – Provider raises; method falls back to original entities."""

    def test_fallback_on_provider_error(self):
        original = [_make_entity("Apple Inc.", "ORG")]
        extractor = _make_failing_extractor()
        result = extractor.enhance_entities("Apple Inc. is a company.", original)

        assert len(result) == 1
        assert result[0].text == "Apple Inc."


class TestEnhanceEntitiesMetadata:
    """Test 7 – enhanced_by and model metadata always present."""

    def test_metadata_present_on_updated_entity(self):
        original = [_make_entity("Apple Inc.", "PRODUCT")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("text", original)

        assert result[0].metadata.get("enhanced_by") == "openai"
        assert result[0].metadata.get("model") == "gpt-4"

    def test_metadata_present_on_new_entity(self):
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
            EntityOut(text="Steve Jobs", label="PERSON", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("Apple Inc. was founded by Steve Jobs.", original)

        new_ent = next(e for e in result if e.text == "Steve Jobs")
        assert new_ent.metadata.get("enhanced_by") == "openai"
        assert new_ent.metadata.get("model") == "gpt-4"

    def test_metadata_present_on_untouched_entity(self):
        original = [
            _make_entity("Apple Inc.", "ORG"),
            _make_entity("Tim Cook", "PERSON"),
        ]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.98),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("text", original)

        tim = next(e for e in result if e.text == "Tim Cook")
        assert tim.metadata.get("enhanced_by") == "openai"


class TestEnhanceEntitiesPreservesUntouched:
    """Test 8 – Entities not referenced by the LLM are preserved unchanged."""

    def test_untouched_entity_preserved(self):
        original = [
            _make_entity("Apple Inc.", "ORG", confidence=0.9),
            _make_entity("Cupertino", "GPE", confidence=0.85),
        ]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("text", original)

        cupertino = next(e for e in result if e.text == "Cupertino")
        assert cupertino.label == "GPE"
        assert cupertino.confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Entity enhancement — repeated mentions
# ---------------------------------------------------------------------------

class TestEnhanceEntitiesRepeatedMentions:
    """Test 9 – Same entity text at different offsets are ALL updated."""

    def test_all_occurrences_updated(self):
        """Apple appears twice at different offsets; both must get the updated label."""
        source = "Apple is large. Apple is also profitable."
        original = [
            _make_entity("Apple", "PRODUCT", start=0, end=5),
            _make_entity("Apple", "PRODUCT", start=16, end=21),
        ]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities(source, original)

        assert len(result) == 2
        for ent in result:
            assert ent.label == "ORG", (
                "All occurrences of the entity text must receive the updated label"
            )

    def test_offsets_of_repeated_mentions_preserved(self):
        """Original character positions must be preserved after an update."""
        source = "Apple is large. Apple is also profitable."
        original = [
            _make_entity("Apple", "PRODUCT", start=0, end=5),
            _make_entity("Apple", "PRODUCT", start=16, end=21),
        ]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities(source, original)

        spans = sorted((e.start_char, e.end_char) for e in result)
        assert spans == [(0, 5), (16, 21)], (
            "Character offsets must be preserved during an update"
        )


# ---------------------------------------------------------------------------
# Entity enhancement — deduplication
# ---------------------------------------------------------------------------

class TestNoDuplicateEntities:
    """Test 10 – LLM repeating an entity does not duplicate it."""

    def test_no_duplicate_on_repeated_existing_entity(self):
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("text", original)

        apple_count = sum(1 for e in result if e.text == "Apple Inc.")
        assert apple_count == 1

    def test_no_duplicate_new_entity_mentioned_twice(self):
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Steve Jobs", label="PERSON", confidence=0.95),
            EntityOut(text="Steve Jobs", label="PERSON", confidence=0.93),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("Steve Jobs founded Apple Inc.", original)

        jobs_count = sum(1 for e in result if e.text == "Steve Jobs")
        assert jobs_count == 1


# ---------------------------------------------------------------------------
# Relation enhancement — predicate correction (subject+object identity)
# ---------------------------------------------------------------------------

class TestEnhanceRelationsPredicateUpdate:
    """Test 11 – Relation enhancement matching uses (subject, predicate, object) identity.

    The prompt sends all existing relations WITH their predicates to the LLM, so
    the LLM has full context.  An exact-triple match updates confidence; a
    response with a different predicate is additive (new relation appended).
    """

    def test_exact_triple_match_updates_confidence(self):
        """When the LLM returns the same (subj, pred, obj), only confidence changes."""
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs", confidence=0.5)]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.99),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        assert len(result) == 1
        assert result[0].predicate == "founded_by"
        assert result[0].confidence == pytest.approx(0.99)

    def test_new_predicate_is_appended_not_overwritten(self):
        """When the LLM returns a different predicate for an existing (subj, obj),
        the result is additive: original is preserved and new predicate is appended.
        Enhancement never silently deletes existing graph edges."""
        original = [_make_relation("Apple Inc.", "related_to", "Steve Jobs")]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations(
            "Apple Inc. was founded by Steve Jobs.", original
        )

        predicates = {r.predicate for r in result}
        assert "related_to" in predicates, "Original relation must be preserved"
        assert "founded_by" in predicates, "LLM-suggested new predicate must be appended"
        assert len(result) == 2


class TestEnhanceRelationsConfidenceUpdate:
    """Test 12 – LLM updates an existing relation's confidence."""

    def test_confidence_is_updated(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs", confidence=0.5)]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.99),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        assert result[0].confidence == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# Relation enhancement — new relation, empty, fallback, metadata
# ---------------------------------------------------------------------------

class TestEnhanceRelationsNewRelation:
    """Test 13 – LLM adds a new relation absent from the original list."""

    def test_new_relation_appended(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
            RelationOut(subject="Apple Inc.", predicate="located_in",
                        object="Cupertino", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations(
            "Apple Inc. is located in Cupertino.", original
        )

        predicates = [r.predicate for r in result]
        assert "located_in" in predicates
        assert len(result) == 2


class TestEnhanceRelationsEmptyResponse:
    """Test 14 – Empty LLM response preserves the original relations."""

    def test_empty_response_preserves_originals(self):
        original = [
            _make_relation("Apple Inc.", "founded_by", "Steve Jobs"),
            _make_relation("Steve Jobs", "ceo_of", "Apple Inc."),
        ]
        llm_resp = RelationsResponse(relations=[])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        assert len(result) == 2


class TestEnhanceRelationsMalformedResponse:
    """Test 15 – Provider raises; method falls back to original relations."""

    def test_fallback_on_provider_error(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]
        extractor = _make_failing_extractor()
        result = extractor.enhance_relations("text", original)

        assert len(result) == 1
        assert result[0].predicate == "founded_by"


class TestEnhanceRelationsMetadata:
    """Test 16 – enhanced_by and model metadata always present on relations."""

    def test_metadata_present_on_updated_relation(self):
        original = [_make_relation("Apple Inc.", "related_to", "Steve Jobs")]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        assert result[0].metadata.get("enhanced_by") == "openai"
        assert result[0].metadata.get("model") == "gpt-4"

    def test_metadata_present_on_new_relation(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
            RelationOut(subject="Apple Inc.", predicate="located_in",
                        object="Cupertino", confidence=0.9),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        new_rel = next(r for r in result if r.predicate == "located_in")
        assert new_rel.metadata.get("enhanced_by") == "openai"
        assert new_rel.metadata.get("model") == "gpt-4"

    def test_metadata_present_on_untouched_relation(self):
        original = [
            _make_relation("Apple Inc.", "founded_by", "Steve Jobs"),
            _make_relation("Steve Jobs", "ceo_of", "Apple Inc."),
        ]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        untouched = next(r for r in result if r.predicate == "ceo_of")
        assert untouched.metadata.get("enhanced_by") == "openai"


class TestEnhanceRelationsPreservesUntouched:
    """Test 17 – Relations not referenced by the LLM are preserved unchanged."""

    def test_untouched_relation_preserved(self):
        original = [
            _make_relation("Apple Inc.", "founded_by", "Steve Jobs", confidence=0.9),
            _make_relation("Steve Jobs", "ceo_of", "Apple Inc.", confidence=0.85),
        ]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        untouched = next(r for r in result if r.predicate == "ceo_of")
        assert untouched.subject.text == "Steve Jobs"
        assert untouched.confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Relation enhancement — deduplication
# ---------------------------------------------------------------------------

class TestNoDuplicateRelations:
    """Test 18 – LLM repeating the same (subject, object) pair does not
    duplicate relations."""

    def test_no_duplicate_on_repeated_pair(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        count = sum(
            1 for r in result
            if r.subject.text == "Apple Inc." and r.object.text == "Steve Jobs"
        )
        assert count == 1

    def test_no_duplicate_new_relation_mentioned_twice(self):
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="located_in",
                        object="Cupertino", confidence=0.9),
            RelationOut(subject="Apple Inc.", predicate="located_in",
                        object="Cupertino", confidence=0.85),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        new_count = sum(1 for r in result if r.object.text == "Cupertino")
        assert new_count == 1


# ---------------------------------------------------------------------------
# Relation enhancement — multiple predicates same endpoints (core correctness)
# ---------------------------------------------------------------------------

class TestMultiplePredicatesSameEndpoints:
    """Tests 19 — Multiple relations with the same endpoints but different
    predicates must remain independent.  An LLM response for one predicate
    must not overwrite the other."""

    def test_unrelated_predicate_not_overwritten(self):
        """Core correctness: Apple→founded_by→Jobs and Apple→employs→Jobs.
        LLM returns founded_by — employs must NOT be changed."""
        original = [
            _make_relation("Apple Inc.", "founded_by", "Steve Jobs"),
            _make_relation("Apple Inc.", "employs", "Steve Jobs"),
        ]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.99),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        assert len(result) == 2, "Both original relations must be preserved"
        predicates = {r.predicate for r in result}
        assert "founded_by" in predicates
        assert "employs" in predicates, (
            "employs relation must not be overwritten by the founded_by LLM response"
        )

    def test_founded_by_confidence_updated_employs_unchanged(self):
        """founded_by confidence must be updated; employs confidence must stay unchanged."""
        original = [
            _make_relation("Apple Inc.", "founded_by", "Steve Jobs", confidence=0.5),
            _make_relation("Apple Inc.", "employs", "Steve Jobs", confidence=0.8),
        ]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.99),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        founded = next(r for r in result if r.predicate == "founded_by")
        employs = next(r for r in result if r.predicate == "employs")
        assert founded.confidence == pytest.approx(0.99)
        assert employs.confidence == pytest.approx(0.8), (
            "employs confidence must be unchanged"
        )

    def test_llm_can_add_second_predicate_between_same_pair(self):
        """LLM can legitimately add a second predicate between an existing pair."""
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.99),
            RelationOut(subject="Apple Inc.", predicate="employs",
                        object="Steve Jobs", confidence=0.85),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        predicates = {r.predicate for r in result}
        assert "founded_by" in predicates
        assert "employs" in predicates
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Relation endpoint resolution
# ---------------------------------------------------------------------------

class TestNewRelationEndpointResolution:
    """Tests 20–21 — endpoint resolution for new relations."""

    def test_new_relation_reuses_canonical_subject_entity(self):
        """Test 20: New relation's subject resolves to the canonical entity."""
        apple_entity = Entity(
            text="Apple Inc.", label="ORG",
            start_char=0, end_char=10,
            confidence=0.95,
            metadata={"canonical": True},
        )
        original = [
            Relation(
                subject=apple_entity,
                predicate="founded_by",
                object=_make_entity("Steve Jobs", "PERSON"),
                confidence=0.9, context="", metadata={},
            )
        ]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="located_in",
                        object="Cupertino", confidence=0.88),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("Apple Inc. is in Cupertino.", original)

        new_rel = next(r for r in result if r.predicate == "located_in")
        assert new_rel.subject.label == "ORG"
        assert new_rel.subject.metadata.get("canonical") is True

    def test_unresolvable_endpoint_becomes_synthetic(self):
        """Test 21: Unknown endpoint becomes a synthetic UNKNOWN entity."""
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Completely Unknown Corp", predicate="partner_of",
                        object="Apple Inc.", confidence=0.7),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        new_rel = next(r for r in result if r.predicate == "partner_of")
        assert new_rel.subject.label == "UNKNOWN"
        assert new_rel.subject.metadata.get("synthetic") is True
        assert new_rel.object.label == "ORG"

    def test_synthetic_endpoint_span_located_in_source_text(self):
        """Finding #2: A synthetic endpoint that appears in the source text must
        receive its actual character span, not a fabricated (0, len(name)) value."""
        source = "The Board met. Tim Cook announced that Apple would expand."
        # Only Apple is in the original relation pool
        apple = Entity(text="Apple", label="ORG", start_char=40, end_char=45,
                       confidence=0.9, metadata={})
        original = [
            Relation(
                subject=apple,
                predicate="will_expand",
                object=_make_entity("market", "CONCEPT"),
                confidence=0.8, context="", metadata={},
            )
        ]
        llm_resp = RelationsResponse(relations=[
            # Tim Cook is NOT in the original entity pool → synthetic
            RelationOut(subject="Tim Cook", predicate="leads",
                        object="Apple", confidence=0.95),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations(source, original)

        new_rel = next(r for r in result if r.predicate == "leads")
        expected_start = source.find("Tim Cook")
        assert new_rel.subject.start_char == expected_start, (
            "Synthetic endpoint must be located at its actual position in source text"
        )
        assert new_rel.subject.end_char == expected_start + len("Tim Cook")

    def test_synthetic_endpoint_absent_from_text_gets_zero_span(self):
        """Finding #2: A synthetic endpoint that genuinely does not appear in the
        source text must receive the (0, 0) sentinel, not a fabricated span."""
        source = "Apple was founded in 1976."
        original = [_make_relation("Apple", "founded_in", "1976")]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Nonexistent Entity XYZ", predicate="partner_of",
                        object="Apple", confidence=0.7),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations(source, original)

        new_rel = next(r for r in result if r.predicate == "partner_of")
        assert new_rel.subject.start_char == 0
        assert new_rel.subject.end_char == 0, (
            "Endpoint absent from source text must receive (0, 0) sentinel span"
        )


# ---------------------------------------------------------------------------
# Temperature propagation (Finding 6)
# ---------------------------------------------------------------------------

class TestTemperaturePropagation:
    """Tests 22–23 — temperature is always forwarded to generate_typed."""

    def test_temperature_none_is_forwarded(self):
        """Test 22: temperature=None must be forwarded so providers.py can apply
        its own default (0.1 for instructor) consistently."""
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp, temperature=None)
        extractor.enhance_entities("Apple Inc.", original)

        call_kwargs = extractor.provider.generate_typed.call_args[1]
        assert "temperature" in call_kwargs, (
            "temperature must always be passed to generate_typed"
        )
        assert call_kwargs["temperature"] is None

    def test_explicit_temperature_is_forwarded(self):
        """Test 23: an explicit temperature value is forwarded unchanged."""
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp, temperature=0.7)
        extractor.enhance_entities("Apple Inc.", original)

        call_kwargs = extractor.provider.generate_typed.call_args[1]
        assert call_kwargs.get("temperature") == pytest.approx(0.7)

    def test_option_temperature_overrides_instance(self):
        """Per-call temperature option takes priority over instance temperature."""
        original = [_make_entity("Apple Inc.", "ORG")]
        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp, temperature=0.5)
        extractor.enhance_entities("Apple Inc.", original, temperature=0.2)

        call_kwargs = extractor.provider.generate_typed.call_args[1]
        assert call_kwargs.get("temperature") == pytest.approx(0.2)

    def test_temperature_none_also_forwarded_for_relations(self):
        """Temperature=None is forwarded for relation enhancement too."""
        original = [_make_relation("Apple Inc.", "founded_by", "Steve Jobs")]
        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp, temperature=None)
        extractor.enhance_relations("text", original)

        call_kwargs = extractor.provider.generate_typed.call_args[1]
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] is None


# ---------------------------------------------------------------------------
# Case-insensitive matching
# ---------------------------------------------------------------------------

class TestCaseInsensitiveMatching:
    """Tests 24–25 — matching is case-insensitive."""

    def test_entity_match_is_case_insensitive(self):
        """Test 24: entity matched case-insensitively; original casing preserved."""
        original = [_make_entity("apple inc.", "PRODUCT")]

        llm_resp = EntitiesResponse(entities=[
            EntityOut(text="Apple Inc.", label="ORG", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_entities("text", original)

        assert len(result) == 1
        assert result[0].label == "ORG"

    def test_relation_match_is_case_insensitive(self):
        """Test 25: triple matched case-insensitively; same predicate updates
        only confidence."""
        original = [_make_relation("apple inc.", "founded_by", "steve jobs",
                                   confidence=0.5)]

        llm_resp = RelationsResponse(relations=[
            RelationOut(subject="Apple Inc.", predicate="founded_by",
                        object="Steve Jobs", confidence=0.97),
        ])
        extractor = _make_extractor(llm_resp)
        result = extractor.enhance_relations("text", original)

        # Exact triple match (case-insensitive) -> update confidence, no append
        assert len(result) == 1
        assert result[0].predicate == "founded_by"
        assert result[0].confidence == pytest.approx(0.97)

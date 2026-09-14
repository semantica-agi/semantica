"""Regression tests for the packaged MCP extraction handlers."""

from types import SimpleNamespace
from unittest.mock import patch

from semantica.semantic_extract import (
    CoreferenceResolver,
    Event,
    EventDetector,
    NamedEntityRecognizer,
    RelationExtractor,
    TripletExtractor,
)
from semantica.semantic_extract.coreference_resolver import CoreferenceChain, Mention
from semantica.semantic_extract.types import Entity, Relation, Triplet
from semantica_mcp.mcp.server import call_tool


def test_extract_entities_preserves_input_text_and_serializes_entity_fields():
    """Entity offsets must remain relative to the original, untrimmed payload."""
    text = "  Alice works at Acme Corp."
    extracted = Entity("Acme Corp", "ORG", 17, 26, confidence=0.7)

    with patch.object(
        NamedEntityRecognizer, "extract_entities", return_value=[extracted]
    ) as extract_entities:
        result = call_tool("extract_entities", {"text": text})

    extract_entities.assert_called_once_with(text)
    assert result == {
        "entities": [
            {
                "text": "Acme Corp",
                "label": "ORG",
                "type": "ORG",
                "start": 17,
                "end": 26,
                "confidence": 0.7,
            }
        ],
        "count": 1,
    }


def test_extract_entities_uses_consistent_defaults_for_missing_label():
    extracted = SimpleNamespace(text="unknown", start_char=0, end_char=7)

    with patch.object(
        NamedEntityRecognizer, "extract_entities", return_value=[extracted]
    ):
        result = call_tool("extract_entities", {"text": "unknown"})

    assert result["entities"][0]["label"] == ""
    assert result["entities"][0]["type"] == ""


def test_extract_relations_serializes_relation_fields_and_preserves_text():
    text = "  Alice founded Acme Corp."
    alice = Entity("Alice", "PERSON", 2, 7, confidence=0.9)
    acme = Entity("Acme Corp", "ORG", 16, 25, confidence=0.8)
    relation = Relation(alice, "founded", acme, confidence=0.75)
    triplet = Triplet("Alice", "founded", "Acme Corp", confidence=0.7)

    with (
        patch.object(
            NamedEntityRecognizer, "extract_entities", return_value=[alice, acme]
        ) as extract_entities,
        patch.object(
            RelationExtractor, "extract", return_value=[relation]
        ) as extract_relations,
        patch.object(
            TripletExtractor, "extract", return_value=[triplet]
        ) as extract_triplets,
    ):
        result = call_tool("extract_relations", {"text": text})

    extract_entities.assert_called_once_with(text)
    extract_relations.assert_called_once_with(text, [alice, acme])
    extract_triplets.assert_called_once_with(text)
    assert result == {
        "relations": [
            {
                "source": "Alice",
                "type": "founded",
                "target": "Acme Corp",
                "confidence": 0.75,
            }
        ],
        "triplets": [
            {"subject": "Alice", "predicate": "founded", "object": "Acme Corp"}
        ],
        "relation_count": 1,
        "triplet_count": 1,
    }


def test_extract_all_keeps_coreferences_separate_from_downstream_text():
    text = "  Alice founded Acme Corp. She leads it."
    alice = Entity("Alice", "PERSON", 2, 7, confidence=0.9)
    acme = Entity("Acme Corp", "ORG", 16, 25, confidence=0.8)
    representative = Mention("Alice", 2, 7, "entity", entity_id="alice")
    pronoun = Mention("She", 27, 30, "pronoun", entity_id="alice")
    chain = CoreferenceChain(
        mentions=[representative, pronoun],
        representative=representative,
        entity_type="PERSON",
    )
    relation = Relation(alice, "founded", acme, confidence=0.75)
    triplet = Triplet("Alice", "founded", "Acme Corp", confidence=0.7)
    event = Event("founded", "FOUNDING", 8, 15, confidence=0.85)

    with (
        patch.object(
            NamedEntityRecognizer, "extract_entities", return_value=[alice, acme]
        ) as extract_entities,
        patch.object(CoreferenceResolver, "resolve", return_value=[chain]) as resolve,
        patch.object(
            RelationExtractor, "extract", return_value=[relation]
        ) as extract_relations,
        patch.object(EventDetector, "extract", return_value=[event]),
        patch.object(
            TripletExtractor, "extract", return_value=[triplet]
        ) as extract_triplets,
    ):
        result = call_tool("extract_all", {"text": text})

    extract_entities.assert_called_once_with(text)
    resolve.assert_called_once_with(text, entities=[alice, acme])
    extract_relations.assert_called_once_with(text, [alice, acme])
    extract_triplets.assert_called_once_with(text)
    assert result == {
        "entities": [
            {"text": "Alice", "label": "PERSON", "type": "PERSON"},
            {"text": "Acme Corp", "label": "ORG", "type": "ORG"},
        ],
        "coreferences": [
            {
                "representative": "Alice",
                "mentions": ["Alice", "She"],
                "entity_type": "PERSON",
            }
        ],
        "relations": [
            {
                "source": "Alice",
                "type": "founded",
                "target": "Acme Corp",
                "confidence": 0.75,
            }
        ],
        "events": [{"type": "FOUNDING", "trigger": "founded"}],
        "triplets": [
            {"subject": "Alice", "predicate": "founded", "object": "Acme Corp"}
        ],
        "summary": {
            "entities": 2,
            "coreferences": 1,
            "relations": 1,
            "events": 1,
            "triplets": 1,
        },
    }

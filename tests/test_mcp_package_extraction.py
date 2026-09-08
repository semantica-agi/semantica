"""Regression tests for the packaged MCP extraction handlers."""

from unittest.mock import patch

from semantica.semantic_extract import (
    CoreferenceResolver,
    EventDetector,
    NamedEntityRecognizer,
    RelationExtractor,
    TripletExtractor,
)
from semantica.semantic_extract.types import Entity
from semantica_mcp.mcp.server import call_tool


def test_extract_entities_uses_public_ner_api_and_serializes_entity_fields():
    """A real text payload must reach ``extract_entities``, not a nonexistent alias."""
    extracted = Entity(
        text="Acme Corp",
        label="ORG",
        start_char=15,
        end_char=24,
        confidence=0.7,
    )

    with patch.object(
        NamedEntityRecognizer,
        "extract_entities",
        return_value=[extracted],
    ):
        result = call_tool(
            "extract_entities",
            {"text": "Alice works at Acme Corp."},
        )

    assert result == {
        "entities": [
            {
                "text": "Acme Corp",
                "label": "ORG",
                "type": "ORG",
                "start": 15,
                "end": 24,
                "confidence": 0.7,
            }
        ],
        "count": 1,
    }


def test_extract_relations_uses_public_ner_api():
    with (
        patch.object(NamedEntityRecognizer, "extract_entities", return_value=[]),
        patch.object(RelationExtractor, "extract", return_value=[]),
        patch.object(TripletExtractor, "extract", return_value=[]),
    ):
        result = call_tool(
            "extract_relations",
            {"text": "Alice works at Acme Corp."},
        )

    assert result == {
        "relations": [],
        "triplets": [],
        "relation_count": 0,
        "triplet_count": 0,
    }


def test_extract_all_uses_public_ner_api_and_serializes_entity_fields():
    extracted = Entity(
        text="Acme Corp",
        label="ORG",
        start_char=15,
        end_char=24,
        confidence=0.7,
    )

    with (
        patch.object(
            NamedEntityRecognizer,
            "extract_entities",
            return_value=[extracted],
        ),
        patch.object(CoreferenceResolver, "resolve", return_value=[]),
        patch.object(RelationExtractor, "extract", return_value=[]),
        patch.object(EventDetector, "extract", return_value=[]),
        patch.object(TripletExtractor, "extract", return_value=[]),
    ):
        result = call_tool(
            "extract_all",
            {"text": "Alice works at Acme Corp."},
        )

    assert result == {
        "entities": [{"text": "Acme Corp", "label": "ORG", "type": "ORG"}],
        "relations": [],
        "events": [],
        "triplets": [],
        "summary": {
            "entities": 1,
            "relations": 0,
            "events": 0,
            "triplets": 0,
        },
    }

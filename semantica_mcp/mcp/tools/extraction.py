"""
Extraction tools — NER, relation extraction, event detection, triplets.
"""

from __future__ import annotations

import logging
from typing import Any

from ..schemas import EXTRACT_ALL, EXTRACT_ENTITIES, EXTRACT_RELATIONS

log = logging.getLogger("semantica.mcp.tools.extraction")


def _clear_cache() -> None:
    try:
        from semantica.semantic_extract.cache import _result_cache

        _result_cache.clear()
    except Exception:
        log.debug("Could not clear semantic_extract cache; continuing", exc_info=True)


def _relation_endpoint(value: Any) -> Any:
    """Return a stable textual value for a relation endpoint."""
    if value is None or isinstance(value, str):
        return value
    return getattr(value, "text", str(value))


def _serialize_relation(relation: Any) -> dict[str, Any]:
    return {
        "source": _relation_endpoint(getattr(relation, "subject", None)),
        "type": getattr(relation, "predicate", None),
        "target": _relation_endpoint(getattr(relation, "object", None)),
        "confidence": getattr(relation, "confidence", None),
    }


def _serialize_coreference(chain: Any) -> dict[str, Any]:
    representative = getattr(chain, "representative", None)
    return {
        "representative": getattr(representative, "text", ""),
        "mentions": [
            getattr(mention, "text", "") for mention in getattr(chain, "mentions", [])
        ],
        "entity_type": getattr(chain, "entity_type", None),
    }


def handle_extract_entities(args: dict) -> dict:
    """Extract named entities from text using Semantica NER."""
    text = args.get("text", "")
    if not text.strip():
        return {"error": "text is required", "entities": []}
    _clear_cache()
    try:
        from semantica.semantic_extract import NamedEntityRecognizer

        entities = NamedEntityRecognizer().extract_entities(text) or []
        return {
            "entities": [
                {
                    "text": getattr(e, "text", ""),
                    "label": getattr(e, "label", ""),
                    "type": getattr(e, "label", ""),
                    "start": getattr(e, "start_char", getattr(e, "start", None)),
                    "end": getattr(e, "end_char", getattr(e, "end", None)),
                    "confidence": getattr(e, "confidence", None),
                }
                for e in entities
            ],
            "count": len(entities),
        }
    except Exception as exc:
        log.exception("extract_entities failed")
        return {"error": str(exc), "entities": []}


def handle_extract_relations(args: dict) -> dict:
    """Extract relations and triplets from text."""
    text = args.get("text", "")
    if not text.strip():
        return {"error": "text is required", "relations": [], "triplets": []}
    _clear_cache()
    try:
        from semantica.semantic_extract import (
            NamedEntityRecognizer,
            RelationExtractor,
            TripletExtractor,
        )

        entities = NamedEntityRecognizer().extract_entities(text) or []
        relations = RelationExtractor().extract(text, entities) or []
        triplets = TripletExtractor().extract(text) or []
        return {
            "relations": [_serialize_relation(r) for r in relations],
            "triplets": [
                {
                    "subject": getattr(t, "subject", None),
                    "predicate": getattr(t, "predicate", None),
                    "object": getattr(t, "object", None),
                }
                for t in triplets
            ],
            "relation_count": len(relations),
            "triplet_count": len(triplets),
        }
    except Exception as exc:
        log.exception("extract_relations failed")
        return {"error": str(exc), "relations": [], "triplets": []}


def handle_extract_all(args: dict) -> dict:
    """Run the full extraction pipeline: NER + relations + events + triplets."""
    text = args.get("text", "")
    if not text.strip():
        return {"error": "text is required"}
    include_events = args.get("include_events", True)
    include_triplets = args.get("include_triplets", True)
    _clear_cache()
    result: dict[str, Any] = {}
    try:
        from semantica.semantic_extract import (
            CoreferenceResolver,
            EventDetector,
            NamedEntityRecognizer,
            RelationExtractor,
            TripletExtractor,
        )

        entities = NamedEntityRecognizer().extract_entities(text) or []
        result["entities"] = [
            {
                "text": getattr(e, "text", ""),
                "label": getattr(e, "label", ""),
                "type": getattr(e, "label", ""),
            }
            for e in entities
        ]

        coreferences = CoreferenceResolver().resolve(text, entities=entities) or []
        result["coreferences"] = [
            _serialize_coreference(chain) for chain in coreferences
        ]

        relations = RelationExtractor().extract(text, entities) or []
        result["relations"] = [_serialize_relation(r) for r in relations]

        if include_events:
            events = EventDetector().extract(text) or []
            result["events"] = [
                {
                    "type": getattr(ev, "event_type", getattr(ev, "type", None)),
                    "trigger": getattr(ev, "text", getattr(ev, "trigger", str(ev))),
                }
                for ev in events
            ]

        if include_triplets:
            triplets = TripletExtractor().extract(text) or []
            result["triplets"] = [
                {
                    "subject": getattr(t, "subject", None),
                    "predicate": getattr(t, "predicate", None),
                    "object": getattr(t, "object", None),
                }
                for t in triplets
            ]

        result["summary"] = {
            "entities": len(result.get("entities", [])),
            "coreferences": len(result.get("coreferences", [])),
            "relations": len(result.get("relations", [])),
            "events": len(result.get("events", [])),
            "triplets": len(result.get("triplets", [])),
        }
        return result
    except Exception as exc:
        log.exception("extract_all failed")
        return {"error": str(exc)}


EXTRACTION_TOOLS = [
    {
        "name": "extract_entities",
        "description": "Extract named entities (people, places, organisations, concepts) from text.",
        "inputSchema": EXTRACT_ENTITIES,
        "_handler": handle_extract_entities,
    },
    {
        "name": "extract_relations",
        "description": "Extract relations and (subject, predicate, object) triplets from text.",
        "inputSchema": EXTRACT_RELATIONS,
        "_handler": handle_extract_relations,
    },
    {
        "name": "extract_all",
        "description": "Run the full Semantica extraction pipeline: NER, coreference resolution, relation extraction, event detection, and triplet generation.",
        "inputSchema": EXTRACT_ALL,
        "_handler": handle_extract_all,
    },
]

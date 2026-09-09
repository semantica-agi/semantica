"""Schema-guided validation for semantic extractions.

:class:`SchemaValidator` is a sibling of
:class:`~semantica.semantic_extract.extraction_validator.ExtractionValidator`:
same two entry points (:meth:`validate_entities` / :meth:`validate_relations`)
returning the same :class:`ValidationResult`, so the two compose back-to-back.

The two validators check **orthogonal** axes. ``ExtractionValidator`` checks
*confidence* and structural sanity; ``SchemaValidator`` checks *conformance to a
domain ontology*:

* every entity label must be a concept in the schema;
* every relation predicate must be in the schema and satisfy its ``domain`` /
  ``range``.

This is the deterministic core of ontology-based information extraction (OBIE,
Wimalasuriya & Dou 2010): it needs no LLM and is fully unit-testable.
:meth:`validate_entities` / :meth:`validate_relations` *report* conformance;
:meth:`filter_by_schema` / :meth:`filter_relations_by_schema` return the
conforming subset (mirroring ``ExtractionValidator.filter_by_confidence``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from .extraction_validator import ValidationResult
from .ner_extractor import Entity
from .relation_extractor import Relation
from .schema import ExtractionSchema


class SchemaValidator:
    """Validate extractions against a domain ontology (:class:`ExtractionSchema`)."""

    def __init__(
        self, schema: ExtractionSchema, method: Optional[str] = None, **config: Any
    ) -> None:
        """Initialize the validator.

        Args:
            schema: The domain ontology view to validate against.
            method: Reserved for future method-specific validation (unused),
                mirroring ``ExtractionValidator``.
            **config: Reserved configuration options.
        """
        self.schema = schema
        self.method = method
        self.config = config

    def validate_entities(
        self, entities: Union[List[Entity], List[List[Entity]]], **options: Any
    ) -> Union[ValidationResult, List[ValidationResult]]:
        """Validate that entity labels are concepts in the schema.

        Handles both a single list and a batch (list of lists), like
        ``ExtractionValidator.validate_entities``.
        """
        if entities and isinstance(entities, list) and isinstance(entities[0], list):
            results = []
            for idx, batch in enumerate(entities):
                res = self.validate_entities(batch, **options)
                if "batch_index" not in res.metadata:
                    res.metadata["batch_index"] = idx
                results.append(res)
            return results

        errors: List[str] = []
        warnings: List[str] = []

        out_of_vocab = [e for e in entities if not self.schema.has_concept(e.label)]
        unknown_labels = sorted({e.label for e in out_of_vocab})
        if out_of_vocab:
            errors.append(
                f"{len(out_of_vocab)} entities with labels outside the schema: "
                f"{', '.join(unknown_labels)}"
            )

        total = len(entities)
        conforming = total - len(out_of_vocab)
        metrics = {
            "total_entities": total,
            "in_vocabulary": conforming,
            "out_of_vocabulary": len(out_of_vocab),
            "unknown_labels": unknown_labels,
            "schema_concepts": len(self.schema.concepts),
        }
        score = conforming / total if total else 1.0

        return ValidationResult(
            valid=not errors,
            score=score,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            metadata=self._metadata(entities),
        )

    def validate_relations(
        self, relations: Union[List[Relation], List[List[Relation]]], **options: Any
    ) -> Union[ValidationResult, List[ValidationResult]]:
        """Validate relation predicates and ``domain`` / ``range`` against the schema.

        Handles both a single list and a batch (list of lists), like
        ``ExtractionValidator.validate_relations``.
        """
        if relations and isinstance(relations, list) and isinstance(relations[0], list):
            results = []
            for idx, batch in enumerate(relations):
                res = self.validate_relations(batch, **options)
                if "batch_index" not in res.metadata:
                    res.metadata["batch_index"] = idx
                results.append(res)
            return results

        errors: List[str] = []
        warnings: List[str] = []

        # Guard malformed relations (missing subject/object) before dereferencing
        # their endpoints, matching ExtractionValidator's own leniency.
        malformed = [r for r in relations if not r.subject or not r.object]
        well_formed = [r for r in relations if r.subject and r.object]

        unknown_predicate = [
            r for r in well_formed if not self.schema.has_predicate(r.predicate)
        ]
        dr_violation = [
            r
            for r in well_formed
            if self.schema.has_predicate(r.predicate)
            and not self.schema.allows_relation(
                r.subject.label, r.predicate, r.object.label
            )
        ]
        if malformed:
            errors.append(f"{len(malformed)} relations missing a subject or object")
        if unknown_predicate:
            preds = sorted({r.predicate for r in unknown_predicate})
            errors.append(
                f"{len(unknown_predicate)} relations with predicates outside the "
                f"schema: {', '.join(preds)}"
            )
        if dr_violation:
            errors.append(
                f"{len(dr_violation)} relations violating domain/range constraints"
            )

        total = len(relations)
        conforming = total - len(malformed) - len(unknown_predicate) - len(dr_violation)
        metrics = {
            "total_relations": total,
            "conforming": conforming,
            "malformed": len(malformed),
            "unknown_predicate": len(unknown_predicate),
            "domain_range_violation": len(dr_violation),
            "schema_predicates": len(self.schema.predicates),
        }
        score = conforming / total if total else 1.0

        return ValidationResult(
            valid=not errors,
            score=score,
            errors=errors,
            warnings=warnings,
            metrics=metrics,
            metadata=self._metadata(relations),
        )

    def filter_by_schema(self, entities: List[Entity]) -> List[Entity]:
        """Return only entities whose label is a concept in the schema."""
        return [e for e in entities if self.schema.has_concept(e.label)]

    def filter_relations_by_schema(self, relations: List[Relation]) -> List[Relation]:
        """Return only relations that fully conform to the schema."""
        return [
            r
            for r in relations
            if r.subject
            and r.object
            and self.schema.has_predicate(r.predicate)
            and self.schema.allows_relation(
                r.subject.label, r.predicate, r.object.label
            )
        ]

    @staticmethod
    def _metadata(items: List[Any]) -> Dict[str, Any]:
        """Carry ``batch_index`` / ``document_id`` through, like ``ExtractionValidator``."""
        metadata: Dict[str, Any] = {}
        if items:
            first = items[0]
            if getattr(first, "metadata", None):
                for key in ("batch_index", "document_id"):
                    if key in first.metadata:
                        metadata[key] = first.metadata[key]
        return metadata

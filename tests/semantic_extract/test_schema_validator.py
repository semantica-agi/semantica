"""Unit tests for ExtractionSchema and SchemaValidator (schema-guided validation)."""

from __future__ import annotations

from semantica.semantic_extract import (
    Entity,
    ExtractionSchema,
    ExtractionValidator,
    Relation,
    SchemaValidator,
    ValidationResult,
)

ONTOLOGY = {
    "classes": [{"name": "Person"}, {"name": "Organization"}, {"label": "City"}],
    "properties": [
        {"name": "worksAt", "domain": ["Person"], "range": ["Organization"]},
        {"name": "locatedIn", "domain": "Organization", "range": "City"},
        {"name": "knows"},  # unconstrained domain / range
    ],
}

TTL = """
@prefix : <https://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Person a owl:Class .
:Organization a owl:Class .
:worksAt a owl:ObjectProperty ;
    rdfs:domain :Person ;
    rdfs:range :Organization .
"""


def _schema() -> ExtractionSchema:
    return ExtractionSchema.from_ontology(ONTOLOGY)


def _person() -> Entity:
    return Entity(text="Alice", label="Person", start_char=0, end_char=5)


def _org() -> Entity:
    return Entity(text="Acme", label="Organization", start_char=0, end_char=4)


def _city() -> Entity:
    return Entity(text="Paris", label="City", start_char=0, end_char=5)


def _product() -> Entity:
    return Entity(text="Widget", label="Product", start_char=0, end_char=6)


# --------------------------------------------------------------------------- #
# ExtractionSchema
# --------------------------------------------------------------------------- #


def test_from_ontology_parses_concepts_and_predicates() -> None:
    schema = _schema()
    assert schema.concepts == frozenset({"Person", "Organization", "City"})
    assert set(schema.predicates) == {"worksAt", "locatedIn", "knows"}
    assert schema.predicates["worksAt"].domain == frozenset({"Person"})
    assert schema.predicates["worksAt"].range == frozenset({"Organization"})
    # Missing domain / range means unconstrained.
    assert schema.predicates["knows"].domain == frozenset()
    assert schema.predicates["knows"].range == frozenset()


def test_allows_relation_respects_domain_range() -> None:
    schema = _schema()
    assert schema.allows_relation("Person", "worksAt", "Organization")
    assert not schema.allows_relation("Person", "worksAt", "City")  # range violation
    assert not schema.allows_relation("Person", "unknownPred", "Organization")
    assert not schema.allows_relation("Product", "worksAt", "Organization")  # off-vocab
    # Unconstrained predicate accepts any known concepts.
    assert schema.allows_relation("Person", "knows", "City")


def test_from_owl_parses_turtle() -> None:
    schema = ExtractionSchema.from_owl(TTL, format="turtle")
    assert {"Person", "Organization"} <= schema.concepts
    assert schema.predicates["worksAt"].domain == frozenset({"Person"})
    assert schema.predicates["worksAt"].range == frozenset({"Organization"})


# --------------------------------------------------------------------------- #
# SchemaValidator — entities
# --------------------------------------------------------------------------- #


def test_validate_entities_all_conforming() -> None:
    result = SchemaValidator(_schema()).validate_entities([_person(), _org(), _city()])
    assert isinstance(result, ValidationResult)
    assert result.valid
    assert result.score == 1.0
    assert result.metrics["out_of_vocabulary"] == 0


def test_validate_entities_flags_out_of_vocabulary() -> None:
    result = SchemaValidator(_schema()).validate_entities([_person(), _product()])
    assert not result.valid
    assert result.metrics["out_of_vocabulary"] == 1
    assert result.metrics["unknown_labels"] == ["Product"]
    assert result.score == 0.5
    assert result.errors


def test_validate_entities_empty_is_vacuously_valid() -> None:
    result = SchemaValidator(_schema()).validate_entities([])
    assert result.valid
    assert result.score == 1.0


def test_validate_entities_batch_returns_list_with_index() -> None:
    results = SchemaValidator(_schema()).validate_entities([[_person()], [_product()]])
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0].valid
    assert not results[1].valid
    assert results[0].metadata["batch_index"] == 0
    assert results[1].metadata["batch_index"] == 1


# --------------------------------------------------------------------------- #
# SchemaValidator — relations
# --------------------------------------------------------------------------- #


def test_validate_relations_conforming() -> None:
    rels = [
        Relation(subject=_person(), predicate="worksAt", object=_org()),
        Relation(subject=_person(), predicate="knows", object=_city()),
    ]
    result = SchemaValidator(_schema()).validate_relations(rels)
    assert result.valid
    assert result.score == 1.0


def test_validate_relations_flags_unknown_predicate_and_domain_range() -> None:
    rels = [
        Relation(subject=_person(), predicate="worksAt", object=_org()),  # ok
        Relation(subject=_person(), predicate="founded", object=_org()),  # unknown pred
        Relation(subject=_person(), predicate="worksAt", object=_city()),  # range viol
    ]
    result = SchemaValidator(_schema()).validate_relations(rels)
    assert not result.valid
    assert result.metrics["unknown_predicate"] == 1
    assert result.metrics["domain_range_violation"] == 1
    assert result.metrics["conforming"] == 1
    assert result.score == 1 / 3


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


def test_filter_by_schema_drops_off_vocabulary() -> None:
    kept = SchemaValidator(_schema()).filter_by_schema([_person(), _org(), _product()])
    assert [e.label for e in kept] == ["Person", "Organization"]


def test_filter_relations_by_schema_keeps_only_conforming() -> None:
    rels = [
        Relation(subject=_person(), predicate="worksAt", object=_org()),  # keep
        Relation(subject=_person(), predicate="founded", object=_org()),  # drop
        Relation(subject=_person(), predicate="worksAt", object=_city()),  # drop
        Relation(subject=_person(), predicate="knows", object=_city()),  # keep
    ]
    kept = SchemaValidator(_schema()).filter_relations_by_schema(rels)
    assert [r.predicate for r in kept] == ["worksAt", "knows"]


# --------------------------------------------------------------------------- #
# Composition with the confidence-based ExtractionValidator (orthogonal axis)
# --------------------------------------------------------------------------- #


def test_composes_with_extraction_validator_same_shape() -> None:
    entities = [_person(), _org()]
    confidence = ExtractionValidator().validate_entities(entities)
    conformance = SchemaValidator(_schema()).validate_entities(entities)
    assert isinstance(confidence, ValidationResult)
    assert isinstance(conformance, ValidationResult)


# --------------------------------------------------------------------------- #
# Robustness fixes surfaced in review
# --------------------------------------------------------------------------- #


def test_owl_thing_domain_range_is_unconstrained() -> None:
    # OntologyGenerator emits owl:Thing when it cannot resolve endpoint types;
    # it must behave as "any concept", not a literal {"Thing"} constraint.
    ont = {
        "classes": [{"name": "Person"}, {"name": "Organization"}],
        "properties": [
            {"name": "relatedTo", "domain": ["owl:Thing"], "range": ["owl:Thing"]}
        ],
    }
    schema = ExtractionSchema.from_ontology(ont)
    assert schema.predicates["relatedTo"].domain == frozenset()
    assert schema.predicates["relatedTo"].range == frozenset()
    assert schema.allows_relation("Person", "relatedTo", "Organization")


def test_from_owl_prefers_rdfs_label_and_supports_rdfs_class() -> None:
    ttl = """
    @prefix : <https://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    :Cls1 a owl:Class ; rdfs:label "Person" .
    :Org a rdfs:Class .
    :worksAt a owl:ObjectProperty ;
        rdfs:domain :Cls1 ;
        rdfs:range :Org .
    """
    schema = ExtractionSchema.from_owl(ttl, format="turtle")
    # rdfs:label wins over the URI suffix "Cls1"
    assert "Person" in schema.concepts
    assert "Cls1" not in schema.concepts
    # rdfs:Class is picked up too
    assert "Org" in schema.concepts
    assert schema.predicates["worksAt"].domain == frozenset({"Person"})


def test_validate_relations_handles_malformed_without_crashing() -> None:
    # A relation missing an endpoint must be reported, not raise AttributeError.
    good = Relation(subject=_person(), predicate="worksAt", object=_org())
    bad = Relation(subject=_person(), predicate="worksAt", object=None)  # type: ignore[arg-type]
    result = SchemaValidator(_schema()).validate_relations([good, bad])
    assert isinstance(result, ValidationResult)
    assert not result.valid
    assert result.metrics["malformed"] == 1
    assert result.metrics["conforming"] == 1
    # Filtering also drops the malformed one instead of crashing.
    kept = SchemaValidator(_schema()).filter_relations_by_schema([good, bad])
    assert kept == [good]


def test_from_ontology_folds_endpoint_types_like_from_owl() -> None:
    # pkupt's case: an endpoint type (Org) that didn't clear the class-frequency
    # gate is absent from "classes" but referenced in a property's range. Both
    # constructors must agree that (Person, worksFor, Org) is allowed.
    ont = {
        "classes": [{"name": "Person"}],
        "properties": [{"name": "worksFor", "domain": ["Person"], "range": ["Org"]}],
    }
    dict_schema = ExtractionSchema.from_ontology(ont)
    assert {"Person", "Org"} <= dict_schema.concepts
    assert dict_schema.allows_relation("Person", "worksFor", "Org")

    ttl = """
    @prefix : <https://example.org/> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

    :Person a owl:Class .
    :worksFor a owl:ObjectProperty ;
        rdfs:domain :Person ;
        rdfs:range :Org .
    """
    owl_schema = ExtractionSchema.from_owl(ttl, format="turtle")
    assert owl_schema.allows_relation(
        "Person", "worksFor", "Org"
    ) == dict_schema.allows_relation("Person", "worksFor", "Org")


def test_from_ontology_accepts_ontologydata_like_object() -> None:
    # semantica.ingest.OntologyIngestor.ingest_ontology returns an OntologyData
    # whose ontology dict is held in `.data`; from_ontology should unwrap it
    # instead of raising AttributeError on `.get()`.
    from types import SimpleNamespace

    wrapped = SimpleNamespace(data=ONTOLOGY)
    schema = ExtractionSchema.from_ontology(wrapped)
    assert schema.concepts == frozenset({"Person", "Organization", "City"})
    assert "worksAt" in schema.predicates

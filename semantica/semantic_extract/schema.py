"""Domain schema view over an ontology, for schema-guided extraction.

An :class:`ExtractionSchema` is a lightweight, read-only view over a domain
ontology: the set of allowed *concept* names (entity labels) and the allowed
*predicates* with optional ``domain`` / ``range`` constraints. It is what
:class:`~semantica.semantic_extract.schema_validator.SchemaValidator` checks
extraction output against.

The schema deliberately **reuses the project's existing OWL ontology
representation** instead of introducing a parallel "template" type. Build one
from the dict produced by :func:`semantica.ontology.generate_ontology`
(:meth:`ExtractionSchema.from_ontology`), or from an OWL / Turtle file or string
(:meth:`ExtractionSchema.from_owl`).

An empty ``domain`` / ``range`` means "unconstrained", matching OWL's convention
that an object property with no ``rdfs:domain`` / ``rdfs:range`` places no
restriction on its subjects / objects.

Reference
---------
Using an ontology to constrain what may be extracted is the defining idea of
ontology-based information extraction (OBIE): Wimalasuriya & Dou, "Ontology-Based
Information Extraction: An Introduction and a Survey" (2010).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Set


def _as_name_set(value: Any) -> Set[str]:
    """Coerce a ``domain`` / ``range`` value to a set of concept names.

    Accepts a string, an iterable of strings / mappings, a mapping (reads its
    ``name`` / ``label``), or ``None``. ``None`` / empty yields an empty set,
    interpreted downstream as "unconstrained".
    """
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, Mapping):
        name = value.get("name") or value.get("label")
        return {str(name)} if name else {str(k) for k in value}
    if isinstance(value, Iterable):
        out: Set[str] = set()
        for item in value:
            out |= _as_name_set(item)
        return out
    return {str(value)}


_OWL_THING = {
    "owl:Thing",
    "Thing",
    "http://www.w3.org/2002/07/owl#Thing",
}


def _drop_thing(names: Set[str]) -> Set[str]:
    """Collapse an ``owl:Thing`` domain / range to *unconstrained* (empty set).

    ``owl:Thing`` is the universal class, so a property whose ``domain`` / ``range``
    is ``owl:Thing`` places no restriction. ``OntologyGenerator`` emits it as the
    fallback when it cannot resolve endpoint types; keeping it as a literal
    ``{"Thing"}`` constraint would reject every real endpoint, so we treat its
    presence as "any concept".
    """
    return set() if names & _OWL_THING else names


def _constraint_set(value: Any) -> Set[str]:
    """A ``domain`` / ``range`` constraint set, with ``owl:Thing`` meaning unconstrained."""
    return _drop_thing(_as_name_set(value))


@dataclass(frozen=True)
class Predicate:
    """An allowed predicate with optional ``domain`` / ``range`` constraints.

    Empty ``domain`` / ``range`` means any concept is allowed in that position.
    """

    name: str
    domain: FrozenSet[str] = frozenset()
    range: FrozenSet[str] = frozenset()


@dataclass
class ExtractionSchema:
    """Read-only view over a domain ontology used to gate extraction.

    Names are matched **exactly**: the schema vocabulary and the extraction labels
    must share a normalization convention. ``OntologyGenerator`` normalizes concept
    names to PascalCase and predicate names to camelCase, so entity labels /
    relation predicates validated against a generated schema should follow the same
    convention (e.g. label entities ``Person`` rather than ``person``).
    """

    concepts: FrozenSet[str] = field(default_factory=frozenset)
    predicates: Dict[str, Predicate] = field(default_factory=dict)

    # ---- constructors -------------------------------------------------

    @classmethod
    def from_ontology(cls, ontology: Any) -> "ExtractionSchema":
        """Build a schema from a ``generate_ontology``-style ontology.

        Accepts the mapping returned by :func:`semantica.ontology.generate_ontology`,
        or an object exposing such a mapping via a ``.data`` attribute — e.g. the
        ``OntologyData`` returned by ``semantica.ingest.OntologyIngestor``.

        Reads ``ontology["classes"]`` (each carrying a ``name`` / ``label``) as
        concepts and ``ontology["properties"]`` (each carrying a ``name`` and
        optional ``domain`` / ``range``) as predicates. Missing ``domain`` /
        ``range`` means unconstrained; unrecognised keys are ignored.

        Endpoint types named in a property's ``domain`` / ``range`` are also folded
        into the concept set (consistent with :meth:`from_owl`), so a type referenced
        only as an endpoint — e.g. one that didn't clear the class-frequency gate
        during induction — is still a known concept.
        """
        if not isinstance(ontology, Mapping) and hasattr(ontology, "data"):
            ontology = ontology.data  # unwrap OntologyData-like objects

        concepts: Set[str] = set()
        for c in ontology.get("classes", []) or []:
            name = (c.get("name") or c.get("label")) if isinstance(c, Mapping) else c
            if name:
                concepts.add(str(name))

        predicates: Dict[str, Predicate] = {}
        for p in ontology.get("properties", []) or []:
            if not isinstance(p, Mapping):
                continue
            name = p.get("name") or p.get("label")
            if not name:
                continue
            domain = _constraint_set(p.get("domain"))
            rng = _constraint_set(p.get("range"))
            predicates[str(name)] = Predicate(
                name=str(name),
                domain=frozenset(domain),
                range=frozenset(rng),
            )
            concepts |= domain | rng
        return cls(concepts=frozenset(concepts), predicates=predicates)

    @classmethod
    def from_owl(
        cls, source: str, *, format: Optional[str] = None
    ) -> "ExtractionSchema":
        """Build a schema from an OWL / RDF file path or serialized string.

        ``owl:Class`` / ``rdfs:Class`` become concepts; ``owl:ObjectProperty`` with
        ``rdfs:domain`` / ``rdfs:range`` becomes a predicate (its domain / range
        names are folded into the concept set, with ``owl:Thing`` treated as
        unconstrained). Names prefer an explicit ``rdfs:label``, falling back to the
        URI's local name, so the vocabulary matches :meth:`from_ontology`. Requires
        ``rdflib`` (an existing project dependency).
        """
        from rdflib import OWL, RDF, RDFS, Graph, URIRef

        graph = Graph()
        if os.path.exists(source):
            graph.parse(source, format=format)
        else:
            graph.parse(data=source, format=format or "turtle")

        def _local(term: Any) -> str:
            text = str(term)
            for sep in ("#", "/"):
                if sep in text:
                    text = text.rsplit(sep, 1)[-1]
            return text

        def _name_of(term: Any) -> str:
            label = graph.value(term, RDFS.label)
            return str(label) if label is not None else _local(term)

        concepts: Set[str] = {
            _name_of(c)
            for class_type in (OWL.Class, RDFS.Class)
            for c in graph.subjects(RDF.type, class_type)
            if isinstance(c, URIRef)
        }
        predicates: Dict[str, Predicate] = {}
        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            name = _name_of(prop)
            domain = _drop_thing(
                {_name_of(d) for d in graph.objects(prop, RDFS.domain)}
            )
            rng = _drop_thing({_name_of(r) for r in graph.objects(prop, RDFS.range)})
            predicates[name] = Predicate(
                name=name, domain=frozenset(domain), range=frozenset(rng)
            )
            concepts |= domain | rng
        return cls(concepts=frozenset(concepts), predicates=predicates)

    # ---- queries ------------------------------------------------------

    def has_concept(self, name: str) -> bool:
        """Whether ``name`` is an allowed concept (entity label)."""
        return name in self.concepts

    def has_predicate(self, name: str) -> bool:
        """Whether ``name`` is an allowed predicate."""
        return name in self.predicates

    def allows_relation(
        self, subject_label: str, predicate: str, object_label: str
    ) -> bool:
        """Whether a relation conforms to the schema.

        True iff subject and object are known concepts, the predicate is known,
        and subject / object satisfy the predicate's ``domain`` / ``range``
        (an empty ``domain`` / ``range`` allows any concept).

        Membership is exact; ``subClassOf`` hierarchies are not traversed, so a
        subclass endpoint is not accepted for a superclass ``domain`` / ``range``
        (subclass-aware validation is a possible follow-up).
        """
        if subject_label not in self.concepts or object_label not in self.concepts:
            return False
        pred = self.predicates.get(predicate)
        if pred is None:
            return False
        if pred.domain and subject_label not in pred.domain:
            return False
        if pred.range and object_label not in pred.range:
            return False
        return True

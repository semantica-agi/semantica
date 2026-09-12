"""Bootstrap a draft domain ontology from a sample of extracted data.

Part of #1510 (Schema-guided extraction). Complements ``SchemaValidator``:
where the validator *constrains* extraction output against an existing
ontology, ``bootstrap_schema`` *induces* a draft ``Ontology`` from a sample of
``{entities, relationships}`` so you can ratify it by hand and then use it to
gate future extraction.

The draft is never applied automatically: this module emits a TTL serialization
(for human review) and marks the result as a draft. Auto-application is
explicitly a human decision, per the OBIE / ontology-learning convention that
frequency alone yields proposals, not final ontologies.
"""

from typing import Any, Dict, List, Optional

from ..utils.logging import get_logger
from .ontology_generator import OntologyGenerator
from .owl_generator import OWLGenerator

logger = get_logger("bootstrap_schema")


def _align_endpoints(ontology: Dict[str, Any]) -> Dict[str, Any]:
    """Drop property endpoints that never made it into ``classes``.

    Class inference and predicate inference share a frequency gate, but a rare
    endpoint type can still appear on a frequent relationship's property.  If we
    left it in ``domain``/``range``, the emitted TTL would reference an undeclared
    class and ``ExtractionSchema.from_ontology`` would fold the filtered type back
    into its concept vocabulary, defeating the gate.  Unconstrained is the honest
    reading of "did not clear the gate", so such endpoints become ``owl:Thing``.
    """
    declared = set()
    for c in ontology.get("classes", []):
        if not isinstance(c, dict):
            continue
        name = c.get("name") or c.get("label")
        if name:
            declared.add(name)
        # Property endpoints carry the *raw* entity type while class names are
        # normalized ("person" -> "Person"); match both spellings.
        inferred_from = (c.get("metadata") or {}).get("inferred_from")
        if isinstance(inferred_from, str):
            declared.add(inferred_from)
    for prop in ontology.get("properties", []):
        if not isinstance(prop, dict):
            continue
        for key in ("domain", "range"):
            values = prop.get(key)
            if not isinstance(values, list):
                continue
            prop[key] = [
                v
                for v in values
                if not isinstance(v, str) or v in declared or v == "owl:Thing"
            ] or ["owl:Thing"]
    return ontology


def bootstrap_schema(
    entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    min_occurrences: int = 2,
    base_uri: Optional[str] = None,
    **options: Any,
) -> Dict[str, Any]:
    """Induce a draft ontology from a sample of extracted entities/relationships.

    Thin wrapper over ``OntologyGenerator``: the entities/relationships ->
    concepts/properties induction, the ``domain``/``range`` inference (via
    ``PropertyInferencer``) and the TTL export all live inside the existing
    pipeline. This function only (a) threads ``min_occurrences`` through as a
    frequency gate, and (b) wraps the result as a *draft* that must be
    human-ratified before use.

    Args:
        entities: Extracted entities as dicts. ``type`` is used as the class
            label; per ``semantica/semantic_extract/`` the common fields are
            ``type``/``text``/``confidence``/``metadata``.
        relationships: Extracted relationships as dicts, with ``type`` as the
            predicate and ``source``/``target`` endpoints.
        min_occurrences: Minimum occurrence count for a class/property to be
            induced. Passed through to the pipeline's frequency gate
            (``ClassInferrer``/``PropertyGenerator`` default to 2).
        base_uri: Base IRI for generated classes/properties; defaults to the
            generator's own.
        **options: Forwarded to ``OntologyGenerator.generate_ontology``.

    Returns:
        A dictionary (never auto-applied):
            - ``ontology``: the induced ontology dict from the pipeline
            - ``ttl``: Turtle serialization for human review
            - ``draft``: always ``True``
            - ``min_occurrences``: the frequency gate actually used
    """
    gen_options: Dict[str, Any] = dict(options)
    if base_uri is not None:
        gen_options["base_uri"] = base_uri
    gen_options["min_occurrences"] = min_occurrences

    generator = OntologyGenerator(**gen_options)
    data: Dict[str, List[Dict[str, Any]]] = {
        "entities": entities,
        "relationships": relationships,
    }
    ontology = generator.generate_ontology(data, **gen_options)
    ontology = _align_endpoints(ontology)

    # Serialize with the generator's own namespace manager so declared classes,
    # properties and domain/range endpoints resolve under one consistent IRI
    # scheme (a fresh OWLGenerator would mint a second, inconsistent set).
    ttl = OWLGenerator(namespace_manager=generator.namespace_manager).generate_owl(
        ontology, format="turtle"
    )

    return {
        "ontology": ontology,
        "ttl": ttl,
        "draft": True,
        "min_occurrences": min_occurrences,
    }

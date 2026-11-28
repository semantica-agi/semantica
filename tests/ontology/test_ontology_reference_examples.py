"""The ``docs/reference/ontology.md`` examples run, and still mean what
they say.

These execute the page's own code blocks rather than a copy of them, because
the defect they guard against is drift between the page and the API: three
calls on this page named methods that do not exist (`SHACLGraph.serialize`,
`OntologyValidator.validate_graph`, `NamespaceManager.register`), and a
reader following the page got an `AttributeError` on the first line of the
SHACL section.

Copying the examples into the test would let the page drift again while the
test stayed green, so the blocks are read out of the Markdown.
"""

import re
from pathlib import Path

import pytest

PAGE = Path(__file__).parents[2] / "docs" / "reference" / "ontology.md"


def _python_block(heading):
    """The first ```python block under ``heading`` in the reference page.

    Raises rather than returning None: a renamed heading should fail loudly
    instead of silently skipping the example it was meant to check.
    """
    text = PAGE.read_text(encoding="utf-8")
    start = text.index(f"\n{heading}\n")
    match = re.search(r"```python\n(.*?)```", text[start:], re.DOTALL)
    assert match, f"no python block under {heading!r}"
    return match.group(1)


# Entity and relationship data for the SHACL block, which uses ``ontology``
# and ``kg`` as placeholders the page defines earlier in prose. Two Person
# entities, because a single one of a type yields no node shape and would
# make the validation vacuous.
SAMPLE_DATA = {
    "entities": [
        {"name": "Alice", "type": "Person",
         "attributes": {"email": "alice@example.org", "age": 31}},
        {"name": "Bob", "type": "Person",
         "attributes": {"email": "bob@example.org", "age": 45}},
        {"name": "Acme", "type": "Company",
         "attributes": {"domain": "acme.example.org"}},
    ],
    "relationships": [
        {"source": "Alice", "target": "Acme", "type": "works_at"},
        {"source": "Bob", "target": "Acme", "type": "works_at"},
    ],
}

SAMPLE_GRAPH = (
    "@prefix ex: <https://example.org/ontology/> .\n"
    "ex:alice a ex:Person .\n"
)


def test_namespace_management_block_runs():
    """The namespace block is self-contained, so it executes as written."""
    namespace = {}
    exec(compile(_python_block("## Namespace Management"),
                 "<ontology.md: Namespace Management>", "exec"), namespace)

    ns = namespace["ns"]
    assert ns.get_namespace("ex") == "https://example.org/"
    assert namespace["class_iri"] == "https://example.org/Person"
    assert namespace["property_iri"].endswith("worksFor")


def test_namespace_manager_has_no_bare_register():
    """Pins the rename the page now shows.

    ``register`` is the name the page used to document. If it ever becomes
    real, the page should say so deliberately rather than by accident.
    """
    from semantica.ontology import NamespaceManager

    assert hasattr(NamespaceManager, "register_namespace")
    assert not hasattr(NamespaceManager, "register")


def test_shacl_validation_block_runs():
    """The SHACL block executes against shapes it generates itself."""
    pytest.importorskip(
        "pyshacl", reason="validate_graph needs the shacl extra"
    )

    from semantica.ontology import OntologyEngine, SHACLValidationReport

    seed = OntologyEngine(base_uri="https://example.org/ontology/")
    namespace = {
        "ontology": seed.from_data(SAMPLE_DATA),
        "kg": SAMPLE_GRAPH,
    }
    exec(compile(_python_block("## SHACL Validation"),
                 "<ontology.md: SHACL Validation>", "exec"), namespace)

    assert isinstance(namespace["shapes_ttl"], str)
    assert "sh:NodeShape" in namespace["shapes_ttl"]
    assert isinstance(namespace["report"], SHACLValidationReport)


def test_shacl_graph_carries_no_serializer():
    """Why the block uses ``to_shacl``, not ``generate(...).serialize(...)``.

    ``SHACLGenerator.generate`` returns a plain dataclass. The page used to
    call ``.serialize(format="turtle")`` on it, which is an AttributeError on
    the third line of the example.
    """
    from semantica.ontology import OntologyEngine, SHACLGenerator
    from semantica.ontology.ontology_generator import SHACLGraph

    engine = OntologyEngine(base_uri="https://example.org/ontology/")
    ontology = engine.from_data(SAMPLE_DATA)

    shapes = SHACLGenerator().generate(ontology)
    assert isinstance(shapes, SHACLGraph)
    assert not hasattr(shapes, "serialize")
    # The fields the page now points readers at instead.
    for field in ("node_shapes", "prefixes", "class_iris", "property_iris"):
        assert hasattr(shapes, field), field

    assert isinstance(engine.to_shacl(ontology, format="turtle"), str)


def test_ontology_validator_takes_an_ontology_not_a_graph():
    """Pins the corrected ``Exported Classes`` row.

    The table said ``OntologyValidator`` validates a graph against SHACL
    shapes and returns ``SHACLValidationReport``. It takes an ontology and
    returns ``ValidationResult``; graph-against-shapes is
    ``OntologyEngine.validate_graph``.
    """
    from semantica.ontology import OntologyEngine, OntologyValidator
    from semantica.ontology.ontology_validator import ValidationResult

    assert not hasattr(OntologyValidator, "validate_graph")
    assert hasattr(OntologyEngine, "validate_graph")

    engine = OntologyEngine(base_uri="https://example.org/ontology/")
    result = OntologyValidator().validate(engine.from_data(SAMPLE_DATA))
    assert isinstance(result, ValidationResult)
    for field in ("valid", "consistent", "satisfiable", "errors", "warnings"):
        assert hasattr(result, field), field


def test_validate_graph_rejects_both_shacl_and_ontology():
    """The comment the block now carries about ``shacl=`` vs ``ontology=``."""
    pytest.importorskip(
        "pyshacl", reason="validate_graph needs the shacl extra"
    )

    from semantica.ontology import OntologyEngine

    engine = OntologyEngine(base_uri="https://example.org/ontology/")
    ontology = engine.from_data(SAMPLE_DATA)
    shapes_ttl = engine.to_shacl(ontology, format="turtle")

    with pytest.raises(ValueError):
        engine.validate_graph(
            SAMPLE_GRAPH, shacl=shapes_ttl, ontology=ontology
        )
    with pytest.raises(ValueError):
        engine.validate_graph(SAMPLE_GRAPH)

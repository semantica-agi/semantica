"""Regression tests for #1788: _resolve_xsd must not double the xsd: prefix.

A range that already carries the prefix (``xsd:string``) or that is a full IRI
used to come back as ``xsd:xsd:string`` / ``xsd:http://...#string``, which is
not a resolvable IRI, so the generated ``sh:datatype`` constraint could never
match. Every range must resolve to a single, valid datatype IRI.
"""

import pytest

from semantica.ontology import SHACLGenerator


@pytest.fixture
def generator():
    return SHACLGenerator()


def test_already_xsd_qualified_range_is_left_alone(generator):
    assert generator._resolve_xsd("xsd:string") == "xsd:string"
    assert generator._resolve_xsd("xsd:integer") == "xsd:integer"


def test_bare_names_still_map_to_xsd(generator):
    assert generator._resolve_xsd("string") == "xsd:string"
    assert generator._resolve_xsd("int") == "xsd:integer"
    assert generator._resolve_xsd("datetime") == "xsd:dateTime"


def test_absolute_iri_range_is_left_alone(generator):
    iri = "http://www.w3.org/2001/XMLSchema#string"
    assert generator._resolve_xsd(iri) == iri


def test_scheme_without_slashes_is_left_alone(generator):
    # A URN or DOI is an absolute IRI too, even without "//".
    assert generator._resolve_xsd("urn:example:datatype") == "urn:example:datatype"
    assert generator._resolve_xsd("doi:10.1000/182") == "doi:10.1000/182"


def test_property_shape_carries_a_single_prefix(generator):
    shape = generator._build_property_shape(
        {"type": "datatype", "range": "xsd:string", "name": "title"}
    )
    assert shape.datatype == "xsd:string"

    bare = generator._build_property_shape(
        {"type": "datatype", "range": "string", "name": "title"}
    )
    assert bare.datatype == "xsd:string"


# A resolved datatype reaches the serializers as either a declared prefix name
# or an absolute IRI. Turtle is the only format that pastes it through
# unmodified, so it was the only one that emitted the absolute form unbracketed.
rdflib = pytest.importorskip("rdflib")

from rdflib import Graph, URIRef  # noqa: E402

SH_DATATYPE = URIRef("http://www.w3.org/ns/shacl#datatype")

# range → the datatype IRI the serialized shapes have to carry
DATATYPE_CASES = [
    ("xsd:string", "http://www.w3.org/2001/XMLSchema#string"),
    ("string", "http://www.w3.org/2001/XMLSchema#string"),
    (
        "http://www.w3.org/2001/XMLSchema#string",
        "http://www.w3.org/2001/XMLSchema#string",
    ),
    ("urn:example:datatype", "urn:example:datatype"),
    ("doi:10.1000/182", "doi:10.1000/182"),
]

# rdflib's plugin name differs from the generator's format name for N-Triples
RDFLIB_FORMAT = {"turtle": "turtle", "json-ld": "json-ld", "n-triples": "nt"}


def _ontology_with_datatype(range_):
    return {
        "namespace": {"base_uri": "http://example.org/core/"},
        "classes": [{"name": "Person", "label": "Person"}],
        "properties": [
            {"name": "title", "type": "datatype", "range": range_, "domain": "Person"}
        ],
    }


@pytest.mark.parametrize("range_,expected", DATATYPE_CASES)
def test_turtle_serialization_round_trips_datatype(generator, range_, expected):
    shapes = generator.generate(_ontology_with_datatype(range_))
    parsed = Graph()
    parsed.parse(data=generator.serialize(shapes, "turtle"), format="turtle")

    assert {str(dt) for dt in parsed.objects(None, SH_DATATYPE)} == {expected}


@pytest.mark.parametrize("range_,expected", DATATYPE_CASES)
@pytest.mark.parametrize("fmt", sorted(RDFLIB_FORMAT))
def test_every_serialization_format_parses(generator, range_, expected, fmt):
    shapes = generator.generate(_ontology_with_datatype(range_))
    parsed = Graph()
    parsed.parse(data=generator.serialize(shapes, fmt), format=RDFLIB_FORMAT[fmt])

    assert {str(dt) for dt in parsed.objects(None, SH_DATATYPE)} == {expected}


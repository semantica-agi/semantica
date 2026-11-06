"""
Tests for semantica/explorer/utils/rdf_parser.py

Covers:
- parse_skos_file() with Turtle and RDF/XML formats
- ConceptScheme and Concept node extraction
- Label priority resolution (en > en-* > untagged > fallback)
- altLabel collection
- Structural edge extraction (broader/narrower/inScheme/related/topConceptOf/hasTopConcept)
- Edge filtering: edges with unknown endpoints are dropped
- Invalid bytes raises ValueError
- Empty graph returns empty lists
- _get_best_label and _get_all_labels helpers
"""

import pytest
import rdflib
from rdflib.namespace import RDF, SKOS

from semantica.explorer.utils.rdf_parser import (
    _get_all_labels,
    _get_best_label,
    parse_skos_file,
)

# ---------------------------------------------------------------------------
# Sample TTL fixtures
# ---------------------------------------------------------------------------

MINIMAL_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:Animals a skos:ConceptScheme ;
    skos:prefLabel "Animals"@en .

ex:Mammal a skos:Concept ;
    skos:prefLabel "Mammal"@en ;
    skos:inScheme ex:Animals .

ex:Dog a skos:Concept ;
    skos:prefLabel "Dog"@en ;
    skos:broader ex:Mammal ;
    skos:inScheme ex:Animals .
"""

MULTILINGUAL_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:C1 a skos:Concept ;
    skos:prefLabel "French Only"@fr ;
    skos:prefLabel "English Label"@en ;
    skos:prefLabel "British English"@en-GB ;
    skos:altLabel "Alias One"@en ;
    skos:altLabel "Alias Two"@en .
"""

UNTAGGED_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:C2 a skos:Concept ;
    skos:prefLabel "No Language Tag" ;
    skos:altLabel "alt1" ;
    skos:altLabel "alt2" .
"""

FALLBACK_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:C3 a skos:Concept ;
    skos:prefLabel "Nur Deutsch"@de .
"""

ALL_EDGE_TYPES_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:S1 a skos:ConceptScheme ;
    skos:prefLabel "Scheme One" .

ex:A a skos:Concept ;
    skos:prefLabel "A" ;
    skos:inScheme ex:S1 ;
    skos:topConceptOf ex:S1 .

ex:B a skos:Concept ;
    skos:prefLabel "B" ;
    skos:broader ex:A ;
    skos:inScheme ex:S1 .

ex:C a skos:Concept ;
    skos:prefLabel "C" ;
    skos:related ex:B ;
    skos:inScheme ex:S1 .

ex:S1 skos:hasTopConcept ex:A .
"""

# An edge pointing to an external URI not declared as a Concept/ConceptScheme
ORPHAN_EDGE_TTL = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .

ex:Known a skos:Concept ;
    skos:prefLabel "Known" ;
    skos:broader ex:ExternalConcept .
"""

MINIMAL_RDF_XML = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:skos="http://www.w3.org/2004/02/skos/core#"
         xmlns:ex="http://example.org/">

  <skos:ConceptScheme rdf:about="http://example.org/SchemeX">
    <skos:prefLabel xml:lang="en">Scheme X</skos:prefLabel>
  </skos:ConceptScheme>

  <skos:Concept rdf:about="http://example.org/ConceptY">
    <skos:prefLabel xml:lang="en">Concept Y</skos:prefLabel>
    <skos:inScheme rdf:resource="http://example.org/SchemeX"/>
  </skos:Concept>

</rdf:RDF>
"""


# ---------------------------------------------------------------------------
# Helper: get node by URI
# ---------------------------------------------------------------------------

def _node(nodes, uri):
    return next((n for n in nodes if n["id"] == uri), None)

def _edges_of_type(edges, edge_type):
    return [e for e in edges if e["type"] == edge_type]


# ---------------------------------------------------------------------------
# parse_skos_file — basic extraction
# ---------------------------------------------------------------------------

class TestParseSkosFileBasic:
    def test_returns_tuple_of_two_lists(self):
        nodes, edges = parse_skos_file(MINIMAL_TTL)
        assert isinstance(nodes, list)
        assert isinstance(edges, list)

    def test_extracts_concept_scheme(self):
        nodes, _ = parse_skos_file(MINIMAL_TTL)
        scheme = _node(nodes, "http://example.org/Animals")
        assert scheme is not None
        assert scheme["type"] == "skos:ConceptScheme"
        assert scheme["properties"]["content"] == "Animals"

    def test_extracts_concepts(self):
        nodes, _ = parse_skos_file(MINIMAL_TTL)
        uris = {n["id"] for n in nodes}
        assert "http://example.org/Mammal" in uris
        assert "http://example.org/Dog" in uris

    def test_concept_type_tag(self):
        nodes, _ = parse_skos_file(MINIMAL_TTL)
        mammal = _node(nodes, "http://example.org/Mammal")
        assert mammal["type"] == "skos:Concept"

    def test_node_has_required_keys(self):
        nodes, _ = parse_skos_file(MINIMAL_TTL)
        for n in nodes:
            assert "id" in n
            assert "type" in n
            assert "properties" in n
            assert "content" in n["properties"]
            assert "alt_labels" in n["properties"]
            assert "description" in n["properties"]

    def test_edge_has_required_keys(self):
        _, edges = parse_skos_file(MINIMAL_TTL)
        for e in edges:
            assert "source_id" in e
            assert "target_id" in e
            assert "type" in e
            assert "weight" in e
            assert "properties" in e

    def test_edge_weight_default(self):
        _, edges = parse_skos_file(MINIMAL_TTL)
        assert all(e["weight"] == 1.0 for e in edges)


# ---------------------------------------------------------------------------
# parse_skos_file — label priority
# ---------------------------------------------------------------------------

class TestLabelPriority:
    def test_en_preferred_over_fr(self):
        nodes, _ = parse_skos_file(MULTILINGUAL_TTL)
        c1 = _node(nodes, "http://example.org/C1")
        assert c1 is not None
        assert c1["properties"]["content"] == "English Label"

    def test_untagged_used_when_no_en(self):
        nodes, _ = parse_skos_file(UNTAGGED_TTL)
        c2 = _node(nodes, "http://example.org/C2")
        assert c2 is not None
        assert c2["properties"]["content"] == "No Language Tag"

    def test_fallback_to_any_language(self):
        nodes, _ = parse_skos_file(FALLBACK_TTL)
        c3 = _node(nodes, "http://example.org/C3")
        assert c3 is not None
        assert c3["properties"]["content"] == "Nur Deutsch"

    def test_uri_fragment_used_when_no_pref_label(self):
        ttl = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .
ex:NoLabel a skos:Concept .
"""
        nodes, _ = parse_skos_file(ttl)
        n = _node(nodes, "http://example.org/NoLabel")
        assert n is not None
        assert n["properties"]["content"] == "NoLabel"


# ---------------------------------------------------------------------------
# parse_skos_file — altLabels
# ---------------------------------------------------------------------------

class TestAltLabels:
    def test_alt_labels_collected(self):
        nodes, _ = parse_skos_file(MULTILINGUAL_TTL)
        c1 = _node(nodes, "http://example.org/C1")
        assert set(c1["properties"]["alt_labels"]) == {"Alias One", "Alias Two"}

    def test_alt_labels_empty_when_none(self):
        nodes, _ = parse_skos_file(MINIMAL_TTL)
        mammal = _node(nodes, "http://example.org/Mammal")
        assert mammal["properties"]["alt_labels"] == []

    def test_alt_labels_deduped(self):
        ttl = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex:   <http://example.org/> .
ex:C a skos:Concept ;
    skos:prefLabel "C" ;
    skos:altLabel "same"@en ;
    skos:altLabel "same"@en .
"""
        nodes, _ = parse_skos_file(ttl)
        c = _node(nodes, "http://example.org/C")
        assert c["properties"]["alt_labels"].count("same") == 1


# ---------------------------------------------------------------------------
# parse_skos_file — edge types
# ---------------------------------------------------------------------------

class TestEdgeTypes:
    def setup_method(self):
        self.nodes, self.edges = parse_skos_file(ALL_EDGE_TYPES_TTL)

    def test_in_scheme_edges(self):
        in_scheme = _edges_of_type(self.edges, "skos:inScheme")
        assert len(in_scheme) >= 2  # A, B, C all inScheme S1

    def test_broader_edge(self):
        broader = _edges_of_type(self.edges, "skos:broader")
        assert any(
            e["source_id"] == "http://example.org/B" and
            e["target_id"] == "http://example.org/A"
            for e in broader
        )

    def test_related_edge(self):
        related = _edges_of_type(self.edges, "skos:related")
        assert any(
            e["source_id"] == "http://example.org/C" and
            e["target_id"] == "http://example.org/B"
            for e in related
        )

    def test_top_concept_of_edge(self):
        top_concept_of = _edges_of_type(self.edges, "skos:topConceptOf")
        assert any(
            e["source_id"] == "http://example.org/A" and
            e["target_id"] == "http://example.org/S1"
            for e in top_concept_of
        )

    def test_has_top_concept_edge(self):
        has_top = _edges_of_type(self.edges, "skos:hasTopConcept")
        assert any(
            e["source_id"] == "http://example.org/S1" and
            e["target_id"] == "http://example.org/A"
            for e in has_top
        )


# ---------------------------------------------------------------------------
# parse_skos_file — edge filtering (orphan edges dropped)
# ---------------------------------------------------------------------------

class TestOrphanEdgeFiltering:
    def test_edge_to_external_uri_is_dropped(self):
        nodes, edges = parse_skos_file(ORPHAN_EDGE_TTL)
        # ex:ExternalConcept is not declared as a Concept/ConceptScheme
        # so the broader edge should be dropped
        assert len(edges) == 0

    def test_known_node_is_still_extracted(self):
        nodes, _ = parse_skos_file(ORPHAN_EDGE_TTL)
        assert _node(nodes, "http://example.org/Known") is not None


# ---------------------------------------------------------------------------
# parse_skos_file — empty and error cases
# ---------------------------------------------------------------------------

class TestEmptyAndErrors:
    def test_empty_graph_returns_empty_lists(self):
        empty_ttl = b"@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
        nodes, edges = parse_skos_file(empty_ttl)
        assert nodes == []
        assert edges == []

    def test_invalid_bytes_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to parse RDF file"):
            parse_skos_file(b"this is not valid turtle !!!!", rdf_format="turtle")

    def test_invalid_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="Failed to parse RDF file"):
            parse_skos_file(b"<not-valid-xml>", rdf_format="xml")


# ---------------------------------------------------------------------------
# parse_skos_file — RDF/XML format
# ---------------------------------------------------------------------------

class TestRdfXmlFormat:
    def test_parses_rdf_xml(self):
        pytest.importorskip("defusedxml")
        nodes, edges = parse_skos_file(MINIMAL_RDF_XML, rdf_format="xml")
        uris = {n["id"] for n in nodes}
        assert "http://example.org/SchemeX" in uris
        assert "http://example.org/ConceptY" in uris

    def test_rdf_xml_scheme_type(self):
        pytest.importorskip("defusedxml")
        nodes, _ = parse_skos_file(MINIMAL_RDF_XML, rdf_format="xml")
        scheme = _node(nodes, "http://example.org/SchemeX")
        assert scheme["type"] == "skos:ConceptScheme"
        assert scheme["properties"]["content"] == "Scheme X"

    def test_rdf_xml_in_scheme_edge(self):
        pytest.importorskip("defusedxml")
        _, edges = parse_skos_file(MINIMAL_RDF_XML, rdf_format="xml")
        in_scheme = _edges_of_type(edges, "skos:inScheme")
        assert any(
            e["source_id"] == "http://example.org/ConceptY" and
            e["target_id"] == "http://example.org/SchemeX"
            for e in in_scheme
        )


# ---------------------------------------------------------------------------
# _get_best_label helper
# ---------------------------------------------------------------------------

class TestGetBestLabel:
    def _make_graph(self, triples_ttl: bytes) -> rdflib.Graph:
        g = rdflib.Graph()
        g.parse(data=triples_ttl, format="turtle")
        return g

    def test_returns_en_when_available(self):
        ttl = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/> .
ex:X skos:prefLabel "English"@en ;
     skos:prefLabel "Deutsch"@de .
"""
        g = self._make_graph(ttl)
        result = _get_best_label(g, rdflib.URIRef("http://example.org/X"), SKOS.prefLabel)
        assert result == "English"

    def test_returns_empty_string_when_no_labels(self):
        g = rdflib.Graph()
        result = _get_best_label(g, rdflib.URIRef("http://example.org/X"), SKOS.prefLabel)
        assert result == ""

    def test_en_variant_beats_untagged(self):
        ttl = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/> .
ex:X skos:prefLabel "No Tag" ;
     skos:prefLabel "British"@en-GB .
"""
        g = self._make_graph(ttl)
        result = _get_best_label(g, rdflib.URIRef("http://example.org/X"), SKOS.prefLabel)
        assert result == "British"


# ---------------------------------------------------------------------------
# _get_all_labels helper
# ---------------------------------------------------------------------------

class TestGetAllLabels:
    def test_returns_all_values(self):
        ttl = b"""
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/> .
ex:X skos:altLabel "A"@en ;
     skos:altLabel "B"@fr ;
     skos:altLabel "C" .
"""
        g = rdflib.Graph()
        g.parse(data=ttl, format="turtle")
        result = _get_all_labels(g, rdflib.URIRef("http://example.org/X"), SKOS.altLabel)
        assert set(result) == {"A", "B", "C"}

    def test_returns_empty_list_when_no_labels(self):
        g = rdflib.Graph()
        result = _get_all_labels(g, rdflib.URIRef("http://example.org/X"), SKOS.altLabel)
        assert result == []

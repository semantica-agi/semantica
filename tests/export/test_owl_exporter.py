"""Tests for OWLExporter._export_owl_turtle fixes (issue #478).

Bug 1: invalid Turtle when subClassOf/domain/range present (predicates appended
       after a closing period).
Bug 2: data_properties silently dropped from Turtle output.
"""

import pytest
from semantica.export import OWLExporter


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def exporter():
    return OWLExporter()


@pytest.fixture
def full_ontology():
    return {
        "uri": "http://example.org/onto",
        "name": "TestOntology",
        "description": "A test ontology",
        "classes": [
            {
                "uri": "http://example.org/Person",
                "name": "Person",
            },
            {
                "uri": "http://example.org/Employee",
                "name": "Employee",
                "comment": "A person who is employed",
                "subClassOf": "http://example.org/Person",
            },
            {
                "uri": "http://example.org/Manager",
                "name": "Manager",
                "subClassOf": "http://example.org/Employee",
                "equivalentClass": "http://example.org/Supervisor",
            },
        ],
        "object_properties": [
            {
                "uri": "http://example.org/worksFor",
                "name": "worksFor",
                "domain": "http://example.org/Employee",
                "range": "http://example.org/Company",
            },
            {
                "uri": "http://example.org/manages",
                "name": "manages",
                "comment": "manages a team",
                "domain": ["http://example.org/Manager"],
                "range": ["http://example.org/Employee"],
            },
        ],
        "data_properties": [
            {
                "uri": "http://example.org/hasAge",
                "name": "hasAge",
                "domain": "http://example.org/Person",
                "range": "integer",
            },
            {
                "uri": "http://example.org/hasName",
                "name": "hasName",
                "comment": "full name",
                "domain": "http://example.org/Person",
                "range": "string",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Bug 1 — valid Turtle syntax
# ---------------------------------------------------------------------------

class TestTurtleSyntaxValidity:
    """Every subject block must have exactly one closing period at the end."""

    def _blocks(self, turtle: str) -> list[str]:
        """Split output into non-empty logical blocks (separated by blank lines)."""
        return [b.strip() for b in turtle.split("\n\n") if b.strip()]

    def test_no_triple_after_period(self, exporter, full_ontology):
        """No predicate line may appear after a line that ends with ' .'."""
        turtle = exporter._export_owl_turtle(full_ontology)
        lines = turtle.splitlines()
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            if stripped.endswith(" .") and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # next non-blank line must not be a predicate continuation
                if next_line:
                    assert not next_line.startswith("rdfs:"), (
                        f"Predicate continuation after closing '.' at line {i + 1}: "
                        f"{lines[i]!r} → {lines[i + 1]!r}"
                    )

    def test_each_subject_block_ends_with_period(self, exporter, full_ontology):
        """Every subject block (class / property declaration) ends with exactly one '.'."""
        turtle = exporter._export_owl_turtle(full_ontology)
        blocks = self._blocks(turtle)
        # skip the @prefix lines block and ontology declaration
        subject_blocks = [b for b in blocks if b.startswith("<http://")]
        for block in subject_blocks:
            assert block.endswith("."), f"Block does not end with '.': {block!r}"
            # Must not have a bare '.' on an interior line
            interior_lines = block.splitlines()[:-1]
            for ln in interior_lines:
                assert not ln.rstrip().endswith(" ."), (
                    f"Premature closing period inside block: {ln!r}"
                )

    def test_class_with_subclassof_is_valid(self, exporter):
        ontology = {
            "uri": "http://example.org/onto",
            "name": "T",
            "classes": [
                {
                    "uri": "http://example.org/Employee",
                    "name": "Employee",
                    "subClassOf": "http://example.org/Person",
                }
            ],
            "object_properties": [],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        # Must contain both predicates in the same block
        assert 'rdfs:label "Employee"' in turtle
        assert "rdfs:subClassOf <http://example.org/Person>" in turtle
        # The subClassOf line must NOT come after a closing period
        lines = turtle.splitlines()
        for i, ln in enumerate(lines):
            if "rdfs:subClassOf" in ln:
                # Search backwards for the closest period-terminated line
                for prev in reversed(lines[:i]):
                    prev_s = prev.rstrip()
                    if prev_s:
                        assert not prev_s.endswith(" ."), (
                            "rdfs:subClassOf appeared after a closed block"
                        )
                        break

    def test_object_property_with_domain_range_is_valid(self, exporter):
        ontology = {
            "uri": "http://example.org/onto",
            "name": "T",
            "classes": [],
            "object_properties": [
                {
                    "uri": "http://example.org/worksFor",
                    "name": "worksFor",
                    "domain": "http://example.org/Employee",
                    "range": "http://example.org/Company",
                }
            ],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:domain <http://example.org/Employee>" in turtle
        assert "rdfs:range <http://example.org/Company>" in turtle
        lines = turtle.splitlines()
        for i, ln in enumerate(lines):
            if "rdfs:domain" in ln or "rdfs:range" in ln:
                for prev in reversed(lines[:i]):
                    prev_s = prev.rstrip()
                    if prev_s:
                        assert not prev_s.endswith(" ."), (
                            "domain/range appeared after a closed block"
                        )
                        break

    def test_class_with_comment_subclassof_both_present(self, exporter):
        ontology = {
            "uri": "http://example.org/onto",
            "name": "T",
            "classes": [
                {
                    "uri": "http://example.org/X",
                    "name": "X",
                    "comment": "some comment",
                    "subClassOf": "http://example.org/Y",
                }
            ],
            "object_properties": [],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert 'rdfs:comment "some comment"' in turtle
        assert "rdfs:subClassOf <http://example.org/Y>" in turtle
        # block must end with single period
        block = [b for b in turtle.split("\n\n") if "owl:Class" in b][0].strip()
        assert block.endswith(".")
        assert block.count("\n.") == 0  # no bare period-only lines


# ---------------------------------------------------------------------------
# Bug 2 — data properties present in Turtle output
# ---------------------------------------------------------------------------

class TestDataPropertiesInTurtle:

    def test_data_property_declared_as_datatypeproperty(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "owl:DatatypeProperty" in turtle

    def test_data_property_uri_present(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "<http://example.org/hasAge>" in turtle
        assert "<http://example.org/hasName>" in turtle

    def test_data_property_label(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert 'rdfs:label "hasAge"' in turtle
        assert 'rdfs:label "hasName"' in turtle

    def test_data_property_domain(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "rdfs:domain <http://example.org/Person>" in turtle

    def test_data_property_range_uses_xsd_prefix(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "rdfs:range xsd:integer" in turtle
        assert "rdfs:range xsd:string" in turtle

    def test_data_property_comment(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert 'rdfs:comment "full name"' in turtle

    def test_data_properties_not_in_turtle_was_bug(self, exporter):
        """Regression: data_properties were silently dropped before the fix."""
        ontology = {
            "uri": "http://example.org/onto",
            "name": "T",
            "classes": [],
            "object_properties": [],
            "data_properties": [
                {
                    "uri": "http://example.org/birthDate",
                    "name": "birthDate",
                    "range": "date",
                }
            ],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert "owl:DatatypeProperty" in turtle, (
            "Data properties must appear in Turtle output (was silently dropped)"
        )
        assert "<http://example.org/birthDate>" in turtle
        assert "rdfs:range xsd:date" in turtle

    def test_data_property_block_ends_with_period(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        blocks = [b.strip() for b in turtle.split("\n\n") if "owl:DatatypeProperty" in b]
        assert blocks, "Expected at least one DatatypeProperty block"
        for block in blocks:
            assert block.endswith("."), f"DatatypeProperty block missing closing '.': {block!r}"


# ---------------------------------------------------------------------------
# Namespace and ontology header
# ---------------------------------------------------------------------------

class TestTurtleHeader:

    def test_prefix_declarations(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "@prefix rdf:" in turtle
        assert "@prefix rdfs:" in turtle
        assert "@prefix owl:" in turtle
        assert "@prefix xsd:" in turtle

    def test_ontology_declaration(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert "a owl:Ontology" in turtle
        assert 'rdfs:label "TestOntology"' in turtle
        assert 'owl:versionInfo "1.0"' in turtle

    def test_ontology_description_included(self, exporter, full_ontology):
        turtle = exporter._export_owl_turtle(full_ontology)
        assert 'rdfs:comment "A test ontology"' in turtle

    def test_ontology_without_description(self, exporter):
        ontology = {"uri": "http://example.org/onto", "name": "NoDesc",
                    "classes": [], "object_properties": [], "data_properties": []}
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:comment" not in turtle


# ---------------------------------------------------------------------------
# Object properties — list domain/range
# ---------------------------------------------------------------------------

class TestObjectPropertyListDomainRange:

    def test_list_domain(self, exporter):
        ontology = {
            "uri": "http://example.org/onto", "name": "T",
            "classes": [],
            "object_properties": [
                {
                    "uri": "http://example.org/p",
                    "name": "p",
                    "domain": ["http://example.org/A", "http://example.org/B"],
                }
            ],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:domain <http://example.org/A>" in turtle
        assert "rdfs:domain <http://example.org/B>" in turtle

    def test_list_range(self, exporter):
        ontology = {
            "uri": "http://example.org/onto", "name": "T",
            "classes": [],
            "object_properties": [
                {
                    "uri": "http://example.org/p",
                    "name": "p",
                    "range": ["http://example.org/X", "http://example.org/Y"],
                }
            ],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:range <http://example.org/X>" in turtle
        assert "rdfs:range <http://example.org/Y>" in turtle


# ---------------------------------------------------------------------------
# equivalentClass support (also tested under Bug 1 guard)
# ---------------------------------------------------------------------------

class TestEquivalentClass:

    def test_equivalent_class_in_turtle(self, exporter):
        ontology = {
            "uri": "http://example.org/onto", "name": "T",
            "classes": [
                {
                    "uri": "http://example.org/Manager",
                    "name": "Manager",
                    "equivalentClass": "http://example.org/Supervisor",
                }
            ],
            "object_properties": [],
            "data_properties": [],
        }
        turtle = exporter._export_owl_turtle(ontology)
        assert "owl:equivalentClass <http://example.org/Supervisor>" in turtle
        block = [b for b in turtle.split("\n\n") if "owl:Class" in b][0].strip()
        assert block.endswith(".")


# ---------------------------------------------------------------------------
# String escaping in Turtle literals (issue #478 review — escape_001)
# ---------------------------------------------------------------------------

class TestTurtleStringEscaping:
    """User-provided strings must be escaped before embedding in Turtle literals."""

    def _onto(self, **kwargs):
        base = {"uri": "http://example.org/onto", "name": "T",
                "classes": [], "object_properties": [], "data_properties": []}
        base.update(kwargs)
        return base

    def test_escape_ttl_str_double_quote(self, exporter):
        assert exporter._escape_ttl_str('say "hello"') == r'say \"hello\"'

    def test_escape_ttl_str_backslash(self, exporter):
        assert exporter._escape_ttl_str("C:\\path") == "C:\\\\path"

    def test_escape_ttl_str_newline(self, exporter):
        assert exporter._escape_ttl_str("line1\nline2") == "line1\\nline2"

    def test_escape_ttl_str_carriage_return(self, exporter):
        assert exporter._escape_ttl_str("a\rb") == "a\\rb"

    def test_escape_ttl_str_tab(self, exporter):
        assert exporter._escape_ttl_str("col1\tcol2") == "col1\\tcol2"

    def test_escape_ttl_str_combined(self, exporter):
        raw = 'back\\slash and "quote"\nnewline'
        escaped = exporter._escape_ttl_str(raw)
        assert '\\"' in escaped
        assert "\\\\" in escaped
        assert "\\n" in escaped

    def test_ontology_name_with_quote_is_escaped(self, exporter):
        ontology = self._onto(name='John"s Ontology')
        turtle = exporter._export_owl_turtle(ontology)
        assert 'rdfs:label "John\\"s Ontology"' in turtle
        assert 'rdfs:label "John"s Ontology"' not in turtle

    def test_ontology_description_with_quote_is_escaped(self, exporter):
        ontology = self._onto(description='Describes "things"')
        turtle = exporter._export_owl_turtle(ontology)
        assert 'rdfs:comment "Describes \\"things\\""' in turtle

    def test_class_name_with_quote_is_escaped(self, exporter):
        ontology = self._onto(classes=[{
            "uri": "http://example.org/C",
            "name": 'My "Special" Class',
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:label "My \"Special\" Class"' in turtle

    def test_class_comment_with_backslash_is_escaped(self, exporter):
        ontology = self._onto(classes=[{
            "uri": "http://example.org/C",
            "name": "C",
            "comment": "path is C:\\Users",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:comment "path is C:\\Users"' in turtle

    def test_class_comment_with_newline_is_escaped(self, exporter):
        ontology = self._onto(classes=[{
            "uri": "http://example.org/C",
            "name": "C",
            "comment": "line1\nline2",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:comment "line1\nline2"' in turtle

    def test_object_property_name_with_quote_is_escaped(self, exporter):
        ontology = self._onto(object_properties=[{
            "uri": "http://example.org/p",
            "name": 'has"Value',
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:label "has\"Value"' in turtle

    def test_object_property_comment_with_quote_is_escaped(self, exporter):
        ontology = self._onto(object_properties=[{
            "uri": "http://example.org/p",
            "name": "p",
            "comment": 'links "A" to "B"',
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:comment "links \"A\" to \"B\""' in turtle

    def test_data_property_name_with_quote_is_escaped(self, exporter):
        ontology = self._onto(data_properties=[{
            "uri": "http://example.org/dp",
            "name": 'the "name" prop',
            "range": "string",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:label "the \"name\" prop"' in turtle

    def test_data_property_comment_with_quote_is_escaped(self, exporter):
        ontology = self._onto(data_properties=[{
            "uri": "http://example.org/dp",
            "name": "dp",
            "comment": 'see "spec" §3',
            "range": "string",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert r'rdfs:comment "see \"spec\" §3"' in turtle

    def test_plain_strings_unchanged(self, exporter):
        """Strings without special chars must pass through unchanged."""
        ontology = self._onto(
            name="MyOntology",
            classes=[{"uri": "http://example.org/C", "name": "SafeName"}],
        )
        turtle = exporter._export_owl_turtle(ontology)
        assert 'rdfs:label "MyOntology"' in turtle
        assert 'rdfs:label "SafeName"' in turtle


# ---------------------------------------------------------------------------
# Null / missing optional fields — no KeyError raised (review null_check_001-3)
# ---------------------------------------------------------------------------

class TestNullFieldHandling:
    """Optional fields absent from dicts must not raise KeyError."""

    def _onto(self, **kwargs):
        base = {"uri": "http://example.org/onto", "name": "T",
                "classes": [], "object_properties": [], "data_properties": []}
        base.update(kwargs)
        return base

    def test_class_no_optional_fields(self, exporter):
        ontology = self._onto(classes=[{"uri": "http://example.org/C", "name": "C"}])
        turtle = exporter._export_owl_turtle(ontology)
        assert "owl:Class" in turtle

    def test_object_property_no_domain_no_range(self, exporter):
        ontology = self._onto(object_properties=[{
            "uri": "http://example.org/p", "name": "p"
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "owl:ObjectProperty" in turtle
        assert "rdfs:domain" not in turtle
        assert "rdfs:range" not in turtle

    def test_data_property_no_domain_no_range(self, exporter):
        ontology = self._onto(data_properties=[{
            "uri": "http://example.org/dp", "name": "dp"
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "owl:DatatypeProperty" in turtle
        assert "rdfs:domain" not in turtle
        assert "rdfs:range" not in turtle

    def test_data_property_none_domain(self, exporter):
        """Explicit None value for domain must not raise KeyError."""
        ontology = self._onto(data_properties=[{
            "uri": "http://example.org/dp", "name": "dp",
            "domain": None, "range": "string",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:domain" not in turtle

    def test_data_property_none_range(self, exporter):
        """Explicit None value for range must not raise KeyError."""
        ontology = self._onto(data_properties=[{
            "uri": "http://example.org/dp", "name": "dp",
            "domain": "http://example.org/C", "range": None,
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:range" not in turtle

    def test_object_property_none_domain(self, exporter):
        ontology = self._onto(object_properties=[{
            "uri": "http://example.org/p", "name": "p",
            "domain": None, "range": "http://example.org/X",
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:domain" not in turtle

    def test_object_property_none_range(self, exporter):
        ontology = self._onto(object_properties=[{
            "uri": "http://example.org/p", "name": "p",
            "domain": "http://example.org/A", "range": None,
        }])
        turtle = exporter._export_owl_turtle(ontology)
        assert "rdfs:range" not in turtle

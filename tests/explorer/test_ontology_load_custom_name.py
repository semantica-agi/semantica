"""Regression tests: ``POST /api/ontology/load`` ignored ``name`` and ``description``.

``LoadOntologyRequest`` declares both fields, and the Explorer's Load Ontology
dialog exposes them under Advanced options as "Custom display name" and
"Description", but the handler never read either. The registry entry and the
response were built from the parsed file's own metadata instead. When that
metadata carries no name, it falls back to the server-side temporary file the
content is written to, so the ontology lands in the registry as e.g.
``tmp9mqzirf8.ttl``.

Both the OntologyIngestor path and the basic-parser fallback path build the
entry, so both are covered.
"""

import pytest

# fastapi ships in the optional `explorer` extra, not in `dev`, so this module
# must skip rather than fail collection when it is absent.
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from semantica.context.context_graph import ContextGraph  # noqa: E402
from semantica.explorer.app import create_app  # noqa: E402
from semantica.explorer.session import GraphSession  # noqa: E402

UNTITLED_URI = "http://example.org/untitled"
UNTITLED = f"""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<{UNTITLED_URI}> a owl:Ontology .
<{UNTITLED_URI}#Thing> a owl:Class ; rdfs:label "Thing" .
"""

LABELLED_URI = "http://example.org/labelled"
LABELLED = f"""
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<{LABELLED_URI}> a owl:Ontology ; rdfs:label "Labelled Ontology" .
<{LABELLED_URI}#Thing> a owl:Class .
"""


def _client() -> TestClient:
    return TestClient(create_app(session=GraphSession(ContextGraph(advanced_analytics=False))))


def _load(client: TestClient, content: str, **fields) -> dict:
    response = client.post(
        "/api/ontology/load", json={"content": content, "format": "turtle", **fields}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _entry(client: TestClient, uri: str) -> dict:
    registry = client.get("/api/ontology/registry").json()
    matches = [entry for entry in registry if entry["uri"] == uri]
    assert matches, f"{uri} not in registry: {[e['uri'] for e in registry]}"
    return matches[0]


def test_custom_name_and_description_are_used():
    """Fails before the fix: name is the temp file name, description is None."""
    with _client() as client:
        loaded = _load(client, UNTITLED, name="Custom Name", description="Custom description")
        entry = _entry(client, UNTITLED_URI)

    assert loaded["name"] == "Custom Name"
    assert entry["name"] == "Custom Name"
    assert entry["description"] == "Custom description"


def test_custom_name_overrides_parsed_label():
    """A caller-supplied name wins over the ontology's own rdfs:label."""
    with _client() as client:
        loaded = _load(client, LABELLED, name="Custom Name")
        entry = _entry(client, LABELLED_URI)

    assert loaded["name"] == "Custom Name"
    assert entry["name"] == "Custom Name"


def test_parsed_label_still_used_when_name_omitted():
    """Omitting name keeps the existing behaviour of using the parsed label."""
    with _client() as client:
        loaded = _load(client, LABELLED)
        entry = _entry(client, LABELLED_URI)

    assert loaded["name"] == "Labelled Ontology"
    assert entry["name"] == "Labelled Ontology"


def _force_fallback_parser(monkeypatch) -> None:
    """Make OntologyIngestor raise so the handler takes the basic-parser path."""
    import semantica.ingest.ontology_ingestor as ontology_ingestor

    class _FailingIngestor:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("force the fallback parser")

    monkeypatch.setattr(ontology_ingestor, "OntologyIngestor", _FailingIngestor)


def test_custom_name_used_on_fallback_parser_path(monkeypatch):
    """The basic-parser fallback builds its own registry entry and must honour
    the same fields."""
    _force_fallback_parser(monkeypatch)

    with _client() as client:
        loaded = _load(client, UNTITLED, name="Custom Name", description="Custom description")
        registry = client.get("/api/ontology/registry").json()

    assert loaded["name"] == "Custom Name"
    entry = next(e for e in registry if e["name"] == "Custom Name")
    assert entry["description"] == "Custom description"


@pytest.mark.parametrize("fallback_parser", [False, True], ids=["ingestor", "fallback-parser"])
def test_blank_name_and_description_behave_like_omitted(monkeypatch, fallback_parser):
    """A blank value means "not set", as in the dialog's "Leave blank to use
    ontology title" placeholder (OntologyLoader.tsx already sends
    ``customName || undefined``). Storing "" verbatim would leave a nameless
    row in the registry."""
    if fallback_parser:
        _force_fallback_parser(monkeypatch)

    with _client() as client:
        omitted = _load(client, LABELLED)
        omitted_registry = client.get("/api/ontology/registry").json()
    with _client() as client:
        blank = _load(client, LABELLED, name="", description="")
        blank_registry = client.get("/api/ontology/registry").json()

    assert blank["name"] == omitted["name"] != ""
    assert [(e["name"], e["description"]) for e in blank_registry] == [
        (e["name"], e["description"]) for e in omitted_registry
    ]

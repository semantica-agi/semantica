"""Run generated read queries through a real SPARQL parser below HTTP."""

from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from semantica.triplet_store import TripletStore

ox = pytest.importorskip("pyoxigraph")

EX = "http://example.org/"


@pytest.fixture(params=["blazegraph", "rdf4j", "jena", "anzo"])
def remote_store(request, monkeypatch):
    server = ox.Store()
    server.update(
        f"INSERT DATA {{ <{EX}alice> <{EX}knows> <{EX}bob> . "
        f"<{EX}bob> <{EX}knows> <{EX}carol> . "
        f"<{EX}alice> <{EX}likes> <{EX}carol> }}"
    )
    queries = []

    def select(query, **options):
        queries.append(query)
        return server.query(query, **options).serialize(
            format=ox.QueryResultsFormat.JSON
        )

    def post(url, **kwargs):
        response = requests.Response()
        try:
            data = kwargs["data"]
            if isinstance(data, str):
                server.load(input=data, format=ox.RdfFormat.N_TRIPLES)
                response.status_code = 204
            elif "update" in data:
                server.update(data["update"])
                response.status_code = 204
            else:
                response._content = select(data["query"])
                response.status_code = 200
        except SyntaxError as exc:
            response._content = str(exc).encode()
            response.status_code = 400
        return response

    def urlopen(req):
        if req.data is not None:
            server.update(req.data.decode())
            return BytesIO()
        params = parse_qs(urlsplit(req.full_url).query)
        graph_uri = params["default-graph-uri"][0]
        # RDFLib uses this identifier for its default graph.
        graph = (
            ox.DefaultGraph()
            if graph_uri == "urn:x-rdflib:default"
            else ox.NamedNode(graph_uri)
        )
        try:
            response = BytesIO(select(params["query"][0], default_graph=graph))
        except SyntaxError as exc:
            raise HTTPError(req.full_url, 400, str(exc), {}, None) from exc
        response.headers = {"Content-Type": "application/sparql-results+json"}
        return response

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(
        requests, "get", lambda *a, **kw: type("Response", (), {"status_code": 200})()
    )
    monkeypatch.setattr("rdflib.plugins.stores.sparqlconnector.urlopen", urlopen)
    store = TripletStore(
        backend=request.param,
        endpoint="http://store.invalid/ds",
        dataset_uri=EX + "dataset",
        enable_caching=False,
        enable_optimization=False,
    )
    return store, queries, server


@pytest.mark.parametrize(
    "criteria, count",
    [
        ({}, 3),
        ({"subject": EX + "alice"}, 2),
        ({"predicate": EX + "knows"}, 2),
        ({"object": EX + "bob"}, 1),
        ({"subject": EX + "alice", "predicate": EX + "knows", "object": EX + "bob"}, 1),
        ({"subject": EX + "carol"}, 0),
    ],
)
def test_get_triplets_filters_are_valid_sparql(remote_store, criteria, count):
    store, queries, _ = remote_store

    actual = store.get_triplets(**criteria)

    assert len(actual) == count
    for key, value in criteria.items():
        assert all(getattr(triplet, key) == value for triplet in actual)
    assert queries


def test_get_triplets_preserves_literal_terms(remote_store):
    store, _, server = remote_store
    backend = store.backend_type
    xsd = "http://www.w3.org/2001/XMLSchema#"
    samples = [
        ('"42"^^<%sinteger>' % xsd, "42", {"datatype": xsd + "integer"}),
        ('"true"^^<%sboolean>' % xsd, "true", {"datatype": xsd + "boolean"}),
        ('"2026-11-07"^^<%sdate>' % xsd, "2026-11-07", {"datatype": xsd + "date"}),
        ('"plain"', "plain", {}),
        ('"string"^^<%sstring>' % xsd, "string", {}),
        ('"café"@fr', "café", {"language": "fr"}),
        ('"colour"@en-GB', "colour", {"language": "en-gb"}),
        (
            '"say \\"hello\\"\\nnext"^^<%stext>' % EX,
            'say "hello"\nnext',
            {"datatype": EX + "text"},
        ),
        (
            '"https://example.org/doc"^^<%sanyURI>' % xsd,
            "https://example.org/doc",
            {"datatype": xsd + "anyURI"},
        ),
        ('"http://example.org/home"@en', "http://example.org/home", {"language": "en"}),
        ("<%sbob>" % EX, EX + "bob", {}),
    ]
    server.clear()
    data = " . ".join(
        f"<{EX}alice> <{EX}p{i}> {term}" for i, (term, _, _) in enumerate(samples)
    )
    server.update(f"INSERT DATA {{ {data} }}")
    expected = {(q.subject, q.predicate, q.object) for q in server}

    actual = store.get_triplets()

    assert len(actual) == len(samples)
    by_predicate = {triplet.predicate: triplet for triplet in actual}
    for i, (_, value, metadata) in enumerate(samples):
        triplet = by_predicate[EX + f"p{i}"]
        assert triplet.object == value
        assert triplet.metadata == {"source": backend, **metadata}

    copy = TripletStore(backend="oxigraph", enable_caching=False)
    for triplet in actual:
        assert copy.add_triplet(triplet)["success"]
        assert store.add_triplet(triplet)["success"]
    assert {(q.subject, q.predicate, q.object) for q in server} == expected
    assert {
        (q.subject, q.predicate, q.object) for q in copy._store_backend.store
    } == expected
    for triplet in actual:
        assert store.delete_triplet(triplet)["success"]
    assert len(server) == 0


def test_get_triplets_blank_nodes_keep_source_metadata(remote_store):
    store, _, server = remote_store
    server.clear()
    data = f"<{EX}alice> <{EX}knows> _:friend"
    server.update(f"INSERT DATA {{ {data} }}")

    actual = store.get_triplets()

    assert len(actual) == 1
    assert actual[0].object == next(iter(server)).object.value
    assert actual[0].metadata == {"source": store.backend_type}


@pytest.mark.parametrize("remote_store", ["blazegraph", "rdf4j", "anzo"], indirect=True)
def test_get_triplets_language_takes_precedence(remote_store, monkeypatch):
    store, _, _ = remote_store
    binding = {
        "o": {
            "type": "literal",
            "value": "colour",
            "xml:lang": "en-GB",
            "datatype": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
        }
    }
    monkeypatch.setattr(
        store._store_backend, "execute_sparql", lambda *a, **kw: {"bindings": [binding]}
    )

    assert store.get_triplets()[0].metadata == {
        "source": store.backend_type,
        "language": "en-GB",
    }

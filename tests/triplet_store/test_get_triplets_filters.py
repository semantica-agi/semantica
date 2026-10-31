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
    # RDFLib requests this graph via default-graph-uri; isolate query syntax.
    server.update(
        "INSERT { GRAPH <urn:x-rdflib:default> { ?s ?p ?o } } WHERE { ?s ?p ?o }"
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
            response._content = select(kwargs["data"]["query"])
            response.status_code = 200
        except SyntaxError as exc:
            response._content = str(exc).encode()
            response.status_code = 400
        return response

    def urlopen(req):
        params = parse_qs(urlsplit(req.full_url).query)
        graph = ox.NamedNode(params["default-graph-uri"][0])
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
    return store, queries


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
    store, queries = remote_store

    actual = store.get_triplets(**criteria)

    assert len(actual) == count
    for key, value in criteria.items():
        assert all(getattr(triplet, key) == value for triplet in actual)
    assert queries

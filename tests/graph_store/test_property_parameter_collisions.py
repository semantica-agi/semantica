"""Property names must not replace the parameters identifying graph entities."""

import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from semantica.graph_store import amazon_neptune
from semantica.graph_store.graph_store import GraphStore


@pytest.fixture(params=["falkordb", "neptune"])
def recording_store(request, monkeypatch):
    monkeypatch.setattr(amazon_neptune, "NEO4J_AVAILABLE", True)
    store = GraphStore(backend=request.param, iam_auth=False)
    calls = []

    def run(query, params):
        calls.append((query, params))
        if request.param == "falkordb":
            return SimpleNamespace(
                result_set=[[params.get("node_id", 9), {}, ["Person"]]]
            )
        if "CREATE (a)-[r:" in query:
            return [{"r": {"~id": params["rel_id"], "~type": "LINK"}}]
        return [{"n": {"~id": params["node_id"], "~labels": ["Person"]}}]

    if request.param == "falkordb":
        store._store_backend._graph = SimpleNamespace(query=run)
    else:
        driver = MagicMock()
        driver.session.return_value.__enter__.return_value.run.side_effect = run
        store._store_backend._driver = driver
        store._store_backend._connected = True
    return store, calls


def _assert_properties_bound(query, params, properties):
    assignments = dict(re.findall(r"(?:\b[nr]\.)?(\w+)\s*[:=]\s*\$(\w+)", query))
    assert {key: params[assignments[key]] for key in properties} == properties


@pytest.mark.parametrize(
    "properties",
    [
        {},
        {"weight": 0.5},
        {"start_id": 3, "end_id": 4, "rel_id": "external", "prop_0": 8},
    ],
)
def test_relationship_properties_do_not_replace_endpoints(recording_store, properties):
    store, calls = recording_store

    store.create_relationship(1, 2, "LINK", properties)

    query, params = calls[-1]
    expected = ("1", "2") if store.backend == "neptune" else (1, 2)
    assert (params["start_id"], params["end_id"]) == expected
    _assert_properties_bound(query, params, properties)
    if store.backend == "neptune":
        assert params["rel_id"] != properties.get("rel_id")


@pytest.mark.parametrize("merge", [True, False])
@pytest.mark.parametrize("recording_store", ["falkordb"], indirect=True)
def test_falkordb_update_property_does_not_replace_node_id(recording_store, merge):
    store, calls = recording_store
    properties = {"node_id": 99, "props": "external", "prop_0": [1, 2]}

    updated = store.update_node(1, properties, merge=merge)

    query, params = calls[-1]
    assert updated["id"] == 1
    assert params["node_id"] == 1
    if merge:
        _assert_properties_bound(query, params, properties)
    else:
        assert params["props"] == properties


@pytest.mark.parametrize("merge", [True, False])
@pytest.mark.parametrize("recording_store", ["neptune"], indirect=True)
def test_neptune_node_property_does_not_replace_native_id(recording_store, merge):
    store, calls = recording_store
    properties = {"id": "alice", "node_id": "external", "prop_0": "retained"}

    created = store.create_node(["Person"], properties, merge=merge)

    query, params = calls[-1]
    assert created["id"] == "alice"
    assert params["node_id"] == "alice"
    _assert_properties_bound(
        query, params, {key: value for key, value in properties.items() if key != "id"}
    )
    assert properties["id"] == "alice"

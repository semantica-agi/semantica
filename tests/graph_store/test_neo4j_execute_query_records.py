"""Regression tests for #1727: Neo4jStore.execute_query must convert
Node/Relationship record values via the Mapping protocol instead of
degrading them to a list of property names, and must keep the entity's
graph identity (labels/type and element id) alongside the properties
under reserved, underscore-prefixed keys.

neo4j.graph.Node and neo4j.graph.Relationship subclass Entity, which
implements the Mapping protocol (items()/keys()) while __iter__ yields
property *keys*. The conversion in execute_query checked __iter__ before
items(), so ``MATCH (n) RETURN n`` came back as ``{"n": ["name", "age"]}``
and property values were silently lost. GraphStore.query and DecisionQuery
read decisions through this path.

Identity lives in a reserved "_"-prefixed namespace ("_labels" for
nodes, "_type" for relationships, "_element_id" for both) so user
properties named "labels"/"type"/"element_id" (no underscore) are never
shadowed. User properties whose names already start with "_" — e.g.
"_labels", "_type", "_element_id" — will be overwritten by the
corresponding identity key; such property names are therefore reserved and
should not be used in Neo4j schemas managed by this library.

Conversion is recursive: entities nested in ``collect(n)`` results or
Cypher map literals are fully converted. Records whose columns contain
only string, integer, float, bool, None, Duration, or spatial Point
values are JSON-serializable. Records containing neo4j.time.DateTime,
Date, or Time property values are NOT JSON-serializable because those
types have no built-in JSON representation and are returned as driver
objects by the passthrough scalar branch.

neo4j.graph.Path objects are iterable over their *relationships only*
(``Path.__iter__`` returns ``iter(self._relationships)``). Iterating a
Path therefore produces a list of converted Relationship dicts; the
start node, end node, and all intermediate nodes are absent from the
converted output. This is the documented flat-record contract for Path
columns; callers that need node data from a path must access
``path.nodes`` before conversion.

The tests feed real driver ``neo4j.graph.Node``/``Relationship``/``Path``
objects through execute_query (mirroring the issue reproduction, no
server needed), pin the unchanged behavior for plain mappings, iterables,
paths and primitives, and cover the related
``GraphAnalytics.connected_components`` envelope read reported in the
same issue.

The neo4j driver is an optional dependency (``graph-neo4j`` extra), so its
import is guarded: the driver-dependent tests skip when the extra is not
installed, while the backend-independent analytics test still runs.
"""

import json
import logging
import unittest
from types import MappingProxyType
from unittest.mock import MagicMock

from semantica.graph_store.graph_store import GraphAnalytics
from semantica.graph_store.neo4j_store import Neo4jStore
from semantica.utils.progress_tracker import get_progress_tracker

try:
    from neo4j.graph import Graph, Node, Relationship

    NEO4J_DRIVER_AVAILABLE = True
except ImportError:
    NEO4J_DRIVER_AVAILABLE = False
    Graph = Node = Relationship = None


class _FakeRecord(dict):
    def keys(self):
        return list(super().keys())


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter([_FakeRecord(r) for r in self._rows])

    def keys(self):
        return list(self._rows[0].keys())

    def consume(self):
        summary = MagicMock()
        summary.counters = None
        summary.result_available_after = 0
        summary.result_consumed_after = 0
        return summary


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def run(self, query, parameters=None, **kwargs):
        return _FakeResult(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _make_store(rows):
    store = Neo4jStore.__new__(Neo4jStore)
    store.logger = logging.getLogger("test")
    store.progress_tracker = get_progress_tracker()
    store.get_session = lambda *a, **k: _FakeSession(rows)
    store.database = None
    return store


class _FakeNeo4jBackend:
    """Backend double whose class name routes GraphAnalytics to the Neo4j
    branch and whose execute_query returns the real envelope shape."""

    def __init__(self, envelope):
        self._envelope = envelope

    def execute_query(self, query, params):
        return self._envelope


@unittest.skipUnless(
    NEO4J_DRIVER_AVAILABLE, "requires the graph-neo4j extra (neo4j driver)"
)
class TestExecuteQueryRecordConversion(unittest.TestCase):
    def test_node_value_keeps_properties_and_identity(self):
        node = Node(Graph(), "4:abc:1", 1, ["Person"], {"name": "Alice", "age": 30})
        store = _make_store([{"n": node, "name": "Alice"}])

        result = store.execute_query("MATCH (n:Person) RETURN n, n.name AS name")

        self.assertEqual(
            result["records"],
            [
                {
                    "n": {
                        "name": "Alice",
                        "age": 30,
                        "_labels": ["Person"],
                        "_element_id": "4:abc:1",
                    },
                    "name": "Alice",
                }
            ],
        )

    def test_node_with_multiple_labels_sorts_labels(self):
        node = Node(Graph(), "4:abc:2", 2, ["Person", "Leader"], {})
        store = _make_store([{"n": node}])

        result = store.execute_query("MATCH (n) RETURN n")

        self.assertEqual(
            result["records"],
            [{"n": {"_labels": ["Leader", "Person"], "_element_id": "4:abc:2"}}],
        )

    def test_relationship_value_keeps_properties_and_identity(self):
        graph = Graph()
        rel = graph.relationship_type("KNOWS")(graph, "4:rel:9", 9, {"since": 2020})
        store = _make_store([{"r": rel}])

        result = store.execute_query("MATCH ()-[r:KNOWS]->() RETURN r")

        self.assertEqual(
            result["records"],
            [{"r": {"since": 2020, "_type": "KNOWS", "_element_id": "4:rel:9"}}],
        )

    def test_identity_keys_never_shadow_user_properties(self):
        # "type"/"labels" are realistic property names (RDF-style data);
        # the reserved "_"-prefixed namespace must keep user data and
        # identity separately addressable, each with one fixed meaning.
        graph = Graph()
        rel = graph.relationship_type("KNOWS")(
            graph, "4:rel:1", 9, {"type": "rdf:Resource", "since": 2020}
        )
        node = Node(Graph(), "4:abc:3", 3, ["Person"], {"labels": "user-defined"})
        store = _make_store([{"r": rel, "n": node}])

        result = store.execute_query("MATCH (n)-[r]->() RETURN n, r")

        record = result["records"][0]
        self.assertEqual(record["n"]["labels"], "user-defined")
        self.assertEqual(record["n"]["_labels"], ["Person"])
        self.assertEqual(record["n"]["_element_id"], "4:abc:3")
        self.assertEqual(record["r"]["type"], "rdf:Resource")
        self.assertEqual(record["r"]["_type"], "KNOWS")
        self.assertEqual(record["r"]["_element_id"], "4:rel:1")

    def test_reserved_key_node_labels_overwritten_by_identity(self):
        # A user property literally named "_labels" occupies the same key that
        # _convert_query_value uses for the node's label list.  The identity
        # value is written last and therefore wins; the user value is lost.
        # This is documented behaviour: "_labels", "_type", and "_element_id"
        # are reserved and must not be used as Neo4j property names in schemas
        # managed by this library.
        node = Node(Graph(), "4:abc:10", 10, ["Tag"], {"_labels": "user-value", "x": 1})
        store = _make_store([{"n": node}])

        result = store.execute_query("MATCH (n) RETURN n")

        record = result["records"][0]["n"]
        # Identity wins: the sorted label list replaces the user string.
        self.assertEqual(record["_labels"], ["Tag"])
        # The user string "user-value" is no longer accessible.
        self.assertNotEqual(record["_labels"], "user-value")
        # Unrelated properties are unaffected.
        self.assertEqual(record["x"], 1)
        self.assertEqual(record["_element_id"], "4:abc:10")

    def test_reserved_key_node_element_id_overwritten_by_identity(self):
        # A user property named "_element_id" is overwritten by the node's
        # actual element_id string.  Same reservation rule as "_labels".
        node = Node(
            Graph(), "4:abc:11", 11, ["Resource"], {"_element_id": "app-id-xyz"}
        )
        store = _make_store([{"n": node}])

        result = store.execute_query("MATCH (n) RETURN n")

        record = result["records"][0]["n"]
        # Identity wins: the driver's element_id replaces the user value.
        self.assertEqual(record["_element_id"], "4:abc:11")
        self.assertNotEqual(record["_element_id"], "app-id-xyz")

    def test_reserved_key_relationship_type_overwritten_by_identity(self):
        # A user property named "_type" on a Relationship is overwritten by
        # the relationship type string.  Same reservation rule as "_labels".
        graph = Graph()
        rel = graph.relationship_type("KNOWS")(
            graph, "4:rel:20", 20, {"_type": "rdf:type", "since": 2021}
        )
        store = _make_store([{"r": rel}])

        result = store.execute_query("MATCH ()-[r]->() RETURN r")

        record = result["records"][0]["r"]
        # Identity wins: the relationship type replaces the user value.
        self.assertEqual(record["_type"], "KNOWS")
        self.assertNotEqual(record["_type"], "rdf:type")
        # Unrelated properties are unaffected.
        self.assertEqual(record["since"], 2021)
        self.assertEqual(record["_element_id"], "4:rel:20")

    def test_collect_of_nodes_converts_recursively_and_is_json_serializable(self):
        graph = Graph()
        nodes = [
            Node(graph, "4:abc:4", 4, ["Person"], {"name": "Alice"}),
            Node(graph, "4:abc:5", 5, ["Person"], {"name": "Bob"}),
        ]
        store = _make_store([{"ns": nodes}])

        result = store.execute_query("MATCH (n:Person) RETURN collect(n) AS ns")

        self.assertEqual(
            result["records"],
            [
                {
                    "ns": [
                        {
                            "name": "Alice",
                            "_labels": ["Person"],
                            "_element_id": "4:abc:4",
                        },
                        {
                            "name": "Bob",
                            "_labels": ["Person"],
                            "_element_id": "4:abc:5",
                        },
                    ]
                }
            ],
        )
        json.dumps(result["records"])  # records are plain Python data

    def test_map_with_nested_entity_converts_recursively(self):
        node = Node(Graph(), "4:abc:6", 6, ["Person"], {"name": "Alice"})
        store = _make_store([{"m": {"person": node, "count": 2}}])

        result = store.execute_query("RETURN {person: n, count: 2} AS m")

        self.assertEqual(
            result["records"][0]["m"]["person"],
            {"name": "Alice", "_labels": ["Person"], "_element_id": "4:abc:6"},
        )
        self.assertEqual(result["records"][0]["m"]["count"], 2)
        json.dumps(result["records"])

    def test_mapping_value_keeps_entries_without_identity_keys(self):
        # MappingProxyType exposes items() and __iter__ exactly like the
        # driver's Node/Relationship entities (Relationship shares the
        # Entity/Mapping base with Node), so it pins the generic mapping
        # branch: plain mappings stay plain dicts and gain no identity keys.
        mapping = MappingProxyType({"a": 1, "b": 2})
        store = _make_store([{"m": mapping}])

        result = store.execute_query("RETURN $m AS m", {"m": mapping})

        self.assertEqual(result["records"], [{"m": {"a": 1, "b": 2}}])

    def test_iterable_value_stays_a_list(self):
        store = _make_store([{"xs": [1, 2, 3]}])

        result = store.execute_query("RETURN [1, 2, 3] AS xs")

        self.assertEqual(result["records"], [{"xs": [1, 2, 3]}])

    def test_real_path_converts_to_list_of_relationship_dicts_only(self):
        # neo4j.graph.Path.__iter__ is defined as:
        #     def __iter__(self) -> Iterator[Relationship]:
        #         return iter(self._relationships)
        # It yields Relationship objects only — nodes are NOT yielded.
        # _convert_query_value therefore produces a list of converted
        # Relationship dicts; the start/end nodes are absent from the result.
        # This is the documented flat-record contract for Path columns.
        graph = Graph()
        n1 = Node(graph, "4:a:10", 10, ["Person"], {"name": "Alice"})
        n2 = Node(graph, "4:a:20", 20, ["Person"], {"name": "Bob"})
        RelKnows = graph.relationship_type("KNOWS")
        r1 = RelKnows(graph, "4:rel:1", 1, {"since": 2020})
        r1._start_node = n1
        r1._end_node = n2

        from neo4j.graph import Path

        path = Path(n1, r1)
        store = _make_store([{"p": path}])

        result = store.execute_query("MATCH p = (a)-[r]->(b) RETURN p")

        records = result["records"]
        self.assertEqual(len(records), 1)
        path_value = records[0]["p"]

        # The converted path is a list containing one Relationship dict.
        self.assertIsInstance(path_value, list)
        self.assertEqual(len(path_value), 1)

        rel_dict = path_value[0]
        # Relationship properties and identity are present.
        self.assertEqual(rel_dict["since"], 2020)
        self.assertEqual(rel_dict["_type"], "KNOWS")
        self.assertEqual(rel_dict["_element_id"], "4:rel:1")

        # Node data (Alice, Bob) is absent — Path.__iter__ does not yield nodes.
        self.assertNotIn("name", rel_dict)
        path_str = str(path_value)
        self.assertNotIn("Alice", path_str)
        self.assertNotIn("Bob", path_str)

        # The result is JSON-serializable (all values are plain Python).
        json.dumps(records)

    def test_multi_hop_path_produces_one_rel_dict_per_hop(self):
        # A two-hop path yields two Relationship dicts and no node dicts.
        graph = Graph()
        n1 = Node(graph, "4:a:1", 1, ["A"], {"x": 1})
        n2 = Node(graph, "4:a:2", 2, ["B"], {"x": 2})
        n3 = Node(graph, "4:a:3", 3, ["C"], {"x": 3})
        r1 = graph.relationship_type("FIRST")(graph, "4:rel:1", 1, {"order": 1})
        r1._start_node = n1
        r1._end_node = n2
        r2 = graph.relationship_type("SECOND")(graph, "4:rel:2", 2, {"order": 2})
        r2._start_node = n2
        r2._end_node = n3

        from neo4j.graph import Path

        path = Path(n1, r1, r2)
        store = _make_store([{"p": path}])

        result = store.execute_query("MATCH p = (a)-[*2]->(c) RETURN p")

        path_value = result["records"][0]["p"]
        self.assertIsInstance(path_value, list)
        self.assertEqual(len(path_value), 2)
        self.assertEqual(path_value[0]["_type"], "FIRST")
        self.assertEqual(path_value[0]["order"], 1)
        self.assertEqual(path_value[1]["_type"], "SECOND")
        self.assertEqual(path_value[1]["order"], 2)
        json.dumps(result["records"])

    def test_string_and_primitive_values_pass_through(self):
        row = {"name": "Alice", "age": 30, "score": 1.5, "flag": True, "meta": None}
        store = _make_store([row])

        result = store.execute_query("RETURN name, age, score, flag, meta")

        self.assertEqual(result["records"], [dict(row)])


class TestConnectedComponentsEnvelope(unittest.TestCase):
    def test_reads_records_from_execute_query_envelope(self):
        envelope = {
            "success": True,
            "records": [
                {"componentId": 0, "nodes": [1, 2, 3]},
                {"componentId": 1, "nodes": [4]},
            ],
            "keys": ["componentId", "nodes"],
            "metadata": {"query": "CALL gds.wcc.stream(...)"},
        }

        components = GraphAnalytics(_FakeNeo4jBackend(envelope)).connected_components()

        self.assertEqual(
            components,
            [
                {"component": 0, "nodes": [1, 2, 3]},
                {"component": 1, "nodes": [4]},
            ],
        )


if __name__ == "__main__":
    unittest.main()

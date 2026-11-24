"""Regression tests for the ignored ``config`` in ``execute_query`` (#2271).

The CLI passes ``config=config.to_dict()`` into ``execute_query`` with every
``kg query`` call, but the methods layer dropped it and answered from the
module-level ``graph_store_config`` singleton, which only reads environment
variables. A ``--config`` file with a ``graph_db`` section (uri/user/password)
was therefore silently ignored and the query authenticated with default
credentials.

The fix routes a caller-supplied ``config`` through a store built from its
``graph_db`` section — the same keys ``cli._get_graph_store`` passes to
``GraphStore``. Calls without ``config`` keep using the env-configured
singleton, unchanged.
"""

import unittest
from unittest import mock

from semantica.graph_store import methods
from semantica.graph_store.methods import execute_query


class FakeStore:
    """Records how it was built and which queries it received."""

    instances = []

    def __init__(self, backend=None, **config):
        self.backend = backend
        self.config = config
        self.queries = []
        FakeStore.instances.append(self)

    def execute_query(self, query, parameters=None, **options):
        self.queries.append((query, parameters, options))
        return {"success": True, "records": [], "keys": []}


class ExecuteQueryConfigTests(unittest.TestCase):
    def setUp(self):
        FakeStore.instances = []
        methods._config_stores.clear()
        methods._global_store = None
        self.patches = [
            mock.patch("semantica.graph_store.methods.GraphStore", FakeStore),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        methods._config_stores.clear()
        methods._global_store = None

    def test_config_graph_db_section_builds_the_store(self):
        config = {
            "graph_db": {
                "backend": "neo4j",
                "uri": "bolt://configured:7687",
                "user": "configured-user",
                "password": "configured-password",
            },
            "unrelated_section": {"ignored": True},
        }
        result = execute_query("MATCH (n) RETURN n", config=config)

        self.assertEqual(len(FakeStore.instances), 1)
        store = FakeStore.instances[0]
        self.assertEqual(store.backend, "neo4j")
        self.assertEqual(
            store.config,
            {
                "uri": "bolt://configured:7687",
                "user": "configured-user",
                "password": "configured-password",
            },
        )
        self.assertEqual(result, {"success": True, "records": [], "keys": []})
        self.assertEqual(store.queries[0][0], "MATCH (n) RETURN n")

    def test_config_drops_memory_path_key(self):
        # `graph_db.path` selects the ContextGraph persistence file; GraphStore
        # has no memory backend, so the key must not reach the constructor.
        execute_query(
            "RETURN 1",
            config={"graph_db": {"backend": "neo4j", "path": "/tmp/graph.json"}},
        )
        self.assertNotIn("path", FakeStore.instances[0].config)

    def test_same_config_reuses_one_store(self):
        config = {"graph_db": {"backend": "neo4j", "uri": "bolt://x:7687"}}
        execute_query("RETURN 1", config=config)
        execute_query("RETURN 2", config=dict(config))
        self.assertEqual(len(FakeStore.instances), 1)
        self.assertEqual(len(FakeStore.instances[0].queries), 2)

    def test_different_config_builds_a_second_store(self):
        execute_query(
            "RETURN 1",
            config={"graph_db": {"backend": "neo4j", "uri": "bolt://a:7687"}},
        )
        execute_query(
            "RETURN 2",
            config={"graph_db": {"backend": "neo4j", "uri": "bolt://b:7687"}},
        )
        self.assertEqual(len(FakeStore.instances), 2)

    def test_config_without_graph_db_section_keeps_env_singleton(self):
        # No `graph_db` section: the store is built from the env-configured
        # singleton defaults, exactly as when no config was passed.
        with mock.patch.object(
            methods.graph_store_config, "get_all", return_value={"default_backend": "neo4j"}
        ):
            execute_query("RETURN 1", config={"vector_store": {"backend": "faiss"}})
            execute_query("RETURN 2")

        self.assertEqual(len(FakeStore.instances), 1)
        self.assertIs(FakeStore.instances[0], methods._global_store)
        self.assertEqual(FakeStore.instances[0].backend, "neo4j")

    def test_no_config_unchanged_singleton_path(self):
        with mock.patch.object(
            methods.graph_store_config, "get_all", return_value={"default_backend": "neo4j"}
        ):
            execute_query("RETURN 1")
            execute_query("RETURN 2")

        self.assertEqual(len(FakeStore.instances), 1)
        self.assertIs(FakeStore.instances[0], methods._global_store)
        self.assertEqual(FakeStore.instances[0].config, {"default_backend": "neo4j"})

    def test_config_never_reaches_the_backend_call(self):
        # The backend's execute_query must not receive a stray `config` kwarg.
        execute_query(
            "RETURN 1",
            config={"graph_db": {"backend": "neo4j"}},
        )
        query, parameters, options = FakeStore.instances[0].queries[0]
        self.assertNotIn("config", options)


class CustomMethodConfigTests(unittest.TestCase):
    def tearDown(self):
        methods.method_registry.unregister("query", "fake_custom")

    def test_custom_method_still_receives_config_in_options(self):
        seen = {}

        def fake_custom(query, parameters=None, **options):
            seen.update(options)
            return "custom"

        methods.method_registry.register("query", "fake_custom", fake_custom)
        result = execute_query(
            "RETURN 1",
            method="fake_custom",
            config={"graph_db": {"backend": "neo4j"}},
        )
        self.assertEqual(result, "custom")
        self.assertIn("config", seen)


if __name__ == "__main__":
    unittest.main()

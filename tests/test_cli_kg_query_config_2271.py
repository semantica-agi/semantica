"""Regression tests for ``kg query`` ignoring ``--config`` (#2271).

``kg query`` used to call ``graph_store.execute_query``, which answers from the
module-level ``graph_store_config`` singleton that only reads environment
variables. A ``--config`` file whose ``graph_db`` section set uri/user/password
was silently ignored, so ``doctor`` reported the store as OK while ``kg query``
authenticated with default credentials. The global ``--store`` flag was ignored
too.

``kg query`` now builds its store with ``_get_graph_store`` like every other
graph command. The memory backend (the CLI default) has no query engine, so it
keeps the env-configured path it always used.
"""

import pytest
from click.testing import CliRunner

import semantica.cli as cli_module
import semantica.graph_store as graph_store_module

QUERY = "MATCH (n) RETURN n LIMIT 1"


class FakeStore:
    """Records how it was built, which queries it ran, and whether it closed."""

    instances = []
    fail_with = None

    def __init__(self, backend=None, **config):
        self.backend = backend
        self.config = config
        self.queries = []
        self.closed = False
        FakeStore.instances.append(self)

    def execute_query(self, query, parameters=None, **options):
        self.queries.append((query, parameters, options))
        if FakeStore.fail_with is not None:
            raise FakeStore.fail_with
        return {"success": True, "records": [], "keys": []}

    def close(self):
        self.closed = True


@pytest.fixture
def env_queries(monkeypatch, tmp_path):
    """Isolate HOME, fake GraphStore, and record env-path execute_query calls."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(cli_module.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(cli_module, "setup_logging", lambda *a, **kw: None)

    FakeStore.instances = []
    FakeStore.fail_with = None
    monkeypatch.setattr(graph_store_module, "GraphStore", FakeStore)

    calls = []

    def fake_execute_query(query, **options):
        calls.append((query, options))
        return {"success": True, "records": [], "keys": []}

    monkeypatch.setattr(graph_store_module, "execute_query", fake_execute_query)
    return calls


def _write_config(tmp_path, body):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(body)
    return str(cfg)


def _invoke(*args):
    return CliRunner().invoke(cli_module.main, list(args))


NEO4J_CONFIG = (
    "graph_db:\n"
    "  backend: neo4j\n"
    "  uri: bolt://configured:7687\n"
    "  user: configured-user\n"
    "  password: configured-password\n"
    "  path: /tmp/ignored-graph.json\n"
)


def test_config_graph_db_section_reaches_the_store(env_queries, tmp_path):
    cfg = _write_config(tmp_path, NEO4J_CONFIG)

    result = _invoke("--config", cfg, "kg", "query", QUERY, "--json")

    assert result.exit_code == 0, result.output
    assert len(FakeStore.instances) == 1
    store = FakeStore.instances[0]
    assert store.backend == "neo4j"
    # `path` belongs to the memory backend and never reaches GraphStore.
    assert store.config == {
        "uri": "bolt://configured:7687",
        "user": "configured-user",
        "password": "configured-password",
    }
    assert store.queries == [(QUERY, None, {"lang": "cypher", "limit": 100})]
    assert store.closed
    assert env_queries == []


def test_store_flag_overrides_the_configured_backend(env_queries, tmp_path):
    cfg = _write_config(tmp_path, NEO4J_CONFIG)

    result = _invoke("--config", cfg, "--store", "falkordb", "kg", "query", QUERY)

    assert result.exit_code == 0, result.output
    assert [s.backend for s in FakeStore.instances] == ["falkordb"]
    assert env_queries == []


def test_lang_and_limit_reach_the_store(env_queries, tmp_path):
    cfg = _write_config(tmp_path, NEO4J_CONFIG)

    result = _invoke(
        "--config", cfg, "kg", "query", "SELECT * WHERE {?s ?p ?o}",
        "--lang", "sparql", "--limit", "5",
    )

    assert result.exit_code == 0, result.output
    _, _, options = FakeStore.instances[0].queries[0]
    assert options == {"lang": "sparql", "limit": 5}


def test_store_is_closed_when_the_query_fails(env_queries, tmp_path):
    cfg = _write_config(tmp_path, NEO4J_CONFIG)
    FakeStore.fail_with = RuntimeError("Neo.ClientError.Security.Unauthorized")

    result = _invoke("--config", cfg, "kg", "query", QUERY)

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert FakeStore.instances[0].closed


@pytest.mark.parametrize(
    "config_body",
    [
        "graph_db:\n  backend: memory\n",
        "vector_store:\n  backend: faiss\n",  # no graph_db: CLI default is memory
    ],
    ids=["memory-backend", "no-graph-db-section"],
)
def test_memory_backend_keeps_the_env_configured_store(env_queries, tmp_path, config_body):
    cfg = _write_config(tmp_path, config_body)

    result = _invoke("--config", cfg, "kg", "query", QUERY)

    assert result.exit_code == 0, result.output
    assert FakeStore.instances == []
    assert env_queries == [(QUERY, {"lang": "cypher", "limit": 100})]


def test_no_config_file_keeps_the_env_configured_store(env_queries):
    result = _invoke("kg", "query", QUERY)

    assert result.exit_code == 0, result.output
    assert FakeStore.instances == []
    assert env_queries == [(QUERY, {"lang": "cypher", "limit": 100})]

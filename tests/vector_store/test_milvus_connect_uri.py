"""Tests for MilvusStore's uri/token connection passthrough.

Covers connecting to Milvus Lite / a remote server / Zilliz Cloud via a
single `uri` (+ optional `token`), added alongside the existing host/port
server-connection path. pymilvus is not installed in this environment, so
these patch `connections` directly, following the pattern already used in
test_milvus_store.py.
"""

from unittest.mock import patch

from semantica.vector_store.milvus_store import MilvusStore, _redact_uri


def test_redact_uri_strips_userinfo_credentials():
    assert _redact_uri("https://user:pass@myhost:19530/db") == "https://myhost:19530/db"


def test_redact_uri_strips_query_string_secrets():
    assert _redact_uri("https://myhost:19530?token=secret") == "https://myhost:19530"


def test_redact_uri_leaves_local_lite_path_unchanged():
    # No scheme/netloc to redact -- a Milvus Lite file path carries no secrets.
    assert _redact_uri("./milvus_demo.db") == "./milvus_demo.db"


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_connect_logs_redacted_uri_not_raw_credentials(mock_connections):
    store = MilvusStore(uri="https://user:s3cr3t@myhost:19530", token="tok")
    with patch.object(store.logger, "info") as mock_info:
        store.connect()

    logged = " ".join(str(call) for call in mock_info.call_args_list)
    assert "s3cr3t" not in logged
    assert "myhost:19530" in logged


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_connect_uses_uri_and_token_when_uri_given(mock_connections):
    store = MilvusStore(uri="./milvus_demo.db", token="secret")
    store.connect()

    mock_connections.connect.assert_called_once()
    _, kwargs = mock_connections.connect.call_args
    assert kwargs["uri"] == "./milvus_demo.db"
    assert kwargs["token"] == "secret"
    assert "host" not in kwargs
    assert "port" not in kwargs


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_uri_wins_over_an_explicitly_set_host(mock_connections):
    # uri must take precedence even when host/port are *explicitly* passed,
    # not just when they're left at their defaults.
    store = MilvusStore(host="explicit-host", port=9999, uri="./milvus_demo.db")
    store.connect()

    _, kwargs = mock_connections.connect.call_args
    assert kwargs["uri"] == "./milvus_demo.db"
    assert "host" not in kwargs
    assert "port" not in kwargs


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_uri_still_forwards_user_password_for_rbac(mock_connections):
    # A self-hosted Milvus reached via uri (e.g. "http://host:19530") may use
    # RBAC user/password rather than a token — those must not be dropped.
    store = MilvusStore(uri="http://myserver:19530", user="alice", password="pw")
    store.connect()

    _, kwargs = mock_connections.connect.call_args
    assert kwargs["uri"] == "http://myserver:19530"
    assert kwargs["user"] == "alice"
    assert kwargs["password"] == "pw"


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_connect_falls_back_to_host_port_without_uri(mock_connections):
    store = MilvusStore(host="localhost", port=19530)
    store.connect()

    mock_connections.connect.assert_called_once()
    _, kwargs = mock_connections.connect.call_args
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 19530
    assert "uri" not in kwargs
    assert "token" not in kwargs


@patch("semantica.vector_store.milvus_store.connections")
@patch("semantica.vector_store.milvus_store.MILVUS_AVAILABLE", True)
def test_uri_and_token_flow_through_config_kwargs(mock_connections):
    # Mirrors VectorStore(backend="milvus", config={...}) -> MilvusStore(**config)
    store = MilvusStore(
        **{"uri": "https://cluster.zillizcloud.com", "token": "tok", "dimension": 8}
    )
    store.connect()

    _, kwargs = mock_connections.connect.call_args
    assert kwargs["uri"] == "https://cluster.zillizcloud.com"
    assert kwargs["token"] == "tok"

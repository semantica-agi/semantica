"""
Unit tests for Databricks Ingestor

This test module uses mocks to test Databricks ingestion functionality
without requiring a live Databricks workspace.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# Test if databricks-sdk / databricks-sql-connector are available
try:
    import databricks.sdk  # noqa: F401
    from databricks import sql  # noqa: F401

    DATABRICKS_LIBS_AVAILABLE = True
except ImportError:
    DATABRICKS_LIBS_AVAILABLE = False


@pytest.fixture(autouse=True)
def mock_databricks_if_needed():
    """Mock databricks modules if not installed."""
    if not DATABRICKS_LIBS_AVAILABLE:
        with patch.dict(
            "sys.modules",
            {
                "databricks": MagicMock(),
                "databricks.sql": MagicMock(),
                "databricks.sdk": MagicMock(),
            },
        ):
            yield
    else:
        yield


@pytest.fixture
def mock_databricks_connection():
    """Create a mock Databricks SQL connection."""
    mock_conn = Mock()
    mock_cursor = Mock()

    mock_cursor.execute = Mock()
    mock_cursor.fetchall = Mock(return_value=[])
    mock_cursor.fetchone = Mock(return_value=[1])
    mock_cursor.fetchmany = Mock(return_value=[])
    mock_cursor.description = [("id", None), ("name", None), ("value", None)]
    mock_cursor.close = Mock()

    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.close = Mock()

    return mock_conn, mock_cursor


class TestDatabricksConnector:
    """Test DatabricksConnector class."""

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_init_with_token(self, mock_sql):
        """Test connector initialization with personal access token authentication."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
        )

        assert connector.host == "https://adb-xxx.azuredatabricks.net"
        assert connector.token == "test_token"
        assert connector.http_path == "/sql/1.0/warehouses/xxxx"
        assert connector.catalog == "TEST_CATALOG"
        assert connector.schema == "default"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_init_from_env(self, mock_sql):
        """Test connector initialization from environment variables."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        with patch.dict(
            os.environ,
            {
                "DATABRICKS_HOST": "https://env-host.azuredatabricks.net",
                "DATABRICKS_TOKEN": "env_token",
                "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/env",
            },
        ):
            connector = DatabricksConnector()

            assert connector.host == "https://env-host.azuredatabricks.net"
            assert connector.token == "env_token"
            assert connector.http_path == "/sql/1.0/warehouses/env"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_init_missing_host(self, mock_sql):
        """Test connector initialization fails without host."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Databricks host is required"):
            DatabricksConnector(token="test_token")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_init_missing_auth(self, mock_sql):
        """Test connector initialization fails without any authentication method."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Databricks authentication is required"):
            DatabricksConnector(host="https://adb-xxx.azuredatabricks.net")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_connect_token_auth(self, mock_sql, mock_databricks_connection):
        """Test connection with personal access token authentication."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        conn = connector.connect()

        assert conn == mock_conn
        mock_sql.connect.assert_called_once()

        call_kwargs = mock_sql.connect.call_args[1]
        assert call_kwargs["server_hostname"] == "adb-xxx.azuredatabricks.net"
        assert call_kwargs["http_path"] == "/sql/1.0/warehouses/xxxx"
        assert call_kwargs["access_token"] == "test_token"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.oauth_service_principal")
    @patch("semantica.ingest.databricks_ingestor.Config")
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_connect_oauth_m2m(
        self, mock_sql, mock_config, mock_oauth_sp, mock_databricks_connection
    ):
        """Test connection with OAuth M2M authentication uses credentials_provider.

        databricks-sql-connector does NOT accept client_id/client_secret as
        direct kwargs to sql.connect(); the correct mechanism is a
        credentials_provider callable wrapping oauth_service_principal().
        """
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)
        mock_oauth_sp.return_value = {"Authorization": "Bearer fake-token"}

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            http_path="/sql/1.0/warehouses/xxxx",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )

        connector.connect()

        call_kwargs = mock_sql.connect.call_args[1]

        # Must use credentials_provider, not bare client_id/client_secret
        assert "credentials_provider" in call_kwargs
        assert callable(call_kwargs["credentials_provider"])
        assert "client_id" not in call_kwargs
        assert "client_secret" not in call_kwargs
        assert "access_token" not in call_kwargs

        # Invoke the provider to verify it wires Config + oauth_service_principal
        call_kwargs["credentials_provider"]()
        mock_config.assert_called_once_with(
            host="https://adb-xxx.azuredatabricks.net",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        mock_oauth_sp.assert_called_once_with(mock_config.return_value)

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_connect_missing_http_path(self, mock_sql):
        """Test connection fails without http_path."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector
        from semantica.utils.exceptions import ValidationError

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
        )

        with pytest.raises(ValidationError, match="http_path"):
            connector.connect()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_disconnect(self, mock_sql, mock_databricks_connection):
        """Test connection disconnect."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        connector.connect()
        connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector.connection is None

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_test_connection_success(self, mock_sql, mock_databricks_connection):
        """Test successful connection test."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        result = connector.test_connection()

        assert result is True
        mock_cursor.execute.assert_called_with("SELECT 1")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_connector_test_connection_failure(self, mock_sql):
        """Test connection test failure."""
        from semantica.ingest.databricks_ingestor import DatabricksConnector

        mock_sql.connect = Mock(side_effect=Exception("Connection failed"))

        connector = DatabricksConnector(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        result = connector.test_connection()

        assert result is False


class TestDatabricksIngestor:
    """Test DatabricksIngestor class."""

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingestor_init(self, mock_sql):
        """Test ingestor initialization."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        assert ingestor.connector is not None
        assert ingestor.connector.host == "https://adb-xxx.azuredatabricks.net"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_basic(self, mock_sql, mock_databricks_connection):
        """Test basic table ingestion."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        mock_cursor.fetchall = Mock(
            return_value=[
                (1, "Alice", 100),
                (2, "Bob", 200),
            ]
        )
        mock_cursor.description = [("id", None), ("name", None), ("value", None)]

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
            schema="TEST_SCHEMA",
        )

        data = ingestor.ingest_table("customers")

        assert data.row_count == 2
        assert data.table_name == "customers"
        assert data.catalog == "TEST_CATALOG"
        assert data.schema == "TEST_SCHEMA"
        assert len(data.columns) == 3
        assert "id" in data.columns
        assert data.data[0]["name"] == "Alice"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_closes_connection(self, mock_sql, mock_databricks_connection):
        """Test that ingest_table() closes the SQL connection after use instead of leaking it."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        ingestor.ingest_table("customers")

        mock_conn.close.assert_called_once()
        assert ingestor.connector.connection is None

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_catalog_only(self, mock_sql, mock_databricks_connection):
        """Test table ingestion still qualifies the reference when only catalog is provided."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        # Force a missing schema past the connector's "default" fallback.
        ingestor.connector.schema = None

        ingestor.ingest_table("customers", catalog="main")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "`main`.`customers`" in executed_query
        assert "None" not in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_with_limit(self, mock_sql, mock_databricks_connection):
        """Test table ingestion with limit."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        ingestor.ingest_table("customers", limit=100)

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 100" in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_with_where(self, mock_sql, mock_databricks_connection):
        """Test table ingestion with WHERE clause."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        ingestor.ingest_table("customers", where="value > 100")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE value > 100" in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_rejects_unsafe_order_by(self, mock_sql, mock_databricks_connection):
        """Test table ingestion rejects unsafe ORDER BY clauses."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        from semantica.utils.exceptions import ProcessingError

        with pytest.raises(ProcessingError):
            ingestor.ingest_table("customers", order_by="value; DROP TABLE customers")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_query_basic(self, mock_sql, mock_databricks_connection):
        """Test basic query execution."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        mock_cursor.fetchall = Mock(return_value=[(1000,)])
        mock_cursor.description = [("total", None)]

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        query = "SELECT SUM(value) AS total FROM sales"
        data = ingestor.ingest_query(query)

        assert data.row_count == 1
        assert data.query == query
        assert data.data[0]["total"] == 1000

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_query_closes_connection(self, mock_sql, mock_databricks_connection):
        """Test that ingest_query() closes the SQL connection after use instead of leaking it."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        ingestor.ingest_query("SELECT * FROM sales")

        mock_conn.close.assert_called_once()
        assert ingestor.connector.connection is None

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_query_with_batching(self, mock_sql, mock_databricks_connection):
        """Test query execution with batch fetching."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        batch1 = [(1,), (2,)]
        batch2 = [(3,)]
        mock_cursor.fetchmany = Mock(side_effect=[batch1, batch2, []])
        mock_cursor.description = [("id", None)]

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        data = ingestor.ingest_query("SELECT * FROM customers", batch_size=2)

        assert data.row_count == 3
        assert len(data.data) == 3

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_get_table_schema(self, mock_ws_client_cls, mock_sql):
        """Test getting table schema information."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_column_1 = Mock(name="id")
        mock_column_1.name = "id"
        mock_column_1.type_text = "BIGINT"
        mock_column_1.nullable = False
        mock_column_1.comment = None

        mock_column_2 = Mock(name="name")
        mock_column_2.name = "name"
        mock_column_2.type_text = "STRING"
        mock_column_2.nullable = True
        mock_column_2.comment = None

        mock_table_info = Mock()
        mock_table_info.columns = [mock_column_1, mock_column_2]

        mock_ws_client = Mock()
        mock_ws_client.tables.get = Mock(return_value=mock_table_info)
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
            schema="TEST_SCHEMA",
        )

        schema = ingestor.get_table_schema("customers")

        assert len(schema["columns"]) == 2
        assert schema["columns"][0]["name"] == "id"
        assert schema["columns"][0]["type"] == "BIGINT"
        assert schema["columns"][0]["nullable"] is False
        mock_ws_client.tables.get.assert_called_once_with(
            full_name="TEST_CATALOG.TEST_SCHEMA.customers"
        )

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_get_table_schema_requires_schema(self, mock_ws_client_cls, mock_sql):
        """Test that get_table_schema() raises instead of calling the SDK with a missing schema."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_ws_client = Mock()
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
        )
        ingestor.connector.schema = None

        with pytest.raises(ProcessingError, match="Schema name is required"):
            ingestor.get_table_schema("customers")

        mock_ws_client.tables.get.assert_not_called()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_list_catalogs(self, mock_ws_client_cls, mock_sql):
        """Test listing catalogs."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_catalog_1 = Mock()
        mock_catalog_1.name = "main"
        mock_catalog_2 = Mock()
        mock_catalog_2.name = "samples"

        mock_ws_client = Mock()
        mock_ws_client.catalogs.list = Mock(return_value=[mock_catalog_1, mock_catalog_2])
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        catalogs = ingestor.list_catalogs()

        assert len(catalogs) == 2
        assert "main" in catalogs

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_list_tables(self, mock_ws_client_cls, mock_sql):
        """Test listing tables in a catalog/schema."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_table_1 = Mock()
        mock_table_1.name = "customers"
        mock_table_2 = Mock()
        mock_table_2.name = "orders"

        mock_ws_client = Mock()
        mock_ws_client.tables.list = Mock(return_value=[mock_table_1, mock_table_2])
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
            schema="TEST_SCHEMA",
        )

        tables = ingestor.list_tables()

        assert len(tables) == 2
        assert "customers" in tables
        mock_ws_client.tables.list.assert_called_once_with(
            catalog_name="TEST_CATALOG", schema_name="TEST_SCHEMA"
        )

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_list_tables_requires_schema(self, mock_ws_client_cls, mock_sql):
        """Test that list_tables() raises instead of calling the SDK with schema_name=None."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_ws_client = Mock()
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="TEST_CATALOG",
        )
        # Force a missing schema past the connector's "default" fallback.
        ingestor.connector.schema = None

        with pytest.raises(ProcessingError, match="Schema name is required"):
            ingestor.list_tables()

        mock_ws_client.tables.list.assert_not_called()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_get_table_lineage(self, mock_ws_client_cls, mock_sql):
        """Test getting table lineage."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_ws_client = Mock()
        mock_ws_client.api_client.do = Mock(
            return_value={
                "upstreams": [{"tableInfo": {"name": "main.default.raw_customers"}}],
                "downstreams": [{"tableInfo": {"name": "main.default.customer_summary"}}],
            }
        )
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="main",
            schema="default",
        )

        lineage = ingestor.get_table_lineage("customers")

        assert lineage["upstream"] == ["main.default.raw_customers"]
        assert lineage["downstream"] == ["main.default.customer_summary"]
        assert "columns" not in lineage

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_get_table_lineage_with_column_lineage(self, mock_ws_client_cls, mock_sql):
        """Test that include_column_lineage=True fetches per-column lineage."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_column_1 = Mock()
        mock_column_1.name = "id"
        mock_column_1.type_text = "BIGINT"
        mock_column_1.nullable = False
        mock_column_1.comment = None

        mock_column_2 = Mock()
        mock_column_2.name = "name"
        mock_column_2.type_text = "STRING"
        mock_column_2.nullable = True
        mock_column_2.comment = None

        mock_table_info = Mock()
        mock_table_info.columns = [mock_column_1, mock_column_2]

        def do_side_effect(method, path, query=None):
            if path.endswith("table-lineage"):
                return {
                    "upstreams": [{"tableInfo": {"name": "main.default.raw_customers"}}],
                    "downstreams": [],
                }
            if path.endswith("column-lineage"):
                if query["column_name"] == "id":
                    return {
                        "upstream_cols": [
                            {
                                "catalog_name": "main",
                                "schema_name": "default",
                                "table_name": "raw_customers",
                                "name": "customer_id",
                            }
                        ],
                        "downstream_cols": [],
                    }
                return {"upstream_cols": [], "downstream_cols": []}
            raise AssertionError(f"unexpected path: {path}")

        mock_ws_client = Mock()
        mock_ws_client.tables.get = Mock(return_value=mock_table_info)
        mock_ws_client.api_client.do = Mock(side_effect=do_side_effect)
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="main",
            schema="default",
        )

        lineage = ingestor.get_table_lineage("customers", include_column_lineage=True)

        assert lineage["upstream"] == ["main.default.raw_customers"]
        assert lineage["columns"]["id"]["upstream"] == ["main.default.raw_customers.customer_id"]
        assert lineage["columns"]["id"]["downstream"] == []
        assert lineage["columns"]["name"]["upstream"] == []

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    @patch("semantica.ingest.databricks_ingestor.WorkspaceClient")
    def test_get_table_lineage_requires_schema(self, mock_ws_client_cls, mock_sql):
        """Test that get_table_lineage() validates schema before calling the REST API."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_ws_client = Mock()
        mock_ws_client_cls.return_value = mock_ws_client

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
            catalog="main",
        )
        ingestor.connector.schema = None

        with pytest.raises(ProcessingError, match="Schema name is required"):
            ingestor.get_table_lineage("customers")

        mock_ws_client.api_client.do.assert_not_called()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_export_as_documents(self, mock_sql):
        """Test exporting data as documents."""
        from semantica.ingest.databricks_ingestor import DatabricksData, DatabricksIngestor

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        data = DatabricksData(
            data=[
                {"id": 1, "name": "Alice", "description": "Engineer"},
                {"id": 2, "name": "Bob", "description": "Designer"},
            ],
            row_count=2,
            columns=["id", "name", "description"],
            table_name="employees",
            catalog="main",
            schema="default",
        )

        documents = ingestor.export_as_documents(
            data, id_field="id", text_fields=["name", "description"]
        )

        assert len(documents) == 2
        assert documents[0]["id"] == "1"
        assert documents[0]["text"] == "Alice Engineer"
        assert documents[0]["metadata"]["source"] == "databricks"
        assert documents[0]["metadata"]["table"] == "employees"

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_context_manager(self, mock_sql, mock_databricks_connection):
        """Test using ingestor as context manager."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        with DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        ) as ingestor:
            assert ingestor.connector.connection == mock_conn

        mock_conn.close.assert_called()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_context_manager_reuses_connection_across_calls(
        self, mock_sql, mock_databricks_connection
    ):
        """Test that ingest_table()/ingest_query() reuse (not leak) the connection
        opened by __enter__, and only close it once on __exit__."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        with DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        ) as ingestor:
            ingestor.ingest_table("customers")
            # The connection opened by __enter__ must still be the live one:
            # ingest_table() should not have closed it out from under the
            # context manager.
            assert ingestor.connector.connection == mock_conn
            mock_conn.close.assert_not_called()

            ingestor.ingest_query("SELECT * FROM sales")
            assert ingestor.connector.connection == mock_conn
            mock_conn.close.assert_not_called()

        # databricks_sql.connect() should only have been called once (by
        # __enter__): both ingestion calls reused that same connection.
        mock_sql.connect.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_convert_datetime(self, mock_sql):
        """Test datetime conversion in _convert_rows."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )

        test_dt = datetime(2024, 1, 15, 10, 30, 0)
        rows = [{"timestamp": test_dt, "value": 100}]

        converted = ingestor._convert_rows(rows)

        assert converted[0]["timestamp"] == "2024-01-15T10:30:00"
        assert converted[0]["value"] == 100

    def test_import_error_without_databricks(self):
        """Test that proper error is raised when databricks libraries are not installed."""
        with patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", False):
            from semantica.ingest.databricks_ingestor import DatabricksConnector

            with pytest.raises(ImportError, match="databricks-sdk"):
                DatabricksConnector(
                    host="https://adb-xxx.azuredatabricks.net",
                    token="test_token",
                )

    # ------------------------------------------------------------------
    # WHERE-clause validation regression tests
    # ------------------------------------------------------------------

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_union_in_where_raises_validation_error(self, mock_sql):
        """UNION in WHERE must raise ValidationError, not just block semicolons."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ValidationError

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        with pytest.raises(ValidationError):
            ingestor.ingest_table("customers", where="1=1 UNION SELECT * FROM secrets")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_comment_in_where_raises_validation_error(self, mock_sql):
        """SQL comment sequences in WHERE must raise ValidationError."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ValidationError

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        with pytest.raises(ValidationError):
            ingestor.ingest_table("customers", where="1=1 -- bypass")

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_ingest_table_quoted_literal_union_passes(
        self, mock_sql, mock_databricks_connection
    ):
        """'union' inside a quoted string literal must NOT be rejected."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        # 'Credit Union' is a data value, not SQL syntax — must pass
        ingestor.ingest_table("customers", where="name = 'Credit Union'")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE name = 'Credit Union'" in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_invalid_where_rejected_before_connect(
        self, mock_sql, mock_databricks_connection
    ):
        """ValidationError must be raised before any connection is attempted."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ValidationError

        mock_conn, _ = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        with pytest.raises(ValidationError):
            ingestor.ingest_table("customers", where="1=1 UNION SELECT * FROM secrets")

        mock_sql.connect.assert_not_called()

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_backtick_quoted_identifier_with_blocked_word_passes(
        self, mock_sql, mock_databricks_connection
    ):
        """Backtick-quoted identifiers containing blocked words must not be rejected.

        Databricks SQL uses backtick quoting for column names that collide
        with reserved words or contain special characters, e.g.:
            WHERE `union` = 1
            WHERE `my--column` > 0
        These are valid column references, not injection syntax.
        """
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        # backtick-quoted column name that happens to spell a blocked word
        ingestor.ingest_table("events", where="`union` = 1")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE `union` = 1" in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_backtick_quoted_identifier_with_comment_chars_passes(
        self, mock_sql, mock_databricks_connection
    ):
        """Backtick-quoted identifier containing -- must not be rejected."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor

        mock_conn, mock_cursor = mock_databricks_connection
        mock_sql.connect = Mock(return_value=mock_conn)

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        ingestor.ingest_table("events", where="`my--column` > 0")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE `my--column` > 0" in executed_query

    @patch("semantica.ingest.databricks_ingestor.DATABRICKS_AVAILABLE", True)
    @patch("semantica.ingest.databricks_ingestor.databricks_sql")
    def test_bare_union_outside_backticks_still_rejected(
        self, mock_sql, mock_databricks_connection
    ):
        """UNION outside any quoting must still raise ValidationError."""
        from semantica.ingest.databricks_ingestor import DatabricksIngestor
        from semantica.utils.exceptions import ValidationError

        ingestor = DatabricksIngestor(
            host="https://adb-xxx.azuredatabricks.net",
            token="test_token",
            http_path="/sql/1.0/warehouses/xxxx",
        )
        with pytest.raises(ValidationError):
            ingestor.ingest_table("events", where="1=1 UNION SELECT * FROM secrets")


class TestDatabricksData:
    """Test DatabricksData dataclass."""

    def test_databricks_data_creation(self):
        """Test DatabricksData creation."""
        from semantica.ingest.databricks_ingestor import DatabricksData

        data = DatabricksData(
            data=[{"col1": "val1"}],
            row_count=1,
            columns=["col1"],
            table_name="test_table",
        )

        assert data.row_count == 1
        assert data.table_name == "test_table"
        assert len(data.data) == 1
        assert isinstance(data.ingested_at, datetime)

    def test_databricks_data_with_metadata(self):
        """Test DatabricksData with metadata."""
        from semantica.ingest.databricks_ingestor import DatabricksData

        metadata = {"custom_field": "value"}
        data = DatabricksData(
            data=[],
            row_count=0,
            columns=[],
            metadata=metadata,
        )

        assert data.metadata["custom_field"] == "value"

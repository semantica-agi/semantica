"""
Unit tests for Snowflake Ingestor

This test module uses mocks to test Snowflake ingestion functionality
without requiring a live Snowflake connection.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# Test if snowflake-connector-python is available
try:
    import snowflake.connector

    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False


# Mock snowflake module if not available
@pytest.fixture(autouse=True)
def mock_snowflake_if_needed():
    """Mock snowflake module if not installed."""
    if not SNOWFLAKE_AVAILABLE:
        with patch.dict("sys.modules", {"snowflake": MagicMock(), "snowflake.connector": MagicMock()}):
            yield
    else:
        yield


@pytest.fixture
def mock_snowflake_connection():
    """Create a mock Snowflake connection."""
    mock_conn = Mock()
    mock_cursor = Mock()

    # Mock cursor methods
    mock_cursor.execute = Mock()
    mock_cursor.fetchall = Mock(return_value=[])
    mock_cursor.fetchone = Mock(return_value=["1.0.0"])
    mock_cursor.fetchmany = Mock(return_value=[])
    mock_cursor.description = [("ID", None), ("NAME", None), ("VALUE", None)]
    mock_cursor.close = Mock()

    # Mock connection methods
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.close = Mock()

    return mock_conn, mock_cursor


class TestSnowflakeConnector:
    """Test SnowflakeConnector class."""

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_init_with_password(self, mock_snowflake):
        """Test connector initialization with password authentication."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            password="test_password",
            warehouse="TEST_WH",
            database="TEST_DB",
        )

        assert connector.account == "test_account"
        assert connector.user == "test_user"
        assert connector.password == "test_password"
        assert connector.warehouse == "TEST_WH"
        assert connector.database == "TEST_DB"
        assert connector.schema == "PUBLIC"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_init_from_env(self, mock_snowflake):
        """Test connector initialization from environment variables."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        with patch.dict(
            os.environ,
            {
                "SNOWFLAKE_ACCOUNT": "env_account",
                "SNOWFLAKE_USER": "env_user",
                "SNOWFLAKE_PASSWORD": "env_password",
            },
        ):
            connector = SnowflakeConnector()

            assert connector.account == "env_account"
            assert connector.user == "env_user"
            assert connector.password == "env_password"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_init_missing_account(self, mock_snowflake):
        """Test connector initialization fails without account."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Snowflake account is required"):
            SnowflakeConnector(user="test_user", password="test_password")

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_connect_password_auth(self, mock_snowflake, mock_snowflake_connection):
        """Test connection with password authentication."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        conn = connector.connect()

        assert conn == mock_conn
        mock_snowflake.connector.connect.assert_called_once()

        # Verify password authentication params
        call_kwargs = mock_snowflake.connector.connect.call_args[1]
        assert call_kwargs["account"] == "test_account"
        assert call_kwargs["user"] == "test_user"
        assert call_kwargs["password"] == "test_password"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_connect_oauth(self, mock_snowflake, mock_snowflake_connection):
        """Test connection with OAuth authentication."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            authenticator="oauth",
            token="test_token",
        )

        conn = connector.connect()

        call_kwargs = mock_snowflake.connector.connect.call_args[1]
        assert call_kwargs["authenticator"] == "oauth"
        assert call_kwargs["token"] == "test_token"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_connect_sso(self, mock_snowflake, mock_snowflake_connection):
        """Test connection with SSO authentication."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            authenticator="externalbrowser",
        )

        conn = connector.connect()

        call_kwargs = mock_snowflake.connector.connect.call_args[1]
        assert call_kwargs["authenticator"] == "externalbrowser"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_disconnect(self, mock_snowflake, mock_snowflake_connection):
        """Test connection disconnect."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_conn, _ = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        connector.connect()
        connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector.connection is None

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_test_connection_success(self, mock_snowflake, mock_snowflake_connection):
        """Test successful connection test."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        result = connector.test_connection()

        assert result is True
        mock_cursor.execute.assert_called_with("SELECT 1")

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_connector_test_connection_failure(self, mock_snowflake):
        """Test connection test failure."""
        from semantica.ingest.snowflake_ingestor import SnowflakeConnector

        mock_snowflake.connector.connect = Mock(side_effect=Exception("Connection failed"))

        connector = SnowflakeConnector(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        result = connector.test_connection()

        assert result is False


class TestSnowflakeIngestor:
    """Test SnowflakeIngestor class."""

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingestor_init(self, mock_snowflake):
        """Test ingestor initialization."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        assert ingestor.connector is not None
        assert ingestor.connector.account == "test_account"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_table_basic(self, mock_snowflake, mock_snowflake_connection):
        """Test basic table ingestion."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        # Mock table data
        mock_cursor.fetchall = Mock(
            return_value=[
                {"ID": 1, "NAME": "Alice", "VALUE": 100},
                {"ID": 2, "NAME": "Bob", "VALUE": 200},
            ]
        )
        mock_cursor.description = [("ID", None), ("NAME", None), ("VALUE", None)]

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
            database="TEST_DB",
            schema="PUBLIC",
        )

        data = ingestor.ingest_table("CUSTOMERS")

        assert data.row_count == 2
        assert data.table_name == "CUSTOMERS"
        assert data.database == "TEST_DB"
        assert data.schema == "PUBLIC"
        assert len(data.columns) == 3
        assert "ID" in data.columns

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_table_with_limit(self, mock_snowflake, mock_snowflake_connection):
        """Test table ingestion with limit."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        ingestor.ingest_table("CUSTOMERS", limit=100)

        # Verify LIMIT clause in query — the implementation uses bind parameters
        # (%s) rather than literal interpolation, so check for the LIMIT keyword
        # and that the param value was passed separately.
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "LIMIT" in executed_query
        executed_params = mock_cursor.execute.call_args[0][1]
        assert 100 in executed_params

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_table_with_where(self, mock_snowflake, mock_snowflake_connection):
        """Test table ingestion with WHERE clause."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        ingestor.ingest_table("CUSTOMERS", where="VALUE > 100")

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE VALUE > 100" in executed_query

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_query_basic(self, mock_snowflake, mock_snowflake_connection):
        """Test basic query execution."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        mock_cursor.fetchall = Mock(
            return_value=[{"TOTAL": 1000}]
        )
        mock_cursor.description = [("TOTAL", None)]

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        query = "SELECT SUM(VALUE) AS TOTAL FROM SALES"
        data = ingestor.ingest_query(query)

        assert data.row_count == 1
        assert data.query == query
        assert len(data.data) == 1

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_query_with_params(self, mock_snowflake, mock_snowflake_connection):
        """Test query execution with parameters."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        query = "SELECT * FROM SALES WHERE date > %(date)s"
        params = {"date": "2024-01-01"}

        ingestor.ingest_query(query, params=params)

        # Verify params were passed
        assert mock_cursor.execute.call_args[0][1] == params

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_ingest_query_with_batching(self, mock_snowflake, mock_snowflake_connection):
        """Test query execution with batch fetching."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        # Mock fetchmany to return batches
        batch1 = [{"ID": 1}, {"ID": 2}]
        batch2 = [{"ID": 3}]
        mock_cursor.fetchmany = Mock(side_effect=[batch1, batch2, []])
        mock_cursor.description = [("ID", None)]

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        data = ingestor.ingest_query("SELECT * FROM CUSTOMERS", batch_size=2)

        assert data.row_count == 3
        assert len(data.data) == 3

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_get_table_schema(self, mock_snowflake, mock_snowflake_connection):
        """Test getting table schema information."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        # Mock schema query results
        mock_cursor.fetchall = Mock(
            side_effect=[
                # Column information
                [
                    {
                        "COLUMN_NAME": "ID",
                        "DATA_TYPE": "NUMBER",
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                    },
                    {
                        "COLUMN_NAME": "NAME",
                        "DATA_TYPE": "VARCHAR",
                        "IS_NULLABLE": "YES",
                        "COLUMN_DEFAULT": None,
                    },
                ],
                # Primary key information
                [{"COLUMN_NAME": "ID"}],
            ]
        )

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
            database="TEST_DB",
            schema="PUBLIC",
        )

        schema = ingestor.get_table_schema("CUSTOMERS")

        assert len(schema["columns"]) == 2
        assert schema["columns"][0]["name"] == "ID"
        assert schema["columns"][0]["type"] == "NUMBER"
        assert schema["columns"][0]["nullable"] is False
        assert schema["primary_keys"] == ["ID"]

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_list_tables(self, mock_snowflake, mock_snowflake_connection):
        """Test listing tables in a schema."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        mock_cursor.fetchall = Mock(
            return_value=[("CUSTOMERS",), ("ORDERS",), ("PRODUCTS",)]
        )

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
            database="TEST_DB",
            schema="PUBLIC",
        )

        tables = ingestor.list_tables()

        assert len(tables) == 3
        assert "CUSTOMERS" in tables
        assert "ORDERS" in tables

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_export_as_documents(self, mock_snowflake):
        """Test exporting data as documents."""
        from semantica.ingest.snowflake_ingestor import SnowflakeData, SnowflakeIngestor

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        # Create sample data
        data = SnowflakeData(
            data=[
                {"ID": 1, "NAME": "Alice", "DESCRIPTION": "Engineer"},
                {"ID": 2, "NAME": "Bob", "DESCRIPTION": "Designer"},
            ],
            row_count=2,
            columns=["ID", "NAME", "DESCRIPTION"],
            table_name="EMPLOYEES",
            database="TEST_DB",
            schema="PUBLIC",
        )

        documents = ingestor.export_as_documents(
            data, id_field="ID", text_fields=["NAME", "DESCRIPTION"]
        )

        assert len(documents) == 2
        assert documents[0]["id"] == "1"
        assert documents[0]["text"] == "Alice Engineer"
        assert documents[0]["metadata"]["source"] == "snowflake"
        assert documents[0]["metadata"]["table"] == "EMPLOYEES"

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_context_manager(self, mock_snowflake, mock_snowflake_connection):
        """Test using ingestor as context manager."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        mock_conn, mock_cursor = mock_snowflake_connection
        mock_snowflake.connector.connect = Mock(return_value=mock_conn)

        with SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        ) as ingestor:
            assert ingestor.connector.connection == mock_conn

        mock_conn.close.assert_called()

    @patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", True)
    @patch("semantica.ingest.snowflake_ingestor.snowflake")
    def test_convert_datetime(self, mock_snowflake):
        """Test datetime conversion in _convert_rows."""
        from semantica.ingest.snowflake_ingestor import SnowflakeIngestor

        ingestor = SnowflakeIngestor(
            account="test_account",
            user="test_user",
            password="test_password",
        )

        test_dt = datetime(2024, 1, 15, 10, 30, 0)
        rows = [{"timestamp": test_dt, "value": 100}]

        converted = ingestor._convert_rows(rows)

        assert converted[0]["timestamp"] == "2024-01-15T10:30:00"
        assert converted[0]["value"] == 100

    def test_import_error_without_snowflake(self):
        """Test that proper error is raised when snowflake-connector-python is not installed."""
        with patch("semantica.ingest.snowflake_ingestor.SNOWFLAKE_AVAILABLE", False):
            from semantica.ingest.snowflake_ingestor import SnowflakeConnector

            with pytest.raises(ImportError, match="snowflake-connector-python is required"):
                SnowflakeConnector(
                    account="test_account",
                    user="test_user",
                    password="test_password",
                )


class TestSnowflakeData:
    """Test SnowflakeData dataclass."""

    def test_snowflake_data_creation(self):
        """Test SnowflakeData creation."""
        from semantica.ingest.snowflake_ingestor import SnowflakeData

        data = SnowflakeData(
            data=[{"col1": "val1"}],
            row_count=1,
            columns=["col1"],
            table_name="TEST_TABLE",
        )

        assert data.row_count == 1
        assert data.table_name == "TEST_TABLE"
        assert len(data.data) == 1
        assert isinstance(data.ingested_at, datetime)

    def test_snowflake_data_with_metadata(self):
        """Test SnowflakeData with metadata."""
        from semantica.ingest.snowflake_ingestor import SnowflakeData

        metadata = {"custom_field": "value"}
        data = SnowflakeData(
            data=[],
            row_count=0,
            columns=[],
            metadata=metadata,
        )

        assert data.metadata["custom_field"] == "value"

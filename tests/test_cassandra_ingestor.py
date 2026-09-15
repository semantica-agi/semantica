"""Tests for the Cassandra ingestor."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from semantica.utils.exceptions import ValidationError
from semantica.ingest.cassandra_ingestor import (
    CassandraConnector,
    CassandraData,
    CassandraIngestor,
)


class TestCassandraData:
    """Tests for CassandraData."""

    def test_data_creation(self):
        data = CassandraData(
            data=[{"id": 1, "name": "Alice"}],
            row_count=1,
            columns=["id", "name"],
            keyspace="test",
            table_name="users",
            schema={},
        )

        assert data.row_count == 1
        assert data.columns == ["id", "name"]
        assert data.keyspace == "test"
        assert data.table_name == "users"


class TestCassandraConnector:
    """Tests for CassandraConnector."""

    @patch("semantica.ingest.cassandra_ingestor.CASSANDRA_AVAILABLE", False)
    def test_missing_dependency(self):
        with pytest.raises(
            ImportError,
            match="cassandra-driver.*semantica\\[db-cassandra\\]",
        ):
            CassandraConnector()

    @patch("semantica.ingest.cassandra_ingestor.CASSANDRA_AVAILABLE", True)
    @patch("semantica.ingest.cassandra_ingestor.PlainTextAuthProvider")
    def test_connect_without_auth(self, mock_auth):
        mock_session = MagicMock()
        mock_cluster_instance = MagicMock()
        mock_cluster_instance.connect.return_value = mock_session

        fake_cluster_module = types.ModuleType("cassandra.cluster")
        mock_cluster = MagicMock(return_value=mock_cluster_instance)
        fake_cluster_module.Cluster = mock_cluster

        with patch.dict(sys.modules, {"cassandra.cluster": fake_cluster_module}):
            connector = CassandraConnector(
                hosts=["localhost"],
                port=9042,
            )

            session = connector.connect()

        assert session == mock_session
        mock_cluster.assert_called_once_with(
            contact_points=["localhost"],
            port=9042,
            auth_provider=None,
        )
        mock_auth.assert_not_called()

    @patch("semantica.ingest.cassandra_ingestor.CASSANDRA_AVAILABLE", True)
    @patch("semantica.ingest.cassandra_ingestor.PlainTextAuthProvider")
    def test_connect_with_auth(self, mock_auth):
        mock_session = MagicMock()
        mock_cluster_instance = MagicMock()
        mock_cluster_instance.connect.return_value = mock_session

        fake_cluster_module = types.ModuleType("cassandra.cluster")
        mock_cluster = MagicMock(return_value=mock_cluster_instance)
        fake_cluster_module.Cluster = mock_cluster

        with patch.dict(sys.modules, {"cassandra.cluster": fake_cluster_module}):
            connector = CassandraConnector(
                hosts=["localhost"],
                username="user",
                password="password",
            )

            session = connector.connect()

        assert session == mock_session
        mock_auth.assert_called_once_with(
            username="user",
            password="password",
        )

    @patch("semantica.ingest.cassandra_ingestor.CASSANDRA_AVAILABLE", True)
    def test_disconnect(self):
        mock_session = MagicMock()
        mock_cluster_instance = MagicMock()
        mock_cluster_instance.connect.return_value = mock_session

        fake_cluster_module = types.ModuleType("cassandra.cluster")
        mock_cluster = MagicMock(return_value=mock_cluster_instance)
        fake_cluster_module.Cluster = mock_cluster

        with patch.dict(sys.modules, {"cassandra.cluster": fake_cluster_module}):
            connector = CassandraConnector(hosts=["localhost"])
            connector.connect()
            connector.disconnect()

        mock_session.shutdown.assert_called_once()
        mock_cluster_instance.shutdown.assert_called_once()
        assert connector.session is None
        assert connector.cluster is None


class TestCassandraIngestor:
    """Tests for CassandraIngestor."""

    def test_export_as_documents(self):
        data = CassandraData(
            data=[
                {"id": 1, "name": "Alice", "city": "Delhi"},
                {"id": 2, "name": "Bob", "city": "Mumbai"},
            ],
            row_count=2,
            columns=["id", "name", "city"],
            keyspace="test",
            table_name="users",
            schema={},
        )

        ingestor = object.__new__(CassandraIngestor)
        ingestor.logger = MagicMock()

        documents = ingestor.export_as_documents(data)

        assert len(documents) == 2
        assert documents[0]["id"] == "1"
        assert documents[0]["text"] == "Alice Delhi"
        assert documents[0]["metadata"]["source"] == "cassandra"
        assert documents[0]["metadata"]["keyspace"] == "test"
        assert documents[0]["metadata"]["table"] == "users"

    def test_export_as_documents_with_text_fields(self):
        data = CassandraData(
            data=[{"id": 1, "name": "Alice", "city": "Delhi"}],
            row_count=1,
            columns=["id", "name", "city"],
            keyspace="test",
            table_name="users",
            schema={},
        )

        ingestor = object.__new__(CassandraIngestor)
        ingestor.logger = MagicMock()

        documents = ingestor.export_as_documents(
            data,
            text_fields=["name"],
        )

        assert documents[0]["text"] == "Alice"

    def test_invalid_table_name(self):
        connector = MagicMock()
        connector.keyspace = "test"

        ingestor = CassandraIngestor(connector=connector)

        with pytest.raises(ValidationError, match="Invalid Cassandra table name"):
            ingestor.ingest_table("users;DROP TABLE users")

    @patch("semantica.ingest.cassandra_ingestor.CASSANDRA_AVAILABLE", True)
    def test_get_table_schema(self):
        mock_column_id = MagicMock()
        mock_column_id.name = "id"
        mock_column_id.cql_type = "int"
        mock_column_id.is_static = False

        mock_column_name = MagicMock()
        mock_column_name.name = "name"
        mock_column_name.cql_type = "text"
        mock_column_name.is_static = False


        mock_table = MagicMock()
        mock_table.columns = {
            "id": mock_column_id,
            "name": mock_column_name,
        }
        mock_table.primary_key = [mock_column_id]

        mock_keyspace = MagicMock()
        mock_keyspace.tables = {"users": mock_table}

        mock_cluster = MagicMock()
        mock_cluster.metadata.keyspaces = {"test": mock_keyspace}

        connector = MagicMock()
        connector.keyspace = "test"
        connector.cluster = mock_cluster
        connector.connect.return_value = MagicMock()

        ingestor = CassandraIngestor(connector=connector)

        schema = ingestor.get_table_schema("users")

        assert len(schema["columns"]) == 2
        assert schema["primary_keys"] == ["id"]
        assert schema["columns"][0]["name"] == "id"
        assert schema["columns"][0]["primary_key"] is True
        assert schema["columns"][1]["name"] == "name"
        assert schema["columns"][1]["primary_key"] is False


    def test_ingest_table(self):
        mock_session = MagicMock()

        mock_row1 = MagicMock()
        mock_row1._asdict.return_value = {
            "id": 1,
            "name": "Alice",
        }

        mock_row2 = MagicMock()
        mock_row2._asdict.return_value = {
            "id": 2,
            "name": "Bob",
        }

        mock_session.execute.return_value = [mock_row1, mock_row2]

        connector = MagicMock()
        connector.keyspace = "test"
        connector.connect.return_value = mock_session

        ingestor = CassandraIngestor(connector=connector)

        schema = {
            "columns": [
                {"name": "id"},
                {"name": "name"},
            ],
            "primary_keys": ["id"],
        }

        with patch.object(
            ingestor,
            "get_table_schema",
            return_value=schema,
        ):
            data = ingestor.ingest_table("users")

        assert data.row_count == 2
        assert data.columns == ["id", "name"]
        assert data.keyspace == "test"
        assert data.table_name == "users"
        assert data.data == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        mock_session.execute.assert_called_once_with(
            "SELECT * FROM test.users"
        )


    def test_ingest_table_with_limit(self):
        mock_session = MagicMock()

        mock_row = MagicMock()
        mock_row._asdict.return_value = {
            "id": 1,
            "name": "Alice",
        }

        mock_session.execute.return_value = [mock_row]

        connector = MagicMock()
        connector.keyspace = "test"
        connector.connect.return_value = mock_session

        ingestor = CassandraIngestor(connector=connector)

        schema = {
            "columns": [
                {"name": "id"},
                {"name": "name"},
            ],
            "primary_keys": ["id"],
        }

        with patch.object(
            ingestor,
            "get_table_schema",
            return_value=schema,
        ):
            data = ingestor.ingest_table("users", limit=10)

        assert data.row_count == 1
        mock_session.execute.assert_called_once_with(
            "SELECT * FROM test.users LIMIT 10"
        )

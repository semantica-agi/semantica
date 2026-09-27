"""
Cassandra Ingestion Module

Provides Cassandra data ingestion capabilities for the Semantica framework.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger


try:
    import cassandra
    from cassandra.auth import PlainTextAuthProvider

    CASSANDRA_AVAILABLE = True
except (ImportError, OSError):
    cassandra = None
    PlainTextAuthProvider = None
    CASSANDRA_AVAILABLE = False


@dataclass
class CassandraData:
    """Cassandra data representation."""

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    keyspace: str
    table_name: str
    schema: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class CassandraConnector:
    """Manage connections to a Cassandra cluster."""

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        port: int = 9042,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keyspace: Optional[str] = None,
        **config: Any,
    ) -> None:
        if not CASSANDRA_AVAILABLE:
            raise ImportError(
                "cassandra-driver is required for CassandraConnector. "
                "Install it with: pip install 'semantica[db-cassandra]'"
            )

        self.logger = get_logger("cassandra_connector")

        if (username and not password) or (password and not username):
            raise ValidationError(
                "Cassandra credentials must include both username and password, or neither"
            )

        self.hosts = hosts or ["127.0.0.1"]
        self.port = port
        self.username = username
        self.password = password
        self.keyspace = keyspace
        self.config = config

        self.cluster = None
        self.session = None

    def connect(self):
        """Connect to Cassandra and return the session."""
        if self.session is not None:
            return self.session

        try:
            from cassandra.cluster import Cluster

            auth_provider = None

            if self.username and self.password:
                auth_provider = PlainTextAuthProvider(
                    username=self.username,
                    password=self.password,
                )

            self.cluster = Cluster(
                contact_points=self.hosts,
                port=self.port,
                auth_provider=auth_provider,
                **self.config,
            )

            if self.keyspace:
                self.session = self.cluster.connect(self.keyspace)
            else:
                self.session = self.cluster.connect()

            self.logger.info("Connected to Cassandra")
            return self.session

        except Exception as exc:
            if self.cluster is not None:
                try:
                    self.cluster.shutdown()
                except Exception:
                    pass
            self.cluster = None
            self.session = None
            self.logger.error(
                "Failed to connect to Cassandra: %s",
                type(exc).__name__,
            )
            raise ProcessingError(
                f"Failed to connect to Cassandra: {type(exc).__name__}"
            ) from exc

    def disconnect(self) -> None:
        """Close the Cassandra connection."""
        if self.session is not None:
            try:
                self.session.shutdown()
            except Exception:
                pass
            finally:
                self.session = None

        if self.cluster is not None:
            try:
                self.cluster.shutdown()
            except Exception:
                pass
            finally:
                self.cluster = None

        self.logger.info("Disconnected from Cassandra")

    def test_connection(self) -> bool:
        """Test whether Cassandra is reachable."""
        already_connected = self.session is not None
        try:
            session = self.connect()
            session.execute("SELECT release_version FROM system.local")
            return True
        except Exception as exc:
            self.logger.debug(
                "Cassandra connection test failed: %s",
                type(exc).__name__,
            )
            return False
        finally:
            if not already_connected:
                self.disconnect()

def _validate_identifier(value: str, name: str) -> str:
    """Validate a Cassandra keyspace or table identifier."""
    if (
        not value
        or value[0].isdigit()
        or not all(char.isalnum() or char == "_" for char in value)
    ):
        raise ValidationError(f"Invalid Cassandra {name}: {value}")
    return value

class CassandraIngestor:
    """Cassandra data ingestion handler."""

    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        port: int = 9042,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keyspace: Optional[str] = None,
        connector: Optional[CassandraConnector] = None,
        **config: Any,
    ) -> None:
        self.logger = get_logger("cassandra_ingestor")

        self.connector = connector or CassandraConnector(
            hosts=hosts,
            port=port,
            username=username,
            password=password,
            keyspace=keyspace,
            **config,
        )

        self.keyspace = keyspace or self.connector.keyspace

    def get_table_schema(
        self,
        table_name: str,
        keyspace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get schema information for a Cassandra table."""
        keyspace = keyspace or self.keyspace

        if not keyspace:
            raise ValueError("keyspace is required")

        _validate_identifier(keyspace, "keyspace")
        _validate_identifier(table_name, "table name")

        try:
            if self.connector.cluster is None:
                self.connector.connect()

            keyspace_metadata = self.connector.cluster.metadata.keyspaces.get(
                keyspace
            )

            if keyspace_metadata is None:
                raise ValidationError(f"Keyspace not found: {keyspace}")

            table_metadata = keyspace_metadata.tables.get(table_name)

            if table_metadata is None:
                raise ValidationError(
                    f"Table not found: {keyspace}.{table_name}"
                )

            primary_key_names = {
                column.name for column in table_metadata.primary_key
            }

            columns = [
                {
                    "name": column.name,
                    "type": str(column.cql_type),
                    "nullable": column.name not in primary_key_names,
                    "primary_key": column.name in primary_key_names,
                    "static": column.is_static,
                }
                for column in table_metadata.columns.values()
            ]

            return {
                "columns": columns,
                "primary_keys": [
                    column.name for column in table_metadata.primary_key
                ],
            }

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to get Cassandra table schema: %s",
                type(exc).__name__,
            )
            raise ProcessingError(
                f"Failed to get Cassandra table schema: {type(exc).__name__}"
            ) from exc

    def ingest_table(
        self,
        table_name: str,
        keyspace: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> CassandraData:
        """Ingest rows and schema information from a Cassandra table."""
        keyspace = keyspace or self.keyspace

        if not keyspace:
            raise ValueError("keyspace is required")

        _validate_identifier(keyspace, "keyspace")
        _validate_identifier(table_name, "table name")

        try:
            session = self.connector.connect()

            schema = self.get_table_schema(
                table_name=table_name,
                keyspace=keyspace,
            )

            columns = [column["name"] for column in schema["columns"]]

            query = f"SELECT * FROM {keyspace}.{table_name}"

            if limit is not None:
                if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                    raise ValidationError(
                        f"Limit must be a positive integer, got {limit!r}"
                    )
                query += f" LIMIT {limit}"

            result = session.execute(query)

            rows = [
                dict(row._asdict()) if hasattr(row, "_asdict") else dict(row)
                for row in result
            ]

            return CassandraData(
                data=rows,
                row_count=len(rows),
                columns=columns,
                keyspace=keyspace,
                table_name=table_name,
                schema=schema,
                metadata={"query": query},
            )

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to ingest Cassandra table: %s",
                type(exc).__name__,
            )
            raise ProcessingError(
                f"Failed to ingest Cassandra table: {type(exc).__name__}"
            ) from exc

    def export_as_documents(
        self,
        data: CassandraData,
        id_field: str = "id",
        text_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert Cassandra rows to Semantica document dictionaries."""
        documents = []

        for idx, row in enumerate(data.data):
            doc = {
                "id": str(row.get(id_field, idx)),
                "metadata": {
                    "source": "cassandra",
                    "keyspace": data.keyspace,
                    "table": data.table_name,
                    "row_data": row,
                },
            }

            if text_fields:
                text_parts = [
                    str(row[field_name])
                    for field_name in text_fields
                    if field_name in row and row[field_name] is not None
                ]
            else:
                text_parts = [
                    str(value)
                    for value in row.values()
                    if isinstance(value, str)
                ]

            doc["text"] = " ".join(text_parts)
            documents.append(doc)

        self.logger.debug(
            "Exported %d Cassandra documents",
            len(documents),
        )

        return documents
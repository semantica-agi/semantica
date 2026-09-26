"""
Databricks Ingestion Module

This module provides comprehensive Databricks ingestion capabilities for the
Semantica framework, enabling data extraction from Databricks lakehouses
(Unity Catalog + Delta Lake) into the knowledge graph pipeline.

Key Features:
    - Native Databricks SQL connection using databricks-sql-connector
    - Unity Catalog metadata via databricks-sdk (catalogs, schemas, tables, columns)
    - Multiple authentication methods (personal access token, OAuth M2M)
    - Query execution with streaming and pagination
    - Table and schema introspection
    - Table-level and (optional) column-level lineage via Unity Catalog's lineage API
    - Progress tracking and error handling
    - Connection management with proper cleanup

Main Classes:
    - DatabricksIngestor: Main Databricks ingestion class
    - DatabricksConnector: Databricks connection handler
    - DatabricksData: Data representation for Databricks ingestion

Example Usage:
    >>> from semantica.ingest import DatabricksIngestor
    >>> ingestor = DatabricksIngestor(
    ...     host="https://adb-xxx.azuredatabricks.net",
    ...     token="dapi-xxxxxxxx",
    ...     http_path="/sql/1.0/warehouses/xxxxxxxx",
    ...     catalog="main",
    ...     schema="default",
    ... )
    >>> data = ingestor.ingest_table("customers", limit=10000)
    >>> query_data = ingestor.ingest_query("SELECT * FROM sales WHERE date > '2024-01-01'")
    >>> documents = ingestor.export_as_documents(data)

Author: Semantica Contributors
License: MIT
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .db_ingestor import _validate_sql_fragment

try:
    from databricks import sql as databricks_sql
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config, oauth_service_principal

    DATABRICKS_AVAILABLE = True
except (ImportError, OSError):
    databricks_sql = None
    WorkspaceClient = None
    Config = None
    oauth_service_principal = None
    DATABRICKS_AVAILABLE = False


@dataclass
class DatabricksData:
    """Databricks data representation."""

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    table_name: Optional[str] = None
    query: Optional[str] = None
    catalog: Optional[str] = None
    schema: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class DatabricksConnector:
    """
    Databricks connection management.

    This class manages connections to a Databricks workspace and provides
    support for multiple authentication methods.

    Supported Authentication Methods:
        - Personal Access Token (PAT)
        - OAuth M2M (service principal client id / secret)

    Example Usage:
        >>> connector = DatabricksConnector(
        ...     host="https://adb-xxx.azuredatabricks.net",
        ...     token="dapi-xxxxxxxx",
        ...     http_path="/sql/1.0/warehouses/xxxxxxxx",
        ... )
        >>> conn = connector.connect()
        >>> connector.disconnect()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        http_path: Optional[str] = None,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        **config,
    ):
        """
        Initialize Databricks connector.

        Args:
            host: Databricks workspace URL (e.g. 'https://adb-xxx.azuredatabricks.net')
            token: Personal access token (for PAT authentication)
            http_path: HTTP path of a SQL warehouse or cluster
                (e.g. '/sql/1.0/warehouses/xxxxxxxx')
            catalog: Default Unity Catalog catalog to use
            schema: Default schema to use
            client_id: OAuth M2M service principal client ID
            client_secret: OAuth M2M service principal client secret
            **config: Additional Databricks connection configuration
        """
        if not DATABRICKS_AVAILABLE:
            raise ImportError(
                "databricks-sdk and databricks-sql-connector are required for "
                "DatabricksConnector. Install them with: "
                "pip install databricks-sdk databricks-sql-connector"
            )

        self.logger = get_logger("databricks_connector")

        # Get configuration from environment variables if not provided
        self.host = host or os.getenv("DATABRICKS_HOST")
        self.token = token or os.getenv("DATABRICKS_TOKEN")
        self.http_path = http_path or os.getenv("DATABRICKS_HTTP_PATH")
        self.catalog = catalog or os.getenv("DATABRICKS_CATALOG", "main")
        self.schema = schema or os.getenv("DATABRICKS_SCHEMA", "default")
        self.client_id = client_id or os.getenv("DATABRICKS_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("DATABRICKS_CLIENT_SECRET")

        # Validate required parameters
        if not self.host:
            raise ValidationError(
                "Databricks host is required. "
                "Provide via 'host' parameter or DATABRICKS_HOST environment variable."
            )

        if not (self.client_id and self.client_secret) and not self.token:
            raise ValidationError(
                "Databricks authentication is required. "
                "Provide either 'token' (or DATABRICKS_TOKEN) for personal access "
                "token authentication, or 'client_id'/'client_secret' (or "
                "DATABRICKS_CLIENT_ID/DATABRICKS_CLIENT_SECRET) for OAuth M2M "
                "authentication."
            )

        self.config = config
        self.connection = None
        self._workspace_client: Optional["WorkspaceClient"] = None

        self.logger.debug(
            f"Databricks connector initialized: host={self.host}, "
            f"catalog={self.catalog}, schema={self.schema}"
        )

    def connect(self):
        """
        Establish a Databricks SQL connection for table/query ingestion.

        If a connection is already open (e.g. because the ingestor is being
        used as a context manager), it is reused instead of opening a second
        one, which would otherwise be left unclosed.

        Authentication:
            - Personal access token: pass ``access_token`` to ``sql.connect``.
            - OAuth M2M (service principal): ``sql.connect`` does **not** accept
              ``client_id``/``client_secret`` directly. The correct mechanism is
              ``credentials_provider``, a callable that returns a header-factory
              produced by ``databricks.sdk.core.oauth_service_principal``.

        Returns:
            Connection: databricks-sql-connector connection object

        Raises:
            ProcessingError: If connection fails
            ValidationError: If 'http_path' is not configured
        """
        if self.connection is not None:
            return self.connection

        if not self.http_path:
            raise ValidationError(
                "Databricks 'http_path' is required for SQL ingestion. "
                "Provide via 'http_path' parameter or DATABRICKS_HTTP_PATH "
                "environment variable (the HTTP path of a SQL warehouse or cluster)."
            )

        try:
            conn_params: Dict[str, Any] = {
                "server_hostname": self._hostname(),
                "http_path": self.http_path,
            }

            if self.client_id and self.client_secret:
                # databricks-sql-connector ≥2.5 requires OAuth M2M to be wired
                # through a credentials_provider callable; passing client_id /
                # client_secret as plain kwargs is silently ignored and causes
                # the connector to fall back to an interactive browser flow.
                _client_id = self.client_id
                _client_secret = self.client_secret
                _host = self.host

                def _m2m_credentials_provider():
                    cfg = Config(
                        host=_host,
                        client_id=_client_id,
                        client_secret=_client_secret,
                    )
                    return oauth_service_principal(cfg)

                conn_params["credentials_provider"] = _m2m_credentials_provider
            else:
                conn_params["access_token"] = self.token

            conn_params.update(self.config)

            self.connection = databricks_sql.connect(**conn_params)

            self.logger.info(f"Connected to Databricks: {self.host}")

            return self.connection

        except Exception as e:
            self.logger.error(f"Failed to connect to Databricks: {e}")
            raise ProcessingError(f"Failed to connect to Databricks: {e}") from e

    def _hostname(self) -> str:
        """Strip the scheme from the configured host for the SQL connector."""
        return re.sub(r"^https?://", "", self.host).rstrip("/")

    def get_workspace_client(self) -> "WorkspaceClient":
        """
        Get (and lazily create) a Unity Catalog WorkspaceClient.

        Returns:
            WorkspaceClient: databricks-sdk workspace client

        Raises:
            ProcessingError: If client creation fails
        """
        if self._workspace_client is not None:
            return self._workspace_client

        try:
            if self.client_id and self.client_secret:
                self._workspace_client = WorkspaceClient(
                    host=self.host,
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )
            else:
                self._workspace_client = WorkspaceClient(
                    host=self.host, token=self.token
                )
            return self._workspace_client
        except Exception as e:
            self.logger.error(f"Failed to create Databricks workspace client: {e}")
            raise ProcessingError(
                f"Failed to create Databricks workspace client: {e}"
            ) from e

    def disconnect(self):
        """Close Databricks SQL connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.info("Disconnected from Databricks")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")

    def test_connection(self) -> bool:
        """
        Test the Databricks SQL connection without keeping it open.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            self.connection = None
            return True
        except Exception as e:
            self.logger.debug(f"Connection test failed: {e}")
            return False


class DatabricksIngestor:
    """
    Databricks ingestion handler.

    This class provides comprehensive Databricks ingestion capabilities,
    connecting to Databricks SQL warehouses/clusters for table and query
    ingestion, and to Unity Catalog for metadata and lineage introspection.

    Features:
        - Table ingestion with pagination
        - Query execution with streaming
        - Unity Catalog schema introspection
        - Table-level lineage
        - Multiple authentication methods
        - Progress tracking and error handling
        - Connection management with proper cleanup

    Example Usage:
        >>> ingestor = DatabricksIngestor(
        ...     host="https://adb-xxx.azuredatabricks.net",
        ...     token="dapi-xxxxxxxx",
        ...     http_path="/sql/1.0/warehouses/xxxxxxxx",
        ...     catalog="main",
        ... )
        >>> data = ingestor.ingest_table("customers", limit=10000)
        >>> query_data = ingestor.ingest_query("SELECT * FROM sales")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        token: Optional[str] = None,
        http_path: Optional[str] = None,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize Databricks ingestor.

        Args:
            host: Databricks workspace URL
            token: Personal access token
            http_path: HTTP path of a SQL warehouse or cluster
            catalog: Default catalog (default: 'main')
            schema: Default schema (default: 'default')
            client_id: OAuth M2M service principal client ID
            client_secret: OAuth M2M service principal client secret
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.logger = get_logger("databricks_ingestor")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize connector
        self.connector = DatabricksConnector(
            host=host,
            token=token,
            http_path=http_path,
            catalog=catalog,
            schema=schema,
            client_id=client_id,
            client_secret=client_secret,
            **self.config,
        )

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Databricks ingestor initialized")

    def _escape_identifier(self, identifier: str) -> str:
        """Escape a SQL identifier by wrapping in backticks and doubling internal backticks.

        Args:
            identifier: The identifier to escape

        Returns:
            Properly escaped identifier safe for SQL interpolation
        """
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"

    def _full_table_name(
        self, table_name: str, catalog: Optional[str], schema: Optional[str]
    ) -> str:
        """Build a fully-qualified 'catalog.schema.table' identifier, omitting
        any component (catalog and/or schema) that wasn't provided."""
        parts = [part for part in (catalog, schema, table_name) if part]
        return ".".join(parts)

    def _escaped_table_ref(
        self, table_name: str, catalog: Optional[str], schema: Optional[str]
    ) -> str:
        """Build a fully-qualified, identifier-escaped table reference for SQL,
        omitting any component (catalog and/or schema) that wasn't provided."""
        parts = [
            self._escape_identifier(part)
            for part in (catalog, schema, table_name)
            if part
        ]
        return ".".join(parts)

    def ingest_table(
        self,
        table_name: str,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        **options,
    ) -> DatabricksData:
        """
        Ingest data from a Databricks (Delta) table.

        This method retrieves data from a Unity Catalog table with optional
        filtering, pagination, and ordering.

        Args:
            table_name: Name of the table to ingest
            catalog: Catalog name (uses default if not provided)
            schema: Schema name (uses default if not provided)
            limit: Maximum number of rows to retrieve (optional)
            offset: Row offset for pagination (optional)
            where: WHERE clause for filtering (optional, must be trusted SQL)
            order_by: ORDER BY clause for sorting (optional, must be trusted SQL)
            **options: Additional query options

        Warning:
            The 'where' and 'order_by' parameters accept raw SQL and must be
            trusted input from the caller. Do not pass untrusted user input.

        Returns:
            DatabricksData: Ingested data object containing:
                - data: List of row dictionaries
                - row_count: Number of rows retrieved
                - columns: List of column names
                - table_name: Table name
                - catalog: Catalog name
                - schema: Schema name

        Raises:
            ProcessingError: If table ingestion fails
        """
        catalog = catalog or self.connector.catalog
        schema = schema or self.connector.schema

        # Validate SQL fragments BEFORE opening any connection so invalid
        # inputs are rejected cheaply without a network round-trip.
        if where:
            _validate_sql_fragment(where, "where")

        tracking_id = self.progress_tracker.start_tracking(
            file=f"{catalog}.{schema}.{table_name}",
            module="ingest",
            submodule="DatabricksIngestor",
            message=f"Table: {catalog}.{schema}.{table_name}",
        )

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()
            try:
                table_ref = self._escaped_table_ref(table_name, catalog, schema)

                query = f"SELECT * FROM {table_ref}"

                if where:
                    query += f" WHERE {where}"

                if order_by:
                    _SAFE_ORDER_RE = re.compile(
                        r"^[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?"
                        r"(\s*,\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?)*$",
                        re.IGNORECASE,
                    )
                    if not _SAFE_ORDER_RE.match(order_by.strip()):
                        raise ValueError(f"Invalid ORDER BY clause: '{order_by}'")
                    query += f" ORDER BY {order_by}"

                if limit is not None:
                    query += f" LIMIT {int(limit)}"

                if offset is not None:
                    query += f" OFFSET {int(offset)}"

                self.logger.debug(f"Executing query: {query}")

                self.progress_tracker.update_tracking(
                    tracking_id, message="Executing query..."
                )

                cursor = conn.cursor()
                cursor.execute(query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Fetching results..."
                )

                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )
                rows = cursor.fetchall()
                row_dicts = [dict(zip(columns, row)) for row in rows]

                cursor.close()

                data = self._convert_rows(row_dicts)

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Ingested {len(data)} rows",
                )

                self.logger.info(f"Table ingestion completed: {len(data)} row(s)")

                return DatabricksData(
                    data=data,
                    row_count=len(data),
                    columns=columns,
                    table_name=table_name,
                    catalog=catalog,
                    schema=schema,
                    metadata={"query": query},
                )
            finally:
                if not already_connected:
                    self.connector.disconnect()

        except ValidationError:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Validation failed"
            )
            raise
        except ProcessingError:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Processing failed"
            )
            raise
        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to ingest table: {e}")
            raise ProcessingError(f"Failed to ingest table: {e}") from e

    def ingest_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        batch_size: Optional[int] = None,
        **options,
    ) -> DatabricksData:
        """
        Execute a Databricks SQL query and ingest results.

        This method executes a SQL query and returns the results with
        optional batching for large result sets.

        Args:
            query: SQL query to execute
            parameters: Query parameters for parameterized queries (optional)
            batch_size: Batch size for result fetching (optional)
            **options: Additional query options

        Returns:
            DatabricksData: Query results as DatabricksData object

        Raises:
            ProcessingError: If query execution fails

        Example:
            >>> data = ingestor.ingest_query(
            ...     "SELECT * FROM sales WHERE date > :date",
            ...     parameters={"date": "2024-01-01"}
            ... )
        """
        tracking_id = self.progress_tracker.start_tracking(
            file="query",
            module="ingest",
            submodule="DatabricksIngestor",
            message="Executing query...",
        )

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()
            try:
                self.logger.debug(f"Executing query: {query[:100]}...")

                cursor = conn.cursor()

                if parameters:
                    cursor.execute(query, parameters)
                else:
                    cursor.execute(query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Fetching results..."
                )

                columns = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description
                    else []
                )

                if batch_size:
                    all_rows = []
                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break
                        all_rows.extend(rows)
                        self.progress_tracker.update_tracking(
                            tracking_id, message=f"Fetched {len(all_rows)} rows..."
                        )
                else:
                    all_rows = cursor.fetchall()

                row_dicts = [dict(zip(columns, row)) for row in all_rows]

                cursor.close()

                data = self._convert_rows(row_dicts)

                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message=f"Query completed: {len(data)} rows",
                )

                self.logger.info(f"Query execution completed: {len(data)} row(s)")

                return DatabricksData(
                    data=data,
                    row_count=len(data),
                    columns=columns,
                    query=query,
                    metadata={"parameters": parameters} if parameters else {},
                )
            finally:
                if not already_connected:
                    self.connector.disconnect()

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to execute query: {e}")
            raise ProcessingError(f"Failed to execute query: {e}") from e

    def get_table_schema(
        self,
        table_name: str,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get schema information for a Unity Catalog table.

        Args:
            table_name: Name of the table
            catalog: Catalog name (uses default if not provided)
            schema: Schema name (uses default if not provided)

        Returns:
            dict: Table schema information containing:
                - columns: List of column dictionaries with name, type, nullable
                - primary_keys: List of primary key column names (if any)

        Raises:
            ProcessingError: If schema retrieval fails
        """
        try:
            catalog = catalog or self.connector.catalog
            schema = schema or self.connector.schema

            if not catalog:
                raise ValidationError(
                    "Catalog name is required for schema introspection. "
                    "Provide via 'catalog' parameter or set default catalog in connector."
                )

            if not schema:
                raise ValidationError(
                    "Schema name is required for schema introspection. "
                    "Provide via 'schema' parameter or set default schema in connector."
                )

            client = self.connector.get_workspace_client()
            full_name = self._full_table_name(table_name, catalog, schema)

            table_info = client.tables.get(full_name=full_name)

            column_info = []
            primary_keys: List[str] = []
            for col in getattr(table_info, "columns", None) or []:
                column_info.append(
                    {
                        "name": col.name,
                        "type": getattr(col, "type_text", None)
                        or getattr(col, "type_name", None),
                        "nullable": getattr(col, "nullable", True),
                        "comment": getattr(col, "comment", None),
                    }
                )

            self.logger.debug(
                f"Retrieved schema for {full_name}: {len(column_info)} columns"
            )

            return {"columns": column_info, "primary_keys": primary_keys}

        except Exception as e:
            self.logger.error(f"Failed to get table schema: {e}")
            raise ProcessingError(f"Failed to get table schema: {e}") from e

    def list_catalogs(self) -> List[str]:
        """
        List all catalogs visible in Unity Catalog.

        Returns:
            list: List of catalog names

        Raises:
            ProcessingError: If listing fails
        """
        try:
            client = self.connector.get_workspace_client()
            catalogs = [c.name for c in client.catalogs.list()]

            self.logger.debug(f"Found {len(catalogs)} catalogs")

            return catalogs

        except Exception as e:
            self.logger.error(f"Failed to list catalogs: {e}")
            raise ProcessingError(f"Failed to list catalogs: {e}") from e

    def list_schemas(self, catalog: Optional[str] = None) -> List[str]:
        """
        List all schemas in a catalog.

        Args:
            catalog: Catalog name (uses default if not provided)

        Returns:
            list: List of schema names

        Raises:
            ProcessingError: If listing fails
        """
        try:
            catalog = catalog or self.connector.catalog

            if not catalog:
                raise ValidationError(
                    "Catalog name is required for listing schemas. "
                    "Provide via 'catalog' parameter or set default catalog in connector."
                )

            client = self.connector.get_workspace_client()
            schemas = [s.name for s in client.schemas.list(catalog_name=catalog)]

            self.logger.debug(f"Found {len(schemas)} schemas in {catalog}")

            return schemas

        except Exception as e:
            self.logger.error(f"Failed to list schemas: {e}")
            raise ProcessingError(f"Failed to list schemas: {e}") from e

    def list_tables(
        self, catalog: Optional[str] = None, schema: Optional[str] = None
    ) -> List[str]:
        """
        List all tables in a Unity Catalog catalog/schema.

        Args:
            catalog: Catalog name (uses default if not provided)
            schema: Schema name (uses default if not provided)

        Returns:
            list: List of table names

        Raises:
            ProcessingError: If listing fails
        """
        try:
            catalog = catalog or self.connector.catalog
            schema = schema or self.connector.schema

            if not catalog:
                raise ValidationError(
                    "Catalog name is required for listing tables. "
                    "Provide via 'catalog' parameter or set default catalog in connector."
                )

            if not schema:
                raise ValidationError(
                    "Schema name is required for listing tables. "
                    "Provide via 'schema' parameter or set default schema in connector."
                )

            client = self.connector.get_workspace_client()
            tables = [
                t.name
                for t in client.tables.list(catalog_name=catalog, schema_name=schema)
            ]

            self.logger.debug(f"Found {len(tables)} tables in {catalog}.{schema}")

            return tables

        except Exception as e:
            self.logger.error(f"Failed to list tables: {e}")
            raise ProcessingError(f"Failed to list tables: {e}") from e

    def get_table_lineage(
        self,
        table_name: str,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        include_column_lineage: bool = False,
    ) -> Dict[str, Any]:
        """
        Get table-level (and optionally column-level) lineage from Unity Catalog.

        Args:
            table_name: Name of the table
            catalog: Catalog name (uses default if not provided)
            schema: Schema name (uses default if not provided)
            include_column_lineage: If True, also fetch per-column upstream/
                downstream lineage via Unity Catalog's column-lineage API. This
                issues one additional request per column in the table, so it is
                slower than table-level lineage alone and is opt-in.

        Returns:
            dict: Lineage information containing:
                - upstream: List of fully-qualified upstream table names
                - downstream: List of fully-qualified downstream table names
                - columns: (only when include_column_lineage=True) dict mapping
                  each column name to {"upstream": [...], "downstream": [...]}
                  fully-qualified column references

        Raises:
            ProcessingError: If lineage retrieval fails
        """
        try:
            catalog = catalog or self.connector.catalog
            schema = schema or self.connector.schema

            if not catalog:
                raise ValidationError(
                    "Catalog name is required for lineage retrieval. "
                    "Provide via 'catalog' parameter or set default catalog in connector."
                )

            if not schema:
                raise ValidationError(
                    "Schema name is required for lineage retrieval. "
                    "Provide via 'schema' parameter or set default schema in connector."
                )

            full_name = self._full_table_name(table_name, catalog, schema)

            client = self.connector.get_workspace_client()

            response = client.api_client.do(
                "GET",
                "/api/2.0/lineage-tracking/table-lineage",
                query={"table_name": full_name, "include_entity_lineage": False},
            )

            upstream = [
                item.get("tableInfo", {}).get("name")
                for item in response.get("upstreams", []) or []
                if item.get("tableInfo")
            ]
            downstream = [
                item.get("tableInfo", {}).get("name")
                for item in response.get("downstreams", []) or []
                if item.get("tableInfo")
            ]

            self.logger.debug(
                f"Retrieved lineage for {full_name}: "
                f"{len(upstream)} upstream, {len(downstream)} downstream"
            )

            result: Dict[str, Any] = {"upstream": upstream, "downstream": downstream}

            if include_column_lineage:
                result["columns"] = self._get_column_lineage(
                    client, full_name, table_name, catalog, schema
                )

            return result

        except Exception as e:
            self.logger.error(f"Failed to get table lineage: {e}")
            raise ProcessingError(f"Failed to get table lineage: {e}") from e

    def _get_column_lineage(
        self,
        client: "WorkspaceClient",
        full_name: str,
        table_name: str,
        catalog: str,
        schema: str,
    ) -> Dict[str, Dict[str, List[str]]]:
        """Fetch per-column lineage for every column in a table.

        Unity Catalog's column-lineage API resolves one column at a time, so
        this issues one lineage-tracking request per column in the table's
        schema. Columns that fail to resolve lineage (no permissions, no
        tracked lineage, etc.) are skipped rather than failing the whole call.
        """
        schema_info = self.get_table_schema(table_name, catalog=catalog, schema=schema)
        columns_lineage: Dict[str, Dict[str, List[str]]] = {}

        for column in schema_info["columns"]:
            column_name = column["name"]
            try:
                response = client.api_client.do(
                    "GET",
                    "/api/2.0/lineage-tracking/column-lineage",
                    query={"table_name": full_name, "column_name": column_name},
                )
            except Exception as e:
                self.logger.debug(
                    f"Skipping column lineage for {full_name}.{column_name}: {e}"
                )
                continue

            columns_lineage[column_name] = {
                "upstream": [
                    ref
                    for ref in (
                        self._format_column_ref(item)
                        for item in response.get("upstream_cols", []) or []
                    )
                    if ref
                ],
                "downstream": [
                    ref
                    for ref in (
                        self._format_column_ref(item)
                        for item in response.get("downstream_cols", []) or []
                    )
                    if ref
                ],
            }

        return columns_lineage

    @staticmethod
    def _format_column_ref(item: Dict[str, Any]) -> Optional[str]:
        """Format a Unity Catalog column-lineage entry as 'catalog.schema.table.column'."""
        table = item.get("table_name") or item.get("tableName")
        column = item.get("name") or item.get("column_name") or item.get("columnName")
        if not table or not column:
            return None
        catalog_name = item.get("catalog_name") or item.get("catalogName")
        schema_name = item.get("schema_name") or item.get("schemaName")
        parts = [part for part in (catalog_name, schema_name, table, column) if part]
        return ".".join(parts)

    def export_as_documents(
        self,
        data: DatabricksData,
        id_field: str = "id",
        text_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert Databricks data to document format for Semantica processing.

        Args:
            data: DatabricksData object to convert
            id_field: Field to use as document ID (default: 'id')
            text_fields: List of fields to combine into document text (optional)

        Returns:
            list: List of document dictionaries

        Example:
            >>> data = ingestor.ingest_table("customers")
            >>> documents = ingestor.export_as_documents(data, text_fields=["name", "notes"])
        """
        documents = []

        for idx, row in enumerate(data.data):
            doc = {
                "id": str(row.get(id_field, idx)),
                "metadata": {
                    "source": "databricks",
                    "table": data.table_name,
                    "catalog": data.catalog,
                    "schema": data.schema,
                },
            }

            if text_fields:
                text_parts = []
                for field_name in text_fields:
                    if field_name in row and row[field_name] is not None:
                        text_parts.append(str(row[field_name]))
                doc["text"] = " ".join(text_parts)
            else:
                text_parts = []
                for key, value in row.items():
                    if isinstance(value, str):
                        text_parts.append(value)
                doc["text"] = " ".join(text_parts)

            doc["metadata"]["row_data"] = row

            documents.append(doc)

        self.logger.debug(f"Exported {len(documents)} documents")

        return documents

    def close(self):
        """Close Databricks connection."""
        self.connector.disconnect()

    def _convert_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Databricks rows to JSON-serializable format.

        Args:
            rows: List of row dictionaries from Databricks

        Returns:
            list: Converted row dictionaries
        """
        converted = []

        for row in rows:
            converted_row = {}
            for key, value in row.items():
                if isinstance(value, datetime):
                    converted_row[key] = value.isoformat()
                elif isinstance(value, bytes):
                    try:
                        converted_row[key] = value.decode("utf-8")
                    except UnicodeDecodeError:
                        converted_row[key] = str(value)
                else:
                    converted_row[key] = value

            converted.append(converted_row)

        return converted

    def __enter__(self):
        """Context manager entry."""
        self.connector.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

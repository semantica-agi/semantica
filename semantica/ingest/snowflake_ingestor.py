"""
Snowflake Ingestion Module

This module provides comprehensive Snowflake ingestion capabilities for the
Semantica framework, enabling data extraction from Snowflake data warehouses.

Key Features:
    - Native Snowflake connection using snowflake-connector-python
    - Multiple authentication methods (password, key-pair, OAuth, SSO)
    - Query execution with streaming and pagination
    - Table and schema introspection
    - Batch data loading
    - Progress tracking and error handling
    - Connection management with proper cleanup

Main Classes:
    - SnowflakeIngestor: Main Snowflake ingestion class
    - SnowflakeConnector: Snowflake connection handler
    - SnowflakeData: Data representation for Snowflake ingestion

Example Usage:
    >>> from semantica.ingest import SnowflakeIngestor
    >>> ingestor = SnowflakeIngestor(
    ...     account="myaccount",
    ...     user="myuser",
    ...     password="mypassword",
    ...     warehouse="COMPUTE_WH",
    ...     database="MYDB",
    ...     schema="PUBLIC"
    ... )
    >>> data = ingestor.ingest_table("CUSTOMERS", limit=10000)
    >>> query_data = ingestor.ingest_query("SELECT * FROM SALES WHERE date > '2024-01-01'")
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

try:
    import snowflake.connector
    from snowflake.connector import DictCursor, SnowflakeConnection

    SNOWFLAKE_AVAILABLE = True
except (ImportError, OSError):
    snowflake = None
    SnowflakeConnection = None
    DictCursor = None
    SNOWFLAKE_AVAILABLE = False


@dataclass
class SnowflakeData:
    """Snowflake data representation."""

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    table_name: Optional[str] = None
    query: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class SnowflakeConnector:
    """
    Snowflake connection management.

    This class manages connections to Snowflake and provides support for
    multiple authentication methods.

    Supported Authentication Methods:
        - Password: Username and password
        - Key-pair: Private key authentication
        - OAuth: OAuth token authentication
        - SSO: External browser SSO (where applicable)

    Example Usage:
        >>> connector = SnowflakeConnector(
        ...     account="myaccount",
        ...     user="myuser",
        ...     password="mypassword"
        ... )
        >>> conn = connector.connect()
        >>> connector.disconnect()
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        authenticator: Optional[str] = None,
        private_key: Optional[bytes] = None,
        private_key_path: Optional[str] = None,
        private_key_passphrase: Optional[str] = None,
        token: Optional[str] = None,
        **config,
    ):
        """
        Initialize Snowflake connector.

        Args:
            account: Snowflake account identifier (e.g., 'myaccount')
            user: Snowflake username
            password: User password (for password authentication)
            warehouse: Default warehouse to use
            database: Default database to use
            schema: Default schema to use
            role: Snowflake role to use
            authenticator: Authentication method:
                - None or 'snowflake': Password authentication (default)
                - 'externalbrowser': SSO via external browser
                - 'oauth': OAuth token authentication
                - 'snowflake_jwt': Key-pair authentication
            private_key: Private key bytes (for key-pair auth)
            private_key_path: Path to private key file (for key-pair auth)
            private_key_passphrase: Passphrase for encrypted private key
            token: OAuth token (for OAuth authentication)
            **config: Additional Snowflake connection configuration
        """
        if not SNOWFLAKE_AVAILABLE:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeConnector. "
                "Install it with: pip install snowflake-connector-python"
            )

        self.logger = get_logger("snowflake_connector")

        # Get configuration from environment variables if not provided
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = user or os.getenv("SNOWFLAKE_USER")
        self.password = password or os.getenv("SNOWFLAKE_PASSWORD")
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE")
        self.database = database or os.getenv("SNOWFLAKE_DATABASE")
        self.schema = schema or os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
        self.role = role or os.getenv("SNOWFLAKE_ROLE")
        self.authenticator = authenticator or os.getenv("SNOWFLAKE_AUTHENTICATOR")
        self.token = token or os.getenv("SNOWFLAKE_TOKEN")

        # Validate required parameters
        if not self.account:
            raise ValidationError(
                "Snowflake account is required. "
                "Provide via 'account' parameter or SNOWFLAKE_ACCOUNT environment variable."
            )

        if not self.user:
            raise ValidationError(
                "Snowflake user is required. "
                "Provide via 'user' parameter or SNOWFLAKE_USER environment variable."
            )

        # Handle private key authentication
        self.private_key = private_key
        if private_key_path and not private_key:
            self.private_key = self._load_private_key(
                private_key_path, private_key_passphrase
            )

        self.config = config
        self.connection: Optional[SnowflakeConnection] = None

        self.logger.debug(
            f"Snowflake connector initialized: account={self.account}, user={self.user}, "
            f"warehouse={self.warehouse}, database={self.database}, schema={self.schema}"
        )

    def _load_private_key(
        self, key_path: str, passphrase: Optional[str] = None
    ) -> bytes:
        """
        Load private key from file for key-pair authentication.

        Args:
            key_path: Path to private key file (PEM format)
            passphrase: Optional passphrase for encrypted key

        Returns:
            bytes: Private key bytes

        Raises:
            ProcessingError: If key loading fails
        """
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization

            with open(key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=passphrase.encode() if passphrase else None,
                    backend=default_backend(),
                )

            pkb = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            self.logger.debug(f"Loaded private key from: {key_path}")
            return pkb

        except Exception as e:
            self.logger.error(f"Failed to load private key: {e}")
            raise ProcessingError(f"Failed to load private key: {e}") from e

    def connect(self) -> SnowflakeConnection:
        """
        Establish Snowflake connection.

        This method creates a connection to Snowflake using the configured
        authentication method and connection parameters.

        Returns:
            SnowflakeConnection: Snowflake connection object

        Raises:
            ProcessingError: If connection fails
        """
        try:
            # Build connection parameters
            conn_params = {
                "account": self.account,
                "user": self.user,
                "application": "Semantica",
            }

            # Add optional parameters
            if self.warehouse:
                conn_params["warehouse"] = self.warehouse
            if self.database:
                conn_params["database"] = self.database
            if self.schema:
                conn_params["schema"] = self.schema
            if self.role:
                conn_params["role"] = self.role

            # Configure authentication
            if self.authenticator:
                conn_params["authenticator"] = self.authenticator

                if self.authenticator == "oauth":
                    if not self.token:
                        raise ValidationError(
                            "OAuth token is required when using OAuth authentication. "
                            "Provide via 'token' parameter or SNOWFLAKE_TOKEN environment variable."
                        )
                    conn_params["token"] = self.token
            elif self.private_key:
                # Key-pair authentication
                conn_params["private_key"] = self.private_key
            else:
                # Password authentication
                if not self.password:
                    raise ValidationError(
                        "Password is required for password authentication. "
                        "Provide via 'password' parameter or SNOWFLAKE_PASSWORD environment variable."
                    )
                conn_params["password"] = self.password

            # Add additional config
            conn_params.update(self.config)

            # Create connection
            self.connection = snowflake.connector.connect(**conn_params)

            # Test connection
            cursor = self.connection.cursor()
            cursor.execute("SELECT CURRENT_VERSION()")
            version = cursor.fetchone()
            cursor.close()

            self.logger.info(
                f"Connected to Snowflake: {self.account}, version: {version[0] if version else 'unknown'}"
            )

            return self.connection

        except Exception as e:
            self.logger.error(f"Failed to connect to Snowflake: {e}")
            raise ProcessingError(f"Failed to connect to Snowflake: {e}") from e

    def disconnect(self):
        """Close Snowflake connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                self.logger.info("Disconnected from Snowflake")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")

    def test_connection(self) -> bool:
        """
        Test Snowflake connection without creating a persistent connection.

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


class SnowflakeIngestor:
    """
    Snowflake ingestion handler.

    This class provides comprehensive Snowflake ingestion capabilities,
    connecting to Snowflake data warehouses, executing queries, and
    exporting data with pagination and streaming support.

    Features:
        - Table ingestion with pagination
        - Query execution with streaming
        - Schema introspection
        - Batch data loading
        - Multiple authentication methods
        - Progress tracking and error handling
        - Connection management with proper cleanup

    Example Usage:
        >>> ingestor = SnowflakeIngestor(
        ...     account="myaccount",
        ...     user="myuser",
        ...     password="mypassword",
        ...     warehouse="COMPUTE_WH",
        ...     database="MYDB"
        ... )
        >>> data = ingestor.ingest_table("CUSTOMERS", limit=10000)
        >>> query_data = ingestor.ingest_query("SELECT * FROM SALES")
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        role: Optional[str] = None,
        authenticator: Optional[str] = None,
        private_key: Optional[bytes] = None,
        private_key_path: Optional[str] = None,
        private_key_passphrase: Optional[str] = None,
        token: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize Snowflake ingestor.

        Args:
            account: Snowflake account identifier
            user: Snowflake username
            password: User password
            warehouse: Default warehouse
            database: Default database
            schema: Default schema (default: PUBLIC)
            role: Snowflake role
            authenticator: Authentication method
            private_key: Private key bytes (for key-pair auth)
            private_key_path: Path to private key file
            private_key_passphrase: Passphrase for private key
            token: OAuth token
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.logger = get_logger("snowflake_ingestor")
        self.config = config or {}
        self.config.update(kwargs)

        # Initialize connector
        self.connector = SnowflakeConnector(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
            authenticator=authenticator,
            private_key=private_key,
            private_key_path=private_key_path,
            private_key_passphrase=private_key_passphrase,
            token=token,
            **self.config,
        )

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Snowflake ingestor initialized")

    def _escape_identifier(self, identifier: str) -> str:
        """Escape SQL identifier by wrapping in quotes and doubling internal quotes.
        
        Args:
            identifier: The identifier to escape
            
        Returns:
            Properly escaped identifier safe for SQL interpolation
        """
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def ingest_table(
        self,
        table_name: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        **options,
    ) -> SnowflakeData:
        """
        Ingest data from Snowflake table.

        This method retrieves data from a Snowflake table with optional
        filtering, pagination, and ordering.

        Args:
            table_name: Name of the table to ingest
            database: Database name (uses default if not provided)
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
            SnowflakeData: Ingested data object containing:
                - data: List of row dictionaries
                - row_count: Number of rows retrieved
                - columns: List of column names
                - table_name: Table name
                - database: Database name
                - schema: Schema name

        Raises:
            ProcessingError: If table ingestion fails
        """
        database = database or self.connector.database
        schema = schema or self.connector.schema

        tracking_id = self.progress_tracker.start_tracking(
            file=f"{database}.{schema}.{table_name}",
            module="ingest",
            submodule="SnowflakeIngestor",
            message=f"Table: {database}.{schema}.{table_name}",
        )

        try:
            # Connect to Snowflake
            conn = self.connector.connect()

            # Build query with escaped identifiers
            if database and schema:
                table_ref = (
                    f"{self._escape_identifier(database)}."
                    f"{self._escape_identifier(schema)}."
                    f"{self._escape_identifier(table_name)}"
                )
            else:
                table_ref = self._escape_identifier(table_name)
            
            query = f"SELECT * FROM {table_ref}"
            params: list = []

            if where:
                # where is appended verbatim — callers MUST only pass
                # trusted, application-controlled predicates here.
                # Reject obvious injection attempts: multiple statements.
                if ";" in where:
                    raise ValueError("Invalid WHERE clause: semicolons not permitted.")
                query += f" WHERE {where}"

            if order_by:
                # Validate order_by to column names + optional ASC/DESC only.
                _SAFE_ORDER_RE = re.compile(
                    r'^[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?'
                    r'(\s*,\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?)*$',
                    re.IGNORECASE,
                )
                if not _SAFE_ORDER_RE.match(order_by.strip()):
                    raise ValueError(f"Invalid ORDER BY clause: '{order_by}'")
                query += f" ORDER BY {order_by}"

            if limit is not None:
                query += " LIMIT %s"
                params.append(int(limit))

            if offset is not None:
                query += " OFFSET %s"
                params.append(int(offset))

            self.logger.debug(f"Executing query: {query}")

            # Execute query
            self.progress_tracker.update_tracking(
                tracking_id, message="Executing query..."
            )

            cursor = conn.cursor(DictCursor)
            cursor.execute(query, params if params else None)

            # Fetch results
            self.progress_tracker.update_tracking(
                tracking_id, message="Fetching results..."
            )

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            cursor.close()

            # Convert to JSON-serializable format
            data = self._convert_rows(rows)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {len(data)} rows",
            )

            self.logger.info(f"Table ingestion completed: {len(data)} row(s)")

            return SnowflakeData(
                data=data,
                row_count=len(data),
                columns=columns,
                table_name=table_name,
                database=database,
                schema=schema,
                metadata={"query": query},
            )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to ingest table: {e}")
            raise ProcessingError(f"Failed to ingest table: {e}") from e

    def ingest_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        batch_size: Optional[int] = None,
        **options,
    ) -> SnowflakeData:
        """
        Execute Snowflake query and ingest results.

        This method executes a SQL query and returns the results with
        optional batching for large result sets.

        Args:
            query: SQL query to execute
            params: Query parameters for parameterized queries (optional)
            batch_size: Batch size for result fetching (optional)
            **options: Additional query options

        Returns:
            SnowflakeData: Query results as SnowflakeData object

        Raises:
            ProcessingError: If query execution fails

        Example:
            >>> data = ingestor.ingest_query(
            ...     "SELECT * FROM SALES WHERE date > %(date)s",
            ...     params={"date": "2024-01-01"}
            ... )
        """
        tracking_id = self.progress_tracker.start_tracking(
            file="query",
            module="ingest",
            submodule="SnowflakeIngestor",
            message="Executing query...",
        )

        try:
            # Connect to Snowflake
            conn = self.connector.connect()

            self.logger.debug(f"Executing query: {query[:100]}...")

            # Execute query
            cursor = conn.cursor(DictCursor)

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Fetch results
            self.progress_tracker.update_tracking(
                tracking_id, message="Fetching results..."
            )

            if batch_size:
                # Fetch in batches
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

            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            cursor.close()

            # Convert to JSON-serializable format
            data = self._convert_rows(all_rows)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Query completed: {len(data)} rows",
            )

            self.logger.info(f"Query execution completed: {len(data)} row(s)")

            return SnowflakeData(
                data=data,
                row_count=len(data),
                columns=columns,
                query=query,
                metadata={"params": params} if params else {},
            )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            self.logger.error(f"Failed to execute query: {e}")
            raise ProcessingError(f"Failed to execute query: {e}") from e

    def get_table_schema(
        self,
        table_name: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get schema information for a Snowflake table.

        Args:
            table_name: Name of the table
            database: Database name (uses default if not provided)
            schema: Schema name (uses default if not provided)

        Returns:
            dict: Table schema information containing:
                - columns: List of column dictionaries with name, type, nullable
                - primary_keys: List of primary key column names (if any)

        Raises:
            ProcessingError: If schema retrieval fails
        """
        try:
            database = database or self.connector.database
            schema = schema or self.connector.schema
            
            # Validate required parameters
            if not database:
                raise ValidationError(
                    "Database name is required for schema introspection. "
                    "Provide via 'database' parameter or set default database in connector."
                )

            conn = self.connector.connect()

            # Get column information with escaped identifiers
            query = f"""
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT
            FROM {self._escape_identifier(database)}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{schema}'
              AND TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
            """

            cursor = conn.cursor(DictCursor)
            cursor.execute(query)
            columns = cursor.fetchall()
            cursor.close()

            # Get primary key information with escaped identifiers
            pk_query = f"""
            SELECT COLUMN_NAME
            FROM {self._escape_identifier(database)}.INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN {self._escape_identifier(database)}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
              ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE tc.TABLE_SCHEMA = '{schema}'
              AND tc.TABLE_NAME = '{table_name}'
              AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            """

            cursor = conn.cursor(DictCursor)
            cursor.execute(pk_query)
            pk_rows = cursor.fetchall()
            cursor.close()

            primary_keys = [row["COLUMN_NAME"] for row in pk_rows]

            column_info = [
                {
                    "name": col["COLUMN_NAME"],
                    "type": col["DATA_TYPE"],
                    "nullable": col["IS_NULLABLE"] == "YES",
                    "default": col["COLUMN_DEFAULT"],
                }
                for col in columns
            ]

            self.logger.debug(
                f"Retrieved schema for {table_name}: {len(column_info)} columns"
            )

            return {"columns": column_info, "primary_keys": primary_keys}

        except Exception as e:
            self.logger.error(f"Failed to get table schema: {e}")
            raise ProcessingError(f"Failed to get table schema: {e}") from e

    def list_tables(
        self, database: Optional[str] = None, schema: Optional[str] = None
    ) -> List[str]:
        """
        List all tables in a Snowflake database/schema.

        Args:
            database: Database name (uses default if not provided)
            schema: Schema name (uses default if not provided)

        Returns:
            list: List of table names

        Raises:
            ProcessingError: If listing fails
        """
        try:
            database = database or self.connector.database
            schema = schema or self.connector.schema
            
            # Validate required parameters
            if not database:
                raise ValidationError(
                    "Database name is required for listing tables. "
                    "Provide via 'database' parameter or set default database in connector."
                )

            conn = self.connector.connect()

            # Build query with escaped database identifier
            query = f"""
            SELECT TABLE_NAME
            FROM {self._escape_identifier(database)}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{schema}'
              AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """

            cursor = conn.cursor()
            cursor.execute(query)
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()

            self.logger.debug(f"Found {len(tables)} tables in {database}.{schema}")

            return tables

        except Exception as e:
            self.logger.error(f"Failed to list tables: {e}")
            raise ProcessingError(f"Failed to list tables: {e}") from e

    def export_as_documents(
        self, data: SnowflakeData, id_field: str = "id", text_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Convert Snowflake data to document format for Semantica processing.

        Args:
            data: SnowflakeData object to convert
            id_field: Field to use as document ID (default: 'id')
            text_fields: List of fields to combine into document text (optional)

        Returns:
            list: List of document dictionaries

        Example:
            >>> data = ingestor.ingest_table("CUSTOMERS")
            >>> documents = ingestor.export_as_documents(data, text_fields=["name", "description"])
        """
        documents = []

        for idx, row in enumerate(data.data):
            doc = {
                "id": str(row.get(id_field, idx)),
                "metadata": {
                    "source": "snowflake",
                    "table": data.table_name,
                    "database": data.database,
                    "schema": data.schema,
                },
            }

            # Combine text fields if specified
            if text_fields:
                text_parts = []
                for field in text_fields:
                    if field in row and row[field] is not None:
                        text_parts.append(str(row[field]))
                doc["text"] = " ".join(text_parts)
            else:
                # Use all string fields
                text_parts = []
                for key, value in row.items():
                    if isinstance(value, str):
                        text_parts.append(value)
                doc["text"] = " ".join(text_parts)

            # Add all row data to metadata
            doc["metadata"]["row_data"] = row

            documents.append(doc)

        self.logger.debug(f"Exported {len(documents)} documents")

        return documents

    def close(self):
        """Close Snowflake connection."""
        self.connector.disconnect()

    def _convert_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Snowflake rows to JSON-serializable format.

        Args:
            rows: List of row dictionaries from Snowflake

        Returns:
            list: Converted row dictionaries
        """
        converted = []

        for row in rows:
            converted_row = {}
            for key, value in row.items():
                # Convert datetime objects to ISO format strings
                if isinstance(value, datetime):
                    converted_row[key] = value.isoformat()
                # Convert bytes to string
                elif isinstance(value, bytes):
                    try:
                        converted_row[key] = value.decode("utf-8")
                    except UnicodeDecodeError:
                        converted_row[key] = str(value)
                # Keep other types as-is
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

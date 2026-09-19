"""Amazon Redshift ingestion module.

Pulls data from an Amazon Redshift cluster and flattens it into document
dicts that the pipeline can feed to ``GraphBuilder``.

Design notes
------------
Three classes, matching the Snowflake/Databricks/Salesforce ingestors:

- ``RedshiftData``: holds the rows returned by one table fetch or query
  (``data``, ``row_count``, ``columns``, ``table_name``, ``query``,
  ``database``, ``schema``, ``metadata``, ``ingested_at``).  No SDK
  dependency — always importable.

- ``RedshiftConnector``: manages the ``redshift_connector`` client
  lifecycle.  Raises ``ImportError`` at instantiation time when the
  optional ``redshift-connector`` package is absent.  Supports both
  password/native authentication and IAM-role authentication.

- ``RedshiftIngestor``: orchestrates ingestion.  Composes
  ``RedshiftConnector`` and exposes ``ingest_table``, ``ingest_query``,
  and ``_convert_rows``.  Schema-discovery (``get_table_schema``,
  ``list_tables``) and document export (``export_as_documents``) are
  implemented in later stages.

Authentication
--------------
**Password / native**::

    conn = RedshiftConnector(
        host="cluster.abc.us-east-1.redshift.amazonaws.com",
        database="dev",
        user="awsuser",
        password="secret",
    )

**IAM role (profile-based)**::

    conn = RedshiftConnector(
        host="cluster.abc.us-east-1.redshift.amazonaws.com",
        database="dev",
        iam=True,
        db_user="awsuser",
        cluster_identifier="my-cluster",
        profile="default",          # reads ~/.aws/credentials
    )

**IAM role (explicit credentials)**::

    conn = RedshiftConnector(
        host="cluster.abc.us-east-1.redshift.amazonaws.com",
        database="dev",
        iam=True,
        db_user="awsuser",
        cluster_identifier="my-cluster",
        region="us-east-1",
        access_key_id="AKIA...",
        secret_access_key="...",
        session_token="...",        # only for temporary credentials
    )

SDK parameter note
------------------
The secret-access-key parameter accepted by ``redshift_connector.connect()``
is named ``secret_access_key`` (confirmed from the official SDK README
example).  The AWS docs configuration table lists it as
``secret_access_key_id``, which appears to be a documentation error;
the README connect() example — the authoritative usage reference — uses
``secret_access_key``.

SQL safety
----------
Table/schema/database names are validated with
:func:`~semantica.ingest.db_ingestor._validate_sql_identifier` (must
match ``^[A-Za-z_][A-Za-z0-9_]*$``) and then escaped with double-quotes
before being interpolated into query strings.  ``WHERE`` and
``ORDER BY`` fragments are checked with
:func:`~semantica.ingest.db_ingestor._validate_sql_fragment` which
blocks statement separators, ``UNION``, DML/DDL keywords, comment
sequences, and time-based blind-injection oracles.

Optional dependency
-------------------
Install the SDK before using ``RedshiftConnector`` or
``RedshiftIngestor``::

    pip install "semantica[db-redshift]"

or directly::

    pip install redshift-connector>=2.0.0

The top-level ``import semantica.ingest`` never imports
``redshift_connector`` eagerly; the SDK is loaded only when this module
is first accessed through the lazy-export mechanism in ``__init__.py``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

# Re-use the repository's established SQL-safety helpers from db_ingestor
# rather than duplicating them.  This import is always available (db_ingestor
# has no optional dependency) and keeps validation logic in one place.
from .db_ingestor import _validate_sql_fragment, _validate_sql_identifier

# ---------------------------------------------------------------------------
# Optional-dependency guard
# ---------------------------------------------------------------------------
# The module always imports cleanly.  The sentinel fires at instantiation
# time (inside RedshiftConnector.__init__) so that:
#   - ``from semantica.ingest import RedshiftData`` succeeds with no SDK
#   - ``from semantica.ingest import RedshiftIngestor`` succeeds (lazy)
#   - ``RedshiftConnector(...)`` raises a clear ImportError when SDK absent
# ---------------------------------------------------------------------------
try:
    import redshift_connector as _redshift_connector

    REDSHIFT_AVAILABLE = True
except (ImportError, OSError):
    _redshift_connector = None  # type: ignore[assignment]
    REDSHIFT_AVAILABLE = False

__all__ = [
    "RedshiftData",
    "RedshiftConnector",
    "RedshiftIngestor",
]

_logger = get_logger("redshift_ingestor")

# ---------------------------------------------------------------------------
# RedshiftData
# ---------------------------------------------------------------------------


@dataclass
class RedshiftData:
    """Records returned from an Amazon Redshift table or query.

    Attributes:
        data: List of row dictionaries.
        row_count: Number of rows in ``data``.
        columns: Ordered list of column names present in ``data``.
        table_name: Source table name, or ``None`` for raw-query results.
        query: SQL query string used to produce these rows, or ``None``.
        database: Redshift database name used for the ingestion.
        schema: Redshift schema name used for the ingestion.
        metadata: Arbitrary extra metadata (e.g. ``{"query": sql}``).
        ingested_at: Timestamp recorded when this object was created.
    """

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    table_name: Optional[str] = None
    query: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# RedshiftConnector
# ---------------------------------------------------------------------------


class RedshiftConnector:
    """Manages the ``redshift_connector`` client lifecycle.

    Responsibilities:

    * Reads credentials from constructor arguments, falling back to
      environment variables with ``REDSHIFT_*`` names.
    * Validates that a usable authentication path is configured *before*
      any network call is made.
    * Exposes :meth:`connect`, :meth:`disconnect`, and
      :meth:`test_connection` so the ingestor (and tests) can control the
      connection lifecycle explicitly.
    * **Connection reuse**: :meth:`connect` returns the existing connection
      when one is already open, preventing duplicate round-trips and
      resource leaks when used as a context manager.

    Supported Authentication Modes
    --------------------------------
    **Password / native** — ``host``, ``database``, ``user``, ``password``
    are all required.  ``ssl`` defaults to ``True`` and ``timeout`` is
    optional::

        connector = RedshiftConnector(
            host="cluster.abc.us-east-1.redshift.amazonaws.com",
            database="dev",
            user="awsuser",
            password="secret",
        )

    **IAM role** — set ``iam=True``; ``host``, ``database``, ``db_user``,
    and ``cluster_identifier`` are required.  AWS credentials are resolved
    in order: explicit kwargs → profile → standard AWS environment variables
    (``AWS_ACCESS_KEY_ID`` etc.) / instance-profile metadata::

        connector = RedshiftConnector(
            host="cluster.abc.us-east-1.redshift.amazonaws.com",
            database="dev",
            iam=True,
            db_user="awsuser",
            cluster_identifier="my-cluster",
            profile="default",   # or access_key_id/secret_access_key/region
        )

    Environment Variables
    ----------------------
    Every constructor parameter has an ``REDSHIFT_*`` environment-variable
    fallback:

    * ``REDSHIFT_HOST``
    * ``REDSHIFT_DATABASE``
    * ``REDSHIFT_USER``
    * ``REDSHIFT_PASSWORD``
    * ``REDSHIFT_PORT``             (default: ``5439``)
    * ``REDSHIFT_DB_USER``
    * ``REDSHIFT_CLUSTER_IDENTIFIER``
    * ``REDSHIFT_REGION``
    * ``REDSHIFT_PROFILE``
    * ``REDSHIFT_ACCESS_KEY_ID``
    * ``REDSHIFT_SECRET_ACCESS_KEY``
    * ``REDSHIFT_SESSION_TOKEN``

    Raises:
        ImportError: When ``redshift-connector`` is not installed.
        ValidationError: When required credentials are incomplete.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        # IAM-role authentication
        iam: bool = False,
        db_user: Optional[str] = None,
        cluster_identifier: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        # TLS / misc
        ssl: bool = True,
        timeout: Optional[int] = None,
        **config: Any,
    ) -> None:
        """Initialise the connector and validate credentials.

        Args:
            host: Redshift cluster endpoint hostname.
            port: Redshift port. Defaults to ``5439`` (or
                ``REDSHIFT_PORT`` env var).
            database: Target database name.
            user: Database username (password auth). For IAM auth pass
                an empty string — the SDK requires the kwarg but ignores
                its value.
            password: Database password (password auth). For IAM auth
                pass an empty string.
            iam: Enable IAM-role authentication.
            db_user: Redshift database user to assume (IAM auth).
            cluster_identifier: Redshift cluster identifier (IAM auth).
            region: AWS region where the cluster is located (IAM auth).
            profile: AWS credentials-file profile name (IAM auth).
            access_key_id: Explicit AWS access key (IAM auth).
            secret_access_key: Explicit AWS secret access key (IAM auth).
            session_token: Temporary AWS session token (IAM auth).
            ssl: Enable SSL/TLS. Defaults to ``True``.
            timeout: Connection timeout in seconds.
            **config: Extra keyword arguments forwarded verbatim to
                ``redshift_connector.connect()``.

        Raises:
            ImportError: When ``redshift-connector`` is not installed.
            ValidationError: When required credentials are incomplete.
        """
        if not REDSHIFT_AVAILABLE:
            raise ImportError(
                "redshift-connector is required for RedshiftConnector. "
                'Install it with: pip install "semantica[db-redshift]"'
            )

        self.logger = _logger

        # ------------------------------------------------------------------
        # Resolve credentials — explicit args override env vars.
        # Secrets (password, access keys, session token) are stored under
        # private attributes and are NEVER included in log messages.
        # ------------------------------------------------------------------
        self.host: Optional[str] = host or os.getenv("REDSHIFT_HOST")
        self.database: Optional[str] = database or os.getenv("REDSHIFT_DATABASE")
        self.user: Optional[str] = user or os.getenv("REDSHIFT_USER")
        self._password: Optional[str] = password or os.getenv("REDSHIFT_PASSWORD")

        # Port: explicit kwarg → env var → default 5439
        _port_env = os.getenv("REDSHIFT_PORT")
        if port is not None:
            self.port: int = port
        elif _port_env is not None:
            try:
                self.port = int(_port_env)
            except ValueError:
                raise ValidationError(
                    f"REDSHIFT_PORT must be an integer, got {_port_env!r}."
                )
        else:
            self.port = 5439

        self.iam: bool = iam
        self.db_user: Optional[str] = db_user or os.getenv("REDSHIFT_DB_USER")
        self.cluster_identifier: Optional[str] = cluster_identifier or os.getenv(
            "REDSHIFT_CLUSTER_IDENTIFIER"
        )
        self.region: Optional[str] = region or os.getenv("REDSHIFT_REGION")
        self.profile: Optional[str] = profile or os.getenv("REDSHIFT_PROFILE")
        self._access_key_id: Optional[str] = access_key_id or os.getenv(
            "REDSHIFT_ACCESS_KEY_ID"
        )
        self._secret_access_key: Optional[str] = secret_access_key or os.getenv(
            "REDSHIFT_SECRET_ACCESS_KEY"
        )
        self._session_token: Optional[str] = session_token or os.getenv(
            "REDSHIFT_SESSION_TOKEN"
        )
        self.ssl: bool = ssl
        self.timeout: Optional[int] = timeout
        self._extra_config: Dict[str, Any] = config

        # Internal connection — None until connect() is called.
        self._connection: Optional[Any] = None

        # Validate credentials before any network call.
        self._validate_auth()

        self.logger.debug(
            "Redshift connector initialised (host=%s, database=%s, iam=%s)",
            self.host,
            self.database,
            self.iam,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_auth(self) -> None:
        """Raise :class:`~semantica.utils.exceptions.ValidationError` when
        the configured credentials are insufficient to attempt a connection.

        Validates before any network call so failures are immediate and
        never leak partial state.

        Password mode requires: ``host``, ``database``, ``user``,
        ``password``.

        IAM mode requires: ``host``, ``database``, ``db_user``,
        ``cluster_identifier``.  AWS credential material (``profile`` or
        ``access_key_id``/``secret_access_key``) is optional when the SDK
        can fall back to the standard AWS credential chain (env vars,
        instance profile, etc.).

        Raises:
            ValidationError: When a required credential is absent.
        """
        if not self.host:
            raise ValidationError(
                "Redshift host is required. "
                "Provide via 'host' or REDSHIFT_HOST environment variable."
            )
        if not self.database:
            raise ValidationError(
                "Redshift database is required. "
                "Provide via 'database' or REDSHIFT_DATABASE environment variable."
            )

        if self.iam:
            if not self.db_user:
                raise ValidationError(
                    "Redshift IAM authentication requires 'db_user'. "
                    "Provide via 'db_user' or REDSHIFT_DB_USER environment variable."
                )
            if not self.cluster_identifier:
                raise ValidationError(
                    "Redshift IAM authentication requires 'cluster_identifier'. "
                    "Provide via 'cluster_identifier' or "
                    "REDSHIFT_CLUSTER_IDENTIFIER environment variable."
                )
        else:
            # Password / native authentication.
            if not self.user:
                raise ValidationError(
                    "Redshift password authentication requires 'user'. "
                    "Provide via 'user' or REDSHIFT_USER environment variable."
                )
            if not self._password:
                raise ValidationError(
                    "Redshift password authentication requires 'password'. "
                    "Provide via 'password' or REDSHIFT_PASSWORD environment variable."
                )

    def _build_connect_kwargs(self) -> Dict[str, Any]:
        """Assemble keyword arguments for ``redshift_connector.connect()``.

        Credentials are assembled here and nowhere else; they are not
        logged.

        Returns:
            Keyword arguments dict ready for
            ``redshift_connector.connect(**kwargs)``.
        """
        kwargs: Dict[str, Any] = {
            "host": self.host,
            "database": self.database,
            "port": self.port,
            "ssl": self.ssl,
        }

        if self.timeout is not None:
            kwargs["timeout"] = self.timeout

        if self.iam:
            # IAM auth — the SDK calls GetClusterCredentials via boto3 to
            # obtain a temporary database password.  ``user`` and ``password``
            # must be present as kwargs (SDK requirement) but are ignored
            # when iam=True; pass empty strings to satisfy the signature.
            kwargs["iam"] = True
            kwargs["user"] = ""
            kwargs["password"] = ""
            kwargs["db_user"] = self.db_user
            kwargs["cluster_identifier"] = self.cluster_identifier

            if self.region:
                kwargs["region"] = self.region
            if self.profile:
                kwargs["profile"] = self.profile
            if self._access_key_id:
                kwargs["access_key_id"] = self._access_key_id
            if self._secret_access_key:
                kwargs["secret_access_key"] = self._secret_access_key
            if self._session_token:
                kwargs["session_token"] = self._session_token
        else:
            # Password / native authentication.
            kwargs["user"] = self.user
            kwargs["password"] = self._password

        # Forward any extra config supplied by the caller.
        kwargs.update(self._extra_config)
        return kwargs

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def connection(self) -> Optional[Any]:
        """The active ``redshift_connector`` connection, or ``None``."""
        return self._connection

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> Any:
        """Create and return a ``redshift_connector`` connection.

        If a connection is already open, returns it immediately without
        creating a new one (connection-reuse semantics matching the
        Salesforce and Databricks connectors).

        Returns:
            The ``redshift_connector`` connection object.

        Raises:
            ProcessingError: If the connection attempt fails for any
                reason (network error, bad credentials, SDK error).
                Passwords and secret keys are never included in the
                raised message.
        """
        if self._connection is not None:
            return self._connection

        try:
            kwargs = self._build_connect_kwargs()
            self._connection = _redshift_connector.connect(**kwargs)
            self.logger.info(
                "Connected to Redshift: host=%s database=%s iam=%s",
                self.host,
                self.database,
                self.iam,
            )
            return self._connection

        except Exception as exc:
            # Ensure no partial connection reference leaks out.
            self._connection = None
            # Log only the exception type — never the message, which may
            # contain credential material from the SDK or AWS SDK.
            self.logger.error(
                "Failed to connect to Redshift: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to connect to Redshift: {type(exc).__name__}"
            ) from exc

    def disconnect(self) -> None:
        """Close the connection and release the reference.

        Safe to call when already disconnected — subsequent calls are
        no-ops.
        """
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._connection = None
            self.logger.info("Disconnected from Redshift.")

    def test_connection(self) -> bool:
        """Verify connectivity by opening a transient connection.

        Opens a fresh connection (or reuses an existing one), executes
        ``SELECT 1`` to confirm the session is live, then closes the
        connection if it was opened by this call.

        Returns:
            ``True`` if the ping succeeds, ``False`` for any failure.
        """
        already_connected = self._connection is not None
        try:
            conn = self.connect()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()
            return True
        except Exception as exc:
            self.logger.debug(
                "Redshift connection test failed: %s", type(exc).__name__
            )
            return False
        finally:
            if not already_connected:
                self.disconnect()


# ---------------------------------------------------------------------------
# RedshiftIngestor
# ---------------------------------------------------------------------------


class RedshiftIngestor:
    """Amazon Redshift data ingestor for the Semantica framework.

    Wraps :class:`RedshiftConnector` and exposes table and query
    ingestion, row-to-dict conversion, and SQL-safe query construction.

    Schema-discovery methods (``get_table_schema``, ``list_tables``) and
    document export (``export_as_documents``) are implemented in later
    stages.

    Args:
        host: Redshift cluster endpoint hostname.
        port: Redshift port (default: ``5439``).
        database: Target database name.
        user: Database username (password auth).
        password: Database password (password auth).
        schema: Default schema (default: ``"public"``).
        iam: Use IAM-role authentication when ``True``.
        db_user: Redshift database user to assume (IAM auth).
        cluster_identifier: Redshift cluster identifier (IAM auth).
        region: AWS region (IAM auth).
        profile: AWS credentials-file profile name (IAM auth).
        access_key_id: Explicit AWS access key (IAM auth).
        secret_access_key: Explicit AWS secret access key (IAM auth).
        session_token: Temporary AWS session token (IAM auth).
        ssl: Enable SSL/TLS. Defaults to ``True``.
        timeout: Connection timeout in seconds.
        connector: An existing :class:`RedshiftConnector` to reuse.
        config: Optional extra configuration dict forwarded to the
            connector.
        **kwargs: Additional keyword arguments merged into ``config``.

    Raises:
        ImportError: When ``redshift-connector`` is not installed.
        ValidationError: When required credentials are incomplete.

    Example::

        import os
        from semantica.ingest import RedshiftIngestor

        # Password authentication
        ingestor = RedshiftIngestor(
            host=os.getenv("REDSHIFT_HOST"),
            database=os.getenv("REDSHIFT_DATABASE"),
            user=os.getenv("REDSHIFT_USER"),
            password=os.getenv("REDSHIFT_PASSWORD"),
        )

        # Context manager — preferred for production use
        with RedshiftIngestor(
            host=os.getenv("REDSHIFT_HOST"),
            database=os.getenv("REDSHIFT_DATABASE"),
            user=os.getenv("REDSHIFT_USER"),
            password=os.getenv("REDSHIFT_PASSWORD"),
        ) as ing:
            data = ing.ingest_table("orders", schema="sales", limit=1000)
            query_data = ing.ingest_query(
                "SELECT id, total FROM sales.orders WHERE status = %s",
                params=("shipped",),
            )
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        schema: Optional[str] = None,
        iam: bool = False,
        db_user: Optional[str] = None,
        cluster_identifier: Optional[str] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        ssl: bool = True,
        timeout: Optional[int] = None,
        connector: Optional[RedshiftConnector] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = _logger

        self.config: Dict[str, Any] = config or {}
        self.config.update(kwargs)

        # Instantiate a connector unless one is supplied.
        # ImportError propagates when SDK is absent; ValidationError when
        # credentials are incomplete.
        self.connector: RedshiftConnector = connector or RedshiftConnector(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            iam=iam,
            db_user=db_user,
            cluster_identifier=cluster_identifier,
            region=region,
            profile=profile,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            ssl=ssl,
            timeout=timeout,
            **self.config,
        )

        self.schema: str = schema or os.getenv("REDSHIFT_SCHEMA", "public")

        # Progress tracker — consistent with all other ingestors.
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("Redshift ingestor initialised.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "RedshiftIngestor":
        """Open the Redshift connection on context entry."""
        self.connector.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Close the Redshift connection on context exit."""
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Disconnect from Redshift and release the connection."""
        self.connector.disconnect()

    # ------------------------------------------------------------------
    # SQL-identity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        """Escape a SQL identifier using double-quote quoting.

        Redshift (PostgreSQL-compatible) uses ``"identifier"`` quoting.
        Internal double-quote characters are doubled (``""``).

        Args:
            identifier: Already-validated identifier string.

        Returns:
            Double-quoted, safely escaped identifier.
        """
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    @staticmethod
    def _build_table_ref(
        table_name: str,
        schema: Optional[str],
        database: Optional[str],
    ) -> str:
        """Build a fully-qualified, double-quote-escaped table reference.

        Components that are ``None`` or empty are omitted.

        Args:
            table_name: Already-validated table name.
            schema: Optional schema name (already validated).
            database: Optional database name (already validated).

        Returns:
            SQL table reference such as ``"mydb"."myschema"."mytable"``
            or just ``"mytable"``.
        """
        parts = [
            RedshiftIngestor._escape_identifier(part)
            for part in (database, schema, table_name)
            if part
        ]
        return ".".join(parts)

    # ------------------------------------------------------------------
    # Ingestion — ingest_table
    # ------------------------------------------------------------------

    def ingest_table(
        self,
        table_name: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        **options: Any,
    ) -> RedshiftData:
        """Fetch rows from a Redshift table.

        Builds a ``SELECT * FROM <table>`` query with optional
        ``WHERE``, ``ORDER BY``, ``LIMIT``, and ``OFFSET`` clauses and
        executes it against the Redshift cluster.

        All identifier components (``table_name``, ``schema``,
        ``database``) are validated with
        :func:`~semantica.ingest.db_ingestor._validate_sql_identifier`
        and then escaped with double-quotes before interpolation.
        ``WHERE`` and ``ORDER BY`` fragments are validated with
        :func:`~semantica.ingest.db_ingestor._validate_sql_fragment`.
        Validation is performed before opening any connection so
        malformed inputs fail fast without a network round-trip.

        Connection lifecycle mirrors the Databricks/Snowflake pattern:
        if the ingestor is used as a context manager the existing
        connection is reused; standalone calls open a transient
        connection and close it in a ``finally`` block.

        Args:
            table_name: Name of the Redshift table to query.
            database: Override database name (defaults to the connector's
                configured database).
            schema: Override schema name (defaults to the ingestor's
                default ``schema`` attribute).
            limit: Maximum number of rows to return.
            offset: Number of leading rows to skip.
            where: SQL ``WHERE`` clause fragment (without the
                ``WHERE`` keyword).  Trusted / operator input only —
                do not pass raw end-user text.
            order_by: SQL ``ORDER BY`` clause fragment (without the
                keyword).  Same trust requirement.
            **options: Reserved for future use.

        Returns:
            :class:`RedshiftData` with ``data``, ``row_count``,
            ``columns``, ``table_name``, ``database``, ``schema``,
            ``query``, and ``metadata`` populated.

        Raises:
            ValidationError: If any identifier or SQL fragment fails
                safety validation.
            ProcessingError: If the query fails or the connection
                cannot be established.
        """
        effective_schema = schema or self.schema
        effective_database = database or self.connector.database

        # ------------------------------------------------------------------
        # Validate all identifiers and SQL fragments BEFORE connecting so
        # invalid inputs are rejected cheaply and without any network call.
        # ------------------------------------------------------------------
        _validate_sql_identifier(table_name, "table_name")
        if effective_schema:
            _validate_sql_identifier(effective_schema, "schema")
        if effective_database:
            _validate_sql_identifier(effective_database, "database")
        if where:
            _validate_sql_fragment(where, "where")
        if order_by:
            _validate_sql_fragment(order_by, "order_by")

        table_ref = self._build_table_ref(
            table_name, effective_schema, effective_database
        )

        tracking_id = self.progress_tracker.start_tracking(
            file=table_ref,
            module="ingest",
            submodule="RedshiftIngestor",
            message=f"Table: {table_ref}",
        )

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()

            # Capture the previous autocommit state so we can restore it
            # when the connection was already open (caller-owned).  We only
            # need to restore it in that case; transient connections are
            # closed in the finally block anyway.
            _prev_autocommit = conn.autocommit if already_connected else None
            try:
                # Enable autocommit for read-only ingestion to avoid leaving
                # idle transactions open on the server (Redshift/Postgres
                # DB-API starts a transaction automatically otherwise).
                conn.autocommit = True

                query = f"SELECT * FROM {table_ref}"

                if where:
                    query += f" WHERE {where}"
                if order_by:
                    query += f" ORDER BY {order_by}"
                if limit is not None:
                    query += f" LIMIT {int(limit)}"
                if offset is not None:
                    query += f" OFFSET {int(offset)}"

                self.logger.debug("Executing ingest_table query: %s", query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Executing query..."
                )

                cursor = conn.cursor()
                try:
                    cursor.execute(query)

                    self.progress_tracker.update_tracking(
                        tracking_id, message="Fetching results..."
                    )

                    columns, data = self._fetch_all(cursor)
                finally:
                    cursor.close()

            finally:
                if already_connected and _prev_autocommit is not None:
                    conn.autocommit = _prev_autocommit
                if not already_connected:
                    self.connector.disconnect()

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {len(data)} rows",
            )
            self.logger.info(
                "ingest_table completed: %s — %d row(s)", table_ref, len(data)
            )

            return RedshiftData(
                data=data,
                row_count=len(data),
                columns=columns,
                table_name=table_name,
                database=effective_database,
                schema=effective_schema,
                query=query,
                metadata={"query": query},
            )

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Query failed"
            )
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error(
                "Failed to ingest table %s: %s", table_name, type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to ingest Redshift table '{table_name}': "
                f"{type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Ingestion — ingest_query
    # ------------------------------------------------------------------

    def ingest_query(
        self,
        query: str,
        params: Optional[Any] = None,
        batch_size: Optional[int] = None,
        **options: Any,
    ) -> RedshiftData:
        """Execute a raw SQL query and return all matching rows.

        Passes the query verbatim to the Redshift cursor.  The caller
        is responsible for correctness and safety of the query string.
        Use ``params`` for any user-supplied values rather than
        interpolating them directly.

        ``redshift_connector`` cursors support DB-API 2.0 parameter
        binding: pass a tuple or list for positional ``%s`` placeholders,
        or a dict for named ``%(name)s`` style, depending on the cursor's
        ``paramstyle`` setting (default: ``"format"``).

        When ``batch_size`` is provided the rows are fetched in repeated
        ``fetchmany(batch_size)`` calls until the result set is exhausted.

        Connection lifecycle mirrors :meth:`ingest_table`: standalone
        calls open and close a transient connection; calls made inside a
        context manager reuse the open connection.

        Args:
            query: Complete SQL query string.
            params: Query parameters forwarded to
                ``cursor.execute(query, params)``.  Accepts any form
                the ``redshift_connector`` cursor accepts (tuple, list,
                dict, or ``None``).
            batch_size: If set, rows are fetched in batches of this
                size using ``cursor.fetchmany(batch_size)``.
            **options: Reserved for future use.

        Returns:
            :class:`RedshiftData` with ``data``, ``row_count``,
            ``columns``, and ``query`` populated.

        Raises:
            ProcessingError: If the query fails or the connection
                cannot be established.
        """
        tracking_id = self.progress_tracker.start_tracking(
            file="query",
            module="ingest",
            submodule="RedshiftIngestor",
            message="Executing query...",
        )

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()

            _prev_autocommit = conn.autocommit if already_connected else None
            try:
                # Enable autocommit for read-only ingestion.
                conn.autocommit = True

                self.logger.debug(
                    "Executing ingest_query: %s", query[:200]
                )

                self.progress_tracker.update_tracking(
                    tracking_id, message="Executing query..."
                )

                cursor = conn.cursor()
                try:
                    if params is not None:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)

                    self.progress_tracker.update_tracking(
                        tracking_id, message="Fetching results..."
                    )

                    columns = (
                        self._disambiguate_columns(
                            [desc[0] for desc in cursor.description]
                        )
                        if cursor.description
                        else []
                    )

                    if batch_size:
                        # Process each batch immediately so raw tuples from
                        # the previous batch are eligible for GC before the
                        # next fetch.  This keeps live memory proportional to
                        # one batch of raw rows plus the accumulated converted
                        # results, rather than two full copies of all rows.
                        data: List[Dict[str, Any]] = []
                        while True:
                            batch = cursor.fetchmany(batch_size)
                            if not batch:
                                break
                            batch_dicts = self._make_row_dicts(columns, batch)
                            data.extend(self._convert_rows(batch_dicts))
                            self.progress_tracker.update_tracking(
                                tracking_id,
                                message=f"Fetched {len(data)} rows...",
                            )
                    else:
                        raw_rows = cursor.fetchall()
                        row_dicts = self._make_row_dicts(columns, raw_rows)
                        data = self._convert_rows(row_dicts)

                finally:
                    cursor.close()

            finally:
                if already_connected and _prev_autocommit is not None:
                    conn.autocommit = _prev_autocommit
                if not already_connected:
                    self.connector.disconnect()

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Query completed: {len(data)} rows",
            )
            self.logger.info(
                "ingest_query completed: %d row(s)", len(data)
            )

            return RedshiftData(
                data=data,
                row_count=len(data),
                columns=columns,
                query=query,
                metadata={"params": params} if params is not None else {},
            )

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="Query failed"
            )
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error(
                "Failed to execute query: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to execute Redshift query: {type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Schema discovery
    # ------------------------------------------------------------------

    def get_table_schema(
        self,
        table_name: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return column metadata and primary-key information for a table.

        Queries ``information_schema.COLUMNS`` for column order, names, data
        types, and nullability, and ``information_schema.TABLE_CONSTRAINTS``
        joined with ``information_schema.KEY_COLUMN_USAGE`` for primary-key
        column names.

        ``TABLE_SCHEMA`` and ``TABLE_NAME`` filter values are passed as
        DB-API ``%s`` parameters so they are never interpolated directly into
        the SQL string.  The optional *database* prefix is double-quote-escaped
        via :meth:`_escape_identifier` after passing through
        :func:`~semantica.ingest.db_ingestor._validate_sql_identifier`.

        Args:
            table_name: Name of the Redshift table to introspect.
            database: Override database name.  Defaults to the connector's
                configured database.
            schema: Override schema name.  Defaults to the ingestor's
                ``schema`` attribute (``"public"`` unless changed).

        Returns:
            A dictionary with two keys:

            ``"columns"``
                Ordered list of column dicts, each containing
                ``"name"``, ``"type"``, and ``"nullable"`` (``bool``).

            ``"primary_keys"``
                List of column-name strings that form the primary key, or
                an empty list when no primary key is defined.

        Raises:
            ValidationError: If *table_name*, *database*, or *schema* fails
                identifier validation.
            ProcessingError: If the metadata query fails.
        """
        effective_schema = schema or self.schema
        effective_database = database or self.connector.database

        # Validate identifiers before connecting.
        _validate_sql_identifier(table_name, "table_name")
        if effective_schema:
            _validate_sql_identifier(effective_schema, "schema")
        if effective_database:
            _validate_sql_identifier(effective_database, "database")

        # Build the information_schema reference, qualified by database when
        # available (Redshift allows cross-database queries via the database
        # prefix on information_schema).
        if effective_database:
            info_schema = (
                f"{self._escape_identifier(effective_database)}.information_schema"
            )
        else:
            info_schema = "information_schema"

        # Column query — TABLE_SCHEMA and TABLE_NAME are %s params (values,
        # not identifiers) so they are never interpolated into the SQL string.
        col_query = f"""
            SELECT
                column_name,
                data_type,
                is_nullable
            FROM {info_schema}.columns
            WHERE table_schema = %s
              AND table_name   = %s
            ORDER BY ordinal_position
        """

        # Primary-key query — same parameterised approach.
        pk_query = f"""
            SELECT kcu.column_name
            FROM {info_schema}.table_constraints  tc
            JOIN {info_schema}.key_column_usage   kcu
              ON tc.constraint_name  = kcu.constraint_name
             AND tc.table_schema     = kcu.table_schema
             AND tc.table_name       = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema    = %s
              AND tc.table_name      = %s
            ORDER BY kcu.ordinal_position
        """

        params = (effective_schema, table_name)

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()

            _prev_autocommit = conn.autocommit if already_connected else None
            try:
                conn.autocommit = True

                # --- columns ---
                cursor = conn.cursor()
                try:
                    cursor.execute(col_query, params)
                    col_rows = cursor.fetchall()
                    col_names = [desc[0] for desc in cursor.description]
                finally:
                    cursor.close()

                col_dicts = [dict(zip(col_names, row)) for row in col_rows]
                columns = [
                    {
                        "name": row["column_name"],
                        "type": row["data_type"],
                        "nullable": str(row["is_nullable"]).upper() == "YES",
                    }
                    for row in col_dicts
                ]

                # --- primary keys ---
                cursor = conn.cursor()
                try:
                    cursor.execute(pk_query, params)
                    pk_rows = cursor.fetchall()
                finally:
                    cursor.close()

                primary_keys = [row[0] for row in pk_rows]

            finally:
                if already_connected and _prev_autocommit is not None:
                    conn.autocommit = _prev_autocommit
                if not already_connected:
                    self.connector.disconnect()

            self.logger.debug(
                "get_table_schema: %s — %d column(s), %d PK(s)",
                table_name,
                len(columns),
                len(primary_keys),
            )

            return {"columns": columns, "primary_keys": primary_keys}

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to get schema for %s: %s", table_name, type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to get schema for Redshift table '{table_name}': "
                f"{type(exc).__name__}"
            ) from exc

    def list_tables(
        self,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[str]:
        """Return the names of all base tables in the specified schema.

        Queries ``information_schema.tables`` filtering by
        ``table_type = 'BASE TABLE'`` so views are excluded, which matches
        the Snowflake connector's convention.  The *schema* filter value is
        passed as a ``%s`` parameter; the optional *database* prefix is
        validated and escaped as an identifier before interpolation.

        Args:
            database: Override database name.  Defaults to the connector's
                configured database.
            schema: Override schema name.  Defaults to the ingestor's
                ``schema`` attribute (``"public"``).

        Returns:
            Sorted list of table-name strings, or an empty list when the
            schema contains no base tables.

        Raises:
            ValidationError: If *database* or *schema* fails identifier
                validation.
            ProcessingError: If the catalog query fails.
        """
        effective_schema = schema or self.schema
        effective_database = database or self.connector.database

        if effective_schema:
            _validate_sql_identifier(effective_schema, "schema")
        if effective_database:
            _validate_sql_identifier(effective_database, "database")

        if effective_database:
            info_schema = (
                f"{self._escape_identifier(effective_database)}.information_schema"
            )
        else:
            info_schema = "information_schema"

        query = f"""
            SELECT table_name
            FROM {info_schema}.tables
            WHERE table_schema = %s
              AND table_type   = 'BASE TABLE'
            ORDER BY table_name
        """

        try:
            already_connected = self.connector.connection is not None
            conn = self.connector.connect()

            _prev_autocommit = conn.autocommit if already_connected else None
            try:
                conn.autocommit = True

                cursor = conn.cursor()
                try:
                    cursor.execute(query, (effective_schema,))
                    rows = cursor.fetchall()
                finally:
                    cursor.close()

            finally:
                if already_connected and _prev_autocommit is not None:
                    conn.autocommit = _prev_autocommit
                if not already_connected:
                    self.connector.disconnect()

            tables = [row[0] for row in rows]
            self.logger.debug(
                "list_tables: %d table(s) in schema '%s'",
                len(tables),
                effective_schema,
            )
            return tables

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to list tables: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to list Redshift tables: {type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Document export
    # ------------------------------------------------------------------

    def export_as_documents(
        self,
        data: RedshiftData,
        id_field: str = "id",
        text_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert :class:`RedshiftData` to the Semantica document format.

        Produces the same ``{"id", "text", "metadata"}`` shape used by
        :class:`~semantica.ingest.snowflake_ingestor.SnowflakeIngestor` and
        :class:`~semantica.ingest.databricks_ingestor.DatabricksIngestor`,
        making :class:`RedshiftData` directly usable with
        :class:`~semantica.kg.graph_builder.GraphBuilder`.

        **ID resolution**
            ``str(row.get(id_field, idx))`` — uses the row-index integer as a
            deterministic fallback when the *id_field* key is absent, cast to
            a string.  This matches the Snowflake/Databricks convention exactly.

        **Text composition**
            * When *text_fields* is provided: only those fields are used; each
              non-``None`` value is converted to a string and joined with a
              single space.
            * When *text_fields* is ``None``: only ``str``-typed values are
              joined (integers, floats, booleans, and ``None`` are excluded).
              This matches the Snowflake/Databricks default behavior.

        **Metadata**
            ``{"source": "redshift", "table": ..., "database": ...,
            "schema": ..., "row_data": <full cleaned row dict>}``

        Args:
            data: A :class:`RedshiftData` object returned by
                :meth:`ingest_table` or :meth:`ingest_query`.
            id_field: Row field to use as the document ``"id"``.  Defaults
                to ``"id"``.
            text_fields: List of field names whose values form the document
                ``"text"``.  When ``None`` all string-typed field values are
                joined.

        Returns:
            List of document dictionaries::

                [
                    {
                        "id": str,
                        "text": str,
                        "metadata": {
                            "source": "redshift",
                            "table": str | None,
                            "database": str | None,
                            "schema": str | None,
                            "row_data": dict,
                        },
                    },
                    ...
                ]
        """
        documents: List[Dict[str, Any]] = []

        for idx, row in enumerate(data.data):
            doc: Dict[str, Any] = {
                "id": str(row.get(id_field, idx)),
                "metadata": {
                    "source": "redshift",
                    "table": data.table_name,
                    "database": data.database,
                    "schema": data.schema,
                },
            }

            if text_fields:
                text_parts = [
                    str(row[f])
                    for f in text_fields
                    if f in row and row[f] is not None
                ]
            else:
                text_parts = [
                    value
                    for value in row.values()
                    if isinstance(value, str)
                ]

            doc["text"] = " ".join(text_parts)
            doc["metadata"]["row_data"] = row

            documents.append(doc)

        self.logger.debug(
            "export_as_documents: exported %d document(s)", len(documents)
        )
        return documents

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _disambiguate_columns(columns: List[str]) -> List[str]:
        """Return a new column-name list with duplicate labels made unique.

        When the cursor reports duplicate column labels (e.g. from a JOIN
        that selects the same column name from two tables), a plain
        ``dict(zip(columns, row))`` silently drops every value except the
        last one for each repeated key.

        This method appends a ``_1``, ``_2``, … suffix to each duplicate
        occurrence (the *first* occurrence keeps the original name) so that
        all values are retained in the resulting dict.

        Args:
            columns: Raw column-name list from ``cursor.description``.

        Returns:
            A new list of the same length where every name is unique.
        """
        seen: Dict[str, int] = {}
        result: List[str] = []
        for name in columns:
            if name not in seen:
                seen[name] = 0
                result.append(name)
            else:
                seen[name] += 1
                result.append(f"{name}_{seen[name]}")
        return result

    def _make_row_dicts(
        self,
        columns: List[str],
        rows: List[Any],
    ) -> List[Dict[str, Any]]:
        """Zip *rows* (tuples from the cursor) with *columns* into dicts.

        Duplicate column labels are disambiguated before zipping so that no
        value is silently discarded.  The returned column list (already
        stored in ``RedshiftData.columns``) matches the disambiguated names.

        Args:
            columns: Column-name list, already disambiguated via
                :meth:`_disambiguate_columns`.
            rows: Raw cursor rows (each a tuple of values).

        Returns:
            List of ``{column_name: value}`` dicts.
        """
        return [dict(zip(columns, row)) for row in rows]

    def _fetch_all(
        self, cursor: Any
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Fetch all rows from an already-executed cursor.

        Extracts column names from ``cursor.description``, fetches all
        rows as tuples, zips them into dicts, then applies
        :meth:`_convert_rows`.

        Args:
            cursor: An executed ``redshift_connector`` cursor.

        Returns:
            A ``(columns, data)`` tuple where *columns* is the ordered
            list of column-name strings and *data* is the list of
            converted row dictionaries.
        """
        columns = (
            self._disambiguate_columns(
                [desc[0] for desc in cursor.description]
            )
            if cursor.description
            else []
        )
        raw_rows = cursor.fetchall()
        row_dicts = self._make_row_dicts(columns, raw_rows)
        return columns, self._convert_rows(row_dicts)

    def _convert_rows(
        self, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert row dicts to JSON-serialisable format.

        Applies the same transformations used by the Databricks and
        Snowflake ingestors:

        * ``datetime`` / date-like values → ISO-8601 string via
          ``.isoformat()``.
        * ``bytes`` → UTF-8 string; falls back to ``str()`` when the
          bytes are not valid UTF-8.
        * All other scalar types (``int``, ``float``, ``str``,
          ``bool``, ``None``, ``Decimal``) are passed through unchanged
          so downstream code can convert them as needed.

        Args:
            rows: List of row dictionaries produced by
                ``dict(zip(columns, row))``.

        Returns:
            New list of row dictionaries with type conversions applied.
        """
        converted = []
        for row in rows:
            converted_row: Dict[str, Any] = {}
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

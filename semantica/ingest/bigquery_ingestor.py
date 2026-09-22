"""BigQuery ingestion module.

Pulls data from Google BigQuery tables and queries and flattens it into
document dicts that the pipeline can feed to ``GraphBuilder``.

Design notes
------------
Three classes, matching the Snowflake/Databricks/Salesforce/Redshift ingestors:

- ``BigQueryData``: holds the rows returned by one table fetch or query
  (``data``, ``row_count``, ``columns``, ``table_name``, ``query``,
  ``project``, ``dataset``, ``location``, ``metadata``, ``ingested_at``).
  No SDK dependency — always importable.

- ``BigQueryConnector``: manages the ``google-cloud-bigquery`` client
  lifecycle.  Raises ``ImportError`` at instantiation time when the
  optional ``google-cloud-bigquery`` package is absent.  Supports
  Application Default Credentials (ADC) and service-account key-file
  authentication.

- ``BigQueryIngestor``: orchestrates ingestion.  Composes
  ``BigQueryConnector`` and exposes ``ingest_table``, ``ingest_query``,
  ``get_table_schema``, ``list_tables``, ``export_as_documents``, and
  ``close``, together with context-manager support.

Authentication
--------------
**Application Default Credentials (ADC)** — the recommended mode for
managed environments (GKE, Cloud Run, Vertex AI) and local development
(``gcloud auth application-default login``)::

    conn = BigQueryConnector(project="my-project")

**Service account key file** — for CI/CD or environments without ambient
credentials.  The path to a JSON key file exported from the GCP console::

    conn = BigQueryConnector(
        project="my-project",
        credentials_file="/run/secrets/sa-key.json",
    )

Set ``BIGQUERY_CREDENTIALS_FILE`` in the environment to avoid passing the
path in code.

SQL safety
----------
Table, dataset, and project names are validated before being interpolated
into query strings.  BigQuery identifier validation permits the
characters ``[A-Za-z0-9_]``, with the project component additionally
allowing hyphens (``-``) because all valid GCP project IDs contain
hyphens.  ``WHERE`` and ``ORDER BY`` fragments are checked with the
shared :func:`~semantica.ingest.db_ingestor._validate_sql_fragment`
helper which blocks statement separators, ``UNION``, DML/DDL keywords,
comment sequences, and time-based blind-injection oracles.  Validated
identifier components are wrapped in backticks (BigQuery's quoting
character) before interpolation.

Optional dependency
-------------------
Install the SDK before using ``BigQueryConnector`` or
``BigQueryIngestor``::

    pip install "semantica[db-bigquery]"

or directly::

    pip install google-cloud-bigquery>=3.0.0

The top-level ``import semantica.ingest`` never imports
``google-cloud-bigquery`` eagerly; the SDK is loaded only when this
module is first accessed through the lazy-export mechanism in
``__init__.py``.
"""

from __future__ import annotations

import decimal
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .db_ingestor import _validate_sql_fragment

# ---------------------------------------------------------------------------
# Optional-dependency guard
# ---------------------------------------------------------------------------
# The module always imports cleanly.  The sentinel fires at instantiation
# time (inside BigQueryConnector.__init__) so that:
#   - ``from semantica.ingest import BigQueryData`` succeeds with no SDK
#   - ``from semantica.ingest import BigQueryIngestor`` succeeds (lazy)
#   - ``BigQueryConnector(...)`` raises a clear ImportError when SDK absent
# ---------------------------------------------------------------------------
try:
    from google.cloud import bigquery as _bigquery

    BIGQUERY_AVAILABLE = True
except (ImportError, OSError):
    _bigquery = None  # type: ignore[assignment]
    BIGQUERY_AVAILABLE = False

__all__ = [
    "BigQueryData",
    "BigQueryConnector",
    "BigQueryIngestor",
]

_logger = get_logger("bigquery_ingestor")

# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------

# Standard BigQuery identifier: letter/underscore start, alphanumeric/underscore body.
_BQ_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# GCP project IDs allow hyphens (e.g. ``my-project-123``).  The first
# character must be a letter; subsequent characters may be letters, digits,
# or hyphens.  Unlike the general identifier regex, underscores are also
# accepted here because GCP silently maps them to hyphens in some contexts
# and existing customers rely on underscore-containing project IDs.
_BQ_PROJECT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _validate_bq_identifier(name: str, kind: str) -> str:
    """Validate a BigQuery table or dataset name for safe interpolation.

    Accepts names matching ``^[A-Za-z_][A-Za-z0-9_]*$``.

    Args:
        name: The identifier to validate.
        kind: Human-readable label used in error messages (e.g.
            ``"table_name"``).

    Returns:
        The unchanged name if valid.

    Raises:
        ValidationError: If the name does not match the expected pattern.
    """
    if not isinstance(name, str) or not _BQ_IDENTIFIER_RE.match(name):
        raise ValidationError(
            f"Invalid {kind}: {name!r}. Must start with a letter or "
            "underscore and contain only letters, digits, and underscores."
        )
    return name


def _validate_bq_project_id(project_id: str) -> str:
    """Validate a GCP project ID for safe interpolation.

    Accepts identifiers matching ``^[A-Za-z][A-Za-z0-9_-]*$`` to cover
    real-world GCP project IDs that contain hyphens (e.g.
    ``my-project-123``).  The generic SQL identifier validator
    (:func:`~semantica.ingest.db_ingestor._validate_sql_identifier`)
    rejects hyphens and therefore cannot be used here.

    Args:
        project_id: The GCP project ID to validate.

    Returns:
        The unchanged project ID if valid.

    Raises:
        ValidationError: If the project ID does not match the expected
            pattern.
    """
    if not isinstance(project_id, str) or not _BQ_PROJECT_ID_RE.match(project_id):
        raise ValidationError(
            f"Invalid BigQuery project ID: {project_id!r}. "
            "Must start with a letter and contain only letters, digits, "
            "hyphens, and underscores."
        )
    return project_id


def _bq_quote(identifier: str) -> str:
    """Wrap a validated identifier in BigQuery backtick quoting.

    BigQuery uses backticks (`` ` ``) to quote identifiers containing
    special characters.  Internal backticks are doubled.

    Args:
        identifier: Already-validated identifier string.

    Returns:
        Backtick-quoted identifier.
    """
    return "`" + identifier.replace("`", "``") + "`"


def _build_table_ref(
    table_name: str,
    dataset: Optional[str],
    project: Optional[str],
) -> str:
    """Build a fully-qualified, backtick-quoted BigQuery table reference.

    Components that are ``None`` or empty are omitted.

    Args:
        table_name: Already-validated table name.
        dataset: Optional dataset name (already validated).
        project: Optional project ID (already validated).

    Returns:
        A BigQuery table reference such as
        `` `my-project`.`my_dataset`.`my_table` `` or just
        `` `my_table` ``.
    """
    parts = []
    if project:
        parts.append(_bq_quote(project))
    if dataset:
        parts.append(_bq_quote(dataset))
    parts.append(_bq_quote(table_name))
    return ".".join(parts)


# ---------------------------------------------------------------------------
# BigQueryData
# ---------------------------------------------------------------------------


@dataclass
class BigQueryData:
    """Records returned from a BigQuery table or query.

    Attributes:
        data: List of row dictionaries.  Values are JSON-serialisable
            Python types (see :meth:`BigQueryIngestor._convert_rows`).
        row_count: Number of rows in ``data``.
        columns: Ordered list of column names present in ``data``.
        table_name: Source table name, or ``None`` for raw-query results.
        query: SQL query string used to produce these rows, or ``None``.
        project: GCP project ID used for the ingestion, or ``None``.
        dataset: BigQuery dataset name used for the ingestion, or
            ``None``.
        location: BigQuery location (e.g. ``"US"`` or
            ``"europe-west1"``), or ``None`` (defaults to the project
            default).
        metadata: Arbitrary extra metadata.
        ingested_at: Timestamp recorded when this object was created.
    """

    data: List[Dict[str, Any]]
    row_count: int
    columns: List[str]
    table_name: Optional[str] = None
    query: Optional[str] = None
    project: Optional[str] = None
    dataset: Optional[str] = None
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# BigQueryConnector
# ---------------------------------------------------------------------------


class BigQueryConnector:
    """Manages the ``google-cloud-bigquery`` client lifecycle.

    Responsibilities:

    * Reads credentials from constructor arguments, falling back to
      environment variables with ``BIGQUERY_*`` names.
    * Validates that the project is configured *before* any network call
      is made (project is the minimum required identifier for BigQuery).
    * Exposes :meth:`connect`, :meth:`disconnect`, and
      :meth:`test_connection` so the ingestor (and tests) can control the
      client lifecycle explicitly.
    * **Connection reuse**: :meth:`connect` returns the existing client
      when one is already open, preventing duplicate auth round-trips and
      resource leaks when used as a context manager.

    Supported Authentication Modes
    --------------------------------
    **Application Default Credentials (ADC)** — recommended for GKE,
    Cloud Run, Vertex AI, and local development.  No explicit credential
    argument is needed; the SDK resolves credentials automatically from
    the environment::

        import os
        from semantica.ingest import BigQueryConnector

        connector = BigQueryConnector(
            project=os.getenv("BIGQUERY_PROJECT"),
        )

    To configure ADC locally::

        gcloud auth application-default login

    In production, attach a service account to the workload identity and
    no credential file is required.

    **Service Account Key File** — for CI/CD or environments without
    ambient credentials::

        import os
        from semantica.ingest import BigQueryConnector

        connector = BigQueryConnector(
            project=os.getenv("BIGQUERY_PROJECT"),
            credentials_file=os.getenv("BIGQUERY_CREDENTIALS_FILE"),
        )

    The credentials file is a JSON key file downloaded from the GCP
    console (*IAM & Admin → Service Accounts → Keys*).

    Environment Variables
    ----------------------
    Every constructor parameter has an environment-variable fallback:

    * ``BIGQUERY_PROJECT``
    * ``BIGQUERY_DATASET``
    * ``BIGQUERY_LOCATION``
    * ``BIGQUERY_CREDENTIALS_FILE``  (path to service-account JSON key)

    Raises:
        ImportError: When ``google-cloud-bigquery`` is not installed.
        ValidationError: When required configuration is incomplete.
    """

    def __init__(
        self,
        project: Optional[str] = None,
        dataset: Optional[str] = None,
        location: Optional[str] = None,
        credentials_file: Optional[str] = None,
        **config: Any,
    ) -> None:
        """Initialise the connector and validate configuration.

        Args:
            project: GCP project ID.  Resolved from ``BIGQUERY_PROJECT``
                environment variable when not supplied.
            dataset: Default BigQuery dataset.  Resolved from
                ``BIGQUERY_DATASET`` environment variable.
            location: BigQuery job location, e.g. ``"US"`` or
                ``"europe-west1"``.  Resolved from ``BIGQUERY_LOCATION``
                environment variable.
            credentials_file: Path to a service-account JSON key file.
                When ``None`` (default), Application Default Credentials
                are used.  Resolved from ``BIGQUERY_CREDENTIALS_FILE``
                environment variable.
            **config: Extra keyword arguments forwarded to
                ``bigquery.Client()``.

        Raises:
            ImportError: When ``google-cloud-bigquery`` is not installed.
            ValidationError: When ``project`` cannot be resolved.
        """
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "google-cloud-bigquery is required for BigQueryConnector. "
                'Install it with: pip install "semantica[db-bigquery]"'
            )

        self.logger = _logger

        # ------------------------------------------------------------------
        # Resolve configuration — explicit args override env vars.
        # ``credentials_file`` is a path (not a secret value), but we store
        # it under a private attribute as a convention (it points to key
        # material) and never include it in log messages.
        # ------------------------------------------------------------------
        self.project: Optional[str] = project or os.getenv("BIGQUERY_PROJECT")
        self.dataset: Optional[str] = dataset or os.getenv("BIGQUERY_DATASET")
        self.location: Optional[str] = location or os.getenv("BIGQUERY_LOCATION")
        self._credentials_file: Optional[str] = credentials_file or os.getenv(
            "BIGQUERY_CREDENTIALS_FILE"
        )
        self._extra_config: Dict[str, Any] = config

        # Internal client — None until connect() is called.
        self._client: Optional[Any] = None

        # Validate that project is resolvable before any network call.
        self._validate_config()

        self.logger.debug(
            "BigQuery connector initialised (project=%s, dataset=%s, location=%s, "
            "credentials_file=%s)",
            self.project,
            self.dataset,
            self.location,
            "set" if self._credentials_file else "unset (ADC)",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Raise :class:`~semantica.utils.exceptions.ValidationError` when
        required configuration is absent.

        BigQuery's SDK can resolve the project from the ambient environment
        (``GOOGLE_CLOUD_PROJECT``, ADC metadata, etc.), but relying on that
        silently makes the connector's behaviour environment-dependent.
        We require an explicit project so failures are immediate and
        obvious.

        Raises:
            ValidationError: When ``project`` is not set.
        """
        if not self.project:
            raise ValidationError(
                "BigQuery project is required. "
                "Provide via 'project' or the BIGQUERY_PROJECT environment variable."
            )

    def _build_client(self) -> Any:
        """Create and return a ``bigquery.Client`` instance.

        Selects the credential strategy based on available configuration:
        * ``_credentials_file`` is set → load a
          ``google.oauth2.service_account.Credentials`` from the file.
        * Otherwise → pass no ``credentials`` argument and let the SDK
          resolve Application Default Credentials.

        Returns:
            A ``google.cloud.bigquery.Client`` instance.

        Raises:
            ProcessingError: If the client cannot be created.
        """
        kwargs: Dict[str, Any] = {"project": self.project}

        if self.location:
            kwargs["location"] = self.location

        if self._credentials_file:
            try:
                from google.oauth2 import service_account as _sa

                credentials = _sa.Credentials.from_service_account_file(
                    self._credentials_file,
                    scopes=["https://www.googleapis.com/auth/bigquery"],
                )
                kwargs["credentials"] = credentials
            except Exception as exc:
                raise ProcessingError(
                    f"Failed to load BigQuery credentials from file: "
                    f"{type(exc).__name__}"
                ) from exc

        kwargs.update(self._extra_config)

        try:
            return _bigquery.Client(**kwargs)
        except Exception as exc:
            raise ProcessingError(
                f"Failed to create BigQuery client: {type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def client(self) -> Optional[Any]:
        """The active ``google.cloud.bigquery.Client`` instance, or ``None``."""
        return self._client

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> Any:
        """Create and return the BigQuery client.

        If a client is already open, returns it immediately without
        re-authenticating (connection-reuse semantics matching the
        Salesforce, Databricks, and Redshift connectors).

        Returns:
            The ``google.cloud.bigquery.Client`` instance.

        Raises:
            ProcessingError: If the client cannot be created.
        """
        if self._client is not None:
            return self._client

        try:
            self._client = self._build_client()
            self.logger.info(
                "Connected to BigQuery (project=%s, location=%s)",
                self.project,
                self.location,
            )
            return self._client
        except ProcessingError:
            self._client = None
            raise
        except Exception as exc:
            self._client = None
            self.logger.error(
                "Failed to connect to BigQuery: %s", type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to connect to BigQuery: {type(exc).__name__}"
            ) from exc

    def disconnect(self) -> None:
        """Close the BigQuery client and release the reference.

        Safe to call when already disconnected — subsequent calls are
        no-ops.
        """
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # noqa: BLE001
                pass
            finally:
                self._client = None
            self.logger.info("Disconnected from BigQuery.")

    def test_connection(self) -> bool:
        """Verify connectivity by issuing a cheap query.

        Opens a client (or reuses an existing one), runs
        ``SELECT 1`` to confirm the session is live, then closes
        the client if it was opened by this call.

        Returns:
            ``True`` if the ping succeeds, ``False`` for any failure.
        """
        already_connected = self._client is not None
        try:
            client = self.connect()
            query_job = client.query("SELECT 1")
            # Consume the result to confirm the job completed successfully.
            list(query_job.result())
            return True
        except Exception as exc:
            self.logger.debug(
                "BigQuery connection test failed: %s", type(exc).__name__
            )
            return False
        finally:
            if not already_connected:
                self.disconnect()


# ---------------------------------------------------------------------------
# BigQueryIngestor
# ---------------------------------------------------------------------------


class BigQueryIngestor:
    """Google BigQuery data ingestor for the Semantica framework.

    Wraps :class:`BigQueryConnector` and exposes table and query
    ingestion, schema introspection, and document export.

    Args:
        project: GCP project ID.  Resolved from ``BIGQUERY_PROJECT``
            environment variable when not supplied.
        dataset: Default BigQuery dataset.  Resolved from
            ``BIGQUERY_DATASET`` environment variable.
        location: BigQuery job location, e.g. ``"US"`` or
            ``"europe-west1"``.  Resolved from ``BIGQUERY_LOCATION``
            environment variable.
        credentials_file: Path to a service-account JSON key file.
            When ``None``, Application Default Credentials are used.
            Resolved from ``BIGQUERY_CREDENTIALS_FILE`` environment
            variable.
        connector: An existing :class:`BigQueryConnector` to reuse.
            Useful when you want to share one client across multiple
            ingestor instances.
        config: Optional extra configuration dict forwarded to the
            connector.
        **kwargs: Additional keyword arguments merged into ``config``.

    Raises:
        ImportError: When ``google-cloud-bigquery`` is not installed.
        ValidationError: When required configuration is incomplete.

    Example::

        import os
        from semantica.ingest import BigQueryIngestor

        # ADC authentication
        ingestor = BigQueryIngestor(
            project=os.getenv("BIGQUERY_PROJECT"),
            dataset=os.getenv("BIGQUERY_DATASET"),
        )

        # Context manager — preferred for production use
        with BigQueryIngestor(
            project=os.getenv("BIGQUERY_PROJECT"),
            dataset=os.getenv("BIGQUERY_DATASET"),
        ) as bq:
            data = bq.ingest_table("orders", limit=1000)
            documents = bq.export_as_documents(data)
    """

    def __init__(
        self,
        project: Optional[str] = None,
        dataset: Optional[str] = None,
        location: Optional[str] = None,
        credentials_file: Optional[str] = None,
        connector: Optional[BigQueryConnector] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self.logger = _logger

        self.config: Dict[str, Any] = config or {}
        self.config.update(kwargs)

        # Instantiate a connector unless one is supplied.
        # ImportError propagates when SDK is absent; ValidationError when
        # configuration is incomplete.
        self.connector: BigQueryConnector = connector or BigQueryConnector(
            project=project,
            dataset=dataset,
            location=location,
            credentials_file=credentials_file,
            **self.config,
        )

        # Progress tracker — consistent with all other ingestors.
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("BigQuery ingestor initialised.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "BigQueryIngestor":
        """Open the BigQuery client on context entry."""
        self.connector.connect()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Close the BigQuery client on context exit."""
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Disconnect from BigQuery and release the client."""
        self.connector.disconnect()

    # ------------------------------------------------------------------
    # Ingestion — ingest_table
    # ------------------------------------------------------------------

    def ingest_table(
        self,
        table_name: str,
        dataset: Optional[str] = None,
        project: Optional[str] = None,
        limit: Optional[int] = None,
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        **options: Any,
    ) -> BigQueryData:
        """Fetch rows from a BigQuery table.

        Builds a ``SELECT * FROM <table>`` query with optional
        ``WHERE``, ``ORDER BY``, and ``LIMIT`` clauses and executes it
        against BigQuery.

        All identifier components (``table_name``, ``dataset``,
        ``project``) are validated before interpolation:
        table and dataset names must match
        ``^[A-Za-z_][A-Za-z0-9_]*$``; the project ID must match
        ``^[A-Za-z][A-Za-z0-9_-]*$`` (hyphens permitted).
        Validated components are wrapped in backticks.  ``WHERE`` and
        ``ORDER BY`` fragments are validated with
        :func:`~semantica.ingest.db_ingestor._validate_sql_fragment`.
        All validation happens before any network call.

        Connection lifecycle: if the ingestor is used as a context
        manager the existing client is reused; standalone calls open a
        transient client and close it in a ``finally`` block.

        Args:
            table_name: Name of the BigQuery table to query.
            dataset: Override dataset name (defaults to the connector's
                configured dataset).
            project: Override project ID (defaults to the connector's
                configured project).
            limit: Maximum number of rows to return.
            where: SQL ``WHERE`` clause fragment (without the
                ``WHERE`` keyword).  Trusted / operator input only —
                do not pass raw end-user text.
            order_by: SQL ``ORDER BY`` clause fragment (without the
                keyword).  Same trust requirement.
            **options: Reserved for future use.

        Returns:
            :class:`BigQueryData` with ``data``, ``row_count``,
            ``columns``, ``table_name``, ``project``, ``dataset``,
            ``location``, ``query``, and ``metadata`` populated.

        Raises:
            ValidationError: If any identifier or SQL fragment fails
                safety validation.
            ProcessingError: If the query fails or the client cannot
                be created.
        """
        effective_project = project or self.connector.project
        effective_dataset = dataset or self.connector.dataset

        # ------------------------------------------------------------------
        # Validate all identifiers and SQL fragments BEFORE connecting so
        # invalid inputs are rejected cheaply without any network call.
        # ------------------------------------------------------------------
        if not effective_dataset:
            raise ValidationError(
                "BigQuery dataset is required for ingest_table(). "
                "Provide via 'dataset' argument or the BIGQUERY_DATASET "
                "environment variable."
            )
        _validate_bq_identifier(table_name, "table_name")
        _validate_bq_identifier(effective_dataset, "dataset")
        if effective_project:
            _validate_bq_project_id(effective_project)
        if where:
            _validate_sql_fragment(where, "where")
        if order_by:
            _validate_sql_fragment(order_by, "order_by")

        table_ref = _build_table_ref(table_name, effective_dataset, effective_project)

        tracking_id = self.progress_tracker.start_tracking(
            file=table_ref,
            module="ingest",
            submodule="BigQueryIngestor",
            message=f"Table: {table_ref}",
        )

        try:
            already_connected = self.connector.client is not None
            client = self.connector.connect()

            try:
                query = f"SELECT * FROM {table_ref}"

                if where:
                    query += f" WHERE {where}"
                if order_by:
                    query += f" ORDER BY {order_by}"
                if limit is not None:
                    query += f" LIMIT {int(limit)}"

                self.logger.debug("Executing ingest_table query: %s", query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Executing query..."
                )

                query_job = client.query(query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Fetching results..."
                )

                result_iter = query_job.result()
                # Extract column names from the RowIterator schema BEFORE
                # materialising rows so zero-row results preserve the
                # declared schema (Finding 2).
                schema_columns = (
                    [field.name for field in result_iter.schema]
                    if result_iter.schema
                    else None
                )
                rows = list(result_iter)
                columns, data = self._rows_to_dicts(rows, schema_columns=schema_columns)
                data = self._convert_rows(data)

            finally:
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

            return BigQueryData(
                data=data,
                row_count=len(data),
                columns=columns,
                table_name=table_name,
                project=effective_project,
                dataset=effective_dataset,
                location=self.connector.location,
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
                f"Failed to ingest BigQuery table '{table_name}': "
                f"{type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Ingestion — ingest_query
    # ------------------------------------------------------------------

    def ingest_query(
        self,
        query: str,
        job_config: Optional[Any] = None,
        **options: Any,
    ) -> BigQueryData:
        """Execute a raw SQL query and return all matching rows.

        Passes the query verbatim to the BigQuery client.  The caller
        is responsible for the correctness and safety of the query
        string.

        For parameterised queries pass a
        ``google.cloud.bigquery.QueryJobConfig`` with ``query_parameters``
        set via the ``job_config`` argument.

        Connection lifecycle mirrors :meth:`ingest_table`: standalone
        calls open and close a transient client; calls made inside a
        context manager reuse the open client.

        Args:
            query: Complete Standard SQL query string.
            job_config: Optional ``bigquery.QueryJobConfig`` instance for
                parameterised queries, timeouts, dry-run mode, etc.
            **options: Reserved for future use.

        Returns:
            :class:`BigQueryData` with ``data``, ``row_count``,
            ``columns``, and ``query`` populated.

        Raises:
            ProcessingError: If the query fails or the client cannot be
                created.
        """
        tracking_id = self.progress_tracker.start_tracking(
            file="query",
            module="ingest",
            submodule="BigQueryIngestor",
            message="Executing query...",
        )

        try:
            already_connected = self.connector.client is not None
            client = self.connector.connect()

            try:
                self.logger.debug("Executing ingest_query: %s", query[:200])

                self.progress_tracker.update_tracking(
                    tracking_id, message="Executing query..."
                )

                if job_config is not None:
                    query_job = client.query(query, job_config=job_config)
                else:
                    query_job = client.query(query)

                self.progress_tracker.update_tracking(
                    tracking_id, message="Fetching results..."
                )

                result_iter = query_job.result()
                # Extract column names from the RowIterator schema BEFORE
                # materialising rows so zero-row results preserve the
                # declared schema (Finding 2).
                schema_columns = (
                    [field.name for field in result_iter.schema]
                    if result_iter.schema
                    else None
                )
                rows = list(result_iter)
                columns, data = self._rows_to_dicts(rows, schema_columns=schema_columns)
                data = self._convert_rows(data)

            finally:
                if not already_connected:
                    self.connector.disconnect()

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Query completed: {len(data)} rows",
            )
            self.logger.info("ingest_query completed: %d row(s)", len(data))

            return BigQueryData(
                data=data,
                row_count=len(data),
                columns=columns,
                query=query,
                project=self.connector.project,
                dataset=self.connector.dataset,
                location=self.connector.location,
                metadata={},
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
                f"Failed to execute BigQuery query: {type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Schema discovery — get_table_schema
    # ------------------------------------------------------------------

    def get_table_schema(
        self,
        table_name: str,
        dataset: Optional[str] = None,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return schema metadata for a BigQuery table.

        Uses the ``bigquery.Client.get_table()`` API to retrieve the
        table's ``SchemaField`` list without executing a query.  The
        result includes column names, types, nullability, and the
        table-level row count.

        Args:
            table_name: Name of the BigQuery table to introspect.
            dataset: Override dataset name.  Defaults to the connector's
                configured dataset.
            project: Override project ID.  Defaults to the connector's
                configured project.

        Returns:
            A dictionary with three keys:

            ``"columns"``
                Ordered list of column dicts, each containing
                ``"name"``, ``"type"``, and ``"nullable"`` (``bool``).

            ``"num_rows"``
                Approximate row count reported by BigQuery, or ``None``
                when unavailable.

            ``"clustering_fields"``
                List of clustering-column names, or an empty list when
                the table is not clustered.

        Raises:
            ValidationError: If *table_name*, *dataset*, or *project*
                fails identifier validation.
            ProcessingError: If the metadata call fails.
        """
        effective_project = project or self.connector.project
        effective_dataset = dataset or self.connector.dataset

        if not effective_dataset:
            raise ValidationError(
                "BigQuery dataset is required for get_table_schema(). "
                "Provide via 'dataset' argument or the BIGQUERY_DATASET "
                "environment variable."
            )
        _validate_bq_identifier(table_name, "table_name")
        _validate_bq_identifier(effective_dataset, "dataset")
        if effective_project:
            _validate_bq_project_id(effective_project)

        # Build the table reference string expected by get_table().
        # If project and dataset are available, use the fully-qualified form.
        parts = []
        if effective_project:
            parts.append(effective_project)
        if effective_dataset:
            parts.append(effective_dataset)
        parts.append(table_name)
        table_ref_str = ".".join(parts)

        try:
            already_connected = self.connector.client is not None
            client = self.connector.connect()

            try:
                table = client.get_table(table_ref_str)
            finally:
                if not already_connected:
                    self.connector.disconnect()

            columns = [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "nullable": f.mode != "REQUIRED",
                }
                for f in (table.schema or [])
            ]

            self.logger.debug(
                "get_table_schema: %s — %d column(s)",
                table_ref_str,
                len(columns),
            )

            return {
                "columns": columns,
                "num_rows": getattr(table, "num_rows", None),
                "clustering_fields": list(table.clustering_fields or []),
            }

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to get schema for %s: %s", table_name, type(exc).__name__
            )
            raise ProcessingError(
                f"Failed to get schema for BigQuery table '{table_name}': "
                f"{type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Schema discovery — list_tables
    # ------------------------------------------------------------------

    def list_tables(
        self,
        dataset: Optional[str] = None,
        project: Optional[str] = None,
    ) -> List[str]:
        """Return the names of all tables in the specified dataset.

        Uses ``bigquery.Client.list_tables()`` to enumerate table IDs.
        The result includes regular tables, views, and materialized views
        (matching BigQuery's API behaviour).

        Args:
            dataset: Override dataset name.  Defaults to the connector's
                configured dataset.
            project: Override project ID.  Defaults to the connector's
                configured project.

        Returns:
            Sorted list of table-name strings, or an empty list when the
            dataset contains no tables.

        Raises:
            ValidationError: If *dataset* or *project* fails identifier
                validation, or if no dataset is configured.
            ProcessingError: If the list call fails.
        """
        effective_project = project or self.connector.project
        effective_dataset = dataset or self.connector.dataset

        if not effective_dataset:
            raise ValidationError(
                "BigQuery dataset is required for list_tables(). "
                "Provide via 'dataset' argument or the BIGQUERY_DATASET "
                "environment variable."
            )

        _validate_bq_identifier(effective_dataset, "dataset")
        if effective_project:
            _validate_bq_project_id(effective_project)

        # Build dataset reference string expected by list_tables().
        dataset_ref_str = (
            f"{effective_project}.{effective_dataset}"
            if effective_project
            else effective_dataset
        )

        try:
            already_connected = self.connector.client is not None
            client = self.connector.connect()

            try:
                tables = list(client.list_tables(dataset_ref_str))
            finally:
                if not already_connected:
                    self.connector.disconnect()

            table_names = sorted(t.table_id for t in tables)
            self.logger.debug(
                "list_tables: %d table(s) in dataset '%s'",
                len(table_names),
                effective_dataset,
            )
            return table_names

        except (ValidationError, ProcessingError):
            raise
        except Exception as exc:
            self.logger.error(
                "Failed to list tables in dataset '%s': %s",
                effective_dataset,
                type(exc).__name__,
            )
            raise ProcessingError(
                f"Failed to list BigQuery tables in dataset '{effective_dataset}': "
                f"{type(exc).__name__}"
            ) from exc

    # ------------------------------------------------------------------
    # Document export
    # ------------------------------------------------------------------

    def export_as_documents(
        self,
        data: BigQueryData,
        id_field: str = "id",
        text_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert :class:`BigQueryData` to the Semantica document format.

        Produces the same ``{"id", "text", "metadata"}`` shape used by
        :class:`~semantica.ingest.snowflake_ingestor.SnowflakeIngestor`,
        :class:`~semantica.ingest.databricks_ingestor.DatabricksIngestor`,
        and :class:`~semantica.ingest.redshift_ingestor.RedshiftIngestor`,
        making :class:`BigQueryData` directly usable with
        :class:`~semantica.kg.graph_builder.GraphBuilder`.

        **ID resolution**
            ``str(row.get(id_field, idx))`` — the row-index integer is
            used as a deterministic fallback when *id_field* is absent,
            cast to a string.  This matches the Snowflake/Redshift
            convention.

        **Text composition**
            * When *text_fields* is provided: only those fields are used;
              each non-``None`` value is converted to a string and joined
              with a single space.
            * When *text_fields* is ``None``: only ``str``-typed values
              are joined (integers, floats, booleans, ``None``, and
              ``Decimal`` are excluded).  This matches the
              Snowflake/Databricks default behaviour.

        **Metadata**
            ``{"source": "bigquery", "table": ..., "project": ...,
            "dataset": ..., "location": ..., "row_data": <full row>}``

        Args:
            data: A :class:`BigQueryData` object returned by
                :meth:`ingest_table` or :meth:`ingest_query`.
            id_field: Row field to use as the document ``"id"``.
                Defaults to ``"id"``.
            text_fields: List of field names whose values form the
                document ``"text"``.  When ``None``, all string-typed
                field values are joined.

        Returns:
            List of document dictionaries::

                [
                    {
                        "id": str,
                        "text": str,
                        "metadata": {
                            "source": "bigquery",
                            "table": str | None,
                            "project": str | None,
                            "dataset": str | None,
                            "location": str | None,
                            "row_data": dict,
                        },
                    },
                    ...
                ]
        """
        documents: List[Dict[str, Any]] = []

        for idx, row in enumerate(data.data):
            # Treat a present-but-None id_field value the same as a
            # missing key: fall back to the row index.  This prevents
            # every null-id row from receiving the shared string "None"
            # as its document identifier (Finding 3).
            raw_id = row.get(id_field)
            doc_id = str(raw_id) if raw_id is not None else str(idx)

            doc: Dict[str, Any] = {
                "id": doc_id,
                "metadata": {
                    "source": "bigquery",
                    "table": data.table_name,
                    "project": data.project,
                    "dataset": data.dataset,
                    "location": data.location,
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
    def _rows_to_dicts(
        rows: List[Any],
        schema_columns: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Convert BigQuery ``Row`` objects to plain dictionaries.

        ``google.cloud.bigquery.Row`` supports ``dict(row)`` and
        ``row.keys()``.  Column names are derived from *schema_columns*
        when supplied (populated from the ``RowIterator.schema`` before
        row materialisation, so empty result sets preserve the declared
        schema).  When *schema_columns* is ``None`` and rows are present,
        column names are taken from the first row.  When both are absent
        the column list is empty.

        Args:
            rows: List of ``google.cloud.bigquery.Row`` objects from a
                completed ``QueryJob``.
            schema_columns: Optional ordered list of column names derived
                from the ``RowIterator`` schema before rows are fetched.
                Pass this to preserve columns for zero-row results.

        Returns:
            A ``(columns, data)`` tuple where *columns* is the ordered
            list of column-name strings and *data* is the list of row
            dictionaries.
        """
        if schema_columns is not None:
            columns = schema_columns
        elif rows:
            columns = list(rows[0].keys())
        else:
            columns = []
        data = [dict(row) for row in rows]
        return columns, data

    @staticmethod
    def _convert_value(value: Any) -> Any:
        """Recursively convert a single value to a JSON-serialisable type.

        Handles scalars, ``dict``-like BigQuery RECORD/STRUCT values, and
        ``list``-like REPEATED field values at every nesting level so that
        nested records containing dates, decimals, or bytes do not reach
        ``BigQueryData.data`` or document metadata in their raw SDK form.

        Conversion rules (applied at every nesting level):

        * ``datetime`` → ISO-8601 string (checked before ``date`` because
          ``datetime`` is a subclass of ``date``).
        * ``date`` / ``time`` → ISO-8601 string.
        * ``decimal.Decimal`` → ``str`` (preserves full NUMERIC precision).
        * ``bytes`` → UTF-8 decoded string; falls back to ``str()`` on
          ``UnicodeDecodeError``.
        * ``dict`` / mapping → recursively converted ``dict``.
        * ``list`` / sequence (but not ``str`` / ``bytes``) → recursively
          converted ``list``.
        * Everything else (``int``, ``float``, ``bool``, ``None``,
          ``str``) → passed through unchanged.

        Args:
            value: Any value returned by the BigQuery Python client.

        Returns:
            A JSON-serialisable Python value.
        """
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            # Checked AFTER datetime: datetime is a subclass of date.
            return value.isoformat()
        if isinstance(value, time):
            return value.isoformat()
        if isinstance(value, decimal.Decimal):
            return str(value)
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError:
                return str(value)
        if isinstance(value, dict):
            return {k: BigQueryIngestor._convert_value(v) for k, v in value.items()}
        # Handle list-like repeated fields; exclude str/bytes which are
        # also sequences but must not be iterated character-by-character.
        if isinstance(value, (list, tuple)):
            return [BigQueryIngestor._convert_value(item) for item in value]
        return value

    def _convert_rows(
        self, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert row dicts to JSON-serialisable format at every level.

        Delegates each top-level value to :meth:`_convert_value`, which
        recurses into BigQuery RECORD (STRUCT) and REPEATED fields so that
        nested dates, decimals, bytes, or further sub-records are converted
        correctly rather than left as raw SDK objects.

        Args:
            rows: List of row dictionaries produced by
                :meth:`_rows_to_dicts`.

        Returns:
            New list of row dictionaries with type conversions applied
            at all nesting levels.
        """
        return [
            {key: self._convert_value(value) for key, value in row.items()}
            for row in rows
        ]

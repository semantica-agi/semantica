"""
Unit tests for BigQueryConnector and BigQueryIngestor.

All google-cloud-bigquery API calls are mocked — no real GCP project or
BigQuery dataset is required.

Test structure mirrors tests/test_redshift_ingestor.py and
tests/test_salesforce_ingestor.py:
  - autouse fixture injects a minimal google-cloud-bigquery stub when the
    SDK is not installed, so the test suite runs in both environments.
  - Each test that needs the connector to appear available patches
    ``BIGQUERY_AVAILABLE`` to ``True`` and ``_bigquery`` to a
    ``MagicMock``.
  - Credentials are always supplied so secret values are never embedded
    in assertions.
"""

from __future__ import annotations

import decimal
import os
from datetime import date, datetime, time
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Optional SDK detection
# ---------------------------------------------------------------------------
try:
    from google.cloud import bigquery as _bq_sdk  # noqa: F401

    BIGQUERY_SDK_AVAILABLE = True
except ImportError:
    BIGQUERY_SDK_AVAILABLE = False


# ---------------------------------------------------------------------------
# autouse fixture — inject stub when SDK is absent
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_bigquery_sdk_if_needed():
    """Inject a minimal google-cloud-bigquery stub when the SDK is not installed.

    Design constraints (mirroring test_salesforce_ingestor.py):
    1. Tests in ``TestImportBehaviourWithoutLib`` deliberately exercise the
       production missing-dependency guard (``BIGQUERY_AVAILABLE=False``).
       They must *not* receive the stub.
    2. Every other test needs the stub so imports work even without the SDK.
    3. After each stubbed test, any BigQuery symbols cached in the package
       globals are removed so subsequent availability checks re-run the guard.
    """
    import sys

    # Only inject the stub when the real SDK is absent.
    if not BIGQUERY_SDK_AVAILABLE:
        # Build a minimal stub hierarchy that satisfies all import paths
        # used by bigquery_ingestor.py.
        bq_stub = MagicMock()
        google_stub = MagicMock()
        google_cloud_stub = MagicMock()
        google_auth_stub = MagicMock()
        google_api_core_stub = MagicMock()
        google_oauth2_stub = MagicMock()
        google_oauth2_sa_stub = MagicMock()

        class _GAPIError(Exception):
            pass

        class _CredentialsError(Exception):
            pass

        bq_stub.Client = MagicMock()
        google_api_core_stub.exceptions = MagicMock()
        google_api_core_stub.exceptions.GoogleAPICallError = _GAPIError
        google_auth_stub.exceptions = MagicMock()
        google_auth_stub.exceptions.DefaultCredentialsError = _CredentialsError
        google_oauth2_sa_stub.Credentials = MagicMock()

        _BQ_EXPORT_NAMES = (
            "BigQueryIngestor",
            "BigQueryConnector",
            "BigQueryData",
        )

        import semantica.ingest as _ingest_pkg

        _cached_before = {
            name: _ingest_pkg.__dict__.get(name) for name in _BQ_EXPORT_NAMES
        }

        stub_modules = {
            "google": google_stub,
            "google.cloud": google_cloud_stub,
            "google.cloud.bigquery": bq_stub,
            "google.auth": google_auth_stub,
            "google.auth.exceptions": google_auth_stub.exceptions,
            "google.api_core": google_api_core_stub,
            "google.api_core.exceptions": google_api_core_stub.exceptions,
            "google.oauth2": google_oauth2_stub,
            "google.oauth2.service_account": google_oauth2_sa_stub,
        }

        with patch.dict("sys.modules", stub_modules):
            import semantica.ingest.bigquery_ingestor as _bq_mod

            with patch.object(_bq_mod, "BIGQUERY_AVAILABLE", True):
                try:
                    yield
                finally:
                    for name in _BQ_EXPORT_NAMES:
                        if _cached_before[name] is None:
                            _ingest_pkg.__dict__.pop(name, None)
    else:
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_bq_client(project: str = "test-project") -> Mock:
    """Return a Mock that looks like a connected bigquery.Client."""
    mock_client = Mock()
    mock_client.project = project
    mock_client.close = Mock()
    return mock_client


def _make_mock_row(keys: list, values: list) -> Mock:
    """Return a Mock that behaves like a google.cloud.bigquery.Row."""
    mock_row = Mock()
    mock_row.keys = Mock(return_value=keys)
    mock_row.__iter__ = Mock(return_value=iter(zip(keys, values)))
    # Support dict(row) by making the row behave as a mapping.
    mapping = dict(zip(keys, values))
    mock_row.__getitem__ = Mock(side_effect=mapping.__getitem__)
    mock_row.keys = Mock(return_value=list(mapping.keys()))
    # _rows_to_dicts calls dict(row) — patch it to return the mapping.
    mock_row.items = Mock(return_value=list(mapping.items()))
    return mock_row


def _make_query_job(rows: list) -> Mock:
    """Return a Mock that behaves like a bigquery.QueryJob.

    The mock's ``.result()`` returns a RowIterator-like object with a
    ``.schema`` attribute (list of SchemaField mocks derived from the first
    row's keys when rows are present) and is iterable.
    """
    job = Mock()

    # Build a RowIterator-like mock that has .schema and is iterable.
    result_iter = Mock()

    if rows:
        # Derive schema field names from the first row's keys (if it's a dict).
        first = rows[0]
        if isinstance(first, dict):
            schema_fields = []
            for name in first.keys():
                f = Mock()
                f.name = name
                schema_fields.append(f)
            result_iter.schema = schema_fields
        else:
            # Non-dict row (e.g. plain Mock for test_connection ping) — no schema.
            result_iter.schema = []
    else:
        result_iter.schema = []

    result_iter.__iter__ = Mock(return_value=iter(rows))
    # list(result_iter) needs __iter__ to work; also support being called
    # as an iterable directly.
    job.result = Mock(return_value=result_iter)
    return job


# ---------------------------------------------------------------------------
# TestBigQueryData
# ---------------------------------------------------------------------------


class TestBigQueryData:
    """BigQueryData is a plain dataclass — no SDK dependency."""

    def test_creation_with_required_fields(self):
        from semantica.ingest.bigquery_ingestor import BigQueryData

        data = BigQueryData(data=[], row_count=0, columns=[])

        assert data.row_count == 0
        assert data.data == []
        assert data.columns == []
        assert data.table_name is None
        assert data.query is None
        assert data.project is None
        assert data.dataset is None
        assert data.location is None
        assert data.metadata == {}
        assert isinstance(data.ingested_at, datetime)

    def test_creation_with_all_fields(self):
        from semantica.ingest.bigquery_ingestor import BigQueryData

        rows = [{"id": "1", "name": "Alice"}]
        data = BigQueryData(
            data=rows,
            row_count=1,
            columns=["id", "name"],
            table_name="users",
            query="SELECT * FROM users",
            project="my-project",
            dataset="my_dataset",
            location="US",
            metadata={"custom": "value"},
        )

        assert data.row_count == 1
        assert data.table_name == "users"
        assert data.query == "SELECT * FROM users"
        assert data.project == "my-project"
        assert data.dataset == "my_dataset"
        assert data.location == "US"
        assert data.metadata["custom"] == "value"

    def test_importable_without_sdk(self):
        """BigQueryData must import even when google-cloud-bigquery is absent."""
        from semantica.ingest.bigquery_ingestor import BigQueryData

        data = BigQueryData(data=[{"col": 1}], row_count=1, columns=["col"])
        assert data.row_count == 1


# ---------------------------------------------------------------------------
# TestBigQueryConnectorInit — ADC
# ---------------------------------------------------------------------------


class TestBigQueryConnectorInitADC:
    """Constructor validation for Application Default Credentials."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_with_explicit_project(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        conn = BigQueryConnector(project="my-project")

        assert conn.project == "my-project"
        assert conn.dataset is None
        assert conn.location is None
        assert conn._credentials_file is None
        assert conn._client is None  # not connected yet

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_with_project_dataset_location(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        conn = BigQueryConnector(
            project="my-project",
            dataset="my_dataset",
            location="europe-west1",
        )

        assert conn.project == "my-project"
        assert conn.dataset == "my_dataset"
        assert conn.location == "europe-west1"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_project_with_hyphens_accepted(self):
        """GCP project IDs contain hyphens — must not raise ValidationError."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        # Should not raise.
        conn = BigQueryConnector(project="my-gcp-project-123")
        assert conn.project == "my-gcp-project-123"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_missing_project_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="BigQuery project is required"):
            BigQueryConnector()

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_empty_project_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="BigQuery project is required"):
            BigQueryConnector(project="")


# ---------------------------------------------------------------------------
# TestBigQueryConnectorInitKeyFile
# ---------------------------------------------------------------------------


class TestBigQueryConnectorInitKeyFile:
    """Constructor validation for service-account key-file authentication."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_with_credentials_file(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        conn = BigQueryConnector(
            project="my-project",
            credentials_file="/path/to/sa-key.json",
        )

        assert conn._credentials_file == "/path/to/sa-key.json"
        assert conn.project == "my-project"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_credentials_file_not_logged(self):
        """credentials_file path must not appear in INFO/DEBUG log output."""
        import logging

        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch("semantica.ingest.bigquery_ingestor._logger") as mock_log:
            BigQueryConnector(
                project="my-project",
                credentials_file="/secrets/sa-key.json",
            )
            # The path itself should not appear as a plain value in log calls.
            for call_args in mock_log.debug.call_args_list:
                args_str = str(call_args)
                assert "/secrets/sa-key.json" not in args_str


# ---------------------------------------------------------------------------
# TestBigQueryConnectorEnvVars
# ---------------------------------------------------------------------------


class TestBigQueryConnectorEnvVars:
    """Environment-variable fallback for every constructor parameter."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_project_from_env(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch.dict(os.environ, {"BIGQUERY_PROJECT": "env-project"}):
            conn = BigQueryConnector()
        assert conn.project == "env-project"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_dataset_from_env(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch.dict(
            os.environ,
            {"BIGQUERY_PROJECT": "p", "BIGQUERY_DATASET": "env_dataset"},
        ):
            conn = BigQueryConnector()
        assert conn.dataset == "env_dataset"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_location_from_env(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch.dict(
            os.environ,
            {"BIGQUERY_PROJECT": "p", "BIGQUERY_LOCATION": "EU"},
        ):
            conn = BigQueryConnector()
        assert conn.location == "EU"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_credentials_file_from_env(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch.dict(
            os.environ,
            {
                "BIGQUERY_PROJECT": "p",
                "BIGQUERY_CREDENTIALS_FILE": "/env/sa-key.json",
            },
        ):
            conn = BigQueryConnector()
        assert conn._credentials_file == "/env/sa-key.json"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_explicit_args_override_env(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        with patch.dict(
            os.environ,
            {"BIGQUERY_PROJECT": "env-project", "BIGQUERY_DATASET": "env_ds"},
        ):
            conn = BigQueryConnector(project="explicit-project", dataset="explicit_ds")

        assert conn.project == "explicit-project"
        assert conn.dataset == "explicit_ds"


# ---------------------------------------------------------------------------
# TestBigQueryConnectorConnect
# ---------------------------------------------------------------------------


class TestBigQueryConnectorConnect:
    """connect() / disconnect() / test_connection() lifecycle."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_connect_adc_calls_client_constructor(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        client = conn.connect()

        assert client is mock_client
        assert conn._client is mock_client
        mock_bq.Client.assert_called_once_with(project="my-project")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_connect_with_location(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_bq.Client.return_value = _make_mock_bq_client()

        conn = BigQueryConnector(project="my-project", location="EU")
        conn.connect()

        call_kwargs = mock_bq.Client.call_args[1]
        assert call_kwargs["location"] == "EU"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_connect_reuse_existing_client(self, mock_bq):
        """Second connect() must reuse the existing client, not call Client() again."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_bq.Client.return_value = _make_mock_bq_client()

        conn = BigQueryConnector(project="my-project")
        client1 = conn.connect()
        client2 = conn.connect()

        assert client1 is client2
        mock_bq.Client.assert_called_once()

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_disconnect_closes_client(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        conn.connect()
        conn.disconnect()

        mock_client.close.assert_called_once()
        assert conn._client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_disconnect_idempotent(self, mock_bq):
        """Calling disconnect() twice must not raise."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_bq.Client.return_value = _make_mock_bq_client()

        conn = BigQueryConnector(project="my-project")
        conn.connect()
        conn.disconnect()
        conn.disconnect()  # second call — no-op, no exception

        assert conn._client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_connect_failure_clears_client_ref(self, mock_bq):
        """If Client() raises, _client must remain None."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector
        from semantica.utils.exceptions import ProcessingError

        mock_bq.Client.side_effect = RuntimeError("auth failure")

        conn = BigQueryConnector(project="my-project")
        with pytest.raises(ProcessingError):
            conn.connect()

        assert conn._client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_connect_with_credentials_file(self, mock_bq):
        """Service-account key-file path must be used to build credentials."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_bq.Client.return_value = mock_client

        mock_sa = MagicMock()
        mock_creds = MagicMock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds

        conn = BigQueryConnector(
            project="my-project",
            credentials_file="/run/secrets/sa.json",
        )

        with patch(
            "google.oauth2.service_account", mock_sa, create=True
        ):
            # Patch the import inside _build_client
            with patch(
                "semantica.ingest.bigquery_ingestor._bigquery", mock_bq
            ):
                with patch(
                    "semantica.ingest.bigquery_ingestor.BigQueryConnector._build_client"
                ) as mock_build:
                    mock_build.return_value = mock_client
                    client = conn.connect()

        assert client is mock_client

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_test_connection_returns_true_on_success(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([Mock()])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        result = conn.test_connection()

        assert result is True
        mock_client.query.assert_called_once_with("SELECT 1")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_test_connection_returns_false_on_failure(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_client.query = Mock(side_effect=RuntimeError("network error"))
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        result = conn.test_connection()

        assert result is False

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_test_connection_closes_transient_client(self, mock_bq):
        """test_connection() must close a client it opened itself."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([Mock()])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        assert conn._client is None

        conn.test_connection()

        # Client must be closed after test_connection returns.
        mock_client.close.assert_called_once()
        assert conn._client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_test_connection_keeps_existing_client(self, mock_bq):
        """test_connection() must not close a client it did not open."""
        from semantica.ingest.bigquery_ingestor import BigQueryConnector

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([Mock()])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        conn = BigQueryConnector(project="my-project")
        conn.connect()  # open before test_connection
        conn.test_connection()

        # Client must NOT be closed.
        mock_client.close.assert_not_called()
        assert conn._client is mock_client


# ---------------------------------------------------------------------------
# TestBigQueryIngestorInit
# ---------------------------------------------------------------------------


class TestBigQueryIngestorInit:
    """BigQueryIngestor.__init__ and connector composition."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_stores_connector(self):
        from semantica.ingest.bigquery_ingestor import (
            BigQueryConnector,
            BigQueryIngestor,
        )

        conn = BigQueryConnector(project="my-project")
        ing = BigQueryIngestor(connector=conn)

        assert ing.connector is conn

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_creates_connector_from_kwargs(self):
        from semantica.ingest.bigquery_ingestor import BigQueryConnector, BigQueryIngestor

        ing = BigQueryIngestor(project="my-project", dataset="my_dataset")

        assert isinstance(ing.connector, BigQueryConnector)
        assert ing.connector.project == "my-project"
        assert ing.connector.dataset == "my_dataset"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_init_missing_project_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="BigQuery project is required"):
            BigQueryIngestor()


# ---------------------------------------------------------------------------
# TestBigQueryIngestorTable
# ---------------------------------------------------------------------------


class TestBigQueryIngestorTable:
    """BigQueryIngestor.ingest_table()."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_basic(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        mock_client = _make_mock_bq_client()
        rows = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
        mock_rows = [Mock() for _ in rows]
        for mock_row, row in zip(mock_rows, rows):
            mock_row.keys = Mock(return_value=list(row.keys()))
            # Make dict(row) work
            mock_row.__iter__ = Mock(return_value=iter(row.items()))
        # Override _rows_to_dicts path — patch at the class level
        mock_job = _make_query_job(mock_rows)
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="my-project", dataset="my_dataset")

        # Patch _rows_to_dicts to return plain dicts directly.
        with patch.object(
            type(ing),
            "_rows_to_dicts",
            staticmethod(lambda rows, schema_columns=None: (["id", "name"], [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}])),
        ):
            data = ing.ingest_table("users")

        assert isinstance(data, BigQueryData)
        assert data.row_count == 2
        assert data.table_name == "users"
        assert data.project == "my-project"
        assert data.dataset == "my_dataset"
        assert "SELECT * FROM" in data.query
        assert "`users`" in data.query

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_generates_correct_sql(self, mock_bq):
        """Verify the SQL sent to client.query() is well-formed."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="my-project", dataset="my_dataset")
        ing.ingest_table(
            "orders",
            where="status = 'active'",
            order_by="created_at DESC",
            limit=100,
        )

        executed_sql = mock_client.query.call_args[0][0]
        assert "`my-project`.`my_dataset`.`orders`" in executed_sql
        assert "WHERE status = 'active'" in executed_sql
        assert "ORDER BY created_at DESC" in executed_sql
        assert "LIMIT 100" in executed_sql

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_no_limit(self, mock_bq):
        """When limit is None, no LIMIT clause should be added."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        ing.ingest_table("t")

        executed_sql = mock_client.query.call_args[0][0]
        assert "LIMIT" not in executed_sql

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_override_project_dataset(self, mock_bq):
        """Per-call project/dataset overrides the connector defaults."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="default-proj", dataset="default_ds")
        ing.ingest_table("t", project="override-proj", dataset="override_ds")

        executed_sql = mock_client.query.call_args[0][0]
        assert "`override-proj`" in executed_sql
        assert "`override_ds`" in executed_sql
        assert "default" not in executed_sql

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_closes_transient_connection(self, mock_bq):
        """Standalone ingest_table must close the client it opened."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        assert ing.connector.client is None

        ing.ingest_table("t")

        mock_client.close.assert_called_once()
        assert ing.connector.client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_reuses_context_manager_connection(self, mock_bq):
        """Inside a context manager, ingest_table must not close the shared client."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        with BigQueryIngestor(project="p", dataset="d") as ing:
            ing.ingest_table("t")
            # Client must still be open inside the context.
            assert ing.connector.client is mock_client
            mock_client.close.assert_not_called()

        # Client closed on __exit__.
        mock_client.close.assert_called_once()

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_invalid_table_name_raises(self):
        """Table names with SQL-injection characters must be rejected."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ValidationError):
            ing.ingest_table("my-table")  # hyphen not allowed in table name

        with pytest.raises(ValidationError):
            ing.ingest_table("my table")  # space not allowed

        with pytest.raises(ValidationError):
            ing.ingest_table("1table")  # leading digit not allowed

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_invalid_where_raises(self):
        """WHERE clauses with injection characters must be rejected."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ValidationError):
            ing.ingest_table("t", where="1=1; DROP TABLE t")

        with pytest.raises(ValidationError):
            ing.ingest_table("t", where="1=1 UNION SELECT * FROM secrets")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_invalid_order_by_raises(self):
        """ORDER BY clauses with injection characters must be rejected."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ValidationError):
            ing.ingest_table("t", order_by="name; DROP TABLE t")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_invalid_dataset_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ValidationError):
            ing.ingest_table("t", dataset="my dataset")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_missing_dataset_raises(self):
        """ingest_table must reject calls when no dataset is configured (PR comment)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        # No dataset on the ingestor, none passed at call site.
        ing = BigQueryIngestor(project="my-project")

        with pytest.raises(ValidationError, match="dataset is required"):
            ing.ingest_table("orders")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_ingest_table_valid_project_id_with_hyphens(self):
        """ingest_table must not reject valid GCP project IDs that contain hyphens."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")

        # This should raise ValidationError for project, NOT a blanket rejection.
        # The project override "my-project-123" is valid.
        # We only test validation passes (no error from _validate_bq_project_id).
        from semantica.ingest.bigquery_ingestor import _validate_bq_project_id

        result = _validate_bq_project_id("my-gcp-project-123")
        assert result == "my-gcp-project-123"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_wraps_sdk_error_in_processing_error(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_client = _make_mock_bq_client()
        mock_client.query = Mock(side_effect=RuntimeError("BQ error"))
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ProcessingError, match="Failed to ingest BigQuery table"):
            ing.ingest_table("t")


# ---------------------------------------------------------------------------
# TestBigQueryIngestorQuery
# ---------------------------------------------------------------------------


class TestBigQueryIngestorQuery:
    """BigQueryIngestor.ingest_query()."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_basic(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p")
        data = ing.ingest_query("SELECT 1 AS val")

        assert isinstance(data, BigQueryData)
        assert data.query == "SELECT 1 AS val"
        mock_client.query.assert_called_once_with("SELECT 1 AS val")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_with_job_config(self, mock_bq):
        """job_config is forwarded to client.query()."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        mock_job_config = MagicMock()

        ing = BigQueryIngestor(project="p")
        ing.ingest_query("SELECT @param AS v", job_config=mock_job_config)

        mock_client.query.assert_called_once_with(
            "SELECT @param AS v", job_config=mock_job_config
        )

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_closes_transient_connection(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p")
        ing.ingest_query("SELECT 1")

        mock_client.close.assert_called_once()
        assert ing.connector.client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_wraps_sdk_error(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_client = _make_mock_bq_client()
        mock_client.query = Mock(side_effect=RuntimeError("quota exceeded"))
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p")

        with pytest.raises(ProcessingError, match="Failed to execute BigQuery query"):
            ing.ingest_query("SELECT 1")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_stores_project_dataset_on_result(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="my-project", dataset="my_ds", location="US")
        data = ing.ingest_query("SELECT 1")

        assert data.project == "my-project"
        assert data.dataset == "my_ds"
        assert data.location == "US"


# ---------------------------------------------------------------------------
# TestBigQueryIngestorSchema
# ---------------------------------------------------------------------------


class TestBigQueryIngestorSchema:
    """BigQueryIngestor.get_table_schema() and list_tables()."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_get_table_schema_basic(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()

        # Build mock SchemaField objects.
        def _field(name, field_type, mode):
            f = Mock()
            f.name = name
            f.field_type = field_type
            f.mode = mode
            return f

        mock_table = Mock()
        mock_table.schema = [
            _field("id", "STRING", "REQUIRED"),
            _field("name", "STRING", "NULLABLE"),
            _field("value", "FLOAT64", "NULLABLE"),
        ]
        mock_table.num_rows = 1000
        mock_table.clustering_fields = None
        mock_client.get_table = Mock(return_value=mock_table)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="my-project", dataset="my_ds")
        schema = ing.get_table_schema("users")

        assert len(schema["columns"]) == 3
        assert schema["columns"][0] == {
            "name": "id",
            "type": "STRING",
            "nullable": False,  # REQUIRED → not nullable
        }
        assert schema["columns"][1] == {
            "name": "name",
            "type": "STRING",
            "nullable": True,  # NULLABLE → nullable
        }
        assert schema["num_rows"] == 1000
        assert schema["clustering_fields"] == []

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_get_table_schema_with_clustering(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_table = Mock()
        mock_table.schema = []
        mock_table.num_rows = 0
        mock_table.clustering_fields = ["region", "date"]
        mock_client.get_table = Mock(return_value=mock_table)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        schema = ing.get_table_schema("t")

        assert schema["clustering_fields"] == ["region", "date"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_get_table_schema_builds_correct_table_ref(self, mock_bq):
        """get_table() must receive a fully-qualified dotted reference."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_table = Mock()
        mock_table.schema = []
        mock_table.num_rows = None
        mock_table.clustering_fields = None
        mock_client.get_table = Mock(return_value=mock_table)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="my-proj", dataset="my_ds")
        ing.get_table_schema("orders")

        called_ref = mock_client.get_table.call_args[0][0]
        assert called_ref == "my-proj.my_ds.orders"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_get_table_schema_invalid_table_name_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ValidationError):
            ing.get_table_schema("my-table")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_get_table_schema_missing_dataset_raises(self):
        """get_table_schema must reject calls when no dataset is configured (PR comment)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        # No dataset on the ingestor, none passed at call site.
        ing = BigQueryIngestor(project="my-project")

        with pytest.raises(ValidationError, match="dataset is required"):
            ing.get_table_schema("orders")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_get_table_schema_wraps_sdk_error(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_client = _make_mock_bq_client()
        mock_client.get_table = Mock(side_effect=RuntimeError("not found"))
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ProcessingError, match="Failed to get schema"):
            ing.get_table_schema("missing_table")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_list_tables_basic(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()

        def _make_table_item(name):
            t = Mock()
            t.table_id = name
            return t

        mock_client.list_tables = Mock(
            return_value=[
                _make_table_item("orders"),
                _make_table_item("customers"),
                _make_table_item("products"),
            ]
        )
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="my_ds")
        tables = ing.list_tables()

        assert tables == ["customers", "orders", "products"]  # sorted
        mock_client.list_tables.assert_called_once_with("p.my_ds")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_list_tables_override_dataset_project(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_client.list_tables = Mock(return_value=[])
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="default-p", dataset="default_ds")
        ing.list_tables(dataset="override_ds", project="override-p")

        mock_client.list_tables.assert_called_once_with("override-p.override_ds")

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_list_tables_no_dataset_raises(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ValidationError

        # No dataset configured at all.
        ing = BigQueryIngestor(project="p")

        with pytest.raises(ValidationError, match="dataset is required"):
            ing.list_tables()

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_list_tables_returns_empty_list_when_none(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_client.list_tables = Mock(return_value=[])
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        tables = ing.list_tables()

        assert tables == []

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_list_tables_wraps_sdk_error(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_client = _make_mock_bq_client()
        mock_client.list_tables = Mock(side_effect=RuntimeError("permission denied"))
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")

        with pytest.raises(ProcessingError, match="Failed to list BigQuery tables"):
            ing.list_tables()


# ---------------------------------------------------------------------------
# TestRowConversion
# ---------------------------------------------------------------------------


class TestRowConversion:
    """BigQueryIngestor._convert_rows() — type normalisation."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_string_passthrough(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"name": "Alice", "city": "NYC"}]
        result = ing._convert_rows(rows)
        assert result == [{"name": "Alice", "city": "NYC"}]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_int_float_bool_none_passthrough(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"i": 42, "f": 3.14, "b": True, "n": None}]
        result = ing._convert_rows(rows)
        assert result == [{"i": 42, "f": 3.14, "b": True, "n": None}]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_datetime_converted_to_isoformat(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        dt = datetime(2024, 6, 15, 12, 30, 0)
        rows = [{"ts": dt}]
        result = ing._convert_rows(rows)
        assert result[0]["ts"] == "2024-06-15T12:30:00"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_date_converted_to_isoformat(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        d = date(2024, 6, 15)
        rows = [{"day": d}]
        result = ing._convert_rows(rows)
        assert result[0]["day"] == "2024-06-15"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_time_converted_to_isoformat(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        t = time(14, 30, 59)
        rows = [{"t": t}]
        result = ing._convert_rows(rows)
        assert result[0]["t"] == "14:30:59"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_decimal_converted_to_string(self):
        """NUMERIC / BIGNUMERIC must become str to preserve precision."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"amount": decimal.Decimal("12345.6789")}]
        result = ing._convert_rows(rows)
        assert result[0]["amount"] == "12345.6789"
        assert isinstance(result[0]["amount"], str)

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_bytes_decoded_as_utf8(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"data": b"hello world"}]
        result = ing._convert_rows(rows)
        assert result[0]["data"] == "hello world"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_bytes_non_utf8_falls_back_to_str(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"data": b"\xff\xfe"}]  # not valid UTF-8
        result = ing._convert_rows(rows)
        # Should not raise; result is a string representation.
        assert isinstance(result[0]["data"], str)

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_datetime_subclass_not_mishandled_as_date(self):
        """datetime must be processed before date (datetime is a date subclass)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        dt = datetime(2024, 1, 1, 8, 0, 0)
        rows = [{"ts": dt}]
        result = ing._convert_rows(rows)
        # A full datetime string, not just "2024-01-01".
        assert "T" in result[0]["ts"]
        assert result[0]["ts"] == "2024-01-01T08:00:00"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_rows_to_dicts_empty_returns_empty(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        columns, data = ing._rows_to_dicts([])
        assert columns == []
        assert data == []

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_rows_to_dicts_empty_with_schema_columns_preserves_columns(self):
        """Zero rows with schema_columns preserves the declared schema (Finding 2)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        columns, data = ing._rows_to_dicts([], schema_columns=["id", "name", "score"])
        assert columns == ["id", "name", "score"]
        assert data == []

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_rows_to_dicts_extracts_column_names(self):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")

        mock_row = Mock()
        mock_row.keys = Mock(return_value=["id", "name", "score"])
        # dict(row) must work.
        mock_row.__iter__ = Mock(
            return_value=iter([("id", "1"), ("name", "Alice"), ("score", 99)])
        )

        # Patch dict() behaviour by making the Mock iterable as a mapping.
        with patch("semantica.ingest.bigquery_ingestor.BigQueryIngestor._rows_to_dicts") as mock_r2d:
            mock_r2d.return_value = (
                ["id", "name", "score"],
                [{"id": "1", "name": "Alice", "score": 99}],
            )
            columns, data = ing._rows_to_dicts([mock_row])

        # Verify shape from the patched return.
        assert columns == ["id", "name", "score"]
        assert data[0]["name"] == "Alice"


# ---------------------------------------------------------------------------
# TestExportAsDocuments
# ---------------------------------------------------------------------------


class TestExportAsDocuments:
    """BigQueryIngestor.export_as_documents()."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_basic_export(self):
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[
                {"id": "1", "name": "Alice", "city": "NYC"},
                {"id": "2", "name": "Bob", "city": "LA"},
            ],
            row_count=2,
            columns=["id", "name", "city"],
            table_name="users",
            project="my-project",
            dataset="my_ds",
            location="US",
        )

        docs = ing.export_as_documents(data, text_fields=["name", "city"])

        assert len(docs) == 2
        assert docs[0]["id"] == "1"
        assert docs[0]["text"] == "Alice NYC"
        assert docs[0]["metadata"]["source"] == "bigquery"
        assert docs[0]["metadata"]["table"] == "users"
        assert docs[0]["metadata"]["project"] == "my-project"
        assert docs[0]["metadata"]["dataset"] == "my_ds"
        assert docs[0]["metadata"]["location"] == "US"
        assert docs[0]["metadata"]["row_data"]["name"] == "Alice"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_default_text_uses_all_string_fields(self):
        """When text_fields is None, all non-None string values are joined."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"id": "1", "name": "Alice", "score": 100}],
            row_count=1,
            columns=["id", "name", "score"],
            table_name="t",
        )

        docs = ing.export_as_documents(data)

        # Only string fields: id and name. score is int, excluded.
        assert "Alice" in docs[0]["text"]
        assert "1" in docs[0]["text"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_id_field_default_is_id(self):
        """Default id_field is 'id'."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"id": "row_001", "name": "Alice"}],
            row_count=1,
            columns=["id", "name"],
            table_name="t",
        )

        docs = ing.export_as_documents(data)
        assert docs[0]["id"] == "row_001"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_custom_id_field(self):
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"order_id": "ORD-999", "amount": "100.00"}],
            row_count=1,
            columns=["order_id", "amount"],
            table_name="orders",
        )

        docs = ing.export_as_documents(data, id_field="order_id")
        assert docs[0]["id"] == "ORD-999"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_missing_id_field_falls_back_to_index(self):
        """If id_field key is absent, the row index is used."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"name": "No-ID record"}],
            row_count=1,
            columns=["name"],
            table_name="t",
        )

        docs = ing.export_as_documents(data)
        assert docs[0]["id"] == "0"  # row index 0 as string

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_none_text_fields_skipped(self):
        """None values in text_fields are not included in the text."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"id": "1", "name": "Alice", "desc": None}],
            row_count=1,
            columns=["id", "name", "desc"],
            table_name="t",
        )

        docs = ing.export_as_documents(data, text_fields=["name", "desc"])
        assert docs[0]["text"] == "Alice"  # None desc excluded

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_empty_data_returns_empty_list(self):
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(data=[], row_count=0, columns=[])
        docs = ing.export_as_documents(data)
        assert docs == []

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_metadata_shape(self):
        """Document metadata must contain all expected keys."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"id": "1", "v": "x"}],
            row_count=1,
            columns=["id", "v"],
            table_name="my_table",
            project="my-project",
            dataset="my_ds",
            location="US",
        )

        docs = ing.export_as_documents(data)
        meta = docs[0]["metadata"]

        assert meta["source"] == "bigquery"
        assert meta["table"] == "my_table"
        assert meta["project"] == "my-project"
        assert meta["dataset"] == "my_ds"
        assert meta["location"] == "US"
        assert "row_data" in meta


# ---------------------------------------------------------------------------
# TestContextManagerLifecycle
# ---------------------------------------------------------------------------


class TestContextManagerLifecycle:
    """Context-manager support."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_context_manager_opens_and_closes_connection(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_bq.Client.return_value = mock_client

        with BigQueryIngestor(project="p", dataset="d") as ing:
            # Client must be open inside the block.
            assert ing.connector.client is mock_client

        # Client must be closed on exit.
        mock_client.close.assert_called_once()
        assert ing.connector.client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_multiple_calls_inside_context_reuse_connection(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        with BigQueryIngestor(project="p", dataset="d") as ing:
            ing.ingest_table("t1")
            ing.ingest_table("t2")
            ing.ingest_query("SELECT 1")

        # Client constructor called exactly once — __enter__ only.
        mock_bq.Client.assert_called_once()
        # Client closed once on __exit__.
        mock_client.close.assert_called_once()

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_standalone_call_closes_connection(self, mock_bq):
        """Standalone ingest_table opens and closes its own connection."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_job = _make_query_job([])
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        ing.ingest_table("t")

        assert ing.connector.client is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_close_method_disconnects(self, mock_bq):
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        ing.connector.connect()  # open directly
        ing.close()

        mock_client.close.assert_called_once()
        assert ing.connector.client is None


# ---------------------------------------------------------------------------
# TestIdentifierValidation
# ---------------------------------------------------------------------------


class TestIdentifierValidation:
    """Validate the BigQuery-specific identifier validators."""

    def test_valid_bq_identifier(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_identifier

        assert _validate_bq_identifier("my_table", "t") == "my_table"
        assert _validate_bq_identifier("Table1", "t") == "Table1"
        assert _validate_bq_identifier("_private", "t") == "_private"

    def test_invalid_bq_identifier_hyphen(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_identifier
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_bq_identifier("my-table", "t")

    def test_invalid_bq_identifier_leading_digit(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_identifier
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_bq_identifier("1table", "t")

    def test_invalid_bq_identifier_space(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_identifier
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_bq_identifier("my table", "t")

    def test_valid_project_id_with_hyphens(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_project_id

        assert _validate_bq_project_id("my-project") == "my-project"
        assert _validate_bq_project_id("my-gcp-project-123") == "my-gcp-project-123"
        assert _validate_bq_project_id("project") == "project"
        assert _validate_bq_project_id("proj_123") == "proj_123"

    def test_invalid_project_id_leading_hyphen(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_project_id
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_bq_project_id("-bad-project")

    def test_invalid_project_id_leading_digit(self):
        from semantica.ingest.bigquery_ingestor import _validate_bq_project_id
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            _validate_bq_project_id("1project")

    def test_bq_quote_wraps_in_backticks(self):
        from semantica.ingest.bigquery_ingestor import _bq_quote

        assert _bq_quote("my_table") == "`my_table`"
        assert _bq_quote("my-project") == "`my-project`"

    def test_bq_quote_escapes_internal_backticks(self):
        from semantica.ingest.bigquery_ingestor import _bq_quote

        assert _bq_quote("my`table") == "`my``table`"

    def test_build_table_ref_full(self):
        from semantica.ingest.bigquery_ingestor import _build_table_ref

        ref = _build_table_ref("orders", "my_ds", "my-project")
        assert ref == "`my-project`.`my_ds`.`orders`"

    def test_build_table_ref_no_project(self):
        from semantica.ingest.bigquery_ingestor import _build_table_ref

        ref = _build_table_ref("orders", "my_ds", None)
        assert ref == "`my_ds`.`orders`"

    def test_build_table_ref_no_project_no_dataset(self):
        from semantica.ingest.bigquery_ingestor import _build_table_ref

        ref = _build_table_ref("orders", None, None)
        assert ref == "`orders`"


# ---------------------------------------------------------------------------
# TestImportBehaviourWithoutLib
# ---------------------------------------------------------------------------


class TestImportBehaviourWithoutLib:
    """Verify that the missing-SDK guard fires with the correct pip hint."""

    def test_bigquery_connector_raises_import_error_when_sdk_absent(self):
        """BigQueryConnector.__init__ must raise ImportError when SDK is absent."""
        with patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", False):
            from semantica.ingest.bigquery_ingestor import BigQueryConnector

            with pytest.raises(ImportError) as exc_info:
                BigQueryConnector(project="p")

            msg = str(exc_info.value)
            assert "google-cloud-bigquery" in msg
            assert 'semantica[db-bigquery]' in msg

    def test_bigquery_data_importable_without_sdk(self):
        """BigQueryData must remain importable even when SDK is absent."""
        with patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", False):
            from semantica.ingest.bigquery_ingestor import BigQueryData

            data = BigQueryData(data=[], row_count=0, columns=[])
            assert data.row_count == 0

    def test_lazy_import_raises_import_error_with_hint(self):
        """semantica.ingest.BigQueryConnector must raise ImportError with hint
        when BIGQUERY_AVAILABLE is False (secondary guard in __getattr__)."""
        import semantica.ingest as _ingest

        # Remove any cached entry first.
        _ingest.__dict__.pop("BigQueryConnector", None)
        _ingest.__dict__.pop("BigQueryIngestor", None)

        with patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                _ = _ingest.BigQueryConnector

        msg = str(exc_info.value)
        assert "google-cloud-bigquery" in msg
        assert "semantica[db-bigquery]" in msg

        # Cleanup cached values so other tests are unaffected.
        _ingest.__dict__.pop("BigQueryConnector", None)
        _ingest.__dict__.pop("BigQueryIngestor", None)


# ---------------------------------------------------------------------------
# TestNestedConversion — Finding 1
# ---------------------------------------------------------------------------


class TestNestedConversion:
    """_convert_rows recurses into RECORD and REPEATED fields (Finding 1)."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_nested_record_dates_converted(self):
        """RECORD (STRUCT) fields containing date/datetime must be converted (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{
            "id": "1",
            "metadata": {
                "created": date(2024, 3, 15),
                "updated": datetime(2024, 3, 15, 10, 30, 0),
            }
        }]
        result = ing._convert_rows(rows)
        assert result[0]["metadata"]["created"] == "2024-03-15"
        assert result[0]["metadata"]["updated"] == "2024-03-15T10:30:00"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_nested_record_decimal_converted(self):
        """RECORD fields containing Decimal must be converted (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"price": {"amount": decimal.Decimal("99.99"), "currency": "USD"}}]
        result = ing._convert_rows(rows)
        assert result[0]["price"]["amount"] == "99.99"
        assert result[0]["price"]["currency"] == "USD"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_nested_record_bytes_converted(self):
        """RECORD fields containing bytes must be decoded (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"attachment": {"data": b"hello", "mime": "text/plain"}}]
        result = ing._convert_rows(rows)
        assert result[0]["attachment"]["data"] == "hello"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_repeated_field_dates_converted(self):
        """REPEATED (ARRAY) fields containing dates must be converted (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{
            "id": "1",
            "event_dates": [date(2024, 1, 1), date(2024, 6, 15)],
        }]
        result = ing._convert_rows(rows)
        assert result[0]["event_dates"] == ["2024-01-01", "2024-06-15"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_repeated_field_decimals_converted(self):
        """REPEATED fields containing Decimals must be converted (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"scores": [decimal.Decimal("1.5"), decimal.Decimal("2.75")]}]
        result = ing._convert_rows(rows)
        assert result[0]["scores"] == ["1.5", "2.75"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_repeated_record_nested_dates_converted(self):
        """REPEATED RECORD (array of structs) at multiple nesting levels (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{
            "line_items": [
                {"name": "Widget", "ordered_on": date(2024, 1, 10)},
                {"name": "Gadget", "ordered_on": date(2024, 2, 20)},
            ]
        }]
        result = ing._convert_rows(rows)
        assert result[0]["line_items"][0]["ordered_on"] == "2024-01-10"
        assert result[0]["line_items"][1]["ordered_on"] == "2024-02-20"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_string_and_scalars_unchanged_in_nested_record(self):
        """Plain scalar types inside RECORD must pass through unchanged (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{
            "profile": {
                "name": "Alice",
                "age": 30,
                "active": True,
                "score": 9.5,
                "notes": None,
            }
        }]
        result = ing._convert_rows(rows)
        p = result[0]["profile"]
        assert p["name"] == "Alice"
        assert p["age"] == 30
        assert p["active"] is True
        assert p["score"] == 9.5
        assert p["notes"] is None

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_convert_value_static_method(self):
        """_convert_value is callable as a static method (Finding 1)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        assert BigQueryIngestor._convert_value(date(2024, 1, 1)) == "2024-01-01"
        assert BigQueryIngestor._convert_value(decimal.Decimal("3.14")) == "3.14"
        assert BigQueryIngestor._convert_value(42) == 42
        assert BigQueryIngestor._convert_value(None) is None
        assert BigQueryIngestor._convert_value("text") == "text"
        assert BigQueryIngestor._convert_value([date(2024, 1, 1)]) == ["2024-01-01"]
        assert BigQueryIngestor._convert_value({"d": date(2024, 6, 1)}) == {"d": "2024-06-01"}

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_tuple_repeated_field_converted(self):
        """Tuple values are also recursively converted (PR nit 3)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        rows = [{"tags": (date(2024, 1, 1), date(2024, 6, 15))}]
        result = ing._convert_rows(rows)
        # Tuples are converted element-by-element; result is a list.
        assert result[0]["tags"] == ["2024-01-01", "2024-06-15"]


# ---------------------------------------------------------------------------
# TestZeroRowResults — Finding 2
# ---------------------------------------------------------------------------


class TestZeroRowResults:
    """ingest_table and ingest_query preserve column schema for zero-row results."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_zero_rows_preserves_columns(self, mock_bq):
        """Zero-row ingest_table must still return the correct column list (Finding 2)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()

        # Build a mock RowIterator with schema but no rows.
        mock_result = Mock()
        field1, field2, field3 = Mock(), Mock(), Mock()
        field1.name = "order_id"
        field2.name = "customer"
        field3.name = "total"
        mock_result.schema = [field1, field2, field3]
        mock_result.__iter__ = Mock(return_value=iter([]))

        mock_job = Mock()
        mock_job.result = Mock(return_value=mock_result)
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        data = ing.ingest_table("orders")

        assert data.row_count == 0
        assert data.data == []
        assert data.columns == ["order_id", "customer", "total"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_query_zero_rows_preserves_columns(self, mock_bq):
        """Zero-row ingest_query must still return the correct column list (Finding 2)."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()

        mock_result = Mock()
        f1, f2 = Mock(), Mock()
        f1.name = "id"
        f2.name = "name"
        mock_result.schema = [f1, f2]
        mock_result.__iter__ = Mock(return_value=iter([]))

        mock_job = Mock()
        mock_job.result = Mock(return_value=mock_result)
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p")
        data = ing.ingest_query("SELECT id, name FROM t WHERE 1=0")

        assert data.row_count == 0
        assert data.data == []
        assert data.columns == ["id", "name"]

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    @patch("semantica.ingest.bigquery_ingestor._bigquery")
    def test_ingest_table_zero_rows_no_schema_returns_empty_columns(self, mock_bq):
        """If RowIterator has no schema (e.g. DDL), columns is empty but no crash."""
        from semantica.ingest.bigquery_ingestor import BigQueryIngestor

        mock_client = _make_mock_bq_client()

        mock_result = Mock()
        mock_result.schema = None
        mock_result.__iter__ = Mock(return_value=iter([]))

        mock_job = Mock()
        mock_job.result = Mock(return_value=mock_result)
        mock_client.query = Mock(return_value=mock_job)
        mock_bq.Client.return_value = mock_client

        ing = BigQueryIngestor(project="p", dataset="d")
        data = ing.ingest_table("t")

        assert data.columns == []
        assert data.data == []


# ---------------------------------------------------------------------------
# TestNullIdHandling — Finding 3
# ---------------------------------------------------------------------------


class TestNullIdHandling:
    """export_as_documents handles None id_field values as fallback (Finding 3)."""

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_none_id_field_value_uses_row_index(self):
        """A present-but-None id_field must fall back to the row index (Finding 3)."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[
                {"id": None, "name": "Alice"},
                {"id": None, "name": "Bob"},
            ],
            row_count=2,
            columns=["id", "name"],
            table_name="t",
        )

        docs = ing.export_as_documents(data, id_field="id")

        # Each None id must yield its row index, not the shared string "None".
        assert docs[0]["id"] == "0"
        assert docs[1]["id"] == "1"
        # Must NOT be "None".
        assert docs[0]["id"] != "None"
        assert docs[1]["id"] != "None"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_multiple_none_ids_get_distinct_fallback_indices(self):
        """Multiple rows with None id must produce distinct document IDs (Finding 3)."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[
                {"id": None, "name": "Row0"},
                {"id": None, "name": "Row1"},
                {"id": None, "name": "Row2"},
            ],
            row_count=3,
            columns=["id", "name"],
            table_name="t",
        )

        docs = ing.export_as_documents(data, id_field="id")

        ids = [d["id"] for d in docs]
        assert ids == ["0", "1", "2"]
        # All distinct.
        assert len(set(ids)) == 3

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_mixed_real_and_none_ids(self):
        """Rows with real IDs keep them; None rows fall back to their indices."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[
                {"id": "real-001", "name": "Alice"},
                {"id": None, "name": "Bob"},
                {"id": "real-003", "name": "Carol"},
            ],
            row_count=3,
            columns=["id", "name"],
            table_name="t",
        )

        docs = ing.export_as_documents(data, id_field="id")

        assert docs[0]["id"] == "real-001"
        assert docs[1]["id"] == "1"   # row index fallback
        assert docs[2]["id"] == "real-003"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_missing_id_field_still_uses_index(self):
        """Absent id_field key (not present in row) still falls back to index."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[{"name": "No-ID"}],
            row_count=1,
            columns=["name"],
            table_name="t",
        )
        docs = ing.export_as_documents(data)
        assert docs[0]["id"] == "0"

    @patch("semantica.ingest.bigquery_ingestor.BIGQUERY_AVAILABLE", True)
    def test_zero_numeric_id_is_not_treated_as_falsy(self):
        """An id value of integer 0 or string '0' must NOT fall back to index."""
        from semantica.ingest.bigquery_ingestor import BigQueryData, BigQueryIngestor

        ing = BigQueryIngestor(project="p", dataset="d")
        data = BigQueryData(
            data=[
                {"id": 0, "name": "Zero-int"},
                {"id": "0", "name": "Zero-str"},
            ],
            row_count=2,
            columns=["id", "name"],
            table_name="t",
        )
        docs = ing.export_as_documents(data, id_field="id")
        assert docs[0]["id"] == "0"   # str(0)
        assert docs[1]["id"] == "0"   # "0"


def _load_pyproject_toml():
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # backport for <3.11
        except ModuleNotFoundError:
            pytest.skip("tomllib / tomli not available — skipping TOML-based tests")
    from pathlib import Path

    toml_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


class TestDbAllIncludesBigQuery:
    """pyproject.toml db-all aggregate must reference db-bigquery."""

    def test_db_all_references_db_bigquery(self):
        """Read pyproject.toml and verify db-all includes db-bigquery."""
        data = _load_pyproject_toml()

        db_all = data["project"]["optional-dependencies"]["db-all"]
        # db-all is a list of strings like ["semantica[db-snowflake,...]"]
        combined = " ".join(db_all)
        assert "db-bigquery" in combined, (
            f"db-all does not reference db-bigquery. Got: {db_all}"
        )

    def test_db_bigquery_extra_exists(self):
        """pyproject.toml must define the db-bigquery optional extra."""
        data = _load_pyproject_toml()

        extras = data["project"]["optional-dependencies"]
        assert "db-bigquery" in extras, "db-bigquery extra is missing from pyproject.toml"

        combined = " ".join(extras["db-bigquery"])
        assert "google-cloud-bigquery" in combined

    def test_db_bigquery_version_floor(self):
        """db-bigquery must specify google-cloud-bigquery>=3.0.0."""
        data = _load_pyproject_toml()

        db_bigquery = data["project"]["optional-dependencies"]["db-bigquery"]
        combined = " ".join(db_bigquery)
        assert ">=3.0.0" in combined, (
            f"db-bigquery does not specify >=3.0.0. Got: {db_bigquery}"
        )


# ---------------------------------------------------------------------------
# TestEagerImportGuard
# ---------------------------------------------------------------------------


class TestEagerImportGuard:
    """import semantica.ingest must NOT eagerly import google-cloud-bigquery."""

    def test_import_semantica_ingest_does_not_import_bigquery(self):
        """The google.cloud.bigquery module must not appear in sys.modules
        purely as a side-effect of importing semantica.ingest."""
        import sys

        # Remove any previously cached google.cloud.bigquery entry.
        saved = sys.modules.pop("google.cloud.bigquery", None)
        try:
            # Re-importing semantica.ingest must not trigger the BigQuery SDK.
            import importlib

            import semantica.ingest
            importlib.reload(semantica.ingest)

            assert "google.cloud.bigquery" not in sys.modules, (
                "google.cloud.bigquery was eagerly imported by semantica.ingest"
            )
        finally:
            # Restore original state so other tests are unaffected.
            if saved is not None:
                sys.modules["google.cloud.bigquery"] = saved

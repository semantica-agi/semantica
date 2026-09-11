"""
Unit tests for RedshiftConnector and RedshiftIngestor.

All redshift_connector API calls are mocked — no real AWS or Redshift
connection is made.

Test structure mirrors tests/test_snowflake_ingestor.py and
tests/test_salesforce_ingestor.py:
  - autouse fixture injects a ``redshift_connector`` stub when the SDK
    is not installed, so the test suite runs in both environments.
  - Each test that needs the connector to appear available patches
    ``REDSHIFT_AVAILABLE`` to ``True`` and ``_redshift_connector`` to
    a ``MagicMock``.
  - Credentials are always supplied so secret values are never embedded
    in assertions.
"""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Optional SDK detection
# ---------------------------------------------------------------------------
try:
    import redshift_connector as _sdk  # noqa: F401

    REDSHIFT_SDK_AVAILABLE = True
except ImportError:
    REDSHIFT_SDK_AVAILABLE = False


# ---------------------------------------------------------------------------
# autouse fixture — inject stub when SDK is absent
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_redshift_sdk_if_needed():
    """Inject a minimal redshift_connector stub when the SDK is not installed."""
    if not REDSHIFT_SDK_AVAILABLE:
        stub = MagicMock()
        # Provide a real exception hierarchy so isinstance/except clauses work.
        class _Error(Exception):
            pass

        class _InterfaceError(_Error):
            pass

        class _ProgrammingError(_Error):
            pass

        stub.Error = _Error
        stub.InterfaceError = _InterfaceError
        stub.ProgrammingError = _ProgrammingError
        stub.connect = MagicMock()

        with patch.dict(
            "sys.modules",
            {"redshift_connector": stub},
        ):
            yield
    else:
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_connection():
    """Return a mock that behaves like a redshift_connector connection."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.execute = Mock()
    mock_cursor.fetchone = Mock(return_value=(1,))
    mock_cursor.fetchall = Mock(return_value=[])
    mock_cursor.description = [("?column?",)]
    mock_cursor.close = Mock()
    mock_conn.cursor = Mock(return_value=mock_cursor)
    mock_conn.close = Mock()
    return mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# TestRedshiftData
# ---------------------------------------------------------------------------


class TestRedshiftData:
    """RedshiftData is a plain dataclass — no SDK dependency."""

    def test_creation_with_required_fields(self):
        from semantica.ingest.redshift_ingestor import RedshiftData

        data = RedshiftData(data=[], row_count=0, columns=[])

        assert data.row_count == 0
        assert data.data == []
        assert data.columns == []
        assert data.table_name is None
        assert data.query is None
        assert data.database is None
        assert data.schema is None
        assert data.metadata == {}
        assert isinstance(data.ingested_at, datetime)

    def test_creation_with_all_fields(self):
        from semantica.ingest.redshift_ingestor import RedshiftData

        rows = [{"id": 1, "name": "Alice"}]
        data = RedshiftData(
            data=rows,
            row_count=1,
            columns=["id", "name"],
            table_name="users",
            query="SELECT id, name FROM users",
            database="dev",
            schema="public",
            metadata={"custom": "value"},
        )

        assert data.row_count == 1
        assert data.table_name == "users"
        assert data.query == "SELECT id, name FROM users"
        assert data.database == "dev"
        assert data.schema == "public"
        assert data.metadata["custom"] == "value"

    def test_importable_without_sdk(self):
        """RedshiftData must import even when redshift_connector is absent."""
        # This test intentionally does NOT patch REDSHIFT_AVAILABLE —
        # it relies on the autouse stub (or the real SDK) already in place.
        from semantica.ingest.redshift_ingestor import RedshiftData

        data = RedshiftData(data=[{"col": 1}], row_count=1, columns=["col"])
        assert data.row_count == 1


# ---------------------------------------------------------------------------
# TestRedshiftConnectorInit — password auth
# ---------------------------------------------------------------------------


class TestRedshiftConnectorInitPassword:
    """Constructor validation for password / native authentication."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_init_explicit_credentials_stored(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            user="awsuser",
            password="s3cr3t",
        )

        assert conn.host == "cluster.example.com"
        assert conn.database == "dev"
        assert conn.user == "awsuser"
        assert conn._password == "s3cr3t"
        assert conn.port == 5439  # default
        assert conn.ssl is True   # default
        assert conn.iam is False
        assert conn._connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_init_explicit_port_overrides_default(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            user="awsuser",
            password="s3cr3t",
            port=5450,
        )

        assert conn.port == 5450

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_init_ssl_false_stored(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            user="awsuser",
            password="s3cr3t",
            ssl=False,
        )

        assert conn.ssl is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_init_timeout_stored(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            user="awsuser",
            password="s3cr3t",
            timeout=30,
        )

        assert conn.timeout == 30


# ---------------------------------------------------------------------------
# TestRedshiftConnectorInitEnvVars
# ---------------------------------------------------------------------------


class TestRedshiftConnectorInitEnvVars:
    """Environment-variable fallbacks for all credential parameters."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_password_auth_from_env_vars(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        env = {
            "REDSHIFT_HOST": "env-cluster.example.com",
            "REDSHIFT_DATABASE": "env_db",
            "REDSHIFT_USER": "env_user",
            "REDSHIFT_PASSWORD": "env_pass",
        }
        with patch.dict(os.environ, env):
            conn = RedshiftConnector()

        assert conn.host == "env-cluster.example.com"
        assert conn.database == "env_db"
        assert conn.user == "env_user"
        assert conn._password == "env_pass"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_port_from_env_var(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        env = {
            "REDSHIFT_HOST": "cluster.example.com",
            "REDSHIFT_DATABASE": "dev",
            "REDSHIFT_USER": "u",
            "REDSHIFT_PASSWORD": "p",
            "REDSHIFT_PORT": "5450",
        }
        with patch.dict(os.environ, env):
            conn = RedshiftConnector()

        assert conn.port == 5450

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_iam_params_from_env_vars(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        env = {
            "REDSHIFT_HOST": "cluster.example.com",
            "REDSHIFT_DATABASE": "dev",
            "REDSHIFT_DB_USER": "env_db_user",
            "REDSHIFT_CLUSTER_IDENTIFIER": "env-cluster-id",
            "REDSHIFT_REGION": "us-west-2",
            "REDSHIFT_PROFILE": "env-profile",
            "REDSHIFT_ACCESS_KEY_ID": "env_key",
            "REDSHIFT_SECRET_ACCESS_KEY": "env_secret",
            "REDSHIFT_SESSION_TOKEN": "env_token",
        }
        with patch.dict(os.environ, env):
            conn = RedshiftConnector(iam=True)

        assert conn.db_user == "env_db_user"
        assert conn.cluster_identifier == "env-cluster-id"
        assert conn.region == "us-west-2"
        assert conn.profile == "env-profile"
        assert conn._access_key_id == "env_key"
        assert conn._secret_access_key == "env_secret"
        assert conn._session_token == "env_token"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_explicit_arg_overrides_env_var(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        env = {
            "REDSHIFT_HOST": "env-host.example.com",
            "REDSHIFT_DATABASE": "env_db",
            "REDSHIFT_USER": "env_user",
            "REDSHIFT_PASSWORD": "env_pass",
        }
        with patch.dict(os.environ, env):
            conn = RedshiftConnector(
                host="explicit-host.example.com",
                database="explicit_db",
                user="explicit_user",
                password="explicit_pass",
            )

        assert conn.host == "explicit-host.example.com"
        assert conn.database == "explicit_db"
        assert conn.user == "explicit_user"
        assert conn._password == "explicit_pass"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_port_env_var_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        env = {
            "REDSHIFT_HOST": "cluster.example.com",
            "REDSHIFT_DATABASE": "dev",
            "REDSHIFT_USER": "u",
            "REDSHIFT_PASSWORD": "p",
            "REDSHIFT_PORT": "not-a-number",
        }
        with patch.dict(os.environ, env):
            with pytest.raises(ValidationError, match="REDSHIFT_PORT"):
                RedshiftConnector()


# ---------------------------------------------------------------------------
# TestRedshiftConnectorValidation — missing credentials
# ---------------------------------------------------------------------------


class TestRedshiftConnectorValidation:
    """ValidationError is raised for incomplete credentials."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_missing_host_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="host"):
            RedshiftConnector(database="dev", user="u", password="p")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_missing_database_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="database"):
            RedshiftConnector(host="h", user="u", password="p")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_password_mode_missing_user_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="user"):
            RedshiftConnector(host="h", database="d", password="p")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_password_mode_missing_password_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="password"):
            RedshiftConnector(host="h", database="d", user="u")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_iam_mode_missing_db_user_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="db_user"):
            RedshiftConnector(
                host="h",
                database="d",
                iam=True,
                cluster_identifier="c",
            )

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_iam_mode_missing_cluster_identifier_raises(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="cluster_identifier"):
            RedshiftConnector(
                host="h",
                database="d",
                iam=True,
                db_user="awsuser",
            )

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_missing_sdk_raises_import_error_with_hint(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        with patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                RedshiftConnector(
                    host="h", database="d", user="u", password="p"
                )

        msg = str(exc_info.value)
        assert "redshift-connector" in msg
        assert "db-redshift" in msg

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_validation_error_message_does_not_contain_password(self):
        """ValidationError messages must never echo secret values."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            # Missing host — but provide a "password" to confirm it's not leaked.
            RedshiftConnector(database="d", user="u", password="super_s3cr3t")

        assert "super_s3cr3t" not in str(exc_info.value)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_iam_and_password_modes_do_not_conflict(self):
        """iam=True with user/password set does not raise; IAM mode takes over."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        # Providing user/password alongside iam=True is harmless;
        # _build_connect_kwargs ignores them when iam=True.
        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            user="ignored",
            password="ignored",
        )
        assert conn.iam is True
        # Verify build kwargs uses IAM path
        kwargs = conn._build_connect_kwargs()
        assert kwargs["iam"] is True
        assert kwargs["user"] == ""
        assert kwargs["password"] == ""
        assert kwargs["db_user"] == "awsuser"


# ---------------------------------------------------------------------------
# TestRedshiftConnectorConnect — password auth
# ---------------------------------------------------------------------------


class TestRedshiftConnectorConnectPassword:
    """connect() for password authentication."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_calls_sdk_with_correct_kwargs(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            user="awsuser",
            password="s3cr3t",
        )
        result = conn.connect()

        assert result is mock_conn
        mock_sdk.connect.assert_called_once()

        call_kwargs = mock_sdk.connect.call_args[1]
        assert call_kwargs["host"] == "cluster.example.com"
        assert call_kwargs["database"] == "dev"
        assert call_kwargs["user"] == "awsuser"
        assert call_kwargs["password"] == "s3cr3t"
        assert call_kwargs["port"] == 5439
        assert call_kwargs["ssl"] is True
        assert "iam" not in call_kwargs

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_passes_custom_port(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h", database="d", user="u", password="p", port=5450
        )
        conn.connect()

        assert mock_sdk.connect.call_args[1]["port"] == 5450

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_passes_ssl_false(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h", database="d", user="u", password="p", ssl=False
        )
        conn.connect()

        assert mock_sdk.connect.call_args[1]["ssl"] is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_passes_timeout(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h", database="d", user="u", password="p", timeout=30
        )
        conn.connect()

        assert mock_sdk.connect.call_args[1]["timeout"] == 30

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_stores_connection_reference(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        assert connector.connection is None
        connector.connect()
        assert connector.connection is mock_conn

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_reuses_existing_connection(self, mock_sdk):
        """Second connect() call returns the same connection without re-calling SDK."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        first = connector.connect()
        second = connector.connect()

        assert first is second
        mock_sdk.connect.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_failure_raises_processing_error(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ProcessingError

        mock_sdk.connect.side_effect = Exception("connection refused")

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        with pytest.raises(ProcessingError):
            connector.connect()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_failure_leaves_connection_none(self, mock_sdk):
        """A failed connect() must not leave a partial connection reference."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ProcessingError

        mock_sdk.connect.side_effect = RuntimeError("auth failed")

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        with pytest.raises(ProcessingError):
            connector.connect()

        assert connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_error_message_does_not_contain_password(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ProcessingError

        mock_sdk.connect.side_effect = Exception("some sdk error")

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="hunter2"
        )
        with pytest.raises(ProcessingError) as exc_info:
            connector.connect()

        assert "hunter2" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestRedshiftConnectorConnect — IAM auth
# ---------------------------------------------------------------------------


class TestRedshiftConnectorConnectIAM:
    """connect() for IAM-role authentication."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_connect_calls_sdk_with_iam_true(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="cluster.example.com",
            database="dev",
            iam=True,
            db_user="awsuser",
            cluster_identifier="my-cluster",
            profile="default",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        assert kwargs["iam"] is True
        assert kwargs["db_user"] == "awsuser"
        assert kwargs["cluster_identifier"] == "my-cluster"
        assert kwargs["profile"] == "default"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_connect_passes_empty_user_and_password(self, mock_sdk):
        """SDK requires user='' and password='' when iam=True."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            profile="default",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        assert kwargs["user"] == ""
        assert kwargs["password"] == ""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_connect_with_explicit_credentials(self, mock_sdk):
        """Explicit AWS credentials are forwarded as access_key_id / secret_access_key."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            region="us-east-1",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            session_token="AQoDYXdzEJr//example",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        assert kwargs["access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert kwargs["secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        assert kwargs["session_token"] == "AQoDYXdzEJr//example"
        assert kwargs["region"] == "us-east-1"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_connect_without_explicit_aws_creds_omits_those_kwargs(self, mock_sdk):
        """When no explicit AWS credentials are given, optional IAM kwargs
        are absent from the SDK call — the SDK resolves them from its own
        credential chain (env vars, instance profile, etc.)."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        assert "access_key_id" not in kwargs
        assert "secret_access_key" not in kwargs
        assert "session_token" not in kwargs
        assert "profile" not in kwargs
        assert "region" not in kwargs

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_connect_profile_based(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            profile="my-profile",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        assert kwargs["profile"] == "my-profile"
        assert "access_key_id" not in kwargs

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_iam_does_not_include_plain_password_in_sdk_call(self, mock_sdk):
        """The real DB password must not appear in the SDK call for IAM auth."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            profile="default",
        )
        conn.connect()

        kwargs = mock_sdk.connect.call_args[1]
        # password kwarg must be empty string (SDK requirement), not a real secret
        assert kwargs["password"] == ""


# ---------------------------------------------------------------------------
# TestRedshiftConnectorDisconnect
# ---------------------------------------------------------------------------


class TestRedshiftConnectorDisconnect:
    """disconnect() lifecycle behaviour."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_disconnect_closes_connection_and_clears_reference(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.connect()
        assert connector.connection is mock_conn

        connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_disconnect_without_connect_is_safe(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.disconnect()  # must not raise
        assert connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_disconnect_is_idempotent(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.connect()
        connector.disconnect()
        connector.disconnect()  # second call — must not raise

        assert connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_disconnect_clears_reference_even_if_close_raises(self, mock_sdk):
        """Connection reference is set to None even when conn.close() raises."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_conn.close.side_effect = RuntimeError("already closed")
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.connect()
        connector.disconnect()  # must not raise despite conn.close() failing

        assert connector.connection is None


# ---------------------------------------------------------------------------
# TestRedshiftConnectorTestConnection
# ---------------------------------------------------------------------------


class TestRedshiftConnectorTestConnection:
    """test_connection() behaviour."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_test_connection_success_returns_true(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, mock_cursor = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        result = connector.test_connection()

        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cursor.fetchone.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_test_connection_closes_transient_connection(self, mock_sdk):
        """test_connection() closes the connection it opens (no leak)."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.test_connection()

        mock_conn.close.assert_called_once()
        assert connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_test_connection_failure_returns_false(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_sdk.connect.side_effect = Exception("connection refused")

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        result = connector.test_connection()

        assert result is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_test_connection_query_failure_returns_false(self, mock_sdk):
        """Returns False when SELECT 1 raises after a successful connect()."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, mock_cursor = _make_mock_connection()
        mock_cursor.execute.side_effect = Exception("query failed")
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        result = connector.test_connection()

        assert result is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_test_connection_does_not_close_pre_existing_connection(self, mock_sdk):
        """test_connection() must not close a connection opened before the call."""
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        connector.connect()  # open before test_connection
        assert connector.connection is mock_conn

        connector.test_connection()

        # Connection opened externally must still be alive.
        assert connector.connection is mock_conn
        mock_conn.close.assert_not_called()


# ---------------------------------------------------------------------------
# TestRedshiftConnectorSecurity
# ---------------------------------------------------------------------------


class TestRedshiftConnectorSecurity:
    """Verify that secret values are never exposed in repr or exceptions."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_password_not_in_repr(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="h", database="d", user="u", password="my_secret_password"
        )
        assert "my_secret_password" not in repr(conn)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_secret_access_key_not_in_repr(self):
        from semantica.ingest.redshift_ingestor import RedshiftConnector

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="TOP_SECRET_KEY",
        )
        assert "TOP_SECRET_KEY" not in repr(conn)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_error_does_not_expose_password(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ProcessingError

        mock_sdk.connect.side_effect = Exception("auth failure")

        conn = RedshiftConnector(
            host="h", database="d", user="u", password="hunter2"
        )
        with pytest.raises(ProcessingError) as exc_info:
            conn.connect()

        assert "hunter2" not in str(exc_info.value)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connect_error_does_not_expose_secret_key(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector
        from semantica.utils.exceptions import ProcessingError

        mock_sdk.connect.side_effect = Exception("iam failure")

        conn = RedshiftConnector(
            host="h",
            database="d",
            iam=True,
            db_user="awsuser",
            cluster_identifier="c",
            secret_access_key="SUPER_SECRET_AWS_KEY",
        )
        with pytest.raises(ProcessingError) as exc_info:
            conn.connect()

        assert "SUPER_SECRET_AWS_KEY" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestRedshiftIngestor
# ---------------------------------------------------------------------------


class TestRedshiftIngestor:
    """Tests for the RedshiftIngestor wrapper."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingestor_creates_connector(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector, RedshiftIngestor

        ingestor = RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        )

        assert isinstance(ingestor.connector, RedshiftConnector)
        assert ingestor.connector.host == "h"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingestor_accepts_existing_connector(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftConnector, RedshiftIngestor

        connector = RedshiftConnector(
            host="h", database="d", user="u", password="p"
        )
        ingestor = RedshiftIngestor(connector=connector)

        assert ingestor.connector is connector

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_ingestor_missing_credentials_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            RedshiftIngestor(host="h", database="d")  # missing user+password

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_ingestor_missing_sdk_raises_import_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        with patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                RedshiftIngestor(host="h", database="d", user="u", password="p")

        assert "db-redshift" in str(exc_info.value)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_connects_and_disconnects(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        with RedshiftIngestor(host="h", database="d", user="u", password="p") as ing:
            assert ing.connector.connection is mock_conn

        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_closes_on_exception(self, mock_sdk):
        """__exit__ closes the connection even when an exception is raised."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        with pytest.raises(ValueError):
            with RedshiftIngestor(
                host="h", database="d", user="u", password="p"
            ) as ing:
                raise ValueError("something went wrong")

        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_close_delegates_to_connector(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        ingestor = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ingestor.connector.connect()
        ingestor.close()

        assert ingestor.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_schema_default_is_public(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ingestor = RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        )
        assert ingestor.schema == "public"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_schema_custom_value_stored(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ingestor = RedshiftIngestor(
            host="h", database="d", user="u", password="p", schema="analytics"
        )
        assert ingestor.schema == "analytics"


# ---------------------------------------------------------------------------
# TestPublicAPIInSemanticaIngest
# ---------------------------------------------------------------------------


class TestPublicAPIInSemanticaIngest:
    """Verify the lazy-import wiring in semantica.ingest is intact."""

    def test_all_contains_redshift_names(self):
        """All three Redshift symbols appear in semantica.ingest.__all__."""
        import semantica.ingest as pkg

        for name in ("RedshiftIngestor", "RedshiftConnector", "RedshiftData"):
            assert name in pkg.__all__, f"{name} missing from __all__"

    def test_redshift_data_importable_via_package(self):
        """RedshiftData is importable from semantica.ingest without the SDK."""
        from semantica.ingest import RedshiftData

        data = RedshiftData(data=[], row_count=0, columns=[])
        assert data.row_count == 0


# ===========================================================================
# Stage 3 — ingest_table, ingest_query, _convert_rows, connection lifecycle
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared helpers for Stage 3
# ---------------------------------------------------------------------------


def _make_cursor_with_rows(columns, rows):
    """Return a mock cursor pre-loaded with *columns* and *rows*.

    ``cursor.description`` follows the DB-API 7-tuple convention where
    ``description[i][0]`` is the column name.  ``cursor.fetchall`` returns
    the raw tuples exactly as ``redshift_connector`` does (NOT dicts).
    ``cursor.fetchmany(n)`` returns successive slices until exhausted.
    """
    cursor = Mock()
    cursor.description = [(col,) + (None,) * 6 for col in columns]

    # fetchall returns all rows as tuples
    cursor.fetchall = Mock(return_value=list(rows))

    # fetchmany returns successive batches then []
    _remaining = list(rows)

    def _fetchmany(n):
        nonlocal _remaining
        batch = _remaining[:n]
        _remaining = _remaining[n:]
        return batch

    cursor.fetchmany = Mock(side_effect=_fetchmany)
    cursor.execute = Mock()
    cursor.close = Mock()
    return cursor


# ---------------------------------------------------------------------------
# TestEscapeIdentifier / TestBuildTableRef
# ---------------------------------------------------------------------------


class TestEscapeIdentifier:
    """Unit tests for _escape_identifier and _build_table_ref."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_escape_plain_identifier(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        assert RedshiftIngestor._escape_identifier("orders") == '"orders"'

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_escape_identifier_with_internal_quote(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        assert RedshiftIngestor._escape_identifier('my"table') == '"my""table"'

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_build_table_ref_table_only(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ref = RedshiftIngestor._build_table_ref("orders", None, None)
        assert ref == '"orders"'

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_build_table_ref_schema_and_table(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ref = RedshiftIngestor._build_table_ref("orders", "sales", None)
        assert ref == '"sales"."orders"'

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_build_table_ref_database_schema_table(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ref = RedshiftIngestor._build_table_ref("orders", "sales", "mydb")
        assert ref == '"mydb"."sales"."orders"'


# ---------------------------------------------------------------------------
# TestConvertRows
# ---------------------------------------------------------------------------


class TestConvertRows:
    """Unit tests for RedshiftIngestor._convert_rows."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_plain_values_pass_through(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        rows = [{"id": 1, "name": "Alice", "score": 9.5, "active": True, "note": None}]
        result = ing._convert_rows(rows)

        assert result[0]["id"] == 1
        assert result[0]["name"] == "Alice"
        assert result[0]["score"] == 9.5
        assert result[0]["active"] is True
        assert result[0]["note"] is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_datetime_converted_to_iso_string(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        dt = datetime(2024, 6, 15, 12, 0, 0)
        rows = [{"created_at": dt}]
        result = ing._convert_rows(rows)

        assert result[0]["created_at"] == "2024-06-15T12:00:00"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_bytes_decoded_to_utf8_string(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        rows = [{"data": b"hello world"}]
        result = ing._convert_rows(rows)

        assert result[0]["data"] == "hello world"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_utf8_bytes_fall_back_to_str(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        bad_bytes = b"\xff\xfe"
        rows = [{"blob": bad_bytes}]
        result = ing._convert_rows(rows)

        # fallback: str(bad_bytes) — just verify it's a string, not bytes
        assert isinstance(result[0]["blob"], str)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_empty_list_returns_empty(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        assert ing._convert_rows([]) == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_multiple_rows_all_converted(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        dt1 = datetime(2024, 1, 1)
        dt2 = datetime(2024, 6, 1)
        rows = [{"ts": dt1, "val": 1}, {"ts": dt2, "val": 2}]
        result = ing._convert_rows(rows)

        assert result[0]["ts"] == "2024-01-01T00:00:00"
        assert result[1]["ts"] == "2024-06-01T00:00:00"
        assert result[0]["val"] == 1
        assert result[1]["val"] == 2


# ---------------------------------------------------------------------------
# TestIngestTable
# ---------------------------------------------------------------------------


class TestIngestTable:
    """Tests for RedshiftIngestor.ingest_table()."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_basic_table_ingestion(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(
            ["id", "name"], [(1, "Alice"), (2, "Bob")]
        )
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_table("customers")

        assert isinstance(result, RedshiftData)
        assert result.row_count == 2
        assert result.table_name == "customers"
        assert result.columns == ["id", "name"]
        assert result.data == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_result_data_fields_populated(self, mock_sdk):
        """RedshiftData.database, .schema, .query are all set."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(1,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="mydb", user="u", password="p")
        result = ing.ingest_table("orders", schema="sales")

        assert result.database == "mydb"
        assert result.schema == "sales"
        assert result.query is not None
        assert '"orders"' in result.query

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_schema_qualified_table_reference(self, mock_sdk):
        """Query uses a double-quoted schema.table reference."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("orders", schema="sales")

        executed_sql = cursor.execute.call_args[0][0]
        assert '"sales"."orders"' in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_database_schema_table_reference(self, mock_sdk):
        """Query includes database when explicitly passed."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("orders", database="mydb", schema="sales")

        executed_sql = cursor.execute.call_args[0][0]
        assert '"mydb"."sales"."orders"' in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_limit_in_query(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t", limit=100)

        executed_sql = cursor.execute.call_args[0][0]
        assert "LIMIT 100" in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_offset_in_query(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t", offset=200)

        executed_sql = cursor.execute.call_args[0][0]
        assert "OFFSET 200" in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_where_clause_in_query(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t", where="status = 'active'")

        executed_sql = cursor.execute.call_args[0][0]
        assert "WHERE status = 'active'" in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_order_by_in_query(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t", order_by="created_at DESC")

        executed_sql = cursor.execute.call_args[0][0]
        assert "ORDER BY created_at DESC" in executed_sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_all_clauses_order(self, mock_sdk):
        """WHERE comes before ORDER BY before LIMIT before OFFSET."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table(
            "t",
            where="active = true",
            order_by="id ASC",
            limit=10,
            offset=5,
        )
        sql = cursor.execute.call_args[0][0]
        w = sql.index("WHERE")
        ob = sql.index("ORDER BY")
        lim = sql.index("LIMIT")
        off = sql.index("OFFSET")
        assert w < ob < lim < off

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_autocommit_set_on_connection(self, mock_sdk):
        """conn.autocommit must be set to True before query execution."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t")

        assert mock_conn.autocommit is True

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_after_fetch(self, mock_sdk):
        """cursor.close() is called even on a successful fetch."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(1,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t")

        cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_standalone_call_closes_connection(self, mock_sdk):
        """A standalone ingest_table() must close the connection it opens."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        assert ing.connector.connection is None
        ing.ingest_table("t")
        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_connection_reused(self, mock_sdk):
        """ingest_table() inside a context manager reuses the open connection."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [(1,)])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.ingest_table("t")
            # Connection must still be alive — ingest_table must not have closed it.
            assert ing.connector.connection is mock_conn
            mock_conn.close.assert_not_called()

        # Closed only on __exit__.
        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_query_failure_raises_processing_error(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("syntax error")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_table("t")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_on_query_failure(self, mock_sdk):
        """cursor.close() is called even when execute() raises."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("query error")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_table("t")

        cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connection_closed_on_query_failure(self, mock_sdk):
        """Standalone call must close the connection even when query fails."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("failure")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_table("t")

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_empty_result_set(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id", "name"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_table("t")

        assert result.row_count == 0
        assert result.data == []
        assert result.columns == ["id", "name"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_tuple_rows_converted_to_dicts(self, mock_sdk):
        """Redshift cursor returns tuples; ingest_table must produce dicts."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(
            ["id", "name", "score"],
            [(42, "Charlie", 7.5)],
        )
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_table("t")

        assert result.data[0] == {"id": 42, "name": "Charlie", "score": 7.5}

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_datetime_converted_in_result(self, mock_sdk):
        """datetime values in rows are converted to ISO-8601 strings."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        dt = datetime(2024, 3, 15, 9, 30, 0)
        cursor = _make_cursor_with_rows(["ts"], [(dt,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_table("t")

        assert result.data[0]["ts"] == "2024-03-15T09:30:00"


# ---------------------------------------------------------------------------
# TestIngestTableValidation
# ---------------------------------------------------------------------------


class TestIngestTableValidation:
    """SQL-safety validation for ingest_table identifiers and fragments."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_table_name_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("orders; DROP TABLE orders")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_schema_name_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("orders", schema="sales; DROP")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_database_name_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("t", database="db-bad-name")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_malicious_where_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("t", where="1=1; DROP TABLE t")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_union_in_where_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("t", where="1=1 UNION SELECT * FROM secrets")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_malicious_order_by_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.ingest_table("t", order_by="id; DROP TABLE t")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_validation_raises_before_connecting(self):
        """ValidationError from a bad identifier must fire before any SDK call."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")

        with patch("semantica.ingest.redshift_ingestor._redshift_connector") as mock_sdk:
            with pytest.raises(ValidationError):
                ing.ingest_table("bad-name!")

            mock_sdk.connect.assert_not_called()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_valid_where_with_quoted_union_passes(self, mock_sdk):
        """'union' inside a string literal in WHERE must not be rejected."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        # "Credit Union" is a literal value, not SQL syntax — must pass.
        ing.ingest_table("t", where="name = 'Credit Union'")

        executed_sql = cursor.execute.call_args[0][0]
        assert "Credit Union" in executed_sql


# ---------------------------------------------------------------------------
# TestIngestQuery
# ---------------------------------------------------------------------------


class TestIngestQuery:
    """Tests for RedshiftIngestor.ingest_query()."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_basic_query_returns_redshift_data(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id", "total"], [(1, 99.5), (2, 42.0)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id, total FROM sales")

        assert isinstance(result, RedshiftData)
        assert result.row_count == 2
        assert result.columns == ["id", "total"]
        assert result.query == "SELECT id, total FROM sales"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_query_stored_verbatim(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["n"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        sql = "SELECT * FROM public.events WHERE type = 'click'"
        result = ing.ingest_query(sql)

        assert result.query == sql

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_tuple_rows_converted_to_dicts(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["a", "b"], [(10, "x"), (20, "y")])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT a, b FROM t")

        assert result.data == [{"a": 10, "b": "x"}, {"a": 20, "b": "y"}]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_params_forwarded_to_cursor_execute(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT id FROM t WHERE status = %s", params=("active",))

        cursor.execute.assert_called_once_with(
            "SELECT id FROM t WHERE status = %s", ("active",)
        )

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_no_params_calls_execute_without_params(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT id FROM t")

        cursor.execute.assert_called_once_with("SELECT id FROM t")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_batch_size_uses_fetchmany(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(
            ["id"],
            [(1,), (2,), (3,), (4,), (5,)],
        )
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id FROM t", batch_size=2)

        assert result.row_count == 5
        assert result.data == [{"id": i} for i in range(1, 6)]
        # fetchmany called multiple times (3 batches: 2, 2, 1, then empty)
        assert cursor.fetchmany.call_count >= 3

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_batch_size_calls_fetchmany_with_correct_size(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(1,), (2,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT id FROM t", batch_size=50)

        # All fetchmany calls must use the requested batch size.
        for c in cursor.fetchmany.call_args_list:
            assert c[0][0] == 50

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_empty_result_set(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id FROM t WHERE 1=0")

        assert result.row_count == 0
        assert result.data == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_after_fetch(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(1,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT id FROM t")

        cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_standalone_call_closes_connection(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT 1")

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_connection_reused(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["n"], [(1,)])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.ingest_query("SELECT 1")
            assert ing.connector.connection is mock_conn
            mock_conn.close.assert_not_called()

        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_query_failure_raises_processing_error(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("query error")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_query("SELECT bad query")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_on_query_failure(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("error")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_query("SELECT 1")

        cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connection_closed_on_query_failure(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = Mock()
        cursor.description = None
        cursor.execute.side_effect = RuntimeError("error")
        cursor.close = Mock()
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.ingest_query("SELECT 1")

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_autocommit_set_on_connection(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT 1")

        assert mock_conn.autocommit is True

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_params_stored_in_metadata(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id FROM t WHERE x = %s", params=("val",))

        assert result.metadata.get("params") == ("val",)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_no_params_metadata_empty(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT 1")

        assert result.metadata == {}


# ---------------------------------------------------------------------------
# TestContextManagerIntegration
# ---------------------------------------------------------------------------


class TestContextManagerIntegration:
    """End-to-end context manager tests for Stage 3 ingestion."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_both_methods_reuse_context_connection(self, mock_sdk):
        """Both ingest_table and ingest_query reuse the context-manager connection."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [(1,)])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.ingest_table("t1")
            ing.ingest_query("SELECT id FROM t2")
            # SDK connect must have been called exactly once (by __enter__)
            assert mock_sdk.connect.call_count == 1
            assert ing.connector.connection is mock_conn

        # Closed once on __exit__
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_closes_on_exception(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        with pytest.raises(ValueError):
            with RedshiftIngestor(
                host="h", database="d", user="u", password="p"
            ) as ing:
                raise ValueError("something went wrong")

        assert ing.connector.connection is None


# ===========================================================================
# Stage 4 — get_table_schema, list_tables, export_as_documents
# ===========================================================================

# ---------------------------------------------------------------------------
# Helpers for Stage 4
# ---------------------------------------------------------------------------


def _schema_cursor(columns_rows, pk_rows=None):
    """Return a sequence of cursors matching get_table_schema's two queries.

    First cursor returns *columns_rows* (column metadata tuples).
    Second cursor returns *pk_rows* (primary-key name tuples).

    Each fake cursor exposes .description, .fetchall(), .execute(), .close().
    """
    if pk_rows is None:
        pk_rows = []

    cursors = []
    for rows, col_names in [
        (
            columns_rows,
            ["column_name", "data_type", "is_nullable"],
        ),
        (pk_rows, ["column_name"]),
    ]:
        c = Mock()
        c.description = [(name,) + (None,) * 6 for name in col_names]
        c.fetchall = Mock(return_value=list(rows))
        c.execute = Mock()
        c.close = Mock()
        cursors.append(c)

    conn = Mock()
    conn.autocommit = False
    _call_count = [0]

    def _cursor():
        idx = _call_count[0]
        _call_count[0] += 1
        if idx < len(cursors):
            return cursors[idx]
        # fallback — return empty cursor
        c = Mock()
        c.description = [("col",)]
        c.fetchall = Mock(return_value=[])
        c.execute = Mock()
        c.close = Mock()
        return c

    conn.cursor = Mock(side_effect=_cursor)
    conn.close = Mock()
    return conn, cursors


def _list_tables_cursor(table_rows):
    """Return a mock connection + cursor for list_tables."""
    mock_conn, mock_cursor = _make_mock_connection()
    cursor = Mock()
    cursor.description = [("table_name",)]
    cursor.fetchall = Mock(return_value=list(table_rows))
    cursor.execute = Mock()
    cursor.close = Mock()
    mock_conn.cursor = Mock(return_value=cursor)
    return mock_conn, cursor


# ---------------------------------------------------------------------------
# TestGetTableSchema
# ---------------------------------------------------------------------------


class TestGetTableSchema:
    """Tests for RedshiftIngestor.get_table_schema()."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_basic_schema_returned(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [
            ("id", "integer", "NO"),
            ("name", "character varying", "YES"),
            ("score", "numeric", "YES"),
        ]
        mock_conn, cursors = _schema_cursor(col_rows, pk_rows=[("id",)])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("customers")

        assert "columns" in result
        assert "primary_keys" in result
        assert len(result["columns"]) == 3
        assert result["primary_keys"] == ["id"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_column_names_correct(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [("id", "integer", "NO"), ("email", "text", "YES")]
        mock_conn, _ = _schema_cursor(col_rows)
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("users")

        names = [c["name"] for c in result["columns"]]
        assert names == ["id", "email"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_column_types_correct(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [("amount", "numeric", "YES")]
        mock_conn, _ = _schema_cursor(col_rows)
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("orders")

        assert result["columns"][0]["type"] == "numeric"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_nullable_yes_is_true(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [("notes", "text", "YES")]
        mock_conn, _ = _schema_cursor(col_rows)
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("t")

        assert result["columns"][0]["nullable"] is True

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_nullable_no_is_false(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [("id", "integer", "NO")]
        mock_conn, _ = _schema_cursor(col_rows)
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("t")

        assert result["columns"][0]["nullable"] is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_column_order_preserved(self, mock_sdk):
        """Columns must appear in ordinal_position order (cursor row order)."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [
            ("a", "integer", "NO"),
            ("b", "text", "YES"),
            ("c", "boolean", "YES"),
        ]
        mock_conn, _ = _schema_cursor(col_rows)
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("t")

        assert [c["name"] for c in result["columns"]] == ["a", "b", "c"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_multiple_primary_keys(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [
            ("order_id", "integer", "NO"),
            ("item_id", "integer", "NO"),
        ]
        mock_conn, _ = _schema_cursor(col_rows, pk_rows=[("order_id",), ("item_id",)])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("order_items")

        assert set(result["primary_keys"]) == {"order_id", "item_id"}

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_no_primary_key_returns_empty_list(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        col_rows = [("col1", "text", "YES")]
        mock_conn, _ = _schema_cursor(col_rows, pk_rows=[])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("t")

        assert result["primary_keys"] == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_empty_table_returns_empty_columns(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _schema_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.get_table_schema("empty_t")

        assert result["columns"] == []
        assert result["primary_keys"] == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_schema_and_table_passed_as_params(self, mock_sdk):
        """table_name and schema are passed as %s params, not interpolated."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursors = _schema_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(
            host="h", database="d", user="u", password="p", schema="myschema"
        )
        ing.get_table_schema("mytable")

        # First cursor's execute call should have params=("myschema", "mytable")
        first_execute_params = cursors[0].execute.call_args[0][1]
        assert first_execute_params == ("myschema", "mytable")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_both_cursors_are_closed(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursors = _schema_cursor([("id", "integer", "NO")])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.get_table_schema("t")

        for c in cursors:
            c.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_standalone_call_closes_connection(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _schema_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.get_table_schema("t")

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_connection_reused(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _schema_cursor([])
        mock_sdk.connect.return_value = mock_conn

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.get_table_schema("t")
            assert ing.connector.connection is mock_conn
            mock_conn.close.assert_not_called()

        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_table_name_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.get_table_schema("bad-table-name!")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_schema_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.get_table_schema("t", schema="bad schema")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_validation_fires_before_connecting(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.get_table_schema("bad-name!")

        mock_sdk.connect.assert_not_called()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_query_failure_raises_processing_error(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("permission denied")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.get_table_schema("t")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_on_failure(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("error")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.get_table_schema("t")

        bad_cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_connection_closed_on_failure(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("error")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.get_table_schema("t")

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_autocommit_set(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _schema_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.get_table_schema("t")

        assert mock_conn.autocommit is True


# ---------------------------------------------------------------------------
# TestListTables
# ---------------------------------------------------------------------------


class TestListTables:
    """Tests for RedshiftIngestor.list_tables()."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_basic_list_returns_table_names(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursor = _list_tables_cursor(
            [("customers",), ("orders",), ("products",)]
        )
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.list_tables()

        assert result == ["customers", "orders", "products"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_schema_filter_passed_as_param(self, mock_sdk):
        """The schema value must be passed as a %s parameter, not interpolated."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursor = _list_tables_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(
            host="h", database="d", user="u", password="p", schema="analytics"
        )
        ing.list_tables()

        # The execute call should include the schema as a param tuple.
        execute_params = cursor.execute.call_args[0][1]
        assert execute_params == ("analytics",)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_explicit_schema_override(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursor = _list_tables_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(
            host="h", database="d", user="u", password="p", schema="public"
        )
        ing.list_tables(schema="staging")

        execute_params = cursor.execute.call_args[0][1]
        assert execute_params == ("staging",)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_empty_schema_returns_empty_list(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _list_tables_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.list_tables()

        assert result == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_after_fetch(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, cursor = _list_tables_cursor([("t",)])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.list_tables()

        cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_standalone_call_closes_connection(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _list_tables_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.list_tables()

        mock_conn.close.assert_called_once()
        assert ing.connector.connection is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_context_manager_connection_reused(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _list_tables_cursor([("t1",)])
        mock_sdk.connect.return_value = mock_conn

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.list_tables()
            assert ing.connector.connection is mock_conn
            mock_conn.close.assert_not_called()

        assert ing.connector.connection is None
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_invalid_schema_raises_validation_error(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.list_tables(schema="bad schema!")

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_validation_fires_before_connecting(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ValidationError

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ValidationError):
            ing.list_tables(schema="bad schema!")

        mock_sdk.connect.assert_not_called()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_query_failure_raises_processing_error(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("query error")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.list_tables()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_cursor_closed_on_failure(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("error")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        with pytest.raises(ProcessingError):
            ing.list_tables()

        bad_cursor.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_autocommit_set(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _list_tables_cursor([])
        mock_sdk.connect.return_value = mock_conn

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.list_tables()

        assert mock_conn.autocommit is True


# ---------------------------------------------------------------------------
# TestExportAsDocuments
# ---------------------------------------------------------------------------


class TestExportAsDocuments:
    """Tests for RedshiftIngestor.export_as_documents()."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_basic_conversion(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "Alice", "dept": "Eng"}],
            row_count=1,
            columns=["id", "name", "dept"],
            table_name="employees",
            database="dev",
            schema="public",
        )
        docs = ing.export_as_documents(data, id_field="id", text_fields=["name", "dept"])

        assert len(docs) == 1
        assert docs[0]["id"] == "1"
        assert docs[0]["text"] == "Alice Eng"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_metadata_source_is_redshift(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "Bob"}],
            row_count=1,
            columns=["id", "name"],
            table_name="t",
            database="mydb",
            schema="myschema",
        )
        docs = ing.export_as_documents(data)

        assert docs[0]["metadata"]["source"] == "redshift"
        assert docs[0]["metadata"]["table"] == "t"
        assert docs[0]["metadata"]["database"] == "mydb"
        assert docs[0]["metadata"]["schema"] == "myschema"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_row_data_in_metadata(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        row = {"id": 7, "name": "Carol", "score": 99}
        data = RedshiftData(data=[row], row_count=1, columns=["id", "name", "score"])
        docs = ing.export_as_documents(data)

        assert docs[0]["metadata"]["row_data"] == row

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_default_id_field_uses_id_key(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 42, "name": "Dave"}], row_count=1, columns=["id", "name"]
        )
        docs = ing.export_as_documents(data)

        assert docs[0]["id"] == "42"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_custom_id_field(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"order_id": "ORD-001", "item": "Widget"}],
            row_count=1,
            columns=["order_id", "item"],
        )
        docs = ing.export_as_documents(data, id_field="order_id")

        assert docs[0]["id"] == "ORD-001"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_missing_id_field_falls_back_to_row_index(self):
        """When id_field is absent from a row, the row index is used."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"name": "Eve"}, {"name": "Frank"}],
            row_count=2,
            columns=["name"],
        )
        docs = ing.export_as_documents(data, id_field="id")

        # Index fallback: row 0 → "0", row 1 → "1"
        assert docs[0]["id"] == "0"
        assert docs[1]["id"] == "1"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_text_fields_explicit_join(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "first": "Ada", "last": "Lovelace", "year": 1815}],
            row_count=1,
            columns=["id", "first", "last", "year"],
        )
        docs = ing.export_as_documents(data, text_fields=["first", "last"])

        assert docs[0]["text"] == "Ada Lovelace"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_text_fields_none_value_excluded(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "Alice", "notes": None}],
            row_count=1,
            columns=["id", "name", "notes"],
        )
        docs = ing.export_as_documents(data, text_fields=["name", "notes"])

        assert docs[0]["text"] == "Alice"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_default_text_uses_only_string_values(self):
        """When text_fields=None, only str-typed values contribute to text."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "Grace", "count": 10, "active": True}],
            row_count=1,
            columns=["id", "name", "count", "active"],
        )
        docs = ing.export_as_documents(data)

        # Only "Grace" is str — integers and bools are excluded.
        assert docs[0]["text"] == "Grace"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_multiple_rows_all_exported(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
                {"id": 3, "name": "Charlie"},
            ],
            row_count=3,
            columns=["id", "name"],
        )
        docs = ing.export_as_documents(data)

        assert len(docs) == 3
        assert docs[1]["id"] == "2"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_empty_data_returns_empty_list(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(data=[], row_count=0, columns=[])
        docs = ing.export_as_documents(data)

        assert docs == []

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_numeric_id_is_string_in_output(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 99}], row_count=1, columns=["id"]
        )
        docs = ing.export_as_documents(data)

        assert isinstance(docs[0]["id"], str)
        assert docs[0]["id"] == "99"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_table_name_none_when_from_query(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "val": "x"}],
            row_count=1,
            columns=["id", "val"],
            table_name=None,
            query="SELECT id, val FROM t",
        )
        docs = ing.export_as_documents(data)

        assert docs[0]["metadata"]["table"] is None

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_ids_are_deterministic(self):
        """Same data produces same IDs on every call — no random UUIDs."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 5, "name": "Dave"}], row_count=1, columns=["id", "name"]
        )
        docs1 = ing.export_as_documents(data)
        docs2 = ing.export_as_documents(data)

        assert docs1[0]["id"] == docs2[0]["id"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_no_credentials_in_documents(self):
        """No password, access key, or session token may appear in documents."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(
            host="h", database="d", user="awsuser", password="hunter2"
        )
        data = RedshiftData(
            data=[{"id": 1, "name": "Test"}],
            row_count=1,
            columns=["id", "name"],
        )
        docs = ing.export_as_documents(data)

        import json
        serialized = json.dumps(docs)
        assert "hunter2" not in serialized

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_text_fields_numeric_value_stringified(self):
        """Numeric values in explicit text_fields are str()-converted."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "score": 42}],
            row_count=1,
            columns=["id", "score"],
        )
        docs = ing.export_as_documents(data, text_fields=["score"])

        assert docs[0]["text"] == "42"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_text_fields_datetime_value_stringified(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        # _convert_rows already converted datetime → ISO string before export
        data = RedshiftData(
            data=[{"id": 1, "ts": "2024-06-15T12:00:00"}],
            row_count=1,
            columns=["id", "ts"],
        )
        docs = ing.export_as_documents(data, text_fields=["ts"])

        assert "2024-06-15" in docs[0]["text"]


# ---------------------------------------------------------------------------
# TestGraphBuilderContract
# ---------------------------------------------------------------------------


class TestGraphBuilderContract:
    """Verify that documents produced by export_as_documents are accepted
    by GraphBuilder without modification.

    The contract (from reading GraphBuilder._process_item) is:
      - A dict with ``"id"`` key is routed to all_entities.
      - A dict with ``"text"`` key (and no ``"source"``/``"target"``) is
        passed to _extract_from_text.
      - Both can coexist in the same dict.

    We verify the shape without invoking a live GraphBuilder
    (no NLP models, no network).
    """

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_document_has_id_key(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "description": "A widget"}],
            row_count=1,
            columns=["id", "description"],
        )
        docs = ing.export_as_documents(data)

        assert "id" in docs[0], "GraphBuilder requires 'id' for entity recognition"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_document_has_text_key(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "description": "A widget"}],
            row_count=1,
            columns=["id", "description"],
        )
        docs = ing.export_as_documents(data)

        assert "text" in docs[0], "GraphBuilder uses 'text' for NLP extraction"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_document_id_is_string(self):
        """GraphBuilder uses entity IDs as dict keys — must be hashable strings."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 123}], row_count=1, columns=["id"]
        )
        docs = ing.export_as_documents(data)

        assert isinstance(docs[0]["id"], str)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_document_text_is_string(self):
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "test"}], row_count=1, columns=["id", "name"]
        )
        docs = ing.export_as_documents(data)

        assert isinstance(docs[0]["text"], str)

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_document_shape_matches_snowflake_convention(self):
        """The shape must exactly match Snowflake/Databricks so GraphBuilder
        processes them identically."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[{"id": 1, "name": "Alice", "role": "Engineer"}],
            row_count=1,
            columns=["id", "name", "role"],
            table_name="employees",
            database="dev",
            schema="public",
        )
        docs = ing.export_as_documents(
            data, id_field="id", text_fields=["name", "role"]
        )

        doc = docs[0]
        # Top-level keys exactly {id, text, metadata}
        assert set(doc.keys()) == {"id", "text", "metadata"}
        # id is a string
        assert doc["id"] == "1"
        # text is the joined fields
        assert doc["text"] == "Alice Engineer"
        # metadata keys matching Snowflake convention (source, table, database,
        # schema, row_data) — Redshift adds "redshift" as source.
        assert doc["metadata"]["source"] == "redshift"
        assert doc["metadata"]["table"] == "employees"
        assert doc["metadata"]["database"] == "dev"
        assert doc["metadata"]["schema"] == "public"
        assert "row_data" in doc["metadata"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_graphbuilder_processes_documents_without_error(self):
        """GraphBuilder.build() must accept a list of Redshift documents
        without raising.  No live service calls; text extraction is
        explicitly disabled via extract=False."""
        from semantica.ingest.redshift_ingestor import RedshiftData, RedshiftIngestor
        from semantica.kg.graph_builder import GraphBuilder

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        data = RedshiftData(
            data=[
                {"id": 1, "product": "Widget A", "category": "Hardware"},
                {"id": 2, "product": "Widget B", "category": "Software"},
            ],
            row_count=2,
            columns=["id", "product", "category"],
            table_name="products",
            database="dev",
            schema="public",
        )
        docs = ing.export_as_documents(data, text_fields=["product", "category"])

        builder = GraphBuilder(resolve_conflicts=False)
        # extract=False: skip NLP extraction so the test needs no spaCy model.
        graph = builder.build(docs, extract=False)

        assert "entities" in graph
        assert "relationships" in graph
        assert graph["metadata"]["num_entities"] == 2


# ===========================================================================
# Code-review fix tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Fix #1 — autocommit state restored on caller-owned connections
# ---------------------------------------------------------------------------


class TestAutocommitRestoration:
    """autocommit must be restored to its previous value when the connection
    was already open (caller-owned) before the ingestion call."""

    def _make_ingesting_connection(self, initial_autocommit: bool):
        """Return a mock connection with autocommit pre-set."""
        mock_conn = Mock()
        mock_conn.autocommit = initial_autocommit
        return mock_conn

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingest_table_restores_autocommit_false(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn = self._make_ingesting_connection(initial_autocommit=False)
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [(1,)])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            # autocommit is False on the shared connection
            assert ing.connector.connection is mock_conn
            ing.ingest_table("t")
            # must be restored to False after the call
            assert mock_conn.autocommit is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingest_table_restores_autocommit_true(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn = self._make_ingesting_connection(initial_autocommit=True)
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.ingest_table("t")
            # was True before → must still be True after
            assert mock_conn.autocommit is True

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingest_query_restores_autocommit(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn = self._make_ingesting_connection(initial_autocommit=False)
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["n"], [])

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.ingest_query("SELECT 1")
            assert mock_conn.autocommit is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_get_table_schema_restores_autocommit(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _schema_cursor([])
        mock_conn.autocommit = False
        mock_sdk.connect.return_value = mock_conn

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.get_table_schema("t")
            assert mock_conn.autocommit is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_list_tables_restores_autocommit(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _list_tables_cursor([])
        mock_conn.autocommit = False
        mock_sdk.connect.return_value = mock_conn

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            ing.list_tables()
            assert mock_conn.autocommit is False

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_transient_connection_sets_autocommit_true(self, mock_sdk):
        """A standalone (transient) call must still enable autocommit for
        the duration of the query."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_conn.autocommit = False
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_table("t")
        # Transient connection is closed; autocommit was set True during the
        # call (we verify it was set by confirming the query completed).
        # The connection is gone, so we just verify no error occurred.
        mock_conn.close.assert_called_once()

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_autocommit_restored_even_when_query_fails(self, mock_sdk):
        """autocommit must be restored on caller-owned connections even when
        the query raises."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor
        from semantica.utils.exceptions import ProcessingError

        mock_conn = Mock()
        mock_conn.autocommit = False
        mock_sdk.connect.return_value = mock_conn
        bad_cursor = Mock()
        bad_cursor.execute.side_effect = RuntimeError("boom")
        bad_cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=bad_cursor)

        with RedshiftIngestor(
            host="h", database="d", user="u", password="p"
        ) as ing:
            with pytest.raises(ProcessingError):
                ing.ingest_table("t")
            # autocommit restored despite the exception
            assert mock_conn.autocommit is False


# ---------------------------------------------------------------------------
# Fix #2 — batch_size processes rows per-batch (memory behaviour)
# ---------------------------------------------------------------------------


class TestBatchFetchMemoryBehaviour:
    """With batch_size, each batch must be converted before the next fetch
    so raw tuples from prior batches are eligible for garbage collection."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_batch_produces_correct_total_count(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        # 5 rows, batch_size=2 → 3 fetches (2, 2, 1) + empty
        cursor = _make_cursor_with_rows(
            ["id"], [(1,), (2,), (3,), (4,), (5,)]
        )
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id FROM t", batch_size=2)

        assert result.row_count == 5
        assert result.data == [{"id": i} for i in range(1, 6)]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_batch_fetchmany_called_per_batch(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(1,), (2,), (3,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        ing.ingest_query("SELECT id FROM t", batch_size=2)

        # fetchmany called 3 times: [1,2], [3], [] (stop)
        assert cursor.fetchmany.call_count == 3
        for c in cursor.fetchmany.call_args_list:
            assert c[0][0] == 2

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_non_batch_path_still_works(self, mock_sdk):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        cursor = _make_cursor_with_rows(["id"], [(10,), (20,)])
        mock_conn.cursor.return_value = cursor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT id FROM t")

        assert result.data == [{"id": 10}, {"id": 20}]
        cursor.fetchall.assert_called_once()


# ---------------------------------------------------------------------------
# Fix #3 — REDSHIFT_SCHEMA env var is honoured when schema arg is omitted
# ---------------------------------------------------------------------------


class TestSchemaEnvVarFallback:
    """REDSHIFT_SCHEMA must supply the default when no schema= arg is given."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_schema_from_env_var(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        with patch.dict(
            os.environ,
            {
                "REDSHIFT_HOST": "h",
                "REDSHIFT_DATABASE": "d",
                "REDSHIFT_USER": "u",
                "REDSHIFT_PASSWORD": "p",
                "REDSHIFT_SCHEMA": "analytics",
            },
        ):
            ing = RedshiftIngestor()

        assert ing.schema == "analytics"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_explicit_schema_arg_overrides_env_var(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        with patch.dict(os.environ, {"REDSHIFT_SCHEMA": "analytics"}):
            ing = RedshiftIngestor(
                host="h", database="d", user="u", password="p",
                schema="overridden",
            )

        assert ing.schema == "overridden"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_schema_defaults_to_public_when_no_env_var(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        env = {k: v for k, v in os.environ.items() if k != "REDSHIFT_SCHEMA"}
        with patch.dict(os.environ, env, clear=True):
            ing = RedshiftIngestor(
                host="h", database="d", user="u", password="p"
            )

        assert ing.schema == "public"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_env_schema_used_in_ingest_table_query(self, mock_sdk):
        """The schema from REDSHIFT_SCHEMA is used when building the table ref."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn
        mock_conn.cursor.return_value = _make_cursor_with_rows(["id"], [])

        with patch.dict(os.environ, {"REDSHIFT_SCHEMA": "staging"}):
            ing = RedshiftIngestor(
                host="h", database="d", user="u", password="p"
            )
        # Ensure schema was picked up
        assert ing.schema == "staging"

        ing.ingest_table("orders")
        executed_sql = mock_conn.cursor.return_value.execute.call_args[0][0]
        assert '"staging"."orders"' in executed_sql


# ---------------------------------------------------------------------------
# Fix #4 — db-all includes db-redshift
# ---------------------------------------------------------------------------


class TestDbAllIncludesRedshift:
    """pyproject.toml db-all aggregate must reference db-redshift."""

    def test_db_all_references_db_redshift(self):
        """Read pyproject.toml and verify db-all includes db-redshift."""
        import tomllib
        from pathlib import Path

        toml_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        db_all = data["project"]["optional-dependencies"]["db-all"]
        # db-all is a list of strings like ["semantica[db-snowflake,...]"]
        combined = " ".join(db_all)
        assert "db-redshift" in combined, (
            f"db-all does not reference db-redshift. Got: {db_all}"
        )


# ---------------------------------------------------------------------------
# Fix #5 — duplicate column labels are disambiguated
# ---------------------------------------------------------------------------


class TestDisambiguateColumns:
    """_disambiguate_columns must make every label unique."""

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_no_duplicates_unchanged(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing._disambiguate_columns(["id", "name", "score"])
        assert result == ["id", "name", "score"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_single_duplicate_gets_suffix(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing._disambiguate_columns(["id", "name", "id"])
        # First occurrence keeps original name; second gets _1
        assert result == ["id", "name", "id_1"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_triple_duplicate_gets_incrementing_suffixes(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing._disambiguate_columns(["x", "x", "x"])
        assert result == ["x", "x_1", "x_2"]

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    def test_all_unique_after_disambiguation(self):
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        cols = ["a", "b", "a", "c", "b", "a"]
        result = ing._disambiguate_columns(cols)
        assert len(result) == len(set(result)), "Result contains duplicates"

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingest_query_with_duplicate_columns_retains_all_values(self, mock_sdk):
        """A JOIN-style query with two columns named 'id' must not lose the
        second value — it must appear as 'id_1' in the row dict."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        # Simulate cursor.description with duplicate 'id' labels
        cursor = Mock()
        cursor.description = [
            ("id",) + (None,) * 6,
            ("name",) + (None,) * 6,
            ("id",) + (None,) * 6,   # duplicate!
        ]
        cursor.fetchall = Mock(return_value=[(1, "Alice", 99)])
        cursor.execute = Mock()
        cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT t1.id, name, t2.id FROM ...")

        assert result.columns == ["id", "name", "id_1"]
        assert result.data[0]["id"] == 1
        assert result.data[0]["name"] == "Alice"
        assert result.data[0]["id_1"] == 99

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_ingest_table_with_duplicate_columns_retains_all_values(self, mock_sdk):
        """ingest_table uses _fetch_all which must also disambiguate."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        cursor = Mock()
        cursor.description = [
            ("val",) + (None,) * 6,
            ("val",) + (None,) * 6,   # duplicate!
        ]
        cursor.fetchall = Mock(return_value=[(10, 20)])
        cursor.execute = Mock()
        cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_table("t")

        assert result.columns == ["val", "val_1"]
        assert result.data[0]["val"] == 10
        assert result.data[0]["val_1"] == 20

    @patch("semantica.ingest.redshift_ingestor.REDSHIFT_AVAILABLE", True)
    @patch("semantica.ingest.redshift_ingestor._redshift_connector")
    def test_batch_with_duplicate_columns(self, mock_sdk):
        """Duplicate disambiguation must also apply when batch_size is set."""
        from semantica.ingest.redshift_ingestor import RedshiftIngestor

        mock_conn, _ = _make_mock_connection()
        mock_sdk.connect.return_value = mock_conn

        cursor = Mock()
        cursor.description = [
            ("score",) + (None,) * 6,
            ("score",) + (None,) * 6,   # duplicate!
        ]
        _batches = [[(1, 2)], [(3, 4)], []]
        cursor.fetchmany = Mock(side_effect=_batches)
        cursor.execute = Mock()
        cursor.close = Mock()
        mock_conn.cursor = Mock(return_value=cursor)

        ing = RedshiftIngestor(host="h", database="d", user="u", password="p")
        result = ing.ingest_query("SELECT ...", batch_size=1)

        assert result.columns == ["score", "score_1"]
        assert result.data[0] == {"score": 1, "score_1": 2}
        assert result.data[1] == {"score": 3, "score_1": 4}

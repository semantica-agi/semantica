"""
Unit tests for LookerConnector and LookerIngestor.

All ``looker_sdk`` calls are mocked — no live Looker instance is contacted
and no network I/O occurs.

Test structure mirrors ``tests/test_redshift_ingestor.py`` and
``tests/test_salesforce_ingestor.py``:

  - an autouse fixture injects a ``looker_sdk`` stub into ``sys.modules``
    when the real SDK is absent, so tests that reference the symbol can
    still run; the module-level optional-dependency guard has already run
    at import time, so this fixture cannot change ``LOOKER_AVAILABLE``;
  - an autouse fixture clears ``LOOKERSDK_*`` variables so a developer's
    live configuration can never leak into a test;
  - tests that need the real ``ApiSettings``/``init40`` implementation are
    skipped when ``looker-sdk`` is not installed; the import guard, the
    normalizer, the redaction contract, and the document projection are
    covered without it.

SSRF assertions use literal hosts (``localhost``, ``127.0.0.1``) only.
The DNS-stubbing autouse fixture lives in ``tests/ingest/conftest.py``,
not at the repository root, so no test here may require DNS resolution.
"""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import requests
from requests.adapters import BaseAdapter
from requests.exceptions import TooManyRedirects

# ---------------------------------------------------------------------------
# Optional SDK detection
# ---------------------------------------------------------------------------
try:
    import looker_sdk as _looker_sdk  # noqa: F401

    LOOKER_SDK_AVAILABLE = True
except ImportError:
    LOOKER_SDK_AVAILABLE = False

requires_looker_sdk = pytest.mark.skipif(
    not LOOKER_SDK_AVAILABLE,
    reason="looker-sdk is required for this test",
)

# A literal public IP is used instead of a hostname: the SSRF validator
# performs real DNS lookups, and the DNS-stubbing fixture lives only in
# tests/ingest/conftest.py, not at the repository root.
PUBLIC_BASE_URL = "https://93.184.216.34"
PRIVATE_BASE_URL = "http://127.0.0.1:19999"
CLIENT_ID = "test-client-id"
CLIENT_SECRET = "test-client-secret"
ACCESS_TOKEN = "test-access-token-do-not-log"

# Literal secret values that must never survive normalization or logging.
SECRET_FIELD_VALUES = {
    "git_password": "git-password-do-not-log",
    "deploy_secret": "deploy-secret-do-not-log",
    "password": "dashboard-password-do-not-log",
    "pdt_password": "pdt-password-do-not-log",
    "device_token": ACCESS_TOKEN,
}

# Logger names whose records must never carry a credential or token.
CONNECTOR_LOGGER = "semantica.looker_ingestor"
TRANSPORT_LOGGER = "looker_sdk.rtl.requests_transport"

_LOOKER_ENV_KEYS = (
    "LOOKERSDK_BASE_URL",
    "LOOKERSDK_CLIENT_ID",
    "LOOKERSDK_CLIENT_SECRET",
    "LOOKERSDK_VERIFY_SSL",
    "LOOKERSDK_TIMEOUT",
)


# ---------------------------------------------------------------------------
# autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_looker_sdk_if_needed():
    """Expose a minimal ``looker_sdk`` stub when the SDK is not installed.

    The stub is installed in ``sys.modules`` for the duration of each test,
    but ``semantica.ingest.looker_ingestor`` has already evaluated its
    module-level import guard by then, so this fixture does **not** exercise
    that guard — it only keeps ``looker_sdk`` importable for tests that
    reference the module object directly.
    """
    if not LOOKER_SDK_AVAILABLE:
        stub = MagicMock()
        stub.error.SDKError = type("SDKError", (Exception,), {})

        with patch.dict("sys.modules", {"looker_sdk": stub}):
            yield
    else:
        yield


@pytest.fixture(autouse=True)
def _clean_looker_env(monkeypatch):
    """Remove inherited ``LOOKERSDK_*`` variables before every test."""
    for key in _LOOKER_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(base_url: str = PUBLIC_BASE_URL) -> MagicMock:
    """Return a mock that behaves like a ``Looker40SDK`` instance.

    ``connect()`` asserts that the client's resolved ``base_url`` matches
    the validated endpoint, and applies the redirect/proxy transport
    controls to ``client.transport.session``, so the mock must expose
    both paths with realistic starting values.
    """
    client = MagicMock()
    client.auth.settings.base_url = base_url
    client.transport.session.max_redirects = 5
    client.transport.session.trust_env = True
    return client


class _FakeConnector:
    """Minimal connector double for ingestor tests (no SDK required)."""

    def __init__(self, client, base_url: str = PUBLIC_BASE_URL):
        self.client = client
        self.base_url = base_url
        self.connected = False
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self):
        self.connect_calls += 1
        self.connected = True
        return self.client

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False


def _make_ingestor(client) -> "object":
    """Return a LookerIngestor wired to a fake connector."""
    from semantica.ingest.looker_ingestor import LookerIngestor

    return LookerIngestor(connector=_FakeConnector(client))


# ---------------------------------------------------------------------------
# TestLookerConnectorDataContract — LookerData is SDK-independent
# ---------------------------------------------------------------------------


class TestLookerConnectorDataContract:
    """``LookerData`` must import and construct without ``looker_sdk``."""

    def test_importable_without_sdk(self):
        from semantica.ingest.looker_ingestor import LookerData

        with patch("semantica.ingest.looker_ingestor.LOOKER_AVAILABLE", False):
            data = LookerData(data=[], row_count=0, columns=[], content_type="look")

        assert data.data == []
        assert data.row_count == 0
        assert data.columns == []
        assert data.content_type == "look"
        assert data.base_url is None
        assert data.metadata == {}
        assert isinstance(data.ingested_at, datetime)

    def test_full_field_contract(self):
        from semantica.ingest.looker_ingestor import LookerData

        rows = [{"id": 1, "title": "Orders"}]
        data = LookerData(
            data=rows,
            row_count=1,
            columns=["id", "title"],
            content_type="look",
            base_url=PUBLIC_BASE_URL,
            metadata={"content_type": "look"},
        )

        assert data.data == rows
        assert data.row_count == 1
        assert data.base_url == PUBLIC_BASE_URL
        assert data.metadata == {"content_type": "look"}

    def test_module_all_and_logger_are_module_level(self):
        from semantica.ingest import looker_ingestor as mod

        assert mod.__all__ == [
            "LookerData",
            "LookerConnector",
            "LookerIngestor",
        ]
        assert mod._logger is not None


# ---------------------------------------------------------------------------
# TestLookerConnectorImportGuard
# ---------------------------------------------------------------------------


class TestLookerConnectorImportGuard:
    """R8 — the optional-dependency guard and its install hint."""

    def test_missing_sdk_raises_import_error_with_exact_hint(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        with patch("semantica.ingest.looker_ingestor.LOOKER_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                LookerConnector(
                    base_url=PUBLIC_BASE_URL,
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                )

        message = str(exc_info.value)
        assert 'pip install "semantica[ingest-looker]"' in message
        assert CLIENT_SECRET not in message

    def test_missing_sdk_error_does_not_leak_secret(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        with patch("semantica.ingest.looker_ingestor.LOOKER_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                LookerConnector(client_secret="super-sensitive")

        assert "super-sensitive" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestLookerConnectorInit
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorInit:
    """Credential resolution, defaults, and pre-flight validation."""

    def test_explicit_credentials_stored(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )

        assert conn.base_url == PUBLIC_BASE_URL
        assert conn.client_id == CLIENT_ID
        assert conn._client_secret == CLIENT_SECRET
        assert conn.connected is False
        assert conn.client is None
        assert conn.allow_private_ips is False

    def test_credentials_default_to_environment(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        env = {
            "LOOKERSDK_BASE_URL": PUBLIC_BASE_URL,
            "LOOKERSDK_CLIENT_ID": "env-client",
            "LOOKERSDK_CLIENT_SECRET": "env-secret",
        }
        with patch.dict(os.environ, env):
            conn = LookerConnector()

        assert conn.base_url == PUBLIC_BASE_URL
        assert conn.client_id == "env-client"
        assert conn._client_secret == "env-secret"

    def test_explicit_args_override_env_credentials(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        env = {
            "LOOKERSDK_CLIENT_ID": "env-client",
            "LOOKERSDK_CLIENT_SECRET": "env-secret",
        }
        with patch.dict(os.environ, env):
            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

        assert conn.client_id == CLIENT_ID
        assert conn._client_secret == CLIENT_SECRET

    def test_missing_base_url_raises_validation_error(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

    def test_missing_client_id_raises_validation_error(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(base_url=PUBLIC_BASE_URL, client_secret=CLIENT_SECRET)

    def test_missing_client_secret_raises_validation_error(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(base_url=PUBLIC_BASE_URL, client_id=CLIENT_ID)

    def test_validation_error_does_not_contain_secret(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LookerConnector(client_id=CLIENT_ID, client_secret="s3cr3t-value")

        assert "s3cr3t-value" not in str(exc_info.value)

    def test_api_settings_built_with_config_file_section_and_env_prefix(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        mock_settings = MagicMock()
        mock_settings.base_url = PUBLIC_BASE_URL
        mock_settings.client_id = CLIENT_ID
        mock_settings.client_secret = CLIENT_SECRET

        with patch(
            "semantica.ingest.looker_ingestor.api_settings.ApiSettings",
            return_value=mock_settings,
        ) as mock_api_settings:
            LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                config_file="custom.ini",
                section="looker",
            )

        mock_api_settings.assert_called_once_with(
            filename="custom.ini", section="looker", env_prefix="LOOKERSDK"
        )

    def test_does_not_mutate_os_environ(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        before = dict(os.environ)
        LookerConnector(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )
        assert dict(os.environ) == before


# ---------------------------------------------------------------------------
# TestLookerConnectorFailClosed
# ---------------------------------------------------------------------------


class TestLookerConnectorFailClosed:
    """AE1, AE2 — unsafe endpoints fail before any SDK object is built.

    These cases exercise only the pre-flight checks, so they run whether
    or not ``looker-sdk`` is installed; the fixture patches
    ``LOOKER_AVAILABLE`` so the optional-dependency guard does not
    short-circuit first.
    """

    @pytest.fixture(autouse=True)
    def _force_available(self):
        with patch("semantica.ingest.looker_ingestor.LOOKER_AVAILABLE", True):
            yield

    def test_http_base_url_rejected_by_default(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            LookerConnector(
                base_url="http://looker.internal",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

        assert "https" in str(exc_info.value)

    def test_http_rejected_before_any_client_is_built(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with patch("semantica.ingest.looker_ingestor.looker_sdk") as mock_sdk:
            with pytest.raises(ValidationError):
                LookerConnector(
                    base_url="http://looker.internal",
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                )

        mock_sdk.init40.assert_not_called()

    def test_localhost_rejected_by_default(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(
                base_url="https://localhost",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

    def test_loopback_ip_rejected_by_default(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(
                base_url="https://127.0.0.1",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

    @pytest.mark.parametrize("value", ["false", "0", "no", "off"])
    def test_falsey_strings_do_not_enable_allow_private_ips(self, value):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(
                base_url=PRIVATE_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                config={"allow_private_ips": value},
            )

    def test_config_dict_overrides_kwarg_allow_private_ips(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError):
            LookerConnector(
                base_url=PRIVATE_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                allow_private_ips=True,
                config={"allow_private_ips": "0"},
            )

    def test_env_base_url_conflicting_with_constructor_fails_closed(self):
        """AE2 — the environment must not silently redirect the client."""
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with patch.dict(os.environ, {"LOOKERSDK_BASE_URL": "https://10.0.0.5"}):
            with pytest.raises(ValidationError):
                LookerConnector(
                    base_url=PUBLIC_BASE_URL,
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                )

    def test_env_base_url_conflict_message_does_not_leak_secret(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        with patch.dict(os.environ, {"LOOKERSDK_BASE_URL": "https://10.0.0.5"}):
            with pytest.raises(ValidationError) as exc_info:
                LookerConnector(
                    base_url=PUBLIC_BASE_URL,
                    client_id=CLIENT_ID,
                    client_secret="do-not-leak",
                )

        assert "do-not-leak" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestLookerConnectorEndpointValidation
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorEndpointValidation:
    """R10 — validate-once binding and the allow_private_ips opt-in."""

    def test_http_allowed_with_allow_private_ips_true(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PRIVATE_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            allow_private_ips=True,
        )

        assert conn.allow_private_ips is True
        assert conn.base_url == PRIVATE_BASE_URL

    def test_config_dict_true_string_enables_allow_private_ips(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PRIVATE_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            config={"allow_private_ips": "true"},
        )

        assert conn.allow_private_ips is True

    def test_env_private_base_url_rejected_without_allow_private_ips(self):
        """A private endpoint supplied only by the environment fails closed."""
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        env = {
            "LOOKERSDK_BASE_URL": "https://10.0.0.5",
            "LOOKERSDK_CLIENT_ID": CLIENT_ID,
            "LOOKERSDK_CLIENT_SECRET": CLIENT_SECRET,
        }
        with patch.dict(os.environ, env):
            with pytest.raises(ValidationError):
                LookerConnector()

    def test_settings_read_config_carries_explicit_credentials(self):
        """KTD4 — credentials ride the settings object, not os.environ."""
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )
        resolved = conn._settings.read_config()

        assert resolved["base_url"] == PUBLIC_BASE_URL
        assert resolved["client_id"] == CLIENT_ID
        assert resolved["client_secret"] == CLIENT_SECRET
        assert os.getenv("LOOKERSDK_CLIENT_SECRET") is None


# ---------------------------------------------------------------------------
# TestLookerConnectorLifecycle
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorLifecycle:
    """connect()/disconnect()/context-manager and the transport controls."""

    def _connected_connector(self, client):
        from semantica.ingest.looker_ingestor import LookerConnector

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ) as mock_init:
            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            result = conn.connect()
        return conn, result, mock_init

    def test_connect_passes_same_settings_object(self):
        client = _make_mock_client()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ) as mock_init:
            from semantica.ingest.looker_ingestor import LookerConnector

            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            conn.connect()

        assert mock_init.call_args[1]["config_settings"] is conn._settings
        assert conn._settings.base_url == PUBLIC_BASE_URL

    def test_connect_returns_existing_client(self):
        client = _make_mock_client()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ) as mock_init:
            from semantica.ingest.looker_ingestor import LookerConnector

            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            first = conn.connect()
            second = conn.connect()

        assert first is client
        assert second is client
        mock_init.assert_called_once()

    def test_connect_applies_transport_controls(self):
        client = _make_mock_client()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            from semantica.ingest.looker_ingestor import LookerConnector

            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            conn.connect()

        assert client.transport.session.max_redirects == 0
        assert client.transport.session.trust_env is False

    def test_connect_fails_closed_when_client_base_url_differs(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        client = _make_mock_client(base_url="https://elsewhere.example.com")

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            with pytest.raises(ValidationError):
                conn.connect()

        assert conn.connected is False
        assert conn.client is None

    def test_connect_failure_raises_processing_error_without_secret(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ProcessingError

        error = _looker_sdk.error.SDKError(f"auth failed client_secret={CLIENT_SECRET}")

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            side_effect=error,
        ):
            conn = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            with pytest.raises(ProcessingError) as exc_info:
                conn.connect()

        message = str(exc_info.value)
        assert CLIENT_SECRET not in message
        assert "SDKError" in message

    def test_disconnect_clears_client_and_is_idempotent(self):
        client = _make_mock_client()
        conn, _, _ = self._connected_connector(client)

        conn.disconnect()
        assert conn.connected is False
        assert conn.client is None

        conn.disconnect()
        assert conn.connected is False

    def test_context_manager_connects_and_disconnects(self):
        client = _make_mock_client()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            from semantica.ingest.looker_ingestor import LookerConnector

            with LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            ) as conn:
                assert conn.connected is True

        assert conn.connected is False

    def test_close_delegates_to_disconnect(self):
        client = _make_mock_client()
        conn, _, _ = self._connected_connector(client)

        conn.close()

        assert conn.connected is False

    def test_real_init40_client_is_bound_and_constrained(self):
        """End-to-end (offline) proof that the validated value is dialed.

        Real ``looker_sdk.init40`` constructs the client and its
        ``requests.Session`` without any network I/O, which lets this test
        assert the binding and the KTD2 transport controls for real rather
        than against a mock.
        """
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )

        client = conn.connect()

        assert conn.connected is True
        assert client.auth.settings is conn._settings
        assert client.auth.settings.base_url == PUBLIC_BASE_URL
        assert client.transport.session.max_redirects == 0
        assert client.transport.session.trust_env is False

        resolved = client.auth.settings.read_config()
        assert resolved["base_url"] == PUBLIC_BASE_URL
        assert resolved["client_id"] == CLIENT_ID
        assert resolved["client_secret"] == CLIENT_SECRET

        conn.disconnect()
        assert conn.connected is False


# ---------------------------------------------------------------------------
# TestLookerConnectorTestConnection
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorTestConnection:
    """test_connection() — bool result, safe logging, lifecycle discipline."""

    def _connector(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        conn = LookerConnector(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
        )
        conn.logger = Mock()
        return conn

    def test_returns_true_on_success(self):
        client = _make_mock_client()
        client.me.return_value = object()
        conn = self._connector()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            assert conn.test_connection() is True

        client.me.assert_called_once()

    def test_opens_and_closes_transient_client(self):
        client = _make_mock_client()
        client.me.return_value = object()
        conn = self._connector()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            conn.test_connection()

        assert conn.connected is False

    def test_returns_false_and_logs_only_exception_type(self):
        client = _make_mock_client()
        client.me.side_effect = _looker_sdk.error.SDKError(
            f"access_token=leaked client_secret={CLIENT_SECRET}"
        )
        conn = self._connector()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            assert conn.test_connection() is False

        rendered = " ".join(
            str(argument)
            for call in conn.logger.debug.call_args_list
            for argument in call.args
        )
        assert CLIENT_SECRET not in rendered
        assert "leaked" not in rendered
        assert "SDKError" in rendered

    def test_does_not_disconnect_pre_existing_client(self):
        client = _make_mock_client()
        client.me.return_value = object()
        conn = self._connector()

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            conn.connect()
            assert conn.connected is True
            with patch.object(conn, "disconnect") as mock_disconnect:
                assert conn.test_connection() is True

        mock_disconnect.assert_not_called()
        assert conn.connected is True


# ---------------------------------------------------------------------------
# TestLookerIngestorReads
# ---------------------------------------------------------------------------


class TestLookerIngestorReads:
    """U2 — the five metadata reads and the connection lifecycle."""

    @pytest.mark.parametrize(
        ("method_name", "sdk_method", "content_type", "rows", "columns"),
        [
            (
                "ingest_looks",
                "all_looks",
                "look",
                [{"id": 1, "title": "one"}, {"id": 2, "title": "two"}],
                ["id", "title"],
            ),
            (
                "ingest_dashboards",
                "all_dashboards",
                "dashboard",
                [{"id": 1, "title": "one"}, {"id": 2, "title": "two"}],
                ["id", "title"],
            ),
            (
                "ingest_lookml_models",
                "all_lookml_models",
                "lookml_model",
                [{"name": "one"}, {"name": "two"}],
                ["name"],
            ),
            (
                "ingest_folders",
                "all_folders",
                "folder",
                [{"id": 1, "name": "one"}, {"id": 2, "name": "two"}],
                ["id", "name"],
            ),
            (
                "ingest_projects",
                "all_projects",
                "project",
                [{"id": "a", "name": "one"}, {"id": "b", "name": "two"}],
                ["id", "name"],
            ),
        ],
    )
    def test_read_returns_rows_and_row_count(
        self, method_name, sdk_method, content_type, rows, columns
    ):
        client = MagicMock()
        getattr(client, sdk_method).return_value = rows
        ingestor = _make_ingestor(client)

        data = getattr(ingestor, method_name)()

        assert data.row_count == 2
        assert len(data.data) == 2
        assert data.content_type == content_type
        assert data.base_url == PUBLIC_BASE_URL
        assert data.columns == columns

    def test_read_calls_sdk_method(self):
        client = MagicMock()
        client.all_looks.return_value = []
        ingestor = _make_ingestor(client)

        ingestor.ingest_looks()

        client.all_looks.assert_called_once()

    def test_empty_result_set_returns_empty_list(self):
        client = MagicMock()
        client.all_looks.return_value = []
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_looks()

        assert data.data == []
        assert data.row_count == 0
        assert ingestor.export_as_documents(data) == []

    def test_none_result_set_is_treated_as_empty(self):
        client = MagicMock()
        client.all_looks.return_value = None
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_looks()

        assert data.data == []
        assert data.row_count == 0

    def test_transient_connection_is_closed(self):
        client = MagicMock()
        client.all_looks.return_value = []
        fake = _FakeConnector(client)
        from semantica.ingest.looker_ingestor import LookerIngestor

        ingestor = LookerIngestor(connector=fake)
        ingestor.ingest_looks()

        assert fake.connect_calls == 1
        assert fake.disconnect_calls == 1
        assert fake.connected is False

    def test_pre_existing_connection_is_reused(self):
        client = MagicMock()
        client.all_looks.return_value = []
        fake = _FakeConnector(client)
        fake.connected = True
        from semantica.ingest.looker_ingestor import LookerIngestor

        ingestor = LookerIngestor(connector=fake)
        ingestor.ingest_looks()

        assert fake.disconnect_calls == 0
        assert fake.connected is True

    @requires_looker_sdk
    def test_sdk_error_translated_to_processing_error(self):
        from semantica.utils.exceptions import ProcessingError

        client = MagicMock()
        client.all_looks.side_effect = _looker_sdk.error.SDKError(
            f"token=leaked secret={CLIENT_SECRET}"
        )
        fake = _FakeConnector(client)
        from semantica.ingest.looker_ingestor import LookerIngestor

        ingestor = LookerIngestor(connector=fake)
        ingestor.logger = Mock()

        with pytest.raises(ProcessingError) as exc_info:
            ingestor.ingest_looks()

        message = str(exc_info.value)
        assert CLIENT_SECRET not in message
        assert "SDKError" in message
        assert fake.disconnect_calls == 1

    def test_ingestor_context_manager_uses_connector(self):
        client = MagicMock()
        client.all_looks.return_value = []
        fake = _FakeConnector(client)
        from semantica.ingest.looker_ingestor import LookerIngestor

        with LookerIngestor(connector=fake) as ingestor:
            assert fake.connected is True
            ingestor.ingest_looks()

        assert fake.connected is False


# ---------------------------------------------------------------------------
# TestLookerIngestorNormalization
# ---------------------------------------------------------------------------


class TestLookerIngestorNormalization:
    """U2 — deep normalization and allowlist redaction."""

    def test_plain_dict_records_pass_through_allowed_fields(self):
        client = MagicMock()
        client.all_looks.return_value = [
            {"id": 7, "title": "Revenue", "unexpected": "drop-me"}
        ]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_looks()

        assert data.data == [{"id": 7, "title": "Revenue"}]

    def test_unknown_content_type_raises_validation_error(self):
        from semantica.ingest.looker_ingestor import LookerData
        from semantica.utils.exceptions import ValidationError

        ingestor = _make_ingestor(MagicMock())
        data = LookerData(
            data=[{"id": 1}], row_count=1, columns=[], content_type="tile"
        )

        with pytest.raises(ValidationError):
            ingestor.export_as_documents(data)

    def test_datetime_values_become_iso_8601_strings(self):
        stamp = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        client = MagicMock()
        client.all_looks.return_value = [{"id": 1, "title": "T", "created_at": stamp}]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_looks()

        assert data.data[0]["created_at"] == stamp.isoformat()
        json.dumps(data.data)

    def test_nested_models_and_sequences_are_normalized(self):
        class _Nested:
            def __init__(self, **kwargs):
                self._data = kwargs

            def keys(self):
                return self._data.keys()

            def items(self):
                return self._data.items()

        client = MagicMock()
        client.all_lookml_models.return_value = [
            {
                "name": "model",
                "project_name": "proj",
                "explores": [
                    _Nested(name="orders", label="Orders", group_label="Commerce")
                ],
            }
        ]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_lookml_models()
        record = data.data[0]

        assert record["explores"][0] == {
            "name": "orders",
            "label": "Orders",
            "group_label": "Commerce",
        }
        json.dumps(record)

    def test_secret_fields_absent_from_plain_dict_records(self):
        client = MagicMock()
        client.all_dashboards.return_value = [
            {
                "id": 1,
                "title": "Ops",
                "password": "DASH_PASSWORD",
                "pdt_password": "PDT_PASSWORD",
            }
        ]
        client.all_lookml_models.return_value = [
            {
                "name": "model",
                "project_name": "proj",
                "device_token": "DEVICE_TOKEN",
            }
        ]
        ingestor = _make_ingestor(client)

        dashboards = ingestor.ingest_dashboards()
        models = ingestor.ingest_lookml_models()

        rendered = json.dumps([dashboards.data, models.data])
        for secret in ("DASH_PASSWORD", "PDT_PASSWORD", "DEVICE_TOKEN"):
            assert secret not in rendered

    def test_nested_secret_fields_are_redacted(self):
        class _NestedProject:
            def __init__(self, **kwargs):
                self._data = kwargs

            def keys(self):
                return self._data.keys()

            def items(self):
                return self._data.items()

        client = MagicMock()
        client.all_folders.return_value = [
            {
                "id": 1,
                "name": "Shared",
                "looks": [
                    _NestedProject(
                        id=9,
                        title="Nested look",
                        password="NESTED_PASSWORD",
                    )
                ],
            }
        ]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_folders()

        rendered = json.dumps(data.data)
        assert "NESTED_PASSWORD" not in rendered
        assert "password" not in rendered

    @requires_looker_sdk
    def test_project_secrets_absent_from_data_and_documents(self):
        from looker_sdk.sdk.api40 import models as sdk_models

        project = sdk_models.Project(
            id="shop",
            name="shop",
            git_remote_url="https://gituser:gitpass@git.example.com/shop.git",
            git_username="gituser",
            git_password="GIT_PASSWORD",
            deploy_secret="DEPLOY_SECRET",
        )
        client = MagicMock()
        client.all_projects.return_value = [project]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_projects()
        documents = ingestor.export_as_documents(data)

        payload = json.dumps({"data": data.data, "documents": documents})
        for secret in (
            "GIT_PASSWORD",
            "DEPLOY_SECRET",
            "gitpass",
            "gituser:gitpass",
        ):
            assert secret not in payload

        record = data.data[0]
        assert record["name"] == "shop"
        assert record["git_remote_url"] == "https://git.example.com/shop.git"
        assert "git_username" in record
        assert "git_password" not in record
        assert "deploy_secret" not in record

    @requires_looker_sdk
    def test_lookml_model_explores_are_nested_with_parent_identity(self):
        from looker_sdk.sdk.api40 import models as sdk_models

        explore = sdk_models.LookmlModelNavExplore(
            name="orders",
            label="Orders",
            description="Order facts",
            hidden=False,
            group_label="Commerce",
        )
        model = sdk_models.LookmlModel(
            name="ecommerce",
            project_name="shop",
            label="Ecommerce",
            explores=[explore],
        )
        client = MagicMock()
        client.all_lookml_models.return_value = [model]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_lookml_models()
        record = data.data[0]

        assert record["name"] == "ecommerce"
        assert record["project_name"] == "shop"
        # ``all_lookml_models()`` yields ``LookmlModelNavExplore`` records: only
        # the navigation fields exist, and ``group_label`` must survive.
        assert record["explores"][0] == {
            "name": "orders",
            "description": "Order facts",
            "label": "Orders",
            "hidden": False,
            "group_label": "Commerce",
        }
        assert "device_token" not in record
        json.dumps(record)


# ---------------------------------------------------------------------------
# TestLookerIngestorExport
# ---------------------------------------------------------------------------


class TestLookerIngestorExport:
    """U2/R3/R4 — document projection, ids, metadata, and JSON safety."""

    def _sample_rows_by_content_type(self):
        return {
            "look": [{"id": 1, "title": "Orders look", "description": "desc"}],
            "dashboard": [{"id": 2, "title": "Ops dashboard"}],
            "lookml_model": [
                {
                    "name": "ecommerce",
                    "project_name": "shop",
                    "label": "Ecommerce",
                    "explores": [
                        {
                            "name": "orders",
                            "label": "Orders",
                            "description": "Order facts",
                            "hidden": False,
                            "group_label": "Commerce",
                        }
                    ],
                }
            ],
            "folder": [{"id": 3, "name": "Shared"}],
            "project": [{"id": "shop", "name": "shop"}],
        }

    def test_document_shape_and_metadata(self):
        client = MagicMock()
        client.all_looks.return_value = [
            {"id": 1, "title": "Orders look", "description": "desc"}
        ]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_looks()
        documents = ingestor.export_as_documents(data)

        assert len(documents) == 1
        document = documents[0]
        assert set(document) == {"id", "text", "metadata"}
        assert document["id"] == "looker:look:1"
        assert "Orders look" in document["text"]
        assert document["metadata"]["source"] == "looker"
        assert document["metadata"]["content_type"] == "look"
        assert "base_url" not in document["metadata"]
        assert "base_url" not in json.dumps(document["metadata"])

    def test_metadata_never_contains_credentials(self):
        client = MagicMock()
        client.all_projects.return_value = [
            {
                "id": "shop",
                "name": "shop",
                "client_id": "cid",
                "client_secret": "csecret",
                "secret": "nope",
            }
        ]
        ingestor = _make_ingestor(client)

        data = ingestor.ingest_projects()
        documents = ingestor.export_as_documents(data)

        rendered = json.dumps(documents)
        assert "csecret" not in rendered
        assert "client_secret" not in rendered

    def test_document_ids_are_unique_across_content_types(self):
        from semantica.ingest.looker_ingestor import LookerData

        ingestor = _make_ingestor(MagicMock())
        documents = []
        for content_type, rows in self._sample_rows_by_content_type().items():
            data = LookerData(
                data=rows,
                row_count=len(rows),
                columns=[],
                content_type=content_type,
            )
            documents.extend(ingestor.export_as_documents(data))

        ids = [document["id"] for document in documents]
        assert ids == [
            "looker:look:1",
            "looker:dashboard:2",
            "looker:lookml_model:shop.ecommerce",
            "looker:folder:3",
            "looker:project:shop",
        ]
        assert len(ids) == len(set(ids))

    def test_lookml_model_document_nests_explores(self):
        from semantica.ingest.looker_ingestor import LookerData

        ingestor = _make_ingestor(MagicMock())
        rows = self._sample_rows_by_content_type()["lookml_model"]
        data = LookerData(
            data=rows,
            row_count=len(rows),
            columns=[],
            content_type="lookml_model",
        )

        documents = ingestor.export_as_documents(data)
        metadata = documents[0]["metadata"]

        assert documents[0]["id"] == "looker:lookml_model:shop.ecommerce"
        assert metadata["project_name"] == "shop"
        assert metadata["model_name"] == "ecommerce"
        assert metadata["explores"][0]["id"] == (
            "looker:lookml_model:shop.ecommerce:explore:orders"
        )
        assert metadata["explores"][0]["name"] == "orders"
        assert metadata["explores"][0]["label"] == "Orders"
        assert metadata["explores"][0]["description"] == "Order facts"
        assert metadata["explores"][0]["hidden"] is False
        assert metadata["explores"][0]["group_label"] == "Commerce"
        assert metadata["explores"][0]["parent_model"] == "shop.ecommerce"
        assert "view_name" not in metadata["explores"][0]

    def test_full_export_is_json_serializable(self):
        from semantica.ingest.looker_ingestor import LookerData

        ingestor = _make_ingestor(MagicMock())
        documents = []
        for content_type, rows in self._sample_rows_by_content_type().items():
            data = LookerData(
                data=rows,
                row_count=len(rows),
                columns=[],
                content_type=content_type,
            )
            documents.extend(ingestor.export_as_documents(data))

        json.dumps(documents)

    @requires_looker_sdk
    def test_export_with_sdk_models_and_datetimes_is_json_serializable(self):
        from looker_sdk.sdk.api40 import models as sdk_models

        look = sdk_models.Look(
            id=11,
            title="Timed look",
            created_at=datetime(2024, 5, 6, 7, 8, 9, tzinfo=timezone.utc),
        )
        model = sdk_models.LookmlModel(
            name="ecommerce",
            project_name="shop",
            explores=[
                sdk_models.LookmlModelNavExplore(
                    name="orders",
                    label="Orders",
                    description="Order facts",
                    hidden=False,
                    group_label="Commerce",
                )
            ],
        )
        client = MagicMock()
        client.all_looks.return_value = [look]
        client.all_lookml_models.return_value = [model]
        ingestor = _make_ingestor(client)

        looks_data = ingestor.ingest_looks()
        models_data = ingestor.ingest_lookml_models()

        json.dumps(looks_data.data)
        json.dumps(models_data.data)
        json.dumps(ingestor.export_as_documents(looks_data))
        json.dumps(ingestor.export_as_documents(models_data))


# ---------------------------------------------------------------------------
# TestLookerConnectorSecretLogging — R11/R13
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorSecretLogging(unittest.TestCase):
    """No credential, PAT, or secret-adjacent field may reach a log record.

    Records are captured with :meth:`unittest.TestCase.assertLogs` from the
    connector logger and from the SDK's own transport logger across a
    mocked ``connect()``, the ``test_connection()`` probe, and all five
    metadata reads.
    """

    @staticmethod
    def _secret_rows():
        """Rows carrying every secret-adjacent SDK field."""
        return [
            {
                "id": 1,
                "title": "Orders",
                "project_name": "shop",
                "name": "ecommerce",
                "git_remote_url": (
                    f"https://user:{CLIENT_SECRET}@git.example.com/shop.git"
                ),
                **SECRET_FIELD_VALUES,
            }
        ]

    def test_secret_and_access_token_never_reach_log_records(self):
        from semantica.ingest.looker_ingestor import LookerConnector, LookerIngestor

        client = _make_mock_client()
        rows = self._secret_rows()
        for sdk_method in (
            "all_looks",
            "all_dashboards",
            "all_lookml_models",
            "all_folders",
            "all_projects",
        ):
            getattr(client, sdk_method).return_value = rows

        # The probe fails with an SDK error whose text embeds both a token
        # and the client secret: only the exception type may be logged.
        client.me.side_effect = _looker_sdk.error.SDKError(
            f"auth failed token={ACCESS_TOKEN} secret={CLIENT_SECRET}"
        )

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            connector = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

            with self.assertLogs(CONNECTOR_LOGGER, level="DEBUG") as connector_logs:
                connector.connect()
                assert connector.test_connection() is False

                ingestor = LookerIngestor(connector=connector)
                for method_name in (
                    "ingest_looks",
                    "ingest_dashboards",
                    "ingest_lookml_models",
                    "ingest_folders",
                    "ingest_projects",
                ):
                    data = getattr(ingestor, method_name)()
                    ingestor.export_as_documents(data)

        captured = "\n".join(connector_logs.output)
        assert connector_logs.output, "expected connector log records"

        for secret in (CLIENT_SECRET, ACCESS_TOKEN, *SECRET_FIELD_VALUES.values()):
            assert secret not in captured


# ---------------------------------------------------------------------------
# TestLookerConnectorTransportHardening — KTD2 compensating controls
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorTransportHardening:
    """The SDK session must not follow redirects or trust proxy env vars."""

    def _connect_with_real_session(self, session, base_url: str = PUBLIC_BASE_URL):
        """Connect a LookerConnector whose client carries *session*."""
        from semantica.ingest.looker_ingestor import LookerConnector

        client = _make_mock_client(base_url=base_url)
        client.transport.session = session

        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            connector = LookerConnector(
                base_url=base_url,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            connector.connect()
        return connector

    def test_redirect_response_is_not_followed(self):
        target = f"{PUBLIC_BASE_URL}/api/4.0/looks"
        seen = []

        class _RedirectAdapter(BaseAdapter):
            def send(self, request, **kwargs):
                seen.append(request.url)
                response = requests.Response()
                response.status_code = 302
                response.headers["Location"] = "https://evil.example.com/steal"
                response.url = request.url
                response.request = request
                response.raw = None
                return response

            def close(self):
                pass

        session = requests.Session()
        assert session.max_redirects != 0  # default is a real redirect cap

        self._connect_with_real_session(session)
        session.mount("https://", _RedirectAdapter())

        assert session.max_redirects == 0
        with pytest.raises(TooManyRedirects):
            session.get(target)

        # The redirect target was never requested: only the original hop.
        assert seen == [target]

    def test_proxy_environment_variable_is_not_honoured(self, monkeypatch):
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")

        session = requests.Session()
        assert session.trust_env is True  # default honours the environment

        self._connect_with_real_session(session)

        assert session.trust_env is False
        settings = session.merge_environment_settings(
            f"{PUBLIC_BASE_URL}/api/4.0/looks", {}, None, None, None
        )
        assert settings["proxies"] == {}

    def test_connections_are_pinned_to_the_validated_address(self):
        session = requests.Session()

        self._connect_with_real_session(session)

        adapter = session.adapters.get("https://")
        assert getattr(adapter, "_semantica_pinned", False) is True

    def test_metadata_read_is_routed_through_the_ssrf_validator(self):
        """AE1 — every SDK request must pass the repository SSRF validator.

        The SDK's ``all_looks`` is wired to issue a real request through the
        session that ``connect()`` hardens.  With the validator patched to
        raise, the read must fail *before* the pinned transport is reached.
        """
        from semantica.ingest.looker_ingestor import LookerIngestor
        from semantica.utils.exceptions import ValidationError

        target = f"{PUBLIC_BASE_URL}/api/4.0/looks"
        session = requests.Session()
        client = _make_mock_client()
        client.transport.session = session

        class _RecordingAdapter(BaseAdapter):
            """Pinned-transport stand-in that never dials the network."""

            def __init__(self):
                self.seen = []

            def send(self, request, **kwargs):
                self.seen.append(request.url)
                response = requests.Response()
                response.status_code = 200
                response.url = request.url
                response.request = request
                response._content = b"[]"
                return response

            def close(self):
                pass

        delegate = _RecordingAdapter()

        def _all_looks(**_kwargs):
            session.get(target)
            return []

        client.all_looks.side_effect = _all_looks

        with (
            patch(
                "semantica.ingest.looker_ingestor.looker_sdk.init40",
                return_value=client,
            ),
            patch(
                "semantica.ingest.looker_ingestor._make_pinned_adapter",
                return_value=delegate,
            ),
        ):
            ingestor = LookerIngestor(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )

            with patch(
                "semantica.ingest.looker_ingestor.validate_url_for_request",
                side_effect=ValidationError("blocked by the test double"),
            ):
                with pytest.raises(ValidationError):
                    ingestor.ingest_looks()

        # The validator raised before the pinned adapter was reached.
        assert delegate.seen == []

    @pytest.mark.parametrize(
        ("base_url", "expected_host"),
        [
            ("https://[2001:db8::1]", "[2001:db8::1]"),
            ("https://[2001:db8::1]:8443", "[2001:db8::1]:8443"),
        ],
    )
    def test_ipv6_host_header_is_bracketed(self, base_url, expected_host):
        """AE4 — the pinned session's Host header is a valid authority."""
        session = requests.Session()

        with (
            patch("semantica.ingest.looker_ingestor.validate_url_for_request"),
            patch(
                "semantica.ingest.looker_ingestor._resolve_pinned_ips",
                return_value=["2001:db8::1"],
            ),
        ):
            self._connect_with_real_session(session, base_url=base_url)

        assert session.headers["Host"] == expected_host


# ---------------------------------------------------------------------------
# TestLookerHardeningRegressions — defects found in code review
# ---------------------------------------------------------------------------


class TestLookerHardeningRegressions:
    """Regressions for review findings: redaction and config forwarding."""

    def test_userinfo_is_scrubbed_without_a_scheme(self):
        """Credentials in a scheme-less remote must not survive."""
        from semantica.ingest.looker_ingestor import _scrub_url_userinfo

        assert (
            _scrub_url_userinfo("oauth2:glpat-TOKEN@gitlab.example.com/org/r.git")
            == "gitlab.example.com/org/r.git"
        )
        assert (
            _scrub_url_userinfo("git@github.com:org/repo.git")
            == "github.com:org/repo.git"
        )
        assert _scrub_url_userinfo("https://user:pw@example.com/r.git") == (
            "https://example.com/r.git"
        )

    def test_userinfo_in_path_is_not_treated_as_credentials(self):
        from semantica.ingest.looker_ingestor import _scrub_url_userinfo

        assert (
            _scrub_url_userinfo("https://example.com/path@file")
            == "https://example.com/path@file"
        )

    def test_userinfo_is_scrubbed_when_an_at_sign_follows_the_authority(self):
        """The deciding '@' must be the one inside the authority section."""
        from semantica.ingest.looker_ingestor import _scrub_url_userinfo

        assert _scrub_url_userinfo("https://user:pw@example.com/path@file") == (
            "https://example.com/path@file"
        )
        assert (
            _scrub_url_userinfo(
                "https://oauth2:glpat-SECRET@gitlab.example.com/org/repo.git"
                "?ref=user@example.com"
            )
            == "https://gitlab.example.com/org/repo.git?ref=user@example.com"
        )

    def test_ipv6_authority_userinfo_is_scrubbed(self):
        from semantica.ingest.looker_ingestor import _scrub_url_userinfo

        assert (
            _scrub_url_userinfo("https://user:pw@[::1]:8080/x")
            == "https://[::1]:8080/x"
        )

    def test_ambiguous_password_containing_a_slash_fails_closed(self):
        """A password containing '/' defeats the authority split."""
        from semantica.ingest.looker_ingestor import (
            _REDACTED_URL,
            _scrub_url_userinfo,
        )

        assert _scrub_url_userinfo("https://user:pa/ss@host/repo.git") == (
            _REDACTED_URL
        )
        # A later '@' in the path must not rescue the earlier userinfo.
        assert (
            _scrub_url_userinfo(
                "https://alice:s3cr3t@git.example.com/groups/dev@example.com/repo.git"
            )
            == "https://git.example.com/groups/dev@example.com/repo.git"
        )
        assert (
            _scrub_url_userinfo("https://user:pw@host/repo.git?x=@y")
            == "https://host/repo.git?x=@y"
        )

    def test_host_port_authority_is_not_treated_as_userinfo(self):
        from semantica.ingest.looker_ingestor import _scrub_url_userinfo

        assert (
            _scrub_url_userinfo("https://example.com:8443/path@file")
            == "https://example.com:8443/path@file"
        )
        assert (
            _scrub_url_userinfo("https://[::1]:8080/path@file")
            == "https://[::1]:8080/path@file"
        )

    def test_guard_adapter_pinned_marker_is_derived_and_read_only(self):
        """``_semantica_pinned`` is derived from the delegate, not cached."""
        from semantica.ingest.looker_ingestor import _SSRFGuardAdapter

        adapter = _SSRFGuardAdapter(allow_private_ips=False)

        assert adapter._semantica_pinned is False
        with pytest.raises(AttributeError):
            adapter._semantica_pinned = True

    @requires_looker_sdk
    def test_ingestor_config_dict_does_not_collide_with_named_arguments(self):
        """A config dict naming a connector parameter must not raise."""
        from semantica.ingest.looker_ingestor import LookerConnector, LookerIngestor

        ingestor = LookerIngestor(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            config={"allow_private_ips": True},
        )

        assert isinstance(ingestor.connector, LookerConnector)

    @requires_looker_sdk
    def test_env_conflict_message_does_not_leak_userinfo(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        env_url = "https://envuser:ENVSECRET@looker.example.com"
        with patch.dict(os.environ, {"LOOKERSDK_BASE_URL": env_url}):
            with pytest.raises(ValidationError) as exc_info:
                LookerConnector(
                    base_url=PUBLIC_BASE_URL,
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                )

        message = str(exc_info.value)
        assert "ENVSECRET" not in message
        assert "envuser" not in message

    @requires_looker_sdk
    def test_ini_conflict_message_does_not_leak_userinfo(self):
        from semantica.ingest.looker_ingestor import LookerConnector
        from semantica.utils.exceptions import ValidationError

        raw_config = {"base_url": "https://iniuser:INISECRET@other.example.com"}

        with patch.object(LookerConnector, "_raw_read_config", return_value=raw_config):
            with pytest.raises(ValidationError) as exc_info:
                LookerConnector(
                    base_url=PUBLIC_BASE_URL,
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                )

        message = str(exc_info.value)
        assert "INISECRET" not in message
        assert "iniuser" not in message


# ---------------------------------------------------------------------------
# TestLookerIngestorConfigForwarding — config keys reach the connector
# ---------------------------------------------------------------------------


class TestLookerIngestorConfigForwarding:
    """A ``config`` value for a named connector argument must reach it.

    ``_CONNECTOR_ARGUMENT_NAMES`` keeps those keys out of the forwarded
    ``**kwargs`` (so the call cannot collide), which means the ingestor must
    resolve each one explicitly instead of silently dropping it.
    """

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("base_url", PUBLIC_BASE_URL),
            ("client_id", "config-client-id"),
            ("client_secret", "config-client-secret"),
            ("config_file", "custom.ini"),
            ("section", "production"),
        ],
    )
    def test_config_value_reaches_the_connector(self, key, value):
        from semantica.ingest.looker_ingestor import LookerIngestor

        with patch(
            "semantica.ingest.looker_ingestor.LookerConnector"
        ) as mock_connector:
            LookerIngestor(config={key: value})

        assert mock_connector.call_args.kwargs[key] == value

    def test_named_argument_wins_over_config_value(self):
        from semantica.ingest.looker_ingestor import LookerIngestor

        with patch(
            "semantica.ingest.looker_ingestor.LookerConnector"
        ) as mock_connector:
            LookerIngestor(
                base_url=PUBLIC_BASE_URL,
                config={"base_url": "https://config.example.com"},
            )

        assert mock_connector.call_args.kwargs["base_url"] == PUBLIC_BASE_URL


# ---------------------------------------------------------------------------
# TestLookerIngestorMalformedRecords — SDK data problems fail safely
# ---------------------------------------------------------------------------


class TestLookerIngestorMalformedRecords:
    """Malformed SDK records must use the documented exception types."""

    def test_unsupported_record_type_raises_processing_error(self):
        from semantica.utils.exceptions import ProcessingError

        client = MagicMock()
        client.all_looks.return_value = [42]
        ingestor = _make_ingestor(client)

        with pytest.raises(ProcessingError) as exc_info:
            ingestor.ingest_looks()

        assert "Unsupported Looker record type: int" in str(exc_info.value)

    def test_record_conversion_failure_is_chained(self):
        from semantica.utils.exceptions import ProcessingError

        class _Unconvertible:
            __slots__ = ()

            def items(self):
                raise RuntimeError("boom")

            def keys(self):
                raise RuntimeError("boom")

        client = MagicMock()
        client.all_looks.return_value = [_Unconvertible()]
        ingestor = _make_ingestor(client)

        with pytest.raises(ProcessingError) as exc_info:
            ingestor.ingest_looks()

        assert isinstance(exc_info.value.__cause__, RuntimeError)
        assert "Unsupported Looker record type: _Unconvertible" in str(exc_info.value)

    def test_non_mapping_row_raises_documented_validation_error(self):
        from semantica.ingest.looker_ingestor import LookerData
        from semantica.utils.exceptions import ValidationError

        ingestor = _make_ingestor(MagicMock())
        data = LookerData(data=["oops"], row_count=1, columns=[], content_type="look")

        with pytest.raises(ValidationError) as exc_info:
            ingestor.export_as_documents(data)

        assert "str" in str(exc_info.value)

    def test_non_iterable_explores_degrades_safely(self):
        from semantica.ingest.looker_ingestor import LookerData

        ingestor = _make_ingestor(MagicMock())
        data = LookerData(
            data=[{"name": "model", "project_name": "proj", "explores": 5}],
            row_count=1,
            columns=[],
            content_type="lookml_model",
        )

        documents = ingestor.export_as_documents(data)

        metadata = documents[0]["metadata"]
        assert metadata["explores"] == []
        assert metadata["explore_count"] == 0


# ---------------------------------------------------------------------------
# TestLookerIngestorOptionForwarding — **options reach the SDK method
# ---------------------------------------------------------------------------


class TestLookerIngestorOptionForwarding:
    """Each read's documented ``**options`` must reach the SDK call."""

    _READS = [
        ("ingest_looks", "all_looks"),
        ("ingest_dashboards", "all_dashboards"),
        ("ingest_lookml_models", "all_lookml_models"),
        ("ingest_folders", "all_folders"),
        ("ingest_projects", "all_projects"),
    ]

    @pytest.mark.parametrize(("method_name", "sdk_method"), _READS)
    def test_options_are_forwarded_to_the_sdk_method(self, method_name, sdk_method):
        client = MagicMock()
        getattr(client, sdk_method).return_value = []
        ingestor = _make_ingestor(client)

        getattr(ingestor, method_name)(fields="id,title", limit=5, offset=10)

        assert getattr(client, sdk_method).call_args == call(
            fields="id,title", limit=5, offset=10
        )

    @pytest.mark.parametrize(("method_name", "sdk_method"), _READS)
    def test_no_options_sends_no_keyword_arguments(self, method_name, sdk_method):
        client = MagicMock()
        getattr(client, sdk_method).return_value = []
        ingestor = _make_ingestor(client)

        getattr(ingestor, method_name)()

        assert getattr(client, sdk_method).call_args == call()


# ---------------------------------------------------------------------------
# TestLookerIngestorConfigOptIn — AE2/AE3 config allow_private_ips resolution
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerIngestorConfigOptIn:
    """``config={"allow_private_ips": True}`` must reach the connector."""

    @pytest.mark.parametrize("kwargs", [{}, {"allow_private_ips": False}])
    def test_config_opt_in_wins_when_named_argument_is_left_at_default(self, kwargs):
        """AE2/AE3 — the config entry wins while the named arg is unset."""
        from semantica.ingest.looker_ingestor import LookerIngestor

        ingestor = LookerIngestor(
            base_url=PRIVATE_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            config={"allow_private_ips": True},
            **kwargs,
        )

        assert ingestor.connector.allow_private_ips is True

    def test_config_value_wins_over_a_non_default_named_argument(self):
        """The connector's config-wins precedence, parsed with parse_bool."""
        from semantica.ingest.looker_ingestor import LookerIngestor

        ingestor = LookerIngestor(
            base_url=PUBLIC_BASE_URL,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            allow_private_ips=True,
            config={"allow_private_ips": "0"},
        )

        assert ingestor.connector.allow_private_ips is False


# ---------------------------------------------------------------------------
# TestLookerConnectorErrorDocEgress — the SDK's error-doc fetch is neutralised
# ---------------------------------------------------------------------------


@requires_looker_sdk
class TestLookerConnectorErrorDocEgress:
    """The SDK's error-documentation lookup must not make its own requests.

    ``looker_sdk.error.ErrorDocHelper.get_index`` performs a bare
    ``requests.get`` (fresh session, ``trust_env=True``, no timeout, no
    redirect cap, no SSRF validation) whenever the API returns a non-2xx
    response.  ``connect()`` disables it, so a failing API call still raises
    the normal SDK error without opening a second, unguarded egress path.
    """

    def _connected_connector(self):
        from semantica.ingest.looker_ingestor import LookerConnector

        client = _make_mock_client()
        with patch(
            "semantica.ingest.looker_ingestor.looker_sdk.init40",
            return_value=client,
        ):
            connector = LookerConnector(
                base_url=PUBLIC_BASE_URL,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
            )
            connector.connect()
        return connector

    def test_error_doc_lookup_makes_no_network_call(self):
        import looker_sdk.error as sdk_error

        self._connected_connector()

        helper = sdk_error.ErrorDocHelper()
        documentation_url = "https://docs.looker.com/r/err/4.0/404/notfound"
        with patch.object(
            sdk_error.requests, "get", side_effect=AssertionError("network egress")
        ) as mock_get:
            error_doc_url, error_doc = helper.parse_and_lookup(documentation_url)

        mock_get.assert_not_called()
        # No index was fetched, so no per-code document URL was resolved
        # either: the helper falls back to its base URL and the inline
        # "no documentation" message.
        assert error_doc_url == helper.ERROR_CODES_URL
        assert "No documentation found" in error_doc

    def test_non_2xx_response_raises_the_normal_sdk_error(self):
        import looker_sdk.error as sdk_error
        from looker_sdk.rtl import api_methods

        self._connected_connector()

        documentation_url = "https://docs.looker.com/r/err/4.0/404/notfound"

        class _Auth:
            class settings:  # noqa: N801 - mirrors the SDK settings shape
                base_url = PUBLIC_BASE_URL

        class _Response:
            ok = False
            encoding = "utf-8"
            value = b'{"message": "not found"}'

        def _deserialize(*, data, structure):
            return sdk_error.SDKError(
                message="not found", documentation_url=documentation_url
            )

        methods = api_methods.APIMethods(
            auth=_Auth(),
            deserialize=_deserialize,
            serialize=MagicMock(),
            transport=MagicMock(),
            api_version="4.0",
        )

        with patch.object(
            sdk_error.requests, "get", side_effect=AssertionError("network egress")
        ) as mock_get:
            with pytest.raises(sdk_error.SDKError) as exc_info:
                methods._return(_Response(), structure=sdk_error.SDKError)

        mock_get.assert_not_called()
        assert "No documentation found" in exc_info.value.error_doc

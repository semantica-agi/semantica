"""
Unit tests for Dynamics365Connector and Dynamics365Ingestor.

All MSAL and HTTP calls are mocked — no live Dynamics 365 org is required.
"""

from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest

try:
    import msal  # noqa: F401
    MSAL_LIB_AVAILABLE = True
except ImportError:
    MSAL_LIB_AVAILABLE = False


# ---------------------------------------------------------------------------
# autouse fixture: mock msal when not installed
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_msal_if_needed(request):
    _is_import_test = (
        getattr(request.node.cls, "__name__", "") == "TestImportBehaviourWithoutLib"
    )
    if not MSAL_LIB_AVAILABLE and not _is_import_test:
        msal_mod = MagicMock()
        with patch.dict("sys.modules", {"msal": msal_mod}):
            import semantica.ingest as _ingest_mod
            for _name in ("Dynamics365Ingestor", "Dynamics365Data", "Dynamics365Connector"):
                _ingest_mod.__dict__.pop(_name, None)
            yield
            for _name in ("Dynamics365Ingestor", "Dynamics365Data", "Dynamics365Connector"):
                _ingest_mod.__dict__.pop(_name, None)
    else:
        yield


# ---------------------------------------------------------------------------
# Import behaviour
# ---------------------------------------------------------------------------


class TestImportBehaviourWithoutLib:
    def test_raises_import_error_without_msal(self):
        with patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", False):
            with pytest.raises((ImportError, Exception)):
                from semantica.ingest.dynamics365_ingestor import Dynamics365Connector
                Dynamics365Connector(
                    tenant_id="t", client_id="c", client_secret="s",
                    org_url="https://org.crm.dynamics.com",
                )


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class TestDynamics365Connector:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_init_with_credentials(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Connector
        connector = Dynamics365Connector(
            tenant_id="tenant-id",
            client_id="client-id",
            client_secret="secret",
            org_url="https://myorg.crm.dynamics.com",
        )
        assert connector.org_url == "https://myorg.crm.dynamics.com"

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_init_raises_without_org_url(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Connector
        from semantica.utils.exceptions import ValidationError
        with pytest.raises((ValidationError, Exception)):
            Dynamics365Connector(
                tenant_id="t", client_id="c", client_secret="s", org_url=None,
            )

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_init_raises_without_credentials(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Connector
        from semantica.utils.exceptions import ValidationError
        with pytest.raises((ValidationError, Exception)):
            Dynamics365Connector(org_url="https://org.crm.dynamics.com")


# ---------------------------------------------------------------------------
# Ingestor
# ---------------------------------------------------------------------------


class TestDynamics365IngestorEntity:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_ingest_entity_returns_data(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Data, Dynamics365Ingestor
        import semantica.ingest.dynamics365_ingestor as _mod

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "value": [
                {"accountid": "acc-001", "name": "Contoso", "statecode": 0},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_ssrf = MagicMock(return_value=mock_response)
        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_silent.return_value = None
        mock_msal_app.acquire_token_for_client.return_value = {
            "access_token": "fake-token"
        }

        with patch.object(_mod, "request_with_ssrf_guard", mock_ssrf), \
             patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app

            ingestor = Dynamics365Ingestor(
                tenant_id="t",
                client_id="c",
                client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            data = ingestor.ingest_entity("accounts", select=["accountid", "name"])

        assert isinstance(data, Dynamics365Data)
        assert len(data.records) == 1
        assert data.records[0]["name"] == "Contoso"
        assert data.entity_name == "accounts"
        assert data.row_count == 1

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_ingest_entity_raises_on_empty_name(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Ingestor
        from semantica.utils.exceptions import ValidationError
        import semantica.ingest.dynamics365_ingestor as _mod

        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_silent.return_value = None
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok"}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            with pytest.raises((ValidationError, Exception)):
                ingestor.ingest_entity("")


# ---------------------------------------------------------------------------
# export_as_documents
# ---------------------------------------------------------------------------


class TestDynamics365ExportDocuments:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_export_document_shape(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Data, Dynamics365Ingestor

        data = Dynamics365Data(
            records=[{"accountid": "acc-001", "name": "Contoso"}],
            entity_name="accounts",
            row_count=1,
            columns=["accountid", "name"],
            org_url="https://myorg.crm.dynamics.com",
        )
        import semantica.ingest.dynamics365_ingestor as _mod
        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_silent.return_value = None
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok"}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            docs = ingestor.export_as_documents(data)

        assert len(docs) == 1
        doc = docs[0]
        assert "id" in doc and "text" in doc and "metadata" in doc
        assert doc["metadata"]["source"] == "dynamics365"
        assert doc["metadata"]["entity_name"] == "accounts"
        assert doc["metadata"]["org_url"] == "https://myorg.crm.dynamics.com"
        assert "Contoso" in doc["text"]

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_export_empty_data(self):
        from semantica.ingest.dynamics365_ingestor import Dynamics365Data, Dynamics365Ingestor
        import semantica.ingest.dynamics365_ingestor as _mod

        data = Dynamics365Data(
            records=[], entity_name="contacts", row_count=0,
            columns=[], org_url="https://myorg.crm.dynamics.com",
        )
        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_silent.return_value = None
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok"}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            docs = ingestor.export_as_documents(data)

        assert docs == []

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_export_opportunities_uses_opportunityid(self):
        """Bug fix: 'opportunities'[:-1] == 'opportunitie', not 'opportunity'."""
        from semantica.ingest.dynamics365_ingestor import Dynamics365Data, Dynamics365Ingestor
        import semantica.ingest.dynamics365_ingestor as _mod

        data = Dynamics365Data(
            records=[{"opportunityid": "opp-001", "name": "Deal A"}],
            entity_name="opportunities",
            row_count=1,
            columns=["opportunityid", "name"],
            org_url="https://myorg.crm.dynamics.com",
        )
        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok"}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            docs = ingestor.export_as_documents(data)

        assert len(docs) == 1
        assert docs[0]["id"] == "opp-001", (
            f"Expected 'opp-001' but got {docs[0]['id']!r} — irregular plural map broken"
        )


# ---------------------------------------------------------------------------
# Context manager on Ingestor
# ---------------------------------------------------------------------------


class TestDynamics365IngestorContextManager:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_ingestor_context_manager_calls_connect_and_disconnect(self):
        """Dynamics365Ingestor must support `with` and delegate to connector."""
        from semantica.ingest.dynamics365_ingestor import Dynamics365Ingestor
        import semantica.ingest.dynamics365_ingestor as _mod

        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            with ingestor as ctx:
                assert ctx is ingestor
                assert ingestor._connector._access_token == "tok"

        # After __exit__ the token should be cleared
        assert ingestor._connector._access_token is None


# ---------------------------------------------------------------------------
# nextLink origin validation
# ---------------------------------------------------------------------------


class TestNextLinkOriginValidation:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_cross_origin_nextlink_raises_processing_error(self):
        """nextLink pointing to a different origin must raise ProcessingError."""
        from semantica.ingest.dynamics365_ingestor import Dynamics365Ingestor
        from semantica.utils.exceptions import ProcessingError
        import semantica.ingest.dynamics365_ingestor as _mod

        # First page returns a cross-origin nextLink.
        page1 = MagicMock()
        page1.raise_for_status = MagicMock()
        page1.json.return_value = {
            "value": [{"accountid": "a1", "name": "Acme"}],
            "@odata.nextLink": "https://evil.attacker.com/api/data/v9.2/accounts?$skip=100",
        }

        mock_ssrf = MagicMock(return_value=page1)
        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

        with patch.object(_mod, "request_with_ssrf_guard", mock_ssrf), \
             patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            ingestor = Dynamics365Ingestor(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            with pytest.raises(ProcessingError, match="nextLink origin mismatch"):
                ingestor.ingest_entity("accounts")


# ---------------------------------------------------------------------------
# Token expiry
# ---------------------------------------------------------------------------


class TestTokenExpiry:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_expired_token_triggers_reconnect(self):
        """_ensure_connected must call connect() again when token has expired."""
        from semantica.ingest.dynamics365_ingestor import Dynamics365Connector
        import semantica.ingest.dynamics365_ingestor as _mod
        import time as _time

        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_for_client.return_value = {
            "access_token": "fresh-token",
            "expires_in": 3600,
        }

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            connector = Dynamics365Connector(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            # Simulate an already-expired token
            connector._access_token = "old-token"
            connector._token_expires_at = _time.time() - 1  # already expired

            connector._ensure_connected()

        # connect() was called again (total calls == 1 since we set state manually)
        assert mock_msal_app.acquire_token_for_client.call_count == 1
        assert connector._access_token == "fresh-token"


# ---------------------------------------------------------------------------
# Package-level exports
# ---------------------------------------------------------------------------

_EXPORTED = ("Dynamics365Ingestor", "Dynamics365Data", "Dynamics365Connector")


class TestPackageExports:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_classes_importable_from_package(self):
        import semantica.ingest as ingest_pkg
        import semantica.ingest.dynamics365_ingestor as _mod

        for name in _EXPORTED:
            ingest_pkg.__dict__.pop(name, None)
        try:
            from semantica.ingest import (
                Dynamics365Connector,
                Dynamics365Data,
                Dynamics365Ingestor,
            )
        finally:
            for name in _EXPORTED:
                ingest_pkg.__dict__.pop(name, None)

        assert Dynamics365Ingestor is _mod.Dynamics365Ingestor
        assert Dynamics365Data is _mod.Dynamics365Data
        assert Dynamics365Connector is _mod.Dynamics365Connector
        assert set(_EXPORTED) <= set(ingest_pkg.__all__)

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", False)
    def test_package_import_without_msal_gives_install_hint(self):
        import semantica.ingest as ingest_pkg

        ingest_pkg.__dict__.pop("Dynamics365Ingestor", None)
        with pytest.raises(ImportError, match=r"semantica\[ingest-dynamics365\]"):
            from semantica.ingest import Dynamics365Ingestor  # noqa: F401


# ---------------------------------------------------------------------------
# MSAL transport goes through the SSRF guard
# ---------------------------------------------------------------------------


class TestMsalTransport:

    @patch("semantica.ingest.dynamics365_ingestor.DYNAMICS_AVAILABLE", True)
    def test_connect_passes_guarded_http_client_to_msal(self):
        import semantica.ingest.dynamics365_ingestor as _mod

        mock_msal_app = MagicMock()
        mock_msal_app.acquire_token_for_client.return_value = {"access_token": "tok"}

        with patch.object(_mod, "_msal") as mock_msal_mod:
            mock_msal_mod.ConfidentialClientApplication.return_value = mock_msal_app
            connector = _mod.Dynamics365Connector(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
                timeout=12,
            )
            connector.connect()

        kwargs = mock_msal_mod.ConfidentialClientApplication.call_args.kwargs
        assert isinstance(kwargs["http_client"], _mod._SSRFGuardedHttpClient)
        assert kwargs["http_client"].timeout == 12

    def test_guarded_http_client_routes_get_and_post_through_guard(self):
        import semantica.ingest.dynamics365_ingestor as _mod

        mock_ssrf = MagicMock()
        client = _mod._SSRFGuardedHttpClient(timeout=5)
        token_url = "https://login.microsoftonline.com/t/oauth2/v2.0/token"
        config_url = (
            "https://login.microsoftonline.com/t/v2.0/"
            ".well-known/openid-configuration"
        )

        with patch.object(_mod, "request_with_ssrf_guard", mock_ssrf):
            client.get(config_url, headers={"X": "1"})
            client.post(token_url, data={"grant_type": "client_credentials"})

        assert mock_ssrf.call_args_list == [
            call("GET", config_url, params=None, headers={"X": "1"}, timeout=5),
            call(
                "POST", token_url,
                params=None, data={"grant_type": "client_credentials"},
                headers=None, timeout=5,
            ),
        ]

    @pytest.mark.skipif(not MSAL_LIB_AVAILABLE, reason="msal not installed")
    def test_real_msal_requests_go_through_guard(self):
        import semantica.ingest.dynamics365_ingestor as _mod
        from semantica.utils.exceptions import ProcessingError

        mock_ssrf = MagicMock(side_effect=RuntimeError("guarded"))
        with patch.object(_mod, "request_with_ssrf_guard", mock_ssrf):
            connector = _mod.Dynamics365Connector(
                tenant_id="t", client_id="c", client_secret="s",
                org_url="https://myorg.crm.dynamics.com",
            )
            with pytest.raises(ProcessingError, match="guarded"):
                connector.connect()

        assert mock_ssrf.called
        assert all(
            c.args[1].startswith("https://login.microsoftonline.com/")
            for c in mock_ssrf.call_args_list
        )

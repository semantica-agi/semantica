"""
Unit tests for Dynamics365Connector and Dynamics365Ingestor.

All MSAL and HTTP calls are mocked — no live Dynamics 365 org is required.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

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

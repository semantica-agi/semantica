"""
Unit tests for TableauConnector and TableauIngestor.

All Tableau API calls are mocked — no real Tableau Server or Cloud account
is required.

Test structure mirrors tests/test_salesforce_ingestor.py:
  - autouse fixture mocks tableauserverclient when not installed
  - @patch("...TABLEAU_AVAILABLE", True) guards every test that needs
    the library to appear installed
  - credentials are always supplied so secrets are never logged or
    embedded in assertions
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Check whether tableauserverclient is available in this environment.
try:
    import tableauserverclient  # noqa: F401

    TSC_LIB_AVAILABLE = True
except ImportError:
    TSC_LIB_AVAILABLE = False


# ---------------------------------------------------------------------------
# autouse fixture: mock tableauserverclient when not installed
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_tsc_if_needed(request):
    """If tableauserverclient is absent, inject a minimal stub for most tests."""
    _is_import_behaviour_test = (
        getattr(request.node.cls, "__name__", "") == "TestImportBehaviourWithoutLib"
    )

    if not TSC_LIB_AVAILABLE and not _is_import_behaviour_test:
        tsc_mod = MagicMock()

        with patch.dict(
            "sys.modules",
            {"tableauserverclient": tsc_mod},
        ):
            # Clear any cached lazy exports from semantica.ingest
            import semantica.ingest as _ingest_mod

            for _name in ("TableauIngestor", "TableauData", "TableauConnector"):
                _ingest_mod.__dict__.pop(_name, None)

            yield
            # Cleanup
            for _name in ("TableauIngestor", "TableauData", "TableauConnector"):
                _ingest_mod.__dict__.pop(_name, None)
    else:
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_workbook(wb_id="wb-001", name="Sales Dashboard", project_name="Finance"):
    wb = MagicMock()
    wb.id = wb_id
    wb.name = name
    wb.project_name = project_name
    wb.owner_id = "owner-001"
    wb.content_url = "SalesDashboard"
    wb.show_tabs = True
    wb.size = 1
    wb.created_at = datetime(2026, 1, 1)
    wb.updated_at = datetime(2026, 6, 1)
    return wb


def _make_mock_datasource(ds_id="ds-001", name="Orders DS", project_name="Finance"):
    ds = MagicMock()
    ds.id = ds_id
    ds.name = name
    ds.project_name = project_name
    ds.content_url = "OrdersDS"
    ds.datasource_type = "postgres"
    ds.created_at = datetime(2026, 1, 1)
    ds.updated_at = datetime(2026, 6, 1)
    return ds


# ---------------------------------------------------------------------------
# Import behaviour (without lib)
# ---------------------------------------------------------------------------


class TestImportBehaviourWithoutLib:
    """Verify that a clear ImportError is raised when TSC is not installed."""

    def test_tableau_ingestor_raises_import_error_without_tsc(self):
        with patch(
            "semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", False
        ):
            with pytest.raises(ImportError, match="tableauserverclient"):
                from semantica.ingest.tableau_ingestor import TableauConnector

                TableauConnector(
                    server_url="https://tableau.example.com",
                    token_name="t",
                    token_value="v",
                )


# ---------------------------------------------------------------------------
# TableauConnector
# ---------------------------------------------------------------------------


class TestTableauConnector:
    """Unit tests for TableauConnector authentication and lifecycle."""

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_init_with_pat_credentials(self):
        from semantica.ingest.tableau_ingestor import TableauConnector

        connector = TableauConnector(
            server_url="https://tableau.example.com",
            site_name="mysite",
            token_name="my-token",
            token_value="secret-value",
        )
        assert connector.server_url == "https://tableau.example.com"
        assert connector.site_name == "mysite"
        assert connector._server is None

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_init_raises_without_server_url(self):
        from semantica.ingest.tableau_ingestor import TableauConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="server_url"):
            TableauConnector(token_name="t", token_value="v")

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_init_raises_without_credentials(self):
        from semantica.ingest.tableau_ingestor import TableauConnector
        from semantica.utils.exceptions import ValidationError

        with pytest.raises(ValidationError, match="authentication"):
            TableauConnector(server_url="https://tableau.example.com")

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_connect_uses_pat_auth(self):
        from semantica.ingest.tableau_ingestor import TableauConnector
        import semantica.ingest.tableau_ingestor as _mod

        mock_server = MagicMock()
        mock_tsc = MagicMock()
        mock_tsc.Server.return_value = mock_server
        mock_tsc.PersonalAccessTokenAuth.return_value = MagicMock()

        with patch.object(_mod, "TSC", mock_tsc):
            connector = TableauConnector(
                server_url="https://tableau.example.com",
                token_name="my-token",
                token_value="secret-value",
            )
            result = connector.connect()

        assert result is mock_server
        mock_tsc.PersonalAccessTokenAuth.assert_called_once()
        mock_server.auth.sign_in.assert_called_once()

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_connect_returns_existing_client(self):
        from semantica.ingest.tableau_ingestor import TableauConnector

        connector = TableauConnector(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        mock_server = MagicMock()
        connector._server = mock_server  # pre-set
        result = connector.connect()
        assert result is mock_server

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_disconnect_clears_server(self):
        from semantica.ingest.tableau_ingestor import TableauConnector

        connector = TableauConnector(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        connector._server = MagicMock()
        connector.disconnect()
        assert connector._server is None


# ---------------------------------------------------------------------------
# TableauIngestor.ingest_workbooks
# ---------------------------------------------------------------------------


class TestTableauIngestorWorkbooks:
    """Unit tests for TableauIngestor.ingest_workbooks."""

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_ingest_workbooks_returns_tableau_data(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        mock_wb = _make_mock_workbook()
        mock_server = MagicMock()
        mock_server.workbooks.get.return_value = ([mock_wb], None)

        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        ingestor.connector._server = mock_server

        data = ingestor.ingest_workbooks()

        assert isinstance(data, TableauData)
        assert len(data.workbooks) == 1
        assert data.workbooks[0]["id"] == "wb-001"
        assert data.workbooks[0]["name"] == "Sales Dashboard"
        assert data.row_count == 1
        assert data.server_url == "https://tableau.example.com"

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_ingest_workbooks_filters_by_project(self):
        from semantica.ingest.tableau_ingestor import TableauIngestor

        wb_finance = _make_mock_workbook(wb_id="wb-001", project_name="Finance")
        wb_sales = _make_mock_workbook(wb_id="wb-002", project_name="Sales")
        mock_server = MagicMock()
        mock_server.workbooks.get.return_value = ([wb_finance, wb_sales], None)

        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        ingestor.connector._server = mock_server

        data = ingestor.ingest_workbooks(project_name="Finance")
        assert len(data.workbooks) == 1
        assert data.workbooks[0]["id"] == "wb-001"


# ---------------------------------------------------------------------------
# TableauIngestor.ingest_datasources
# ---------------------------------------------------------------------------


class TestTableauIngestorDatasources:
    """Unit tests for TableauIngestor.ingest_datasources."""

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_ingest_datasources_returns_tableau_data(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        mock_ds = _make_mock_datasource()
        mock_server = MagicMock()
        mock_server.datasources.get.return_value = ([mock_ds], None)

        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        ingestor.connector._server = mock_server

        data = ingestor.ingest_datasources()

        assert isinstance(data, TableauData)
        assert len(data.datasources) == 1
        assert data.datasources[0]["id"] == "ds-001"
        assert data.datasources[0]["name"] == "Orders DS"


# ---------------------------------------------------------------------------
# TableauIngestor.export_as_documents
# ---------------------------------------------------------------------------


class TestTableauIngestorExportDocuments:
    """Unit tests for TableauIngestor.export_as_documents."""

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_export_workbooks_document_shape(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        data = TableauData(
            workbooks=[
                {
                    "id": "wb-001",
                    "name": "Sales Dashboard",
                    "project_name": "Finance",
                }
            ],
            server_url="https://tableau.example.com",
            site_name="mysite",
            row_count=1,
        )

        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        docs = ingestor.export_as_documents(data)

        assert len(docs) == 1
        doc = docs[0]
        assert doc["id"] == "wb-001"
        assert "Sales Dashboard" in doc["text"]
        assert doc["metadata"]["source"] == "tableau"
        assert doc["metadata"]["type"] == "workbook"
        assert doc["metadata"]["server_url"] == "https://tableau.example.com"
        assert doc["metadata"]["site_name"] == "mysite"
        assert "row_data" in doc["metadata"]

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_export_datasources_document_shape(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        data = TableauData(
            datasources=[{"id": "ds-001", "name": "Orders DS", "project_name": "Finance"}],
            server_url="https://tableau.example.com",
            site_name="",
            row_count=1,
        )
        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        docs = ingestor.export_as_documents(data)

        assert len(docs) == 1
        assert docs[0]["metadata"]["type"] == "datasource"
        assert docs[0]["id"] == "ds-001"

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_export_fields_document_shape(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        data = TableauData(
            fields=[
                {
                    "name": "order_id",
                    "type": "integer",
                    "description": "Unique order identifier",
                    "connection_id": "conn-1",
                }
            ],
            server_url="https://tableau.example.com",
            site_name="",
            row_count=1,
        )
        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        docs = ingestor.export_as_documents(data)

        assert len(docs) == 1
        assert docs[0]["metadata"]["type"] == "field"
        assert "order_id" in docs[0]["text"]

    @patch("semantica.ingest.tableau_ingestor.TABLEAU_AVAILABLE", True)
    def test_export_empty_data_returns_empty_list(self):
        from semantica.ingest.tableau_ingestor import TableauData, TableauIngestor

        data = TableauData(server_url="https://tableau.example.com", row_count=0)
        ingestor = TableauIngestor(
            server_url="https://tableau.example.com",
            token_name="t",
            token_value="v",
        )
        docs = ingestor.export_as_documents(data)
        assert docs == []

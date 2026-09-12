"""Unit tests for the Power BI ingestor.

The HTTP layer is mocked by patching ``request_with_ssrf_guard`` in the
ingestor module.  Tests assert on the *call signature* (method first, url
second) so a mistake in argument order fails here instead of at runtime.
"""

import unittest
from unittest.mock import patch

from semantica.ingest import powerbi_ingestor as pbi
from semantica.ingest.powerbi_ingestor import (
    PowerBIConnector,
    PowerBIData,
    PowerBIIngestor,
)

GUARD = "semantica.ingest.powerbi_ingestor.request_with_ssrf_guard"

CREDS = {
    "tenant_id": "tenant-1",
    "client_id": "client-1",
    "client_secret": "secret-1",
}


class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def token_response():
    return FakeResponse({"access_token": "tok-123", "expires_in": 3600})


class TestLazyExports(unittest.TestCase):
    def test_classes_are_module_level_attributes(self):
        self.assertTrue(hasattr(pbi, "PowerBIData"))
        self.assertTrue(hasattr(pbi, "PowerBIConnector"))
        self.assertTrue(hasattr(pbi, "PowerBIIngestor"))

    def test_module_all_lists_three_classes(self):
        self.assertEqual(
            set(pbi.__all__),
            {"PowerBIData", "PowerBIConnector", "PowerBIIngestor"},
        )

    def test_lazy_export_resolves_via_package(self):
        import semantica.ingest as ingest_pkg

        self.assertIs(ingest_pkg.PowerBIIngestor, PowerBIIngestor)
        self.assertIs(ingest_pkg.PowerBIData, PowerBIData)


class TestCredentialValidation(unittest.TestCase):
    def test_missing_tenant_raises(self):
        with self.assertRaises(Exception):
            PowerBIConnector(client_id="c", client_secret="s")

    def test_missing_client_id_raises(self):
        with self.assertRaises(Exception):
            PowerBIConnector(tenant_id="t", client_secret="s")

    def test_missing_client_secret_raises(self):
        with self.assertRaises(Exception):
            PowerBIConnector(tenant_id="t", client_id="c")

    def test_full_credentials_construct(self):
        connector = PowerBIConnector(**CREDS)
        self.assertEqual(connector.tenant_id, "tenant-1")
        connector.close()

    def test_secret_not_exposed_as_public_attribute(self):
        connector = PowerBIConnector(**CREDS)
        self.assertNotIn("secret-1", str(vars(connector).get("client_id", "")))
        self.assertIsNone(vars(connector).get("client_secret"))
        connector.close()


class TestTokenAcquisition(unittest.TestCase):
    def test_token_request_uses_post_and_token_url(self):
        connector = PowerBIConnector(**CREDS)
        with patch(GUARD, return_value=token_response()) as guard:
            token = connector._request_token()
        self.assertEqual(token, "tok-123")
        args, kwargs = guard.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("oauth2/v2.0/token", args[1])
        self.assertEqual(kwargs["data"]["grant_type"], "client_credentials")
        self.assertEqual(kwargs["data"]["client_id"], "client-1")
        self.assertEqual(kwargs["data"]["client_secret"], "secret-1")
        connector.close()

    def test_token_is_cached(self):
        connector = PowerBIConnector(**CREDS)
        with patch(GUARD, return_value=token_response()) as guard:
            connector._ensure_token()
            connector._ensure_token()
        self.assertEqual(guard.call_count, 1)
        connector.close()

    def test_token_endpoint_error_raises(self):
        connector = PowerBIConnector(**CREDS)
        with patch(GUARD, return_value=FakeResponse({"error": "nope"}, 401)):
            with self.assertRaises(Exception):
                connector._request_token()
        connector.close()

    def test_token_missing_field_raises(self):
        connector = PowerBIConnector(**CREDS)
        with patch(GUARD, return_value=FakeResponse({"expires_in": 3600})):
            with self.assertRaises(Exception):
                connector._request_token()
        connector.close()


class TestApiCalls(unittest.TestCase):
    def setUp(self):
        self.connector = PowerBIConnector(**CREDS)

    def tearDown(self):
        self.connector.close()

    def test_get_uses_get_method_and_full_url(self):
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse({"value": []})]
            self.connector.get("groups")
        args, kwargs = guard.call_args
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], "https://api.powerbi.com/v1.0/myorg/groups")
        self.assertIn("Authorization", kwargs["headers"])
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Bearer "))

    def test_collection_response_is_unwrapped(self):
        payload = {"value": [{"id": "ws-1", "name": "Sales"}]}
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse(payload)]
            result = self.connector.get_workspaces()
        self.assertEqual(result, [{"id": "ws-1", "name": "Sales"}])

    def test_object_response_returned_as_dict(self):
        with patch(GUARD) as guard:
            guard.side_effect = [
                token_response(),
                FakeResponse({"id": "ws-9", "name": "Only"}),
            ]
            result = self.connector.get("groups/ws-9")
        self.assertEqual(result, {"id": "ws-9", "name": "Only"})

    def test_pagination_follows_next_link(self):
        first = {
            "value": [{"id": "a"}],
            "@odata.nextLink": "https://api.powerbi.com/v1.0/myorg/datasets?skip=1",
        }
        second = {"value": [{"id": "b"}]}
        with patch(GUARD) as guard:
            guard.side_effect = [
                token_response(),
                FakeResponse(first),
                FakeResponse(second),
            ]
            result = self.connector.get("datasets")
        self.assertEqual([item["id"] for item in result], ["a", "b"])
        self.assertEqual(guard.call_count, 3)

    def test_pagination_rejects_cross_origin_next_link(self):
        first = {
            "value": [{"id": "a"}],
            "@odata.nextLink": "https://evil.example.com/next",
        }
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse(first)]
            with self.assertRaises(Exception):
                self.connector.get("datasets")
        self.assertEqual(guard.call_count, 2)  # token + first page only

    def test_workspace_scoped_paths(self):
        with patch(GUARD) as guard:
            guard.side_effect = [
                token_response(),
                FakeResponse({"value": []}),
            ]
            self.connector.get_datasets("ws-42")
        args, _ = guard.call_args
        self.assertEqual(
            args[1], "https://api.powerbi.com/v1.0/myorg/groups/ws-42/datasets"
        )

    def test_unscoped_paths(self):
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse({"value": []})]
            self.connector.get_reports()
        args, _ = guard.call_args
        self.assertEqual(args[1], "https://api.powerbi.com/v1.0/myorg/reports")

    def test_http_error_raises(self):
        with patch(GUARD) as guard:
            guard.side_effect = [
                token_response(),
                FakeResponse({"error": "boom"}, 403),
            ]
            with self.assertRaises(Exception):
                self.connector.get_workspaces()

    def test_test_connection_true(self):
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse({"value": []})]
            self.assertTrue(self.connector.test_connection())

    def test_test_connection_false_on_error(self):
        with patch(GUARD) as guard:
            guard.side_effect = [token_response(), FakeResponse({}, 500)]
            self.assertFalse(self.connector.test_connection())


class TestIngestor(unittest.TestCase):
    def setUp(self):
        self.patcher = patch(GUARD)
        self.guard = self.patcher.start()
        self.guard.side_effect = [
            token_response(),
            FakeResponse({"value": [{"id": "ws-1", "name": "Sales"}]}),
            FakeResponse({"value": [{"id": "ds-1", "name": "Orders"}]}),
            FakeResponse({"value": [{"id": "rp-1", "name": "Q3"}]}),
            FakeResponse({"value": []}),
        ]
        self.ingestor = PowerBIIngestor(**CREDS)

    def tearDown(self):
        self.ingestor.close()
        self.patcher.stop()

    def test_ingest_returns_powerbi_data(self):
        data = self.ingestor.ingest_workspace_metadata()
        self.assertIsInstance(data, PowerBIData)
        self.assertEqual(len(data.workspaces), 1)
        self.assertEqual(len(data.datasets), 1)
        self.assertEqual(len(data.reports), 1)
        self.assertEqual(len(data.dataflows), 0)

    def test_metadata_counts(self):
        data = self.ingestor.ingest_workspace_metadata()
        self.assertEqual(data.metadata["dataset_count"], 1)
        self.assertEqual(data.metadata["report_count"], 1)
        self.assertEqual(data.metadata["dataflow_count"], 0)

    def test_include_subset_skips_unwanted_calls(self):
        self.guard.side_effect = [
            token_response(),
            FakeResponse({"value": [{"id": "ws-1", "name": "Sales"}]}),
            FakeResponse({"value": [{"id": "ds-1", "name": "Orders"}]}),
        ]
        data = self.ingestor.ingest_workspace_metadata(include=["datasets"])
        self.assertEqual(len(data.datasets), 1)
        self.assertEqual(data.workspaces, [])
        self.assertEqual(data.reports, [])
        self.assertEqual(data.dataflows, [])

    def test_empty_include_pulls_nothing(self):
        self.guard.side_effect = [token_response()]
        data = self.ingestor.ingest_workspace_metadata(include=[])
        self.assertEqual(data.workspaces, [])
        self.assertEqual(data.datasets, [])
        self.assertEqual(data.reports, [])
        self.assertEqual(data.dataflows, [])
        self.assertEqual(self.guard.call_count, 0)  # not even a token fetch

    def test_unscoped_ingest_walks_each_workspace(self):
        self.guard.side_effect = [
            token_response(),
            FakeResponse({"value": [{"id": "ws-1"}, {"id": "ws-2"}]}),
            FakeResponse({"value": [{"id": "ds-1"}]}),
            FakeResponse({"value": [{"id": "rp-1"}]}),
            FakeResponse({"value": [{"id": "df-1"}]}),
            FakeResponse({"value": [{"id": "ds-2"}]}),
            FakeResponse({"value": [{"id": "rp-2"}]}),
            FakeResponse({"value": [{"id": "df-2"}]}),
        ]
        data = self.ingestor.ingest_workspace_metadata()
        self.assertEqual([d["id"] for d in data.datasets], ["ds-1", "ds-2"])
        self.assertEqual(data.datasets[0]["workspace_id"], "ws-1")
        self.assertEqual(data.dataflows[1]["workspace_id"], "ws-2")
        urls = [call.args[1] for call in self.guard.call_args_list[1:]]
        self.assertIn("https://api.powerbi.com/v1.0/myorg/groups/ws-1/dataflows", urls)
        self.assertIn("https://api.powerbi.com/v1.0/myorg/groups/ws-2/dataflows", urls)

    def test_scoped_ingest_uses_group_paths(self):
        self.guard.side_effect = [
            token_response(),
            FakeResponse({"id": "ws-9", "name": "Only"}),
            FakeResponse({"value": [{"id": "ds-9"}]}),
            FakeResponse({"value": []}),
            FakeResponse({"value": []}),
        ]
        data = self.ingestor.ingest_workspace_metadata(workspace_id="ws-9")
        self.assertEqual(len(data.workspaces), 1)
        self.assertEqual([d["id"] for d in data.datasets], ["ds-9"])
        urls = [call.args[1] for call in self.guard.call_args_list[1:]]
        self.assertIn("https://api.powerbi.com/v1.0/myorg/groups/ws-9/datasets", urls)
        self.assertIn("https://api.powerbi.com/v1.0/myorg/groups/ws-9/dataflows", urls)

    def test_unknown_include_raises(self):
        with self.assertRaises(Exception):
            self.ingestor.ingest_workspace_metadata(include=["nope"])

    def test_export_documents_shape(self):
        data = self.ingestor.ingest_workspace_metadata()
        documents = self.ingestor.export_as_documents(data)
        self.assertEqual(len(documents), 3)
        for doc in documents:
            self.assertIn("id", doc)
            self.assertIn("text", doc)
            self.assertIn("metadata", doc)
            self.assertEqual(doc["metadata"]["source"], "powerbi")

    def test_export_documents_resource_types(self):
        data = self.ingestor.ingest_workspace_metadata()
        documents = self.ingestor.export_as_documents(data)
        types = {doc["metadata"]["resource_type"] for doc in documents}
        self.assertEqual(types, {"workspace", "dataset", "report"})

    def test_export_document_text_mentions_name(self):
        data = self.ingestor.ingest_workspace_metadata()
        documents = self.ingestor.export_as_documents(data)
        dataset_doc = [
            d for d in documents if d["metadata"]["resource_type"] == "dataset"
        ][0]
        self.assertIn("Orders", dataset_doc["text"])

    def test_missing_id_falls_back_to_index(self):
        data = PowerBIData(
            workspaces=[],
            datasets=[{"name": "Nameless"}],
            reports=[],
            dataflows=[],
        )
        documents = self.ingestor.export_as_documents(data)
        self.assertEqual(documents[0]["id"], "dataset-0")

    def test_context_manager_closes(self):
        with PowerBIIngestor(**CREDS) as ingestor:
            self.assertIsNotNone(ingestor.connector)
        self.assertIsNone(ingestor.connector._session)


if __name__ == "__main__":
    unittest.main()

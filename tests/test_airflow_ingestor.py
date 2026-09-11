from unittest.mock import MagicMock, patch

import pytest
import requests

from semantica.ingest.airflow_ingestor import (
    AirflowConnector,
    AirflowData,
    AirflowIngestor,
)
from semantica.utils.exceptions import ProcessingError, ValidationError


def make_response(
    payload=None,
    *,
    status_code=200,
    json_error=None,
):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code

    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = payload

    response.raise_for_status.return_value = None
    return response


class TestAirflowConnector:
    def test_requires_base_url(self):
        with pytest.raises(ValidationError, match="base_url is required"):
            AirflowConnector("")

    def test_basic_auth_configuration(self):
        connector = AirflowConnector(
            "https://airflow.example.com",
            username="user",
            password="secret",
        )

        assert connector.session.auth == ("user", "secret")
        assert connector.base_url == "https://airflow.example.com/"

        connector.close()

    def test_username_requires_password(self):
        with pytest.raises(
            ValidationError,
            match="username and password must be provided together",
        ):
            AirflowConnector(
                "https://airflow.example.com",
                username="user",
            )

    def test_bearer_token_configuration(self):
        connector = AirflowConnector(
            "https://airflow.example.com",
            token="token-value",
        )

        assert (
            connector.session.headers["Authorization"] == "Bearer token-value"
        )

        connector.close()

    def test_api_url_uses_stable_v1_namespace(self):
        connector = AirflowConnector(
            "https://airflow.example.com",
        )

        assert (
            connector.api_url("dags")
            == "https://airflow.example.com/api/v1/dags"
        )

        connector.close()

    @patch("semantica.ingest.airflow_ingestor.request_with_ssrf_guard")
    def test_request_uses_ssrf_guard(self, mock_guard):
        response = make_response({"dags": []})
        mock_guard.return_value = response

        connector = AirflowConnector(
            "https://airflow.example.com",
            token="abc",
            timeout=15,
        )

        result = connector.request(
            "GET",
            "dags",
            params={"limit": 10},
        )

        assert result is response

        mock_guard.assert_called_once_with(
            "GET",
            "https://airflow.example.com/api/v1/dags",
            session=connector.session,
            allow_private_ips=False,
            params={"limit": 10},
            timeout=15,
        )

        connector.close()

    @patch("semantica.ingest.airflow_ingestor.request_with_ssrf_guard")
    def test_request_converts_http_error(self, mock_guard):
        response = make_response()
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )
        mock_guard.return_value = response

        connector = AirflowConnector(
            "https://airflow.example.com",
        )

        with pytest.raises(
            ProcessingError,
            match="Airflow API request failed",
        ):
            connector.request("GET", "dags")

        connector.close()

    @patch("semantica.ingest.airflow_ingestor.request_with_ssrf_guard")
    def test_get_json_rejects_invalid_json(self, mock_guard):
        mock_guard.return_value = make_response(
            json_error=ValueError("bad json"),
        )

        connector = AirflowConnector(
            "https://airflow.example.com",
        )

        with pytest.raises(
            ProcessingError,
            match="did not return valid JSON",
        ):
            connector.get_json("dags")

        connector.close()

    @patch("semantica.ingest.airflow_ingestor.request_with_ssrf_guard")
    def test_get_json_requires_object_response(self, mock_guard):
        mock_guard.return_value = make_response(["not", "an", "object"])

        connector = AirflowConnector(
            "https://airflow.example.com",
        )

        with pytest.raises(
            ProcessingError,
            match="expected an object",
        ):
            connector.get_json("dags")

        connector.close()


class TestAirflowIngestor:
    def test_requires_connector_or_base_url(self):
        with pytest.raises(
            ValidationError,
            match="Provide either an AirflowConnector or base_url",
        ):
            AirflowIngestor()

    def test_list_dags_paginates(self):
        connector = MagicMock(spec=AirflowConnector)

        connector.get_json.side_effect = [
            {
                "dags": [
                    {"dag_id": "dag_one"},
                    {"dag_id": "dag_two"},
                ],
                "total_entries": 3,
            },
            {
                "dags": [
                    {"dag_id": "dag_three"},
                ],
                "total_entries": 3,
            },
        ]

        ingestor = AirflowIngestor(connector=connector)

        dags = ingestor.list_dags(limit=2)

        assert [dag["dag_id"] for dag in dags] == [
            "dag_one",
            "dag_two",
            "dag_three",
        ]

        assert connector.get_json.call_count == 2

        connector.get_json.assert_any_call(
            "dags",
            params={
                "limit": 2,
                "offset": 0,
            },
        )
        connector.get_json.assert_any_call(
            "dags",
            params={
                "limit": 2,
                "offset": 2,
            },
        )

    def test_list_dags_rejects_invalid_limit(self):
        connector = MagicMock(spec=AirflowConnector)
        ingestor = AirflowIngestor(connector=connector)

        with pytest.raises(
            ValidationError,
            match="page limit must be greater than zero",
        ):
            ingestor.list_dags(limit=0)

    def test_list_dags_rejects_non_list_payload(self):
        connector = MagicMock(spec=AirflowConnector)
        connector.get_json.return_value = {
            "dags": "not-a-list",
        }

        ingestor = AirflowIngestor(connector=connector)

        with pytest.raises(
            ProcessingError,
            match="field 'dags' is not a list",
        ):
            ingestor.list_dags()

    def test_list_tasks_encodes_dag_id(self):
        connector = MagicMock(spec=AirflowConnector)
        connector.get_json.return_value = {
            "tasks": [
                {
                    "task_id": "extract",
                    "downstream_task_ids": ["load"],
                }
            ]
        }

        ingestor = AirflowIngestor(connector=connector)

        tasks = ingestor.list_tasks("sales/daily")

        connector.get_json.assert_called_once_with("dags/sales%2Fdaily/tasks")

        assert tasks == [
            {
                "task_id": "extract",
                "downstream_task_ids": ["load"],
                "dag_id": "sales/daily",
            }
        ]

    def test_list_tasks_requires_dag_id(self):
        connector = MagicMock(spec=AirflowConnector)
        ingestor = AirflowIngestor(connector=connector)

        with pytest.raises(
            ValidationError,
            match="dag_id is required",
        ):
            ingestor.list_tasks("")

    def test_list_tasks_rejects_non_list_payload(self):
        connector = MagicMock(spec=AirflowConnector)
        connector.get_json.return_value = {
            "tasks": "not-a-list",
        }

        ingestor = AirflowIngestor(connector=connector)

        with pytest.raises(
            ProcessingError,
            match="non-list 'tasks' field",
        ):
            ingestor.list_tasks("example")

    def test_dependencies_are_derived_from_tasks(self):
        tasks = [
            {
                "dag_id": "pipeline",
                "task_id": "extract",
                "downstream_task_ids": ["transform"],
            },
            {
                "dag_id": "pipeline",
                "task_id": "transform",
                "downstream_task_ids": ["load"],
            },
        ]

        dependencies = AirflowIngestor._dependencies_from_tasks(tasks)

        assert dependencies == [
            {
                "dag_id": "pipeline",
                "upstream_task_id": "extract",
                "downstream_task_id": "transform",
            },
            {
                "dag_id": "pipeline",
                "upstream_task_id": "transform",
                "downstream_task_id": "load",
            },
        ]

    def test_dependencies_remove_duplicates(self):
        tasks = [
            {
                "dag_id": "pipeline",
                "task_id": "extract",
                "downstream_task_ids": [
                    "load",
                    "load",
                ],
            }
        ]

        dependencies = AirflowIngestor._dependencies_from_tasks(tasks)

        assert dependencies == [
            {
                "dag_id": "pipeline",
                "upstream_task_id": "extract",
                "downstream_task_id": "load",
            }
        ]

    def test_ingest_filters_dags_and_paused_dags(self):
        connector = MagicMock(spec=AirflowConnector)
        connector.base_url = "https://airflow.example.com/"

        ingestor = AirflowIngestor(connector=connector)

        ingestor.list_dags = MagicMock(
            return_value=[
                {
                    "dag_id": "active",
                    "is_paused": False,
                },
                {
                    "dag_id": "paused",
                    "is_paused": True,
                },
                {
                    "dag_id": "other",
                    "is_paused": False,
                },
            ]
        )

        ingestor.list_tasks = MagicMock(
            return_value=[
                {
                    "task_id": "task_a",
                    "downstream_task_ids": [],
                    "dag_id": "active",
                }
            ]
        )

        result = ingestor.ingest(
            dag_ids=["active", "paused"],
            include_paused=False,
        )

        assert [dag["dag_id"] for dag in result.dags] == ["active"]
        ingestor.list_tasks.assert_called_once_with("active")

    def test_ingest_builds_lineage(self):
        connector = MagicMock(spec=AirflowConnector)
        connector.base_url = "https://airflow.example.com/"

        ingestor = AirflowIngestor(connector=connector)

        ingestor.list_dags = MagicMock(
            return_value=[
                {
                    "dag_id": "pipeline",
                    "is_paused": False,
                }
            ]
        )

        ingestor.list_tasks = MagicMock(
            return_value=[
                {
                    "dag_id": "pipeline",
                    "task_id": "extract",
                    "downstream_task_ids": ["load"],
                },
                {
                    "dag_id": "pipeline",
                    "task_id": "load",
                    "downstream_task_ids": [],
                },
            ]
        )

        result = ingestor.ingest()

        assert result.dependencies == [
            {
                "dag_id": "pipeline",
                "upstream_task_id": "extract",
                "downstream_task_id": "load",
            }
        ]

        assert result.source == "https://airflow.example.com/"

    def test_export_as_documents_delegates_to_data(self):
        connector = MagicMock(spec=AirflowConnector)
        ingestor = AirflowIngestor(connector=connector)

        data = MagicMock(spec=AirflowData)
        data.to_documents.return_value = [{"id": "document"}]

        documents = ingestor.export_as_documents(data)

        assert documents == [{"id": "document"}]
        data.to_documents.assert_called_once_with()

    def test_close_closes_connector(self):
        connector = MagicMock(spec=AirflowConnector)
        ingestor = AirflowIngestor(connector=connector)

        ingestor.close()

        connector.close.assert_called_once_with()


class TestAirflowData:
    def test_to_documents_exports_dags_tasks_and_dependencies(self):
        data = AirflowData(
            dags=[
                {
                    "dag_id": "pipeline",
                    "description": "Example pipeline",
                }
            ],
            tasks=[
                {
                    "dag_id": "pipeline",
                    "task_id": "extract",
                }
            ],
            dependencies=[
                {
                    "dag_id": "pipeline",
                    "upstream_task_id": "extract",
                    "downstream_task_id": "load",
                }
            ],
            source="https://airflow.example.com/",
        )

        documents = data.to_documents()

        assert len(documents) == 3

        assert documents[0]["id"] == "airflow:dag:pipeline"
        assert documents[0]["type"] == "airflow_dag"

        assert documents[1]["id"] == "airflow:task:pipeline:extract"
        assert documents[1]["type"] == "airflow_task"

        assert documents[2]["id"] == "airflow:dependency:pipeline:extract:load"
        assert documents[2]["type"] == "airflow_dependency"

        assert all(
            document["source"] == "https://airflow.example.com/"
            for document in documents
        )

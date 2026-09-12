"""Apache Airflow metadata ingestor.

Provides read-only ingestion of DAG, task, and task-dependency metadata from
the stable Apache Airflow REST API.

The connector follows Semantica's ingestion pattern:

- ``AirflowData`` stores fetched DAG/task/lineage metadata.
- ``AirflowConnector`` manages authentication and HTTP transport.
- ``AirflowIngestor`` fetches metadata and exports
  GraphBuilder-ready documents.

All outbound requests to the user-supplied Airflow endpoint go through
``request_with_ssrf_guard``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urljoin

import requests

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from .ssrf import request_with_ssrf_guard

__all__ = [
    "AirflowData",
    "AirflowConnector",
    "AirflowIngestor",
]


_logger = get_logger("airflow_ingestor")


@dataclass
class AirflowData:
    """Container for Airflow DAG, task, and dependency metadata."""

    dags: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    dependencies: List[Dict[str, str]]
    source: str
    ingested_at: datetime = field(default_factory=datetime.now)

    def to_documents(self) -> List[Dict[str, Any]]:
        """Convert Airflow metadata into GraphBuilder-friendly document dicts."""

        documents: List[Dict[str, Any]] = []

        for dag in self.dags:
            dag_id = str(dag.get("dag_id") or "")
            if not dag_id:
                continue

            doc = dict(dag)
            doc.setdefault("id", f"airflow:dag:{dag_id}")
            doc.setdefault("name", dag_id)
            doc.setdefault("type", "airflow_dag")
            doc.setdefault("source", self.source)
            documents.append(doc)

        for task in self.tasks:
            dag_id = str(task.get("dag_id") or "")
            task_id = str(task.get("task_id") or "")

            if not dag_id or not task_id:
                continue

            doc = dict(task)
            doc.setdefault("id", f"airflow:task:{dag_id}:{task_id}")
            doc.setdefault("name", task_id)
            doc.setdefault("type", "airflow_task")
            doc.setdefault("source", self.source)
            documents.append(doc)

        for dependency in self.dependencies:
            dag_id = str(dependency.get("dag_id") or "")
            upstream = str(dependency.get("upstream_task_id") or "")
            downstream = str(dependency.get("downstream_task_id") or "")

            if not dag_id or not upstream or not downstream:
                continue

            upstream_id = f"airflow:task:{dag_id}:{upstream}"
            downstream_id = f"airflow:task:{dag_id}:{downstream}"

            documents.append(
                {
                    "id": (f"airflow:dependency:{dag_id}:" f"{upstream}:{downstream}"),
                    "name": f"{upstream} -> {downstream}",
                    "type": "airflow_dependency",
                    "source": upstream_id,
                    "target": downstream_id,
                    "dag_id": dag_id,
                    "upstream_task_id": upstream,
                    "downstream_task_id": downstream,
                    "metadata": {
                        "airflow_source": self.source,
                    },
                }
            )

        return documents


class AirflowConnector:
    """Connection and authentication management for the Airflow REST API."""

    def __init__(
        self,
        base_url: str,
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        allow_private_ips: bool = False,
        timeout: int = 30,
    ) -> None:
        """Initialize an Airflow REST API connection."""

        if not base_url:
            raise ValidationError("Airflow base_url is required.")

        self.base_url = base_url.rstrip("/") + "/"
        self.allow_private_ips = allow_private_ips
        self.timeout = timeout
        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
            }
        )

        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username is not None or password is not None:
            if not username or password is None:
                raise ValidationError(
                    "Airflow username and password must be provided together."
                )
            self.session.auth = (username, password)

    def get_session(self) -> requests.Session:
        """Return the configured requests session."""

        return self.session

    def api_url(self, path: str) -> str:
        """Build a URL below the stable Airflow ``/api/v1/`` namespace."""

        return urljoin(
            self.base_url,
            f"api/v1/{path.lstrip('/')}",
        )

    def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform an SSRF-guarded request against the Airflow API."""

        url = self.api_url(path)
        kwargs.setdefault("timeout", self.timeout)

        try:
            response = request_with_ssrf_guard(
                method,
                url,
                session=self.session,
                allow_private_ips=self.allow_private_ips,
                allow_private_ips_on_redirect=False,
                **kwargs,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ProcessingError(
                f"Airflow API request failed for '{url}': {exc}"
            ) from exc

        return response

    def get_json(
        self,
        path: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Perform a GET request and return the JSON object response."""

        response = self.request("GET", path, **kwargs)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProcessingError(
                f"Airflow API endpoint '{path}' did not return valid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise ProcessingError(
                f"Airflow API endpoint '{path}' returned "
                f"{type(payload).__name__}, expected an object."
            )

        return payload

    def close(self) -> None:
        """Close the underlying requests session."""

        self.session.close()


class AirflowIngestor:
    """Read DAG, task, and task-dependency metadata from Apache Airflow."""

    def __init__(
        self,
        connector: Optional[AirflowConnector] = None,
        *,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        allow_private_ips: bool = False,
        timeout: int = 30,
    ) -> None:
        """Initialize the Airflow metadata ingestor."""

        if connector is not None:
            self.connector = connector
        else:
            if not base_url:
                raise ValidationError("Provide either an AirflowConnector or base_url.")

            self.connector = AirflowConnector(
                base_url,
                username=username,
                password=password,
                token=token,
                allow_private_ips=allow_private_ips,
                timeout=timeout,
            )

        self.logger = _logger

    def list_dags(
        self,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch all DAG metadata using Airflow REST API pagination."""

        if limit <= 0:
            raise ValidationError("Airflow DAG page limit must be greater than zero.")

        dags: List[Dict[str, Any]] = []
        offset = 0

        while True:
            payload = self.connector.get_json(
                "dags",
                params={
                    "limit": limit,
                    "offset": offset,
                },
            )

            page = payload.get("dags", [])

            if not isinstance(page, list):
                raise ProcessingError(
                    "Airflow DAG response field 'dags' is not a list."
                )

            for dag in page:
                if isinstance(dag, dict):
                    dags.append(dict(dag))

            total_entries = payload.get("total_entries")

            if not page:
                break

            offset += len(page)

            if isinstance(total_entries, int):
                if offset >= total_entries:
                    break
            elif len(page) < limit:
                break

        return dags

    def list_tasks(
        self,
        dag_id: str,
    ) -> List[Dict[str, Any]]:
        """Fetch task metadata for one Airflow DAG."""

        if not dag_id:
            raise ValidationError("Airflow dag_id is required.")

        encoded_dag_id = quote(dag_id, safe="")

        payload = self.connector.get_json(f"dags/{encoded_dag_id}/tasks")

        raw_tasks = payload.get("tasks", [])

        if not isinstance(raw_tasks, list):
            raise ProcessingError(
                f"Airflow task response for DAG '{dag_id}' "
                "contains a non-list 'tasks' field."
            )

        tasks: List[Dict[str, Any]] = []

        for raw_task in raw_tasks:
            if not isinstance(raw_task, dict):
                continue

            task = dict(raw_task)
            task["dag_id"] = dag_id
            tasks.append(task)

        return tasks

    @staticmethod
    def _dependencies_from_tasks(
        tasks: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """Derive task lineage edges from ``downstream_task_ids``."""

        dependencies: List[Dict[str, str]] = []
        seen = set()

        for task in tasks:
            dag_id = str(task.get("dag_id") or "")
            task_id = str(task.get("task_id") or "")

            downstream_task_ids = task.get("downstream_task_ids") or []

            if not dag_id or not task_id or not isinstance(downstream_task_ids, list):
                continue

            for downstream_task_id in downstream_task_ids:
                downstream = str(downstream_task_id or "")

                if not downstream:
                    continue

                key = (dag_id, task_id, downstream)

                if key in seen:
                    continue

                seen.add(key)

                dependencies.append(
                    {
                        "dag_id": dag_id,
                        "upstream_task_id": task_id,
                        "downstream_task_id": downstream,
                    }
                )

        return dependencies

    def ingest(
        self,
        *,
        dag_ids: Optional[List[str]] = None,
        include_paused: bool = True,
        page_limit: int = 100,
    ) -> AirflowData:
        """Fetch DAGs, tasks, and dependency metadata from Airflow."""

        dags = self.list_dags(limit=page_limit)

        if dag_ids is not None:
            requested = set(dag_ids)
            dags = [dag for dag in dags if str(dag.get("dag_id") or "") in requested]

        if not include_paused:
            dags = [dag for dag in dags if not bool(dag.get("is_paused"))]

        tasks: List[Dict[str, Any]] = []

        for dag in dags:
            dag_id = str(dag.get("dag_id") or "")

            if not dag_id:
                continue

            try:
                tasks.extend(self.list_tasks(dag_id))
            except ProcessingError as exc:
                self.logger.error(
                    "Failed to fetch Airflow tasks for DAG %s: %s",
                    dag_id,
                    exc,
                )
                raise

        dependencies = self._dependencies_from_tasks(tasks)

        return AirflowData(
            dags=dags,
            tasks=tasks,
            dependencies=dependencies,
            source=self.connector.base_url,
        )

    def export_as_documents(
        self,
        data: AirflowData,
    ) -> List[Dict[str, Any]]:
        """Convert ingested Airflow metadata into document dictionaries."""

        return data.to_documents()

    def close(self) -> None:
        """Close the underlying Airflow connector."""

        self.connector.close()

---
title: 'Apache Airflow Integration'
description: 'Ingest DAG, task, and dependency metadata from Apache Airflow into Semantica.'
icon: 'wind'
---

> Ingest Apache Airflow DAGs, tasks, and task dependencies through the stable Airflow REST API for pipeline and lineage analysis in Semantica.

## Installation

```bash
pip install "semantica[ingest-airflow]"
```

## Basic Usage

```python
from semantica.ingest import AirflowIngestor

ingestor = AirflowIngestor(
    base_url="https://airflow.example.com",
    token="your-access-token",
)

data = ingestor.ingest()
documents = ingestor.export_as_documents(data)

print(f"DAGs: {len(data.dags)}")
print(f"Tasks: {len(data.tasks)}")
print(f"Dependencies: {len(data.dependencies)}")

ingestor.close()
```

`base_url` must point to the Airflow webserver root.

Do not include `/api/v1` in `base_url`; the connector adds the stable REST API path automatically.

## Authentication

### Bearer Token

```python
from semantica.ingest import AirflowIngestor

ingestor = AirflowIngestor(
    base_url="https://airflow.example.com",
    token="your-access-token",
)
```

### Username and Password

```python
from semantica.ingest import AirflowIngestor

ingestor = AirflowIngestor(
    base_url="https://airflow.example.com",
    username="airflow-user",
    password="your-password",
)
```

Username and password must be supplied together.

## Filtering DAGs

Restrict ingestion to selected DAG IDs:

```python
data = ingestor.ingest(
    dag_ids=["daily_etl", "warehouse_sync"],
)
```

Exclude paused DAGs:

```python
data = ingestor.ingest(
    include_paused=False,
)
```

You can combine both options:

```python
data = ingestor.ingest(
    dag_ids=["daily_etl", "warehouse_sync"],
    include_paused=False,
)
```

## Pipeline Lineage

The connector derives task-level dependencies from each Airflow task's `downstream_task_ids`.

For example:

```python
[
    {
        "dag_id": "daily_etl",
        "upstream_task_id": "extract",
        "downstream_task_id": "transform",
    },
    {
        "dag_id": "daily_etl",
        "upstream_task_id": "transform",
        "downstream_task_id": "load",
    },
]
```

Duplicate dependency edges are removed automatically.

## Exported Documents

`export_as_documents()` converts ingested Airflow metadata into GraphBuilder-friendly dictionaries.

The connector exports three document types:

- `airflow_dag`
- `airflow_task`
- `airflow_dependency`

Generated identifiers use these forms:

```text
airflow:dag:<dag_id>
airflow:task:<dag_id>:<task_id>
airflow:dependency:<dag_id>:<upstream_task_id>:<downstream_task_id>
```

## Private Airflow Deployments

All requests to the user-provided Airflow endpoint pass through Semantica's SSRF protection.

Private IP addresses are blocked by default.

For a trusted Airflow deployment on a private network:

```python
from semantica.ingest import AirflowIngestor

ingestor = AirflowIngestor(
    base_url="http://10.0.0.20:8080",
    username="airflow-user",
    password="your-password",
    allow_private_ips=True,
)
```

Only enable `allow_private_ips=True` for endpoints you trust.

## Pagination

DAG results are retrieved using Airflow's `limit` and `offset` pagination.

The default page size is 100.

```python
data = ingestor.ingest(
    page_limit=100,
)
```

A different positive page size can be supplied when required.

## Error Handling

The connector raises Semantica errors for common failures, including:

- missing or invalid connection configuration
- unsuccessful Airflow API requests
- invalid JSON responses
- unexpected API response structures
- invalid pagination limits

## API Coverage

The connector currently uses these stable Airflow REST API endpoints:

```text
GET /api/v1/dags
GET /api/v1/dags/{dag_id}/tasks
```

Task dependencies are derived from each task's `downstream_task_ids`.

## Read-Only Behaviour

The Airflow connector performs metadata ingestion only.

It does not:

- create DAGs
- modify DAGs
- trigger DAG runs
- pause or unpause DAGs
- modify tasks
- delete DAGs or tasks

## Closing the Connection

Close the underlying HTTP session when ingestion is complete:

```python
ingestor.close()
```

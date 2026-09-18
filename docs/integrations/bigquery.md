---
title: "BigQuery Integration"
description: "Ingest structured data from Google BigQuery tables and queries into Semantica's KG pipeline."
icon: "google"
---

> Extract data from BigQuery tables, queries, and schemas into Semantica with Application Default Credentials or service-account key-file authentication.


## Installation

```bash
# Install with BigQuery support
pip install "semantica[db-bigquery]"

# Or install the connector separately
pip install google-cloud-bigquery>=3.0.0
```


## Basic Usage

```python
import os
from semantica.ingest import BigQueryIngestor

ingestor = BigQueryIngestor(
    project=os.getenv("BIGQUERY_PROJECT"),
    dataset=os.getenv("BIGQUERY_DATASET"),
)

data = ingestor.ingest_table("orders", limit=1000)
print(f"Retrieved {data.row_count} rows, columns: {data.columns}")
```

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep configuration out of source code. `BigQueryIngestor()` with no arguments reads from `BIGQUERY_*` environment variables automatically, once `BIGQUERY_PROJECT` is set.
</Tip>


## Authentication

<Tabs>
  <Tab title="Application Default Credentials (Recommended)">
    ```python
    import os
    from semantica.ingest import BigQueryIngestor

    ingestor = BigQueryIngestor(
        project=os.getenv("BIGQUERY_PROJECT"),
        dataset=os.getenv("BIGQUERY_DATASET"),
    )
    ```

    Set `BIGQUERY_PROJECT` and optionally `BIGQUERY_DATASET` in your environment:

    ```bash
    export BIGQUERY_PROJECT="my-gcp-project"
    export BIGQUERY_DATASET="my_dataset"
    ```

    ADC resolves credentials automatically from the environment, in this order:
    1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable (path to a key file)
    2. gcloud default credentials (`gcloud auth application-default login`)
    3. Attached service account (GKE, Cloud Run, Vertex AI, Compute Engine)

    For local development:

    ```bash
    gcloud auth application-default login
    ```

    No credential file is needed in production when the workload identity is
    attached to a service account.
  </Tab>
  <Tab title="Service Account Key File">
    ```python
    import os
    from semantica.ingest import BigQueryIngestor

    ingestor = BigQueryIngestor(
        project=os.getenv("BIGQUERY_PROJECT"),
        dataset=os.getenv("BIGQUERY_DATASET"),
        credentials_file=os.getenv("BIGQUERY_CREDENTIALS_FILE"),
    )
    ```

    ```bash
    export BIGQUERY_PROJECT="my-gcp-project"
    export BIGQUERY_DATASET="my_dataset"
    export BIGQUERY_CREDENTIALS_FILE="/run/secrets/sa-key.json"
    ```

    Download a JSON key file from the GCP console under
    **IAM & Admin → Service Accounts → [your service account] → Keys**.
    Store it outside version control and inject it via a secret manager or
    mounted volume.

    The service account requires at minimum the **BigQuery Data Viewer**
    (`roles/bigquery.dataViewer`) and **BigQuery Job User**
    (`roles/bigquery.jobUser`) roles on the project.
  </Tab>
</Tabs>


## Environment Variables

All constructor parameters have environment-variable fallbacks:

| Variable | Parameter | Default |
|---|---|---|
| `BIGQUERY_PROJECT` | `project` | — (required) |
| `BIGQUERY_DATASET` | `dataset` | — |
| `BIGQUERY_LOCATION` | `location` | project default |
| `BIGQUERY_CREDENTIALS_FILE` | `credentials_file` | ADC |


## Table Ingestion

### Ingest a table with filters

```python
data = ingestor.ingest_table(
    "orders",
    where="status = 'shipped' AND created_date >= '2024-01-01'",
    order_by="created_date DESC",
    limit=50000,
)
print(f"Fetched {data.row_count} rows from {data.table_name}")
```

<Warning>
`where` and `order_by` accept raw SQL fragments. They are validated against
a blocklist (statement separators, UNION, DML/DDL keywords, comment sequences)
but are intended for trusted, operator-controlled input. Do not pass raw
end-user text directly to these parameters.
</Warning>

### Override project and dataset per call

```python
data = ingestor.ingest_table(
    "transactions",
    project="analytics-project-456",
    dataset="finance",
    limit=10000,
)
```

### Ingest from a fully-qualified table

```python
# project and dataset on the ingestor default to the connector's values;
# you can override them at the call site for cross-project queries.
data = ingestor.ingest_table(
    "daily_sales",
    project="reporting-project",
    dataset="warehouse",
)
```


## Custom SQL Queries

```python
data = ingestor.ingest_query("""
    SELECT
        customer_id,
        SUM(amount) AS total_amount,
        COUNT(*) AS order_count
    FROM `my-project`.`sales`.`orders`
    WHERE DATE(created_at) >= '2024-01-01'
    GROUP BY customer_id
    ORDER BY total_amount DESC
    LIMIT 1000
""")
print(f"Query returned {data.row_count} rows")
```

The query string is passed verbatim to BigQuery. The caller is responsible for
correctness and safety of the SQL.

### Parameterised queries

```python
from google.cloud import bigquery

job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ScalarQueryParameter("min_amount", "FLOAT64", 100.0),
    ]
)

data = ingestor.ingest_query(
    "SELECT id, amount FROM `my-project`.`sales`.`orders` WHERE amount >= @min_amount",
    job_config=job_config,
)
```


## Schema Inspection

```python
# Inspect columns for a table
schema = ingestor.get_table_schema("orders")

print(f"Row count: {schema['num_rows']}")
print(f"Clustering fields: {schema['clustering_fields']}")
for col in schema["columns"]:
    nullable = "NULLABLE" if col["nullable"] else "REQUIRED"
    print(f"  {col['name']}: {col['type']} ({nullable})")
```

### List tables in a dataset

```python
tables = ingestor.list_tables()
print(f"Tables in dataset: {tables}")
# ['customers', 'orders', 'products', 'returns']

# Or specify a different dataset
tables = ingestor.list_tables(dataset="analytics", project="my-other-project")
```


## Export as Semantica Documents

Convert ingested rows to the Semantica document format for use with
`GraphBuilder`:

```python
documents = ingestor.export_as_documents(
    data,
    id_field="order_id",              # field to use as document ID
    text_fields=["customer_name", "product_name", "notes"],
)

print(f"Created {len(documents)} documents")
# Each document:
# {
#   "id": "ORD-12345",
#   "text": "Alice Smith Widget Pro Shipped on time",
#   "metadata": {
#     "source": "bigquery",
#     "table": "orders",
#     "project": "my-gcp-project",
#     "dataset": "sales",
#     "location": "US",
#     "row_data": { ... full original row ... }
#   }
# }
```

Feed the documents directly into `GraphBuilder`:

```python
from semantica.kg import GraphBuilder

builder = GraphBuilder()
kg = builder.build(documents)
```

When `text_fields` is omitted, all `str`-typed column values in each row are
joined to form the document text. Integer, float, Decimal, and `None` values
are excluded from the default text composition.


## Context Manager

Prefer the context manager for batches of queries — it opens one client on
entry and closes it on exit, so every call inside the `with` block reuses the
same authenticated session:

```python
import os
from semantica.ingest import BigQueryIngestor

with BigQueryIngestor(
    project=os.getenv("BIGQUERY_PROJECT"),
    dataset=os.getenv("BIGQUERY_DATASET"),
) as bq:
    orders = bq.ingest_table("orders", limit=10000)
    customers = bq.ingest_table("customers", limit=5000)
    tables = bq.list_tables()
    schema = bq.get_table_schema("orders")
```

Outside a context manager each method call opens and closes a transient
client independently.


## Connection Testing

```python
import os
from semantica.ingest import BigQueryConnector

connector = BigQueryConnector(
    project=os.getenv("BIGQUERY_PROJECT"),
)
if connector.test_connection():
    print("Connected to BigQuery successfully.")
else:
    print("Connection failed — check project ID and credentials.")
```


## Troubleshooting

**`ImportError: BigQuery ingestion requires optional dependency 'google-cloud-bigquery'`**

Install the optional extra:

```bash
pip install "semantica[db-bigquery]"
```

**`google.auth.exceptions.DefaultCredentialsError`**

No credentials were found in the environment. Either:
- Run `gcloud auth application-default login` for local development, or
- Set `GOOGLE_APPLICATION_CREDENTIALS` to the path of a service-account JSON key file, or
- Set `BIGQUERY_CREDENTIALS_FILE` to the path of a service-account JSON key file.

**`google.api_core.exceptions.Forbidden`**

The service account or user account does not have permission to access the
dataset or table. Ensure the account has at minimum:
- `roles/bigquery.dataViewer` on the dataset or project
- `roles/bigquery.jobUser` on the project

**`ValidationError: Invalid BigQuery project ID`**

Project IDs may contain letters, digits, hyphens, and underscores, and must
start with a letter. Numeric-only or leading-hyphen project IDs are rejected.

**`ValidationError: Invalid table_name`**

Table and dataset names must start with a letter or underscore and contain
only letters, digits, and underscores. Hyphens are not permitted in table or
dataset names (use underscores instead).

**Slow queries**

Use `limit` and `where` to restrict the rows fetched. For large analytical
queries, consider using `ingest_query()` with a pre-aggregated SQL statement
rather than ingesting raw table rows.


## See Also

- [Ingest Module](../reference/ingest) — Full `BigQueryIngestor` API and all other ingestors.
- [Snowflake Integration](/integrations/snowflake) — Warehouse connector with a similar design.
- [Redshift Integration](/integrations/redshift) — AWS Redshift connector.
- [Databricks Integration](/integrations/databricks) — Lakehouse connector.
- [Installation](../installation) — All optional dependency extras.
- [Knowledge Graph](../reference/kg) — Build a KG from ingested BigQuery data.

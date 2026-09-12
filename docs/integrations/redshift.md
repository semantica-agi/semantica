---
title: "Amazon Redshift Integration"
description: "Ingest structured data from Amazon Redshift tables and queries into Semantica's KG pipeline."
icon: "database"
---

> Extract data from Amazon Redshift into Semantica with password/native or IAM-role authentication, using the PostgreSQL-compatible wire protocol.


## Installation

```bash
# Install with Redshift support
pip install "semantica[db-redshift]"

# Or install the connector separately
pip install redshift-connector>=2.0.0
```

`redshift-connector` is an optional dependency. A plain `pip install semantica` never pulls it in, and `import semantica.ingest` never loads it eagerly — the SDK is imported only when you first use `RedshiftConnector` or `RedshiftIngestor`.

<Note>
This connector uses the Redshift database wire protocol for read ingestion. COPY, UNLOAD, S3 integration, Spectrum external tables, and the Redshift Data API are outside the current scope of this integration.
</Note>


## Basic Usage

```python
from semantica.ingest import RedshiftIngestor
import os

ingestor = RedshiftIngestor(
    host=os.getenv("REDSHIFT_HOST"),
    database=os.getenv("REDSHIFT_DATABASE"),
    user=os.getenv("REDSHIFT_USER"),
    password=os.getenv("REDSHIFT_PASSWORD"),
)

data = ingestor.ingest_table("customers")
print(f"Retrieved {data.row_count} rows — columns: {data.columns}")
```

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `RedshiftIngestor()` with no arguments reads from `REDSHIFT_*` environment variables automatically.
</Tip>


## Authentication

<Tabs>
  <Tab title="Password / Native">
    The standard Redshift database username and password:

    ```python
    import os
    from semantica.ingest import RedshiftIngestor

    ingestor = RedshiftIngestor(
        host=os.getenv("REDSHIFT_HOST"),       # e.g. cluster.abc.us-east-1.redshift.amazonaws.com
        database=os.getenv("REDSHIFT_DATABASE"),
        user=os.getenv("REDSHIFT_USER"),
        password=os.getenv("REDSHIFT_PASSWORD"),
        port=5439,    # default; omit to use the default
        ssl=True,     # default
    )
    ```

    Required environment variables:

    ```bash
    export REDSHIFT_HOST="cluster.abc.us-east-1.redshift.amazonaws.com"
    export REDSHIFT_DATABASE="dev"
    export REDSHIFT_USER="awsuser"
    export REDSHIFT_PASSWORD="your-password"
    ```
  </Tab>
  <Tab title="IAM Role (Recommended for AWS)">
    Use `iam=True` to obtain temporary credentials via
    `GetClusterCredentials`. The connector delegates credential resolution
    entirely to `redshift-connector` / boto3 — Semantica never calls AWS
    APIs directly.

    **Profile-based** (reads `~/.aws/credentials`):

    ```python
    import os
    from semantica.ingest import RedshiftIngestor

    ingestor = RedshiftIngestor(
        host=os.getenv("REDSHIFT_HOST"),
        database=os.getenv("REDSHIFT_DATABASE"),
        iam=True,
        db_user=os.getenv("REDSHIFT_DB_USER"),
        cluster_identifier=os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"),
        profile="default",   # AWS credentials-file profile
    )
    ```

    **Explicit AWS credentials** (e.g. for CI/CD or IAM roles with short-lived keys):

    ```python
    ingestor = RedshiftIngestor(
        host=os.getenv("REDSHIFT_HOST"),
        database=os.getenv("REDSHIFT_DATABASE"),
        iam=True,
        db_user=os.getenv("REDSHIFT_DB_USER"),
        cluster_identifier=os.getenv("REDSHIFT_CLUSTER_IDENTIFIER"),
        region=os.getenv("REDSHIFT_REGION"),
        access_key_id=os.getenv("REDSHIFT_ACCESS_KEY_ID"),
        secret_access_key=os.getenv("REDSHIFT_SECRET_ACCESS_KEY"),
        session_token=os.getenv("REDSHIFT_SESSION_TOKEN"),  # only for temporary creds
    )
    ```

    When neither `profile` nor explicit keys are supplied, `redshift-connector`
    falls back to the standard AWS credential chain: `AWS_*` environment
    variables, instance-profile metadata, etc.

    Required for IAM mode: `host`, `database`, `db_user`, `cluster_identifier`.
    The `region` parameter is optional when it can be inferred from the
    credential chain or the cluster endpoint.
  </Tab>
</Tabs>


## Environment Variables

All constructor parameters have `REDSHIFT_*` environment-variable fallbacks.
Explicit constructor values always take precedence.

| Variable | Parameter | Default |
|---|---|---|
| `REDSHIFT_HOST` | `host` | — |
| `REDSHIFT_DATABASE` | `database` | — |
| `REDSHIFT_USER` | `user` | — |
| `REDSHIFT_PASSWORD` | `password` | — |
| `REDSHIFT_PORT` | `port` | `5439` |
| `REDSHIFT_SCHEMA` | `schema` | `"public"` |
| `REDSHIFT_DB_USER` | `db_user` | — |
| `REDSHIFT_CLUSTER_IDENTIFIER` | `cluster_identifier` | — |
| `REDSHIFT_REGION` | `region` | — |
| `REDSHIFT_PROFILE` | `profile` | — |
| `REDSHIFT_ACCESS_KEY_ID` | `access_key_id` | — |
| `REDSHIFT_SECRET_ACCESS_KEY` | `secret_access_key` | — |
| `REDSHIFT_SESSION_TOKEN` | `session_token` | — |


## Querying

### Ingest a table

```python
data = ingestor.ingest_table("orders")
print(f"{data.row_count} rows, columns: {data.columns}")
```

### Schema, filters, and pagination

```python
data = ingestor.ingest_table(
    "orders",
    schema="sales",          # defaults to the ingestor's schema attribute ("public")
    database="analytics",    # defaults to the connector's database
    where="status = 'shipped' AND total > 100",
    order_by="created_at DESC",
    limit=5000,
    offset=0,
)
```

<Warning>
`where` and `order_by` accept raw SQL fragments and must be trusted, operator-controlled input. Do not pass raw end-user strings here. They are validated against a blocklist that rejects statement separators, `UNION`, DML/DDL keywords, and time-based injection patterns, but this is not a full parser.
</Warning>

### Custom SQL

```python
data = ingestor.ingest_query("""
    SELECT customer_id, SUM(total) AS lifetime_value
    FROM sales.orders
    WHERE status = 'completed'
    GROUP BY customer_id
    ORDER BY lifetime_value DESC
    LIMIT 1000
""")
print(f"{data.row_count} rows")
```

### Parameterized queries

Use `%s` placeholders (DB-API 2.0 `format` paramstyle, which is the default for `redshift-connector`):

```python
data = ingestor.ingest_query(
    "SELECT id, name FROM users WHERE region = %s AND active = %s",
    params=("us-east-1", True),
)
```

### Batch fetching for large result sets

Use `batch_size` to control the driver fetch size — rows are fetched from
the server in chunks of that size rather than all at once, and each chunk is
converted immediately before the next is requested:

```python
data = ingestor.ingest_query(
    "SELECT * FROM large_events_table",
    batch_size=10000,
)
```

`batch_size` controls how many rows the driver reads from Redshift per
round-trip. The returned `RedshiftData.data` list still contains all matching
rows; use `LIMIT`/`OFFSET` in the query itself if you need to cap the total
result size.


## Schema Discovery

### List base tables in a schema

```python
tables = ingestor.list_tables(schema="public")
print(tables)  # ["customers", "orders", "products", ...]
```

Views are excluded; only base tables are returned.

### Inspect column metadata

```python
schema = ingestor.get_table_schema("customers", schema="public")

for col in schema["columns"]:
    print(f"{col['name']}: {col['type']} (nullable={col['nullable']})")

print("Primary keys:", schema["primary_keys"])
```

Each column dict contains:

| Key | Type | Description |
|---|---|---|
| `name` | `str` | Column name |
| `type` | `str` | Redshift data type (e.g. `"integer"`, `"character varying"`) |
| `nullable` | `bool` | Whether the column accepts `NULL` |

`primary_keys` is a list of column-name strings (empty list when no primary key is defined).


## Export as Semantica Documents

Convert ingested rows to the document format that `GraphBuilder` consumes:

```python
documents = ingestor.export_as_documents(
    data,
    id_field="customer_id",        # column used as document ID; defaults to "id"
    text_fields=["name", "notes"], # columns joined as document text; omit to auto-select
)

print(f"Created {len(documents)} documents")
# Each document:
# {
#   "id": "12345",
#   "text": "Alice Acme customer notes here",
#   "metadata": {
#     "source": "redshift",
#     "table": "customers",
#     "database": "analytics",
#     "schema": "public",
#     "row_data": { ... full cleaned row ... }
#   }
# }
```

**ID resolution**: `str(row.get(id_field, row_index))` — the integer row index is used as a deterministic fallback when the `id_field` column is absent.

**Text when `text_fields` is provided**: each non-`None` field value is converted to a string and joined with a single space.

**Text when `text_fields=None`**: only columns whose values are already `str` type are joined. Integer, float, boolean, and `None` values are excluded, matching the Snowflake and Databricks connector behavior.

Pass the documents directly to `GraphBuilder`:

```python
from semantica.kg import GraphBuilder

builder = GraphBuilder()
graph = builder.build(documents)
print(f"Entities: {graph['metadata']['num_entities']}")
```


## Context Manager

Prefer the context manager for jobs that run multiple queries — it opens one connection on entry and closes it on exit, so every call inside the `with` block reuses the same authenticated session:

```python
with RedshiftIngestor(
    host=os.getenv("REDSHIFT_HOST"),
    database=os.getenv("REDSHIFT_DATABASE"),
    user=os.getenv("REDSHIFT_USER"),
    password=os.getenv("REDSHIFT_PASSWORD"),
) as ingestor:
    customers = ingestor.ingest_table("customers", limit=50000)
    orders    = ingestor.ingest_table("orders",    limit=50000)
    schema    = ingestor.get_table_schema("customers")
    tables    = ingestor.list_tables()
# Connection closed automatically on exit, even if an exception is raised.
```

Standalone calls (without `with`) open and close a transient connection per call.


## Connection Test

```python
from semantica.ingest import RedshiftConnector

connector = RedshiftConnector(
    host="cluster.abc.us-east-1.redshift.amazonaws.com",
    database="dev",
    user="awsuser",
    password="your-password",
)
if connector.test_connection():
    print("Connection OK")
else:
    print("Connection failed — check host, credentials, and network access")
```


## See Also

- [Ingest Module](../reference/ingest) — Full `RedshiftIngestor` reference and all other ingestors.
- [Snowflake Integration](/integrations/snowflake) — SQL data warehouse connector with similar table/query ingestion.
- [Databricks Integration](/integrations/databricks) — Delta Lake / Unity Catalog connector.
- [Pipeline](../reference/pipeline) — Use Redshift ingestion as a pipeline step.
- [Installation](../installation) — All optional dependency extras.
- [Knowledge Graph](../reference/kg) — Build a knowledge graph from ingested Redshift data.

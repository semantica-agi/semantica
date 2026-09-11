---
title: "Looker Integration"
description: "Ingest Looker Looks, Dashboards, LookML models, Folders, and Projects metadata into Semantica's KG pipeline."
icon: "chart-line"
---

> Extract Looker metadata into Semantica with API client credentials, using the official `looker-sdk` and the validated instance endpoint.


## Installation

```bash
# Install with Looker support
pip install "semantica[ingest-looker]"

# Or install the connector separately
pip install looker-sdk>=24.0.0
```

`looker-sdk` is an optional dependency. A plain `pip install semantica` never pulls it in, and `import semantica.ingest` never loads it eagerly — the SDK is imported only when you first use `LookerConnector` or `LookerIngestor`. `LookerData` is importable without the SDK, so type annotations and data classes keep working in an SDK-free environment.

<Note>
This connector ingests Looker metadata only — Looks, Dashboards, LookML models (with their Explores), Folders, and Projects. Query result rows, scheduled plans, users, and groups are outside the current scope of this integration.
</Note>


## Basic Usage

```python
import os
from semantica.ingest import LookerIngestor

with LookerIngestor(
    base_url=os.getenv("LOOKERSDK_BASE_URL"),          # e.g. https://looker.example.com
    client_id=os.getenv("LOOKERSDK_CLIENT_ID"),
    client_secret=os.getenv("LOOKERSDK_CLIENT_SECRET"),
) as ingestor:
    looks = ingestor.ingest_looks()
    print(f"Retrieved {looks.row_count} looks — columns: {looks.columns}")

    documents = ingestor.export_as_documents(looks)
```

<Note>
`LookerIngestor` opens one authenticated session on entry and closes it on exit, so every call inside the `with` block reuses the validated connection. Standalone calls (without `with`) open and close a transient connection per call.
</Note>

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `LookerIngestor()` with no arguments reads from the `LOOKERSDK_*` environment variables automatically.
</Tip>


## Authentication

<Tabs>
  <Tab title="Client ID / Client Secret">
    Looker API credentials are the `client_id` and `client_secret` pair that
    Looker issues for API3 access (Admin → Users → API Keys). Pass them
    explicitly, or let the connector read the `LOOKERSDK_CLIENT_ID` and
    `LOOKERSDK_CLIENT_SECRET` environment variables:

    ```python
    import os
    from semantica.ingest import LookerIngestor

    ingestor = LookerIngestor(
        base_url=os.getenv("LOOKERSDK_BASE_URL"),   # must be https
        client_id=os.getenv("LOOKERSDK_CLIENT_ID"),
        client_secret=os.getenv("LOOKERSDK_CLIENT_SECRET"),
    )
    ```

    Required environment variables:

    ```bash
    export LOOKERSDK_BASE_URL="https://looker.example.com"
    export LOOKERSDK_CLIENT_ID="your-client-id"
    export LOOKERSDK_CLIENT_SECRET="your-client-secret"
    ```

    The endpoint must use `https`. A non-`https` scheme (for example
    `http://looker.internal`) is rejected with a `ValidationError` before any
    client is constructed.
  </Tab>
  <Tab title="Existing looker.ini">
    The connector also accepts a Looker SDK configuration file. Point
    `config_file` at the file and, optionally, select a `section` inside it:

    ```python
    from semantica.ingest import LookerIngestor

    ingestor = LookerIngestor(
        config_file="looker.ini",
        section="Looker",
    )
    ```

    `config_file` defaults to `"looker.ini"`. Values already present in the
    file are used when the matching constructor argument or environment
    variable is absent.
  </Tab>
</Tabs>

<Warning>
`allow_private_ips=True` is required to connect to a private, loopback, or
link-local endpoint, and it also relaxes the `https` requirement so a
non-`https` scheme is accepted. Leave it off unless you are deliberately
targeting an internal instance.
</Warning>

If an explicit `base_url` conflicts with `LOOKERSDK_BASE_URL` or the value in
the config file, the connector raises a `ValidationError` rather than
connecting to a host you did not validate.


## Environment Variables

All connection parameters have `LOOKERSDK_*` environment-variable fallbacks,
resolved through the SDK's own `ApiSettings`. Explicit constructor values
always take precedence.

| Variable | Parameter | Default |
|---|---|---|
| `LOOKERSDK_BASE_URL` | `base_url` | — |
| `LOOKERSDK_CLIENT_ID` | `client_id` | — |
| `LOOKERSDK_CLIENT_SECRET` | `client_secret` | — |

`config_file` and `section` are constructor parameters rather than environment
variables:

| Parameter | Description | Default |
|---|---|---|
| `config_file` | Path to an existing `looker.ini` file | `"looker.ini"` |
| `section` | Section name inside `config_file` | — |
| `allow_private_ips` | Allow private endpoints and non-`https` schemes | `False` |


## Metadata Ingestion

Each read returns a `LookerData` object with `data` (normalized metadata
dictionaries), `row_count`, `columns`, `content_type`, `base_url`, `metadata`,
and `ingested_at`.

| Method | SDK read | `content_type` |
|---|---|---|
| `ingest_looks()` | `all_looks` | `"look"` |
| `ingest_dashboards()` | `all_dashboards` | `"dashboard"` |
| `ingest_lookml_models()` | `all_lookml_models` | `"lookml_model"` |
| `ingest_folders()` | `all_folders` | `"folder"` |
| `ingest_projects()` | `all_projects` | `"project"` |

Reads use the SDK's `all_*` collection methods. Each method accepts optional
keyword arguments that are forwarded to the SDK call — `transport_options` and
`fields` for most reads, plus `limit`/`offset` for `ingest_lookml_models()`:

```python
looks = ingestor.ingest_looks(fields="id,title,description,model")
models = ingestor.ingest_lookml_models(limit=100)
```

<Note>
This is a metadata-only connector. Dashboards are read as `DashboardBase`
records without tiles, so no query result rows are fetched or stored.
</Note>

### LookML models and Explores

LookML models are returned with their Explores nested inside the parent model
record. Explores carry no parent reference of their own, so the parent
`project_name`/`name` pair is composed into each nested identifier:

```python
models = ingestor.ingest_lookml_models()

for model in models.data:
    print(f"{model['project_name']}.{model['name']}")
    for explore in model["explores"]:
        print(f"  {explore['name']}")
```


## Export as Semantica Documents

`export_as_documents(data)` converts a `LookerData` result into the
`{"id", "text", "metadata"}` document shape that `GraphBuilder` consumes:

```python
documents = ingestor.export_as_documents(looks)

print(f"Created {len(documents)} documents")
# Each document:
# {
#   "id": "looker:look:42",
#   "text": "Monthly Revenue Revenue by region orders jdoe",
#   "metadata": {
#     "source": "looker",
#     "content_type": "look",
#     "row_data": { ... allowlisted Look metadata ... },
#     "look_id": 42
#   }
# }
```

Document `id` values are namespaced per content type so they stay unique
across collections: `looker:look:<id>`, `looker:dashboard:<id>`,
`looker:folder:<id>`, `looker:project:<id>`, and
`looker:lookml_model:<project>.<name>` for models. Every document's
`metadata["source"]` is `"looker"`, and `metadata["content_type"]` records
which collection it came from. The full normalized record is preserved under
`metadata["row_data"]`.

LookML model documents additionally nest their Explores, each with its own
namespaced id and parent model reference:

```python
# {
#   "id": "looker:lookml_model:ecommerce.orders",
#   "text": "Orders orders ecommerce Order Items order_items",
#   "metadata": {
#     "source": "looker",
#     "content_type": "lookml_model",
#     "row_data": { ... allowlisted LookML model metadata ... },
#     "project_name": "ecommerce",
#     "model_name": "orders",
#     "explores": [
#       {
#         "id": "looker:lookml_model:ecommerce.orders:explore:order_items",
#         "name": "order_items",
#         "label": "Order Items",
#         "view_name": "order_items",
#         "description": None,
#         "parent_model": "ecommerce.orders"
#       }
#     ],
#     "explore_count": 1
#   }
# }
```

Pass the documents directly to `GraphBuilder`:

```python
from semantica.kg import GraphBuilder

builder = GraphBuilder()
graph = builder.build(documents)
print(f"Entities: {graph['metadata']['num_entities']}")
```

Exported documents are JSON-serializable: nested SDK model objects become
plain dictionaries or lists, and `datetime` values become ISO 8601 strings.


## Security

The connector validates the user-supplied endpoint before any client is
constructed, then binds the client to that exact validated `base_url` — if the
SDK resolves a different host from the environment or config file, it fails
closed instead of connecting. It also refuses to follow redirects, does not
trust proxy environment variables, and requires `https` unless
`allow_private_ips` is explicitly enabled.

Record normalization projects every SDK object through an explicit allowlist of
retained fields. Secret-adjacent fields such as `Project.git_password`,
`Project.deploy_secret`, `Dashboard.password`, `Dashboard.pdt_password`, and
`LookmlModel.device_token` are dropped, and any `user:password@` userinfo in
`Project.git_remote_url` is scrubbed. Documents carry no `base_url` or
credentials.


## See Also

- [Ingest Module](../reference/ingest) — Full `LookerIngestor` reference and all other ingestors.
- [Snowflake Integration](/integrations/snowflake) — SQL data warehouse connector with similar metadata ingestion.
- [Redshift Integration](/integrations/redshift) — Warehouse connector for tabular and query-based ingestion.
- [Installation](../installation) — All optional dependency extras.
- [Knowledge Graph](../reference/kg) — Build a knowledge graph from ingested Looker metadata.

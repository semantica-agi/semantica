---
title: "ServiceNow Integration"
description: "Ingest CMDB configuration items, incidents, changes and any other ServiceNow table into Semantica's KG pipeline via the Table API."
icon: "server"
---

> Pull ServiceNow table records into Semantica using the Table API with Basic or OAuth2 authentication.


## Installation

```bash
pip install "semantica[ingest-servicenow]"
```

The connector only needs `requests`, which already ships with Semantica's core, so the extra is a no-op today; it exists so the dependency is declared explicitly. The module is a lazy export: `import semantica.ingest` does not load it until you first touch `ServiceNowIngestor`.


## Basic Usage

```python
import os
from semantica.ingest import ServiceNowIngestor

ingestor = ServiceNowIngestor(
    instance_url=os.getenv("SERVICENOW_INSTANCE_URL"),
    username=os.getenv("SERVICENOW_USERNAME"),
    password=os.getenv("SERVICENOW_PASSWORD"),
)

data = ingestor.ingest_table("cmdb_ci_server", query="operational_status=1")
documents = ingestor.export_as_documents(data)

print(f"{data.count} record(s) from {data.table}")
```

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `ServiceNowIngestor()` with no arguments reads from `SERVICENOW_*` environment variables automatically.
</Tip>


## Authentication

| Setting | Argument | Environment variable |
| --- | --- | --- |
| Instance URL (`https://<instance>.service-now.com`) | `instance_url` | `SERVICENOW_INSTANCE_URL` |
| Auth flow (`basic` or `oauth2`, optional) | `auth` | `SERVICENOW_AUTH` |
| Username | `username` | `SERVICENOW_USERNAME` |
| Password | `password` | `SERVICENOW_PASSWORD` |
| OAuth2 client ID | `client_id` | `SERVICENOW_CLIENT_ID` |
| OAuth2 client secret | `client_secret` | `SERVICENOW_CLIENT_SECRET` |

- **Basic** — the default when only `username`/`password` are set.
- **OAuth2** — selected automatically when `client_id` is set. The token is fetched from `<instance_url>/oauth_token.do` with the `password` grant when `username`/`password` are also present, otherwise with `client_credentials`.

Missing configuration raises `ValidationError` before any network call is made.


## Querying a Table

`ingest_table` maps directly onto the Table API query parameters:

```python
data = ingestor.ingest_table(
    "incident",
    query="active=true^priority=1",       # sysparm_query (encoded query)
    fields=["sys_id", "number", "short_description", "cmdb_ci"],
    limit=500,                            # stop after 500 rows
    batch_size=200,                       # sysparm_limit per request
    display_value="all",                  # raw + display values per field
)
```

Pagination is offset based (`sysparm_limit` / `sysparm_offset`) and is followed until the table is exhausted or `limit` rows have been collected. Reference-field `link` objects are dropped by default (`sysparm_exclude_reference_link=true`); pass `exclude_reference_link=False` to keep them.

CMDB relationships live in `cmdb_rel_ci`:

```python
rels = ingestor.ingest_table("cmdb_rel_ci", fields=["parent", "child", "type"])
```


## Document Output

`export_as_documents` flattens each record to a dict with `id` (the record's `sys_id`), `name` (resolved from `name`, `number` or `short_description`), `source` (the instance URL) and `table`, plus every field returned by the API, so the output feeds directly into `GraphBuilder`:

```python
from semantica.kg import GraphBuilder

documents = ingestor.export_as_documents(data)
graph = GraphBuilder().build(documents)
```


## Security

Every outbound HTTP call — including the OAuth2 token request — goes through Semantica's shared SSRF guard, so a user-supplied instance URL cannot reach private, loopback or link-local address space. Set `allow_private_ips=True` only for self-hosted deployments that genuinely need it.

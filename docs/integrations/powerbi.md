---
title: "Power BI Integration"
description: "Ingest workspace, dataset, report and dataflow metadata from the Power BI REST API into Semantica's KG pipeline."
icon: "chart-simple"
---

> Pull Power BI metadata into Semantica using the REST API with Azure AD OAuth2 client-credentials authentication.


## Installation

```bash
pip install semantica
```

`requests` ships with Semantica as a core dependency, so this connector works as soon as the package is installed — there is no extra to install. The module is a lazy export: `import semantica.ingest` does not load it until you first touch `PowerBIIngestor`.

<Note>
This connector reads **metadata** — workspaces, datasets, reports and dataflows. It does not execute DAX queries or export dataset rows; the Power BI REST API exposes catalog information, not table data.
</Note>


## Basic Usage

```python
import os
from semantica.ingest import PowerBIIngestor

ingestor = PowerBIIngestor(
    tenant_id=os.getenv("POWERBI_TENANT_ID"),
    client_id=os.getenv("POWERBI_CLIENT_ID"),
    client_secret=os.getenv("POWERBI_CLIENT_SECRET"),
)

data = ingestor.ingest_workspace_metadata()
documents = ingestor.export_as_documents(data)

print(f"{len(documents)} documents — {data.metadata['dataset_count']} dataset(s)")
```

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `PowerBIIngestor()` with no arguments reads from `POWERBI_*` environment variables automatically.
</Tip>


## Authentication

The connector uses the Azure AD OAuth2 **client-credentials** flow. Register an application in Azure AD, grant it access to the Power BI service, and supply its tenant, client ID and secret.

Required configuration:

| Setting | Argument | Environment variable |
| --- | --- | --- |
| Azure AD tenant ID | `tenant_id` | `POWERBI_TENANT_ID` |
| Application (client) ID | `client_id` | `POWERBI_CLIENT_ID` |
| Client secret | `client_secret` | `POWERBI_CLIENT_SECRET` |
| Workspace / group ID (optional) | `workspace_id` | `POWERBI_WORKSPACE_ID` |

Missing any of the first three raises `ValidationError` before any network call is made. Tokens are cached and refreshed automatically shortly before expiry. The client secret is never written to logs.


## Scoping to One Workspace

Pass a workspace (group) ID to read a single workspace; omit it to walk every workspace the service principal can see, collecting datasets, reports and dataflows from each and tagging every record with the `workspace_id` it came from. That per-workspace walk is deliberate: the unscoped `myorg` endpoints only cover My workspace, and dataflows have no unscoped endpoint.

```python
data = ingestor.ingest_workspace_metadata(workspace_id="00000000-0000-0000-0000-000000000000")
```

Select only the resources you need with `include` (an empty list pulls nothing):

```python
data = ingestor.ingest_workspace_metadata(include=["datasets", "reports"])
```


## Document Output

`export_as_documents` returns the standard `{"id", "text", "metadata"}` shape, so the output feeds directly into `GraphBuilder`:

```python
from semantica.kg import GraphBuilder

documents = ingestor.export_as_documents(data)
graph = GraphBuilder().build(documents)
```

Each document's `metadata` carries `source: "powerbi"`, a `resource_type` of `workspace`, `dataset`, `report` or `dataflow`, plus the original API fields.


## Security

Every outbound HTTP call — including the token request — goes through Semantica's shared SSRF guard, so a user-supplied endpoint cannot reach private, loopback or link-local address space. Set `allow_private_ips=True` only for self-hosted deployments that genuinely need it.

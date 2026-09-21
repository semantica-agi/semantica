---
title: "Microsoft Dynamics 365 Integration"
description: "Ingest entity records from Microsoft Dynamics 365 into Semantica's KG pipeline using the Dataverse Web API."
icon: "microsoft"
---

> Pull accounts, contacts, opportunities, and any custom entity from Dynamics 365 into Semantica using Azure AD client-credentials authentication.

## Installation

```bash
# Install with Dynamics 365 support
pip install "semantica[ingest-dynamics365]"

# Or install the dependency separately
pip install msal>=1.20
```

## Basic Usage

```python
import os
from semantica.ingest import Dynamics365Ingestor

ingestor = Dynamics365Ingestor(
    tenant_id=os.getenv("DYNAMICS_TENANT_ID"),
    client_id=os.getenv("DYNAMICS_CLIENT_ID"),
    client_secret=os.getenv("DYNAMICS_CLIENT_SECRET"),
    org_url=os.getenv("DYNAMICS_ORG_URL"),  # e.g. https://myorg.crm.dynamics.com
)

data = ingestor.ingest_entity("accounts", select=["accountid", "name", "statecode"])
print(f"Retrieved {data.row_count} records")

docs = ingestor.export_as_documents(data)
```

<Tip>
Use environment variables (or a `.env` file with `python-dotenv`) to keep credentials out of source code. `Dynamics365Ingestor()` with no arguments reads from `DYNAMICS_*` environment variables automatically.
</Tip>

## Authentication

Dynamics 365 uses Azure AD client-credentials (app-to-app) authentication via MSAL. You need an **Azure AD app registration** with the Dynamics 365 `user_impersonation` (or `Dynamics CRM` API) permission granted via admin consent.

```python
ingestor = Dynamics365Ingestor(
    tenant_id="your-azure-tenant-id",
    client_id="your-app-client-id",
    client_secret=os.getenv("DYNAMICS_CLIENT_SECRET"),
    org_url="https://myorg.crm.dynamics.com",
)
```

## Environment Variables

| Variable | Description |
|---|---|
| `DYNAMICS_TENANT_ID` | Azure AD tenant ID |
| `DYNAMICS_CLIENT_ID` | Azure AD app (client) ID |
| `DYNAMICS_CLIENT_SECRET` | Azure AD app client secret |
| `DYNAMICS_ORG_URL` | Dynamics 365 org base URL (e.g. `https://myorg.crm.dynamics.com`) |

## Ingestion Methods

### Ingest an Entity

```python
# Basic — all fields
data = ingestor.ingest_entity("accounts")

# With OData $select, $filter, $top
data = ingestor.ingest_entity(
    "contacts",
    select=["contactid", "fullname", "emailaddress1"],
    filter="statecode eq 0",
    top=500,
)
```

### List Available Entities

```python
entity_names = ingestor.list_entities()
print(entity_names[:10])
```

## Export to Documents

```python
docs = ingestor.export_as_documents(data)
# Each doc: {"id": str, "text": str, "metadata": {"source": "dynamics365", "entity_name": ..., ...}}
```

## Context Manager

```python
with Dynamics365Ingestor(
    tenant_id=os.getenv("DYNAMICS_TENANT_ID"),
    client_id=os.getenv("DYNAMICS_CLIENT_ID"),
    client_secret=os.getenv("DYNAMICS_CLIENT_SECRET"),
    org_url=os.getenv("DYNAMICS_ORG_URL"),
) as d:
    accounts = d.ingest_entity("accounts")
    contacts = d.ingest_entity("contacts")
```

## Dynamics365Data Reference

| Field | Type | Description |
|---|---|---|
| `records` | `list[dict]` | Raw record dicts from the Web API |
| `entity_name` | `str` | Logical name of the entity set |
| `row_count` | `int` | Number of records |
| `columns` | `list[str]` | Field names present across records |
| `org_url` | `str` | Dynamics 365 org base URL |
| `ingested_at` | `datetime` | Timestamp of ingestion |

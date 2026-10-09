---
title: "Apache Cassandra Integration"
description: "Ingest structured data from Apache Cassandra tables into Semantica's KG pipeline."
icon: "database"
---

> Extract data from Apache Cassandra tables into Semantica using the official `cassandra-driver`.

## Installation

```bash
# Install with Cassandra support
pip install "semantica[db-cassandra]"

# Or install the connector separately
pip install "cassandra-driver>=3.29.0"
```

`cassandra-driver` is an optional dependency. A plain `pip install semantica` does not install it, and the Cassandra connector is loaded lazily when first used.

## Basic Usage

```python
import os
from semantica.ingest import CassandraIngestor

ingestor = CassandraIngestor(
    hosts=os.getenv("CASSANDRA_HOSTS", "127.0.0.1").split(","),
    port=int(os.getenv("CASSANDRA_PORT", "9042")),
    username=os.getenv("CASSANDRA_USERNAME"),
    password=os.getenv("CASSANDRA_PASSWORD"),
    keyspace=os.getenv("CASSANDRA_KEYSPACE"),
)

data = ingestor.ingest_table("users")

print(f"Retrieved {data.row_count} rows")
print(f"Columns: {data.columns}")
```

<Tip>
Use environment variables to keep Cassandra credentials out of source code.
</Tip>

## Authentication

For authenticated Cassandra clusters:

```python
from semantica.ingest import CassandraIngestor

ingestor = CassandraIngestor(
    hosts=["127.0.0.1"],
    port=9042,
    username="cassandra",
    password="your-password",
    keyspace="my_keyspace",
)
```

For clusters without authentication:

```python
from semantica.ingest import CassandraIngestor

ingestor = CassandraIngestor(
    hosts=["127.0.0.1"],
    port=9042,
    keyspace="my_keyspace",
)
```

## Querying

### Ingest a table

```python
data = ingestor.ingest_table("orders")
print(f"{data.row_count} rows, columns: {data.columns}")
```

### Limit the number of rows

```python
data = ingestor.ingest_table(
    "orders",
    limit=1000,
)
```

`limit` is translated into a CQL `LIMIT` clause.

## Schema Discovery

```python
schema = ingestor.get_table_schema("users")

for column in schema["columns"]:
    print(
        f"{column['name']}: "
        f"{column['type']} "
        f"(nullable={column['nullable']})"
    )

print("Primary keys:", schema["primary_keys"])
```

Each column contains:

| Key | Type | Description |
|---|---|---|
| `name` | `str` | Column name |
| `type` | `str` | Cassandra CQL type |
| `nullable` | `bool` | Whether the column is nullable |
| `primary_key` | `bool` | Whether the column is part of the primary key |
| `static` | `bool` | Whether the column is static |

`primary_keys` contains the table's primary-key column names in Cassandra order.

## Export as Semantica Documents

```python
documents = ingestor.export_as_documents(
    data,
    id_field="id",
    text_fields=["name", "city"],
)

print(f"Created {len(documents)} documents")
```

Each document contains:

```python
{
    "id": "123",
    "text": "Alice Delhi",
    "metadata": {
        "source": "cassandra",
        "keyspace": "my_keyspace",
        "table": "users",
        "row_data": {}
    }
}
```

**ID resolution**: the configured `id_field` is converted to a string. When the field is absent, the row index is used as a deterministic fallback.

**Text when `text_fields` is provided**: non-`None` values are converted to strings and joined with a single space.

**Text when `text_fields=None`**: only string values are included in the document text.

## Connection Test

```python
from semantica.ingest import CassandraConnector

connector = CassandraConnector(
    hosts=["127.0.0.1"],
    port=9042,
    keyspace="my_keyspace",
)

if connector.test_connection():
    print("Connection OK")
else:
    print("Connection failed")
```

## See Also

- [Ingest Module](../reference/ingest)
- [Redshift Integration](/integrations/redshift)
- [Databricks Integration](/integrations/databricks)
- [Installation](../installation)
- [Knowledge Graph](../reference/kg)

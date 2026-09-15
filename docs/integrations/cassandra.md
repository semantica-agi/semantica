\---

title: "Apache Cassandra Integration"

description: "Ingest structured data from Apache Cassandra tables into Semantica's KG pipeline."

icon: "database"

\---



> Extract data from Apache Cassandra tables into Semantica using the official `cassandra-driver`.



\## Installation



```bash

\# Install with Cassandra support

pip install "semantica\[db-cassandra]"



\# Or install the connector separately

pip install cassandra-driver>=3.29.0





```

`cassandra-driver` is an optional dependency. A plain `pip install semantica` does not install it, and the Cassandra connector is loaded lazily when first used.



\## Basic Usage



```python

from semantica.ingest import CassandraIngestor

import os



ingestor = CassandraIngestor(

&#x20;   hosts=os.getenv("CASSANDRA\_HOSTS", "127.0.0.1").split(","),

&#x20;   port=int(os.getenv("CASSANDRA\_PORT", "9042")),

&#x20;   username=os.getenv("CASSANDRA\_USERNAME"),

&#x20;   password=os.getenv("CASSANDRA\_PASSWORD"),

&#x20;   keyspace=os.getenv("CASSANDRA\_KEYSPACE"),

)



data = ingestor.ingest\_table("users")



print(f"Retrieved {data.row\_count} rows")

print(f"Columns: {data.columns}")



```

<Tip>

Use environment variables to keep Cassandra credentials out of source code.

</Tip>



\## Authentication



For authenticated Cassandra clusters:



```python

from semantica.ingest import CassandraIngestor



ingestor = CassandraIngestor(

&#x20;   hosts=\["127.0.0.1"],

&#x20;   port=9042,

&#x20;   username="cassandra",

&#x20;   password="your-password",

&#x20;   keyspace="my\_keyspace",

)



```

For clusters without authentication:



```python

from semantica.ingest import CassandraIngestor



ingestor = CassandraIngestor(

&#x20;   hosts=\["127.0.0.1"],

&#x20;   port=9042,

&#x20;   keyspace="my\_keyspace",

)



```

\## Querying



\### Ingest a table



```python

data = ingestor.ingest\_table("orders")

print(f"{data.row\_count} rows, columns: {data.columns}")



```

\### Limit the number of rows



```python

data = ingestor.ingest\_table(

&#x20;   "orders",

&#x20;   limit=1000,

)



```



`limit` is translated into a CQL `LIMIT` clause.



\## Schema Discovery



```python

schema = ingestor.get\_table\_schema("users")



for column in schema\["columns"]:

&#x20;   print(

&#x20;       f"{column\['name']}: "

&#x20;       f"{column\['type']} "

&#x20;       f"(nullable={column\['nullable']})"

&#x20;   )



print("Primary keys:", schema\["primary\_keys"])

```



Each column contains:



| Key | Type | Description |

|---|---|---|

| `name` | `str` | Column name |

| `type` | `str` | Cassandra CQL type |

| `nullable` | `bool` | Whether the column is nullable |

| `primary\_key` | `bool` | Whether the column is part of the primary key |

| `static` | `bool` | Whether the column is static |



`primary\_keys` contains the table's primary-key column names in Cassandra order.



\## Export as Semantica Documents



```python

documents = ingestor.export\_as\_documents(

&#x20;   data,

&#x20;   id\_field="id",

&#x20;   text\_fields=\["name", "city"],

)



print(f"Created {len(documents)} documents")

```



Each document contains:



```python

{

&#x20;   "id": "123",

&#x20;   "text": "Alice Delhi",

&#x20;   "metadata": {

&#x20;       "source": "cassandra",

&#x20;       "keyspace": "my\_keyspace",

&#x20;       "table": "users",

&#x20;       "row\_data": {}

&#x20;   }

}

```



\*\*ID resolution\*\*: the configured `id\_field` is converted to a string. When the field is absent, the row index is used as a deterministic fallback.



\*\*Text when `text\_fields` is provided\*\*: non-`None` values are converted to strings and joined with a single space.



\*\*Text when `text\_fields=None`\*\*: only string values are included in the document text.



\## Connection Test



```python

from semantica.ingest import CassandraConnector



connector = CassandraConnector(

&#x20;   hosts=\["127.0.0.1"],

&#x20;   port=9042,

&#x20;   keyspace="my\_keyspace",

)



if connector.test\_connection():

&#x20;   print("Connection OK")

else:

&#x20;   print("Connection failed")

```



\## See Also



\- \[Ingest Module](../reference/ingest)

\- \[Redshift Integration](/integrations/redshift)

\- \[Databricks Integration](/integrations/databricks)

\- \[Installation](../installation)

\- \[Knowledge Graph](../reference/kg)

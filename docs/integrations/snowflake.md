# Snowflake Integration

Semantica features a native integration with **Snowflake**, the powerful cloud data warehouse that enables scalable data storage and analytics for enterprise workloads.

## Overview

Snowflake is integrated into Semantica's `ingest` module via the `SnowflakeIngestor`. This allows you to seamlessly extract structured data from Snowflake tables and queries into semantic structures that can be indexed, searched, and analyzed within the Semantica framework.

- 📖 **Semantica Snowflake Integration Docs**: [Reference Guide](../reference/ingest.md)
- 💻 **Semantica Snowflake Integration GitHub**: [Source Code](https://github.com/Hawksight-AI/semantica/blob/main/semantica/ingest/snowflake_ingestor.py)
- 🧑🏽‍🍳 **Semantica Snowflake Integration Example**: [Snowflake Clear Code Example](../CodeExamples.md#snowflake-clear-code-example)
- 📦 **Semantica Snowflake Integration PyPI**: [Installation Guide](../installation.md)

---

## Integration Documentation

The `SnowflakeIngestor` provides a high-level interface for Snowflake data ingestion. It supports:

*   **Multiple Authentication Methods**: Password, key-pair, OAuth, and SSO authentication.
*   **Advanced Querying**: Custom SQL queries with parameterization and batching.
*   **Schema Introspection**: Automatic table schema discovery and metadata extraction.
*   **Document Export**: Convert Snowflake data to Semantica document format.

### Basic Usage

```python
from semantica.ingest import SnowflakeIngestor

# Initialize with environment variables
ingestor = SnowflakeIngestor()

# Ingest a table
data = ingestor.ingest_table("CUSTOMERS")

# Access the structured data
print(f"Retrieved {data.row_count} rows")
print(f"Columns: {data.columns}")
```

For more details, see the [Ingest Reference](../reference/ingest.md).

---

## Integration Example

We provide a detailed cookbook and clear code examples to help you get started quickly.

### Snowflake Clear Code Example

```python
from semantica.ingest import SnowflakeIngestor
import os
from dotenv import load_dotenv

# 1. Load environment variables
load_dotenv()

# 2. Initialize the Snowflake Ingestor
ingestor = SnowflakeIngestor(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
    database=os.getenv("SNOWFLAKE_DATABASE"),
    schema=os.getenv("SNOWFLAKE_SCHEMA")
)

# 3. Ingest a table with filters
data = ingestor.ingest_table(
    "CUSTOMERS",
    where="COUNTRY = 'USA' AND CREATED_DATE > '2024-01-01'",
    order_by="CREATED_DATE DESC",
    limit=10000
)

# 4. Access the structured data
print(f"--- Customer Data ---")
print(f"Retrieved {data.row_count} customers")
print(f"Columns: {data.columns}")

# 5. Iterate through rows
for row in data.data[:5]:  # Print first 5 rows
    print(f"Customer: {row['NAME']} ({row['EMAIL']})")

# 6. Export as documents for Semantica processing
documents = ingestor.export_as_documents(
    data,
    id_field="CUSTOMER_ID",
    text_fields=["NAME", "EMAIL", "NOTES"]
)

print(f"Created {len(documents)} documents for processing")
```

See more in our [Code Examples](../CodeExamples.md).

---

## GitHub Source

The integration is open-source and available on GitHub. You can explore the implementation, contribute improvements, or report issues.

- [snowflake_ingestor.py](https://github.com/Hawksight-AI/semantica/blob/main/semantica/ingest/snowflake_ingestor.py) - The core implementation of the Snowflake integration.

---

## PyPI & Installation

Snowflake connector is an optional dependency for Semantica. You can install it along with Semantica or as a separate requirement.

### Install via Semantica
```bash
# Install with Snowflake support
pip install semantica[db-snowflake]

# Or install with all database connectors
pip install semantica[db-all]
```

### Install Snowflake connector manually
If you are working in a custom environment:
```bash
pip install snowflake-connector-python
```

For full installation details, see the [Installation Guide](../installation.md).

---

## Authentication Methods

Snowflake integration supports multiple authentication methods for different security requirements:

### Password Authentication
```python
ingestor = SnowflakeIngestor(
    account="myaccount",
    user="myuser",
    password="mypassword",
    warehouse="COMPUTE_WH"
)
```

### Key-Pair Authentication (Recommended for Production)
```python
ingestor = SnowflakeIngestor(
    account="myaccount",
    user="myuser",
    private_key_path="/path/to/rsa_key.p8",
    warehouse="COMPUTE_WH"
)
```

### OAuth Authentication
```python
ingestor = SnowflakeIngestor(
    account="myaccount",
    user="myuser",
    authenticator="oauth",
    token="your_oauth_token",
    warehouse="COMPUTE_WH"
)
```

### SSO Authentication
```python
ingestor = SnowflakeIngestor(
    account="myaccount",
    user="myuser",
    authenticator="externalbrowser",
    warehouse="COMPUTE_WH"
)
```

---

## Advanced Features

### Schema Introspection
```python
# Get table schema
schema = ingestor.get_table_schema("CUSTOMERS")
for column in schema["columns"]:
    print(f"{column['name']}: {column['type']}")
```

### Custom Queries
```python
# Execute custom SQL
data = ingestor.ingest_query("""
    SELECT 
        CUSTOMER_ID,
        SUM(AMOUNT) AS TOTAL_AMOUNT
    FROM SALES
    WHERE DATE >= '2024-01-01'
    GROUP BY CUSTOMER_ID
""")
```

### Batch Processing
```python
# Handle large result sets
data = ingestor.ingest_query(
    "SELECT * FROM LARGE_TABLE",
    batch_size=5000
)
```

---

## Best Practices

### Use Environment Variables
```python
import os
from dotenv import load_dotenv

load_dotenv()
ingestor = SnowflakeIngestor()  # Reads from environment
```

### Use Key-Pair Authentication for Production
```python
ingestor = SnowflakeIngestor(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    private_key_path=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
    warehouse="COMPUTE_WH"
)
```

### Paginate Large Results
```python
PAGE_SIZE = 10000
for page in range(total_pages):
    data = ingestor.ingest_table(
        "LARGE_TABLE",
        limit=PAGE_SIZE,
        offset=page * PAGE_SIZE
    )
    process_batch(data)
```

---

## Troubleshooting

### Connection Issues
```python
# Test connection
connector = SnowflakeConnector(
    account="myaccount",
    user="myuser",
    password="mypassword"
)

if not connector.test_connection():
    print("Connection failed - check credentials")
```

### Performance Optimization
```python
# Use appropriate warehouse size
ingestor = SnowflakeIngestor(
    account="myaccount",
    user="myuser",
    password="mypassword",
    warehouse="LARGE_WH"  # For heavy workloads
)
```

---

## See Also

- **[Ingest Module Reference](../reference/ingest.md)** - Complete ingestion documentation
- **[Getting Started Guide](../getting-started.md)** - Quick start with Semantica
- **[Code Examples](../CodeExamples.md)** - More integration examples
- **[Installation Guide](../installation.md)** - Installation instructions

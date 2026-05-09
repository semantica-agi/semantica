# Ingest

> **Universal data ingestion from files, web, feeds, streams, repos, emails, and databases.**

---

## 🎯 Overview

The **Ingest Module** is the entry point for loading data into Semantica. It provides universal data ingestion from files, web content, feeds, streams, repositories, emails, databases, and more.

### What is Data Ingestion?

**Data ingestion** is the process of loading data from various sources into Semantica for processing. The ingest module handles:
- **File Systems**: Local files, cloud storage (S3, GCS, Azure)
- **Analytics Files**: Apache Parquet files and partitioned datasets
- **Web Content**: Websites, RSS feeds, APIs
- **Streams**: Real-time data from Kafka, RabbitMQ, etc.
- **Databases**: SQL, NoSQL, and cloud data warehouses including Snowflake
- **Repositories**: Git repositories (GitHub, GitLab)
- **Email**: IMAP, POP3 servers
- **MCP**: Model Context Protocol servers

### Why Use the Ingest Module?

- **Universal Support**: Handle multiple data formats and sources
- **Automatic Detection**: Automatically detect file types and content
- **Streaming Support**: Process real-time data streams
- **Cloud Integration**: Direct support for cloud storage
- **Rate Limiting**: Built-in rate limiting for web crawling
- **Error Handling**: Robust error handling and retry logic

### How It Works

1. **Source Detection**: Automatically detect the type of data source
2. **Connection**: Establish connection to the source (file system, web, database, etc.)
3. **Loading**: Load data from the source
4. **Format Detection**: Detect the format of the loaded data
5. **Output**: Return data in a standardized format for processing

<div class="grid cards" markdown>

-   :material-file-document-multiple:{ .lg .middle } **File Ingestion**

    ---

    Local and Cloud (S3/GCS/Azure) file processing with type detection

-   :material-web:{ .lg .middle } **Web Crawling**

    ---

    Scrape websites with rate limiting, robots.txt compliance, and JS rendering

-   :material-rss:{ .lg .middle } **Feed Monitoring**

    ---

    Consume RSS/Atom feeds with real-time update monitoring

-   :material-broadcast:{ .lg .middle } **Stream Processing**

    ---

    Ingest from Kafka, RabbitMQ, Kinesis, and Pulsar

-   :material-source-branch:{ .lg .middle } **Code Repos**

    ---

    Clone and analyze Git repositories (GitHub/GitLab)

-   :material-database:{ .lg .middle } **Databases**

    ---

    Ingest tables and query results from SQL, NoSQL, and cloud data warehouses including Snowflake

-   :material-table:{ .lg .middle } **Parquet Datasets**

    ---

    Read Parquet files, schemas, metadata, and Hive-style partitioned directories

</div>

!!! tip "When to Use"
    - **Data Onboarding**: The entry point for all external data into Semantica
    - **Crawling**: Building a dataset from the web
    - **Monitoring**: Listening to real-time data streams
    - **Migration**: Importing legacy data from databases

---

## ⚙️ Algorithms Used

### File Processing
- **Magic Number Detection**: Identifying file types by binary signatures, not just extensions.
- **Recursive Traversal**: Efficiently walking directory trees.

### Web Ingestion
- **Sitemap Parsing**: Discovering URLs via XML sitemaps.
- **DOM Extraction**: Removing boilerplate (nav/ads) to extract main content.
- **Politeness**: Respecting `robots.txt` and enforcing crawl delays.

### Stream Processing
- **Consumer Groups**: Managing offsets and scaling consumption (Kafka).
- **Backpressure**: Handling high-velocity streams without crashing.

### Repository Analysis
- **AST Parsing**: Extracting code structure (classes/functions) without executing.
- **Dependency Parsing**: Reading `requirements.txt`, `package.json`, etc.

---

## Main Classes

### FileIngestor

Handles file systems and object storage.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_file(path)` | Process single file |
| `ingest_directory(path)` | Process folder |

### ParquetIngestor

Handles Apache Parquet files and partitioned datasets.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_file(path, columns=None, limit=None)` | Read a Parquet file |
| `ingest_directory(path, columns=None, limit=None)` | Read a partitioned Parquet directory |
| `extract_schema(path)` | Extract column names, types, nullability, and schema metadata |
| `extract_metadata(path)` | Extract row counts, row groups, compression, and partition info |

### WebIngestor

Handles web content.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_url(url)` | Scrape page |
| `crawl(url, depth)` | Recursive crawl |

### StreamIngestor

Handles real-time data.

**Methods:**

| Method | Description |
|--------|-------------|
| `consume(topic)` | Start consumption |

### RepoIngestor

Handles code repositories.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_repo(url)` | Clone and process |

### FeedIngestor

Handles RSS and Atom feeds.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_feed(url)` | Parse feed items |
| `monitor(url)` | Watch for updates |

### EmailIngestor

Handles IMAP and POP3 servers.

**Methods:**

| Method | Description |
|--------|-------------|
| `connect_imap(host)` | Connect to server |
| `ingest_mailbox(name)` | Fetch emails |

### DBIngestor

Handles SQL and NoSQL databases including Snowflake.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_database(conn)` | Export tables |
| `execute_query(sql)` | Run custom SQL |
| `connect_snowflake(account, user, password, warehouse)` | Connect to Snowflake |
| `ingest_snowflake_table(table_name)` | Ingest Snowflake table |
| `execute_snowflake_query(sql)` | Run Snowflake SQL |

**Supported Databases:**
- **PostgreSQL**, **MySQL**, **SQLite**
- **Microsoft SQL Server**, **Oracle**
- **Snowflake** (Cloud Data Warehouse)
- **MongoDB**, **Cassandra** (NoSQL)
- **BigQuery**, **Redshift** (Cloud Data Warehouses)

### MCPIngestor

Handles Model Context Protocol servers.

**Methods:**

| Method | Description |
|--------|-------------|
| `connect(url)` | Connect to server |
| `ingest_resources()` | Fetch resources |
| `call_tool(name)` | Execute tool |

---

## Convenience Functions

```python
from semantica.ingest import ingest

# Auto-detect source type
ingest("doc.pdf", source_type="file")
ingest("events.parquet")  # Auto-detects Parquet
ingest("https://google.com", source_type="web")
ingest("kafka://topic", source_type="stream")
```

### Parquet Dataset Ingestion

```python
from semantica.ingest import ParquetIngestor, ingest_parquet

ingestor = ParquetIngestor()

# Read selected columns from a local Parquet file
events = ingestor.ingest_file(
    "events.parquet",
    columns=["event_id", "event_type"],
    limit=1000,
)

# Inspect schema and metadata without reading rows
schema = ingestor.extract_schema("events.parquet")
metadata = ingestor.extract_metadata("events.parquet")

# Read a Hive-style partitioned directory such as country=US/year=2026/
partitioned = ingest_parquet("./warehouse/events", method="directory")
```

---

## Configuration

### Environment Variables

```bash
export INGEST_USER_AGENT="SemanticaBot/1.0"
export AWS_ACCESS_KEY_ID=...
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

### YAML Configuration

```yaml
ingest:
  web:
    user_agent: "MyBot"
    rate_limit: 1.0 # seconds

  files:
    max_size: 100MB
    allowed_extensions: [.pdf, .txt, .md]
```

---

## Integration Examples

### Continuous Feed Ingestion

```python
from semantica.ingest import FeedIngestor
from semantica.pipeline import Pipeline

# 1. Setup Monitor
ingestor = FeedIngestor()
pipeline = Pipeline()

def on_new_item(item):
    # 2. Trigger Pipeline on new content
    pipeline.run(item.content)

# 3. Start Monitoring
ingestor.monitor(
    "https://news.ycombinator.com/rss",
    callback=on_new_item,
    interval=300
)
```

### Snowflake Data Warehouse Integration

```python
from semantica.ingest import DBIngestor

# 1. Connect to Snowflake
ingestor = DBIngestor()
ingestor.connect_snowflake(
    account="your_account.snowflakecomputing.com",
    user="your_username",
    password="your_password",
    warehouse="ANALYTICS_WH",
    database="PRODUCTION_DB",
    schema="PUBLIC"
)

# 2. Ingest entire table
data = ingestor.ingest_snowflake_table("CUSTOMERS")

# 3. Or run custom query
results = ingestor.execute_snowflake_query("""
    SELECT
        CUSTOMER_ID,
        NAME,
        EMAIL,
        CREATED_AT
    FROM CUSTOMERS
    WHERE CREATED_AT > '2024-01-01'
""")

# 4. Process with pipeline
for row in results:
    pipeline.process(row)
```

!!! info "Comprehensive Snowflake Guide"
    For detailed Snowflake integration including authentication methods, advanced features, and best practices, see the **[Snowflake Integration Guide](../integrations/snowflake.md)**.

### Multi-Database Integration

```python
from semantica.ingest import DBIngestor

ingestor = DBIngestor()

# Connect to multiple databases
connections = {
    "snowflake": ingestor.connect_snowflake(...),
    "postgres": ingestor.connect_database("postgresql://..."),
    "mysql": ingestor.connect_database("mysql://...")
}

# Ingest from all sources
for name, conn in connections.items():
    data = ingestor.ingest_database(conn)
    print(f"Ingested {len(data)} records from {name}")
```

---

## Best Practices

1.  **Respect Rate Limits**: When crawling, always set a polite `rate_limit` to avoid getting banned.
2.  **Filter Content**: Use `allowed_extensions` or URL patterns to avoid ingesting junk data.
3.  **Handle Failures**: Stream ingestors should have error handlers for bad messages.
4.  **Use Credentials Securely**: Never hardcode API keys; use Environment Variables.

---

## See Also

- **[Snowflake Integration Guide](../integrations/snowflake.md)** - Comprehensive Snowflake integration with authentication, advanced features, and best practices
- [Parse Module](parse.md) - Processes the raw data ingested here
- [Split Module](split.md) - Chunks the ingested content
- [Utils Module](utils.md) - Validation helpers

## Cookbook

Interactive tutorials to learn data ingestion:

- **[Data Ingestion](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/02_Data_Ingestion.ipynb)**: Comprehensive guide to data ingestion from multiple sources
  - **Topics**: File ingestion, web scraping, database integration, streams, feeds, repositories, email, MCP
  - **Difficulty**: Beginner
  - **Use Cases**: Loading data from various sources, understanding ingestion capabilities

- **[Multi-Source Data Integration](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)**: Merge data from disparate sources into a unified graph
  - **Topics**: Entity resolution, merging, fusion, multi-source integration
  - **Difficulty**: Advanced
  - **Use Cases**: Combining data from multiple sources, data fusion

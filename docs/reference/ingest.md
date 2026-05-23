---
title: "Ingest Module"
description: "Universal data ingestion from files, Parquet, XML, web, feeds, streams, repositories, email, and databases."
icon: "database"
---

`semantica.ingest` is the entry point for loading data into Semantica. Every ingestor returns a list of `DataSource` objects with normalized content and metadata, regardless of the original format.

## What You Get

- **`FileIngestor`** — PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, ZIP/TAR archives
- **`ParquetIngestor`** — PyArrow-based Parquet with Hive-style partition support (v0.5.0)
- **`XMLIngestor`** — XXE-safe lxml with XSD/DTD validation (v0.5.0)
- **`WebIngestor`** — configurable web crawling with robots.txt support
- **`FeedIngestor`** — RSS/Atom feeds with live monitoring
- **`DBIngestor`** / **`SnowflakeIngestor`** — SQL databases and Snowflake
- **`StreamIngestor`** — Kafka, RabbitMQ, Kinesis, Pulsar real-time streams
- **`RepoIngestor`**, **`EmailIngestor`**, **`MCPIngestor`**, **`S3Ingestor`**, **`GCSIngestor`**

## FileIngestor

```python
from semantica.ingest import FileIngestor

ingestor = FileIngestor()

# Single file — type auto-detected from extension
sources = ingestor.ingest("data/report.pdf")

# Recursive directory scan
sources = ingestor.ingest_directory("data/", recursive=True)

# Glob pattern
sources = ingestor.ingest("data/**/*.docx")
```

Supported formats: PDF, DOCX, TXT, HTML, JSON, CSV, Excel (XLSX/XLS), PPTX, ZIP/TAR archives.

## ParquetIngestor (v0.5.0)

PyArrow-based ingestion for Apache Parquet files, including Hive-style partitioned datasets:

```python
from semantica.ingest import ParquetIngestor

ingestor = ParquetIngestor()

# Single Parquet file
sources = ingestor.ingest("data/events.parquet")

# Partitioned directory (year=2024/month=01/...)
sources = ingestor.ingest("data/partitioned/")

# Load only specific columns
sources = ingestor.ingest("data/events.parquet", columns=["id", "text", "timestamp"])
```

## XMLIngestor (v0.5.0)

XXE-safe lxml-based ingestion with optional schema validation:

```python
from semantica.ingest import XMLIngestor

# Basic ingestion
ingestor = XMLIngestor()
sources = ingestor.ingest("data/records.xml")

# With XSD validation
ingestor = XMLIngestor(validate_xsd="schema.xsd")
sources = ingestor.ingest("data/records/")

# With DTD validation
ingestor = XMLIngestor(validate_dtd=True)
sources = ingestor.ingest("data/feed.xml")
```

<Note>
  `XMLIngestor` uses lxml with `resolve_entities=False` to prevent XML External Entity (XXE) injection attacks.
</Note>

## WebIngestor

```python
from semantica.ingest import WebIngestor

ingestor = WebIngestor(
    rate_limit=1.0,       # seconds between requests
    respect_robots=True,  # honor robots.txt
    max_depth=2           # crawl depth from seed URLs
)

# Single URL
sources = ingestor.ingest("https://example.com/about")

# Multiple URLs
sources = ingestor.ingest_urls([
    "https://example.com/page1",
    "https://example.com/page2",
])
```

## FeedIngestor (RSS/Atom)

```python
from semantica.ingest import FeedIngestor

ingestor = FeedIngestor()
sources = ingestor.ingest("https://feeds.example.com/rss")

# Live monitoring — callback fires on new items
ingestor.monitor(
    "https://feeds.example.com/rss",
    interval=300,
    callback=process_new_items
)
```

## DBIngestor (SQL)

```python
from semantica.ingest import DBIngestor

ingestor = DBIngestor(
    connection_string="postgresql://user:pass@localhost/db",
    query="SELECT id, content, created_at FROM documents WHERE status='active'"
)
sources = ingestor.ingest()
```

## SnowflakeIngestor

```python
from semantica.ingest import SnowflakeIngestor
import os

ingestor = SnowflakeIngestor(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    warehouse="COMPUTE_WH",
    database="ANALYTICS",
    schema="PUBLIC"
)
sources = ingestor.ingest(query="SELECT * FROM documents")
```

## Other Ingestors

| Class | Source |
| ----- | ------ |
| `StreamIngestor` | Kafka, RabbitMQ, Kinesis, Pulsar |
| `RepoIngestor` | Git repositories (GitHub, GitLab) |
| `EmailIngestor` | IMAP/POP3 servers with attachment extraction |
| `MCPIngestor` | Model Context Protocol servers |
| `S3Ingestor` | AWS S3 buckets |
| `GCSIngestor` | Google Cloud Storage |
| `MongoIngestor` | MongoDB collections |
| `DuckDBIngestor` | DuckDB databases |
| `GDriveIngestor` | Google Drive |

## DataSource Object

All ingestors return a list of `DataSource` objects with a consistent schema:

```python
@dataclass
class DataSource:
    content:     str             # raw text content
    source_id:   str             # unique identifier
    source_type: str             # "file" | "web" | "database" | "stream" | ...
    metadata:    Dict            # title, author, url, date, page_count, etc.
    raw_bytes:   Optional[bytes] # original binary content if available
```

## Custom Ingestors

Register a custom ingestor and it participates in the full pipeline:

```python
from semantica.ingest.registry import method_registry

def my_ingestor(source, **kwargs):
    # Return a list of DataSource-compatible dicts
    return [{"content": "...", "metadata": {}, "source_id": source}]

method_registry.register("file", "my_format", my_ingestor)
```

<CardGroup cols={2}>
  <Card title="Parse" icon="file-lines" href="parse">
    Parse raw sources into structured text and tables.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Orchestrate ingest as the first pipeline step.
  </Card>
  <Card title="Snowflake Integration" icon="snowflake" href="../integrations/snowflake">
    Snowflake-specific setup and authentication guide.
  </Card>
  <Card title="Provenance" icon="link" href="provenance">
    Track lineage from ingest through to inference.
  </Card>
</CardGroup>

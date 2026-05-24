---
title: "Ingest Module"
description: "Universal data ingestion from files, Parquet, XML, web, feeds, streams, repositories, email, and databases."
icon: "database"
---

`semantica.ingest` is the entry point for loading data into Semantica. Every ingestor returns a list of `DataSource` objects with normalized content and metadata, regardless of the original format.

## Exported Classes

```python
from semantica.ingest import (
    # File ingestion (always available)
    FileIngestor,         # local files and directories: ingest(path, recursive=True)
    CloudStorageIngestor, # AWS S3, Google Cloud Storage, Azure Blob Storage
    FileObject,           # {content, source_id, source_type, metadata, raw_bytes}
    FileTypeDetector,     # auto-detect file type from extension and magic bytes
    ParquetIngestor,      # Apache Parquet files and partitioned datasets
    XMLIngestor,          # XXE-safe lxml XML parsing with optional XSD validation
    # Web ingestion (requires beautifulsoup4)
    WebIngestor,          # web scraping: ingest_url(url), crawl(url, max_pages)
    FeedIngestor,         # RSS/Atom feeds: ingest_feed(url), monitor_feeds(...)
    FeedMonitor,          # live feed monitoring with callback on new items
    # Stream ingestion
    StreamIngestor,       # real-time: ingest_kafka/rabbitmq/kinesis/pulsar
    KafkaProcessor,       # Kafka consumer group processor
    RabbitMQProcessor,    # AMQP queue processor
    KinesisProcessor,     # AWS Kinesis stream processor
    PulsarProcessor,      # Apache Pulsar consumer
    # Repository ingestion (requires gitpython)
    RepoIngestor,         # Git repos: ingest(url_or_path), include_commits=True
    # Email ingestion
    EmailIngestor,        # IMAP/POP3: ingest() with attachment extraction
    # Database ingestion
    DBIngestor,           # SQL: ingest_database(connection_string, include_tables)
    SnowflakeIngestor,    # Snowflake: ingest_query(sql), ingest_table(name)
    OntologyIngestor,     # OWL/RDF ontology files: ingest_ontology(path)
    # Convenience functions
    ingest,               # ingest(source, source_type="file") — unified dispatcher
    ingest_file,          # ingest_file(path, method="directory")
    ingest_web,           # ingest_web(url, method="url")
    ingest_feed,          # ingest_feed(url)
    ingest_stream,        # ingest_stream(topic, ...)
    ingest_database,      # ingest_database(connection_string, ...)
    ingest_parquet,       # ingest_parquet(path, columns=[...])
    ingest_xml,           # ingest_xml(path, validate_xsd=None)
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="FileIngestor" icon="file">
    PDF, DOCX, HTML, JSON, CSV, Excel, PPTX, and ZIP/TAR archives — type auto-detected from extension.
  </Card>
  <Card title="ParquetIngestor" icon="table">
    PyArrow-based Parquet with Hive-style partition support and column selection (v0.5.0).
  </Card>
  <Card title="XMLIngestor" icon="code">
    XXE-safe lxml with XSD/DTD validation and directory scanning (v0.5.0).
  </Card>
  <Card title="StreamIngestor" icon="wave-square">
    Real-time ingestion from Kafka, RabbitMQ, AWS Kinesis, and Apache Pulsar.
  </Card>
  <Card title="Cloud Storage" icon="cloud">
    `CloudStorageIngestor` — unified client for AWS S3, Google Cloud Storage, and Azure Blob Storage.
  </Card>
  <Card title="Database Ingestors" icon="database">
    `DBIngestor` (SQL via SQLAlchemy) and `SnowflakeIngestor` for data warehouse queries.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Ingest local files">
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
  </Step>
  <Step title="Connect to a remote source">
    ```python
    from semantica.ingest import DBIngestor

    ingestor = DBIngestor(
        connection_string="postgresql://user:pass@localhost/db",
        query="SELECT id, content, created_at FROM documents WHERE status='active'"
    )
    sources = ingestor.ingest()
    ```
  </Step>
  <Step title="Feed sources into the pipeline">
    ```python
    from semantica.pipeline import PipelineBuilder, ExecutionEngine
    from semantica.parse import DocumentParser
    from semantica.semantic_extract import NERExtractor
    from semantica.llms import Groq

    llm       = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    ingestor  = FileIngestor()
    parser    = DocumentParser()
    extractor = NERExtractor(method="llm", llm_provider=llm)

    builder = PipelineBuilder()
    builder.add_step("ingest",  "file_ingest",    handler=ingestor.ingest_file)
    builder.add_step("parse",   "document_parse", handler=parser.parse)
    builder.add_step("extract", "ner_extract",    handler=extractor.extract)
    builder.connect_steps("ingest", "parse")
    builder.connect_steps("parse",  "extract")

    pipeline = builder.build("my_pipeline")
    result   = ExecutionEngine().execute_pipeline(pipeline, data="data/")
    ```
  </Step>
</Steps>

## Ingestors

<Tabs>
  <Tab title="File-Based">
    ### FileIngestor

    ```python
    from semantica.ingest import FileIngestor

    ingestor = FileIngestor()
    sources  = ingestor.ingest("data/report.pdf")
    sources  = ingestor.ingest_directory("data/", recursive=True)
    sources  = ingestor.ingest("data/**/*.docx")
    ```

    Supported formats: PDF, DOCX, TXT, HTML, JSON, CSV, Excel (XLSX/XLS), PPTX, ZIP/TAR archives.

    ### ParquetIngestor (v0.5.0)

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

    ### XMLIngestor (v0.5.0)

    XXE-safe lxml-based ingestion with optional schema validation:

    ```python
    from semantica.ingest import XMLIngestor

    ingestor = XMLIngestor()
    sources  = ingestor.ingest("data/records.xml")

    # With XSD validation
    ingestor = XMLIngestor(validate_xsd="schema.xsd")
    sources  = ingestor.ingest("data/records/")

    # With DTD validation
    ingestor = XMLIngestor(validate_dtd=True)
    sources  = ingestor.ingest("data/feed.xml")
    ```

    <Note>
      `XMLIngestor` uses lxml with `resolve_entities=False` to prevent XML External Entity (XXE) injection attacks.
    </Note>
  </Tab>
  <Tab title="Web & Feed">
    ### WebIngestor

    ```python
    from semantica.ingest import WebIngestor

    ingestor = WebIngestor(
        delay=1.0,            # seconds between requests
        respect_robots=True,  # honor robots.txt
        timeout=30,
    )

    sources = ingestor.ingest_url("https://example.com/about")
    ```

    ### FeedIngestor (RSS/Atom)

    ```python
    from semantica.ingest import FeedIngestor

    ingestor = FeedIngestor()
    feed     = ingestor.ingest_feed("https://feeds.example.com/rss")

    # Live monitoring — returns a FeedMonitor; callback fires on new items
    monitor = ingestor.monitor_feeds(
        ["https://feeds.example.com/rss"],
        callback=process_new_items,
    )
    ```

    ### RepoIngestor

    Ingest Git repositories — source code, commit history, and dependency graphs:

    ```python
    from semantica.ingest import RepoIngestor

    ingestor = RepoIngestor(
        branch="main",
        file_types=[".py", ".md", ".yaml"],
        include_commits=True,
        commit_range="HEAD~100..HEAD",
    )

    sources = ingestor.ingest("https://github.com/org/repo")
    sources = ingestor.ingest("/path/to/local/repo")
    ```

    ### EmailIngestor

    Ingest emails via IMAP or POP3 with attachment extraction and thread analysis:

    ```python
    from semantica.ingest import EmailIngestor
    import os

    ingestor = EmailIngestor(
        protocol="imap",
        host="imap.gmail.com",
        port=993,
        use_ssl=True,
        username=os.getenv("EMAIL_USER"),
        password=os.getenv("EMAIL_PASS"),
        folder="INBOX",
        attachment_types=[".pdf", ".docx", ".txt"],
        include_thread_analysis=True,
        max_emails=500,
    )
    sources = ingestor.ingest()
    ```
  </Tab>
  <Tab title="Cloud Storage">
    ### CloudStorageIngestor

    `CloudStorageIngestor` is a unified client for AWS S3, Google Cloud Storage, and Azure Blob Storage:

    ```python
    from semantica.ingest import CloudStorageIngestor
    import os

    # AWS S3
    ingestor = CloudStorageIngestor(
        provider="s3",
        bucket="my-documents-bucket",
        prefix="reports/2024/",
        region="us-east-1",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        # Omit credentials to use IAM instance profile / environment variables
    )
    sources = ingestor.ingest()

    # Google Cloud Storage
    ingestor = CloudStorageIngestor(
        provider="gcs",
        bucket="my-gcs-bucket",
        prefix="data/",
        credentials_file="gcp-credentials.json",  # or use ADC
    )
    sources = ingestor.ingest()

    # Azure Blob Storage
    ingestor = CloudStorageIngestor(
        provider="azure",
        container="documents",
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
    )
    sources = ingestor.ingest()
    ```
  </Tab>
  <Tab title="Database">
    ### DBIngestor (SQL)

    ```python
    from semantica.ingest import DBIngestor

    ingestor = DBIngestor()
    result   = ingestor.ingest_database(
        connection_string="postgresql://user:pass@localhost/db",
        include_tables=["documents"],
    )
    ```

    ### SnowflakeIngestor

    ```python
    from semantica.ingest import SnowflakeIngestor
    import os

    ingestor = SnowflakeIngestor(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse="COMPUTE_WH",
        database="ANALYTICS",
        schema="PUBLIC",
    )
    result = ingestor.ingest_query("SELECT * FROM documents")
    result = ingestor.ingest_table("documents")
    ```

  </Tab>
  <Tab title="Stream">
    ### StreamIngestor

    Real-time ingestion from message brokers:

    ```python
    from semantica.ingest import StreamIngestor

    ingestor = StreamIngestor()

    # Kafka — returns KafkaProcessor
    processor = ingestor.ingest_kafka(
        topic="documents",
        bootstrap_servers=["localhost:9092"],
    )

    # RabbitMQ — returns RabbitMQProcessor
    processor = ingestor.ingest_rabbitmq(
        queue="document_queue",
        connection_url="amqp://guest:guest@localhost/",
    )

    # AWS Kinesis — returns KinesisProcessor
    processor = ingestor.ingest_kinesis(
        stream_name="documents-stream",
        region="us-east-1",
    )

    # Apache Pulsar — returns PulsarProcessor
    processor = ingestor.ingest_pulsar(
        topic="persistent://public/default/documents",
        service_url="pulsar://localhost:6650",
    )
    ```
  </Tab>
</Tabs>

## OntologyIngestor

Ingest existing OWL or RDF ontology files as structured knowledge sources:

```python
from semantica.ingest import OntologyIngestor

ingestor = OntologyIngestor()

ontology_data  = ingestor.ingest_ontology("domain_ontology.owl", format="turtle")
ontology_list  = ingestor.ingest_directory("ontologies/", recursive=True)
```

## FileObject

`FileIngestor` returns `FileObject` instances:

<Accordion title="FileObject schema">

```python
@dataclass
class FileObject:
    content:     str             # raw text content
    source_id:   str             # unique identifier
    source_type: str             # "file" | "web" | "database" | "stream" | ...
    metadata:    Dict            # title, author, url, date, page_count, etc.
    raw_bytes:   Optional[bytes] # original binary content if available
```

</Accordion>

## Custom Ingestors

Register a custom ingestor and it participates in the full pipeline:

```python
from semantica.ingest.registry import method_registry

def my_ingestor(source, **kwargs):
    return [{"content": "...", "metadata": {}, "source_id": source}]

method_registry.register("file", "my_format", my_ingestor)
```

## Tips and Common Pitfalls

<Tip>
  **`FileIngestor` is always the fastest path for local files.** It auto-detects format from extension, handles ZIP/TAR archives automatically, and supports glob patterns. Only reach for `DoclingParser` when `DocumentParser` can't handle your layout.
</Tip>

<Tip>
  **Use `ParquetIngestor` instead of `FileIngestor` for structured analytical data.** Parquet ingestion preserves column types (int, float, datetime) that CSV reading loses. Use `columns=["id", "text"]` to avoid loading unused columns — critical for wide tables with hundreds of columns.
</Tip>

<Warning>
  **`XMLIngestor` is XXE-safe by default.** Do not use standard `xml.etree.ElementTree` to pre-parse XML before passing to Semantica — it doesn't block XXE attacks. `XMLIngestor` uses lxml with `resolve_entities=False` to safely parse untrusted XML.
</Warning>

<Tip>
  **Rate-limit web crawling.** `WebIngestor(delay=1.0, respect_robots=True)` is the responsible default. Without rate limiting, you risk getting blocked by the target server or violating its terms of service.
</Tip>

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

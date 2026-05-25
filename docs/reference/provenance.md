---
title: "Provenance Module"
description: "W3C PROV-O compliant lineage tracking, source attribution, tamper-evident checksums, and audit trails across all modules."
icon: "link"
---

`semantica.provenance` tracks the full lineage of every fact — from raw ingestion through extraction, reasoning, and export. Compliant with W3C PROV-O, suitable for HIPAA, SOX, GDPR, and FDA 21 CFR Part 11 environments.

## Exported Classes

| Class | Role |
| --- | --- |
| `ProvenanceManager` | Track entities and get lineage: `track_entity`, `get_lineage`, `export_provenance` |
| `ProvenanceEntry` | Single record: `{entity_id, source, method, confidence, timestamp, checksum}` |
| `SourceReference` | Rich source pointer: `{url, doi, page, quote, author, publication_date}` |
| `InMemoryStorage` | Default backend — fast, not persisted across restarts |
| `SQLiteStorage` | Production backend — persists to a local SQLite file |
| `compute_checksum()` | Returns SHA-256 fingerprint of a provenance entry |
| `verify_checksum()` | Detects tampering by comparing stored vs recomputed hash |

## ProvenanceManager

```python
from semantica.provenance import ProvenanceManager, InMemoryStorage, SQLiteStorage

# In-memory (default) — fast, not persisted across restarts
manager = ProvenanceManager(storage=InMemoryStorage())

# SQLite — persisted, production-ready
manager = ProvenanceManager(storage=SQLiteStorage("provenance.db"))

# Track an extracted entity (with rich source reference)
manager.track_entity(
    entity_id="apple_inc",
    source="annual_report_2023.pdf",
    source_location="Page 12, Section 3.1",
    source_quote="Apple Inc. was incorporated on January 3, 1977.",
    confidence=0.98,
)

# Track an extracted relationship
manager.track_entity(
    entity_id="steve_jobs_founded_apple",
    source="annual_report_2023.pdf",
    confidence=0.92,
)

# Retrieve full lineage for any entity
entry = manager.get_lineage("apple_inc")
print(f"Source:     {entry.source}")
print(f"Quote:      {entry.source_quote}")
print(f"Confidence: {entry.confidence}")
print(f"Tracked at: {entry.tracked_at}")
```

## SourceReference

`SourceReference` provides a rich, citable pointer to the exact location in a source document:

```python
from semantica.provenance import SourceReference

ref = SourceReference(
    document_id="annual_report_2023.pdf",
    page=12,
    section="3.1",
    quote="Apple Inc. was incorporated on January 3, 1977.",
    url="https://investor.apple.com/sec-filings/annual-reports/",
    doi="10.0000/example.doi",
)

manager.track_entity(
    entity_id="apple_inc",
    source_reference=ref,
    confidence=0.98,
)
```

## ProvenanceManager Methods

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `track_entity(entity_id, source_reference, confidence)` | `str` | Record a provenance entry, returns entry ID |
| `get_lineage(entity_id)` | `ProvenanceEntry` | Retrieve full lineage for an entity |
| `export_prov_o(entity_id, format)` | `str` | Export single entity as W3C PROV-O Turtle/JSON-LD |
| `export_all(path, format)` | `None` | Export full provenance graph to file |
| `verify_checksum(entry, checksum)` | `bool` | Verify entry hasn't been tampered with |

## Tamper-Evident Checksums

Verify that provenance records have not been modified after creation:

```python
from semantica.provenance import compute_checksum, verify_checksum

entry = manager.get_lineage("apple_inc")

# Compute and store a checksum on first write
checksum = compute_checksum(entry)

# Later: verify the entry hasn’t been altered
is_valid = verify_checksum(entry, checksum)
if not is_valid:
    raise RuntimeError("Provenance record has been tampered with!")
```

## W3C PROV-O Export

Export lineage as W3C PROV-O Turtle for compliance reporting:

```python
# Single entity lineage
prov_ttl = manager.export_prov_o("apple_inc", format="turtle")

# Full provenance graph for all tracked entities
manager.export_all(path="provenance.ttl", format="turtle")

# Compliance-ready JSON-LD export
manager.export_all(path="provenance.jsonld", format="json-ld")
```

## Integration with GraphBuilder

`GraphBuilderWithProvenance` (from `semantica.kg`) automatically records provenance for every node and edge constructed:

```python
from semantica.kg import GraphBuilderWithProvenance
from semantica.provenance import ProvenanceManager, SQLiteStorage

prov_manager = ProvenanceManager(storage=SQLiteStorage("provenance.db"))
builder      = GraphBuilderWithProvenance(provenance_manager=prov_manager)
kg           = builder.build_single_source(graph_data)

# Every node and edge now has full source attribution
entry = prov_manager.get_lineage("apple_inc")
print(f"Source document: {entry.source}")
print(f"Confidence:      {entry.confidence}")
```

## Enable Provenance in Extractors

```python
from semantica.semantic_extract import NERExtractor
from semantica.provenance import ProvenanceManager

prov_manager = ProvenanceManager()

ner      = NERExtractor(method="llm", llm_provider=llm, provenance=True)
entities = ner.extract(text)

# Retrieve lineage for the first extracted entity
entry = prov_manager.get_lineage(entities[0]["id"])
print(f"Source: {entry.source}")
```

## Compliance Standards

Provenance tracking in Semantica is designed to satisfy:

| Standard | Requirement Met |
| -------- | --------------- |
| **W3C PROV-O** | Full PROV-O compliant serialization (Turtle and JSON-LD) |
| **HIPAA** | Complete audit trail linking clinical facts to source documents |
| **SOX** | Immutable change history with timestamps and actor IDs |
| **GDPR** | Data lineage supporting right-to-erasure impact analysis |
| **FDA 21 CFR Part 11** | Electronic records with origination timestamp and extraction method |

<CardGroup cols={2}>
  <Card title="Change Management" icon="clock-rotate-left" href="change_management">
    Version control and snapshot audit trails.
  </Card>
  <Card title="Ingest" icon="database" href="ingest">
    Provenance begins at the ingestion stage.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Include provenance metadata in RDF exports.
  </Card>
  <Card title="Context" icon="brain" href="context">
    Decision provenance via AgentContext.
  </Card>
</CardGroup>

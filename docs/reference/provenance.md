---
title: "Provenance Module"
description: "W3C PROV-O compliant lineage tracking, source attribution, and audit trails across all modules."
icon: "link"
---

`semantica.provenance` tracks the full lineage of every fact — from raw ingestion through extraction, reasoning, and export. Compliant with W3C PROV-O, suitable for HIPAA, SOX, GDPR, and FDA 21 CFR Part 11 environments.

## What You Get

<CardGroup cols={2}>
  <Card title="ProvenanceManager" icon="link">
    Track entities, relationships, and activities with full source attribution and confidence scores.
  </Card>
  <Card title="ProvenanceTracker" icon="clock">
    Track entity and relationship lineage within a knowledge graph.
  </Card>
  <Card title="Lineage Graph" icon="diagram-project">
    Full directed lineage from any entity back to its originating source document.
  </Card>
  <Card title="W3C PROV-O Export" icon="file-export">
    Serialize lineage as Turtle RDF or JSON-LD for compliance reporting.
  </Card>
  <Card title="GraphBuilderWithProvenance" icon="hammer">
    Drop-in replacement for GraphBuilder that auto-tracks every node and edge.
  </Card>
  <Card title="Integrity Verification" icon="shield-check">
    SHA-256 checksums to detect tampering in HIPAA and FDA 21 CFR Part 11 environments.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Initialize ProvenanceManager with a storage backend">
    ```python
    from semantica.provenance import ProvenanceManager, SQLiteStorage

    # SQLite — persistent across process restarts (recommended for production)
    manager = ProvenanceManager(
        storage=SQLiteStorage(db_path="provenance.db")
    )
    ```
  </Step>
  <Step title="Track entities and relationships at ingestion time">
    ```python
    manager.track_entity(
        entity_id="apple_inc",
        source="annual_report_2023.pdf",
        entity_type="Organization",
        extraction_method="llm",
        confidence=0.98,
    )

    manager.track_relationship(
        rel_id="steve_jobs_founded_apple",
        source="annual_report_2023.pdf",
        extraction_method="llm",
        confidence=0.92,
    )
    ```
  </Step>
  <Step title="Query lineage for any entity">
    ```python
    lineage = manager.get_lineage("apple_inc")
    print(f"Source:     {lineage.source}")
    print(f"Extracted:  {lineage.extracted_at}")
    print(f"Method:     {lineage.extraction_method}")
    print(f"Confidence: {lineage.confidence}")
    ```
  </Step>
  <Step title="Export PROV-O for compliance reporting">
    ```python
    # Full provenance graph for all tracked entities
    manager.export_all(path="provenance.ttl",    format="turtle")
    manager.export_all(path="provenance.jsonld", format="json-ld")
    ```
  </Step>
</Steps>

## ProvenanceManager

```python
from semantica.provenance import ProvenanceManager

manager = ProvenanceManager()

# Track an extracted entity
manager.track_entity(
    entity_id="apple_inc",
    source="annual_report_2023.pdf",
    entity_type="Organization",
    extraction_method="llm",
    confidence=0.98,
)

# Track an extracted relationship
manager.track_relationship(
    rel_id="steve_jobs_founded_apple",
    source="annual_report_2023.pdf",
    extraction_method="llm",
    confidence=0.92,
)

# Retrieve full lineage for any entity
lineage = manager.get_lineage("apple_inc")
print(f"Source:      {lineage.source}")
print(f"Extracted:   {lineage.extracted_at}")
print(f"Method:      {lineage.extraction_method}")
print(f"Confidence:  {lineage.confidence}")
```

## Activity Tracking

Record pipeline activities — what was consumed and what was produced:

```python
# Start and end an activity
activity_id = manager.start_activity(
    activity_type="ner_extraction",
    used=["annual_report_2023.pdf"],
    generated=["apple_inc", "steve_jobs"],
)

manager.end_activity(activity_id)

# Query activities for an entity
activities = manager.get_activities(entity_id="apple_inc")
for activity in activities:
    print(f"{activity.type} at {activity.started_at}")
    print(f"  Used:      {activity.used}")
    print(f"  Generated: {activity.generated}")
```

## Lineage Graph

Retrieve a full directed lineage graph from any entity back to its source:

```python
lineage_graph = manager.get_lineage_graph("apple_inc")

for node in lineage_graph.nodes:
    print(f"{node.id}: {node.type} — {node.timestamp}")

for edge in lineage_graph.edges:
    print(f"{edge.source} → {edge.target} ({edge.relation})")
```

## Storage Backends

<Tabs>
  <Tab title="InMemoryStorage (development)">
    Fast, no persistence — default backend. Data is lost on process exit.

    ```python
    from semantica.provenance import ProvenanceManager, InMemoryStorage

    manager = ProvenanceManager(storage=InMemoryStorage())

    manager.track_entity("apple_inc", source="report.pdf", confidence=0.98)
    lineage = manager.get_lineage("apple_inc")
    ```

    Best for: development, unit tests, short-lived pipelines.
  </Tab>
  <Tab title="SQLiteStorage (production)">
    Persistent file-based storage — survives process restarts. The API is identical to `InMemoryStorage`.

    ```python
    from semantica.provenance import ProvenanceManager, SQLiteStorage

    manager = ProvenanceManager(
        storage=SQLiteStorage(db_path="provenance.db")
    )

    manager.track_entity("apple_inc", source="report.pdf", confidence=0.98)
    lineage = manager.get_lineage("apple_inc")
    ```

    Best for: production single-machine deployments, compliance environments.
  </Tab>
  <Tab title="Comparison">

    | Storage | Persistence | Best For |
    | ------- | ----------- | -------- |
    | `InMemoryStorage` | No | Development, unit tests, short-lived pipelines |
    | `SQLiteStorage` | Yes (file) | Production single-machine deployments |

  </Tab>
</Tabs>

## Integration with GraphBuilder

`GraphBuilderWithProvenance` automatically records provenance for every node and edge constructed — no manual `track_entity()` calls needed:

```python
from semantica.kg import GraphBuilderWithProvenance

builder = GraphBuilderWithProvenance(provenance=True)
result  = builder.build_single_source(graph_data)

# Every node and edge has a source_id linking back to the originating document
lineage = result.provenance_manager.get_lineage("apple_inc")
print(f"Source document: {lineage.source}")
print(f"Extracted by:    {lineage.extraction_method}")
```

## Integrity Verification

Compute and verify checksums for provenance entries to detect tampering:

```python
from semantica.provenance import compute_checksum, verify_checksum

# Compute a SHA-256 checksum over an entity's provenance record
entry    = manager.get_provenance_entry("apple_inc")
checksum = compute_checksum(entry, algorithm="sha256")
print(f"Checksum: {checksum}")

# Later — verify the record has not been modified
is_valid = verify_checksum(entry, expected_checksum=checksum, algorithm="sha256")
if not is_valid:
    raise RuntimeError("Provenance record has been tampered with!")
```

Supported algorithms: `"sha256"` (default), `"sha512"`, `"md5"`.

## W3C PROV-O Export

```python
# Single entity lineage
prov_ttl = manager.export_prov_o("apple_inc", format="turtle")

# Full provenance graph for all tracked entities
manager.export_all(path="provenance.ttl",    format="turtle")
manager.export_all(path="provenance.jsonld", format="json-ld")
```

## Schemas

<AccordionGroup>
  <Accordion title="ProvenanceEntry schema">

```python
@dataclass
class ProvenanceEntry:
    entity_id:         str
    source:            str            # source document or system
    source_location:   str            # e.g. "page 3, paragraph 2"
    source_quote:      str            # verbatim text from source
    extraction_method: str            # "llm" | "ml" | "pattern"
    confidence:        float          # extraction confidence 0–1
    timestamp:         datetime       # when this entry was recorded
    entity_type:       Optional[str]
```

  </Accordion>
  <Accordion title="SourceReference schema">

```python
@dataclass
class SourceReference:
    source_id:   str
    doi:         Optional[str]      # academic DOI if available
    page:        Optional[int]      # page number in document
    paragraph:   Optional[int]
    quote:       str                # verbatim text supporting the fact
    url:         Optional[str]
    accessed_at: Optional[datetime]
```

  </Accordion>
</AccordionGroup>

## W3C PROV-O Mapping

| Semantica Concept | PROV-O Class / Property |
| ----------------- | ----------------------- |
| Entity (node/fact) | `prov:Entity` |
| Extraction activity | `prov:Activity` |
| Source document | `prov:Entity` |
| `track_entity()` | `prov:wasDerivedFrom` |
| `start_activity()` | `prov:wasGeneratedBy` |
| Extraction method | `prov:wasAssociatedWith` |
| Timestamp | `prov:startedAtTime`, `prov:endedAtTime` |

## Compliance Standards

| Standard | Requirement Met |
| -------- | --------------- |
| **W3C PROV-O** | Full PROV-O compliant serialization (Turtle and JSON-LD) |
| **HIPAA** | Complete audit trail linking clinical facts to source documents |
| **SOX** | Immutable change history with timestamps and actor IDs |
| **GDPR** | Data lineage supporting right-to-erasure impact analysis |
| **FDA 21 CFR Part 11** | Electronic records with origination timestamp and extraction method |

## Tips and Common Pitfalls

<Warning>
  **Use `SQLiteStorage` in production, not `InMemoryStorage`.** The in-memory backend is the default for backwards compatibility, but provenance data is lost on process exit. Switch to `SQLiteStorage(db_path="provenance.db")` before going to production — migrating later means losing all historical lineage.
</Warning>

<Warning>
  **Track provenance at ingestion time, not after.** The `source_location` and `source_quote` fields become unavailable once you've moved past the parsing stage. Capture them during ingestion and pass them to `track_entity()` immediately.
</Warning>

<Tip>
  **Use `GraphBuilderWithProvenance` instead of plain `GraphBuilder`.** It auto-tracks every node and edge without manual `track_entity()` calls — ensuring nothing is accidentally omitted from the provenance record.
</Tip>

<Tip>
  **Verify checksums on high-stakes data.** `compute_checksum()` + `verify_checksum()` detects any modification to a provenance entry since it was recorded — critical for HIPAA and FDA 21 CFR Part 11 environments where tampered records carry legal liability.
</Tip>

<Tip>
  **Export PROV-O Turtle for external auditors.** Compliance teams and external auditors often need machine-readable lineage in a standard format. `manager.export_all("provenance.ttl", format="turtle")` produces W3C PROV-O Turtle that any RDF tool can parse.
</Tip>

<Tip>
  **Use `get_audit_trail(entity_id=...)` for GDPR subject-access requests.** The GDPR right-of-access requires you to show what personal data you hold and where it came from. Scoped lineage per entity ID makes this a one-line export.
</Tip>

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

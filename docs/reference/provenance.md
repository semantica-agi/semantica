---
title: "Provenance Module"
description: "W3C PROV-O compliant lineage tracking, source attribution, and audit trails across all modules."
icon: "link"
---

`semantica.provenance` tracks the full lineage of every fact — from raw ingestion through extraction, reasoning, and export. Compliant with W3C PROV-O, suitable for HIPAA, SOX, GDPR, and FDA 21 CFR Part 11 environments.

## What You Get

- **`ProvenanceManager`** — track entities, relationships, and activities with source attribution
- **`ActivityTracker`** — record pipeline activities and which entities they produced or consumed
- **Lineage graph** — full upstream lineage from any entity back to its source document
- **W3C PROV-O export** — serialize lineage as Turtle RDF for compliance reporting
- **`GraphBuilderWithProvenance`** — drop-in replacement that auto-tracks every node and edge

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
    confidence=0.98
)

# Track an extracted relationship
manager.track_relationship(
    rel_id="steve_jobs_founded_apple",
    source="annual_report_2023.pdf",
    extraction_method="llm",
    confidence=0.92
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
    generated=["apple_inc", "steve_jobs"]
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

`GraphBuilderWithProvenance` automatically records provenance for every node and edge constructed:

```python
from semantica.kg import GraphBuilderWithProvenance

builder = GraphBuilderWithProvenance(provenance=True)
result  = builder.build_single_source(graph_data)

# Each node and edge has a source_id linking back to the originating document
lineage = result.provenance_manager.get_lineage("apple_inc")
print(f"Source document: {lineage.source}")
print(f"Extracted by:    {lineage.extraction_method}")
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

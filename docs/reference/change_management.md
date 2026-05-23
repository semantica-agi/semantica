---
title: "Change Management Module"
description: "Version control, SHA-256 checksums, diff analysis, rollback, and audit trails for knowledge graphs and ontologies."
icon: "clock-rotate-left"
---

`semantica.change_management` provides enterprise-grade versioning and audit trails for knowledge graphs and ontologies — SHA-256 checksums, snapshot history, diff analysis, rollback protection, and compliance-ready audit export (HIPAA, SOX, FDA 21 CFR Part 11).

## What You Get

- **`TemporalVersionManager`** — snapshot, diff, rollback, and audit trail for knowledge graphs
- **`OntologyVersionManager`** — version control for OWL ontologies with diff and migration support
- **`VersionStorage`** — pluggable storage: `InMemoryVersionStorage` for tests, `SQLiteVersionStorage` for production
- **`compute_checksum` / `verify_checksum`** — SHA-256 integrity verification
- **`ChangeLogEntry`** — structured record of every change in a snapshot

## TemporalVersionManager

Version control for knowledge graphs — snapshot, diff, and rollback:

```python
from semantica.change_management import TemporalVersionManager

manager = TemporalVersionManager(storage_path="versions.db")

# Create a snapshot
snapshot_id = manager.create_snapshot(
    graph=kg,
    version="v1.0",
    author="user@example.com",
    message="Initial knowledge graph"
)

print(f"Snapshot: {snapshot_id}")
print(f"Checksum: {manager.get_checksum(snapshot_id)}")
```

### List, Retrieve, and Rollback

```python
# List all versions
versions = manager.list_versions()
for v in versions:
    print(f"{v.version} — {v.author} — {v.created_at} — {v.checksum[:8]}...")

# Retrieve a specific version
kg_v1 = manager.get_version("v1.0")

# Rollback to a previous version (safe by default — fails if data would be lost)
manager.rollback(target_version="v1.0", allow_data_loss=False)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `storage_path` | `str` | `None` | Path to SQLite database; uses in-memory if omitted |
| `storage` | `VersionStorage` | `None` | Explicit storage backend instance |

## Diff Analysis

Compare any two snapshots to see exactly what changed:

```python
diff = manager.diff("v1.0", "v2.0")

print(f"Added nodes:    {len(diff.added_nodes)}")
print(f"Removed nodes:  {len(diff.removed_nodes)}")
print(f"Modified edges: {len(diff.modified_edges)}")

for change in diff.changes:
    print(f"  [{change.type}] {change.element}: {change.description}")
```

## OntologyVersionManager

Version control for OWL ontologies — save, diff, and track schema migrations:

```python
from semantica.change_management import OntologyVersionManager, OntologyVersion

manager = OntologyVersionManager()

# Save a version
version: OntologyVersion = manager.save_version(
    ontology=ontology,
    version="1.2.0",
    author="ontology-team",
    message="Added FHIR alignment mappings"
)

# Diff two ontology versions
diff = manager.diff("1.1.0", "1.2.0")
for change in diff.changes:
    print(f"[{change.type}] {change.class_name}: {change.description}")
```

## VersionStorage Backends

```python
from semantica.change_management import (
    InMemoryVersionStorage,
    SQLiteVersionStorage,
)

# In-memory — for tests and development (data not persisted)
storage = InMemoryVersionStorage()

# SQLite — for production (persistent across restarts)
storage = SQLiteVersionStorage(db_path="versions.db")

# Pass to a version manager
manager = TemporalVersionManager(storage=storage)
```

## Integrity Verification

SHA-256 checksums detect any unauthorized modification to a graph between snapshots:

```python
from semantica.change_management import compute_checksum, verify_checksum

# Compute checksum for a graph
checksum = compute_checksum(kg)

# Verify graph against a stored checksum
is_valid = verify_checksum(kg, expected_checksum=checksum)

if not is_valid:
    raise RuntimeError("Graph has been modified since the checksum was recorded")
```

## Audit Trail

Full per-entity audit trail with CSV and JSON export for compliance reporting:

```python
# Get all changes for a specific entity
trail = manager.get_audit_trail(entity_id="apple_inc")
for entry in trail:
    print(f"{entry.timestamp} — {entry.author}: {entry.action} — {entry.description}")

# Export audit trail for compliance
manager.export_audit_trail("audit.csv",  format="csv")
manager.export_audit_trail("audit.json", format="json")
```

## ChangeLogEntry

Every version snapshot includes a structured `ChangeLogEntry`:

```python
from semantica.change_management import ChangeLogEntry

entry: ChangeLogEntry = manager.get_log_entry(snapshot_id)

print(entry.version)      # "v1.0"
print(entry.author)       # "user@example.com"
print(entry.message)      # "Initial knowledge graph"
print(entry.checksum)     # SHA-256 hex digest
print(entry.created_at)   # datetime
print(entry.changes)      # list of individual change records
```

<CardGroup cols={2}>
  <Card title="Provenance" icon="link" href="provenance">
    W3C PROV-O lineage tracking.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The graph being versioned.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Export versioned snapshots.
  </Card>
  <Card title="Conflicts" icon="triangle-exclamation" href="conflicts">
    Detect conflicts introduced between versions.
  </Card>
</CardGroup>

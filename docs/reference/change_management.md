---
title: "Change Management Module"
description: "Version control, SHA-256 checksums, diff analysis, rollback, and audit trails for knowledge graphs and ontologies."
icon: "clock-rotate-left"
---

`semantica.change_management` provides enterprise-grade versioning and audit trails for knowledge graphs and ontologies. Every snapshot carries a SHA-256 checksum, every modification is logged, and every state can be diffed or rolled back — giving you a complete, tamper-evident record suitable for regulated industries.

<Note>
  Compliance frameworks supported out of the box: **HIPAA**, **SOX**, **GDPR**, and **FDA 21 CFR Part 11**.
</Note>

## Exported Classes

| Class | Role |
| --- | --- |
| `TemporalVersionManager` | Snapshot, diff, rollback, and per-entity audit trail for temporal KGs |
| `OntologyVersionManager` | Schema versioning with backward-compatible migration support |
| `InMemoryVersionStorage` | Fast in-memory storage for dev and testing — no persistence |
| `SQLiteVersionStorage` | Production storage — persists to a local SQLite file |
| `compute_checksum()` | Returns SHA-256 fingerprint of a graph or ontology state |
| `verify_checksum()` | Detects tampering by comparing stored vs recomputed checksum |

## What You Get

<CardGroup cols={2}>
  <Card title="TemporalVersionManager" icon="code-branch">
    Snapshot, diff, rollback, and per-entity audit trail for knowledge graphs.
  </Card>
  <Card title="OntologyVersionManager" icon="sitemap">
    Version control for OWL ontologies with diff and schema migration support.
  </Card>
  <Card title="VersionStorage" icon="database">
    Pluggable backends — `InMemoryVersionStorage` for tests, `SQLiteVersionStorage` for production.
  </Card>
  <Card title="Integrity Verification" icon="shield-check">
    SHA-256 / SHA-512 checksums to detect any unauthorised graph modification.
  </Card>
  <Card title="ChangeLogEntry" icon="list-check">
    Structured record of every change: author, timestamp, checksum, and change list.
  </Card>
  <Card title="Version History" icon="file-shield">
    Full tamper-evident version history via `list_versions()` and `diff()` for regulatory review.
  </Card>
</CardGroup>

## Typical Workflow

<Steps>
  <Step title="Initialise the version manager">
    ```python
    from semantica.change_management import TemporalVersionManager

    manager = TemporalVersionManager(storage_path="versions.db")
    ```
  </Step>
  <Step title="Snapshot before every destructive operation">
    ```python
    snapshot_id = manager.create_snapshot(
        graph=kg,
        version="v1.0",
        author="user@example.com",
        message="Before deduplication run"
    )
    print(f"Snapshot: {snapshot_id}")
    print(f"Checksum: {manager.get_checksum(snapshot_id)}")
    ```
  </Step>
  <Step title="Make your changes">
    Run deduplication, conflict resolution, merges, or any graph modification. The version manager tracks nothing automatically — you control when snapshots are taken.
  </Step>
  <Step title="Snapshot the result">
    ```python
    snapshot_v2 = manager.create_snapshot(
        graph=kg,
        version="v2.0",
        author="user@example.com",
        message="After deduplication — 1 342 duplicates merged"
    )
    ```
  </Step>
  <Step title="Diff to review what changed">
    ```python
    diff = manager.diff("v1.0", "v2.0")
    print(diff.summary)

    for change in diff.changes:
        print(f"  [{change.type}] {change.element}: {change.description}")
    ```
  </Step>
</Steps>

## TemporalVersionManager

Version control for knowledge graphs — snapshot, diff, and rollback.

### Constructor Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `storage_path` | `str` | `None` | Path to SQLite database; uses in-memory if omitted |
| `storage` | `VersionStorage` | `None` | Explicit storage backend instance — overrides `storage_path` |

### List and Retrieve

```python
# List all versions
versions = manager.list_versions()
for v in versions:
    print(f"{v.version} — {v.author} — {v.created_at} — {v.checksum[:8]}...")

# Retrieve a specific version
kg_v1 = manager.get_version("v1.0")
```

## Diff Analysis

Compare any two snapshots to see exactly what changed — useful for code review, incident investigation, and regulatory audit:

```python
diff = manager.diff("v1.0", "v2.0")

print(f"Added nodes:    {len(diff.added_nodes)}")
print(f"Removed nodes:  {len(diff.removed_nodes)}")
print(f"Modified nodes: {len(diff.modified_nodes)}")
print(f"Added edges:    {len(diff.added_edges)}")
print(f"Removed edges:  {len(diff.removed_edges)}")
print(f"Modified edges: {len(diff.modified_edges)}")

for change in diff.changes:
    print(f"  [{change.type}] {change.element}: {change.description}")
```

<Accordion title="DiffResult schema">

```python
@dataclass
class DiffResult:
    from_version:   str                # source snapshot ID
    to_version:     str                # target snapshot ID
    added_nodes:    List[str]          # IDs of newly added entities
    removed_nodes:  List[str]          # IDs of deleted entities
    modified_nodes: List[str]          # IDs of entities with changed properties
    added_edges:    List[str]          # IDs of newly added relationships
    removed_edges:  List[str]          # IDs of deleted relationships
    modified_edges: List[str]          # IDs of relationships with changed properties
    changes:        List[ChangeRecord] # ordered list of all individual changes
    summary:        str                # human-readable summary line
```

</Accordion>

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

<Tabs>
  <Tab title="SQLite (production)">
    ```python
    from semantica.change_management import SQLiteVersionStorage, TemporalVersionManager

    storage = SQLiteVersionStorage(db_path="versions.db")
    manager = TemporalVersionManager(storage=storage)
    ```

    Persists all version history to disk. Survives process restarts. Recommended for any environment where you need to retain the audit trail.

    You can also pass the path directly to `TemporalVersionManager`:

    ```python
    manager = TemporalVersionManager(storage_path="versions.db")
    ```
  </Tab>
  <Tab title="In-Memory (tests)">
    ```python
    from semantica.change_management import InMemoryVersionStorage, TemporalVersionManager

    storage = InMemoryVersionStorage()
    manager = TemporalVersionManager(storage=storage)
    ```

    Fast and zero-setup. Data is **not persisted** — all version history is lost when the process exits. Use this for unit tests and development only.
  </Tab>
</Tabs>

<Warning>
  The default `TemporalVersionManager()` with no arguments uses in-memory storage. Always pass `storage_path="versions.db"` or an explicit `SQLiteVersionStorage` in production — otherwise your entire version history disappears on restart.
</Warning>

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

<Tip>
  `verify_checksum` is deterministic — the same graph always produces the same digest. Use it as a pre-flight check before any compliance export to confirm the graph hasn't been tampered with since the last snapshot.
</Tip>

## ChangeLogEntry

Every version snapshot includes a structured `ChangeLogEntry` that records the full context of a change:

```python
# Retrieve a version entry
entry = manager.get_version("v1.0")

print(entry.version)      # "v1.0"
print(entry.author)       # "user@example.com"
print(entry.message)      # "Initial knowledge graph"
print(entry.checksum)     # SHA-256 hex digest of the full graph state
print(entry.created_at)   # datetime of snapshot creation
print(entry.node_count)   # total nodes at this snapshot
print(entry.edge_count)   # total edges at this snapshot
print(entry.changes)      # list[ChangeRecord] — individual property-level changes
```

<Accordion title="ChangeLogEntry schema">

```python
@dataclass
class ChangeLogEntry:
    snapshot_id: str                # unique snapshot identifier
    version:     str                # human-assigned version tag, e.g. "v1.0"
    author:      str                # identity of the user or process that created it
    message:     str                # commit-style description of what changed
    checksum:    str                # SHA-256 hex digest — changes if graph is tampered
    created_at:  datetime           # UTC timestamp of snapshot creation
    node_count:  int                # total entity count at this point in time
    edge_count:  int                # total relationship count at this point in time
    changes:     List[ChangeRecord] # granular per-property change records
    metadata:    Dict               # arbitrary key-value pairs for custom tagging
```

</Accordion>

## Compliance and Version History

All version snapshots form a tamper-evident audit trail. Use `list_versions()` and `diff()` to reconstruct and review changes for regulatory purposes:

```python
from semantica.change_management import TemporalVersionManager

manager = TemporalVersionManager(storage_path="versions.db")

# Enumerate the full version history
for entry in manager.list_versions():
    print(f"{entry.created_at.isoformat()} | {entry.author} | {entry.version} | {entry.message}")

# Diff any two snapshots for a change report
diff = manager.diff("v1.0", "v2.0")
print(f"Added: {len(diff.added_nodes)} | Removed: {len(diff.removed_nodes)} | Modified: {len(diff.modified_nodes)}")
for change in diff.changes:
    print(f"  [{change.type}] {change.element}: {change.description}")
```

Use `verify_checksum()` before any compliance export to confirm graph integrity:

```python
from semantica.change_management import verify_checksum

is_valid = verify_checksum(kg, expected_checksum=entry.checksum)
if not is_valid:
    raise RuntimeError("Graph has been modified since the snapshot was taken")
```

### Compliance Coverage

<AccordionGroup>
  <Accordion title="HIPAA — subject-access requests">
    Use `get_audit_trail(entity_id="patient_001")` to retrieve every change ever made to a patient entity, then export to JSON for the access request response. The SHA-256 checksum on each entry proves the record has not been altered.
  </Accordion>
  <Accordion title="SOX — quarterly reviews">
    Use `get_audit_trail(from_date=..., to_date=...)` to scope the export to the relevant quarter. Export to CSV for upload to your audit management system. The immutable snapshot chain provides the chain of custody required by SOX Section 404.
  </Accordion>
  <Accordion title="GDPR — right to erasure verification">
    After deleting a data subject's entities, snapshot the graph and diff against the pre-deletion snapshot. `diff.removed_nodes` provides a machine-readable record of exactly what was deleted and when, satisfying Article 17 documentation requirements.
  </Accordion>
  <Accordion title="FDA 21 CFR Part 11 — electronic records">
    Every `ChangeLogEntry` includes `author`, `timestamp`, and `checksum` — the three fields required for a compliant electronic record. `verify_checksum()` provides the tamper-evidence required by 21 CFR § 11.10(e).
  </Accordion>
</AccordionGroup>

## Tips and Common Pitfalls

<Tip>
  **Use `SQLiteVersionStorage` in production.** The default in-memory storage loses all version history when the process exits. Pass `storage_path="versions.db"` to `TemporalVersionManager` or create `SQLiteVersionStorage(db_path="versions.db")` explicitly.
</Tip>

<Warning>
  **Snapshot before every destructive operation.** Call `manager.create_snapshot()` before running deduplication, conflict resolution, or merge operations. `rollback()` is only possible if a snapshot exists before the change.
</Warning>

<Tip>
  **Use `diff()` for code review and incident investigation.** `manager.diff("v1.0", "v2.0")` produces a human-readable change summary in seconds — faster than comparing raw graph exports. Use it to review what changed before approving a version for production.
</Tip>

<Tip>
  **Use `list_versions()` and `diff()` for compliance reviews.** `manager.list_versions()` enumerates the full version history and `manager.diff(v1, v2)` produces a machine-readable change report. Run `verify_checksum()` first to confirm the graph hasn't been modified since the snapshot was taken.
</Tip>

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

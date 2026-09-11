---
name: provenance
description: Trace data lineage, source attribution, audit trails, and W3C PROV-O export in Semantica graphs. Uses ProvenanceManager.
---

# /semantica:provenance

Lineage and audit trails. Usage: `/semantica:provenance <task> [args]`

---

## `lineage <entity_id> [--depth N]`

```python
import os
from semantica.provenance import ProvenanceManager

db_path = os.path.expanduser("~/.semantica/prov.db")   # storage_path is passed to
os.makedirs(os.path.dirname(db_path), exist_ok=True)   # sqlite3.connect() unexpanded
pm = ProvenanceManager(storage_path=db_path)   # SQLite, or omit for in-memory
chain = pm.lineage(entity_id, depth=3)
full  = pm.get_lineage(entity_id)          # complete ancestry
down  = pm.get_descendants(entity_id)      # what this entity influenced
```

---

## `sources <entity_id>`

```python
srcs = pm.get_all_sources(entity_id)       # every source that contributed
prov = pm.get_provenance(entity_id)        # the raw PROV entry
hist = pm.revision_history(entity_id)
```

---

## `audit [--since <iso-date>] [--format table|json]`

```python
log = pm.audit_log(since="2026-01-01", format="table")
between = pm.query_recorded_between(start, end)
stats = pm.get_statistics()
```

---

## `export [--format turtle|json-ld|xml]`

W3C PROV-O export — this is the regulator-facing artifact.

```python
rdf = pm.export_prov(format="turtle", base_uri="https://example.org/prov/")
```

---

## `invalidate <entity_id> <agent_id> [--reason ...]`

Mark an entity superseded without deleting history.

```python
pm.invalidate(entity_id, agent_id, reason="source retracted")
```

## `check [--strict]`

```python
report = pm.check(strict=False)   # integrity check over the provenance store
```

---
name: provenance
description: Trace data lineage, source attribution, audit trails, and provenance assertions in Semantica graphs.
---

# /semantica:provenance

Inspect provenance metadata. Usage: `/semantica:provenance <task> [args]`

`$ARGUMENTS` = task + optional node, edge, or time range.

---

## `trace <node_id> [--depth N]`

Trace the provenance of a node or fact.

```python
from semantica.provenance import ProvenanceTracer

tracer = ProvenanceTracer()
trace = tracer.trace_node(node_id=node_id, depth=depth)
```

Output: source chain, authors, timestamps, and validation status.

---

## `audit [--since <ts>] [--actor <id>]`

View audit logs for graph changes.

```python
audit_log = tracer.get_audit_log(since=since, actor=actor)
```

Return: change events, actor, affected objects, and action details.

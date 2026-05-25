---
name: change
description: Track and inspect graph changes, diffs, temporal updates, and the impact of new data on Semantica knowledge graphs.
---

# /semantica:change

Inspect changes over time and evaluate updates. Usage: `/semantica:change <task> [args]`

`$ARGUMENTS` = task + optional node, time window, or filter.

---

## `diff [--from <ts>] [--to <ts>] [--node <id>]`

Compute graph diffs between two snapshots.

```python
from semantica.provenance.change_tracker import ChangeTracker
from semantica.context import ContextGraph

tracker = ChangeTracker()
diff = tracker.compute_diff(from_ts=from_ts, to_ts=to_ts, node_id=node_id)
```

Output: added/removed nodes and edges, attribute changes, and impact summary.

---

## `history <node_id> [--limit N]`

Show the change history for a node or relationship.

```python
history = tracker.get_node_history(node_id=node_id, limit=limit)
```

Return: revisions, timestamps, authors, and summary comments.

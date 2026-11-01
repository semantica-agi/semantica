---
title: "Temporal Truth Maintenance"
description: "Maintain derived facts over independent valid-time and known-time graph slices."
icon: "clock"
---

`TemporalTruthMaintenanceAdapter` connects explicitly annotated temporal graph
relationships to a [truth-maintenance session](/reference/truth_maintenance).
It turns changes in the selected evidence into one batch of source assertions
and retractions. Conclusions survive while they have another active support.

The two query coordinates are independent:

- **`valid_at`**: the time the claim applies to in the world.
- **`known_at`**: the time at which the evidence was recorded and not yet superseded.

This allows “what did we believe then?” and “what do we now believe about then?”
to have different answers. It does not change `TemporalGraphQuery` or its existing
`time_axis="both"` behavior, which checks both axes at the same timestamp.

## Example: a late correction and expiration

This example needs no database, embedding model or LLM:

```python
from copy import deepcopy

from semantica.reasoning import Rule, TemporalTruthMaintenanceAdapter

adapter = TemporalTruthMaintenanceAdapter(rules=[
    Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)"),
])
original = {
    "source": "alice",
    "target": "acme",
    "type": "EMPLOYED_BY",
    "valid_from": "2026-09-01T00:00:00Z",
    "valid_until": "2026-09-30T00:00:00Z",
    "recorded_at": "2026-09-01T00:00:00Z",
    "metadata": {
        "truth_maintenance": {
            "support_id": "hr-v1:employment",
            "fact": "Employed(Alice)",
        },
    },
}
graph = {
    "entities": [{"id": "alice"}, {"id": "acme"}],
    "relationships": [original],
}
adapter.sync(graph, valid_at="2026-09-15", known_at="2026-09-15")
assert "Eligible(Alice)" in adapter.facts

# On September 20, we learn employment actually ended on September 10.
# Keep the old claim and close its transaction interval, not its valid interval.
corrected_graph = deepcopy(graph)
corrected_graph["relationships"][0]["superseded_at"] = "2026-09-20"
revision = deepcopy(original)
revision["valid_until"] = "2026-09-10"
revision["recorded_at"] = "2026-09-20"
revision["metadata"]["truth_maintenance"]["support_id"] = "hr-v2:employment"
corrected_graph["relationships"].append(revision)

delta = adapter.sync(
    corrected_graph, valid_at="2026-09-15", known_at="2026-09-20",
)
assert delta.removed_facts == frozenset({"Employed(Alice)", "Eligible(Alice)"})

then = adapter.query_at(valid_at="2026-09-15", known_at="2026-09-15")
with_correction = adapter.query_at(valid_at="2026-09-15", known_at="2026-09-20")
assert "Eligible(Alice)" in then.facts
assert not with_correction.facts
assert then.explain("Employed(Alice)").explicit_support_ids == ("hr-v1:employment",)
assert not adapter.facts  # Historical queries did not move the live state.

# Explicitly move through the corrected valid-time boundary.
adapter.advance(valid_at="2026-09-09", known_at="2026-09-20")
assert "Eligible(Alice)" in adapter.facts
expired = adapter.advance(valid_at="2026-09-10", known_at="2026-09-20")
assert "Eligible(Alice)" in expired.removed_facts
assert graph["relationships"][0]["valid_until"] == "2026-09-30T00:00:00Z"
```

## Graph input and history

Pass a dictionary containing `entities` and `relationships`; callers with a
`ContextGraph` can export `to_kg_dict()` first and pass the result unchanged.
The caller must supply and retain the full managed evidence history, including
superseded relationship versions.
Exporting only an active view cannot reconstruct evidence that it omits.

With `ContextGraph`, the annotation and the bounds are ordinary keyword
arguments: `graph.add_edge(source, target, relation_type, valid_from=...,
valid_until=..., recorded_at=..., truth_maintenance={"support_id": ...,
"fact": ...})`. Extra keyword arguments are stored in edge metadata, so do not
wrap them in an explicit `metadata=` dictionary.

Each managed relationship has a `metadata.truth_maintenance` dictionary with
exactly `support_id` and `fact`. The fact uses PR1's canonical atom grammar; no
relation label is automatically translated into a rule predicate. A support ID
identifies **one source assertion revision**. Use distinct IDs for different
facts from the same document and for later revisions. Unannotated relationships
are ignored; malformed annotations raise `ValidationError`.

Temporal fields are read from each record itself and, when present, from its
`metadata` and `properties` dictionaries. That second location matters because
`ContextGraph` keeps everything except the valid-time bounds inside `metadata`
(entities also expose it through `properties`), so `to_kg_dict()` output works
without rewriting. A field supplied in more than one place must denote the same
instant; conflicting duplicates raise `TemporalValidationError`.

| Field | Meaning | Default for managed evidence |
|---|---|---|
| `valid_from` | Inclusive valid-time start | Unbounded past |
| `valid_until` | Exclusive valid-time end | Unbounded future |
| `recorded_at` | Inclusive known-time start | Required explicitly |
| `superseded_at` | Exclusive known-time end | Unbounded future |

Relationship endpoints are read from `source`/`target` or from the canonical
`source_id`/`target_id` emitted by `to_kg_dict()`. Supplying both forms with
different values raises `ValidationError` instead of silently preferring one.

Null upper bounds, `"OPEN"`, and `TemporalBound.OPEN` mean unbounded future.
Finite intervals require `start < end`. Times use the existing temporal parser:
ISO strings, datetimes and numeric Unix timestamps are accepted; naive datetimes
are treated as UTC. Booleans are rejected. There is no day/second truncation.
No default value is taken from the wall clock.

Retained records cannot disappear from a later `sync()`. Their fact, endpoints,
relation type, valid interval and recorded time cannot be rewritten. An open
`superseded_at` may be closed once; a closed interval cannot be reopened or
changed. Corrections close an old revision and add a new one. To withdraw a
source from the current known-time view, close its transaction interval and
advance `known_at` to or past that boundary. Physically removing a row is rejected.

The adapter accepts the source's explicit transaction history as authoritative;
it does not infer arrival times, resolve conflicting evidence or assign a
replacement relationship automatically.

Entity IDs must be unique strings. If the graph includes entities, every managed
edge needs existing endpoints, and both endpoints must be active at both query
coordinates. Entity scaffolding with no temporal fields is timeless. Its retained
time fields follow the same immutability/transaction-closing rules. Relationship-only
graphs are supported, but cannot later acquire endpoint constraints on the same
adapter: doing so would reinterpret retained history. Create a new adapter when
changing that mode. Predicate arity is checked across all retained evidence,
including records that are inactive at the requested coordinates.

## API

### `TemporalTruthMaintenanceAdapter(rules=...)`

Owns a new session with copied, fixed PR1 rules. No externally mutable session is
accepted. All PR1 rule restrictions, including non-recursion and absence of side
effects, apply. Access must be caller-serialized.

### `sync(graph, *, valid_at, known_at) -> MaintenanceDelta`

Validate and ingest the retained evidence projection. Diff its selected support
IDs against the currently active ones and apply one PR1 batch. A source replacement
for the same fact has support changes without intermediate fact churn.

Validation or reasoning failure leaves retained evidence, live facts, clocks and
counters unchanged. Input dictionaries are not mutated or retained by reference.
Non-temporal attributes and unrelated metadata are not part of the managed projection.

### `advance(*, valid_at, known_at) -> MaintenanceDelta`

Select another slice of retained evidence. This is how callers trigger expiration
or activation without modifying the graph. Both forward and backward movement are
allowed. There is no timer: merely waiting does not update the live facts.

### `query_at(*, valid_at, known_at) -> TemporalFactSnapshot`

Build a fresh session for the requested slice and return its facts, active source
supports and direct explanations. The frozen result contains only immutable
values; it exposes `explain(fact)` and remains unchanged by later updates.
It carries `valid_at`, `known_at` and `graph_revision`. It does not change the
live session or pretend that a historical recomputation has a live commit version.

### Live properties and explanation

- `facts`: immutable set of current explicit and inferred facts.
- `explain(fact)`: current PR1 direct sources and derivations.
- `version`: PR1's committed support-set counter. A clock-only change need not increment it.
- `graph_revision`: counter for changes to the normalized retained projection,
  including inactive evidence. It is local to this adapter, not a global graph ID.
- `valid_at`, `known_at`: current UTC coordinates, initially `None`.

For cache identity, distinguish the adapter instance, retained graph revision,
and both time coordinates; do not use the live support version alone.

## Cost and boundaries

Each graph sync normalizes/validates the supplied managed history. Slice selection
scans retained evidence and endpoint lifetimes. PR1 performs its existing update
work and state staging; historical queries recompute a fresh closure and capture
all direct explanations. Retained history grows with evidence revisions. This
implementation does not provide indexed storage-side temporal querying or promise
sublinear update cost.

The adapter does not persist its archive, write conclusions back to the graph,
schedule expiration, modify RETE, support recursive rules, or update RAG prompts
and vector records. Consistency is relative to supplied evidence and fixed rules;
losing support means “not currently derivable,” not “false.”

## Links

- [Grounded Context Assembly](/reference/grounded_context) — assemble RAG context consistent with a temporal truth snapshot, including bitemporal historical reads.

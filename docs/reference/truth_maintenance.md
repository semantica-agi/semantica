---
title: "Truth Maintenance"
description: "Source-aware logical retraction for fixed non-recursive rules."
icon: "microchip"
---

`TruthMaintenanceSession` keeps derived facts synchronized with changing external evidence. It maintains the invariant:

```text
session.facts == closure(fixed_rules, facts_with_remaining_external_support)
```

Retracting a source invalidates conclusions that have lost their premises, while conclusions that still have alternative derivations or explicit support are kept.

This is an **opt-in** session: the existing `Reasoner`, actions, RETE, and Datalog behavior is unchanged.


## When to Use It

Use `TruthMaintenanceSession` when:

- Facts come from external evidence that can be **corrected or withdrawn** (e.g. a document revision replaces one assertion with another).
- You need derived conclusions to be removed **only when they lose all support**, not on any deletion.
- You want a batch update that publishes the final state and **net changes**, instead of replaying intermediate states.
- You are hitting the limits of `RetractAction`: it removes only the requested fact and leaves unsupported conclusions behind, while a naive deletion cascade would wrongly remove conclusions that still have alternative derivations or explicit support.

Do not use it for recursive rules, temporal validity, external side effects, or multi-threaded access — see [Limitations](#limitations).


## Getting Started

```python
from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession

rules = [
    Rule(
        rule_id="employment-eligibility",
        name="Employment eligibility",
        conditions=["Employed(?x)"],
        conclusion="Eligible(?x)",
    ),
]
session = TruthMaintenanceSession(rules=rules)

session.apply(assertions=[
    FactSupport(support_id="document-v1", fact="Employed(Alice)"),
])

delta = session.apply(
    assertions=[FactSupport("document-v2", "Employed(Alice)")],
    retractions=["document-v1"],
)
assert not delta.added_facts
assert not delta.removed_facts
assert session.explain("Eligible(Alice)").active

delta = session.apply(retractions=["document-v2"])
assert delta.removed_facts == frozenset({
    "Employed(Alice)", "Eligible(Alice)",
})
```

The example above is **source replacement**: swapping one supporting document for another in a single batch produces no net fact deletion or insertion, because `Employed(Alice)` remains supported and `Eligible(Alice)` keeps its derivation.


## Core Concepts

- **Support**: an external fact assertion, identified by a caller-provided `support_id`. A support ID is permanently bound to one fact for the session lifetime; withdrawing and later reactivating the same association is allowed, but binding the same ID to a different fact raises `ValidationError`.
- **Derivation**: a rule application with rule identity, ordered premises, variable bindings, and conclusion. Independent derivations of the same conclusion are all retained; duplicate matches cannot inflate support.
- **Version**: a monotonic commit counter. It increments once per batch that changes the support set (even if the fact set is unchanged) and stays unchanged for no-ops.
- **Truth semantics**: losing all support means "not currently derivable", not "logically false".


## Session API

### `TruthMaintenanceSession(rules=...)`

Constructs the session from an iterable of existing [`Rule`](/reference/reasoning#rule-and-fact-dataclass-fields) objects. The rules are copied into immutable internal snapshots: later mutation of the original `Rule` objects does not affect the session.

The rule set must be:

- **Positive, function-free implications** with at least one body atom.
- **Range-restricted**: every head variable occurs in the body.
- **Acyclic**: the predicate dependency graph must not contain direct or indirect recursion; cyclic rule sets are rejected at construction.
- **Side-effect free**: actions, handlers, and non-implication rule types are rejected; `confidence` must be `1.0`.

### `apply(assertions=..., retractions=...)`

Atomically applies one batch:

- `assertions`: iterable of `FactSupport`.
- `retractions`: iterable of support-ID strings.

Returns a `MaintenanceDelta` with `version`, `added_facts`, `removed_facts`, `added_supports`, and `removed_supports` (net values, observed after commit).

Validation and error semantics:

- Re-asserting an already active support with the same fact is a no-op; retracting an unknown or inactive support is a no-op.
- A support ID bound to a different fact, the same ID in both assertions and retractions of one batch, or any malformed input raises the existing `ValidationError`.
- Unexpected internal failures raise `ProcessingError` with the original cause attached.
- **Any failed batch leaves the committed facts, support catalog, derivations, and version unchanged.**

### `explain(fact)`

Returns a `FactExplanation` for the current state:

- `fact`: the canonical fact string.
- `active`: whether the fact currently holds.
- `explicit_support_ids`: sorted IDs of external supports.
- `derivations`: all retained direct derivations (rule ID, ordered premises, bindings).

### Read-only views

- `facts`: frozenset of all currently believed facts (explicit plus derived).
- `version`: the commit counter described above.
- `snapshot()`: returns a `TruthMaintenanceSnapshot` — a frozen dataclass
  with `version`, `facts`, and `active_supports` (tuple sorted by support ID).
  The snapshot is a full detached copy: later `apply()` batches never change
  an existing snapshot.

All read-only views (`facts`, `version`, `snapshot()`, `explain()`) leave the
session state unchanged. Returned snapshots (`MaintenanceDelta`,
`FactExplanation`, `Derivation`, `TruthMaintenanceSnapshot`) are frozen
dataclasses with immutable collections; mutating caller-owned rules or
previously returned results cannot mutate the session.

### Checkpoint export and restore

Use `to_checkpoint()` and `from_checkpoint()` when an application must resume
the same logical session in a later process. These methods are a serialization
boundary, not a storage engine.

- `to_checkpoint()` returns a new JSON-compatible `dict` containing the fixed
  rules captured at construction, the complete support catalog (including
  withdrawn supports), the active support IDs, and the committed session
  version. It does not save derived facts or internal indexes.
- `from_checkpoint(payload)` accepts the result of `json.loads()` — not a JSON
  string or file path — validates the complete payload, rebuilds derived facts,
  direct derivations, and dependency indexes, and returns a new session only
  after reconstruction succeeds.

`snapshot()` remains a read-only query view of the current state. A checkpoint
is different: it is a restart format that preserves the support-ID bindings and
arity constraints needed to continue updates after serialization. The
`session_version` in a checkpoint is only a local commit counter. It does not
authorize reusing old snapshot-provider identities, temporal adapter history,
or external caches.

The fixed v1 schema is:

```json
{
  "format_version": 1,
  "session_version": 4,
  "rules": [
    {
      "rule_id": "employment-eligibility",
      "conditions": ["Employed(?x)"],
      "conclusion": "Eligible(?x)"
    }
  ],
  "support_catalog": [
    {"support_id": "document-v1", "fact": "Employed(Alice)"},
    {"support_id": "document-v2", "fact": "Employed(Alice)"}
  ],
  "active_support_ids": ["document-v2"]
}
```

The top level and each rule/catalog record have exact field sets; missing and
unknown fields are rejected. `format_version` must be integer `1`;
`session_version` must be a non-negative integer. A non-empty support catalog
requires a positive version because it represents at least one committed
update; an empty catalog requires version zero, and a non-empty catalog with no
active supports requires at least two commits. Rules and catalog facts are
semantic values, so invalid atoms, variables in facts, recursive rules, and
arity conflicts are rejected
with the same `ValidationError` used by construction and `apply()`.
Unsupported future formats are also rejected, and restore never returns a
partially reconstructed session.

Applications choose where to store the JSON. The minimal example below is
intended only to show the API; `Path.write_text()` does **not** provide a
crash-safe atomic commit. Use an atomic file replacement or transactional
database commit if losing or partially writing a checkpoint is unacceptable.

```python
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession

session = TruthMaintenanceSession(rules=[
    Rule("eligibility", "Eligibility", ["Employed(?x)"], "Eligible(?x)")
])
session.apply(assertions=[
    FactSupport("doc-1", "Employed(Alice)"),
    FactSupport("doc-2", "Employed(Alice)"),
])
saved_version = session.version
with TemporaryDirectory() as directory:
    path = Path(directory) / "checkpoint.json"
    path.write_text(json.dumps(session.to_checkpoint()), encoding="utf-8")
    del session
    restored = TruthMaintenanceSession.from_checkpoint(
        json.loads(path.read_text(encoding="utf-8"))
    )
    assert restored.version == saved_version
    restored.apply(retractions=["doc-1"])
    assert "Eligible(Alice)" in restored.facts
    restored.apply(retractions=["doc-2"])
    assert "Eligible(Alice)" not in restored.facts
```

Restore covers only the last successfully exported and saved checkpoint.
Updates committed after that checkpoint, including updates that succeeded but
were not durably stored, cannot be recovered. A malformed JSON document raises
`JSONDecodeError` from the application's own `json.loads()` call;
`from_checkpoint()` validates the resulting structured object and raises
`ValidationError` for malformed checkpoint data.


## Cost Model

- **Deletion propagation** and **affected-rule matching** are targeted: a deletion-only batch uses dependency indexes to compute the affected fact set, then re-matches only the rules whose body predicates intersect that set (the affectedness scan itself walks the rule list, so cost still grows with rule count); insertions reevaluate only rules reachable from newly active predicates.
- **Staging copies the whole session state** for each *effective* `apply()` batch to guarantee atomic commits (an empty or already-applied batch is a no-op and stages nothing), and the session retains the **support catalog in memory** for the session lifetime (including withdrawn supports, so IDs stay bound).
- **Each `snapshot()` call copies the full committed state again** (facts, active supports, version), so consumers such as
  [`TruthMaintenanceContextFilter`](/reference/context#support-aware-retrieval-truth_filter)
  pay one whole-state copy per filtered retrieval. Do not call it in a tight
  loop when a single shared read is enough.
- The copy-on-update and catalog costs are per-batch whole-state costs; do not assume end-to-end latency is strictly proportional to the affected subgraph. Measure before relying on performance.
- **Checkpoint payloads grow with the fixed rules and the complete historical
  support catalog**, not just the active supports. Export also pays a
  deterministic sorting cost for the catalog and active IDs.
- **Restore is a full reconstruction**: it validates every catalog entry,
  combines rule and catalog arity constraints, and rebuilds the complete
  closure and direct explanations by replaying only the active supports. Join
  matching can produce many intermediate matches, memory grows with those
  matches and the copied candidate state, and no constant-time or
  active-support-only cost bound is promised.


## Limitations

- **Non-recursive rules only**; the constructor rejects cyclic predicate dependencies.
- **Narrow atom syntax**: ASCII predicate/variable identifiers and unquoted scalar symbol constants, including zero-arity atoms. No quoted strings, whitespace-bearing constants, nested terms, comparisons, aggregation, negation, or disjunction. Exactly one arity per predicate within the session.
- **Boolean support semantics**; no confidence propagation, no probabilistic reasoning.
- **No side effects**: the session never executes actions or handlers and creates no LLM or store clients.
- **No automatic storage or recovery**: checkpoints are an explicit serialization format, but the session never writes to a file or database and does not recover automatically after a crash. The application owns storage, atomic commit, and choosing the last good checkpoint.
- **No thread-safety or concurrent writers**: access remains caller-serialized in a single process, and checkpointing does not add a distributed locking or multi-writer protocol.
- **No temporal validity or cross-store synchronization** guarantees. Restoring a checkpoint does not restore temporal adapter history, snapshot-provider identities, or external caches.
- **Fixed rules**: rule changes require constructing a new session.
- No historical proof archive: `explain()` describes the current state only.


## Links

- [Temporal Truth Maintenance](/reference/temporal_truth_maintenance) — an opt-in graph adapter for independent valid/known-time slices, expiration and late corrections.
- [Reasoning](/reference/reasoning) — the rule engines this session builds on, including the `Rule` representation.
- [Context](/reference/context#support-aware-retrieval-truth_filter) — `TruthMaintenanceContextFilter` consumes immutable snapshots to filter retrieved context by active support.
- [Grounded Context Assembly](/reference/grounded_context) — registered summaries and citations withdrawn when their evidence is withdrawn, with bitemporal historical reads.
- [Ontology](/reference/ontology) — ontology axioms and SHACL constraints.

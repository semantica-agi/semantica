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

Returned snapshots (`MaintenanceDelta`, `FactExplanation`, `Derivation`) are frozen dataclasses with immutable collections; mutating caller-owned rules or previously returned results cannot mutate the session.


## Cost Model

- **Deletion propagation** and **affected-rule matching** are incremental: a deletion-only batch uses dependency indexes without rescanning all rules; insertions reevaluate only rules reachable from newly active predicates.
- **Staging copies the whole session state** per `apply()` batch to guarantee atomic commits, and the session retains the **support catalog in memory** for the session lifetime (including withdrawn supports, so IDs stay bound).
- The copy-on-update and catalog costs are per-batch whole-state costs; do not assume end-to-end latency is strictly proportional to the affected subgraph. Measure before relying on performance.


## Limitations

- **Non-recursive rules only**; the constructor rejects cyclic predicate dependencies.
- **Narrow atom syntax**: ASCII predicate/variable identifiers and unquoted scalar symbol constants, including zero-arity atoms. No quoted strings, whitespace-bearing constants, nested terms, comparisons, aggregation, negation, or disjunction. Exactly one arity per predicate within the session.
- **Boolean support semantics**; no confidence propagation, no probabilistic reasoning.
- **No side effects**: the session never executes actions or handlers and creates no LLM or store clients.
- **No thread-safety, persistence, temporal validity, or cross-store synchronization** guarantees. Access must be caller-serialized in a single process.
- **Fixed rules**: rule changes require constructing a new session.
- No historical proof archive: `explain()` describes the current state only.


## Links

- [Reasoning](/reference/reasoning) — the rule engines this session builds on, including the `Rule` representation.
- [Ontology](/reference/ontology) — ontology axioms and SHACL constraints.

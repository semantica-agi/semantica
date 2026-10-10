---
title: "Grounded Context Assembly"
description: "Assemble RAG context that stays consistent with truth maintenance: registered summaries and citations that are withdrawn when their evidence is withdrawn, with bitemporal historical reads."
icon: "shield-check"
---

`GroundedContextAssembler` turns retrieved content into model-ready context
that is guaranteed consistent with a truth-maintenance session at the moment
of assembly. When the evidence behind a registered summary or citation is
retracted or superseded, the content disappears from the current answer —
while historical coordinates still reproduce exactly what was known at the
time. The stored records themselves are never modified.

## The Four Stages

The stack is four small layers, each consuming only the public interface of
the one below it:

| Stage | Class | Responsibility |
| :--- | :--- | :--- |
| 1. Source of truth | `TruthMaintenanceSession` / `TemporalTruthMaintenanceAdapter` | Maintains facts, support records, and (for the temporal adapter) validity and knowledge coordinates |
| 2. Snapshot | `TruthSnapshotProvider` | Captures an immutable `ContextReadView` of the source — facts, active supports, and the stamp — for either the live state or a historical `valid_at` / `known_at` coordinate |
| 3. Registry | `ContextArtifactIndex` | Holds immutable registered content records (`GroundedArtifact`) and reports which ones became invalid or re-eligible between two views |
| 4. Assembly | `GroundedContextAssembler` | Retrieves candidates, re-checks every registered artifact against the captured view, applies the character budget, and renders grounded text with citations |

The registry only manages content you explicitly register. Ordinary candidates
without `grounded_artifact_id` remain eligible under the existing
`truth_maintenance` annotation rules: their namespace, facts, supports, and
attachments must validate against the captured view. They retain their retrieval
source and render without registered citation footnotes. Candidates carrying
`grounded_artifact_id` must additionally match a registered artifact's content
and satisfy its dependency and citation contracts; an unknown ID is excluded.

## Complete Example: Retracting a Source

The program below runs standalone with no model, database, or network — only
`semantica` itself. It asserts the HR support, registers one citation and one
summary that cites it, assembles, then retracts the HR support in the same
`apply` batch that introduces a replacement badge source. The fact survives
through the badge, but the cited content correctly does not:

```python
from semantica.context import (
    ContextArtifactIndex,
    ContextDependencies,
    ContextRetriever,
    GroundedArtifact,
    GroundedContextAssembler,
    TruthSnapshotProvider,
)
from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession

rules = [
    Rule(
        rule_id="eligibility",
        name="Eligibility",
        conditions=["Employed(?x)"],
        conclusion="Eligible(?x)",
    )
]
session = TruthMaintenanceSession(rules=rules)
session.apply(assertions=[FactSupport("hr-1", "Employed(Alice)")])

provider = TruthSnapshotProvider(session, namespace="hr-docs")
index = ContextArtifactIndex(namespace="hr-docs")
view = provider.capture()

citation = GroundedArtifact(
    artifact_id="cite-hr-1",
    kind="citation",
    content="HR record hr-1 states Alice is employed at Acme",
    dependencies=ContextDependencies(frozenset(), frozenset({"hr-1"})),
    built_from=view.stamp,
    validity_policy="dependencies",
    citation_ids=(),
)
summary = GroundedArtifact(
    artifact_id="summary-alice",
    kind="summary",
    content="Alice is eligible.",
    dependencies=ContextDependencies(frozenset({"Eligible(Alice)"}), frozenset()),
    built_from=view.stamp,
    validity_policy="dependencies",
    citation_ids=("cite-hr-1",),
)
index.register(citation)
index.register(summary)

# A tiny read-only store standing in for any real vector backend.
class StaticVectorStore:
    def __init__(self, rows):
        self.rows = [dict(row, metadata=dict(row["metadata"])) for row in rows]

    def search(self, *, query, limit):
        return self.rows[:limit]

def stored_row(record, score=0.9):
    """Project a registered artifact into the row shape the store returns."""
    return {
        "id": record.artifact_id,
        "content": record.content,
        "score": score,
        "metadata": {
            "grounded_artifact_id": record.artifact_id,
            "truth_maintenance": {
                "schema_version": 1,
                "session_id": record.built_from.namespace,
                "required_facts": sorted(record.dependencies.required_facts),
                "required_support_ids": sorted(
                    record.dependencies.required_support_ids
                ),
            },
        },
    }

retriever = ContextRetriever(
    vector_store=StaticVectorStore([stored_row(citation), stored_row(summary)]),
    use_graph_expansion=False,
)
assembler = GroundedContextAssembler(retriever, provider=provider, artifacts=index)

bundle = assembler.assemble("Is Alice eligible?")
assert bundle.text == (
    "[b1] Alice is eligible. (sources: [c1])\n\n"
    "Sources:\n"
    "[c1] HR record hr-1 states Alice is employed at Acme"
)

# Withdraw hr-1 in the same batch as an alternative badge source.
session.apply(
    assertions=[FactSupport("badge-2", "Employed(Alice)")],
    retractions=["hr-1"],
)
report = index.reconcile(provider.capture())
assert sorted(report.invalidated_ids) == ["cite-hr-1", "summary-alice"]

bundle = assembler.assemble("Is Alice eligible?")
assert bundle.text == ""
assert bundle.citations == ()
```

The stored rows are untouched: `store.rows` still holds both records verbatim.
Only the assembled answer changed, because the summary is bound to the
retracted citation.

## Complete Example: A Late Correction, Read Bitemporally

A correction recorded on 2026-09-20 supersedes the original HR record
`hr-v1` but is itself only valid until 2026-09-10. The current answer
becomes empty, yet the historical coordinates `valid_at=2026-09-15,
known_at=2026-09-15` still reproduce the superseded answer exactly:

```python
from copy import deepcopy

from semantica.context import (
    ContextArtifactIndex,
    ContextDependencies,
    ContextRetriever,
    GroundedArtifact,
    GroundedContextAssembler,
    TruthSnapshotProvider,
)
from semantica.reasoning import Rule, TemporalTruthMaintenanceAdapter

rules = [
    Rule(
        rule_id="eligibility",
        name="Eligibility",
        conditions=["Employed(?x)"],
        conclusion="Eligible(?x)",
    )
]
graph = {
    "entities": [{"id": "alice"}, {"id": "acme"}],
    "relationships": [
        {
            "source": "alice",
            "target": "acme",
            "type": "EMPLOYED_BY",
            "valid_from": "2026-09-01",
            "valid_until": "2026-09-30",
            "recorded_at": "2026-09-01",
            "metadata": {
                "truth_maintenance": {
                    "support_id": "hr-v1",
                    "fact": "Employed(Alice)",
                }
            },
        }
    ],
}

adapter = TemporalTruthMaintenanceAdapter(rules=rules)
adapter.sync(graph, valid_at="2026-09-15", known_at="2026-09-15")

provider = TruthSnapshotProvider(adapter, namespace="hr-temporal")
index = ContextArtifactIndex(namespace="hr-temporal")
view = provider.capture()

citation = GroundedArtifact(
    artifact_id="cite-hr-v1",
    kind="citation",
    content="HR record hr-v1 states Alice is employed at Acme",
    dependencies=ContextDependencies(frozenset(), frozenset({"hr-v1"})),
    built_from=view.stamp,
    validity_policy="dependencies",
    citation_ids=(),
)
summary = GroundedArtifact(
    artifact_id="summary-alice",
    kind="summary",
    content="Alice is eligible.",
    dependencies=ContextDependencies(frozenset({"Eligible(Alice)"}), frozenset()),
    built_from=view.stamp,
    validity_policy="dependencies",
    citation_ids=("cite-hr-v1",),
)
index.register(citation)
index.register(summary)

class StaticVectorStore:
    def __init__(self, rows):
        self.rows = [dict(row, metadata=dict(row["metadata"])) for row in rows]

    def search(self, *, query, limit):
        return self.rows[:limit]

def stored_row(record, score=0.9):
    return {
        "id": record.artifact_id,
        "content": record.content,
        "score": score,
        "metadata": {
            "grounded_artifact_id": record.artifact_id,
            "truth_maintenance": {
                "schema_version": 1,
                "session_id": record.built_from.namespace,
                "required_facts": sorted(record.dependencies.required_facts),
                "required_support_ids": sorted(
                    record.dependencies.required_support_ids
                ),
            },
        },
    }

retriever = ContextRetriever(
    vector_store=StaticVectorStore([stored_row(citation), stored_row(summary)]),
    use_graph_expansion=False,
)
assembler = GroundedContextAssembler(retriever, provider=provider, artifacts=index)

first = assembler.assemble("Is Alice eligible?")
assert "Alice is eligible." in first.text

# The correction arrives late: hr-v1 is superseded on 9/20 by an
# hr-v2 record that was only valid until 9/10.
revised = deepcopy(graph)
revised["relationships"][0]["superseded_at"] = "2026-09-20"
replacement = deepcopy(graph["relationships"][0])
replacement["valid_until"] = "2026-09-10"
replacement["recorded_at"] = "2026-09-20"
replacement["metadata"]["truth_maintenance"]["support_id"] = "hr-v2"
revised["relationships"].append(replacement)
adapter.sync(revised, valid_at="2026-09-15", known_at="2026-09-20")

current = assembler.assemble("Is Alice eligible?")
assert current.text == ""
assert current.citations == ()

report = index.reconcile(provider.capture())
assert sorted(report.invalidated_ids) == ["cite-hr-v1", "summary-alice"]

# Historical coordinates still reproduce the superseded answer.
historical = assembler.assemble(
    "Is Alice eligible?", valid_at="2026-09-15", known_at="2026-09-15"
)
assert historical.text == first.text

# Asked with the knowledge of the correction, history is empty too.
later = assembler.assemble(
    "Is Alice eligible?", valid_at="2026-09-15", known_at="2026-09-20"
)
assert later.text == ""
```

## Boundaries

The assembly guarantee is deliberately narrow. Each boundary below is a
commitment you can rely on — or a non-commitment you must not rely on:

- **Four stages, one direction of trust.** Each layer trusts only the public
  interface of the layer below. A view is an immutable value; a registry
  record is immutable once registered. Nothing in the stack writes back into
  the session, the adapter, or the vector store.
- **Filter vs. assembler.** The [truth filter](/reference/context) validates
  per-row annotations during retrieval, before ranking. The assembler
  validates registered artifact contracts during assembly, adds snapshot
  consistency, the character budget, and citation footnotes. Both leave
  stored records untouched; they answer different questions and can be
  combined.
- **Namespace incarnation.** A registered artifact is only valid for the
  namespace it was stamped from. Recreating a session under a new namespace
  (or a new session ID) starts a fresh incarnation: artifacts stamped from
  the old one never become valid again in the new one.
- **Provider instance identity.** Captured stamps include an opaque `provider_id`.
  `assert_current` rejects views from another provider instance, even when
  both providers wrap the same source and all counters match. Hand-built
  stamps may omit the identity for pure value validation, but cannot pass
  provider freshness checks. This identity is not an authentication token.
- **Snapshot policy is sensitive to anything new.** A `dependencies`-policy
  artifact stays valid as long as its namespace, source kind, declared facts
  and supports match. Switching source kind re-evaluates every registered
  artifact, even when facts and support IDs are unchanged. A
  `snapshot`-policy artifact additionally requires the view stamp to be the
  one it was built from, so any new session version — even one that keeps
  every fact — or a different provider instance invalidates it.
- **Citation constraints.** A citation must use the `dependencies` policy and
  must declare a support ID; it may not reference other artifacts. A summary
  whose citation is invalid is itself excluded (`invalid_citation`) — a
  grounded answer never keeps its prose while silently dropping its source.
- **Only explicitly registered content is managed.** The index never infers
  dependencies and never annotates records on your behalf. Ordinary candidates
  can participate with valid annotations without being registered; candidates
  with an unknown artifact ID cannot bypass registry validation.
- **Value validation.** Read-view facts and artifact fact dependencies use PR1
  ground-atom validation and canonical whitespace. Temporal stamps convert
  timezone-aware coordinates to UTC without changing the instant; naive
  coordinates are rejected. The provider and registry namespaces must match,
  even when retrieval would return no candidates.
- **Historical reads are isolated.** Assembling at a `valid_at` / `known_at`
  coordinate evaluates history and never mutates the adapter, the provider,
  or the registry. Moving the live cursor (advance) during a historical
  assembly is allowed; syncing new retained evidence during one raises
  `ProcessingError` rather than returning a mixed-version answer.
- **Character budget.** Assembly selects content greedily within the
  configured budget; over-budget blocks are excluded and reported, not
  truncated mid-sentence. It continues through the ranked, threshold-filtered
  candidate pool already collected, without a pre-budget top-k cut. Source
  collection remains bounded; at most `max_results` blocks are emitted.
  Ordinary retrieval retains its default top-k behavior.
- **Freshness ends at return.** A returned bundle is a snapshot of the view
  it was assembled from. It does not expire, and it does not track later
  retractions; call `assemble` again for the current answer.
- **Not a storage or semantics guarantee.** Consistency here means: the
  assembled context matches the registered content contracts against the
  captured truth-maintenance view. It does not make your vector store
  transactionally consistent, and it does not make the model's conclusions
  semantically correct.

## Related

- [Context Module](/reference/context) — retrieval, the truth filter, and
  `ContextRetriever` details
- [Truth Maintenance](/reference/truth_maintenance) — sessions, supports,
  and retraction semantics
- [Temporal Truth Maintenance](/reference/temporal_truth_maintenance) —
  validity windows, knowledge time, supersession, and the adapter used above
---
title: "Conflicts Module"
description: "Multi-source conflict detection and resolution — value, type, temporal, and logical conflicts with investigation guides."
icon: "triangle-exclamation"
---

`semantica.conflicts` detects and resolves contradictions when multiple sources disagree on the same fact. It surfaces five conflict types, seven resolution strategies, and generates investigation guides for manual review — so conflicts never silently corrupt your knowledge graph.

## Why Detect Conflicts?

When you ingest data from multiple sources, contradictions are inevitable. One annual report says Apple's revenue was $391B; a financial newswire says $383B. Without conflict detection, both values land in your graph and queries silently return inconsistent answers.

Semantica's conflict detection makes disagreements explicit and actionable:

- **Value conflicts** — SEC says revenue is $391B; Reuters says $383B
- **Type conflicts** — "Python" is a `ProgrammingLanguage` in one source, a `Snake` species in another
- **Temporal conflicts** — a CEO had two different employers during overlapping date ranges
- **Logical conflicts** — an entity simultaneously holds two mutually exclusive properties
- **Relationship conflicts** — the same relationship has inconsistent cardinality or properties across sources

## Exported Classes

| Class | Role |
| --- | --- |
| `ConflictDetector` | Detects value, type, temporal, logical, and relationship conflicts across entity pairs |
| `ConflictResolver` | Resolves conflicts with configurable strategy: `voting`, `credibility_weighted`, `most_recent`, `first_seen`, `highest_confidence`, `manual_review` |
| `ConflictType` | Enum: `VALUE_CONFLICT`, `TYPE_CONFLICT`, `TEMPORAL_CONFLICT`, `LOGICAL_CONFLICT`, `RELATIONSHIP_CONFLICT` |
| `ResolutionStrategy` | Enum of available resolution strategies passed to `ConflictResolver` |
| `SourceTracker` | Tracks which source contributed each property value on each entity |
| `ConflictAnalyzer` | Analyzes conflict patterns, severity distribution, and per-source statistics |
| `InvestigationGuideGenerator` | Generates step-by-step checklists for human review of unresolvable conflicts |

## What You Get

<CardGroup cols={2}>
  <Card title="ConflictDetector" icon="magnifying-glass">
    Value, type, temporal, logical, and relationship conflict detection across all entity pairs.
  </Card>
  <Card title="ConflictResolver" icon="check">
    7 resolution strategies including voting, credibility-weighted, and temporal preference.
  </Card>
  <Card title="SourceTracker" icon="link">
    Track which source each conflicting fact came from, with per-source credibility scores.
  </Card>
  <Card title="ConflictAnalyzer" icon="chart-line">
    Pattern analysis, severity grouping, source-level statistics, and trend identification.
  </Card>
  <Card title="InvestigationGuideGenerator" icon="list-check">
    Auto-generate step-by-step investigation checklists for human and expert review.
  </Card>
  <Card title="Convenience Functions" icon="bolt">
    `detect_conflicts()` and `resolve_conflicts()` for one-call workflows.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Set credibility scores before ingestion">
    ```python
    from semantica.conflicts import SourceTracker

    tracker = SourceTracker()
    tracker.set_source_credibility("sec_filings",   0.95)
    tracker.set_source_credibility("pubmed",        0.92)
    tracker.set_source_credibility("wikipedia",     0.80)
    tracker.set_source_credibility("news_articles", 0.65)
    ```
  </Step>
  <Step title="Detect conflicts after building the graph">
    ```python
    from semantica.conflicts import ConflictDetector

    detector  = ConflictDetector()
    conflicts = detector.detect_conflicts(kg)
    print(f"Found {len(conflicts)} conflicts")

    for conflict in conflicts:
        print(f"[{conflict.conflict_type}] entity='{conflict.entity_id}'  attr='{conflict.attribute}'")
        print(f"  Values: {conflict.values}  Severity: {conflict.severity:.2f}")
    ```
  </Step>
  <Step title="Triage by severity">
    ```python
    from semantica.conflicts import ConflictAnalyzer

    analyzer    = ConflictAnalyzer()
    analysis    = analyzer.analyze_conflicts(conflicts)
    by_severity = analysis["by_severity"]
    print(f"Critical: {len(by_severity.get('critical', []))}")
    print(f"High:     {len(by_severity.get('high', []))}")
    print(f"Low:      {len(by_severity.get('low', []))}")
    ```
  </Step>
  <Step title="Auto-resolve low-severity, escalate critical">
    ```python
    from semantica.conflicts import ConflictResolver, InvestigationGuideGenerator, ResolutionStrategy

    resolver = ConflictResolver(source_tracker=tracker)

    # Auto-resolve low-severity
    auto_resolved = resolver.resolve_conflicts(
        by_severity["low"],
        strategy=ResolutionStrategy.CREDIBILITY_WEIGHTED,
    )

    # Generate investigation guides for critical conflicts
    generator = InvestigationGuideGenerator()
    for conflict in by_severity["critical"]:
        guide = generator.generate_guide(conflict)
        print(f"\n{guide.title}")
        for step in guide.steps:
            print(f"  [{step.order}] ({step.priority.upper()}) {step.description}")
    ```
  </Step>
</Steps>

## ConflictDetector

```python
from semantica.conflicts import ConflictDetector

detector  = ConflictDetector()
conflicts = detector.detect_conflicts(kg)
```

### Detection Types

| Type | What It Detects | Example |
| ---- | --------------- | ------- |
| `VALUE` | Same entity, same attribute, different values across sources | Revenue $391B vs $383B |
| `TYPE` | Same entity classified as different types | "Python" as Language vs Snake |
| `TEMPORAL` | Overlapping validity windows with contradictory facts | CEO at two companies simultaneously |
| `LOGICAL` | Facts that violate ontology axioms or SHACL constraints | `is_alive=True` but `death_date` set |
| `RELATIONSHIP` | Inconsistent relationship properties across sources | Edge weight 0.9 vs 0.3 from two sources |

Run targeted detection by type:

```python
# Detect all types at once (default)
conflicts = detector.detect_conflicts(kg)

# Detect specific types only — faster for targeted checks
value_conflicts    = detector.detect_value_conflicts(entities, "revenue")
type_conflicts     = detector.detect_type_conflicts(entities)
relation_conflicts = detector.detect_relationship_conflicts(kg)
```

**Key behaviours:**
- Severity scores are computed from the magnitude of disagreement — a $8B revenue discrepancy scores higher than a $1M discrepancy
- `LOGICAL` conflicts require an ontology or SHACL schema to be loaded; without one, they are not detected
- Detection runs in O(n·sources) time — it groups by entity+attribute and checks disagreement within each group

## ConflictResolver

```python
from semantica.conflicts import ConflictResolver, ResolutionStrategy

resolver = ConflictResolver()
results  = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.VOTING)

for result in results:
    print(f"Resolved '{result.attribute}' → {result.resolved_value}")
    print(f"  Strategy: {result.strategy}  Confidence: {result.confidence:.2f}")
```

### Choosing a Resolution Strategy

<Tabs>
  <Tab title="CREDIBILITY_WEIGHTED (recommended)">
    Weights each source's value by its assigned credibility score — favors authoritative sources automatically:

    ```python
    from semantica.conflicts import ConflictResolver, SourceTracker, ResolutionStrategy

    tracker = SourceTracker()
    tracker.set_source_credibility("sec_filings",   0.92)
    tracker.set_source_credibility("wikipedia",     0.80)
    tracker.set_source_credibility("news_articles", 0.65)

    resolver = ConflictResolver(source_tracker=tracker)
    results  = resolver.resolve_conflicts(
        conflicts,
        strategy=ResolutionStrategy.CREDIBILITY_WEIGHTED,
    )
    ```

    Best for: sources with known reliability rankings (SEC > blog).
  </Tab>
  <Tab title="VOTING">
    Majority vote — most common value across sources wins:

    ```python
    results = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.VOTING)
    ```

    Best for: 3+ sources with roughly equal credibility. When all sources have identical credibility scores, `CREDIBILITY_WEIGHTED` behaves identically to `VOTING`.
  </Tab>
  <Tab title="MOST_RECENT / FIRST_SEEN">
    ```python
    # Most recent source wins — for fast-changing facts
    results = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.MOST_RECENT)

    # First seen wins — for stable facts (founding date, original name)
    results = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.FIRST_SEEN)
    ```
  </Tab>
  <Tab title="MANUAL_REVIEW / EXPERT_REVIEW">
    ```python
    from semantica.conflicts import InvestigationGuideGenerator

    # Flag for human review — use with InvestigationGuideGenerator
    results   = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.MANUAL_REVIEW)
    generator = InvestigationGuideGenerator()

    for conflict in conflicts:
        guide = generator.generate_guide(conflict)
        print(f"{guide.title}")
        for step in guide.steps:
            print(f"  [{step.order}] {step.description}")
    ```

    Best for: high-stakes decisions (severity > 0.8), regulated data (HIPAA/SOX), and domain-specific ambiguity.
  </Tab>
  <Tab title="Strategy Comparison">

    | Strategy | Enum | When to Use |
    | -------- | ---- | ----------- |
    | Majority vote | `VOTING` | 3+ sources with roughly equal credibility |
    | Credibility-weighted | `CREDIBILITY_WEIGHTED` | Sources have different authority levels |
    | Most recent | `MOST_RECENT` | Fast-changing facts: stock price, headcount, status |
    | First seen | `FIRST_SEEN` | Stable facts: founding date, original name |
    | Highest confidence | `HIGHEST_CONFIDENCE` | Extraction pipeline outputs confidence scores |
    | Manual review | `MANUAL_REVIEW` | High-stakes decisions, regulated data |
    | Expert review | `EXPERT_REVIEW` | Domain-specific ambiguity — escalate to a specialist |
  </Tab>
</Tabs>

Use the convenience aliases for shorter code:

```python
from semantica.conflicts import voting, credibility_weighted, most_recent, highest_confidence

results = resolver.resolve_conflicts(conflicts, strategy=voting)
```

## SourceTracker

```python
from semantica.conflicts import SourceTracker
from datetime import datetime

tracker = SourceTracker()
tracker.set_source_credibility("sec_10k",   0.92)
tracker.set_source_credibility("wikipedia", 0.80)

tracker.track_property_source(
    entity_id="apple_inc",
    property_name="revenue",
    value="$391B",
    source="sec_10k_2023",
    timestamp=datetime(2024, 1, 26),
)

sources = tracker.get_property_sources("apple_inc", "revenue")
for s in sources:
    print(f"{s.source}: {s.value}  (credibility: {s.credibility:.2f})")

chain = tracker.get_traceability_chain("apple_inc")
```

**Key behaviours:**
- Credibility scores default to 0.50 for any source not explicitly set
- `SourceTracker` stores property-level provenance — so you can trace exactly which source contributed each value

## ConflictAnalyzer

```python
from semantica.conflicts import ConflictAnalyzer

analyzer = ConflictAnalyzer()

analysis     = analyzer.analyze_conflicts(conflicts)
patterns     = analysis["patterns"]
by_severity  = analysis["by_severity"]
source_stats = analysis["by_source"]
trends       = analyzer.analyze_trends(conflicts)

print(f"Trend direction: {trends['direction']}")   # "increasing" | "stable" | "decreasing"
print(f"Change:          {trends['change_pct']:.1f}%")
```

**Key behaviours:**
- `analyze_conflicts()["patterns"]` groups conflicts by attribute name and type — use it to find systemic data quality issues
- `analyze_conflicts()["by_source"]` flags sources with disproportionate conflict rates — a signal that a source's pipeline needs review
- `analyze_trends()` compares conflict counts over time — a rising trend means a data source is degrading

## InvestigationGuideGenerator

Auto-generate human-readable investigation checklists for conflicts requiring manual or expert review:

```python
from semantica.conflicts import InvestigationGuideGenerator

generator = InvestigationGuideGenerator()
guide     = generator.generate_guide(conflict)

print(f"Title:   {guide.title}")
print(f"Context: {guide.context}")

for step in guide.steps:
    print(f"  [{step.order}] ({step.priority.upper()}) {step.description}")
    print(f"             → Verify: {step.check}")
```

## Schemas

<AccordionGroup>
  <Accordion title="Conflict schema">

```python
@dataclass
class Conflict:
    id:            str
    entity_id:     str            # the entity involved
    attribute:     str            # the conflicting property name
    values:        List[str]      # conflicting values (one per source)
    sources:       List[str]      # source IDs for each value
    conflict_type: ConflictType   # VALUE | TYPE | TEMPORAL | LOGICAL | RELATIONSHIP
    severity:      float          # 0.0 (minor) to 1.0 (critical)
    confidence:    float          # detection confidence 0–1
    detected_at:   datetime
    metadata:      Dict[str, Any]
```

  </Accordion>
  <Accordion title="ConflictType enum">

```python
from semantica.conflicts import ConflictType

ConflictType.VALUE_CONFLICT         # revenue is $391B in source A, $383B in source B
ConflictType.TYPE_CONFLICT          # "Apple" is ORGANIZATION in one source, PRODUCT in another
ConflictType.TEMPORAL_CONFLICT      # overlapping validity windows with contradictory states
ConflictType.LOGICAL_CONFLICT       # fact violates an ontology axiom or SHACL constraint
ConflictType.RELATIONSHIP_CONFLICT  # inconsistent relationship properties across sources
```

  </Accordion>
  <Accordion title="InvestigationGuide and InvestigationStep schemas">

```python
@dataclass
class InvestigationGuide:
    title:    str                      # human-readable title for the conflict
    context:  str                      # summary of the disagreement
    steps:    List[InvestigationStep]  # ordered checklist for the reviewer

@dataclass
class InvestigationStep:
    order:       int
    description: str   # what to do
    check:       str   # specific fact or document to verify
    priority:    str   # "high" | "medium" | "low"
```

  </Accordion>
</AccordionGroup>

## Tips and Common Pitfalls

<Warning>
  **Detect before you merge, not after.** Run conflict detection on raw entity data before deduplication and graph construction. Detecting conflicts in a live graph that already contains merged entities is harder — you lose the original source attribution.
</Warning>

<Warning>
  **Always set credibility scores.** The default credibility is 0.50 for all sources. Without explicit scores, `CREDIBILITY_WEIGHTED` behaves identically to `VOTING`. The power of this strategy is in the differentiation.
</Warning>

<Tip>
  **Don't auto-resolve everything.** Use `MANUAL_REVIEW` for conflicts with severity > 0.8 — high severity means the disagreement is large and the stakes of getting it wrong are high.
</Tip>

<Warning>
  **LOGICAL conflicts need a schema.** `detect_type_conflicts()` and `LOGICAL` detection only work if an OWL ontology or SHACL schema is loaded. Without one, `detect_conflicts()` will skip those types silently.
</Warning>

<Tip>
  **Use `analyze_sources()` to identify bad data feeds.** A single source causing 80% of your conflicts is a data quality problem upstream, not a conflict to resolve record by record. Flag it and investigate the source pipeline.
</Tip>

<Tip>
  **Severity is relative, not absolute.** A 0.5 severity score on a $1B revenue discrepancy and on a minor label difference both score 0.5 — the number reflects the disagreement structure, not the business impact. Domain context determines what to prioritize.
</Tip>

<Tip>
  **Combine with provenance.** The `SourceTracker` feeds directly into the [Provenance](provenance) module's audit trail. If you need to explain how a resolved value was chosen, provenance records give you the full chain.
</Tip>

<CardGroup cols={2}>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Resolve duplicate entities before conflict detection.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Logical conflicts use SHACL shapes and ontology axioms.
  </Card>
  <Card title="Provenance" icon="link" href="provenance">
    Track which source each conflicting fact came from.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The graph being checked for conflicts.
  </Card>
</CardGroup>

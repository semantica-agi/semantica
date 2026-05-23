---
title: "Conflicts Module"
description: "Multi-source conflict detection and resolution — value, type, temporal, and logical conflicts with investigation guides."
icon: "triangle-exclamation"
---

`semantica.conflicts` detects and resolves contradictions when multiple sources disagree on the same fact. It surfaces five conflict types, seven resolution strategies, and generates investigation guides for manual review — so conflicts never silently corrupt your knowledge graph.

## What You Get

- **`ConflictDetector`** — value, type, temporal, logical, and relationship conflict detection
- **`ConflictResolver`** — 7 resolution strategies including voting, credibility-weighted, and temporal
- **`SourceTracker`** — track which source each conflicting fact came from, with credibility scores
- **`ConflictAnalyzer`** — pattern analysis, severity grouping, and trend identification
- **`InvestigationGuideGenerator`** — auto-generate step-by-step investigation checklists for human review

## ConflictDetector

```python
from semantica.conflicts import ConflictDetector

detector = ConflictDetector()
conflicts = detector.detect_conflicts(kg)

for conflict in conflicts:
    print(f"[{conflict.conflict_type}] '{conflict.entity}' — {conflict.attribute}")
    print(f"  Sources:  {conflict.sources}")
    print(f"  Severity: {conflict.severity:.2f}")
```

### Detection Types

| Type | What It Detects |
| ---- | --------------- |
| `VALUE` | Same entity, same attribute, different values across sources |
| `TYPE` | Same entity classified as different types in different sources |
| `TEMPORAL` | Overlapping validity windows with contradictory facts |
| `LOGICAL` | Facts that violate ontology axioms or SHACL constraints |
| `RELATIONSHIP` | Inconsistent relationship properties across sources |

Run targeted detection by type:

```python
# Detect all types (default)
conflicts = detector.detect_conflicts(kg)

# Detect specific types only
value_conflicts    = detector.detect_value_conflicts(entities, "name")
type_conflicts     = detector.detect_type_conflicts(entities)
relation_conflicts = detector.detect_relationship_conflicts(kg)
```

## ConflictResolver

```python
from semantica.conflicts import ConflictResolver, ResolutionStrategy

resolver = ConflictResolver()
results = resolver.resolve_conflicts(conflicts, strategy=ResolutionStrategy.VOTING)

for result in results:
    print(f"Resolved '{result.attribute}' → {result.resolved_value}")
    print(f"  Strategy: {result.strategy}")
```

### Resolution Strategies

| Strategy | Enum | Description |
|----------|------|-------------|
| Majority vote | `ResolutionStrategy.VOTING` | Most common value wins |
| Credibility-weighted | `ResolutionStrategy.CREDIBILITY_WEIGHTED` | Weighted by source credibility score |
| Most recent | `ResolutionStrategy.MOST_RECENT` | Prefer the most recently updated fact |
| First seen | `ResolutionStrategy.FIRST_SEEN` | Prefer the first observed value |
| Highest confidence | `ResolutionStrategy.HIGHEST_CONFIDENCE` | Prefer the fact with the highest confidence score |
| Manual review | `ResolutionStrategy.MANUAL_REVIEW` | Flag for human review |
| Expert review | `ResolutionStrategy.EXPERT_REVIEW` | Escalate to a domain expert |

Use the convenience aliases for shorter code:

```python
from semantica.conflicts import voting, credibility_weighted, most_recent, highest_confidence

results = resolver.resolve_conflicts(conflicts, strategy=voting)
```

## Source Credibility Scoring

Assign credibility weights per source so `CREDIBILITY_WEIGHTED` resolution favors authoritative sources:

```python
from semantica.conflicts import SourceTracker

tracker = SourceTracker()
tracker.set_credibility("pubmed",     0.95)
tracker.set_credibility("wikipedia",  0.80)
tracker.set_credibility("user_input", 0.60)

resolver = ConflictResolver(source_tracker=tracker)
results = resolver.resolve_conflicts(
    conflicts,
    strategy=ResolutionStrategy.CREDIBILITY_WEIGHTED
)
```

`SourceTracker` also builds full traceability chains:

```python
from semantica.conflicts import SourceTracker

tracker = SourceTracker()
tracker.track_entity_source("apple_inc", "crunchbase")
tracker.track_property_source("apple_inc", "revenue", "annual_report_2023")

chain = tracker.get_traceability_chain("apple_inc")
```

## ConflictAnalyzer

Identify patterns and trends across large conflict sets:

```python
from semantica.conflicts import ConflictAnalyzer

analyzer = ConflictAnalyzer()

# Detect recurring patterns
patterns = analyzer.identify_patterns(conflicts)
for pattern in patterns:
    print(f"Pattern: {pattern.type} — {pattern.frequency} occurrences")

# Group by severity
by_severity = analyzer.group_by_severity(conflicts)
print(f"Critical: {len(by_severity['critical'])}")
print(f"High:     {len(by_severity['high'])}")
print(f"Low:      {len(by_severity['low'])}")

# Trend analysis over time
trends = analyzer.analyze_trends(conflicts, time_window="30d")
```

## InvestigationGuideGenerator

Auto-generate human-readable investigation guides for conflicts that can't be automatically resolved:

```python
from semantica.conflicts import InvestigationGuideGenerator, InvestigationGuide

generator = InvestigationGuideGenerator()
guide: InvestigationGuide = generator.generate(conflict)

print(guide.title)
print(guide.context)
for step in guide.steps:
    print(f"  [{step.order}] {step.description}")
    print(f"       Check: {step.check}")
```

## Convenience Functions

```python
from semantica.conflicts import (
    detect_conflicts, resolve_conflicts, analyze_conflicts,
    track_sources, generate_investigation_guide
)

conflicts = detect_conflicts(entities, method="value")
resolved  = resolve_conflicts(conflicts, strategy="voting")
analysis  = analyze_conflicts(conflicts, method="pattern")
guide     = generate_investigation_guide(conflicts[0])
```

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

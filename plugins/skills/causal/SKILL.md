---
name: causal
description: Analyze cause-and-effect relationships in the Semantica knowledge graph — causal chains, interventions, counterfactuals, and causal influence scores.
---

# /semantica:causal

Analyze causal relationships and infer impacts. Usage: `/semantica:causal <task> [args]`

`$ARGUMENTS` = task + optional target entity, filter, or intervention.

---

## `chain [--subject <node>] [--depth N]`

Build and inspect causal chains for a subject or category.

```python
from semantica.context.causal_analyzer import CausalChainAnalyzer
from semantica.context import AgentContext

# Option 1: Use an existing AgentContext decision backend
chain = ctx.get_causal_chain(
    decision_id=decision_id,
    direction="upstream",
    max_depth=depth,
)

# Option 2: Use CausalChainAnalyzer directly
analyzer = CausalChainAnalyzer(graph_store=ctx.knowledge_graph)
downstream = analyzer.get_causal_chain(
    decision_id=decision_id,
    direction="downstream",
    max_depth=depth,
)
```

Output: chain steps, cause strength, effect reach, and summary graph.

---

## `intervene <node> <action> [--scenario <json>]`

Analyze decision impact and influenced decisions (current causal API).

```python
analyzer = CausalChainAnalyzer(graph_store=ctx.knowledge_graph)
impact_score = analyzer.get_causal_impact_score(decision_id=decision_id)
influenced = analyzer.get_influenced_decisions(
    decision_id=decision_id,
    max_depth=depth,
)
``` 

Return: impact score, influenced decisions, and downstream scope.

---

## `counterfactual <fact> [--weight N]`

Trace root causes and temporal causal paths.

```python
analyzer = CausalChainAnalyzer(graph_store=ctx.knowledge_graph)
roots = analyzer.find_root_causes(decision_id=decision_id, max_depth=depth)
historical_chain = analyzer.trace_at_time(
    event_id=decision_id,
    at_time="2026-01-01T00:00:00Z",
    direction="upstream",
    max_depth=depth,
)
```

Output: root decision lineage and time-bounded causal context.

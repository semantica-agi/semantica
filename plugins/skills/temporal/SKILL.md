---
name: temporal
description: Temporal graph operations on Semantica — scoped queries at a point in time, graph snapshots, node change timelines, temporal causal analysis, and graph state reconstruction. Uses AgentContext.find_precedents(as_of=), ContextGraph.state_at(), CausalChainAnalyzer.trace_at_time(), and TemporalQueryRewriter. Sub-commands: query, snapshot, timeline, causal-at, precedents-at.
---

# /semantica:temporal

Temporal graph operations. Usage: `/semantica:temporal <sub-command> [args]`

`$ARGUMENTS` = sub-command + query/node + date expression.

---

## `query "<question>" [at|before|after <date>]`

Temporally-scoped natural-language graph query.

```python
from semantica.kg.temporal_query_rewriter import TemporalQueryRewriter
from semantica.kg.temporal_normalizer import TemporalNormalizer

normalizer = TemporalNormalizer()
# Normalize natural date expressions: "last month", "Q3 2024", "2025-01-15"
date = normalizer.normalize(date_expr)

rewriter = TemporalQueryRewriter()
# Rewrite query with temporal constraint
rewritten = rewriter.rewrite(
    query=question,
    temporal_constraint={"op": direction, "value": date},  # op: "at"|"before"|"after"
)
```

Then run the rewritten query through `AgentContext.retrieve()` or `ContextGraph.query()`.

Return ranked results with `Valid From`, `Valid Until`, `Active At <date>` columns. Mark nodes that were not yet created at the target time as `[not yet created]`.

---

## `snapshot <date>`

Reconstruct the full graph state as it existed at a specific point in time.

```python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)

# state_at returns a dict snapshot of the graph at that timestamp
snapshot = graph.state_at(timestamp=date)  # ISO string or datetime
```

Output:
```
Graph snapshot at <date>:
  Nodes:       N  (M added since prev snapshot, K removed)
  Edges:       P
  Density:     0.21
  Communities: Q

Active decision categories at <date>:
  | Category | Count | Avg Confidence |

Top 10 nodes (by degree at <date>):
  | Node | Type | Degree |

[Compact Mermaid graph TD — top-10 most connected nodes at that time]
```

---

## `timeline <node_id>`

Show attribute and relationship changes for a node across its full history.

```python
from semantica.context import ContextGraph

graph = ContextGraph()

# Use state_at() at multiple time points to reconstruct history
# Check add_node timestamps and edge addition times from graph data
node_data = graph.find_node(node_id)
```

Output as Markdown timeline:
```
Timeline for "<node_id>" (<type>):

  <timestamp>  CREATED
    Properties: {confidence: 0.71, category: "loan_approval"}
    Source: extraction/pipeline

  <timestamp>  UPDATED
    confidence: 0.71 → 0.91  [source: review]

  <timestamp>  RELATIONSHIP ADDED
    "<node_id>" →[CAUSED]→ "Decision_B"

  <timestamp>  RELATIONSHIP REMOVED
    "<node_id>" →[PRECEDED_BY]→ "Decision_X"  (superseded)

Total lifespan: <duration>
Current state:  <active|superseded>
```

---

## `causal-at <decision_id> <date> [--direction upstream|downstream]`

Trace a causal chain as it existed at a specific point in time.

```python
from semantica.context.causal_analyzer import CausalChainAnalyzer
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True)
analyzer = CausalChainAnalyzer(graph_store=ctx.graph_store)

historical_chain = analyzer.trace_at_time(
    event_id=decision_id,
    at_time=date,           # ISO string or datetime
    direction=direction or "upstream",
    max_depth=10,
)
```

Output:
```
Historical causal chain for <decision_id> at <date>:
  Direction: upstream (what caused it?)

  [Mermaid graph TD showing chain as it existed at <date>]

  Decisions present then but not now: [list]
  Decisions added since then: [list]
```

---

## `precedents-at "<scenario>" <date> [--category <cat>]`

Find precedent decisions that existed as of a specific date — useful for auditing what context was available when a decision was made.

```python
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True)

# find_precedents supports as_of parameter for temporal precedent search
precedents = ctx.find_precedents(
    scenario=scenario,
    category=category or None,
    limit=10,
    use_hybrid_search=True,
    include_context=True,
    include_superseded=False,
    as_of=date,  # Only return precedents that existed at this date
)
```

Return: `| Rank | Decision ID | Scenario | Outcome | Confidence | Set Date | Valid Until |`

Note decisions that were superseded before or after the target date.

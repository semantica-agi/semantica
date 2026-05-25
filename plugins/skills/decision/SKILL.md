---
name: decision
description: Full decision lifecycle in Semantica — record, query, find precedents (hybrid/advanced), analyze influence, explain, insights dashboard, list, and record exceptions. Uses AgentContext, ContextGraph, DecisionQuery, CausalChainAnalyzer, DecisionRecorder.
---

# /semantica:decision

Full decision lifecycle management. Usage: `/semantica:decision <sub-command> [args]`

---

## `record <category> "<scenario>" "<reasoning>" <outcome> <confidence>`

Record a decision with full context.

```python
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True)
decision_id = ctx.record_decision(
    category=category,        # "loan_approval", "deployment", "hiring"
    scenario=scenario,        # natural-language situation description
    reasoning=reasoning,      # why this decision was made
    outcome=outcome,          # "approved", "rejected", "deferred"
    confidence=float(confidence),
    entities=entities or [],
    decision_maker="ai_agent",
    valid_from=valid_from,    # optional ISO date string
    valid_until=valid_until,
)
```

Output: `Decision <decision_id> recorded | <category> | <outcome> (conf: 0.95)`

---

## `query "<question>" [--hops N] [--hybrid]`

Query decisions using natural language with multi-hop graph traversal.

```python
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True)
results = ctx.query_decisions(
    query=question,
    max_hops=int(hops) if hops else 3,
    include_context=True,
    use_hybrid_search="--hybrid" in args,
)
```

For structured lookups use `DecisionQuery`:
```python
from semantica.context.decision_query import DecisionQuery
dq = DecisionQuery(graph_store=ctx.graph_store)
# dq.find_by_category(category, limit=100)
# dq.find_by_entity(entity_id, limit=100)
# dq.find_by_time_range(start, end, limit=100)
# dq.multi_hop_reasoning(start_entity, query_context, max_hops=3)
# dq.trace_decision_path(decision_id, relationship_types)
# dq.analyze_decision_influence(decision_id, max_depth=3)
```

Return: `| ID | Category | Scenario | Outcome | Confidence | Timestamp |`

---

## `precedents "<scenario>" [--category <cat>] [--advanced] [--hops N] [--as-of <date>]`

Find similar past decisions using hybrid semantic + structural + vector search.

```python
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True, kg_algorithms=True, vector_store_features=True)

if "--advanced" in args:
    precedents = ctx.find_precedents_advanced(
        scenario=scenario, category=category, limit=10,
        use_kg_features=True,
        similarity_weights={"semantic": 0.5, "structural": 0.3, "vector": 0.2},
    )
else:
    precedents = ctx.find_precedents(
        scenario=scenario, category=category, limit=10,
        use_hybrid_search=True,
        max_hops=int(hops) if hops else 3,
        include_context=True,
        include_superseded=False,
        as_of=as_of_date or None,   # temporal filter: only precedents that existed as_of this date
    )
```

Return ranked: `| Rank | ID | Scenario | Outcome | Confidence | Similarity | Date |`

---

## `influence <decision_id> [--depth N]`

Analyze how a decision influences others across the graph.

```python
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True, kg_algorithms=True)
influence = ctx.analyze_decision_influence(decision_id, max_depth=int(depth) if depth else 3)
predictions = ctx.predict_decision_relationships(decision_id, top_k=5)
```

Output: Influence score + influenced decisions table + predicted new relationships.

---

## `explain <decision_id>`

Full explainability trace — reasoning steps, causal antecedents, policy compliance.

```python
from semantica.context import AgentContext, ContextGraph

ctx = AgentContext(decision_tracking=True)
explainability = ctx.trace_decision_explainability(decision_id)

graph = ContextGraph(advanced_analytics=True)
chain = graph.trace_decision_chain(decision_id, max_steps=5)
causality = graph.trace_decision_causality(decision_id, max_depth=5)
```

Output: Reasoning steps, causal antecedents, evidence items, policy compliance status.

---

## `insights`

Comprehensive analytics across all tracked decisions.

```python
from semantica.context import ContextGraph, AgentContext

ctx = AgentContext(decision_tracking=True, advanced_analytics=True)
graph = ContextGraph(advanced_analytics=True)

insights = graph.get_decision_insights()
summary = graph.get_decision_summary()
context_insights = ctx.get_context_insights()
```

Output: Total count, category breakdown, outcome distribution, avg confidence, top influential.

---

## `list [--category <cat>] [--entity <id>] [--from <date>] [--to <date>]`

```python
from semantica.context.decision_query import DecisionQuery
from semantica.context import AgentContext
from datetime import datetime

ctx = AgentContext(decision_tracking=True)
dq = DecisionQuery(graph_store=ctx.graph_store)

if category:    decisions = dq.find_by_category(category, limit=100)
elif entity:    decisions = dq.find_by_entity(entity, limit=100)
elif from_date: decisions = dq.find_by_time_range(
                    start=datetime.fromisoformat(from_date),
                    end=datetime.fromisoformat(to_date or "2099-12-31"),
                )
```

Return: `| ID | Category | Scenario | Outcome | Confidence | Maker | Timestamp |`

---

## `exception <decision_id> <policy_id> "<reason>" --approver <name>`

Record a formal policy exception.

```python
from semantica.context.decision_recorder import DecisionRecorder
from semantica.context import AgentContext

ctx = AgentContext(decision_tracking=True)
recorder = DecisionRecorder(graph_store=ctx.graph_store)

exception_id = recorder.record_exception(
    decision_id=decision_id, policy_id=policy_id,
    reason=reason, approver=approver,
    approval_method="manual_override", justification=reason,
)

from semantica.context.decision_query import DecisionQuery
dq = DecisionQuery(graph_store=ctx.graph_store)
similar = dq.find_similar_exceptions(exception_reason=reason, limit=5)
```

Output: `Exception recorded: <exception_id>` + similar past exceptions for audit context.

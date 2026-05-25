---
name: explain
description: Explain Semantica reasoning, decision logic, and graph results with traceability, causal context, and human-readable rationale.
---

# /semantica:explain

Produce explanations for decisions, rules, and graph analytics. Usage: `/semantica:explain <target> [args]`

`$ARGUMENTS` = explanation target + optional detail level.

---

## `decision <decision_id> [--detail <level>]`

Explain why a decision was reached.

```python
from semantica.reasoning.explanation_generator import ExplanationGenerator

# For decision explainability in Semantica contexts:
decision_trace = ctx.trace_decision_explainability(decision_id=decision_id)

# For reasoning/proof explanations:
generator = ExplanationGenerator(detail_level=detail)
explanation = generator.generate_explanation(reasoning_result)
```

Output: decision factors, rule traces, confidence, and suggested next steps.

---

## `graph <node_id> [--path N]`

Explain graph relationships and why a node is connected.

```python
# Use AgentContext explainability + causal tracing for graph-connected decisions
graph_explanation = ctx.trace_decision_explainability(decision_id=node_id)
upstream = ctx.get_causal_chain(decision_id=node_id, direction="upstream", max_depth=depth)
downstream = ctx.get_causal_chain(decision_id=node_id, direction="downstream", max_depth=depth)
```

Return: cause/effect chains, supporting evidence, and relevant metadata.

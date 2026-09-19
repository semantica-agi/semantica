---
name: policy
description: Define and enforce decision policies, compliance rules, and exceptions over Semantica graphs. Uses ContextGraph.check_decision_rules/enforce_decision_policy and context.PolicyEngine.
---

# /semantica:policy

Policy governance over recorded decisions. Usage: `/semantica:policy <task> [args]`

> `PolicyEngine` lives in `semantica.context`. For most cases the two policy
> methods on `ContextGraph` itself are enough.

---

## `check <decision>` — the simple path

No policy store needed; rules default to a built-in policy set.

```python
from semantica.context import ContextGraph

graph = ContextGraph()
result = graph.check_decision_rules({
    "category": "vendor_selection",
    "outcome": "approved",
    "confidence": 0.93,
    "decision_maker": "gyro",
})
# {'compliant': bool, 'violations': [...], 'warnings': [...], 'policy_rules': {...}}
```

Default rules: `min_confidence=0.7`, `required_outcomes=['approved','rejected','flagged']`,
`required_metadata=['decision_maker']`, `max_reasoning_length=1000`. Override by
passing your own `rules=` dict.

## `enforce <decision> [--rules <dict>]`

```python
verdict = graph.enforce_decision_policy(decision_data, policy_rules=None)
```

---

## Managed policies — the full path

`PolicyEngine` requires a graph store and versioned `Policy` objects.

```python
from semantica.context import PolicyEngine
from semantica.context.decision_models import Policy

engine = PolicyEngine(graph_store)

policy_id = engine.add_policy(Policy(...))
policies  = engine.get_applicable_policies(category="vendor_selection", entities=[...])
ok        = engine.check_compliance(decision, policy_id)
history   = engine.get_policy_history(policy_id)

engine.update_policy(policy_id, rules={...}, change_reason="tightened threshold")
engine.record_exception(decision_id, policy_id, reason="...", approver="...")
impact    = engine.analyze_policy_impact(policy_id, proposed_rules={...})
affected  = engine.get_affected_decisions(policy_id, from_version, to_version)
```

Note `check_compliance` takes a `Decision` object, not a dict — fetch it from the
graph rather than constructing one by hand.

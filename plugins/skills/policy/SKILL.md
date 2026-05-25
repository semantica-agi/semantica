---
name: policy
description: Define and enforce policies, access controls, and compliance rules over Semantica knowledge graphs.
---

# /semantica:policy

Apply policy rules and checks. Usage: `/semantica:policy <task> [args]`

`$ARGUMENTS` = task + optional policy name, rule set, or target entity.

---

## `check [--rule <name>] [--target <id>]`

Run policy checks against the graph.

```python
from semantica.policy import PolicyEngine

engine = PolicyEngine()
result = engine.check(rule_name=rule_name, target=target)
```

Output: compliance status, failing rules, and remediation guidance.

---

## `list`

List available policy rules and categories.

```python
rules = engine.list_rules()
```

Return: rule name, description, severity, and category.

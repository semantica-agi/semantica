# Policy Skill

This skill provides policy-based access control and enforcement for semantic resources.

## Classes

### PolicyEngine

Manages and evaluates policies for controlling access to semantic resources.

**Import:**
```python
from semantica.context import PolicyEngine
```

**Usage:**
```python
from semantica.context import PolicyEngine

# Initialize the PolicyEngine
policy_engine = PolicyEngine()

# Add a policy
policy = policy_engine.create_policy(
    name="read_access",
    effect="allow",
    conditions=[...]
)

# Evaluate a policy against a request
allowed = policy_engine.evaluate_policy(policy, context={...})
```

**Methods:**
- `create_policy(name, effect, conditions)`: Create a new policy
- `evaluate_policy(policy, context)`: Evaluate a policy against a context
- `add_policy(policy)`: Add a policy to the engine
- `remove_policy(policy_name)`: Remove a policy by name
- `get_policies()`: Get all policies

**Example:**
```python
from semantica.context import PolicyEngine

# Create a PolicyEngine instance
engine = PolicyEngine()

# Define a policy for read access
policy = engine.create_policy(
    name="read_access",
    effect="allow",
    conditions=[
        {"action": "read", "resource_type": "ontology"},
        {"action": "read", "resource_type": "triplet"}
    ]
)

# Add the policy to the engine
engine.add_policy(policy)

# Evaluate a request
context = {
    "action": "read",
    "resource_type": "ontology",
    "user": "admin"
}
allowed = engine.evaluate_policy(policy, context)
print(f"Access allowed: {allowed}")  # True
```

## Notes

- The PolicyEngine uses a rule-based evaluation system
- Policies can be defined with conditions and effects (allow/deny)
- The engine supports complex policy combinations and inheritance
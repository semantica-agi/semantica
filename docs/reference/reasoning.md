---
title: "Reasoning Module"
description: "Forward chaining, Rete, deductive, abductive, SPARQL, Datalog, and temporal reasoning with explainable inference paths."
icon: "microchip"
---

`semantica.reasoning` derives new knowledge from existing facts using logical rules. Every engine produces **explainable inference paths** — traceable chains of rules and facts, not black-box conclusions.

## Exported Classes

| Class | Role |
| --- | --- |
| `Reasoner` | IF/THEN forward-chaining facade with variable substitution |
| `GraphReasoner` | Inference over full KG structure (transitivity, symmetry, inverses, property chains) |
| `ReteEngine` | High-performance Rete pattern matching for large rule sets |
| `SPARQLReasoner` | Query expansion and property chain inference over RDF graphs |
| `DatalogReasoner` | Recursive Horn clause rules with guaranteed fixpoint termination |
| `TemporalReasoningEngine` | All 13 Allen interval algebra relations for time-aware inference |
| `ExplanationGenerator` | Structured step-by-step explanations with confidence and reasoning path |
| `Rule` | IF/THEN rule definition: `{conditions, actions, confidence, rule_type}` |
| `InferenceResult` | Result of `infer()` — contains `derived_facts` and metadata |

## Quick Start

The most common pattern: add facts + rules, run inference, explain a conclusion:

```python
from semantica.reasoning import Reasoner, Rule, Fact, RuleType, InferenceResult

reasoner = Reasoner()

reasoner.add_fact(Fact(subject="Alice", predicate="is_a", obj="Manager"))
reasoner.add_rule(Rule(
    rule_type=RuleType.FORWARD_CHAIN,
    conditions=[{"subject": "?x", "predicate": "is_a", "object": "Manager"}],
    conclusion={"subject": "?x", "predicate": "has_authority", "object": "true"},
))

result: InferenceResult = reasoner.infer()
for fact in result.derived_facts:
    print(f"{fact.subject} {fact.predicate} {fact.obj}")
    print(f"  via: {fact.explanation}")
```

<img src="/assets/img/diagrams/reasoning-chain.svg" alt="Forward chaining inference: known facts + IF/THEN rules produce derived facts with a full traceable explanation path" style={{ width: '100%', borderRadius: '12px', margin: '0 0 24px' }} />

## Reasoner (Main Facade)

The unified entry point for rule-based forward-chaining inference:

```python
from semantica.reasoning import Reasoner, Rule, Fact, RuleType

reasoner = Reasoner()

# Add base facts
reasoner.add_fact(Fact(subject="John", predicate="is_a", obj="Manager"))
reasoner.add_fact(Fact(subject="John", predicate="is_a", obj="Employee"))

# Add an IF/THEN rule
reasoner.add_rule(Rule(
    rule_type=RuleType.FORWARD_CHAIN,
    conditions=[
        {"subject": "?x", "predicate": "is_a", "object": "Manager"}
    ],
    conclusion={"subject": "?x", "predicate": "has_authority", "object": "true"}
))

# Run inference
result = reasoner.infer()
for inference in result.derived_facts:
    print(f"{inference.subject} {inference.predicate} {inference.obj}")
    print(f"  Derived via: {inference.explanation}")
```

### Built-In Rule Templates

```python
engine = Reasoner()

# Transitive closure: A→B, B→C ⟹ A→C
engine.apply_transitivity("located_in")

# Symmetry: A knows B ⟹ B knows A
engine.apply_symmetry("knows")

# Inverse: A parent_of B ⟹ B child_of A
engine.apply_inverse("parent_of", "child_of")
```

## GraphReasoner

Inference over the full knowledge graph structure:

```python
from semantica.reasoning import GraphReasoner

graph_reasoner = GraphReasoner(kg)

# Define a transitive ancestor rule
graph_reasoner.add_rule({
    "if": [
        {"subject": "?a", "predicate": "parent_of", "object": "?b"},
        {"subject": "?b", "predicate": "parent_of", "object": "?c"}
    ],
    "then": {"subject": "?a", "predicate": "ancestor_of", "object": "?c"}
})

inferences = graph_reasoner.infer(kg)
for inf in inferences:
    print(f"{inf['subject']} {inf['predicate']} {inf['object']}")
```

## ReteEngine

High-performance pattern matching using the Rete algorithm — far faster than naive forward chaining for large rule sets because it caches partial matches across iterations:

```python
from semantica.reasoning import ReteEngine

engine = ReteEngine()
engine.load_rules("rules/domain_rules.json")
results = engine.run(kg)

# Inspect the Rete network
root        = engine.get_root()
alpha_nodes = engine.get_alpha_nodes()   # single-condition filters
beta_nodes  = engine.get_beta_nodes()    # join nodes
```

Rule format (JSON):

```json
{
  "rules": [
    {
      "name": "manager_authority",
      "conditions": [
        { "subject": "?x", "predicate": "role", "object": "Manager" }
      ],
      "action": { "subject": "?x", "predicate": "has_authority", "object": "true" }
    }
  ]
}
```

## SPARQLReasoner

Query-based inference over RDF graphs with property chain support:

```python
from semantica.reasoning import SPARQLReasoner

reasoner = SPARQLReasoner(graph=rdf_graph)

result = reasoner.query("""
    PREFIX ex: <http://example.org/>
    SELECT ?person ?company WHERE {
        ?person ex:founded ?company .
        ?company ex:located_in ex:SiliconValley .
    }
""")

for row in result.bindings:
    print(row["person"], row["company"])

# Property chain inference: A knows B, B colleague_of C ⟹ A knows C
reasoner.add_property_chain("knows", ["knows", "colleague_of"])
inferences = reasoner.infer_property_chains()
```

## DatalogReasoner (v0.4.0)

Pure-Python bottom-up semi-naive fixpoint evaluation for recursive Horn clause rules. Termination is **guaranteed** — the engine detects fixpoint convergence and stops:

```python
from semantica.reasoning import DatalogReasoner, DatalogFact, DatalogRule

datalog = DatalogReasoner()

# Base facts
datalog.add_fact(DatalogFact("parent", ("alice", "bob")))
datalog.add_fact(DatalogFact("parent", ("bob",   "charlie")))

# Recursive rules (Horn clauses)
datalog.add_rule(DatalogRule("ancestor(?X, ?Y) :- parent(?X, ?Y)."))
datalog.add_rule(DatalogRule("ancestor(?X, ?Z) :- parent(?X, ?Y), ancestor(?Y, ?Z)."))

# Evaluate to fixpoint
datalog.evaluate()

# Query
results = datalog.query("ancestor(alice, ?Z)")
# → [{"Z": "bob"}, {"Z": "charlie"}]
```

## TemporalReasoningEngine

Reason about time intervals using all 13 Allen interval algebra relations:

```python
from semantica.reasoning import TemporalReasoningEngine, TemporalInterval, IntervalRelation

engine = TemporalReasoningEngine()

ceo_tenure  = TemporalInterval(start="1997-09-16", end="2011-08-24")
board_member = TemporalInterval(start="2000-01-01", end="2012-06-01")

relation = engine.get_relation(ceo_tenure, board_member)
# → IntervalRelation.DURING  (ceo_tenure is fully inside board_member)
```

All 13 Allen interval algebra relations are supported:

| Relation | Meaning |
| -------- | ------- |
| `BEFORE` | A ends before B starts |
| `MEETS` | A ends exactly when B starts |
| `OVERLAPS` | A starts before B, ends inside B |
| `DURING` | A is fully inside B |
| `STARTS` | A and B start together, A ends first |
| `FINISHES` | A and B end together, A starts later |
| `EQUALS` | Identical intervals |
| + 6 inverses | `AFTER`, `MET_BY`, `OVERLAPPED_BY`, `CONTAINS`, `STARTED_BY`, `FINISHED_BY` |

## ExplanationGenerator

Generate structured step-by-step explanations for any derived conclusion:

```python
from semantica.reasoning import ExplanationGenerator, Explanation, ReasoningStep

generator = ExplanationGenerator(reasoner)

explanation: Explanation = generator.explain(
    conclusion={"subject": "John", "predicate": "has_authority", "object": "true"}
)

print(f"Conclusion: {explanation.conclusion}")
print(f"Confidence: {explanation.confidence:.2f}")

step: ReasoningStep
for step in explanation.reasoning_path.steps:
    print(f"  Step {step.depth}: {step.fact}")
    print(f"    via rule: '{step.rule_name}'")
```

## Choosing an Engine

| Engine | Best For | Termination | Complexity |
| ------ | -------- | ----------- | ---------- |
| `Reasoner` | Simple IF/THEN rules, templates | Always | Low |
| `GraphReasoner` | KG-wide structural inference | Always | Medium |
| `ReteEngine` | Large rule sets (100+ rules) | Always | Low per-match |
| `SPARQLReasoner` | RDF graphs with SPARQL endpoint | Always | Low |
| `DatalogReasoner` | Recursive rules (ancestry, reachability) | Guaranteed fixpoint | Medium |
| `TemporalReasoningEngine` | Time interval relationships | Always | Low |

<Tip>
  For recursive rules (e.g. ancestor, reachability, transitivity), always use `DatalogReasoner` — it guarantees termination via semi-naive bottom-up fixpoint evaluation. `Reasoner` does not handle recursion.
</Tip>

<CardGroup cols={2}>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The knowledge graph being reasoned over.
  </Card>
  <Card title="Ontology" icon="sitemap" href="ontology">
    Ontology axioms and SHACL constraints for logical reasoning.
  </Card>
  <Card title="Triplet Store" icon="table" href="triplet_store">
    RDF backend for SPARQL-based reasoning.
  </Card>
  <Card title="Context" icon="brain" href="context">
    Reasoning integrated into agent decision intelligence.
  </Card>
</CardGroup>

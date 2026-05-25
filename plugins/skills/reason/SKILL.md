---
name: reason
description: Run reasoning over the Semantica knowledge graph — deductive logic, abductive hypothesis generation, Datalog programs, SPARQL queries, Rete network evaluation. Uses DeductiveReasoner, AbductiveReasoner, DatalogReasoner, SPARQLReasoner, ReteEngine. Sub-commands: deductive, abductive, datalog, sparql, rete, prove, hypotheses.
---

# /semantica:reason

Apply reasoning over the knowledge graph. Usage: `/semantica:reason <mode> [args]`

`$ARGUMENTS` = reasoning mode + rules/observations/query.

---

## `deductive [--facts '<json-list>'] [--rules '<rule1>|<rule2>']`

Apply deductive rules to known facts to derive new conclusions.

```python
from semantica.reasoning.deductive_reasoner import DeductiveReasoner, Premise

reasoner = DeductiveReasoner()

# Add base facts to working memory
# Facts can be strings like "Person(John)" or structured dicts
import json
facts = json.loads(facts_json) if facts_json else []
reasoner.add_facts(facts)

# Apply logic with explicit premises
# Premise objects have: statement, confidence, source
premises = [
    Premise(statement=fact, confidence=1.0)
    for fact in facts
]

conclusions = reasoner.apply_logic(premises=premises)
```

Return: `| Conclusion | Triggering Premises | Confidence | Rule Applied |`

If zero rules given, run `reasoner.prove_theorem()` on any provided theorem:
```python
proof = reasoner.prove_theorem(theorem=theorem_text)
```

Output: `Proof: <proof.steps>  |  Valid: YES / NO`

---

## `prove <theorem> [--facts '<json-list>']`

Prove or disprove a theorem against known facts.

```python
from semantica.reasoning.deductive_reasoner import DeductiveReasoner

reasoner = DeductiveReasoner()
import json
reasoner.add_facts(json.loads(facts_json) if facts_json else [])

proof = reasoner.prove_theorem(theorem=theorem)
```

Output:
```
Theorem: "<theorem>"
Result:  PROVED ✓  |  DISPROVED ✗  |  UNDECIDABLE ⚠

Proof steps:
  1. <premise> — <justification>
  2. ...
  → QED: <theorem>

Confidence: <proof.confidence>
```

---

## `abductive <observation> [--knowledge '<json-list>'] [--top N]`

Generate and rank hypotheses that explain an observation.

```python
from semantica.reasoning.abductive_reasoner import (
    AbductiveReasoner, Observation
)

reasoner = AbductiveReasoner()

import json
if knowledge_json:
    reasoner.add_knowledge(json.loads(knowledge_json))

obs = Observation(description=observation)

# Generate all hypotheses then rank them
hypotheses = reasoner.generate_hypotheses(observations=[obs])
ranked = reasoner.rank_hypotheses(hypotheses)
best = reasoner.get_best_explanation(obs)

# Also get full explanations with evidence
explanations = reasoner.find_explanations(observations=[obs])
```

Output:
```
Abductive Reasoning for: "<observation>"

Best explanation:
  <best.description>  (confidence: 0.87)

All hypotheses (ranked):
  | Rank | Hypothesis | Confidence | Supporting Evidence |
  |  1   | <hyp>      | 0.87       | <evidence>         |
  |  2   | ...

Full explanations:
  Explanation 1: <explanation.summary>
    Evidence: <evidence items>
```

---

## `datalog <program>`

Evaluate a Datalog program over graph facts.

```python
from semantica.reasoning.datalog_reasoner import DatalogReasoner
from semantica.context import ContextGraph

graph = ContextGraph()
reasoner = DatalogReasoner()

# program is a string of Datalog rules and queries
results = reasoner.evaluate(program=program, graph=graph)
```

Return derived tuples as a relation table. Show rule derivation counts.

---

## `sparql <query>`

Run a SPARQL query over the knowledge graph and return results.

```python
from semantica.reasoning.sparql_reasoner import SPARQLReasoner
from semantica.context import ContextGraph

graph = ContextGraph()
reasoner = SPARQLReasoner()

results = reasoner.query(sparql_query=query, graph=graph)
```

Return as a Markdown table with bound variable columns matching the SELECT clause.

---

## `rete [--rules '<rule1>|<rule2>'] [--facts '<json-list>']`

Incremental rule evaluation using the Rete network with working memory.

```python
from semantica.reasoning.rete_engine import ReteEngine
import json

engine = ReteEngine()

rules = rules_str.split("|") if rules_str else []
facts = json.loads(facts_json) if facts_json else []

engine.load_rules(rules)
engine.process_facts(facts)
activations = engine.get_activations()
```

Return: `| Rule Fired | Variable Bindings | Working Memory Delta | Activation Order |`

---

## `hypotheses "<scenario>" [--knowledge '<json-list>'] [--top N]`

Generate the top-N most probable explanations for a complex scenario.

```python
from semantica.reasoning.abductive_reasoner import AbductiveReasoner, Observation
import json

reasoner = AbductiveReasoner()
if knowledge_json:
    reasoner.add_knowledge(json.loads(knowledge_json))

obs = Observation(description=scenario)
hypotheses = reasoner.generate_hypotheses(observations=[obs])
ranked = reasoner.rank_hypotheses(hypotheses)
top_n = ranked[:int(n) if n else 5]
```

For each hypothesis also show: what evidence supports it, what would falsify it, and which is the most parsimonious (fewest assumptions).

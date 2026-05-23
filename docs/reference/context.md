---
title: "Context Module"
description: "Agent context graphs, decision tracking, causal chains, precedent search, and policy enforcement."
icon: "brain"
---

`semantica.context` is the memory and decision layer for AI agents. It stores facts with provenance, records decisions as first-class objects with causal chains, and lets agents search their own history to stay consistent across runs.

## What You Get

- **`AgentContext`** — unified interface for memory, decision tracking, and graph-backed retrieval
- **`ContextGraph`** — persistent knowledge graph with centrality analysis, community detection, and decision management
- **`AgentMemory`** — low-level embedding-backed memory with TTL, tagging, and importance scoring
- **`DecisionRecorder`** — records decisions with causal chains, confidence scores, and outcome tracking
- **`CausalAnalyzer`** — traces downstream impact of any decision
- **`PolicyEngine`** — validates decisions against configurable rules before they're recorded

## AgentContext

The main entry point. Wraps memory, graph, and decision tracking behind a single API.

```python
from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore

context = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    knowledge_graph=ContextGraph(advanced_analytics=True),
    decision_tracking=True,
)
```

### Store and Retrieve Memories

```python
# Store a fact — embedded and indexed automatically
memory_id = context.store(
    "GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%",
    metadata={"source": "openai_blog", "date": "2024-01"}
)

# Retrieve by semantic similarity
results = context.retrieve("LLM benchmark comparisons", top_k=5)
for r in results:
    print(f"{r['content']}  (score: {r['score']:.3f})")
```

### Record and Search Decisions

```python
decision_id = context.record_decision(
    category="model_selection",
    scenario="Choose LLM for production reasoning pipeline",
    reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
    outcome="selected_gpt4",
    confidence=0.91,
)

# Find similar past decisions — prevents inconsistent choices
precedents = context.find_precedents("model selection reasoning", limit=5)

# Analyze downstream impact
influence = context.analyze_decision_influence(decision_id)
print(f"Decisions influenced: {len(influence.downstream_decisions)}")
```

### Multi-Hop GraphRAG

```python
from semantica.llms import Groq

llm    = Groq(model="llama-3.3-70b-versatile")
result = context.query_with_reasoning(
    query="What technologies have we chosen and why?",
    llm_provider=llm,
    max_hops=2,
)

print(result["response"])
for step in result["reasoning_path"]:
    print(f"  {step}")
```

### Constructor Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `vector_store` | `VectorStore` | required | Backend for embedding-based memory retrieval |
| `knowledge_graph` | `ContextGraph` | `None` | Enables graph-backed relationships and analytics |
| `decision_tracking` | `bool` | `False` | Activates `DecisionRecorder` for every decision |
| `graph_expansion` | `bool` | `True` | Auto-expands graph from stored memories |
| `advanced_analytics` | `bool` | `True` | Enables centrality and community analysis |
| `kg_algorithms` | `bool` | `True` | Adds path-finding and link prediction |

### Core Methods

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `store(content, metadata)` | `str` (memory_id) | Embed and store a fact |
| `retrieve(query, top_k)` | `List[Dict]` | Semantic similarity search |
| `record_decision(category, scenario, reasoning, outcome, confidence)` | `str` (decision_id) | Record a decision with full provenance |
| `find_precedents(scenario, category, limit)` | `List[Decision]` | Find similar past decisions |
| `analyze_decision_influence(decision_id)` | `InfluenceResult` | Trace downstream impact |
| `query_with_reasoning(query, llm_provider, max_hops)` | `Dict` | GraphRAG with multi-hop traversal |
| `get_context_insights()` | `Dict` | Analytics summary |

## ContextGraph

The knowledge graph backing `AgentContext`. Can be used standalone for relationship modelling.

```python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)

# Add nodes and edges
graph.add_node("Python",  "language",  properties={"paradigm": "multi-paradigm"})
graph.add_node("FastAPI", "framework", properties={"language": "Python"})
graph.add_edge("Python", "FastAPI", "enables")

# Decision management
decision_id = graph.add_decision_simple(
    category="technology_choice",
    scenario="Web API framework selection",
    reasoning="FastAPI's async support and auto-docs match our requirements",
    outcome="selected_fastapi",
    confidence=0.92,
    entities=["Python", "FastAPI"],
)

similar = graph.find_precedents_by_scenario("web framework", limit=3)
impact  = graph.analyze_decision_impact(decision_id)
chain   = graph.trace_decision_chain(decision_id)
```

### ContextGraph Constructor Options

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `advanced_analytics` | `bool` | `False` | PageRank, betweenness centrality |
| `centrality_analysis` | `bool` | `False` | Full centrality suite |
| `community_detection` | `bool` | `False` | Louvain community clustering |
| `node_embeddings` | `bool` | `False` | Node2Vec embeddings for structural similarity |

## Decision Data Structure

```python
@dataclass
class Decision:
    decision_id:    str
    category:       str
    scenario:       str
    reasoning:      str
    outcome:        str
    confidence:     float       # 0.0 – 1.0
    decision_maker: str
    timestamp:      datetime
    entities:       List[str]
    metadata:       Dict
    causal_chain:   List[str]   # IDs of related decisions
```

## AgentMemory (Low-Level)

For fine-grained control over memory storage, TTL, and importance scoring:

```python
from semantica.context import AgentMemory

memory = AgentMemory(
    vector_store=VectorStore(backend="faiss", dimension=768),
    max_memories=10_000,
    ttl_days=90,
)

memory.store("Important fact", importance=0.9, tags=["compliance"])
results = memory.retrieve("fact query", top_k=5, min_importance=0.5)
memory.forget(memory_id)
```

## PolicyEngine

Validate decisions against configurable rules before they're committed:

```python
from semantica.context import PolicyEngine

policy = PolicyEngine()
policy.add_rule("confidence_threshold", lambda d: d.confidence >= 0.7)
policy.add_rule("requires_reasoning",   lambda d: len(d.reasoning) >= 20)

# Validate before recording
is_valid, violations = policy.validate(decision_data)
if is_valid:
    context.record_decision(**decision_data)
```

## Real-World Patterns

### Healthcare — Treatment Decisions

```python
health_agent = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    decision_tracking=True,
)

health_agent.store("Patient has hypertension, type 2 diabetes")
health_agent.store("Patient allergic to penicillin — verified 2024-01")

decision_id = health_agent.record_decision(
    category="treatment_plan",
    scenario="Hypertension with comorbid diabetes",
    reasoning="ACE inhibitors are renoprotective in diabetic patients — preferred over beta blockers",
    outcome="prescribed_lisinopril",
    confidence=0.91,
)

# Check for similar cases
precedents = health_agent.find_precedents("hypertension diabetes", limit=5)
```

### Finance — Loan Decisions

```python
loan_agent = AgentContext(
    vector_store=VectorStore(backend="faiss", dimension=768),
    decision_tracking=True,
)

loan_agent.store("Applicant: credit score 750, DTI 28%, stable employment 4yr")

decision_id = loan_agent.record_decision(
    category="loan_approval",
    scenario="First-time homebuyer — 30yr fixed, 20% down",
    reasoning="Credit score above threshold, DTI within limits, stable income verified",
    outcome="approved_300k",
    confidence=0.94,
)
```

<CardGroup cols={2}>
  <Card title="Vector Store" icon="database" href="vector_store">
    Embedding storage backend for memory retrieval.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    Graph algorithms and analytics used inside ContextGraph.
  </Card>
  <Card title="Reasoning" icon="microchip" href="reasoning">
    Logical inference layered on top of context.
  </Card>
  <Card title="Provenance" icon="link" href="provenance">
    W3C PROV-O lineage for every stored fact.
  </Card>
</CardGroup>

### Cookbooks

- [Context Module](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/19_Context_Module.ipynb) — memory and decision tracking · Intermediate
- [Advanced Context Engineering](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/11_Advanced_Context_Engineering.ipynb) — production FAISS + Neo4j setup · Advanced
- [Decision Tracking with KG Algorithms](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/12_Decision_Tracking_KG.ipynb) — precedent search, policy enforcement · Advanced

---
title: "Context Module"
description: "Agent context graphs, decision tracking, causal chains, precedent search, policy enforcement, and multi-hop GraphRAG."
icon: "brain"
---

`semantica.context` is the memory and decision layer for AI agents. It stores facts with provenance, records decisions as first-class objects with full causal chains, lets agents search their own history to stay consistent across runs, and answers complex queries by traversing the knowledge graph.

## Exported Classes

| Class | Role |
| --- | --- |
| `AgentContext` | Primary entry point — memory, retrieval, decisions, graph traversal, checkpoints |
| `ContextGraph` | In-memory knowledge graph with centrality, community detection, and decision tracking |
| `AgentMemory` | RAG-backed persistent memory: `store(text)`, `retrieve(query, max_results)` |
| `EntityLinker` | Link entity mentions to canonical URIs across multiple sources |
| `ContextRetriever` | Hybrid vector + graph retrieval with min-score and temporal decay options |
| `DecisionRecorder` | Record decisions with embeddings, causal chains, and metadata |
| `PolicyEngine` | Compliance checking: `check_compliance()`, `get_applicable_policies()` |
| `CausalChainAnalyzer` | Trace how decisions influenced each other: `get_causal_chain(decision_id)` |

## What You Get

<CardGroup cols={2}>
  <Card title="AgentContext" icon="brain">
    Unified interface for memory, decision tracking, graph-backed retrieval, conversation history, checkpoints, and persistence.
  </Card>
  <Card title="ContextGraph" icon="diagram-project">
    Thread-safe in-memory knowledge graph with centrality analysis, community detection, temporal validity, cross-graph links, and decision management.
  </Card>
  <Card title="AgentMemory" icon="database">
    Embedding-backed memory with TTL, tagging, importance scoring, and LRU eviction.
  </Card>
  <Card title="DecisionRecorder" icon="list-check">
    Records decisions with causal chains, confidence scores, temporal validity windows, and cross-system context capture.
  </Card>
  <Card title="PolicyEngine" icon="shield-check">
    Validates decisions against configurable lambda rules before they're recorded; creates approval chains for human-in-the-loop gating.
  </Card>
  <Card title="EntityLinker" icon="link">
    Maps entity mentions to canonical URIs — prevents "Apple", "Apple Inc.", and "AAPL" from becoming three separate nodes.
  </Card>
  <Card title="ContextRetriever" icon="magnifying-glass">
    Hybrid retrieval fusing vector similarity, graph traversal, and agent memory for richer context than pure vector search.
  </Card>
  <Card title="CausalChainAnalyzer" icon="arrow-trend-up">
    Traces upstream causes and downstream effects of any decision through the knowledge graph.
  </Card>
</CardGroup>

<img src="/assets/img/diagrams/agent-context-flow.svg" alt="AgentContext hub: AI Agent calls store/retrieve against VectorStore and record_decision against ContextGraph" style={{ width: '100%', borderRadius: '12px', margin: '0 0 24px' }} />

## Quick Start

<Steps>
  <Step title="Initialize the agent context">
    ```python
    from semantica.context import AgentContext, ContextGraph
    from semantica.vector_store import VectorStore

    context = AgentContext(
        vector_store=VectorStore(backend="faiss", dimension=768, index_path="context.faiss"),
        knowledge_graph=ContextGraph(advanced_analytics=True),
        decision_tracking=True,
        retention_days=90,      # auto-expire memories older than 90 days
        max_memories=50_000,
    )
    ```
  </Step>
  <Step title="Store facts and retrieve by semantic similarity">
    ```python
    memory_id = context.store(
        "GPT-4 outperforms GPT-3.5 on reasoning benchmarks by 40%",
        metadata={"source": "openai_blog", "date": "2024-01"}
    )

    results = context.retrieve("LLM benchmark comparisons", max_results=5)
    for r in results:
        print(f"{r['content']}  (score: {r['score']:.3f})")
    ```
  </Step>
  <Step title="Record decisions with full provenance">
    ```python
    decision_id = context.record_decision(
        category="model_selection",
        scenario="Choose LLM for production reasoning pipeline",
        reasoning="GPT-4 benchmark advantage justifies 3x cost increase",
        outcome="selected_gpt4",
        confidence=0.91,
        entities=["gpt-4", "gpt-3.5"],
        decision_maker="pipeline_agent",
    )
    ```
  </Step>
  <Step title="Find precedents and trace causal chains">
    ```python
    # Search past decisions — prevents contradictory choices across runs
    precedents = context.find_precedents("model selection reasoning", limit=5)
    for p in precedents:
        print(f"[{p.category}] {p.outcome}  (confidence: {p.confidence:.2f})")
        print(f"  Reasoning: {p.reasoning}")

    # Trace what downstream decisions were influenced by this one
    chain = context.get_causal_chain(decision_id, direction="downstream", max_depth=5)
    print(f"Downstream decisions: {len(chain)}")

    # Full explainability — upstream causes + downstream effects + relationship paths
    explanation = context.trace_decision_explainability(decision_id)
    print(f"Total connections: {explanation['total_connections']}")
    ```
  </Step>
</Steps>

## AgentContext

The main entry point. Wraps memory, graph, and decision tracking behind a single API.

### Constructor Parameters

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `vector_store` | `VectorStore` | **required** | Backend for embedding-based memory retrieval |
| `knowledge_graph` | `ContextGraph` | `None` | Enables graph-backed relationships and GraphRAG |
| `decision_tracking` | `bool` | `False` | Activates `DecisionRecorder` for every decision |
| `retention_days` | `Optional[int]` | `30` | Auto-expire memories older than N days; `None` = keep forever |
| `max_memories` | `int` | `10000` | Hard cap before LRU eviction |
| `graph_expansion` | `bool` | `True` | Auto-expands graph from stored memories |
| `max_expansion_hops` | `int` | `2` | Max hops for graph expansion during retrieval |
| `hybrid_alpha` | `float` | `0.5` | Balance between vector (`0.0`) and graph (`1.0`) retrieval |
| `advanced_analytics` | `bool` | `True` | Enables PageRank, centrality, and community analysis |
| `kg_algorithms` | `bool` | `True` | Adds path-finding and link prediction |

### Memory Methods

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `store(content, metadata, conversation_id, user_id)` | `str` | Embed and store a fact or list of facts |
| `batch_store(items)` | `List[str]` | Store multiple items at once — returns list of memory IDs |
| `retrieve(query, max_results, min_score, use_graph, conversation_id)` | `List[Dict]` | Semantic retrieval; auto-selects GraphRAG if `knowledge_graph` is set |
| `forget(memory_id, conversation_id, days_old)` | `int` | Delete memories by ID, conversation, or age |
| `update(memory_id, content, metadata)` | `bool` | Update content or metadata of a stored memory |
| `get_memory(memory_id)` | `Optional[Dict]` | Fetch a specific memory by ID |
| `stats()` | `Dict` | Memory counts, vector store status, graph stats |
| `health()` | `Dict` | System health — all backends, status flags |
| `save(path)` | `None` | Persist full context state (memory + graph) to disk |
| `load(path)` | `None` | Restore context state from disk |
| `export(conversation_id, format)` | `str \| Dict` | Export memories as JSON or dict |
| `import_data(data, format)` | `int` | Import memories from JSON or dict |

### Conversation Methods

```python
# Store turns in a conversation thread
context.store("User asked about deployment options", conversation_id="conv_001")
context.store("Agent recommended Docker + Kubernetes", conversation_id="conv_001")

# Retrieve full conversation history
history = context.conversation("conv_001", max_items=50)
for turn in history:
    print(f"[{turn['timestamp']}] {turn['content']}")

# Retrieve across all conversations with a query
results = context.retrieve("deployment recommendations", conversation_id="conv_001", max_results=10)
```

### Multi-Hop GraphRAG

Requires `knowledge_graph` to be set at construction:

```python
from semantica.llms import Groq

llm    = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
result = context.query_with_reasoning(
    query="What technologies have we chosen and why?",
    llm_provider=llm,
    max_hops=2,
    max_results=10,
)

print(result["response"])
print(f"Confidence: {result['confidence']:.2f}")
print(f"Sources used: {result['num_sources']}")
```

### Decision Methods

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `record_decision(category, scenario, reasoning, outcome, confidence, entities, decision_maker, valid_from, valid_until)` | `str` | Record a decision; raises `RuntimeError` if `decision_tracking=False` |
| `find_precedents(scenario, category, limit, use_hybrid_search, max_hops, as_of)` | `List[Decision]` | Find similar past decisions by semantic + structural similarity |
| `query_decisions(query, max_hops, use_hybrid_search)` | `List[Decision]` | Broad context-aware decision search |
| `get_causal_chain(decision_id, direction, max_depth)` | `List[Decision]` | Trace `"upstream"` causes or `"downstream"` effects |
| `trace_decision_explainability(decision_id)` | `Dict` | Full explainability — causes, effects, relationship paths |
| `get_policy_engine()` | `PolicyEngine` | Access the active `PolicyEngine` instance |

### Checkpoint Methods

Useful for detecting what changed across reasoning runs:

```python
# Take a named snapshot of the current graph state
context.checkpoint("before_inference")

# ... run reasoning, record decisions ...

context.checkpoint("after_inference")

# See exactly what was added/removed
diff = context.diff_checkpoints("before_inference", "after_inference")
print(f"Decisions added: {len(diff['decisions_added'])}")
print(f"Relationships added: {len(diff['relationships_added'])}")

# Persist a checkpoint to disk via TemporalVersionManager
context.flush_checkpoint("after_inference")
```

## ContextGraph

The knowledge graph backing `AgentContext`. Can also be used standalone for relationship modelling.

```python
from semantica.context import ContextGraph

graph = ContextGraph(advanced_analytics=True)

# Build the graph
graph.add_node("Python",  "language",  properties={"paradigm": "multi-paradigm"})
graph.add_node("FastAPI", "framework", properties={"language": "Python"})
graph.add_edge("Python", "FastAPI", "enables")

# Record and query decisions directly on the graph
decision_id = graph.record_decision(
    category="technology_choice",
    scenario="Web API framework selection",
    reasoning="FastAPI's async support and auto-docs match our requirements",
    outcome="selected_fastapi",
    confidence=0.92,
    entities=["Python", "FastAPI"],
)

similar = graph.find_precedents_by_scenario("web framework", limit=3)
stats   = graph.stats()
print(f"Nodes: {stats['node_count']}, Edges: {stats['edge_count']}")
```

### Constructor Options

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `advanced_analytics` | `bool` | `False` | PageRank, betweenness centrality |
| `centrality_analysis` | `bool` | `False` | Full centrality suite |
| `community_detection` | `bool` | `False` | Louvain community clustering |
| `node_embeddings` | `bool` | `False` | Node2Vec embeddings for structural similarity |
| `enable_causality` | `bool` | `False` | Causal chain tracking between decision nodes |

### ContextGraph — Full Method Reference

| Method | Returns | Description |
| ------ | ------- | ----------- |
| `add_node(node_id, node_type, properties, valid_from, valid_until)` | `None` | Add a node; supports temporal validity windows |
| `add_edge(source_id, target_id, edge_type, weight, properties)` | `None` | Add a directed edge with optional weight |
| `add_nodes(nodes)` | `int` | Bulk-add from a list of dicts; returns count added |
| `add_edges(edges)` | `int` | Bulk-add edges; returns count added |
| `get_neighbors(node_id, hops)` | `List[Dict]` | BFS neighbors up to given depth |
| `get_neighbor_distances(node_id, hops)` | `List[Dict]` | Neighbors with confidence-decay scoring |
| `find_node(node_id)` | `Optional[Dict]` | Look up a single node by ID |
| `find_nodes(node_type, skip, limit)` | `List[Dict]` | Filter nodes by type with pagination |
| `find_active_nodes(node_type, at_time)` | `List[Dict]` | Nodes that are valid at a given timestamp |
| `find_edges(edge_type, skip, limit)` | `List[Dict]` | Filter edges by type with pagination |
| `record_decision(category, scenario, reasoning, outcome, confidence, entities, decision_maker)` | `str` | Add decision node with causal edges |
| `find_precedents_by_scenario(scenario, category, limit, use_semantic_search, as_of)` | `List[Dict]` | Semantically similar past scenarios |
| `query(query, skip, limit)` | `List[Dict]` | Full-text search over node content |
| `stats()` | `Dict` | Node/edge counts, type breakdowns, graph density |
| `density()` | `float` | Graph density score |
| `save_to_file(path)` | `None` | Persist graph to JSON |
| `load_from_file(path)` | `None` | Load graph from JSON |
| `build_from_conversations(conversations, link_entities)` | `Dict` | Build graph from conversation data |
| `link_graph(other_graph, source_node_id, target_node_id, link_type)` | `str` | Create cross-graph navigation link; returns `link_id` |
| `navigate_to(link_id)` | `Tuple[ContextGraph, str]` | Follow a cross-graph link to `(target_graph, target_node_id)` |
| `cross_graph_path(source_node_id, target_graph, target_node_id, max_hops)` | `Dict` | Shortest path across linked graphs |
| `resolve_links(graphs)` | `int` | Reconnect cross-graph links after `load_from_file` |
| `clear()` | `None` | Reset graph state and all indexes |

### Cross-Graph Navigation

Link multiple independent `ContextGraph` instances so agents can traverse across problem spaces:

```python
domain_graph    = ContextGraph()
decision_graph  = ContextGraph()

domain_graph.add_node("microservices", "architecture", properties={"style": "distributed"})
decision_graph.add_node("deploy_k8s",  "decision",     properties={"outcome": "approved"})

link_id = domain_graph.link_graph(
    other_graph=decision_graph,
    source_node_id="microservices",
    target_node_id="deploy_k8s",
    link_type="INFORMED_BY",
)

# Follow the link at traversal time
target_graph, entry_node = domain_graph.navigate_to(link_id)

# Cross-graph pathfinding
path = domain_graph.cross_graph_path(
    source_node_id="microservices",
    target_graph=decision_graph,
    target_node_id="deploy_k8s",
    max_hops=5,
)
print(f"Reachable: {path['reachable']}, hops: {path['hop_count']}")
```

## AgentMemory (Low-Level)

For fine-grained control over memory storage, TTL, and importance scoring:

```python
from semantica.context import AgentMemory
from semantica.vector_store import VectorStore

memory = AgentMemory(
    vector_store=VectorStore(backend="faiss", dimension=768),
    capacity=10_000,
    ttl_days=90,
)

memory_id = memory.store(
    "Critical compliance rule: all trades must be pre-approved",
    importance=0.95,
    tags=["compliance", "trading"],
)

results = memory.retrieve(
    query="trade approval requirements",
    max_results=5,
    min_importance=0.5,
    tags=["compliance"],
)

memory.update(memory_id, importance=1.0)
memory.forget(memory_id)
all_memories = memory.get_all()
```

| Parameter | Type | Default | Description |
| --------- | ---- | ------- | ----------- |
| `vector_store` | `VectorStore` | **required** | Embedding backend for semantic retrieval |
| `capacity` | `int` | `1000` | Max items before LRU eviction |
| `ttl_days` | `Optional[int]` | `None` | Days before automatic expiry; `None` = keep forever |

## PolicyEngine

Validate decisions against configurable rules before they're committed:

```python
from semantica.context import PolicyEngine

policy = PolicyEngine()
policy.add_rule("confidence_threshold", lambda d: d.confidence >= 0.7)
policy.add_rule("requires_reasoning",   lambda d: len(d.reasoning) >= 20)

is_valid, violations = policy.validate(decision_data)

if is_valid:
    context.record_decision(**decision_data)
else:
    # Create approval chain for human-in-the-loop review
    chain = policy.create_approval_chain(
        decision_data,
        approvers=["manager@company.com", "compliance@company.com"],
    )
    print(f"Approval chain created: {chain.chain_id}")
```

## EntityLinker

Maps extracted entity mentions to canonical URIs — essential for cross-document entity resolution:

```python
from semantica.context import EntityLinker

linker = EntityLinker()

entities = [
    {"text": "Apple Inc.", "type": "ORGANIZATION"},
    {"text": "Apple",      "type": "ORGANIZATION"},
    {"text": "AAPL",       "type": "ORGANIZATION"},
]
linked = linker.link_entities(entities, sources=["reuters", "sec_filings"])

for e in linked:
    print(f"{e.text} → {e.canonical_form}  ({e.uri})")
    print(f"  confidence: {e.confidence:.2f}, sources: {e.sources}")
```

## ContextRetriever

Hybrid retrieval combining vector similarity, graph traversal, and memory — surfaces results that pure vector search misses:

```python
from semantica.context import ContextRetriever

retriever = ContextRetriever(
    vector_store=vector_store,
    context_graph=context_graph,
    agent_memory=memory,
)

results = retriever.retrieve(
    query="What decisions were made about cloud infrastructure?",
    max_results=10,
    use_graph_expansion=True,
    min_relevance_score=0.3,
)

for r in results:
    print(f"[{r['source']}] score={r['score']:.3f}: {r['content'][:80]}")
```

## Data Structures

<AccordionGroup>
  <Accordion title="Decision">

```python
@dataclass
class Decision:
    decision_id:    str
    category:       str
    scenario:       str
    reasoning:      str
    outcome:        str
    confidence:     float               # 0.0 – 1.0
    decision_maker: str                 # default: "ai_agent"
    timestamp:      datetime
    valid_from:     Optional[str]       # ISO datetime — temporal validity start
    valid_until:    Optional[str]       # ISO datetime — temporal validity end
    metadata:       Dict[str, Any]      # arbitrary key/value store
```

  </Accordion>
  <Accordion title="Precedent">

```python
@dataclass
class Precedent:
    decision_id:    str
    similarity:     float               # 0–1 match score against queried scenario
    category:       str
    scenario:       str
    outcome:        str
    reasoning:      str
    confidence:     float
    timestamp:      datetime
```

  </Accordion>
  <Accordion title="Policy">

```python
@dataclass
class Policy:
    policy_id:      str
    name:           str
    description:    str
    rules:          List[Dict]          # list of rule definitions
    active:         bool
    created_at:     datetime
    version:        int
```

  </Accordion>
  <Accordion title="PolicyException">

```python
@dataclass
class PolicyException:
    exception_id:   str
    policy_rule:    str                 # name of the violated rule
    decision_id:    str                 # decision that triggered the exception
    justification:  str                 # why the exception was granted
    approved_by:    str                 # approver identity
    timestamp:      datetime
    expiry:         Optional[datetime]
```

  </Accordion>
  <Accordion title="ApprovalChain">

```python
@dataclass
class ApprovalChain:
    chain_id:       str
    decision_id:    str
    steps:          List[ApprovalStep]
    status:         str                 # "pending" | "approved" | "rejected"
    created_at:     datetime

@dataclass
class ApprovalStep:
    step_id:        str
    approver:       str
    required:       bool
    status:         str                 # "pending" | "approved" | "rejected"
    comment:        Optional[str]
    timestamp:      Optional[datetime]
```

  </Accordion>
  <Accordion title="LinkedEntity">

```python
@dataclass
class LinkedEntity:
    text:           str
    canonical_form: str                 # normalized primary name
    uri:            str                 # e.g. "http://dbpedia.org/resource/Apple_Inc."
    confidence:     float
    sources:        List[str]           # source documents that mention this entity
    aliases:        List[str]           # all observed surface forms
```

  </Accordion>
</AccordionGroup>

## Real-World Patterns

<Tabs>
  <Tab title="Healthcare — Treatment Decisions">
    ```python
    from semantica.context import AgentContext
    from semantica.vector_store import VectorStore

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

    precedents = health_agent.find_precedents("hypertension diabetes", limit=5)
    for p in precedents:
        print(f"Past decision: {p.outcome}  (confidence: {p.confidence:.2f})")

    chain = health_agent.get_causal_chain(decision_id, direction="downstream")
    print(f"Follow-up decisions triggered: {len(chain)}")
    ```
  </Tab>
  <Tab title="Finance — Loan Decisions">
    ```python
    from semantica.context import AgentContext, PolicyEngine
    from semantica.vector_store import VectorStore

    policy = PolicyEngine()
    policy.add_rule("min_confidence",  lambda d: d["confidence"] >= 0.8)
    policy.add_rule("has_reasoning",   lambda d: len(d["reasoning"]) >= 30)

    loan_agent = AgentContext(
        vector_store=VectorStore(backend="faiss", dimension=768),
        decision_tracking=True,
    )

    loan_agent.store("Applicant: credit score 750, DTI 28%, stable employment 4yr")

    decision_data = dict(
        category="loan_approval",
        scenario="First-time homebuyer — 30yr fixed, 20% down",
        reasoning="Credit score above threshold, DTI within limits, stable income verified",
        outcome="approved_300k",
        confidence=0.94,
    )

    is_valid, violations = policy.validate(decision_data)
    if is_valid:
        decision_id = loan_agent.record_decision(**decision_data)
    else:
        chain = policy.create_approval_chain(decision_data, approvers=["underwriter@bank.com"])
        print(f"Sent for review: {chain.chain_id}")
    ```
  </Tab>
  <Tab title="Persist & Restore">
    ```python
    context = AgentContext(
        vector_store=VectorStore(backend="faiss", dimension=768, index_path="ctx.faiss"),
        knowledge_graph=ContextGraph(),
        decision_tracking=True,
    )

    context.store("Important fact learned during session")
    context.record_decision(
        category="ops", scenario="Scale up", reasoning="Load > 80%",
        outcome="scaled_to_10_replicas", confidence=0.97,
    )

    # Persist everything
    context.save("agent_state/")

    # Later — restore and continue
    restored = AgentContext(
        vector_store=VectorStore(backend="faiss", dimension=768, index_path="ctx.faiss"),
        knowledge_graph=ContextGraph(),
        decision_tracking=True,
    )
    restored.load("agent_state/")

    results = restored.retrieve("load scaling decisions", max_results=3)
    ```
  </Tab>
</Tabs>

## Tips and Common Pitfalls

<Warning>
  **Persist your vector store between runs.** Pass `index_path="context.faiss"` to `VectorStore` — without it the FAISS index lives only in memory and is lost on shutdown. An agent that forgets everything on restart isn't an agent.
</Warning>

<Warning>
  **Enable `decision_tracking=True` from the start.** Adding it retroactively means historical decisions are not linked to the causal chain — you lose the ability to trace how one decision influenced later ones. Enable it at initialization, even if you're not using it immediately.
</Warning>

<Tip>
  **Use `find_precedents()` before every significant decision.** This is how the context module prevents agents from making contradictory choices across runs. Surface precedents to the LLM as context: "we chose X for similar reasons before."
</Tip>

<Tip>
  **`retrieve()` uses `max_results=`, not `top_k=`.** The parameter is `max_results` (default `5`). Pass `use_graph=True` to force GraphRAG or `use_graph=False` to force vector-only retrieval regardless of whether a `knowledge_graph` is configured.
</Tip>

<Tip>
  **Set `retention_days` to avoid memory bloat.** Without it `AgentMemory` accumulates indefinitely (the default `AgentContext.retention_days=30` prunes automatically). Compliance-critical agents may need `retention_days=None` with explicit archival via `export()`.
</Tip>

<Warning>
  **Gate irreversible decisions with `PolicyEngine`.** Decisions recorded with `record_decision()` become part of the causal chain immediately. Validate first with `policy.validate()` and create an `ApprovalChain` for human review — don't record until approved.
</Warning>

<Tip>
  **Use `checkpoint()` + `diff_checkpoints()` to audit reasoning loops.** Take a snapshot before and after a reasoning pass to see exactly which decisions and relationships were added. This is the cleanest way to detect divergent agent behaviour across runs.
</Tip>

<Tip>
  **`EntityLinker` prevents graph proliferation.** Without it, "Apple", "Apple Inc.", and "AAPL" land as three separate nodes. Run `EntityLinker.link_entities()` on mentions before storing them to maintain a canonical graph.
</Tip>

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

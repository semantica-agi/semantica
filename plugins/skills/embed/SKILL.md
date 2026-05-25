---
name: embed
description: Generate, inspect, and use node/text embeddings in Semantica — compute Node2Vec embeddings, find similar nodes, score link predictions, batch similarity, and pairwise similarity. Uses NodeEmbedder, SimilarityCalculator, LinkPredictor, and AgentContext. Sub-commands: compute, similar, similarity, predict-link, top-links, batch, pairwise.
---

# /semantica:embed

Generate and inspect graph embeddings. Usage: `/semantica:embed <sub-command> [args]`

`$ARGUMENTS` = sub-command + arguments.

---

## `compute [--labels <t1,t2>] [--rels <r1,r2>] [--dim N] [--walks N]`

Generate Node2Vec embeddings for graph nodes.

```python
from semantica.kg.node_embeddings import NodeEmbedder
from semantica.context import ContextGraph

graph = ContextGraph()
embedder = NodeEmbedder()

node_labels = labels_arg.split(",") if labels_arg else graph.get_all_node_types()
rel_types = rels_arg.split(",") if rels_arg else []

# All positional args required: graph_store, node_labels, relationship_types
embeddings = embedder.compute_embeddings(
    graph_store=graph,
    node_labels=node_labels,
    relationship_types=rel_types,
    embedding_dimension=int(dim_arg) if dim_arg else None,
    num_walks=int(walks_arg) if walks_arg else None,
)

# Store embeddings back on nodes
embedder.store_embeddings(
    graph_store=graph,
    embeddings=embeddings,
    property_name="node2vec_embedding",
)
```

Output:
```
Embeddings computed and stored.
  Nodes embedded:     N
  Embedding dim:      128
  Node types covered: [type1, type2, ...]
  
Sample (first 5 nodes):
  | Node | Type | Embedding dim | Stored |
```

---

## `similar <node_id> [--top N]`

Find the most similar nodes to a given node in embedding space.

```python
from semantica.kg.node_embeddings import NodeEmbedder
from semantica.context import ContextGraph, AgentContext

graph = ContextGraph()
embedder = NodeEmbedder()

# NodeEmbedder.find_similar_nodes uses the stored node2vec_embedding property
neighbors = embedder.find_similar_nodes(
    graph_store=graph,
    node_id=node_id,
    top_k=int(top_n) if top_n else 10,
    embedding_property="node2vec_embedding",
)

# Also use AgentContext for richer similarity with metadata
ctx = AgentContext(kg_algorithms=True)
entity_similar = ctx.find_similar_entities(
    entity_id=node_id,
    similarity_type="content",  # or "structural", "hybrid"
    top_k=int(top_n) if top_n else 10,
)
```

Return: `| Rank | Node ID | Type | Cosine Similarity | Shared Properties |`

---

## `similarity <n1> <n2> [--method cosine|euclidean|manhattan|correlation]`

Compute pairwise similarity between two nodes.

```python
from semantica.kg.similarity_calculator import SimilarityCalculator
from semantica.kg.node_embeddings import NodeEmbedder
from semantica.context import ContextGraph

graph = ContextGraph()
embedder = NodeEmbedder()
calc = SimilarityCalculator()

# Get embeddings for both nodes
v1 = embedder.find_similar_nodes(graph, n1, top_k=1)  # placeholder — use stored embedding
v2 = embedder.find_similar_nodes(graph, n2, top_k=1)

method = method_arg or "cosine"
if method == "cosine":
    score = calc.cosine_similarity(vector1=v1, vector2=v2)
elif method == "euclidean":
    score = calc.euclidean_distance(v1, v2)
elif method == "manhattan":
    score = calc.manhattan_distance(v1, v2)
elif method == "correlation":
    score = calc.correlation_similarity(v1, v2)
```

Output:
```
Similarity: "<n1>" ↔ "<n2>"
  Method:  cosine
  Score:   0.847

  Interpretation: HIGH similarity (>0.8)
  Shared neighbors:   K
  Common node types:  [types]
```

---

## `predict-link <n1> <n2> [--method cosine|jaccard|adamic-adar|common-neighbors]`

Score the likelihood of a relationship between two nodes.

```python
from semantica.kg.link_predictor import LinkPredictor
from semantica.context import ContextGraph

graph = ContextGraph()
predictor = LinkPredictor()

# score_link(graph_store, node_id1, node_id2, method=)
score = predictor.score_link(
    graph_store=graph,
    node_id1=n1,
    node_id2=n2,
    method=method_arg or None,
)
```

Output:
```
Link Prediction: "<n1>" → "<n2>"
  Method:  cosine
  Score:   0.723  (threshold: 0.5 → LIKELY)

  Recommendation: This link is LIKELY to be meaningful.
```

---

## `top-links <node_id> [--top N] [--method <method>]`

Find the top-N most likely new connections for a node.

```python
from semantica.kg.link_predictor import LinkPredictor
from semantica.context import ContextGraph

graph = ContextGraph()
predictor = LinkPredictor()

top = predictor.predict_top_links(
    graph_store=graph,
    node_id=node_id,
    top_k=int(top_n) if top_n else 10,
    method=method_arg or None,
)
```

Return: `| Rank | Target Node | Type | Score | Existing Link? |`

---

## `batch <query_node> [--against <n1,n2,...>] [--top N]`

Score similarity between a query node and a set of target nodes (or all nodes).

```python
from semantica.kg.similarity_calculator import SimilarityCalculator
from semantica.kg.node_embeddings import NodeEmbedder
from semantica.context import ContextGraph

graph = ContextGraph()
embedder = NodeEmbedder()
calc = SimilarityCalculator()

# Get query embedding and all target embeddings
query_vec = ...  # from stored node2vec_embedding
target_embeddings = {n: embedder.get_embedding(n) for n in targets}

scores = calc.batch_similarity(
    embeddings=target_embeddings,
    query_embedding=query_vec,
    top_k=int(top_n) if top_n else 20,
)
```

Return: `| Node | Type | Score |` sorted descending.

---

## `pairwise [--labels <t1,t2>] [--method cosine|euclidean]`

Compute all pairwise similarities among a set of nodes.

```python
from semantica.kg.similarity_calculator import SimilarityCalculator

calc = SimilarityCalculator()

pairwise = calc.pairwise_similarity(
    embeddings=embeddings_dict,
    method=method_arg or None,
)
```

Show as a heatmap summary — top-5 most similar pairs and bottom-5 most dissimilar pairs. Full matrix on request.

Also use `AgentContext.predict_decision_relationships(decision_id, top_k)` when working within decision graphs for relationship prediction enriched with KG algorithms.

# Examples

Code examples organized by complexity. For interactive notebooks, see the [Cookbook](cookbook.md).

---

## Beginner

### Basic Knowledge Graph

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

ingestor = FileIngestor()
parser   = DocumentParser()
ner      = NERExtractor()
rel      = RelationExtractor()

sources = ingestor.ingest("data/sample.pdf")
parsed  = parser.parse(sources[0])

entities      = ner.extract(parsed)
relationships = rel.extract(parsed, entities=entities)

kg = GraphBuilder(merge_entities=True).build(
    entities=entities, relationships=relationships
)
print(f"{len(kg.nodes)} nodes, {len(kg.edges)} edges")
```

### Entity Extraction from Text

```python
from semantica.semantic_extract import NERExtractor

ner      = NERExtractor()
entities = ner.extract("Apple Inc. was founded by Steve Jobs in 1976.")

for entity in entities:
    print(f"{entity['text']}: {entity['type']}")
# Apple Inc.: ORGANIZATION
# Steve Jobs: PERSON
# 1976: DATE
```

### Custom NER Configuration

```python
from semantica.semantic_extract import NERExtractor

ner = NERExtractor(
    method="llm",
    provider="openai",
    model="gpt-4",
    confidence_threshold=0.8,
    temperature=0.0,
)
entities = ner.extract("Your document text here...")
```

---

## Intermediate

### Multi-Source Integration

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

ingestor = FileIngestor()
parser   = DocumentParser()
ner      = NERExtractor()
rel      = RelationExtractor()
builder  = GraphBuilder(merge_entities=True)

all_entities, all_rels = [], []

for path in ["source1.pdf", "source2.pdf", "source3.pdf"]:
    sources = ingestor.ingest(path)
    parsed  = parser.parse(sources[0])
    all_entities.extend(ner.extract(parsed))
    all_rels.extend(rel.extract(parsed, entities=all_entities))

kg = builder.build(entities=all_entities, relationships=all_rels)
print(f"Unified graph: {len(kg.nodes)} nodes, {len(kg.edges)} edges")
```

### Conflict Detection and Resolution

```python
from semantica.conflicts import ConflictDetector, ConflictResolver

detector = ConflictDetector()
conflicts = detector.detect_conflicts(all_entities)

resolver = ConflictResolver(default_strategy="voting")
resolved = resolver.resolve_conflicts(conflicts)

print(f"Detected {len(conflicts)} conflicts, resolved {len(resolved)}")
```

### Persistent Storage (Neo4j)

```python
from semantica.graph_store import GraphStore

store = GraphStore(
    backend="neo4j",
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
)
store.connect()

apple = store.create_node(labels=["Company"], properties={"name": "Apple Inc."})
tim   = store.create_node(labels=["Person"],  properties={"name": "Tim Cook"})
store.create_relationship(
    start_node_id=tim["id"],
    end_node_id=apple["id"],
    rel_type="CEO_OF",
)
store.close()
```

### FalkorDB (High-Speed Queries)

```python
from semantica.graph_store import GraphStore

store = GraphStore(
    backend="falkordb",
    host="localhost",
    port=6379,
    graph_name="knowledge_graph",
)
store.connect()
results = store.execute_query(
    "MATCH (n)-[r]->(m) WHERE n.name CONTAINS 'AI' RETURN n"
)
store.close()
```

---

## Advanced

### GraphRAG with Reasoning

```python
from semantica.context import AgentContext
from semantica.reasoning import Reasoner

context = AgentContext(
    vector_store=vs,
    knowledge_graph=kg,
    graph_expansion=True,
    hybrid_alpha=0.7,
)

reasoner = Reasoner()
reasoner.add_rule("IF Library(?x) AND Language(?y) THEN TechStackItem(?x)")
inferred = reasoner.infer_facts(kg.get_all_triplets())

for fact in inferred:
    kg.add_fact_from_string(fact)

results = context.retrieve("What technologies are used in this project?")
```

[Full GraphRAG tutorial](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb) · [RAG vs. GraphRAG comparison](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/02_RAG_vs_GraphRAG_Comparison.ipynb)

---

## Production

### Batch Processing (Large Datasets)

```python
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

ingestor = FileIngestor()
parser   = DocumentParser()
ner      = NERExtractor()
rel      = RelationExtractor()
builder  = GraphBuilder()

sources    = [f"data/doc_{i}.pdf" for i in range(1000)]
batch_size = 50

for i in range(0, len(sources), batch_size):
    batch = sources[i : i + batch_size]
    all_entities, all_rels = [], []

    for path in batch:
        parsed = parser.parse(ingestor.ingest(path)[0])
        all_entities.extend(ner.extract(parsed))
        all_rels.extend(rel.extract(parsed, entities=all_entities))

    kg = builder.build(entities=all_entities, relationships=all_rels)
    print(f"Batch {i // batch_size + 1}: {len(kg.nodes)} nodes")
```

### Real-Time Streaming

```python
from semantica.ingest import StreamIngestor
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder

stream  = StreamIngestor(stream_uri="kafka://localhost:9092/topic")
ner     = NERExtractor()
rel     = RelationExtractor()
builder = GraphBuilder()

for batch in stream.stream(batch_size=100):
    all_entities, all_rels = [], []
    for item in batch:
        text = str(item)
        all_entities.extend(ner.extract(text))
        all_rels.extend(rel.extract(text, entities=all_entities))
    kg = builder.build(entities=all_entities, relationships=all_rels)
    print(f"Processed batch: {len(kg.nodes)} nodes")
```

---

## More Resources

- [Quickstart Tutorial](quickstart.md) — step-by-step first pipeline
- [Cookbook](cookbook.md) — interactive Jupyter notebooks
- [Use Cases](use-cases.md) — domain-specific examples
- [API Reference](reference/core.md) — complete API documentation

!!! info "Have an example to share?"
    [Contribute on GitHub](https://github.com/Hawksight-AI/semantica)

# Provenance Tracking Module

**W3C PROV-O compliant provenance tracking for high-stakes domains requiring complete traceability**

## Overview

The Semantica provenance module provides W3C PROV-O compliant tracking for knowledge graphs, enabling complete end-to-end lineage from source documents to query responses. Designed for high-stakes domains where every decision must be explainable and auditable.

<div class="grid cards" markdown>

-   :material-web:{ .lg .middle } **W3C PROV-O Compliant**

    ---

    Implements PROV-O ontology (prov:Entity, prov:Activity, prov:Agent, prov:wasDerivedFrom)

-   :material-all-inclusive:{ .lg .middle } **Complete Coverage**

    ---

    All 17 Semantica modules integrated for comprehensive tracking

-   :material-file-document:{ .lg .middle } **Source Tracking**

    ---

    Document identifiers, page numbers, sections, and direct quotes supported

-   :material-backup-restore:{ .lg .middle } **Backward Compatible**

    ---

    100% backward compatible, opt-in only with zero breaking changes

-   :material-database:{ .lg .middle } **Multiple Storage**

    ---

    InMemory (fast) and SQLite (persistent) backends available

-   :material-share-variant:{ .lg .middle } **Bridge Axiom Support**

    ---

    Translation chain tracking for domain transformations (L1 → L2 → L3)

-   :material-shield-check:{ .lg .middle } **Integrity Verification**

    ---

    SHA-256 checksums for tamper detection and verification

-   :material-link-variant:{ .lg .middle } **Complete Lineage**

    ---

    End-to-end tracing from document to AI response

</div>

### Key Features

- ✅ **W3C PROV-O Compliant** — Implements PROV-O ontology (prov:Entity, prov:Activity, prov:Agent, prov:wasDerivedFrom)
- ✅ **All 17 Modules Integrated** — Complete coverage across Semantica
- ✅ **Source Tracking** — Document identifiers, page numbers, sections, and direct quotes supported
- ✅ **Zero Breaking Changes** — 100% backward compatible, opt-in only
- ✅ **Multiple Storage Backends** — InMemory (fast) and SQLite (persistent)
- ✅ **Bridge Axiom Support** — Translation chain tracking for domain transformations (L1 → L2 → L3)
- ✅ **Integrity Verification** — SHA-256 checksums for tamper detection
- ✅ **Complete Lineage Tracing** — End-to-end from document to response

---

## Installation

The provenance module is included with Semantica. No additional installation required.

```python
from semantica.provenance import ProvenanceManager
```

---

## Core Components

### ProvenanceManager

Central manager for all provenance tracking operations.

```python
from semantica.provenance import ProvenanceManager

# Initialize with in-memory storage (default)
manager = ProvenanceManager()

# Initialize with persistent SQLite storage
manager = ProvenanceManager(storage_path="provenance.db")
```

**Key capabilities:**
- Track entities and relationships with complete lineage
- Store provenance data in memory or persistent SQLite storage
- Query provenance information for audit and compliance
- Maintain W3C PROV-O compliant records

**Methods:**
- `track_entity(entity_id, source, entity_type, **metadata)` — Track entity provenance
- `track_relationship(relationship_id, source, subject, predicate, obj, **metadata)` — Track relationship provenance
- `track_chunk(chunk_id, source_document, chunk_text, start_char, end_char, **metadata)` — Track document chunk provenance
- `track_property_source(entity_id, property_name, value, source, **metadata)` — Track property-level provenance
- `get_lineage(entity_id)` — Retrieve complete lineage for an entity
- `get_statistics()` — Get provenance statistics
- `get_all_entries()` — Retrieve all provenance entries

### Storage Backends

#### InMemoryStorage

Fast, non-persistent storage for development and testing.

```python
from semantica.provenance import ProvenanceManager, InMemoryStorage

manager = ProvenanceManager(storage=InMemoryStorage())
```

**Best for:**
- Development and testing environments
- Temporary provenance tracking
- High-performance scenarios where persistence isn't required
- Rapid prototyping and debugging

#### SQLiteStorage

Persistent storage for production use.

```python
from semantica.provenance import ProvenanceManager, SQLiteStorage

storage = SQLiteStorage("provenance.db")
manager = ProvenanceManager(storage=storage)
```

**Best for:**
- Production deployments requiring persistence
- Long-term provenance storage
- Compliance and audit requirements
- Multi-process environments

### Data Schemas

#### ProvenanceEntry

Core data structure for provenance tracking.

```python
from semantica.provenance import ProvenanceEntry
from datetime import datetime

entry = ProvenanceEntry(
    entity_id="entity_1",
    source="document.pdf",
    timestamp=datetime.now(),
    entity_type="named_entity",
    metadata={"text": "Apple Inc.", "confidence": 0.95}
)
```

#### SourceReference

Structured source information with page and section details.

```python
from semantica.provenance import SourceReference

source = SourceReference(
    document="research_paper.pdf",
    page=5,
    section="Results",
    confidence=0.98
)
```

---

## Module Integrations

All Semantica modules have provenance-enabled versions. Enable tracking by setting `provenance=True`.

### Semantic Extract

```python
from semantica.semantic_extract.semantic_extract_provenance import (
    NERExtractorWithProvenance,
    RelationExtractorWithProvenance,
    EventDetectorWithProvenance,
    CoreferenceResolverWithProvenance,
    TripletExtractorWithProvenance
)

# Named Entity Recognition with provenance
ner = NERExtractorWithProvenance(provenance=True)
entities = ner.extract(
    text="Apple Inc. was founded by Steve Jobs in Cupertino.",
    source="company_history.pdf"
)

# Access provenance manager
prov_manager = ner._prov_manager
lineage = prov_manager.get_lineage("entity_id")
```

**Tracks:** Entity text, labels, confidence scores, source documents, character positions, extraction timestamps

### LLM Providers

```python
from semantica.llms.llms_provenance import (
    GroqLLMWithProvenance,
    OpenAILLMWithProvenance,
    HuggingFaceLLMWithProvenance,
    LiteLLMWithProvenance
)

# Groq LLM with provenance
llm = GroqLLMWithProvenance(
    provenance=True,
    model="llama-3.1-70b"
)

response = llm.generate("What is artificial intelligence?")

# Access cost and performance data
stats = llm._prov_manager.get_statistics()
```

**Tracks:** Model name, prompt/completion tokens, API costs, latency, generation parameters, prompts and responses

### Pipeline Execution

```python
from semantica.pipeline.pipeline_provenance import PipelineWithProvenance

pipeline = PipelineWithProvenance(provenance=True)
result = pipeline.run(data=input_data, source="input_file.json")
```

**Tracks:** Pipeline steps executed, duration, input/output data, execution status

### Context Management

```python
from semantica.context.context_provenance import ContextManagerWithProvenance

ctx = ContextManagerWithProvenance(provenance=True)
ctx.add_context("Relevant background information", source="knowledge_base.txt")
```

**Tracks:** Context additions, sources, timestamps

### Document Ingestion

```python
from semantica.ingest.ingest_provenance import PDFIngestorWithProvenance

ingestor = PDFIngestorWithProvenance(provenance=True)
documents = ingestor.ingest("research_paper.pdf")
```

**Tracks:** File paths, page counts, file metadata, ingestion timestamps

### Embeddings Generation

```python
from semantica.embeddings.embeddings_provenance import EmbeddingGeneratorWithProvenance

embedder = EmbeddingGeneratorWithProvenance(
    provenance=True,
    model="sentence-transformers/all-mpnet-base-v2"
)
embeddings = embedder.embed(["Text 1", "Text 2"], source="corpus.txt")
```

**Tracks:** Model name, embedding dimensions, generation timestamps

### Graph Store

```python
from semantica.graph_store.graph_store_provenance import GraphStoreWithProvenance

store = GraphStoreWithProvenance(provenance=True)
store.add_node(entity_node, source="knowledge_graph.json")
```

**Tracks:** Nodes added, node properties, graph structure changes

### Vector Store

```python
from semantica.vector_store.vector_store_provenance import VectorStoreWithProvenance

store = VectorStoreWithProvenance(provenance=True)
store.add_vectors(embedding_vectors, source="embeddings.npy")
```

**Tracks:** Vectors stored, dimensions, storage timestamps

### Triplet Store

```python
from semantica.triplet_store.triplet_store_provenance import TripletStoreWithProvenance

store = TripletStoreWithProvenance(provenance=True)
store.add_triplet("Steve_Jobs", "founded", "Apple_Inc", source="knowledge_base.ttl")
```

**Tracks:** Subject, predicate, object, confidence scores, timestamps

### Other Modules

All remaining modules follow the same pattern:

- **Reasoning** — `ReasoningEngineWithProvenance`
- **Conflicts** — `SourceTrackerWithUnifiedBackend`
- **Deduplication** — `DeduplicatorWithProvenance`
- **Export** — `ExporterWithProvenance`
- **Parse** — `ParserWithProvenance`
- **Normalize** — `NormalizerWithProvenance`
- **Ontology** — `OntologyManagerWithProvenance`
- **Visualization** — `VisualizerWithProvenance`

---

## Usage Examples

### Basic Entity Tracking

```python
from semantica.provenance import ProvenanceManager

manager = ProvenanceManager()

# Track entity
manager.track_entity(
    entity_id="entity_1",
    source="document.pdf",
    entity_type="organization",
    metadata={
        "name": "Apple Inc.",
        "confidence": 0.95,
        "extraction_method": "NER"
    }
)

# Retrieve lineage
lineage = manager.get_lineage("entity_1")
print(f"Source: {lineage['source']}")
print(f"Timestamp: {lineage['timestamp']}")
print(f"Metadata: {lineage['metadata']}")
```

### Relationship Tracking

```python
# Track entities
manager.track_entity("steve_jobs", "biography.pdf", "person")
manager.track_entity("apple_inc", "biography.pdf", "organization")

# Track relationship
manager.track_relationship(
    relationship_id="rel_1",
    source="biography.pdf",
    subject="steve_jobs",
    predicate="founded",
    obj="apple_inc",
    metadata={"confidence": 0.92}
)
```

### Lineage Chain Tracking

```python
# Create lineage chain: document → chunk → entity
manager.track_entity("doc_1", "research_paper.pdf", "document")

manager.track_chunk(
    chunk_id="chunk_1",
    source_document="doc_1",
    chunk_text="Sample text content",
    start_char=0,
    end_char=100
)

manager.track_entity(
    entity_id="entity_1",
    source="chunk_1",
    entity_type="named_entity",
    metadata={"text": "Apple"}
)

# Retrieve complete lineage
lineage = manager.get_lineage("entity_1")
print(f"Lineage chain: {lineage['lineage_chain']}")
```

### Property-Level Provenance

```python
from semantica.provenance import SourceReference

# Track entity
manager.track_entity("company_1", "doc.pdf", "organization")

# Track property sources
manager.track_property_source(
    entity_id="company_1",
    property_name="revenue",
    value="$394.3B",
    source=SourceReference(
        document="annual_report_2023.pdf",
        page=5,
        section="Financial Summary",
        confidence=0.98
    )
)

manager.track_property_source(
    entity_id="company_1",
    property_name="employees",
    value="500",
    source=SourceReference(
        document="company_profile.pdf",
        page=2,
        confidence=0.90
    )
)
```

### End-to-End Workflow

```python
from semantica.provenance import ProvenanceManager
from semantica.ingest.ingest_provenance import PDFIngestorWithProvenance
from semantica.semantic_extract.semantic_extract_provenance import NERExtractorWithProvenance
from semantica.llms.llms_provenance import GroqLLMWithProvenance
from semantica.graph_store.graph_store_provenance import GraphStoreWithProvenance

# Initialize
manager = ProvenanceManager()

# Step 1: Ingest
ingestor = PDFIngestorWithProvenance(provenance=True)
documents = ingestor.ingest("research_paper.pdf")

# Step 2: Extract
ner = NERExtractorWithProvenance(provenance=True)
entities = ner.extract(documents[0].text, source="research_paper.pdf")

# Step 3: LLM Analysis
llm = GroqLLMWithProvenance(provenance=True)
summary = llm.generate(f"Summarize: {documents[0].text[:500]}")

# Step 4: Store
graph = GraphStoreWithProvenance(provenance=True)
for entity in entities:
    graph.add_node(entity, source="research_paper.pdf")

# Step 5: Retrieve provenance
lineage = ner._prov_manager.get_lineage("entity_id")
stats = ner._prov_manager.get_statistics()
print(f"Total operations: {stats['total_entries']}")
```

---

## Bridge Axioms

Bridge axioms enable translation chain tracking across multiple abstraction layers.

```python
from semantica.provenance.bridge_axiom import BridgeAxiom, TranslationChain

# Create bridge axiom
axiom = BridgeAxiom(
    source_layer="L1_ecological",
    target_layer="L2_financial",
    translation_rule="fish_biomass_to_revenue",
    confidence=0.89
)

# Add provenance
axiom.add_source_provenance(
    document="DOI:10.1371/journal.pone.0023601",
    location="Figure 2",
    quote="Total fish biomass increased by 463%"
)

# Create translation chain
chain = TranslationChain()
chain.add_axiom(axiom)

# Track complete chain
provenance_data = chain.get_complete_provenance()
```

**Use Cases:**
- Blue Finance: Ecological data → Financial metrics
- Healthcare: Clinical data → Treatment recommendations
- Legal: Evidence → Legal conclusions
- Pharmaceutical: Research data → Drug efficacy claims

---

## Best Practices

### 1. Always Provide Source Information

```python
# ✅ GOOD - Provides source
entities = ner.extract(text, source="document.pdf")

# ❌ BAD - No source information
entities = ner.extract(text)
```

### 2. Use Descriptive Entity IDs

```python
# ✅ GOOD - Descriptive IDs
manager.track_entity("company_apple_inc", source, "organization")

# ❌ BAD - Generic IDs
manager.track_entity("entity_1", source, "organization")
```

### 3. Include Rich Metadata

```python
# ✅ GOOD - Rich metadata
manager.track_entity(
    entity_id="person_steve_jobs",
    source="biography.pdf",
    entity_type="person",
    metadata={
        "full_name": "Steve Jobs",
        "birth_year": 1955,
        "confidence": 0.95,
        "extraction_method": "NER_spacy"
    }
)
```

### 4. Enable Provenance for High-Stakes Operations

```python
# For high-stakes requirements
llm = GroqLLMWithProvenance(provenance=True)  # Track all LLM calls
ner = NERExtractorWithProvenance(provenance=True)  # Track all extractions
```

### 5. Use Persistent Storage for Production

```python
from semantica.provenance import ProvenanceManager, SQLiteStorage

# Use SQLite for persistence
storage = SQLiteStorage("provenance.db")
manager = ProvenanceManager(storage=storage)
```

---

## Performance

### Benchmarks

- **Entity tracking:** Fast per operation
- **Lineage retrieval:** Quick retrieval for long chains
- **Batch operations:** High-throughput batch processing
- **Storage:** InMemory (fastest), SQLite (persistent)

### Optimization Tips

1. **Batch Operations:** Use batch methods for multiple entities
2. **Selective Tracking:** Only track provenance for critical entities
3. **Storage Choice:** Use InMemory for development, SQLite for production
4. **Index Optimization:** SQLite automatically indexes entity_id and source_document

---

## Compliance Standards Support

The provenance module provides **technical infrastructure** that supports compliance efforts:

- **W3C PROV-O** — Implements PROV-O ontology data structures and relationships
- **FDA 21 CFR Part 11** — Provides audit trails, checksums, and temporal tracking for electronic records
- **SOX** — Enables financial data lineage tracking and integrity verification
- **HIPAA** — Supports healthcare data integrity through checksums and source tracking
- **TNFD** — Enables bridge axiom tracking for nature-to-financial translations

**Important:** This module provides the *technical capabilities* for compliance. Organizations must implement additional policies, procedures, validation, and controls to meet specific regulatory requirements. Semantica does not provide regulatory certification or legal compliance guarantees.

---

## API Reference

### ProvenanceManager

#### `__init__(storage=None, storage_path=None)`

Initialize provenance manager.

**Parameters:**
- `storage` (ProvenanceStorage, optional): Storage backend instance
- `storage_path` (str, optional): Path for SQLite storage

#### `track_entity(entity_id, source, entity_type, **metadata)`

Track entity provenance.

**Parameters:**
- `entity_id` (str): Unique identifier for entity
- `source` (str): Source document or identifier
- `entity_type` (str): Type of entity
- `**metadata`: Additional metadata

**Returns:** ProvenanceEntry

#### `track_relationship(relationship_id, source, subject, predicate, obj, **metadata)`

Track relationship provenance.

**Parameters:**
- `relationship_id` (str): Unique identifier for relationship
- `source` (str): Source document
- `subject` (str): Subject entity ID
- `predicate` (str): Relationship type
- `obj` (str): Object entity ID
- `**metadata`: Additional metadata

**Returns:** ProvenanceEntry

#### `track_chunk(chunk_id, source_document, chunk_text, start_char, end_char, **metadata)`

Track document chunk provenance.

**Parameters:**
- `chunk_id` (str): Unique identifier for chunk
- `source_document` (str): Source document ID
- `chunk_text` (str): Text content of chunk
- `start_char` (int): Start character position
- `end_char` (int): End character position
- `**metadata`: Additional metadata

**Returns:** ProvenanceEntry

#### `get_lineage(entity_id)`

Retrieve complete lineage for an entity.

**Parameters:**
- `entity_id` (str): Entity identifier

**Returns:** dict with lineage information

#### `get_statistics()`

Get provenance statistics.

**Returns:** dict with statistics (total_entries, entities, relationships, chunks)

---

## Testing

Run the provenance test suite:

```bash
# All provenance tests
pytest tests/provenance/ -v

# Specific test categories
pytest tests/provenance/test_manager.py -v
pytest tests/provenance/test_storage.py -v
pytest tests/provenance/test_bridge_axiom.py -v
pytest tests/provenance/test_integration.py -v

# Module integration tests
pytest tests/provenance/test_semantic_extract_provenance.py -v
pytest tests/provenance/test_llms_provenance.py -v
```

---

## Troubleshooting

### Provenance Not Being Tracked

```python
# Check if provenance is enabled
print(f"Provenance enabled: {obj.provenance}")
print(f"Manager available: {obj._prov_manager is not None}")
```

### Performance Issues

```python
# Use batch operations
entities = [{"id": f"entity_{i}"} for i in range(1000)]
manager.track_entities_batch(entities, source="doc_1")
```

### Storage Growing Too Large

```python
# Use separate databases for different time periods
manager_2026 = ProvenanceManager(storage_path="provenance_2026.db")
```

---

## See Also

- [Provenance Usage Guide](https://github.com/Hawksight-AI/semantica/blob/main/semantica/provenance/provenance_usage.md) — Comprehensive usage documentation
- [Change Management](change_management.md) — Version control and audit trails
- [Conflicts Module](conflicts.md) — Source tracking and conflict resolution
- [Knowledge Graph](kg.md) — Entity and relationship tracking

---

## License

MIT License - See [LICENSE](../../LICENSE) for details.

## Support

For issues or questions, please open an issue on GitHub or join our [Discord](https://discord.gg/sV34vps5hH).

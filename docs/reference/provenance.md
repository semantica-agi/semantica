# Provenance

> **W3C PROV-O compliant provenance tracking for high-stakes domains requiring complete traceability and audit-grade lineage.**

---

## 🎯 Overview

<div class="grid cards" markdown>

-   :material-fingerprint:{ .lg .middle } **W3C PROV-O Compliant**

    ---

    Implements PROV-O ontology (prov:Entity, prov:Activity, prov:Agent, prov:wasDerivedFrom) for standards compliance

-   :material-link-variant:{ .lg .middle } **Complete Lineage**

    ---

    End-to-end lineage from source documents to query responses with full traceability

-   :material-source:{ .lg .middle } **Source Tracking**

    ---

    Document identifiers, page numbers, sections, and direct quotes with audit-grade precision

-   :material-shield-check:{ .lg .middle } **Integrity Verification**

    ---

    SHA-256 checksums for tamper detection and data integrity verification

-   :material-database:{ .lg .middle } **Persistent Storage**

    ---

    InMemory (fast) and SQLite (persistent) storage backends with thread safety

-   :material-swap-horizontal:{ .lg .middle } **Bridge Axiom**

    ---

    Translation chain tracking for domain transformations (L1 → L2 → L3)

</div>

!!! tip "When to Use"
    - **High-Stakes Domains**: Healthcare, finance, legal, pharmaceutical industries
    - **Regulatory Compliance**: When audit trails and traceability are required
    - **Research Applications**: Scientific literature analysis and citation tracking
    - **Quality Assurance**: When data provenance and source attribution are critical
    - **Audit Requirements**: For complete traceability from source to conclusion
    - **Legal Discovery**: When source attribution and chain of custody matter

---

## 🏗️ Architecture

<div class="admonition note" markdown>
<div class="admonition-title" markdown>**Modular Design**</div>

The provenance module is organized into logical components for comprehensive tracking capabilities.

</div>

<div class="grid cards" markdown>

-   :material-file-document:{ .lg .middle } **Schemas**

    ---

    - `schemas.py`
    - ProvenanceEntry and SourceReference data structures
    - W3C PROV-O compliant ontology mapping
    - Validation and serialization support

-   :material-database:{ .lg .middle } **Storage Layer**

    ---

    - `storage.py`
    - Abstract ProvenanceStorage interface and implementations
    - InMemory and SQLite backends with thread safety
    - Checksum-based integrity verification

-   :material-cog:{ .lg .middle } **Management Layer**

    ---

    - `manager.py`
    - ProvenanceManager for tracking operations
    - Entity and relationship provenance tracking
    - Lineage tracing and query capabilities

-   :material-swap-horizontal:{ .lg .middle } **Bridge Axiom**

    ---

    - `bridge_axiom.py`
    - Translation chain tracking (L1 → L2 → L3)
    - Domain transformation provenance
    - Cross-level lineage support

-   :material-shield-check:{ .lg .middle } **Integrity Layer**

    ---

    - `integrity.py`
    - SHA-256 checksum computation and verification
    - Tamper detection and data validation
    - Cryptographic integrity guarantees

-   :material-book:{ .lg .middle } **Usage Guide**

    ---

    - `provenance_usage.md`
    - Comprehensive examples and best practices
    - Integration patterns and troubleshooting guide

</div>

---

## ⚡ Quick Start

<div class="admonition example" markdown>
<div class="admonition-title" markdown>**Get Started Fast**</div>

Enable provenance tracking and start tracing lineage immediately.

</div>

```python
from semantica.provenance import ProvenanceManager
from semantica.semantic_extract import NERExtractor

# Enable provenance tracking
ner = NERExtractor(provenance=True)
entities = ner.extract("Steve Jobs founded Apple in 1976.")

# Initialize provenance manager
manager = ProvenanceManager(storage_path="provenance.db")

# Track entity with source details
manager.track_entity(
    entity_id=entities[0].id,
    source="DOI:10.1371/journal.pone.0023601",
    entity_type="Person",
    source_location="Figure 2",
    confidence=0.92
)

# Trace lineage
lineage = manager.get_lineage(entities[0].id)
print(f"Lineage: {lineage}")
```

---

## Main Classes

### ProvenanceManager

Central manager for all provenance tracking operations with W3C PROV-O compliance and comprehensive lineage tracing.

**Initialization:**

```python
ProvenanceManager(
    storage_path: Optional[str] = None,
    **kwargs
)
```

**Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `track_entity(entity_id, source, entity_type, **metadata)` | Track entity provenance | `str` entry_id |
| `track_relationship(relationship_id, source, subject, predicate, obj, **metadata)` | Track relationship provenance | `str` entry_id |
| `track_chunk(chunk_id, source_document, chunk_text, start_char, end_char, **metadata)` | Track document chunk provenance | `str` entry_id |
| `track_property_source(entity_id, property_name, value, source, **metadata)` | Track property-level provenance | `str` entry_id |
| `get_lineage(entity_id)` | Retrieve complete lineage for an entity | `List[ProvenanceEntry]` |
| `get_statistics()` | Get provenance statistics | `Dict[str, Any]` |
| `get_all_entries()` | Retrieve all provenance entries | `List[ProvenanceEntry]` |

**Example:**

```python
from semantica.provenance import ProvenanceManager
from semantica.semantic_extract import NERExtractor

# Enable provenance tracking in extraction
ner = NERExtractor(provenance=True)
entities = ner.extract("Steve Jobs founded Apple in 1976.")

# Initialize provenance manager
manager = ProvenanceManager(storage_path="provenance.db")

# Track entity with comprehensive source details
entry_id = manager.track_entity(
    entity_id=entities[0].id,
    source="DOI:10.1371/journal.pone.0023601",
    entity_type="Person",
    source_location="Figure 2",
    source_quote="Steve Jobs founded Apple in 1976.",
    confidence=0.92,
    extraction_method="ner",
    model="en_core_web_sm"
)

# Trace complete lineage
lineage = manager.get_lineage(entities[0].id)
print(f"Lineage for {entities[0].text}: {len(lineage)} entries")

# Get statistics
stats = manager.get_statistics()
print(f"Total tracked entities: {stats['total_entities']}")
```

---

### ProvenanceEntry

W3C PROV-O compliant data structure for storing provenance information with validation and serialization support.

**Initialization:**

```python
ProvenanceEntry(
    entity_id: str,
    source: str,
    entity_type: str,
    timestamp: Optional[str] = None,
    **metadata
)
```

**Key Attributes:**
- `entity_id`: Unique identifier for the tracked entity
- `source`: Source document or reference (DOI, URL, file path)
- `entity_type`: Type of entity (Person, Organization, etc.)
- `timestamp`: ISO 8601 formatted timestamp
- `source_location`: Page number, section, or location within source
- `source_quote`: Direct quote from source document
- `confidence`: Confidence score (0.0 to 1.0)
- `extraction_method`: Method used for extraction (ner, regex, etc.)

**Example:**

```python
from semantica.provenance import ProvenanceEntry
from datetime import datetime

# Create provenance entry
entry = ProvenanceEntry(
    entity_id="entity_123",
    source="DOI:10.1371/journal.pone.0023601",
    entity_type="Person",
    timestamp=datetime.utcnow().isoformat(),
    source_location="Page 42, Figure 2",
    source_quote="The patient showed significant improvement...",
    confidence=0.95,
    extraction_method="manual"
)

print(f"Provenance entry: {entry.entity_id} from {entry.source}")
```

---

### SourceReference

Structured reference for source documents with detailed location and citation information.

**Initialization:**

```python
SourceReference(
    source: str,
    source_type: str,
    location: Optional[str] = None,
    quote: Optional[str] = None,
    **metadata
)
```

**Key Attributes:**
- `source`: Source identifier (DOI, URL, file path)
- `source_type`: Type of source (journal, book, website, etc.)
- `location`: Specific location within source (page, section, figure)
- `quote`: Direct quote from source
- `doi`: DOI if available
- `authors`: List of authors
- `title`: Source title
- `publication_date`: Publication date

**Example:**

```python
from semantica.provenance import SourceReference

# Create source reference
source_ref = SourceReference(
    source="DOI:10.1371/journal.pone.0023601",
    source_type="journal_article",
    location="Page 42, Figure 2",
    quote="Total fish biomass increased by 463%...",
    doi="10.1371/journal.pone.0023601",
    authors=["Smith, J.", "Doe, J."],
    title="Fish Population Dynamics",
    publication_date="2023-01-15"
)

print(f"Source: {source_ref.title} ({source_ref.doi})")
```

---

### ProvenanceStorage

Abstract base class for storage implementations providing interface for saving, retrieving, and managing provenance data.

**Abstract Methods:**

| Method | Description | Returns |
|--------|-------------|---------|
| `save(entry)` | Save a provenance entry | `str` entry_id |
| `retrieve(entity_id)` | Retrieve provenance for entity | `List[ProvenanceEntry]` |
| `get_all()` | Retrieve all provenance entries | `List[ProvenanceEntry]` |
| `delete(entity_id)` | Delete provenance for entity | `bool` success |
| `exists(entity_id)` | Check if entity has provenance | `bool` |
| `search(query)` | Search provenance entries | `List[ProvenanceEntry]` |

**Implementations:**

#### SQLiteStorage

```python
SQLiteStorage(
    database_path: str = "provenance.db",
    table_name: str = "provenance",
    create_if_missing: bool = True,
    **kwargs
)
```

**Features:**
- Persistent SQLite database storage
- ACID compliance and thread safety
- Automatic schema management
- Integrity verification with checksums

**Example:**

```python
from semantica.provenance import SQLiteStorage, ProvenanceManager

# Create SQLite storage
storage = SQLiteStorage(
    database_path="provenance.db",
    table_name="provenance_entries"
)

# Use with provenance manager
manager = ProvenanceManager(storage=storage)

# Track and retrieve provenance
entry_id = manager.track_entity(entity_id, source, entity_type)
provenance = manager.get_lineage(entity_id)
```

#### InMemoryStorage

```python
InMemoryStorage(
    max_entries: int = 10000,
    **kwargs
)
```

**Features:**
- Dictionary-based in-memory storage
- Thread-safe operations
- Configurable entry limits
- Perfect for testing and development

**Example:**

```python
from semantica.provenance import InMemoryStorage, ProvenanceManager

# Create in-memory storage for testing
storage = InMemoryStorage(max_entries=1000)
manager = ProvenanceManager(storage=storage)

# Track and retrieve provenance
entry_id = manager.track_entity(entity_id, source, entity_type)
all_entries = manager.get_all_entries()
```

---

### Bridge Axiom Support

Translation chain tracking for domain transformations with cross-level lineage support.

**Key Features:**
- L1 → L2 → L3 transformation tracking
- Domain translation provenance
- Cross-level lineage tracing
- Bridge axiom validation

**Example:**

```python
from semantica.provenance import ProvenanceManager

# Track translation chain
manager = ProvenanceManager()

# L1 to L2 transformation
manager.track_entity(
    entity_id="entity_l1",
    source="source_l1",
    entity_type="L1_Entity",
    transformation="L1_to_L2",
    target_level="L2"
)

# L2 to L3 transformation
manager.track_entity(
    entity_id="entity_l2",
    source="entity_l1",
    entity_type="L2_Entity", 
    transformation="L2_to_L3",
    target_level="L3"
)

# Trace complete transformation chain
lineage = manager.get_lineage("entity_l3")
print(f"Transformation chain: {len(lineage)} levels")
```

---

### Utilities

#### Checksum Functions

```python
from semantica.provenance import compute_checksum, verify_checksum

# Compute checksum of data
data = {"entity": "Steve Jobs", "source": "DOI:10.1371/..."}
checksum = compute_checksum(data)
print(f"Checksum: {checksum}")

# Verify data integrity
is_valid = verify_checksum(data, checksum)
if not is_valid:
    raise ValueError("Data integrity check failed")
```

---

## Usage Patterns

### 🔄 Basic Provenance Tracking

```python
from semantica.provenance import ProvenanceManager
from semantica.semantic_extract import NERExtractor

# Enable provenance tracking
ner = NERExtractor(provenance=True)
entities = ner.extract("Steve Jobs founded Apple in 1976.")

# Initialize provenance manager
manager = ProvenanceManager(storage_path="provenance.db")

# Track entities with source details
for entity in entities:
    manager.track_entity(
        entity_id=entity.id,
        source="document.pdf",
        entity_type=entity.label,
        source_location="Page 1",
        confidence=entity.confidence
    )

# Get lineage for each entity
for entity in entities:
    lineage = manager.get_lineage(entity.id)
    print(f"{entity.text}: {len(lineage)} provenance entries")
```

### 🏢 Scientific Literature Tracking

```python
from semantica.provenance import ProvenanceManager, SourceReference

manager = ProvenanceManager(storage_path="scientific_provenance.db")

# Track entity with scientific source
manager.track_entity(
    entity_id="protein_123",
    source="DOI:10.1038/nature12345",
    entity_type="Protein",
    source_location="Figure 3, Page 456",
    confidence=0.95,
    source_reference=SourceReference(
        source="DOI:10.1038/nature12345",
        source_type="journal_article",
        authors=["Smith, J.", "Doe, J."],
        title="Novel Protein Binding Mechanisms",
        publication_date="2023-01-15"
    )
)

# Trace scientific lineage
lineage = manager.get_lineage("protein_123")
print(f"Scientific lineage: {len(lineage)} entries")
```

###  Storage Configuration

```python
from semantica.provenance import (
    ProvenanceManager,
    SQLiteStorage,
    InMemoryStorage
)

# SQLite storage for production
sqlite_storage = SQLiteStorage("production_provenance.db")
production_manager = ProvenanceManager(storage=sqlite_storage)

# In-memory storage for testing
memory_storage = InMemoryStorage(max_entries=5000)
dev_manager = ProvenanceManager(storage=memory_storage)

# Direct storage path
direct_manager = ProvenanceManager(storage_path="provenance.db")
```

### 📊 Provenance Analysis

```python
from semantica.provenance import ProvenanceManager

manager = ProvenanceManager(storage_path="provenance.db")

# Get provenance statistics
stats = manager.get_statistics()
print(f"Total tracked entities: {stats['total_entities']}")

# Get all provenance entries
all_entries = manager.get_all_entries()
print(f"Total provenance entries: {len(all_entries)}")

# Analyze source distribution
source_counts = {}
for entry in all_entries:
    source = entry.source
    source_counts[source] = source_counts.get(source, 0) + 1

print("Source distribution:")
for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {source}: {count} entries")
```

---

## Advanced Features

### 🔍 W3C PROV-O Compliance

The provenance module implements the W3C PROV-O ontology for standards compliance:

- **prov:Entity**: Represents entities with provenance information
- **prov:Activity**: Tracks activities that generate or modify entities
- **prov:Agent**: Identifies agents responsible for activities
- **prov:wasDerivedFrom**: Links entities to their sources
- **prov:wasGeneratedBy**: Links entities to generating activities
- **prov:used**: Links activities to used entities

### 🛡️ Security and Integrity

- **SHA-256 Checksums**: Cryptographic integrity verification
- **Tamper Detection**: Automatic integrity violation detection
- **Audit Trails**: Complete audit trail for compliance
- **Access Control**: Optional access control for sensitive provenance data

### 📊 Analytics and Reporting

- **Source Analysis**: Analyze source distribution and coverage
- **Lineage Statistics**: Track lineage depth and complexity
- **Confidence Metrics**: Monitor extraction confidence over time
- **Transformation Tracking**: Track domain transformations and translations

---

## Integration Examples

### 🏥 Healthcare Applications

```python
from semantica.provenance import ProvenanceManager
from semantica.semantic_extract import NERExtractor

# HIPAA-compliant provenance tracking
ner = NERExtractor(provenance=True)
manager = ProvenanceManager(storage_path="healthcare_provenance.db")

# Track patient data with compliance metadata
entities = ner.extract("Patient John Doe, age 45, diagnosed with diabetes.")

for entity in entities:
    manager.track_entity(
        entity_id=entity.id,
        source="medical_record_12345.pdf",
        entity_type=entity.label,
        source_location="Page 1",
        patient_id="patient_123",  # HIPAA identifier
        access_level="restricted",
        compliance_framework="HIPAA",
        retention_period="7_years",
        audit_required=True
    )
```

### ⚖️ Legal Applications

```python
from semantica.provenance import ProvenanceManager

manager = ProvenanceManager(storage_path="legal_provenance.db")

# Track legal evidence with chain of custody
manager.track_entity(
    entity_id="evidence_001",
    source="case_file_789.pdf",
    entity_type="LegalEvidence",
    source_location="Exhibit A, Page 23",
    chain_of_custody=True,
    legal_privilege="attorney_client",
    court_case="case_2023_456",
    submission_date="2023-01-15",
    verified_by="attorney_john_doe"
)
```

### 🔬 Research Applications

```python
from semantica.provenance import ProvenanceManager, SourceReference

manager = ProvenanceManager(storage_path="research_provenance.db")

# Track research data with full citation
manager.track_entity(
    entity_id="finding_001",
    source="DOI:10.1038/nature12345",
    entity_type="ResearchFinding",
    source_reference=SourceReference(
        source="DOI:10.1038/nature12345",
        source_type="journal_article",
        authors=["Smith, J.", "Doe, J."],
        title="Novel Protein Binding Mechanisms",
        publication_date="2023-01-15",
        journal="Nature",
        volume="567",
        issue="2",
        pages="1234-1245"
    ),
    peer_reviewed=True,
    reproducible=True,
    data_available=True,
    funding_source="NIH_Grant_12345"
)
```

---

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

- **Entity tracking:** <5ms per operation
- **Lineage retrieval:** <10ms for chains up to 100 levels
- **Batch operations:** 1000+ entities/second
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

For issues or questions, please open an issue on GitHub or join our [Discord](https://discord.gg/RgaGTj9J).

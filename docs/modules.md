# Modules

Every Semantica module works independently — use only what you need.

!!! tip "Just need a quick reference?"
    Jump to the [Module Index](#module-index) at the bottom of this page.

---

## Architecture Overview

Semantica is organized into **six logical layers** - each with specific responsibilities:

<div class="grid cards" markdown>

-   **Input Layer**
    
    ---
    
    Data ingestion and preparation
    
    **Modules**: Ingest, Parse, Split, Normalize

-   **Core Processing**
    
    ---
    
    Intelligence and understanding
    
    **Modules**: Semantic Extract, Knowledge Graph, Ontology, Reasoning

-   **Storage**
    
    ---
    
    Persistent data storage
    
    **Modules**: Embeddings, Vector Store, Graph Store, Triplet Store

-   **Quality Assurance**
    
    ---
    
    Data quality and consistency
    
    **Modules**: Deduplication, Conflicts

-   **Context & Memory**
    
    ---
    
    Agent memory and foundation data
    
    **Modules**: Context, Seed, LLM Providers

-   **Output & Orchestration**
    
    ---
    
    Export, visualization, and workflows
    
    **Modules**: Export, Visualization, Pipeline

</div>

---

## Input Layer

### Ingest Module
**Data ingestion from multiple sources**

```python
from semantica.ingest import FileIngestor, WebIngestor

# File ingestion
ingestor = FileIngestor()
documents = ingestor.ingest_directory("data/")

# Web ingestion
web_ingestor = WebIngestor()
pages = web_ingestor.ingest_urls(["https://example.com"])
```

- **File formats** - PDF, DOCX, TXT, JSON, CSV
- **Web scraping** - Extract content from websites
- **Database** - Connect to SQL and NoSQL databases
- **Batch processing** - Handle large datasets efficiently

- Document processing pipelines
- Web data extraction
- Database integration
- Multi-source data collection

### Parse Module
**Document parsing and text extraction**

```python
from semantica.parse import DocumentParser

parser = DocumentParser()
parsed = parser.parse_document("document.pdf")
text = parsed["full_text"]
metadata = parsed["metadata"]
```

- **Text extraction** - Extract clean text from documents
- **Metadata parsing** - Extract titles, authors, dates
- **Structure analysis** - Identify sections, headings
- **OCR support** - Handle scanned documents

- PDF processing
- Document analysis
- Content extraction
- Metadata harvesting

---

### Split Module
**Text chunking and segmentation**

```python
from semantica.split import TextSplitter

splitter = TextSplitter(method="semantic")
chunks = splitter.split(text, chunk_size=1000, overlap=200)
```

- **Intelligent chunking** - Split text while preserving context
- **Semantic splitting** - Break at natural boundaries
- **Size control** - Manage chunk sizes for processing
- **Overlap handling** - Maintain context between chunks

- Document preprocessing
- Embedding preparation
- RAG systems
- Large document processing

---

### Normalize Module
**Data cleaning and standardization**

```python
from semantica.normalize import DataNormalizer

normalizer = DataNormalizer()
clean_text = normalizer.normalize_text(text)
standardized_date = normalizer.normalize_date("Jan 1st, 2020")
```

- **Text cleaning** - Remove noise and artifacts
- **Date standardization** - Convert to ISO format
- **Name normalization** - Standardize person names
- **Entity normalization** - Clean up company names

- Data preprocessing
- Quality improvement
- Standardization
- Consistency enforcement

---

## Core Processing

### Semantic Extract Module
**Entity and relationship extraction**

```python
from semantica.semantic_extract import NERExtractor, RelationExtractor

# Entity extraction
ner = NERExtractor()
entities = ner.extract("Apple Inc. was founded by Steve Jobs.")

# Relationship extraction
rel_extractor = RelationExtractor()
relationships = rel_extractor.extract(text, entities)
```

- **Named Entity Recognition** - Find people, orgs, locations
- **Relationship extraction** - Find connections between entities
- **Custom entities** - Define your own entity types
- **Confidence scoring** - Quality assessment for extractions

- Knowledge graph construction
- Document analysis
- Information extraction
- Content understanding

---

### Knowledge Graph Module
**Graph construction and management**

```python
from semantica.kg import GraphBuilder, GraphAnalyzer

# Build graph
builder = GraphBuilder()
kg = builder.build({"entities": entities, "relationships": relationships})

# Analyze graph
analyzer = GraphAnalyzer()
stats = analyzer.analyze(kg)
```

- **Graph construction** - Build knowledge graphs from data
- **Graph analysis** - Calculate metrics and statistics
- **Graph querying** - Search and retrieve information
- **Graph manipulation** - Merge, split, transform graphs

- Knowledge base creation
- Graph analytics
- Information retrieval
- Data integration

---

### Ontology Module
**Schema definition and validation**

```python
from semantica.ontology import OntologyManager

# Define ontology
ontology = OntologyManager()
ontology.add_class("Person", ["name", "birth_date"])
ontology.add_relationship("works_for", "Person", "Organization")

# Validate data
is_valid = ontology.validate_graph(kg)
```

- **Schema definition** - Define data structure
- **Data validation** - Ensure data conforms to schema
- **Inheritance** - Create hierarchical relationships
- **Constraints** - Enforce data quality rules

- Data modeling
- Quality assurance
- Schema management
- Rule enforcement

---

### Reasoning Module
**Logical inference and deduction**

```python
from semantica.reasoning import ReasoningEngine

engine = ReasoningEngine()
inferences = engine.infer(kg, rules=["transitivity", "symmetry"])
```

- **Logical inference** - Derive new facts from existing ones
- **Pattern matching** - Find complex patterns in data
- **Consistency checking** - Detect contradictions
- **Decision support** - Automated reasoning

- Knowledge discovery
- Decision making
- Consistency checking
- Advanced analytics

---

## Storage Layer

### Embeddings Module
**Vector embeddings and similarity**

```python
from semantica.embeddings import EmbeddingGenerator

generator = EmbeddingGenerator(model="sentence-transformers")
embeddings = generator.generate(["text1", "text2"])
similarity = generator.similarity(embeddings[0], embeddings[1])
```

- **Text embeddings** - Convert text to vectors
- **Similarity search** - Find similar content
- **Clustering** - Group related items
- **AI integration** - Provide context to LLMs

- Semantic search
- Recommendation systems
- Clustering
- AI context

---

### Vector Store Module
**Vector database management**

```python
from semantica.vector_store import VectorStore

store = VectorStore(backend="faiss")
store.add_vectors(embeddings, ids)
results = store.search(query_vector, top_k=10)
```

- **Vector storage** - Efficient vector database
- **Fast search** - Approximate nearest neighbor search
- **Indexing** - Optimize for performance
- **Batch operations** - Handle large datasets

- Semantic search
- RAG systems
- Recommendation engines
- Similarity matching

---

### Graph Store Module
**Graph database integration**

```python
from semantica.graph_store import GraphStore

store = GraphStore(backend="neo4j")
store.add_nodes(entities)
store.add_edges(relationships)
results = store.query("MATCH (n)-[r]->(m) RETURN n, r, m")
```

- **Graph persistence** - Store graphs in databases
- **Graph queries** - Cypher and Gremlin support
- **Graph algorithms** - Path finding, centrality
- **Transactions** - ACID compliance

- Knowledge graph storage
- Graph analytics
- Network analysis
- Relationship queries

---

### Triplet Store Module
**Triple-based storage**

```python
from semantica.triplet_store import TripletStore

store = TripletStore()
store.add_triplets(subject, predicate, object)
triplets = store.get_triplets(entity="Apple Inc.")
```

- **Triple storage** - Store (subject, predicate, object) triples
- **Pattern matching** - Find specific patterns
- **RDF support** - Semantic web standards
- **Bulk operations** - Efficient batch processing

- Semantic web
- Knowledge representation
- Linked data
- Triple stores

---

## Quality Assurance

### Deduplication Module
**Entity deduplication and resolution**

```python
from semantica.deduplication import EntityResolver

resolver = EntityResolver()
merged_entities = resolver.resolve(entities, strategy="semantic")
```

- **Duplicate detection** - Find similar entities
- **Entity resolution** - Merge duplicate records
- **Similarity scoring** - Quality assessment
- **Record linkage** - Connect related records

- Data cleaning
- Master data management
- Record linkage
- Quality improvement

---

### Conflicts Module
**Conflict detection and resolution**

```python
from semantica.conflicts import ConflictDetector

detector = ConflictDetector()
conflicts = detector.detect_conflicts(kg)
resolved = detector.resolve(conflicts, strategy="most_recent")
```

- **Conflict detection** - Find contradictory information
- **Resolution strategies** - Automated conflict resolution
- **Source reliability** - Trustworthiness assessment
- **Temporal analysis** - Time-based conflict handling

- Data quality
- Consistency checking
- Trust management
- Conflict resolution

---

## Context & Memory

### Context Module
**Context management for AI agents**

```python
from semantica.context import ContextManager

manager = ContextManager()
context = manager.get_context(query, history)
```

- **Context tracking** - Maintain conversation context
- **Memory management** - Store and retrieve context
- **Relevance scoring** - Find relevant context
- **Session management** - Handle multiple conversations

- AI agents
- Chatbots
- Conversational AI
- Context-aware systems

---

### Seed Module
**Foundation data and knowledge**

```python
from semantica.seed import SeedData

seed = SeedData()
knowledge = seed.get_knowledge("technology", "companies")
```

- **Seed knowledge** - Foundation data for domains
- **Knowledge bases** - Pre-built domain knowledge
- **Quick start** - Bootstrap applications
- **Domain models** - Industry-specific data

- Domain bootstrapping
- Quick start data
- Industry knowledge
- Foundation models

---

### LLM Providers Module
**Large Language Model integration**

```python
from semantica.llms import LLMProvider

provider = LLMProvider(model="gpt-4")
response = provider.generate(prompt, context=kg)
```

- **LLM integration** - Connect to various LLM providers
- **Prompt engineering** - Optimize prompts for results
- **Context injection** - Provide knowledge graph context
- **Response parsing** - Extract structured outputs

- AI generation
- Question answering
- Text completion
- Knowledge reasoning

---

## Output & Orchestration

### Export Module
**Data export and serialization**

```python
from semantica.export import GraphExporter

exporter = GraphExporter()
exporter.export(kg, format="json", filename="output.json")
```

- **Multiple formats** - JSON, CSV, RDF, GraphML
- **Database export** - Export to various databases
- **Streaming** - Handle large datasets
- **Filtering** - Export specific data subsets

- Data sharing
- System integration
- Backup and restore
- Format conversion

---

### Visualization Module
**Graph visualization and analysis**

```python
from semantica.visualization import GraphVisualizer

visualizer = GraphVisualizer()
visualizer.plot(kg, layout="force_directed")
```

- **Graph visualization** - Interactive graph plots
- **Custom styling** - Tailored visual appearance
- **Analytics charts** - Statistics and metrics
- **Exploration tools** - Interactive data exploration

- Data exploration
- Presentation
- Analysis
- Reporting

---

### Pipeline Module
**Workflow orchestration**

```python
from semantica.pipeline import Pipeline

pipeline = Pipeline()
pipeline.add_step("ingest", FileIngestor())
pipeline.add_step("extract", NERExtractor())
pipeline.add_step("build", GraphBuilder())
result = pipeline.run("data/")
```

- **Workflow orchestration** - Coordinate multiple steps
- **Parallel processing** - Run steps concurrently
- **Progress tracking** - Monitor pipeline execution
- **Error handling** - Robust error management

- Data processing
- Workflow automation
- Batch processing
- System integration

---

## Additional Modules

### Change Management Module
**Version control and audit trails**

```python
from semantica.change_management import TemporalVersionManager

manager = TemporalVersionManager(storage_path="versions.db")
snapshot = manager.create_snapshot(kg, "v1.0", "user@example.com", "Initial version")
```

- **Version control** - Track changes over time
- **Audit trails** - Complete change history
- **Data integrity** - SHA-256 checksums
- **Change comparison** - Detailed diff analysis

- Knowledge graph versioning
- Compliance tracking
- Data governance
- Change management

---

### Provenance Module
**W3C PROV-O compliant tracking**

```python
from semantica.provenance import ProvenanceManager

manager = ProvenanceManager()
manager.track_entity("entity_1", "document.pdf", "person")
```

- **W3C PROV-O compliant** - Industry standard tracking
- **Complete lineage** - End-to-end traceability
- **Source attribution** - Track data origins
- **Integrity verification** - Tamper detection

- Regulatory compliance
- Data provenance
- Audit trails
- Source tracking

---

### Core Module
**Framework orchestration and configuration**

```python
from semantica.core import Semantica, Config

# Initialize framework
semantica = Semantica(config=Config())
result = semantica.process("data/")
```

- **Framework orchestration** - Central coordination
- **Configuration management** - Settings and preferences
- **Lifecycle management** - Start/stop/restart
- **Plugin system** - Extensible architecture

- Framework initialization
- Configuration management
- Plugin development
- System orchestration

---

## Common Module Chains

| Goal | Modules |
|------|---------|
| Document processing | Ingest → Parse → Split → Semantic Extract → KG |
| Web scraping | Ingest (Web) → Normalize → Semantic Extract → Graph Store |
| AI agents | Context → LLM Providers → Reasoning → Export |
| Analytics | KG → Graph Store → Visualization → Export |

---

## Module Index

| Module | Purpose | Key Classes | Use Cases |
|--------|---------|-------------|-----------|
| [Ingest](reference/ingest.md) | Data ingestion | FileIngestor, WebIngestor | File processing, web scraping |
| [Parse](reference/parse.md) | Document parsing | DocumentParser | PDF processing, text extraction |
| [Split](reference/split.md) | Text chunking | TextSplitter | RAG systems, preprocessing |
| [Normalize](reference/normalize.md) | Data cleaning | DataNormalizer | Quality improvement |
| [Semantic Extract](reference/semantic_extract.md) | Information extraction | NERExtractor, RelationExtractor | Knowledge graphs |
| [Knowledge Graph](reference/kg.md) | Graph management | GraphBuilder, GraphAnalyzer | Graph construction |
| [Ontology](reference/ontology.md) | Schema management | OntologyManager | Data modeling |
| [Reasoning](reference/reasoning.md) | Logical inference | ReasoningEngine | Knowledge discovery |
| [Embeddings](reference/embeddings.md) | Vector embeddings | EmbeddingGenerator | Semantic search |
| [Vector Store](reference/vector_store.md) | Vector database | VectorStore | Similarity search |
| [Graph Store](reference/graph_store.md) | Graph database | GraphStore | Graph storage |
| [Triplet Store](reference/triplet_store.md) | Triple storage | TripletStore | Semantic web |
| [Deduplication](reference/deduplication.md) | Entity resolution | EntityResolver | Data quality |
| [Conflicts](reference/conflicts.md) | Conflict resolution | ConflictDetector | Consistency |
| [Context](reference/context.md) | Context management | ContextManager | AI agents |
| [Seed](reference/seed.md) | Foundation data | SeedData | Domain knowledge |
| [LLM Providers](reference/llms.md) | LLM integration | LLMProvider | AI generation |
| [Export](reference/export.md) | Data export | GraphExporter | Data sharing |
| [Visualization](reference/visualization.md) | Graph visualization | GraphVisualizer | Data exploration |
| [Pipeline](reference/pipeline.md) | Workflow orchestration | Pipeline | Process automation |
| [Change Management](reference/change_management.md) | Version control | TemporalVersionManager | Audit trails |
| [Provenance](reference/provenance.md) | Data lineage | ProvenanceManager | Source tracking |
| [Core](reference/core.md) | Framework orchestration | Semantica, Config | System management |

---

## More

- [Getting Started](getting-started.md)
- [Examples](examples.md)
- [Cookbook](cookbook.md)
- [API Reference](reference/core.md)

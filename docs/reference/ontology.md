# Ontology

> **Automated ontology generation, validation, and management system.**

---

## 🎯 Overview

<div class="grid cards" markdown>

-   :material-factory:{ .lg .middle } **Automated Generation**

    ---

    6-stage pipeline to generate OWL ontologies from raw data

-   :material-sitemap:{ .lg .middle } **Inference Engine**

    ---

    Infer classes, properties, and hierarchies from entity patterns

-   :material-chart-bar:{ .lg .middle } **Evaluation**

    ---

    Assess ontology quality using coverage, completeness, and granularity metrics

-   :material-file-code:{ .lg .middle } **OWL/RDF Export**

    ---

    Export to Turtle, RDF/XML, and JSON-LD formats

</div>

!!! tip "When to Use"
    - **Schema Design**: When defining the structure of your Knowledge Graph
    - **Data Modeling**: To formalize domain concepts and relationships
    - **Interoperability**: To ensure your data follows standard semantic web practices

---

## ⚙️ Algorithms Used

### 6-Stage Generation Pipeline

The ontology generation process follows these stages:

1. **Semantic Network Parsing**: Extract concepts and patterns from raw entity/relationship data
2. **YAML-to-Definition**: Transform patterns into intermediate class definitions
3. **Definition-to-Types**: Map definitions to OWL types (`` `owl:Class` ``, `` `owl:ObjectProperty` ``)
4. **Hierarchy Generation**: Build taxonomy trees using transitive closure and cycle detection
5. **TTL Generation**: Serialize to Turtle format using `` `rdflib` ``

### Inference Algorithms

The module uses several inference algorithms:

- **Class Inference**: Clustering entities by type and attribute similarity
- **Property Inference**: Determining domain/range based on connected entity types
- **Hierarchy Inference**: `` `A is_a B` `` detection based on subset relationships

---

## Ontology Ingestion

Ingest existing ontology files directly into usable data structures using `OntologyIngestor`.

**Function:** `ingest_ontology(source, method="file")`

| Argument | Description |
|----------|-------------|
| `source` | File path, directory path, or list of paths |
| `method` | Ingestion method (default: "file") |

**Example:**

```python
from semantica.ontology import ingest_ontology

# Ingest file
data = ingest_ontology("ontology.ttl")

# Ingest directory
dataset = ingest_ontology("ontologies/")
```

## Main Classes

### OntologyEngine

Unified orchestration for generation, inference, validation, OWL export, and evaluation.

**Methods:**

| Method | Description |
|--------|-------------|
| `from_data(data, **options)` | Generate ontology from structured data |
| `from_text(text, provider=None, model=None, **options)` | LLM-based generation from text |
| `validate(ontology, **options)` | Validate ontology consistency |
| `infer_classes(entities, **options)` | Infer classes from entities |
| `infer_properties(entities, relationships, classes, **options)` | Infer properties |
| `evaluate(ontology, **options)` | Evaluate ontology quality |
| `to_owl(ontology, format="turtle")` | Export OWL/RDF serialization |
| `export_owl(ontology, path, format="turtle")` | Save OWL to file |

**Quick Start:**

```python
from semantica.ontology import OntologyEngine

engine = OntologyEngine(base_uri="https://example.org/ontology/")

data = {"entities": entities, "relationships": relationships}
ontology = engine.from_data(data, name="MyOntology")

turtle = engine.to_owl(ontology, format="turtle")
```

### LLMOntologyGenerator

LLM-based ontology generation with multi-provider support (`openai`, `groq`, `deepseek`, `huggingface_llm`).

**Example:**

```python
from semantica.ontology import OntologyEngine

text = "Acme Corp. hired Alice in 2024. Alice works for Acme."
engine = OntologyEngine()

ontology = engine.from_text(
    text,
    provider="deepseek",
    model="deepseek-chat",
    name="EmploymentOntology",
    base_uri="https://example.org/employment/",
)
```

Environment variables:

```bash
export OPENAI_API_KEY=...
export GROQ_API_KEY=...
export DEEPSEEK_API_KEY=...
```

### OntologyGenerator

Main entry point for the generation pipeline.

**Methods:**

| Method | Description |
|--------|-------------|
| `generate_ontology(data)` | Run full pipeline |
| `generate_from_schema(schema)` | Generate from explicit schema |

**Example:**

```python
from semantica.ontology import OntologyGenerator

generator = OntologyGenerator(base_uri="http://example.org/onto/")
ontology = generator.generate_ontology({
    "entities": entities,
    "relationships": relationships
})
print(ontology.serialize(format="turtle"))
```

### OntologyEvaluator

Scores ontology quality.

**Methods:**

| Method | Description |
|--------|-------------|
| `evaluate_ontology(ontology)` | Calculate evaluation metrics |
| `calculate_coverage(ontology, questions)` | Verify coverage |

### ReuseManager

Manages external dependencies.

**Methods:**

| Method | Description |
|--------|-------------|
| `import_external_ontology(uri, ontology)` | Load and merge external ontology |
| `evaluate_alignment(uri, ontology)` | Assess alignment and compatibility |

### OntologyIngestor

Handles ingestion of existing ontologies from files and directories.

**Methods:**

| Method | Description |
|--------|-------------|
| `ingest_ontology(file_path)` | Ingest a single ontology file |
| `ingest_directory(directory_path)` | Recursively ingest ontology files from a directory |

---

## Unified Engine Examples

```python
from semantica.ontology import OntologyEngine

engine = OntologyEngine(base_uri="https://example.org/ontology/")

# Generate
ontology = engine.from_data({
    "entities": entities,
    "relationships": relationships,
})

# Validate
result = engine.validate(ontology, reasoner="hermit")
print("valid=", result.valid, "consistent=", result.consistent)

# Export
turtle = engine.to_owl(ontology, format="turtle")
```

---

## Configuration

### Environment Variables

```bash
export ONTOLOGY_BASE_URI="http://my-org.com/ontology/"
export ONTOLOGY_STRICT_MODE=true
```

### YAML Configuration

```yaml
ontology:
  base_uri: "http://example.org/"
  generation:
    min_class_size: 5
    infer_hierarchy: true
```

---

## Ontology Alignment

Semantica supports mapping and connecting different ontologies to unify data across systems, standards, and domains. This enables cross-system interoperability, allowing a single semantic layer to span multiple standards (e.g., internal models and industry standards).

Alignments are represented using standard RDF predicates such as `owl:equivalentClass`, `owl:equivalentProperty`, and `skos:exactMatch`.

### Creating and Managing Alignments

You can create and query alignments programmatically using the `OntologyEngine`:

```python
from semantica.ontology.engine import OntologyEngine
from semantica.triplet_store.triplet_store import TripletStore

# Setup the store and engine (using Blazegraph as an example)
my_triplet_store = TripletStore(backend="blazegraph")
engine = OntologyEngine(store=my_triplet_store)

# Create an alignment between an internal class and a standard schema
engine.create_alignment(
    source_uri="http://internal.org/ontology/Employee",
    target_uri="http://schema.org/Person",
    predicate="http://www.w3.org/2002/07/owl#equivalentClass"
)

# Retrieve all bidirectional alignments for a specific entity
alignments = engine.get_alignments("http://internal.org/ontology/Employee")
```
### Automated Alignment Suggestions

When importing or merging external ontologies, the ReuseManager can automatically suggest alignments based on heuristic matching (such as identical labels with differing URIs).

```python
from semantica.ontology.reuse_manager import ReuseManager

manager = ReuseManager()

# Merge ontologies and auto-compute alignment suggestions
merged_ontology = manager.merge_ontology_data(
    target=internal_ontology,
    source=industry_ontology,
    compute_alignments=True
)

# Suggestions are stored in merged_ontology["suggested_alignments"]
```

For executing SPARQL queries that utilize these alignments to retrieve cross-ontology results, see the [Triplet Store Alignment-Aware Queries](triplet_store.md#alignment-aware-queries)


## Integration Examples

### Schema-First Knowledge Graph

```python
from semantica.ontology import OntologyEngine
from semantica.kg import GraphBuilder, GraphValidator

# 1. Generate Ontology from Sample Data
engine = OntologyEngine()
ontology = engine.from_data(sample_data)

# 2. Extract schema for validation
schema = {
    "entity_types": [c["name"] for c in ontology["classes"]],
    "relationship_types": [p["name"] for p in ontology["properties"]]
}

# 3. Initialize Validator and Builder
validator = GraphValidator(schema=schema, strict=True)
builder = GraphBuilder()

# 4. Build Knowledge Graph
kg = builder.build(full_dataset)

# 5. Validate against Ontology Schema
validation_result = validator.validate(kg)
if validation_result.is_valid:
    print("Knowledge Graph matches the ontology schema!")
else:
    print(f"Validation issues found: {validation_result.issues}")
```

---

## SKOS Vocabulary Management

Semantica supports [SKOS (Simple Knowledge Organization System)](https://www.w3.org/TR/skos-reference/) vocabularies as first-class semantic assets.  SKOS triples are stored in the existing RDF triplet store and queried through the `OntologyEngine` — no additional packages are required.

### Concepts and data model

| SKOS element | RDF type / predicate |
|---|---|
| ConceptScheme | `skos:ConceptScheme` |
| Concept | `skos:Concept` |
| Preferred label | `skos:prefLabel` |
| Alternative label | `skos:altLabel` |
| Broader concept | `skos:broader` |
| Narrower concept | `skos:narrower` |
| Related concept | `skos:related` |
| Human definition | `skos:definition` |
| Notation / code | `skos:notation` |

### Importing a SKOS vocabulary

Use `TripletStore.add_skos_concept()` to load individual concepts.  The method automatically asserts the parent `skos:ConceptScheme` triple the first time any concept for that scheme is added.

```python
from semantica.triplet_store import TripletStore

store = TripletStore(backend="blazegraph", endpoint="http://localhost:9999/blazegraph")

SCHEME = "https://vocab.example.org/colours"

store.add_skos_concept(
    concept_uri="https://vocab.example.org/colours/red",
    scheme_uri=SCHEME,
    pref_label="Red",
    alt_labels=["Crimson", "Rouge"],
    broader=["https://vocab.example.org/colours/warm"],
    definition="The colour at the long-wavelength end of the visible spectrum.",
    notation="RED",
)

store.add_skos_concept(
    concept_uri="https://vocab.example.org/colours/blue",
    scheme_uri=SCHEME,
    pref_label="Blue",
    alt_labels=["Azure", "Cerulean"],
)
```

For bulk ingestion of an existing SKOS/Turtle file use `TripletStore.add_triplets()` after parsing the file with [rdflib](https://rdflib.readthedocs.io/):

```python
import rdflib
from semantica.semantic_extract.triplet_extractor import Triplet

g = rdflib.Graph()
g.parse("my_vocabulary.ttl", format="turtle")

triplets = [
    Triplet(subject=str(s), predicate=str(p), object=str(o))
    for s, p, o in g
]
store.add_triplets(triplets)
```

### Listing and searching concepts

Once a vocabulary is loaded, use `OntologyEngine` to browse and search it:

```python
from semantica.ontology import OntologyEngine

engine = OntologyEngine(store=store)

# 1. List all ConceptSchemes in the store
vocabularies = engine.list_vocabularies()
# [{"uri": "https://vocab.example.org/colours", "label": "Colours"}, ...]

# 2. List every concept in a specific scheme
concepts = engine.list_concepts("https://vocab.example.org/colours")
# [{"uri": "...", "pref_label": "Red", "alt_labels": ["Crimson", "Rouge"]}, ...]

# 3. Case-insensitive substring search across prefLabel and altLabel
results = engine.search_concepts("crimson")
# [{"uri": "https://vocab.example.org/colours/red", "label": "Crimson"}]

# 4. Restrict search to one scheme
results = engine.search_concepts("azure", scheme_uri="https://vocab.example.org/colours")
```

### Building SKOS URIs with NamespaceManager

`NamespaceManager` provides helpers for constructing well-formed SKOS IRIs:

```python
from semantica.ontology import NamespaceManager

nm = NamespaceManager(base_uri="https://vocab.example.org/")

# Full SKOS predicate URI
nm.get_skos_uri("prefLabel")
# "http://www.w3.org/2004/02/skos/core#prefLabel"

# Slug-based ConceptScheme URI anchored at the base
nm.build_concept_scheme_uri("ISO 3166 Countries")
# "https://vocab.example.org/vocab/iso-3166-countries"
```

---

## Best Practices

1.  **Reuse Standard Ontologies**: Don't reinvent `Person` or `Organization`; import FOAF or Schema.org using `ReuseManager`.
2.  **Validate Early**: Run validation during generation to catch logical errors before populating the graph.
3.  **Use Competency Questions**: Define what questions your ontology should answer and use `OntologyEvaluator` to verify.
4.  **Version Control**: Treat ontologies like code. Use `VersionManager` to track changes.

---

## See Also

- [Knowledge Graph Module](kg.md) - The instance data following the ontology
- [Reasoning Module](reasoning.md) - Uses the ontology for inference
- [Visualization Module](visualization.md) - Visualizing the class hierarchy

## Cookbook

Interactive tutorials to learn ontology generation and management:

- **[Ontology](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/14_Ontology.ipynb)**: Define domain schemas and ontologies to structure your data
  - **Topics**: OWL, RDF, schema design, ontology generation
  - **Difficulty**: Intermediate
  - **Use Cases**: Structuring domain knowledge, schema definition

- **[Unstructured to Ontology](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/12_Unstructured_to_Ontology.ipynb)**: Generate ontologies automatically from unstructured data
  - **Topics**: Automatic ontology generation, 6-stage pipeline, OWL validation
  - **Difficulty**: Advanced
  - **Use Cases**: Domain modeling, automatic schema generation
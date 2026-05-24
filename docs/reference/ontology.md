---
title: "Ontology Module"
description: "Automated ontology generation, SHACL validation, OWL/RDF export, namespace management, and LLM-powered ontology generation."
icon: "sitemap"
---

`semantica.ontology` provides the full lifecycle for knowledge graph schemas — from auto-generation and SHACL validation to OWL/RDF export. Use it for schema design, data modeling, semantic web interoperability, and SHACL-based data quality validation.

## Exported Classes

```python
from semantica.ontology import (
    OntologyGenerator,       # auto-generate from KG data (6-stage pipeline)
    LLMOntologyGenerator,    # LLM-powered ontology generation
    OntologyEngine,          # unified orchestration facade
    ClassInferrer,           # class discovery and hierarchy building
    PropertyGenerator,       # property inference and XSD type mapping
    SHACLGenerator,          # generate SHACL shapes from ontology
    OntologyValidator,       # validate graphs against SHACL shapes
    SHACLValidationReport,   # validation report with violations list
    SHACLViolation,          # individual constraint violation
    OWLGenerator,            # OWL/RDF serialization (Turtle, XML, JSON-LD)
    OntologyEvaluator,       # quality evaluation: coverage, completeness
    NamespaceManager,        # IRI generation and namespace prefix management
    OntologyAligner,         # align and merge ontologies across schemas (use OntologyEngine)
    AssociativeClassBuilder, # N-ary relationship intermediate class creation
    NamingConventions,       # PascalCase/camelCase enforcement
    DomainOntologies,        # pre-built domain ontologies
    ingest_ontology,         # load ontology from file
)
```

## What You Get

- **`OntologyGenerator`** — auto-generate ontologies from existing knowledge graph data (6-stage pipeline)
- **`LLMOntologyGenerator`** — LLM-powered ontology generation for complex domains
- **`OntologyEngine`** — unified facade that orchestrates the full ontology lifecycle
- **`SHACLGenerator`** / **`OntologyValidator`** — generate SHACL shapes and validate any graph
- **`OWLGenerator`** — serialize ontologies to Turtle, RDF/XML, JSON-LD
- **`NamespaceManager`** — IRI generation, prefix management, namespace binding
- **`OntologyEvaluator`** — coverage, completeness, and granularity quality metrics
- **`AssociativeClassBuilder`** — model N-ary relationships as intermediate OWL classes

## OntologyEngine (Unified Facade)

The `OntologyEngine` orchestrates the full ontology lifecycle — generation, validation, export, and versioning:

```python
from semantica.ontology import OntologyEngine

engine = OntologyEngine(base_uri="https://example.org/ontology/")

# Generate ontology from KG data
ontology = engine.generate_ontology({"entities": entities, "relationships": relationships})

# Validate a graph against the generated SHACL shapes
report = engine.validate(kg)
if not report.conforms:
    for v in report.violations:
        print(f"{v.severity}: {v.message} on {v.node}")

# Export to OWL Turtle
engine.export(ontology, "ontology.ttl", format="turtle")
```

## OntologyGenerator (6-Stage Pipeline)

Generate a formal ontology automatically from your knowledge graph entities and relationships:

```python
from semantica.ontology import OntologyGenerator

generator = OntologyGenerator(base_uri="https://example.org/ontology/")
ontology  = generator.generate_ontology({
    "entities":      entities,
    "relationships": relationships,
})
```

The pipeline runs through these stages in order:

1. **Semantic Network Parsing** — extract concepts and patterns from entity/relationship data
2. **YAML-to-Definition** — transform patterns into intermediate class definitions
3. **Definition-to-Types** — map definitions to OWL types (`owl:Class`, `owl:ObjectProperty`)
4. **Hierarchy Generation** — build taxonomy trees using transitive closure and cycle detection
5. **TTL Generation** — serialize to Turtle format using `rdflib`
6. **Quality Evaluation** — assess coverage, completeness, and granularity metrics

## SHACL Validation

Generate SHACL shapes from an ontology and validate any graph against them:

```python
from semantica.ontology import SHACLGenerator, OntologyValidator, SHACLValidationReport, SHACLViolation

# Generate shapes from ontology
generator  = SHACLGenerator()
shapes     = generator.generate(ontology)
shapes_ttl = shapes.serialize(format="turtle")

# Validate a graph against the shapes
validator = OntologyValidator()
report: SHACLValidationReport = validator.validate(kg, shapes=shapes)

if not report.conforms:
    violation: SHACLViolation
    for violation in report.violations:
        print(f"{violation.severity}: {violation.message}")
        print(f"  Node: {violation.node}")
        print(f"  Path: {violation.path}")
```

## LLM-Powered Ontology Generation

For complex or novel domains where schema patterns are hard to infer statistically:

```python
from semantica.ontology import LLMOntologyGenerator
from semantica.llms import Groq
import os

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

generator = LLMOntologyGenerator(llm_provider=llm)
ontology  = generator.generate(
    domain_description="A biomedical ontology for clinical trial protocols",
    examples=["Patient", "Trial", "Intervention", "Outcome"],
)
```

## OWL / RDF Export

```python
from semantica.ontology import OWLGenerator

generator = OWLGenerator()
generator.generate(ontology, path="ontology.ttl",  format="turtle")
generator.generate(ontology, path="ontology.owl",  format="xml")
generator.generate(ontology, path="ontology.json", format="json-ld")
```

## Namespace Management

```python
from semantica.ontology import NamespaceManager

ns = NamespaceManager(base_uri="https://example.org/")
ns.register("ex",     "https://example.org/")
ns.register("schema", "https://schema.org/")
ns.register("owl",    "http://www.w3.org/2002/07/owl#")

# Generate IRIs for classes and properties
class_iri    = ns.generate_class_iri("Person")
property_iri = ns.generate_property_iri("worksFor")
```

## Ontology Evaluation

Measure coverage, completeness, and granularity of a generated ontology:

```python
from semantica.ontology import OntologyEvaluator

evaluator = OntologyEvaluator()
result    = evaluator.evaluate(ontology, kg)

print(f"Class coverage:    {result.class_coverage:.2f}")
print(f"Property coverage: {result.property_coverage:.2f}")
print(f"Completeness:      {result.completeness:.2f}")
print(f"Granularity:       {result.granularity:.2f}")

for gap in result.gaps:
    print(f"Gap: {gap.description}")
```

## Ingest an Existing Ontology

Load and parse an ontology file for downstream use:

```python
from semantica.ontology import ingest_ontology

ontology_data = ingest_ontology("schema.ttl")     # Turtle
ontology_data = ingest_ontology("schema.owl")     # OWL/XML
ontology_data = ingest_ontology("schema.jsonld")  # JSON-LD
```

## Ontology Hub (v0.5.0)

A visual browser UI for the full ontology lifecycle. Launch via CLI:

```bash
pip install "semantica[explorer]"
semantica-explorer --port 8080
# Navigate to http://localhost:8080 → Ontology Hub tab
```

Features:

- **Visual editor** — create and edit classes, properties, and relationships in the browser
- **SHACL Studio** — author and validate SHACL shapes with live feedback
- **Health dashboard** — coverage, completeness, and constraint violation metrics
- **Version control** — snapshot, diff, and restore ontology versions

<Note>
  Ontology versioning (`VersionManager`, `OntologyVersion`) has moved to `semantica.change_management`. Import from there: `from semantica.change_management import VersionManager`.
</Note>

<CardGroup cols={2}>
  <Card title="Reasoning" icon="microchip" href="reasoning">
    Apply inference rules over ontology axioms.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The graph being modeled by the ontology.
  </Card>
  <Card title="Export" icon="file-export" href="export">
    Export ontologies as RDF, OWL, or JSON-LD.
  </Card>
  <Card title="Conflicts" icon="triangle-exclamation" href="conflicts">
    Detect ontology constraint violations.
  </Card>
</CardGroup>

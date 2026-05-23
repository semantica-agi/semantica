---
title: "Ontology Module"
description: "Automated ontology generation, SHACL validation, SKOS vocabularies, alignment, diff/migration, and the visual Ontology Hub."
icon: "sitemap"
---

`semantica.ontology` provides the full lifecycle for knowledge graph schemas — from auto-generation and SHACL validation to visual editing in the Ontology Hub (v0.5.0). Use it for schema design, data modeling, semantic web interoperability, and SHACL-based data quality validation.

## What You Get

- **`OntologyManager`** — define classes, properties, relationships, and constraints
- **`OntologyGenerator`** — auto-generate ontologies from existing knowledge graph data (6-stage pipeline)
- **`SHACLGenerator`** / **`SHACLValidator`** — generate and validate SHACL shapes
- **`SKOSVocabulary`** — controlled vocabulary and taxonomy management
- **`OntologyAligner`** — align and merge ontologies across schemas
- **`OntologyDiff`** / **`OntologyMigrator`** — diff and migrate ontology versions
- **`OWLExporter`** — export to Turtle, RDF/XML, JSON-LD
- **Ontology Hub** — visual browser UI for the full ontology lifecycle (v0.5.0)

## OntologyManager

Define and validate a schema for your knowledge graph:

```python
from semantica.ontology import OntologyManager

ontology = OntologyManager()
ontology.add_class("Person",       properties=["name", "birth_date"])
ontology.add_class("Organization", properties=["name", "founded_date"])
ontology.add_relationship("works_for", domain="Person", range="Organization")
ontology.add_constraint("Person", "must_have_name")

# Validate a graph against the ontology
is_valid = ontology.validate_graph(kg)

# Export as OWL Turtle
owl_ttl = ontology.export_owl(format="turtle")
```

## Auto-Generation (6-Stage Pipeline)

Generate an ontology automatically from your knowledge graph data:

```python
from semantica.ontology import OntologyGenerator

generator = OntologyGenerator()
ontology = generator.generate_from_graph(kg)
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
from semantica.ontology import SHACLGenerator, SHACLValidator

# Generate shapes
generator = SHACLGenerator()
shapes    = generator.generate(ontology)
shapes_ttl = shapes.serialize(format="turtle")

# Validate a graph
validator = SHACLValidator()
report    = validator.validate(kg, shapes=shapes)

if not report.conforms:
    for violation in report.violations:
        print(f"Violation: {violation.message} on {violation.node}")
        print(f"  Path:     {violation.path}")
        print(f"  Severity: {violation.severity}")
```

## SKOS Vocabularies

Build controlled vocabularies and taxonomies using the W3C SKOS standard:

```python
from semantica.ontology import SKOSVocabulary

vocab = SKOSVocabulary()
vocab.add_concept("Machine Learning",   broader="Artificial Intelligence")
vocab.add_concept("Deep Learning",      broader="Machine Learning")
vocab.add_concept("Computer Vision",    broader="Deep Learning")
vocab.add_alt_label("ML", for_concept="Machine Learning")

skos_ttl = vocab.export(format="turtle")
```

## Ontology Alignment

Map concepts across two ontologies and merge them:

```python
from semantica.ontology import OntologyAligner

aligner   = OntologyAligner()
alignment = aligner.align(source_ontology, target_ontology)

for mapping in alignment.mappings:
    print(f"{mapping.source} → {mapping.target}  (confidence: {mapping.confidence:.2f})")

# Merge into a unified ontology
merged = aligner.merge(source_ontology, target_ontology, alignment)
```

## Diff and Migration

Compare ontology versions and generate migration scripts for graph data:

```python
from semantica.ontology import OntologyDiff, OntologyMigrator

diff    = OntologyDiff()
changes = diff.compare(ontology_v1, ontology_v2)

for change in changes:
    print(f"{change.type}: {change.element} — {change.description}")

# Generate and apply a migration script
migrator         = OntologyMigrator()
migration_script = migrator.generate_migration(changes)
migrator.apply(kg, migration_script)
```

## OWL / RDF Export

```python
from semantica.ontology import OWLExporter

exporter = OWLExporter()
exporter.export(ontology, path="ontology.ttl",  format="turtle")
exporter.export(ontology, path="ontology.owl",  format="xml")
exporter.export(ontology, path="ontology.json", format="json-ld")
```

## Ontology Hub (v0.5.0)

A visual browser UI for the full ontology lifecycle, served by `semantica.explorer`:

```bash
pip install "semantica[explorer]"
```

```python
from semantica.explorer import start_explorer

start_explorer(graph=kg, port=8080)
# Navigate to http://localhost:8080 → Ontology Hub tab
```

Features:

- **Visual editor** — create and edit classes, properties, and relationships in the browser
- **SHACL Studio** — author and validate SHACL shapes with live feedback
- **Alignment authoring** — map concepts across ontologies with drag-and-drop
- **Health dashboard** — coverage, completeness, and constraint violation metrics
- **Version control** — snapshot, diff, and restore ontology versions

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

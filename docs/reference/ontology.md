---
title: "Ontology Module"
description: "Automated ontology generation, OWL export, SHACL validation, domain ontologies, and modular ontology development."
icon: "sitemap"
---

`semantica.ontology` provides the full lifecycle for knowledge graph schemas — from auto-generation and OWL export to SHACL validation and modular ontology development. Use it for schema design, data modeling, and semantic web interoperability.

## What You Get

<CardGroup cols={2}>
  <Card title="OntologyGenerator" icon="wand-magic-sparkles">
    Auto-generate ontologies from existing graph data using a 6-stage pipeline.
  </Card>
  <Card title="SHACLGenerator / OntologyValidator" icon="shield-check">
    Generate SHACL shapes from an ontology and validate ontologies for structural consistency.
  </Card>
  <Card title="CompetencyQuestionsManager" icon="circle-question">
    Capture, manage, and validate competency questions that define ontology requirements.
  </Card>
  <Card title="ReuseManager" icon="arrows-left-right">
    Integrate published ontologies (schema.org, FOAF) instead of generating from scratch.
  </Card>
  <Card title="DomainOntologies" icon="list-tree">
    Pre-built domain ontologies for biomedical, finance, legal, supply chain, and more.
  </Card>
  <Card title="OntologyEvaluator" icon="chart-bar">
    Measure coverage, completeness, and granularity — validate against competency questions.
  </Card>
</CardGroup>

## Quick Start

<Steps>
  <Step title="Generate an ontology from your knowledge graph">
    ```python
    from semantica.ontology import OntologyGenerator

    generator = OntologyGenerator()
    ontology  = generator.generate_from_graph(kg)
    ```
  </Step>
  <Step title="Validate the ontology">
    ```python
    from semantica.ontology import OntologyValidator

    validator = OntologyValidator(reasoner="hermit", check_consistency=True)
    result    = validator.validate(ontology)

    if not result.is_valid:
        for issue in result.issues:
            print(f"Issue: {issue.message}  (severity: {issue.severity})")
    ```
  </Step>
  <Step title="Export to OWL">
    ```python
    from semantica.ontology import OWLGenerator

    owl_gen = OWLGenerator()
    owl_gen.export_owl(ontology, file_path="ontology.ttl", format="turtle")
    owl_gen.export_owl(ontology, file_path="ontology.owl", format="xml")
    ```
  </Step>
</Steps>

## Auto-Generation — 6-Stage Pipeline

Generate an ontology automatically from your knowledge graph data:

```python
from semantica.ontology import OntologyGenerator

generator = OntologyGenerator()
ontology  = generator.generate_from_graph(kg)
```

The pipeline runs through these stages in order:

<Steps>
  <Step title="Stage 1 — Semantic Network Parsing">
    Extracts concepts and patterns from entity/relationship data.

    ```python
    generator        = OntologyGenerator()
    semantic_network = generator.parse_semantic_network(kg)
    ```
  </Step>
  <Step title="Stage 2 — YAML-to-Definition (intermediate representation)">
    Transforms extracted patterns into intermediate class definitions.

    ```python
    definitions = generator.build_definitions(semantic_network)
    ```
  </Step>
  <Step title="Stage 3 — Definition-to-OWL Types">
    Maps definitions to OWL types (`owl:Class`, `owl:ObjectProperty`).

    ```python
    from semantica.ontology import ClassInferrer, PropertyGenerator

    class_inferrer = ClassInferrer()
    classes        = class_inferrer.infer_classes(kg.entities)

    prop_generator = PropertyGenerator()
    properties     = prop_generator.infer_properties(kg.entities, kg.relationships, classes)
    ```
  </Step>
  <Step title="Stage 4 — Hierarchy Generation">
    Builds taxonomy trees using transitive closure and cycle detection.

    ```python
    hierarchy = generator.build_hierarchy(classes)
    ```
  </Step>
  <Step title="Stage 5 — TTL Generation">
    Serializes to Turtle format using `rdflib`.

    ```python
    from semantica.ontology import OWLGenerator

    owl_gen = OWLGenerator()
    ttl_str = owl_gen.generate_owl(
        {"classes": classes, "properties": properties, "hierarchy": hierarchy},
        format="turtle",   # "turtle" | "xml" | "json-ld" | "n3"
    )
    ```
  </Step>
  <Step title="Stage 6 — Quality Evaluation">
    Assesses coverage, completeness, and granularity metrics.

    ```python
    from semantica.ontology import OntologyEvaluator

    evaluator = OntologyEvaluator()
    report    = evaluator.evaluate(ttl_str, kg)
    print(f"Coverage:     {report.coverage:.2%}")
    print(f"Completeness: {report.completeness:.2%}")
    print(f"Granularity:  {report.granularity:.2%}")
    ```
  </Step>
</Steps>

## Advanced Generation Tools

<Tabs>
  <Tab title="RequirementsSpecManager">
    Capture and manage ontology requirements before generation:

    ```python
    from semantica.ontology import RequirementsSpecManager

    spec = RequirementsSpecManager()
    spec.add_competency_question("What organizations are headquartered in California?")
    spec.add_competency_question("Who founded each organization?")
    spec.add_competency_question("What products does each organization sell?")

    spec.set_scope(
        domain="Technology industry",
        excluded_types=["Event", "Date"],
        min_confidence=0.7,
    )

    generator = OntologyGenerator()
    ontology  = generator.generate_from_graph(kg, requirements=spec)
    ```
  </Tab>
  <Tab title="LLMOntologyGenerator">
    Generate ontologies directly from natural language:

    ```python
    from semantica.ontology import LLMOntologyGenerator
    from semantica.llms import Groq
    import os

    llm       = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    generator = LLMOntologyGenerator(llm_provider=llm)

    ontology = generator.generate_from_description(
        description="An ontology for tracking pharmaceutical clinical trials, including drugs, patients, dosages, outcomes, and adverse events.",
        num_classes=20,
    )

    ontology = generator.generate_from_corpus(
        documents=["clinical_trial_protocol.pdf"],
        domain_hint="biomedical",
    )

    ontology = generator.refine(
        ontology,
        questions=["What dosage was given to each patient?", "What adverse events occurred?"],
    )
    ```
  </Tab>
  <Tab title="ReuseManager">
    Integrate published ontologies instead of generating from scratch:

    ```python
    from semantica.ontology import ReuseManager

    manager = ReuseManager()
    manager.load_ontology("schema.org", source="https://schema.org/version/latest/schemaorg-current-https.ttl")
    manager.load_ontology("foaf",       source="http://xmlns.com/foaf/spec/index.rdf")

    candidates = manager.find_reusable_classes(
        your_classes=["Person", "Organization", "Product"],
        loaded_ontologies=["schema.org", "foaf"],
    )
    for candidate in candidates:
        print(f"{candidate.local_class} → reuse {candidate.external_uri}  (similarity: {candidate.similarity:.2f})")

    merged = manager.merge_reused(your_ontology, candidates)
    ```
  </Tab>
  <Tab title="DomainOntologies">
    Pre-built domain ontologies for common verticals:

    ```python
    from semantica.ontology import DomainOntologies

    catalog = DomainOntologies()

    for domain in catalog.list_domains():
        print(f"{domain.name}: {domain.description}  ({domain.class_count} classes)")

    biomedical   = catalog.load("biomedical")    # SNOMED CT-aligned
    finance      = catalog.load("finance")       # FinancialInstrument, Company, Market
    legal        = catalog.load("legal")         # Contract, Party, Jurisdiction
    supply_chain = catalog.load("supply_chain")  # Supplier, Product, Shipment

    biomedical.add_class("ClinicalTrial", parent="Study", properties=["phase", "participants"])
    ```

    Available domains: `biomedical`, `finance`, `legal`, `supply_chain`, `cybersecurity`, `e_commerce`, `hr`.
  </Tab>
</Tabs>

## ModuleManager

Build ontologies as composable modules — keep domain logic separated and reusable:

```python
from semantica.ontology import ModuleManager

manager = ModuleManager()

core_module    = manager.create_module("core",    base_uri="http://example.org/core#")
finance_module = manager.create_module("finance", base_uri="http://example.org/finance#")

core_module.add_class("Entity",     properties=["id", "name"])
finance_module.add_class("Company", parent="Entity", properties=["ticker", "revenue"])

finance_module.import_module(core_module)
unified = manager.merge_modules([core_module, finance_module])
```

## NamespaceManager

Manage IRI prefixes and generate consistent URIs for all ontology terms:

```python
from semantica.ontology import NamespaceManager

ns_manager = NamespaceManager(base_uri="http://example.org/")
ns_manager.register("ex",     "http://example.org/")
ns_manager.register("schema", "https://schema.org/")

class_iri = ns_manager.generate_iri("Person")          # → "http://example.org/Person"
prop_iri  = ns_manager.generate_iri("worksFor", prefix="ex")  # → "http://example.org/worksFor"
iri       = ns_manager.resolve("schema:Organization")   # → "https://schema.org/Organization"
```

## OntologyEvaluator

Measure quality across coverage, completeness, and competency questions:

```python
from semantica.ontology import OntologyEvaluator

evaluator = OntologyEvaluator()
report    = evaluator.evaluate(ontology, kg)
print(f"Coverage:     {report.coverage:.2%}")
print(f"Completeness: {report.completeness:.2%}")
print(f"Granularity:  {report.granularity:.2%}")

questions  = ["What organizations were founded in California?", "Who are the employees of Apple Inc.?"]
cq_results = evaluator.validate_competency_questions(ontology, kg, questions)
for q, result in zip(questions, cq_results):
    print(f"Q: {q}  →  Answerable: {result.answerable}  ({result.reason})")
```

## Ontology Hub (v0.5.0)

A visual browser UI for the full ontology lifecycle, served by the Explorer CLI:

```bash
pip install "semantica[explorer]"
semantica explore
# Navigate to http://localhost:8080 → Ontology Hub tab
```

Features: visual editor, SHACL Studio, health dashboard, and version control.

## Tips and Common Pitfalls

<Tip>
  **Define competency questions before generating.** An ontology without competency questions has no measurable success criteria. Write 5–10 natural language questions your ontology must answer before calling `OntologyGenerator`. Then validate them with `OntologyEvaluator.validate_competency_questions()`.
</Tip>

<Tip>
  **Reuse before generating.** `DomainOntologies` and `ReuseManager` give you schema.org, FOAF, and domain-specific ontologies that took years to develop. Reusing established classes (`schema:Organization`, `foaf:Person`) also improves interoperability with external data.
</Tip>

<Warning>
  **`LLMOntologyGenerator` is great for prototyping, not production.** LLM-generated ontologies are a useful starting point but need expert review. Use `OntologyEvaluator` and manual SHACL authoring to harden the schema before relying on it for production graph validation.
</Warning>

<Warning>
  **Always validate after schema changes.** When you add new classes or properties, run `OntologyValidator.validate(ontology)` immediately. Validation issues often surface data quality problems that were silently passing before.
</Warning>

<Tip>
  **Use `ModuleManager` for large ontologies.** A monolithic 500-class ontology becomes unmanageable quickly. Split by domain (`core`, `finance`, `legal`) and use `owl:imports` to compose them — changes in one module don't break others.
</Tip>

<Tip>
  **Namespace your terms consistently.** All classes and properties need stable IRIs. Use `NamespaceManager` to generate them programmatically — never hardcode IRI strings in code, because base URIs change when projects move.
</Tip>

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

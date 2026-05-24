---
title: "Seed Module"
description: "Bootstrap Knowledge Graphs from verified, structured sources — taxonomies, reference tables, product catalogs, and domain anchors."
icon: "database"
---

`semantica.seed` gives your knowledge graph a reliable starting point. Rather than building from an empty graph and hoping extraction produces consistent reference data, you load verified, structured sources first — ISO codes, employee rosters, product catalogs, domain taxonomies — then merge freshly extracted data on top.

## Exported Classes

```python
from semantica.seed import (
    SeedDataManager,   # coordinator: register_source, create_foundation_graph, integrate_with_extracted
    SeedDataSource,    # {name, source_type, path, config} — dataclass for a registered source
    SeedData,          # {entities, relationships, metadata} — loaded seed data container
)
```

## What You Get

<CardGroup cols={2}>
  <Card title="SeedDataManager" icon="database">
    Register sources, build a foundation graph, validate quality, and merge with extracted data.
  </Card>
  <Card title="SeedDataSource" icon="file-code">
    Typed source definition supporting CSV, JSON, SQL, API, and RDF with format-specific config.
  </Card>
  <Card title="Foundation Graph" icon="circle-plus">
    Build a foundation graph from all registered sources in one pass, ready to merge with extracted data.
  </Card>
  <Card title="Merge Strategies" icon="arrows-merge">
    `seed_first`, `extracted_first`, and `smart_merge` with property-level conflict detection.
  </Card>
  <Card title="Validation" icon="shield-check">
    Required field checks, ID uniqueness, type consistency, reference integrity, and encoding validation before loading.
  </Card>
  <Card title="Versioning" icon="clock-rotate-left">
    Track seed data versions across pipeline runs and diff changes between versions.
  </Card>
</CardGroup>

<Tip>
  **When to use the Seed Module:** Bootstrapping with structured reference data (taxonomies, user lists, product catalogs), loading immutable facts (ISO country codes, standard ontology terms) that extracted data should not override, ensuring test reproducibility with deterministic datasets, and anchoring entity disambiguation with canonical forms.
</Tip>

## Quick Start

<Steps>
  <Step title="Register your seed sources">
    ```python
    from semantica.seed import SeedDataManager

    manager = SeedDataManager()

    manager.register_source("countries",  "csv",  "data/countries.csv")
    manager.register_source("taxonomy",   "json", "data/taxonomy.json")
    manager.register_source("employees",  "csv",  "data/employees.csv")
    ```
  </Step>
  <Step title="Build the foundation graph">
    ```python
    foundation_kg = manager.create_foundation_graph()

    print(f"Foundation nodes: {foundation_kg.node_count}")
    print(f"Foundation edges: {foundation_kg.edge_count}")
    ```
  </Step>
  <Step title="Validate before loading">
    ```python
    report = manager.validate_quality(manager.load_source("employees"))

    if not report.is_valid:
        for issue in report.issues:
            print(f"[{issue.severity}] Row {issue.row}: {issue.message}")
    else:
        print(f"Validated {report.record_count} records — no issues found")
    ```
  </Step>
  <Step title="Merge with extracted data">
    ```python
    final_kg = manager.integrate_with_extracted(
        seed_graph=foundation_kg,
        extracted_data=new_entities,
        strategy="smart_merge",
    )
    print(f"Final graph: {final_kg.node_count} nodes, {final_kg.edge_count} edges")
    ```
  </Step>
</Steps>

## SeedDataSource Types

<Tabs>
  <Tab title="CSV">
    ```python
    from semantica.seed import SeedDataSource

    csv_source = SeedDataSource(
        name="employees",
        type="csv",
        path="data/employees.csv",
        config={
            "delimiter": ";",
            "encoding":  "utf-8",
            "id_column": "employee_id",
            "type":      "Person",
        }
    )

    manager.register_source("employees", "csv", csv_source.path, config=csv_source.config)
    ```

    Best for: employee rosters, product lists, reference tables.
  </Tab>
  <Tab title="JSON">
    ```python
    json_source = SeedDataSource(
        name="taxonomy",
        type="json",
        path="data/taxonomy.json",
        config={"encoding": "utf-8"}
    )
    ```

    Expects an array of entity objects. Best for: taxonomies, ontology term lists, structured configs.
  </Tab>
  <Tab title="SQL">
    ```python
    sql_source = SeedDataSource(
        name="products",
        type="sql",
        path="postgresql://user:pass@localhost/db",
        config={"query": "SELECT id, name, category FROM products WHERE active = true"}
    )
    ```

    Best for: live database tables — PostgreSQL, MySQL, SQLite.
  </Tab>
  <Tab title="API & RDF">
    ```python
    # API source — fetch from a REST endpoint
    api_source = SeedDataSource(
        name="geo_codes",
        type="api",
        path="https://restcountries.com/v3.1/all",
        config={"fields": ["name", "cca2", "region"]}
    )

    # RDF source — OWL ontologies or Turtle files
    rdf_source = SeedDataSource(
        name="domain_ontology",
        type="rdf",
        path="data/ontology.ttl",
        config={"format": "turtle"}
    )
    ```

    API: external reference APIs (countries, currencies, geo). RDF: existing knowledge bases, OWL ontologies.
  </Tab>
  <Tab title="Type Reference">

    | Type | Path Format | Use Case |
    | ---- | ----------- | -------- |
    | `csv` | File path | Employee rosters, product lists, reference tables |
    | `json` | File path | Taxonomies, ontology term lists, structured configs |
    | `sql` | Connection string | Live database tables — PostgreSQL, MySQL, SQLite |
    | `api` | URL | External reference APIs (countries, currencies, geo) |
    | `rdf` | File path | OWL ontologies, Turtle files, existing knowledge bases |

  </Tab>
</Tabs>

## SeedDataManager Reference

| Method | Description |
| ------ | ----------- |
| `register_source(name, format, path)` | Add a named data source to the registry |
| `create_foundation_graph()` | Build a KG from all registered sources |
| `validate_quality(seed_data)` | Check schema compliance, required fields, and duplicates |
| `integrate_with_extracted(seed, extracted, strategy)` | Merge seed and extracted graphs |
| `export_seed_data(path, format)` | Export seed graph to RDF (`turtle`, `json-ld`), JSON, or CSV |
| `load_from_csv(path)` | Load seed records from a CSV file |
| `load_from_json(path)` | Load seed records from a JSON file |
| `list_sources()` | List all registered source names and their formats |
| `get_version(name)` | Get the current version metadata for a named source |

## Merge Strategies

<Tabs>
  <Tab title="seed_first">
    Seed data wins on every conflicting property. Use when seed encodes authoritative reference facts that must not be overridden.

    ```python
    final_kg = manager.integrate_with_extracted(
        seed_graph=foundation_kg,
        extracted_data=new_entities,
        strategy="seed_first",
    )
    ```

    Best for: ISO codes, canonical entity names, official taxonomy IDs, employee records.
  </Tab>
  <Tab title="extracted_first">
    Extracted data overrides seed on conflicting properties. Use when new documents contain more current information than your reference data.

    ```python
    final_kg = manager.integrate_with_extracted(
        seed_graph=foundation_kg,
        extracted_data=new_entities,
        strategy="extracted_first",
    )
    ```

    Best for: frequently changing attributes like addresses, titles, revenue figures.
  </Tab>
  <Tab title="smart_merge">
    Property-level merge with conflict detection — irresolvable conflicts are logged for manual review rather than silently overwritten.

    ```python
    final_kg = manager.integrate_with_extracted(
        seed_graph=foundation_kg,
        extracted_data=new_entities,
        strategy="smart_merge",
    )
    ```

    Best for: general-purpose pipelines where surfacing conflicts is more valuable than silently losing data.
  </Tab>
</Tabs>

## Built-in Datasets

Register built-in reference datasets as named sources and load them into your foundation graph:

```python
from semantica.seed import SeedDataManager

manager = SeedDataManager()

# Register built-in reference sources by format and path
manager.register_source("countries",  "csv",  "data/iso_countries.csv")
manager.register_source("currencies", "json", "data/iso_currencies.json")

foundation_kg = manager.create_foundation_graph()
```

| Dataset | Content |
| ------- | ------- |
| `companies` | Fortune 500 companies with type, sector, HQ |
| `countries` | ISO 3166 country codes, regions, populations |
| `currencies` | ISO 4217 codes, symbols, names |
| `person_names` | Common first/last names for synthetic data |

## Full Pipeline Example

```python
from semantica.seed import SeedDataManager
from semantica.ingest import FileIngestor
from semantica.parse import DocumentParser
from semantica.split import TextSplitter
from semantica.semantic_extract import NERExtractor, RelationExtractor
from semantica.kg import GraphBuilder
from semantica.llms import Groq
import os

llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))

# Step 1 — Build the foundation from verified reference data
seed_manager = SeedDataManager()
seed_manager.register_source("taxonomy",  "json", "data/taxonomy.json")
seed_manager.register_source("employees", "csv",  "data/employees.csv")
foundation_kg = seed_manager.create_foundation_graph()

# Step 2 — Ingest and extract from unstructured documents
ingestor  = FileIngestor()
parser    = DocumentParser()
splitter  = TextSplitter(method="semantic_transformer", chunk_size=512)
ner       = NERExtractor(method="llm", llm_provider=llm)
rel_ext   = RelationExtractor(method="llm", llm_provider=llm)

sources                 = ingestor.ingest("news_articles/")
extracted_entities      = []
extracted_relationships = []

for source in sources:
    parsed = parser.parse(source)
    chunks = splitter.split_document(parsed)
    for chunk in chunks:
        entities      = ner.extract(chunk.text)
        relationships = rel_ext.extract(chunk.text, entities=entities)
        extracted_entities.extend(entities)
        extracted_relationships.extend(relationships)

# Step 3 — Merge seed and extracted data
final_kg = seed_manager.integrate_with_extracted(
    seed_graph=foundation_kg,
    extracted_data=extracted_entities,
    strategy="seed_first",
)
print(f"Final graph: {final_kg.node_count} nodes, {final_kg.edge_count} edges")
```

## Versioning

Track seed data versions to detect when reference data changes between pipeline runs:

```python
manager = SeedDataManager()
manager.register_source("taxonomy", "json", "data/taxonomy.json")

version = manager.get_version("taxonomy")
print(f"Version: {version.version_id}")
print(f"Hash:    {version.checksum}")
print(f"Records: {version.record_count}")
print(f"Updated: {version.last_modified}")
```

## YAML Configuration

Define sources in YAML for production deployments — no code changes needed to switch environments:

```yaml
seed:
  sources:
    - name: "employees"
      type: "csv"
      path: "./data/employees.csv"
      config:
        id_column: "employee_id"
        type: "Person"
    - name: "taxonomy"
      type: "json"
      path: "./data/taxonomy.json"
    - name: "products"
      type: "sql"
      path: "${DATABASE_URL}"
      config:
        query: "SELECT id, name, category FROM products WHERE active = true"
  merge:
    strategy: "smart_merge"
  validation:
    strict: true
    required_fields: ["id", "type"]
```

Environment variable overrides:

```bash
export SEMANTICA_SEED_DATA_DIR=./data/seed
export SEMANTICA_SEED_MERGE_STRATEGY=seed_first
```

## Tips and Common Pitfalls

<Warning>
  **Load seed data before extracted data.** Seed data is your ground truth — normalised, curated, and already de-duplicated. Load it first with `create_foundation_graph()`, then merge extracted entities on top. Merging in the wrong order lets noisy extracted data overwrite trusted reference values.
</Warning>

<Tip>
  **Use `seed_first` merge strategy for reference data.** When seed data encodes authoritative facts (official company names, canonical taxonomy IDs, employee records), `strategy="seed_first"` ensures those values win over extracted values. Use `smart_merge` only when extracted data may be more current than the seed.
</Tip>

<Warning>
  **Validate before loading.** `manager.validate_quality(seed_data)` catches missing required fields, type inconsistencies, and duplicate IDs before they corrupt your graph. Running validation after loading means you'll need to roll back. Validation is fast — always run it first.
</Warning>

<Tip>
  **Register all sources before calling `create_foundation_graph()`.** `create_foundation_graph()` processes all registered sources in one pass. Registering a source after calling it means that source is silently excluded. Register all sources at the start of your script, then call `create_foundation_graph()` once.
</Tip>

<Tip>
  **Track seed versions to detect drift.** Use `manager.get_version()` to check the checksum and record count for each registered source between pipeline runs. If a taxonomy file changes, downstream entity normalisation and deduplication thresholds may need re-tuning — don't treat seed data as static.
</Tip>

<Tip>
  **Use YAML configuration for production deployments.** Hard-coding source paths in Python scripts makes environment-switching (dev → staging → prod) fragile. Declare sources in `config.yaml` under the `seed:` key and override paths with `SEMANTICA_SEED_DATA_DIR`. This way, the same code runs in every environment.
</Tip>

<CardGroup cols={2}>
  <Card title="Ingest" icon="file-import" href="ingest">
    Load unstructured data alongside seed data.
  </Card>
  <Card title="Knowledge Graph" icon="diagram-project" href="kg">
    The target graph that seed data populates.
  </Card>
  <Card title="Deduplication" icon="copy" href="deduplication">
    Handle duplicates during seed-extracted merge.
  </Card>
  <Card title="Pipeline" icon="gear" href="pipeline">
    Incorporate seed loading as a named pipeline step.
  </Card>
</CardGroup>

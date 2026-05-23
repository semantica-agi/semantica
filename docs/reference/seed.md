---
title: "Seed Module"
description: "Seed data management for initializing Knowledge Graphs from trusted, verified sources."
icon: "database"
---

`semantica.seed` provides a system for bootstrapping Knowledge Graphs with verified, structured data from trusted sources — taxonomies, reference tables, user lists, product catalogs — so you start with a reliable foundation rather than an empty graph.

## What You Get

- **`SeedDataManager`** — register sources, build a foundation graph, and integrate with extracted data
- **`SeedDataSource`** — define individual data sources with format, path, and config
- **Merge strategies** — `seed_first`, `extracted_first`, `smart_merge` for combining seed and extracted data
- **Validation** — check data quality and schema compliance before loading
- **Versioning** — track and manage versions of seed data sources

<Tip>
  **When to use the Seed Module:**

- **Bootstrapping** — you have existing structured data (taxonomies, user lists, product catalogs) to build on
- **Reference data** — load immutable reference information (countries, ISO codes, ontology terms)
- **Testing** — load consistent, reproducible datasets for development and CI pipelines
</Tip>

## SeedDataManager

The primary interface for seed data:

```python
from semantica.seed import SeedDataManager

manager = SeedDataManager()
manager.register_source("countries", "csv",  "data/countries.csv")
manager.register_source("taxonomy",  "json", "data/taxonomy.json")

# Build a foundation KG from all registered sources
foundation_kg = manager.create_foundation_graph()
```

### Core Methods

| Method | Description |
| ------ | ----------- |
| `register_source(name, format, location)` | Add a data source to the registry |
| `create_foundation_graph()` | Build a KG from all registered sources |
| `validate_quality(seed_data)` | Check data quality and completeness |
| `integrate_with_extracted(seed, extracted)` | Merge seed and extracted graphs |
| `export_seed_data(path, format)` | Export seed data to RDF, JSON, or CSV |

## SeedDataSource

Define a source with format-specific configuration:

```python
from semantica.seed import SeedDataSource

source = SeedDataSource(
    name="taxonomy",
    type="json",          # "csv" | "json" | "api" | "sql"
    path="taxonomy.json",
    config={"encoding": "utf-8"}
)
```

## Merge Strategies

Control how seed data and extracted data are combined:

```python
final_kg = manager.integrate_seed_extracted(
    seed_graph=foundation_kg,
    extracted_data=new_data,
    strategy="seed_first"   # see options below
)
```

| Strategy | Behavior |
| -------- | -------- |
| `seed_first` | Seed data wins on conflicts — use for authoritative reference data |
| `extracted_first` | Extracted data overrides seed — use when new data is more current |
| `smart_merge` | Property-level merging with conflict detection and resolution |

## Bootstrapping a KG

Full example — load foundation data then merge with freshly ingested content:

```python
from semantica.seed import SeedDataManager
from semantica.ingest import FileIngestor
from semantica.semantic_extract import NERExtractor
from semantica.llms import Groq
import os

# Build foundation from verified reference data
manager = SeedDataManager()
manager.register_source("taxonomy",  "json", "taxonomy.json")
manager.register_source("employees", "csv",  "employees.csv")
foundation_kg = manager.create_foundation_graph()

# Ingest and extract from new sources
llm = Groq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
ingestor = FileIngestor()
ner = NERExtractor(method="llm", llm_provider=llm)

sources = ingestor.ingest("news_articles/")
new_data = [ner.extract(s.content) for s in sources]

# Merge — seed data takes precedence for reference facts
final_kg = manager.integrate_seed_extracted(
    seed_graph=foundation_kg,
    extracted_data=new_data,
    strategy="seed_first"
)
```

## Configuration

```yaml
seed:
  sources:
    - name: "employees"
      type: "csv"
      path: "./data/employees.csv"
    - name: "taxonomy"
      type: "json"
      path: "./data/taxonomy.json"
  merge:
    strategy: "seed_first"
  validation:
    strict: true
```

Environment variable overrides:

```bash
export SEED_DATA_DIR=./data/seed
export SEED_MERGE_STRATEGY=seed_first
```

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
    Incorporate seed loading as a pipeline step.
  </Card>
</CardGroup>

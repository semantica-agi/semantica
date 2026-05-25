---
name: semantica
description: Semantica full-stack knowledge graph skill for context graphs, decision intelligence, explainability, extraction, reasoning, visualization, ontology, provenance, policy, and export workflows.
---

# Semantica

This Skill helps Claude apply Semantica knowledge graph capabilities to context graph analysis, decision intelligence, explainability, semantic extraction, graph analytics, reasoning, provenance, ontology, policy, ingestion, deduplication, and export.

## When to use this Skill

- The user asks about knowledge graphs, entities, relations, triplets, or semantic extraction.
- A task requires context graph analysis, graph topology, centrality, communities, paths, or embeddings.
- The request involves decision intelligence, causal influence, decision graphs, or outcome analysis.
- The user asks for explainability, decision rationale, or transparency for graph results.
- The request involves reasoning: deductive, abductive, SPARQL, Datalog, or Rete rules.
- The user needs provenance, audit history, lineage tracking, or change tracing.
- The request is about ontology modeling, schema validation, or policy enforcement.
- Data must be ingested from files, databases, APIs, repositories, or MCP servers.
- There is a need to deduplicate entities, normalize graph data, or merge duplicate graph objects.
- The user wants to export graphs to JSON, RDF, Parquet, CSV, GraphML, or similar.

## What this Skill contains

- Semantic extraction guidance for NER, relation extraction, event detection, coreference resolution, and triplet generation.
- Context graph and graph analytics workflows for topology, centrality, community detection, path finding, embeddings, and decision insights.
- Decision intelligence support for causal reasoning, decision impact, decision graphs, and outcome analysis.
- Explainability guidance for decision rationale, graph reasoning, rule traces, and result transparency.
- Reasoning support for logic, hypotheses, SPARQL, Datalog, and rule-based inference.
- Provenance and audit guidance for tracing sources, recording changes, and verifying graph lineage.
- Ontology guidance for defining concepts, validating schemas, and modeling relationships.
- Policy checks for compliance evaluation and graph governance.
- Temporal analysis guidance for event timelines and graph evolution.
- Deduplication support for duplicate detection, fuzzy matching, and graph cleanup.
- Export workflows for sharing results in multiple structured formats.

## Best prompt patterns

Use clear task descriptions, and mention the desired output format when possible.

- "Extract entities, relations, and events from this text and summarize the resulting graph." 
- "Analyze this context graph and show the top 5 most influential nodes." 
- "Generate a decision intelligence report with causal impact and explainability." 
- "Run a provenance trace for node X and describe its history." 
- "Validate the ontology for this graph and report any schema problems." 
- "Ingest the data from this MCP server and merge it into the current graph." 
- "Export the graph to JSON and GraphML with node and edge metadata."

## How Claude should use this Skill

1. Read the YAML metadata and identify whether the request matches Semantica graph, context graph, decision intelligence, or extraction tasks.
2. Load this Skill when the request mentions Semantica, knowledge graphs, context graphs, decision intelligence, explainability, reasoning, or provenance.
3. Use the instructions here to choose the right workflow and then read additional files or scripts only if needed.

## Authoring note

This Skill is purposely concise and focused on task selection. It is not intended to include every detail; Claude should use the filesystem-based model to load any extra reference files only when asked.

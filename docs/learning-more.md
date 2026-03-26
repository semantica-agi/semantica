# Learning More

Structured learning paths, quick references, and performance guidance for going deeper with Semantica.

---

## Learning Paths

<div class="grid cards" markdown>

-   :material-school: **Beginner** (1–2 hours)
    ---
    New to Semantica and knowledge graphs.

    [Start here](#beginner-path)

-   :material-compass: **Intermediate** (4–6 hours)
    ---
    Comfortable with basics, building production applications.

    [Start here](#intermediate-path)

-   :material-rocket: **Advanced** (8+ hours)
    ---
    Enterprise applications and customization.

    [Start here](#advanced-path)

</div>

---

### Beginner Path

1. **Installation & Setup** — [Installation Guide](installation.md)
2. **Core Concepts** — [Core Concepts](concepts.md) + [Getting Started](getting-started.md)
3. **First Knowledge Graph** — [Quickstart Tutorial](quickstart.md)
4. **Interactive Introduction** — [Welcome to Semantica notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)
5. **Hands-On Practice** — [Your First Knowledge Graph notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)

---

### Intermediate Path

1. **All Modules** — [Modules Guide](modules.md)
2. **Advanced Graph Construction** — [Building Knowledge Graphs notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/07_Building_Knowledge_Graphs.ipynb)
3. **Embeddings & Search** — [Embeddings notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/09_Embeddings.ipynb)
4. **GraphRAG** — [GraphRAG Complete notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)
5. **Multi-Source Integration** — [Multi-Source Data Integration notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb)
6. **Use Case Examples** — [Use Cases](use-cases.md)

---

### Advanced Path

1. **Architecture Deep Dive** — [Architecture Guide](architecture.md)
2. **Temporal Graphs** — [Temporal Graphs notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/04_Temporal_Graphs.ipynb)
3. **Ontologies** — [Ontology notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/14_Ontology.ipynb)
4. **Visualization** — [Complete Visualization Suite notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/03_Complete_Visualization_Suite.ipynb)
5. **Export Pipelines** — [Multi-Format Export notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/advanced/05_Multi_Format_Export.ipynb)
6. **Production GraphRAG** — [GraphRAG Complete notebook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/use_cases/advanced_rag/01_GraphRAG_Complete.ipynb)

---

## Configuration Reference

| Setting | Environment Variable | Default |
|---------|---------------------|---------|
| OpenAI API Key | `OPENAI_API_KEY` | `None` |
| Embedding Provider | `SEMANTICA_EMBEDDING_PROVIDER` | `"openai"` |
| Graph Backend | `SEMANTICA_GRAPH_BACKEND` | `"networkx"` |

---

## Troubleshooting

<div class="grid cards" markdown>

-   :material-alert: **Import Errors**
    ---
    `ModuleNotFoundError`

    Verify installation: `pip list | grep semantica`. Ensure Python 3.8+.

-   :material-key: **API Key Errors**
    ---
    `AuthenticationError`

    Set `OPENAI_API_KEY` (or the relevant provider key) as an environment variable.

-   :material-memory: **Memory Errors**
    ---
    `MemoryError` or OOM crashes

    Reduce batch sizes or switch to a persistent graph backend (Neo4j, FalkorDB).

-   :material-speedometer: **Slow Processing**
    ---
    Long runtimes on large datasets

    Enable parallel processing (`PipelineBuilder` workers) and GPU acceleration.

</div>

---

## Performance Optimization

### Batch Processing

Process documents in batches rather than one at a time. Configure chunk sizes based on available RAM.

### Parallel Execution

`PipelineBuilder` supports configurable worker counts per stage for independent operations.

### Backend Selection

| Operation | NetworkX | Neo4j / FalkorDB |
|-----------|----------|------------------|
| Graph construction | Fast | Moderate |
| Query performance | Moderate | Fast |
| Scalability | Low (in-memory) | High (persistent) |

Use NetworkX for development and smaller graphs; switch to a persistent backend for production at scale.

---

## Security Best Practices

**API keys**
- Store in environment variables or a secrets manager
- Never hardcode keys or commit them to version control
- Rotate keys regularly

**Data privacy**
- Use local embedding models for sensitive data
- Avoid sending PII to external APIs without appropriate data handling agreements
- Encrypt sensitive graph exports at rest

---

## Next Steps

- [Cookbook](cookbook.md) — interactive Jupyter notebook tutorials
- [API Reference](reference/core.md) — complete technical documentation
- [Use Cases](use-cases.md) — real-world domain examples
- [FAQ](faq.md) — common questions

!!! info "Questions or feedback?"
    [Open an issue](https://github.com/Hawksight-AI/semantica/issues) or [start a discussion](https://github.com/Hawksight-AI/semantica/discussions).

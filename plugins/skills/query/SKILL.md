---
name: query
description: Query the Semantica knowledge graph using SPARQL, Cypher, keyword search, and structured graph query patterns.
---

# /semantica:query

Run graph queries and search. Usage: `/semantica:query <mode> [args]`

`$ARGUMENTS` = query mode + query string or filter.

---

## `sparql <query>`

Execute a SPARQL query against the graph.

```python
from semantica.query import QueryEngine

engine = QueryEngine()
results = engine.query_sparql(query)
```

Return: query bindings as a Markdown table.

---

## `cypher <query>`

Execute a Cypher-like query.

```python
results = engine.query_cypher(query)
```

Output: node/relationship results and path summaries.

---

## `search <keywords> [--filter <type>]`

Search graph entities by keyword.

```python
results = engine.search(keywords=keywords, filter_type=filter_type)
```

Return: ranked matches with entity types and relevance scores.

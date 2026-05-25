---
name: extract
description: Run the full Semantica semantic extraction pipeline on a file or selected text — NER, relations, events, coreference resolution, triplets, and validation. Clears result cache before each run. Returns Markdown tables with entity/relation/event/triplet results and inline validator warnings.
---

# /semantica:extract

Run the full extraction pipeline. Usage: `/semantica:extract [file_path | "inline text"]`

`$ARGUMENTS` = file path, inline text in quotes, or blank (uses active editor file).

---

## Steps

**1. Resolve the source.**
- If `$ARGUMENTS` is a readable file path → `text = open(path).read()`
- If it's quoted inline text → use directly
- If blank → use the active editor file

**2. Clear the result cache** to prevent cross-invocation pollution:

```python
from semantica.semantic_extract.cache import _result_cache
_result_cache.clear()
```

**3. Run the full pipeline:**

```python
from semantica.semantic_extract import (
    NamedEntityRecognizer,
    RelationExtractor,
    EventDetector,
    CoreferenceResolver,
    TripletExtractor,
    ExtractionValidator,
)

# Named Entity Recognition
ner = NamedEntityRecognizer()
entities = ner.extract(text)

# Relation Extraction
rel = RelationExtractor()
relations = rel.extract(text)

# Event Detection
evt = EventDetector()
events = evt.extract(text)

# Coreference Resolution — resolve pronouns/aliases before extraction
coref = CoreferenceResolver()
resolved_text = coref.resolve(text)

# Triplet Extraction (subject–predicate–object)
triplet = TripletExtractor()
triplets = triplet.extract(resolved_text)

# Validate quality
validator = ExtractionValidator()
issues = validator.validate(entities, relations)
```

**4. Report validator warnings** above results:
```
⚠ ExtractionValidator: <warning message>
```

**5. Return results as Markdown tables:**

**Entities** (N total)
| Label | Type | Confidence | Span |
|-------|------|------------|------|

**Relations** (M total)
| Source | Relation Type | Target | Confidence |
|--------|---------------|--------|------------|

**Events** (K total)
| Label | Type | Participants | Confidence |
|-------|------|--------------|------------|

**Triplets** (J total)
| Subject | Predicate | Object | Confidence |
|---------|-----------|--------|------------|

**6. Summary line:**
```
Extracted: N entities, M relations, K events, J triplets — from <source>
```

For large files (>50KB), process in chunks and show a progress indicator. Highlight any entities appearing in the context graph already (`ContextGraph.has_node(label)`) with `[in graph]` tag.

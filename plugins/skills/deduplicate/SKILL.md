---
name: deduplicate
description: Detect duplicate entities, duplicate groups, and relationship duplicates in Semantica using fuzzy matching, schema heuristics, and graph similarity.
---

# /semantica:deduplicate

Remove duplicates from the knowledge graph. Usage: `/semantica:deduplicate <strategy> [args]`

`$ARGUMENTS` = deduplication strategy + optional entity or threshold.

---

## `entities [--threshold <score>] [--field <name>]`

Detect duplicate entities and group them by similarity.

```python
from semantica.deduplication import DuplicateDetector

finder = DuplicateDetector()
candidates = finder.detect_duplicates(entities, threshold=threshold)
groups = finder.detect_duplicate_groups(entities, threshold=threshold)
```

Output: duplicate candidate list, duplicate groups, and representative merge recommendations.

---

## `relations [--similarity <score>]`

Detect duplicate relationships and normalize edge representations.

```python
from semantica.deduplication import DuplicateDetector

finder = DuplicateDetector()
relations = finder.detect_duplicates(relation_list, threshold=similarity)
```

Result: duplicate relation candidates, normalized relationship groups, and cleanup summary.

"""The names a relationship record may use for the two ends of an edge.

The local graph store names them ``source_id`` and ``target_id``. The server
backends name them ``start_node_id`` and ``end_node_id``: Neo4j, FalkorDB and
Neptune directly, AGE after renaming its raw ``start_id``/``end_id`` edge
fields. Every serializer reads only the ``source*`` and ``target*`` spellings,
so a record written by a backend reads as having no endpoints at all.

Anything that has to recognise a relationship, or hand one to a serializer,
should take the names from here rather than restate them. Two copies of this
list drift: the router recognised the server names while the Parquet classifier
did not, and a store-shaped edge collection was written with the entity schema.
"""

from typing import Any, Dict, List, Tuple

# Knowledge-graph keys whose values are relationship records.
RELATIONSHIP_COLLECTIONS: Tuple[str, ...] = ("relationships", "edges")

CANONICAL_SOURCE = "source_id"
CANONICAL_TARGET = "target_id"

# Accepted spellings, canonical first. Only names that cannot be an entity
# field: `start` and `end` are the offset columns of every entity schema here
# (`parquet_exporter.ENTITY_SCHEMA`, `arrow_exporter`, `csv_exporter`), and
# reading them as endpoints turns an entity record into a relationship with
# meaningless ids. `from`/`to`/`src`/`dst` are left to the relationship-only
# normalizers in these exporters, which already know what they are holding.
# ``export_relationships`` documents the accepted alternates as
# ``source``/``source_id`` and ``target``/``target_id``.
SOURCE_ENDPOINT_NAMES: Tuple[str, ...] = (
    CANONICAL_SOURCE,
    "source",
    "start_node_id",
    "start_id",
)

TARGET_ENDPOINT_NAMES: Tuple[str, ...] = (
    CANONICAL_TARGET,
    "target",
    "end_node_id",
    "end_id",
)

# Canonical name -> the other spellings accepted for it.
ENDPOINT_ALIASES: Dict[str, Tuple[str, ...]] = {
    CANONICAL_SOURCE: SOURCE_ENDPOINT_NAMES[1:],
    CANONICAL_TARGET: TARGET_ENDPOINT_NAMES[1:],
}


def has_endpoints(sample: Dict[str, Any]) -> bool:
    """Whether a record carries both ends of a relationship, under any name."""
    return any(k in sample for k in SOURCE_ENDPOINT_NAMES) and any(
        k in sample for k in TARGET_ENDPOINT_NAMES
    )


def canonical_endpoints(records: Any) -> Any:
    """Return ``records`` with relationship endpoints under their canonical keys.

    Records that already carry ``source_id``/``target_id`` are returned
    untouched, as are non-dict records. The original list is returned when
    nothing needed adding, so callers that pass a canonical graph pay nothing.
    """
    if not isinstance(records, list):
        return records

    normalized: List[Any] = []
    changed = False
    for record in records:
        if not isinstance(record, dict):
            normalized.append(record)
            continue

        resolved: Dict[str, Any] = {}
        for canonical, aliases in ENDPOINT_ALIASES.items():
            if record.get(canonical) is not None:
                continue
            for alias in aliases:
                if record.get(alias) is not None:
                    resolved[canonical] = record[alias]
                    break

        if resolved:
            changed = True
            merged = dict(record)
            merged.update(resolved)
            normalized.append(merged)
        else:
            normalized.append(record)
    return normalized if changed else records

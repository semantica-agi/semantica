"""
Relational schema mapper.

Turns rows pulled from a relational source (``DBIngestor``, ``SnowflakeIngestor``,
``DatabricksIngestor``, ``PandasIngestor``, a pandas ``DataFrame`` or plain lists
of row dicts) into the ``{"entities": [...], "relationships": [...]}`` shape that
``GraphBuilder`` and ``OntologyGenerator`` consume:

- one row of an entity table becomes one entity; the primary key becomes the
  entity id and the remaining columns become entity properties,
- one foreign key becomes one typed relationship between the two entity ids,
- a junction table (a table that is not an entity table and whose rows are held
  together by two foreign keys) becomes relationships only, never a phantom
  entity,
- every entity and relationship records the ``source`` it came from so that
  ``ConflictDetector`` / ``ConflictResolver`` and the provenance layer can key
  credibility on it: entities carry it flat as ``source`` (where
  ``ConflictDetector`` reads it) and both carry ``metadata: {"source", "table"}``
  (``metadata`` is skipped by ``OntologyGenerator`` when it infers properties).

A junction relationship runs from the first foreign key listed to the second
(explicit keys come before schema-derived ones); its predicate is the second
key's, then the first's, then the table name.

Entity ids are ``"<Type>:<pk>"`` (``|`` and ``\\`` inside a key component are
backslash-escaped), so the same row ingested from two systems of record maps to
the same id and the two copies can be compared for conflicts.

Example:
    >>> mapper = RelationalSchemaMapper(
    ...     entity_tables={
    ...         "CUSTOMERS": {"pk": "CUSTOMER_ID", "type": "Customer", "name": "NAME"},
    ...         "ORDERS": {"pk": "ORDER_ID", "type": "Order"},
    ...     },
    ...     foreign_keys=[
    ...         {"table": "ORDERS", "column": "CUSTOMER_ID",
    ...          "references": ("CUSTOMERS", "CUSTOMER_ID"), "predicate": "placedBy"},
    ...     ],
    ... )
    >>> mapped = mapper.map({"CUSTOMERS": customers, "ORDERS": orders}, source="snowflake_crm")
    >>> GraphBuilder().build(sources=[mapped])
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from ..utils.logging import get_logger

Row = Dict[str, Any]
TableInput = Union[Sequence[Row], Any]

# Keys the mapper sets itself, plus the aliases GraphBuilder promotes to
# "source" / "target" (a column named "object" would turn an entity into a
# relationship). A column with one of these names is rejected, not overwritten.
ENTITY_RESERVED = frozenset(
    {
        "id",
        "entity_id",
        "type",
        "name",
        "source",
        "source_id",
        "target",
        "target_id",
        "subject",
        "object",
        "metadata",
    }
)
RELATIONSHIP_RESERVED = frozenset(
    {
        "source",
        "source_id",
        "target",
        "target_id",
        "subject",
        "object",
        "type",
        "metadata",
    }
)


class RelationalSchemaMapper:
    """Map relational rows plus a small schema spec to entities and relationships.

    Args:
        entity_tables: ``{table_name: {"pk": column or [columns], "type": ClassName,
            "name": column (optional)}}``. ``name`` names the column used as the
            entity's display name; it defaults to the primary key value.
        foreign_keys: Explicit foreign keys, ``[{"table", "column",
            "references": (table, column), "predicate" (optional)}]``. This is the
            required fallback for warehouses where constraints are informational
            or absent. ``predicate`` defaults to the referenced table's name. The
            referenced column must be that table's primary key (entity ids come
            from it), so a key into any other column is a ``ValueError``.
        schema: The dict returned by ``DBIngestor.get_database_schema()``; its
            ``foreign_keys`` entries (SQLAlchemy inspector dicts) are used when no
            explicit foreign key covers the same column. Constraints that point
            at anything but an entity table's whole primary key are skipped with
            a warning. The ingestor does not
            record which table a constraint belongs to, so a ``table_name`` /
            ``table`` key is used when present and the owning table is otherwise
            inferred from which mapped table has the column.
    """

    def __init__(
        self,
        entity_tables: Mapping[str, Mapping[str, Any]],
        foreign_keys: Optional[Iterable[Mapping[str, Any]]] = None,
        schema: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self.logger = get_logger("schema_mapper")
        self.entity_tables: Dict[str, Dict[str, Any]] = {}
        for table, spec in entity_tables.items():
            if not spec.get("pk"):
                raise ValueError(f"entity table {table!r} needs a 'pk' column")
            if not spec.get("type"):
                raise ValueError(f"entity table {table!r} needs a 'type' class name")
            pk = spec["pk"]
            self.entity_tables[table] = {
                "pk": [pk] if isinstance(pk, str) else list(pk),
                "type": spec["type"],
                "name": spec.get("name"),
            }

        self._explicit: List[Dict[str, Any]] = [
            self._normalize_foreign_key(fk) for fk in (foreign_keys or [])
        ]
        self._schema_fks: List[Dict[str, Any]] = [
            fk for fk in self._foreign_keys_from_schema(schema) if fk is not None
        ]

    # ------------------------------------------------------------------ config

    def _normalize_foreign_key(self, fk: Mapping[str, Any]) -> Dict[str, Any]:
        table = fk.get("table")
        column = fk.get("column")
        references = fk.get("references")
        if not table or not column or not references or len(references) != 2:
            raise ValueError(
                "foreign key needs 'table', 'column' and 'references': (table, column); "
                f"got {dict(fk)!r}"
            )
        ref_table, ref_column = references
        if ref_table not in self.entity_tables:
            raise ValueError(
                f"foreign key on {table}.{column} references {ref_table!r}, "
                "which is not an entity table"
            )
        pk = self.entity_tables[ref_table]["pk"]
        if [ref_column] != pk:
            why = (
                "a composite primary key cannot be referenced"
                if len(pk) > 1
                else "a foreign key must reference the primary key"
            )
            raise ValueError(
                f"foreign key on {table}.{column} references {ref_table}.{ref_column}, "
                f"but {ref_table!r} entity ids come from {pk}; {why}"
            )
        return {
            "table": table,
            "column": column,
            "ref_table": ref_table,
            "ref_column": ref_column,
            "predicate": fk.get("predicate"),  # None: defaults to the referenced table
        }

    def _foreign_keys_from_schema(
        self, schema: Optional[Mapping[str, Any]]
    ) -> Iterable[Optional[Dict[str, Any]]]:
        for fk in (schema or {}).get("foreign_keys", []) or []:
            columns = fk.get("constrained_columns") or []
            ref_columns = fk.get("referred_columns") or []
            ref_table = fk.get("referred_table")
            # composite constraints have no single entity id to point at
            if len(columns) != 1 or len(ref_columns) != 1 or not ref_table:
                yield None
                continue
            if ref_table not in self.entity_tables:
                yield None
                continue
            # a constraint on a unique non-key column has no entity id to point at
            pk = self.entity_tables[ref_table]["pk"]
            if list(ref_columns) != pk:
                self.logger.warning(
                    "skipping schema foreign key %s.%s -> %s.%s: %r entity ids "
                    "come from %s",
                    fk.get("table_name") or fk.get("table") or "?",
                    columns[0],
                    ref_table,
                    ref_columns[0],
                    ref_table,
                    pk,
                )
                yield None
                continue
            yield {
                "table": fk.get("table_name") or fk.get("table"),
                "column": columns[0],
                "ref_table": ref_table,
                "ref_column": ref_columns[0],
                "predicate": None,
            }

    def _foreign_keys_for(
        self, table: str, columns: Iterable[str]
    ) -> List[Dict[str, Any]]:
        """Foreign keys that apply to ``table``: explicit ones first, then schema
        ones for columns no explicit key already covers.

        Inference by column name is a heuristic: a table that merely copies a
        key column (a denormalised ``SHIPMENTS.CUSTOMER_ID``) is read as holding
        that foreign key. Pass ``foreign_keys`` explicitly when that is wrong.
        """
        column_set = set(columns)
        result = [fk for fk in self._explicit if fk["table"] == table]
        covered = {fk["column"] for fk in result}
        for fk in self._schema_fks:
            owner = fk["table"]
            if owner is not None and owner != table:
                continue
            if fk["column"] in covered:
                continue
            # a key recorded against this table is kept while the table is empty;
            # once there are columns, recorded and inferred keys both need theirs
            if fk["column"] not in column_set and (owner is None or column_set):
                continue
            # the referenced table carries that key column itself; without an
            # owning table recorded, do not read it as a self-reference.
            if (
                owner is None
                and table == fk["ref_table"]
                and fk["column"] == fk["ref_column"]
            ):
                continue
            result.append({**fk, "table": table})
            covered.add(fk["column"])
        return result

    # ------------------------------------------------------------------ mapping

    def map(
        self, tables: Mapping[str, TableInput], source: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Map ``{table_name: rows}`` to entities and relationships.

        ``rows`` may be a list of dicts, an ingestor result exposing ``.data`` or
        ``.rows`` (Snowflake, Databricks, DBIngestor) or ``.dataframe``
        (PandasIngestor), one of the ``{"columns", "row_count", "rows"}``
        dicts in ``DBIngestor.ingest_database()["tables"]``, or a pandas
        DataFrame. Tables listed in
        ``entity_tables`` produce entities; other tables must be junction tables
        held together by exactly two foreign keys and produce relationships only.
        """
        entities: List[Dict[str, Any]] = []
        relationships: List[Dict[str, Any]] = []

        for table, raw in tables.items():
            rows = _rows_of(raw)
            columns = _columns_of(rows)
            foreign_keys = self._foreign_keys_for(table, columns)

            if table in self.entity_tables:
                for row in rows:
                    entity = self._entity(table, row, source)
                    if entity is None:
                        continue
                    entities.append(entity)
                    relationships.extend(
                        self._fk_relationships(
                            table, row, entity["id"], foreign_keys, source
                        )
                    )
            elif len(foreign_keys) == 2:
                relationships.extend(
                    self._junction_relationships(table, rows, foreign_keys, source)
                )
            else:
                raise ValueError(
                    f"table {table!r} is not an entity table and has {len(foreign_keys)} "
                    "foreign key(s); a junction table needs exactly two"
                )

        return {"entities": entities, "relationships": relationships}

    def _entity(self, table: str, row: Row, source: str) -> Optional[Dict[str, Any]]:
        spec = self.entity_tables[table]
        key_values = [row.get(column) for column in spec["pk"]]
        if any(_is_missing(value) for value in key_values):
            return None
        pk = _pk_text(key_values)
        name_column = spec["name"]
        name = row.get(name_column) if name_column else None
        entity: Dict[str, Any] = {
            "id": f"{spec['type']}:{pk}",
            "type": spec["type"],
            "name": str(name) if not _is_missing(name) else pk,
        }
        for column, value in row.items():
            if column in spec["pk"]:
                continue
            if column in ENTITY_RESERVED:
                if column == name_column:
                    continue  # already the entity's name
                raise ValueError(
                    f"column {column!r} in table {table!r} clashes with a reserved "
                    f"entity key; rename it (reserved: {sorted(ENTITY_RESERVED)})"
                )
            entity[column] = value
        entity["source"] = source
        entity["metadata"] = {"source": source, "table": table}
        return entity

    def _fk_relationships(
        self,
        table: str,
        row: Row,
        entity_id: str,
        foreign_keys: Sequence[Dict[str, Any]],
        source: str,
    ) -> Iterable[Dict[str, Any]]:
        for fk in foreign_keys:
            target = self._referenced_id(fk, row)
            if target is None:
                continue
            yield {
                "source": entity_id,
                "target": target,
                "type": fk["predicate"] or fk["ref_table"],
                "metadata": {"source": source, "table": table},
            }

    def _junction_relationships(
        self,
        table: str,
        rows: Sequence[Row],
        foreign_keys: Sequence[Dict[str, Any]],
        source: str,
    ) -> Iterable[Dict[str, Any]]:
        first, second = foreign_keys
        # an explicit predicate on either key names the relationship; the
        # second key's predicate wins because it names the target side.
        predicate = second["predicate"] or first["predicate"] or table
        key_columns = {first["column"], second["column"]}
        for row in rows:
            head = self._referenced_id(first, row)
            tail = self._referenced_id(second, row)
            if head is None or tail is None:
                continue
            relationship: Dict[str, Any] = {
                "source": head,
                "target": tail,
                "type": predicate,
            }
            for column, value in row.items():
                if column in key_columns:
                    continue
                if column in RELATIONSHIP_RESERVED:
                    raise ValueError(
                        f"column {column!r} in junction table {table!r} clashes with a "
                        f"reserved relationship key; rename it "
                        f"(reserved: {sorted(RELATIONSHIP_RESERVED)})"
                    )
                relationship[column] = value
            relationship["metadata"] = {"source": source, "table": table}
            yield relationship

    def _referenced_id(self, fk: Dict[str, Any], row: Row) -> Optional[str]:
        value = row.get(fk["column"])
        if _is_missing(value):
            return None
        return f"{self.entity_tables[fk['ref_table']]['type']}:{_pk_text([value])}"


# ---------------------------------------------------------------------- helpers


def _rows_of(raw: TableInput) -> List[Row]:
    """Accept row dicts, ingestor results, or a DataFrame."""
    if isinstance(raw, (list, tuple)):
        return [_without_missing(dict(row)) for row in raw]
    if isinstance(raw, Mapping) and isinstance(raw.get("rows"), (list, tuple)):
        return [_without_missing(dict(row)) for row in raw["rows"]]
    for attribute in ("data", "rows"):
        value = getattr(raw, attribute, None)
        if isinstance(value, (list, tuple)):
            return [_without_missing(dict(row)) for row in value]
    frame = getattr(raw, "dataframe", raw)
    if hasattr(frame, "to_dict"):
        return [_without_missing(row) for row in frame.to_dict("records")]
    raise TypeError(f"unsupported table input {type(raw).__name__}")


def _without_missing(row: Row) -> Row:
    """pandas marks gaps as NaN / NaT / NA; the graph wants plain None."""
    return {key: (None if _is_missing(value) else value) for key, value in row.items()}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value))
    except (TypeError, ValueError):
        # lists and other non-scalars
        return False


def _pk_text(values: Iterable[Any]) -> str:
    """Join key components so that ``|`` and ``\\`` inside a component cannot
    make two keys read as one; used for entity ids and relationship targets
    alike so the two always agree."""
    return "|".join(
        _key_text(value).replace("\\", "\\\\").replace("|", "\\|") for value in values
    )


def _key_text(value: Any) -> str:
    """Key text that is the same whichever source the row came from.

    A pandas integer column with a gap is read back as float64, so a key of
    ``1`` arrives as ``1.0``; that must still map to ``"1"``.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _columns_of(rows: Sequence[Row]) -> List[str]:
    seen: Dict[str, None] = {}
    for row in rows:
        for column in row:
            seen.setdefault(column, None)
    return list(seen)

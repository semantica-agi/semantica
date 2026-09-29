"""Tests for RelationalSchemaMapper (issue #1386, part 1)."""

import logging
import math
from types import SimpleNamespace

import pandas as pd
import pytest

from semantica.kg import RelationalSchemaMapper
from semantica.kg.schema_mapper import RelationalSchemaMapper as DirectImport

CUSTOMERS = [
    {"CUSTOMER_ID": 1, "NAME": "Acme", "ADDRESS": "1 Main St", "CREDIT_LIMIT": 1000},
    {"CUSTOMER_ID": 2, "NAME": "Globex", "ADDRESS": "2 Side St", "CREDIT_LIMIT": 500},
]
ORDERS = [
    {"ORDER_ID": 10, "CUSTOMER_ID": 1, "AMOUNT": 99.5},
    {"ORDER_ID": 11, "CUSTOMER_ID": 2, "AMOUNT": 12.0},
    {"ORDER_ID": 12, "CUSTOMER_ID": None, "AMOUNT": 1.0},
]
PRODUCTS = [
    {"PRODUCT_ID": "p1", "SKU": "SKU-1", "CATEGORY": "Electronics"},
    {"PRODUCT_ID": "p2", "SKU": "SKU-2", "CATEGORY": "Electronics"},
]
ORDER_ITEMS = [
    {"ORDER_ID": 10, "PRODUCT_ID": "p1", "QUANTITY": 2},
    {"ORDER_ID": 10, "PRODUCT_ID": "p2", "QUANTITY": 1},
    {"ORDER_ID": 11, "PRODUCT_ID": "p2", "QUANTITY": 3},
]

ENTITY_TABLES = {
    "CUSTOMERS": {"pk": "CUSTOMER_ID", "type": "Customer", "name": "NAME"},
    "ORDERS": {"pk": "ORDER_ID", "type": "Order"},
    "PRODUCTS": {"pk": "PRODUCT_ID", "type": "Product", "name": "SKU"},
}
FOREIGN_KEYS = [
    {
        "table": "ORDERS",
        "column": "CUSTOMER_ID",
        "references": ("CUSTOMERS", "CUSTOMER_ID"),
        "predicate": "placedBy",
    },
    {
        "table": "ORDER_ITEMS",
        "column": "ORDER_ID",
        "references": ("ORDERS", "ORDER_ID"),
    },
    {
        "table": "ORDER_ITEMS",
        "column": "PRODUCT_ID",
        "references": ("PRODUCTS", "PRODUCT_ID"),
        "predicate": "containsProduct",
    },
]


def by_id(entities):
    return {entity["id"]: entity for entity in entities}


def test_exported_from_semantica_kg():
    assert RelationalSchemaMapper is DirectImport


def test_rows_become_entities_with_flat_properties_and_source():
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)

    mapped = mapper.map({"CUSTOMERS": CUSTOMERS}, source="snowflake_crm")

    assert set(mapped) == {"entities", "relationships"}
    assert mapped["relationships"] == []
    entities = by_id(mapped["entities"])
    assert set(entities) == {"Customer:1", "Customer:2"}
    acme = entities["Customer:1"]
    assert acme["type"] == "Customer"
    assert acme["name"] == "Acme"
    # non-key columns land flat on the entity so ConflictDetector can read them
    assert acme["ADDRESS"] == "1 Main St"
    assert acme["CREDIT_LIMIT"] == 1000
    assert "CUSTOMER_ID" not in acme
    assert acme["source"] == "snowflake_crm"
    assert acme["metadata"] == {"source": "snowflake_crm", "table": "CUSTOMERS"}


def test_same_row_from_two_systems_shares_an_id():
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)
    crm = mapper.map({"CUSTOMERS": CUSTOMERS}, source="snowflake_crm")
    master = mapper.map(
        {"CUSTOMERS": [{"CUSTOMER_ID": 1, "NAME": "Acme", "ADDRESS": "1 Main Street"}]},
        source="databricks_master",
    )

    ids = {e["id"] for e in crm["entities"]} & {e["id"] for e in master["entities"]}
    assert ids == {"Customer:1"}
    sources = {e["source"] for e in crm["entities"] + master["entities"]}
    assert sources == {"snowflake_crm", "databricks_master"}


def test_foreign_keys_become_typed_relationships():
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS
    )

    mapped = mapper.map({"CUSTOMERS": CUSTOMERS, "ORDERS": ORDERS}, source="crm")

    orders = by_id(mapped["entities"])
    assert orders["Order:10"]["AMOUNT"] == 99.5
    assert "CUSTOMER_ID" in orders["Order:10"], "FK column stays a property too"
    rels = mapped["relationships"]
    assert rels == [
        {
            "source": "Order:10",
            "target": "Customer:1",
            "type": "placedBy",
            "metadata": {"source": "crm", "table": "ORDERS"},
        },
        {
            "source": "Order:11",
            "target": "Customer:2",
            "type": "placedBy",
            "metadata": {"source": "crm", "table": "ORDERS"},
        },
    ]
    # a null FK produces no relationship and no error


def test_junction_table_maps_to_relationships_only():
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS
    )

    mapped = mapper.map(
        {"ORDERS": ORDERS, "PRODUCTS": PRODUCTS, "ORDER_ITEMS": ORDER_ITEMS},
        source="crm",
    )

    assert not [
        e for e in mapped["entities"] if e["metadata"]["table"] == "ORDER_ITEMS"
    ]
    junction = [
        r for r in mapped["relationships"] if r["metadata"]["table"] == "ORDER_ITEMS"
    ]
    assert junction == [
        {
            "source": "Order:10",
            "target": "Product:p1",
            "type": "containsProduct",
            "QUANTITY": 2,
            "metadata": {"source": "crm", "table": "ORDER_ITEMS"},
        },
        {
            "source": "Order:10",
            "target": "Product:p2",
            "type": "containsProduct",
            "QUANTITY": 1,
            "metadata": {"source": "crm", "table": "ORDER_ITEMS"},
        },
        {
            "source": "Order:11",
            "target": "Product:p2",
            "type": "containsProduct",
            "QUANTITY": 3,
            "metadata": {"source": "crm", "table": "ORDER_ITEMS"},
        },
    ]


def test_junction_predicate_defaults_to_table_name_when_not_given():
    fks = [
        {
            "table": "ORDER_ITEMS",
            "column": "ORDER_ID",
            "references": ("ORDERS", "ORDER_ID"),
        },
        {
            "table": "ORDER_ITEMS",
            "column": "PRODUCT_ID",
            "references": ("PRODUCTS", "PRODUCT_ID"),
        },
    ]
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, foreign_keys=fks)

    mapped = mapper.map({"ORDER_ITEMS": ORDER_ITEMS[:1]}, source="crm")

    assert mapped["relationships"][0]["type"] == "ORDER_ITEMS"


def test_foreign_keys_from_db_ingestor_schema():
    # The shape DBIngestor.get_database_schema()["foreign_keys"] returns
    # (SQLAlchemy inspector dicts). The ingestor does not record the owning
    # table, so it is inferred from which provided table has the column.
    schema = {
        "tables": ["CUSTOMERS", "ORDERS"],
        "foreign_keys": [
            {
                "name": "fk_orders_customer",
                "constrained_columns": ["CUSTOMER_ID"],
                "referred_table": "CUSTOMERS",
                "referred_columns": ["CUSTOMER_ID"],
                "referred_schema": None,
            }
        ],
    }
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, schema=schema)

    mapped = mapper.map({"CUSTOMERS": CUSTOMERS, "ORDERS": ORDERS}, source="pg")

    rels = mapped["relationships"]
    assert [(r["source"], r["target"], r["type"]) for r in rels] == [
        ("Order:10", "Customer:1", "CUSTOMERS"),
        ("Order:11", "Customer:2", "CUSTOMERS"),
    ]


def test_schema_foreign_keys_use_table_name_when_present():
    schema = {
        "foreign_keys": [
            {
                "table_name": "ORDERS",
                "constrained_columns": ["CUSTOMER_ID"],
                "referred_table": "CUSTOMERS",
                "referred_columns": ["CUSTOMER_ID"],
            }
        ]
    }
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, schema=schema)
    mapped = mapper.map({"ORDERS": ORDERS[:1]}, source="pg")
    assert mapped["relationships"] == [
        {
            "source": "Order:10",
            "target": "Customer:1",
            "type": "CUSTOMERS",
            "metadata": {"source": "pg", "table": "ORDERS"},
        }
    ]


def test_explicit_foreign_keys_override_schema_predicates():
    schema = {
        "foreign_keys": [
            {
                "table_name": "ORDERS",
                "constrained_columns": ["CUSTOMER_ID"],
                "referred_table": "CUSTOMERS",
                "referred_columns": ["CUSTOMER_ID"],
            }
        ]
    }
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS[:1], schema=schema
    )
    mapped = mapper.map({"ORDERS": ORDERS[:1]}, source="pg")
    assert [r["type"] for r in mapped["relationships"]] == ["placedBy"]


@pytest.mark.parametrize(
    "wrap",
    [
        lambda rows: SimpleNamespace(data=rows),  # SnowflakeData / DatabricksData
        lambda rows: SimpleNamespace(rows=rows),  # TableData (DBIngestor)
        # DBIngestor.ingest_database()["tables"][name]
        lambda rows: {"columns": list(rows[0]), "row_count": len(rows), "rows": rows},
        lambda rows: SimpleNamespace(dataframe=pd.DataFrame(rows)),  # PandasData
        lambda rows: pd.DataFrame(rows),
    ],
)
def test_accepts_ingestor_results_and_dataframes(wrap):
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)

    mapped = mapper.map({"CUSTOMERS": wrap(CUSTOMERS)}, source="x")

    assert [e["id"] for e in mapped["entities"]] == ["Customer:1", "Customer:2"]
    assert mapped["entities"][0]["ADDRESS"] == "1 Main St"


def test_dataframe_gaps_become_none():
    frame = pd.DataFrame(
        [
            {
                "CUSTOMER_ID": 1,
                "CREDIT_LIMIT": 100,
                "SINCE": pd.Timestamp("2020-01-01"),
            },
            {"CUSTOMER_ID": 2, "CREDIT_LIMIT": None, "SINCE": None},
        ]
    )
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)

    entities = mapper.map({"CUSTOMERS": frame}, source="x")["entities"]

    assert entities[0]["CREDIT_LIMIT"] == 100
    assert entities[1]["CREDIT_LIMIT"] is None  # float NaN column
    assert entities[1]["SINCE"] is None  # NaT
    assert not any(isinstance(v, float) and math.isnan(v) for v in entities[1].values())


def test_dataframe_integer_keys_with_gaps_keep_stable_ids():
    # an int column with a missing row is read back as float64 (1.0, NaN)
    frame = pd.DataFrame(
        [{"CUSTOMER_ID": 1, "NAME": "Acme"}, {"CUSTOMER_ID": None, "NAME": "x"}]
    )
    orders = pd.DataFrame(
        [{"ORDER_ID": 10, "CUSTOMER_ID": 1}, {"ORDER_ID": 11, "CUSTOMER_ID": None}]
    )
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS[:1]
    )

    mapped = mapper.map({"CUSTOMERS": frame, "ORDERS": orders}, source="df")

    assert [e["id"] for e in mapped["entities"]] == [
        "Customer:1",
        "Order:10",
        "Order:11",
    ]
    assert [(r["source"], r["target"]) for r in mapped["relationships"]] == [
        ("Order:10", "Customer:1")
    ]
    plain = mapper.map({"CUSTOMERS": CUSTOMERS[:1]}, source="rows")["entities"][0]["id"]
    assert plain == "Customer:1"


def test_reserved_columns_are_rejected():
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS
    )
    with pytest.raises(ValueError, match="reserved entity key"):
        mapper.map({"CUSTOMERS": [{"CUSTOMER_ID": 1, "type": "gold"}]}, source="x")
    # GraphBuilder promotes "object"/"subject"/"target_id" to relationship ends
    with pytest.raises(ValueError, match="reserved entity key"):
        mapper.map({"CUSTOMERS": [{"CUSTOMER_ID": 1, "object": "x"}]}, source="x")
    with pytest.raises(ValueError, match="reserved relationship key"):
        mapper.map(
            {"ORDER_ITEMS": [{"ORDER_ID": 10, "PRODUCT_ID": "p1", "target": "z"}]},
            source="x",
        )
    # upper-case ERP columns do not clash
    mapped = mapper.map({"CUSTOMERS": [{"CUSTOMER_ID": 1, "TYPE": "gold"}]}, source="x")
    assert mapped["entities"][0]["TYPE"] == "gold"
    assert mapped["entities"][0]["type"] == "Customer"


def test_junction_predicate_precedence():
    def fks(first_pred, second_pred):
        return [
            {
                "table": "ORDER_ITEMS",
                "column": "ORDER_ID",
                "references": ("ORDERS", "ORDER_ID"),
                **({"predicate": first_pred} if first_pred else {}),
            },
            {
                "table": "ORDER_ITEMS",
                "column": "PRODUCT_ID",
                "references": ("PRODUCTS", "PRODUCT_ID"),
                **({"predicate": second_pred} if second_pred else {}),
            },
        ]

    def predicate(first_pred, second_pred):
        mapper = RelationalSchemaMapper(
            entity_tables=ENTITY_TABLES, foreign_keys=fks(first_pred, second_pred)
        )
        return mapper.map({"ORDER_ITEMS": ORDER_ITEMS[:1]}, source="x")[
            "relationships"
        ][0]["type"]

    assert predicate("hasItem", "containsProduct") == "containsProduct"
    assert predicate("hasItem", None) == "hasItem"
    assert predicate(None, None) == "ORDER_ITEMS"
    # a predicate that happens to equal the referenced table name is still explicit
    assert predicate(None, "PRODUCTS") == "PRODUCTS"


def test_junction_edge_cases():
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS
    )
    # a null key in a junction row is skipped
    rows = [{"ORDER_ID": 10, "PRODUCT_ID": None, "QUANTITY": 1}]
    assert mapper.map({"ORDER_ITEMS": rows}, source="x")["relationships"] == []

    # three foreign keys is not a junction table
    three = FOREIGN_KEYS + [
        {
            "table": "ORDER_ITEMS",
            "column": "CUSTOMER_ID",
            "references": ("CUSTOMERS", "CUSTOMER_ID"),
        }
    ]
    mapper3 = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, foreign_keys=three)
    with pytest.raises(ValueError, match="3 foreign key"):
        mapper3.map({"ORDER_ITEMS": ORDER_ITEMS[:1]}, source="x")

    # a junction table described only by the DB schema
    schema = {
        "foreign_keys": [
            {
                "table_name": "ORDER_ITEMS",
                "constrained_columns": ["ORDER_ID"],
                "referred_table": "ORDERS",
                "referred_columns": ["ORDER_ID"],
            },
            {
                "table_name": "ORDER_ITEMS",
                "constrained_columns": ["PRODUCT_ID"],
                "referred_table": "PRODUCTS",
                "referred_columns": ["PRODUCT_ID"],
            },
        ]
    }
    schema_mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, schema=schema)
    rel = schema_mapper.map({"ORDER_ITEMS": ORDER_ITEMS[:1]}, source="x")[
        "relationships"
    ][0]
    assert (rel["source"], rel["target"], rel["type"]) == (
        "Order:10",
        "Product:p1",
        "ORDER_ITEMS",
    )


def test_schema_inference_self_reference_and_limits():
    employees = {"EMPLOYEES": {"pk": "EMP_ID", "type": "Employee"}}
    schema = {
        "foreign_keys": [
            {
                "constrained_columns": ["MANAGER_ID"],
                "referred_table": "EMPLOYEES",
                "referred_columns": ["EMP_ID"],
            },
            # composite constraints have no single entity id: ignored
            {
                "constrained_columns": ["A", "B"],
                "referred_table": "EMPLOYEES",
                "referred_columns": ["EMP_ID", "X"],
            },
        ]
    }
    mapper = RelationalSchemaMapper(entity_tables=employees, schema=schema)
    rows = [{"EMP_ID": 1, "MANAGER_ID": None}, {"EMP_ID": 2, "MANAGER_ID": 1}]

    rels = mapper.map({"EMPLOYEES": rows}, source="hr")["relationships"]

    assert [(r["source"], r["target"], r["type"]) for r in rels] == [
        ("Employee:2", "Employee:1", "EMPLOYEES")
    ]

    # documented limit: inference by column name also matches a denormalised copy
    tables = {**ENTITY_TABLES, "SHIPMENTS": {"pk": "SHIPMENT_ID", "type": "Shipment"}}
    fk_schema = {
        "foreign_keys": [
            {
                "constrained_columns": ["CUSTOMER_ID"],
                "referred_table": "CUSTOMERS",
                "referred_columns": ["CUSTOMER_ID"],
            }
        ]
    }
    shipments = [{"SHIPMENT_ID": "s1", "CUSTOMER_ID": 1}]
    rels = RelationalSchemaMapper(entity_tables=tables, schema=fk_schema).map(
        {"SHIPMENTS": shipments}, source="x"
    )["relationships"]
    assert [(r["source"], r["target"]) for r in rels] == [("Shipment:s1", "Customer:1")]


def test_composite_key_components_containing_the_separator_do_not_collide():
    mapper = RelationalSchemaMapper(
        entity_tables={"P": {"pk": ["A", "B"], "type": "Pair"}}
    )
    rows = [
        {"A": "x|y", "B": "z"},
        {"A": "x", "B": "y|z"},
        {"A": "x\\", "B": "y|z"},
        {"A": "x|y\\", "B": "z"},
    ]
    ids = [e["id"] for e in mapper.map({"P": rows}, source="x")["entities"]]
    assert len(set(ids)) == 4


def test_relationship_targets_use_the_same_key_encoding_as_entity_ids():
    mapper = RelationalSchemaMapper(
        entity_tables={
            "C": {"pk": "CODE", "type": "C"},
            "O": {"pk": "ID", "type": "O"},
        },
        foreign_keys=[{"table": "O", "column": "CODE", "references": ("C", "CODE")}],
    )
    mapped = mapper.map(
        {"C": [{"CODE": "a\\|b"}], "O": [{"ID": 1, "CODE": "a\\|b"}]}, source="x"
    )
    ids = {e["id"] for e in mapped["entities"]}
    assert mapped["relationships"][0]["target"] in ids


def test_metadata_is_skipped_by_the_ontology_property_generator():
    from semantica.ontology.property_generator import PropertyGenerator

    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)
    entity = mapper.map({"ORDERS": ORDERS[:1]}, source="crm")["entities"][0]

    properties = PropertyGenerator()._extract_data_properties([entity])

    assert "AMOUNT" in properties
    assert "metadata" not in properties
    assert "table" not in properties


def test_junction_direction_follows_foreign_key_order():
    reversed_fks = [
        FOREIGN_KEYS[2],
        FOREIGN_KEYS[1],
    ]  # PRODUCT_ID first, ORDER_ID second
    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=reversed_fks
    )
    rel = mapper.map({"ORDER_ITEMS": ORDER_ITEMS[:1]}, source="x")["relationships"][0]
    assert (rel["source"], rel["target"], rel["type"]) == (
        "Product:p1",
        "Order:10",
        "containsProduct",
    )


def test_display_column_named_name_is_allowed():
    mapper = RelationalSchemaMapper(
        entity_tables={"customers": {"pk": "id", "type": "Customer", "name": "name"}}
    )
    entity = mapper.map(
        {"customers": [{"id": 1, "name": "Acme", "city": "SF"}]}, source="pg"
    )["entities"][0]
    assert entity == {
        "id": "Customer:1",
        "type": "Customer",
        "name": "Acme",
        "city": "SF",
        "source": "pg",
        "metadata": {"source": "pg", "table": "customers"},
    }


def test_gaps_in_plain_rows_become_none_too():
    rows = [{"CUSTOMER_ID": 1, "ADDRESS": float("nan"), "SINCE": pd.NaT, "TAGS": ["a"]}]
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)
    entity = mapper.map({"CUSTOMERS": rows}, source="x")["entities"][0]
    assert entity["ADDRESS"] is None
    assert entity["SINCE"] is None
    assert entity["TAGS"] == ["a"]


def test_composite_key_with_a_missing_component_is_skipped():
    mapper = RelationalSchemaMapper(
        entity_tables={"LINES": {"pk": ["ORDER_ID", "LINE_NO"], "type": "OrderLine"}}
    )
    rows = [{"ORDER_ID": 10, "LINE_NO": None}, {"ORDER_ID": 10, "LINE_NO": 2}]
    assert [e["id"] for e in mapper.map({"LINES": rows}, source="x")["entities"]] == [
        "OrderLine:10|2"
    ]


def test_composite_primary_key_and_name_fallback():
    mapper = RelationalSchemaMapper(
        entity_tables={"LINES": {"pk": ["ORDER_ID", "LINE_NO"], "type": "OrderLine"}}
    )
    rows = [{"ORDER_ID": 10, "LINE_NO": 1, "QTY": 2}]

    entity = mapper.map({"LINES": rows}, source="x")["entities"][0]

    assert entity["id"] == "OrderLine:10|1"
    assert entity["name"] == "10|1"
    assert entity["QTY"] == 2
    assert "ORDER_ID" not in entity and "LINE_NO" not in entity


def test_rows_without_a_primary_key_are_skipped():
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)
    rows = [{"CUSTOMER_ID": None, "NAME": "ghost"}, {"CUSTOMER_ID": 3, "NAME": "real"}]

    mapped = mapper.map({"CUSTOMERS": rows}, source="x")

    assert [e["id"] for e in mapped["entities"]] == ["Customer:3"]


def test_unknown_table_without_foreign_keys_is_an_error():
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES)

    with pytest.raises(ValueError, match="MYSTERY"):
        mapper.map({"MYSTERY": [{"A": 1}]}, source="x")


def test_config_validation():
    with pytest.raises(ValueError, match="pk"):
        RelationalSchemaMapper(entity_tables={"T": {"type": "Thing"}})
    with pytest.raises(ValueError, match="type"):
        RelationalSchemaMapper(entity_tables={"T": {"pk": "ID"}})
    with pytest.raises(ValueError, match="references"):
        RelationalSchemaMapper(
            entity_tables=ENTITY_TABLES,
            foreign_keys=[{"table": "ORDERS", "column": "CUSTOMER_ID"}],
        )
    with pytest.raises(ValueError, match="entity table"):
        RelationalSchemaMapper(
            entity_tables=ENTITY_TABLES,
            foreign_keys=[
                {
                    "table": "ORDERS",
                    "column": "CUSTOMER_ID",
                    "references": ("NOPE", "ID"),
                }
            ],
        )
    # entity ids come from the primary key, so a key into any other column
    # would point at an id that no row produces
    with pytest.raises(ValueError, match="primary key"):
        RelationalSchemaMapper(
            entity_tables=ENTITY_TABLES,
            foreign_keys=[
                {
                    "table": "ORDERS",
                    "column": "CUSTOMER_EMAIL",
                    "references": ("CUSTOMERS", "EMAIL"),
                }
            ],
        )
    with pytest.raises(ValueError, match="composite"):
        RelationalSchemaMapper(
            entity_tables={"LINES": {"pk": ["ORDER_ID", "LINE_NO"], "type": "Line"}},
            foreign_keys=[
                {
                    "table": "SHIPMENTS",
                    "column": "ORDER_ID",
                    "references": ("LINES", "ORDER_ID"),
                }
            ],
        )


def test_schema_foreign_keys_to_non_primary_columns_are_skipped(caplog):
    schema = {
        "foreign_keys": [
            {
                "constrained_columns": ["CUSTOMER_EMAIL"],
                "referred_table": "CUSTOMERS",
                "referred_columns": ["EMAIL"],
            }
        ]
    }
    with caplog.at_level(logging.WARNING, logger="semantica.schema_mapper"):
        mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, schema=schema)
    orders = [{"ORDER_ID": 10, "CUSTOMER_EMAIL": "a@x"}]

    mapped = mapper.map({"ORDERS": orders}, source="pg")

    assert mapped["relationships"] == []
    assert any("CUSTOMERS.EMAIL" in r.getMessage() for r in caplog.records)


def test_empty_junction_table_with_schema_foreign_keys_maps_to_nothing():
    schema = {
        "foreign_keys": [
            {
                "table_name": "ORDER_ITEMS",
                "constrained_columns": ["ORDER_ID"],
                "referred_table": "ORDERS",
                "referred_columns": ["ORDER_ID"],
            },
            {
                "table_name": "ORDER_ITEMS",
                "constrained_columns": ["PRODUCT_ID"],
                "referred_table": "PRODUCTS",
                "referred_columns": ["PRODUCT_ID"],
            },
        ]
    }
    mapper = RelationalSchemaMapper(entity_tables=ENTITY_TABLES, schema=schema)

    assert mapper.map({"ORDER_ITEMS": []}, source="pg") == {
        "entities": [],
        "relationships": [],
    }
    # rows that exist but lack a declared key column are still a mismatch
    with pytest.raises(ValueError, match="1 foreign key"):
        mapper.map({"ORDER_ITEMS": [{"ORDER_ID": 10, "QUANTITY": 1}]}, source="pg")


def test_output_feeds_graph_builder():
    from semantica.kg import GraphBuilder

    mapper = RelationalSchemaMapper(
        entity_tables=ENTITY_TABLES, foreign_keys=FOREIGN_KEYS
    )
    mapped = mapper.map({"CUSTOMERS": CUSTOMERS, "ORDERS": ORDERS}, source="crm")

    graph = GraphBuilder().build(sources=[mapped])

    entities = by_id(graph["entities"])
    assert {"Customer:1", "Customer:2", "Order:10", "Order:11", "Order:12"} <= set(
        entities
    )
    assert entities["Customer:1"]["ADDRESS"] == "1 Main St"
    assert entities["Customer:1"]["source"] == "crm"
    edges = {(r["source"], r["target"], r["type"]) for r in graph["relationships"]}
    assert ("Order:10", "Customer:1", "placedBy") in edges
    assert not any(target.endswith(":None") for _, target, _ in edges)

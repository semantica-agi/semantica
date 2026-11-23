import pytest

from semantica.deduplication import EntityMerger, MergeStrategyManager


@pytest.mark.parametrize(
    "values", [(120, 80, 0), (True, True, False), ("London", "Paris", "")]
)
def test_keep_last_preserves_latest_property_values(values):
    entities = [
        {
            "id": f"acme-{index}",
            "name": "Acme Manufacturing",
            "type": "Company",
            "properties": {"value": value, f"source_{index}": "CRM"},
        }
        for index, value in enumerate(values)
    ]

    merged = (
        EntityMerger().merge_entity_group(entities, strategy="keep_last").merged_entity
    )

    assert merged["id"] == "acme-2"
    assert merged["properties"] == {
        "value": values[-1],
        "source_0": "CRM",
        "source_1": "CRM",
        "source_2": "CRM",
    }


@pytest.mark.parametrize("strategy", ["keep_most_complete", "keep_highest_confidence"])
@pytest.mark.parametrize(
    "rule,expected",
    [
        ("keep_first", "London"),
        ("keep_last", "Berlin"),
        ("merge_all", ["London", "Paris", "Berlin"]),
        ("keep_most_complete", "Paris"),
        ("keep_highest_confidence", "Paris"),
    ],
)
def test_property_rules_follow_input_order_independently_of_base(
    strategy, rule, expected
):
    entities = [
        {
            "id": "acme-crm",
            "name": "Acme Manufacturing",
            "properties": {"city": "London", "status": "original"},
        },
        {
            "id": "acme-registry",
            "name": "Acme Manufacturing",
            "confidence": 0.99,
            "properties": {"city": "Paris", "status": "verified", "country": "FR"},
        },
        {
            "id": "acme-update",
            "name": "Acme Manufacturing",
            "properties": {"city": "Berlin", "status": "updated"},
        },
    ]
    manager = MergeStrategyManager()
    manager.add_property_rule("city", rule)

    merged = manager.merge_entities(entities, strategy=strategy).merged_entity

    assert merged["id"] == "acme-registry"
    assert merged["properties"]["city"] == expected
    assert merged["properties"]["status"] == "verified"
    assert merged["properties"]["country"] == "FR"


@pytest.mark.parametrize("rule", ["keep_first", "keep_most_complete"])
def test_custom_resolution_sees_each_entity_once(rule):
    entities = [
        {"id": "acme-crm", "name": "Acme Manufacturing", "properties": {"mentions": 2}},
        {
            "id": "acme-registry",
            "name": "Acme Manufacturing",
            "properties": {"mentions": 5, "country": "FR"},
        },
        {
            "id": "acme-update",
            "name": "Acme Manufacturing",
            "properties": {"mentions": 1},
        },
    ]
    manager = MergeStrategyManager()
    manager.add_property_rule("mentions", rule, conflict_resolution=lambda a, b: a + b)

    merged = manager.merge_entities(entities).merged_entity

    assert merged["properties"]["mentions"] == 8

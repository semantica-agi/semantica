"""Validation tests for the private truth maintenance checkpoint codec."""

import json

import pytest

from semantica.reasoning._truth_maintenance_checkpoint import (
    decode_checkpoint,
    encode_checkpoint,
)
from semantica.reasoning.reasoner import Rule, RuleType
from semantica.reasoning.truth_maintenance_types import FactSupport, _RuleSnapshot
from semantica.utils.exceptions import ValidationError

CHECKPOINT_V1_JSON = """{
  "format_version": 1,
  "session_version": 4,
  "rules": [
    {
      "rule_id": "employment-eligibility",
      "conditions": ["Employed(?x)"],
      "conclusion": "Eligible(?x)"
    }
  ],
  "support_catalog": [
    {"support_id": "document-v1", "fact": "Employed(Alice)"},
    {"support_id": "document-v2", "fact": "Employed(Alice)"}
  ],
  "active_support_ids": ["document-v2"]
}"""

TOP_LEVEL_FIELDS = (
    "format_version",
    "session_version",
    "rules",
    "support_catalog",
    "active_support_ids",
)


def checkpoint_payload():
    return json.loads(CHECKPOINT_V1_JSON)


def test_decode_builds_detached_checkpoint_values():
    payload = checkpoint_payload()
    decoded = decode_checkpoint(payload)

    assert decoded.session_version == 4
    assert len(decoded.rules) == 1
    rule = decoded.rules[0]
    assert isinstance(rule, Rule)
    assert rule.rule_id == "employment-eligibility"
    assert rule.name == "employment-eligibility"
    assert rule.conditions == ["Employed(?x)"]
    assert rule.conclusion == "Eligible(?x)"
    assert rule.rule_type is RuleType.IMPLICATION
    assert rule.confidence == 1.0
    assert rule.handler is None
    assert rule.actions == []

    assert decoded.catalog_supports == (
        FactSupport("document-v1", "Employed(Alice)"),
        FactSupport("document-v2", "Employed(Alice)"),
    )
    assert decoded.active_support_ids == ("document-v2",)
    assert payload == checkpoint_payload()

    payload["rules"][0]["conditions"].append("Injected(?x)")
    payload["support_catalog"][0]["fact"] = "Injected(Alice)"
    payload["active_support_ids"].append("document-v1")

    assert decoded.rules[0].conditions == ["Employed(?x)"]
    assert decoded.catalog_supports[0] == FactSupport("document-v1", "Employed(Alice)")
    assert decoded.active_support_ids == ("document-v2",)


def test_decode_accepts_empty_checkpoint_with_version_zero():
    decoded = decode_checkpoint(
        {
            "format_version": 1,
            "session_version": 0,
            "rules": [],
            "support_catalog": [],
            "active_support_ids": [],
        }
    )

    assert decoded.session_version == 0
    assert decoded.rules == ()
    assert decoded.catalog_supports == ()
    assert decoded.active_support_ids == ()


@pytest.mark.parametrize("payload", [None, [], (), "payload", 1])
def test_reject_non_dict_root(payload):
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("field", TOP_LEVEL_FIELDS)
def test_reject_missing_top_level_field(field):
    payload = checkpoint_payload()
    del payload[field]
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_unknown_top_level_field():
    payload = checkpoint_payload()
    payload["facts"] = []
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize(
    "record",
    [
        lambda payload: payload,
        lambda payload: payload["rules"][0],
        lambda payload: payload["support_catalog"][0],
    ],
    ids=["top-level", "rule-record", "catalog-record"],
)
def test_reject_non_string_field_names(record):
    payload = checkpoint_payload()
    record(payload)[42] = "invalid"
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize(
    "value",
    [0, 2, True, 1.0, "1", None],
    ids=["zero", "two", "bool", "float", "str", "null"],
)
def test_reject_invalid_format_version(value):
    payload = checkpoint_payload()
    payload["format_version"] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize(
    "value",
    [True, False, -1, 1.0, "1", None],
    ids=["true", "false", "negative", "float", "str", "null"],
)
def test_reject_invalid_session_version(value):
    payload = checkpoint_payload()
    payload["session_version"] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_version_zero_with_non_empty_catalog():
    payload = checkpoint_payload()
    payload["session_version"] = 0
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_positive_version_with_empty_catalog():
    payload = checkpoint_payload()
    payload["support_catalog"] = []
    payload["active_support_ids"] = []
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_single_commit_with_all_supports_inactive():
    payload = checkpoint_payload()
    payload["session_version"] = 1
    payload["active_support_ids"] = []
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rules", "not-a-list"),
        ("rules", ()),
        ("rules", (item for item in [])),
        ("support_catalog", "not-a-list"),
        ("support_catalog", ()),
        ("support_catalog", (item for item in [])),
        ("active_support_ids", "document-v2"),
        ("active_support_ids", ()),
        ("active_support_ids", (item for item in [])),
    ],
    ids=[
        "rules-string",
        "rules-tuple",
        "rules-generator",
        "catalog-string",
        "catalog-tuple",
        "catalog-generator",
        "active-string",
        "active-tuple",
        "active-generator",
    ],
)
def test_reject_non_list_collection(field, value):
    payload = checkpoint_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("field", ["rules", "support_catalog"])
@pytest.mark.parametrize("value", [None, [], "record", 1])
def test_reject_non_dict_record(field, value):
    payload = checkpoint_payload()
    payload[field][0] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("field", ["rule_id", "conditions", "conclusion"])
def test_reject_missing_rule_field(field):
    payload = checkpoint_payload()
    del payload["rules"][0][field]
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_unknown_rule_field():
    payload = checkpoint_payload()
    payload["rules"][0]["priority"] = 0
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("field", ["support_id", "fact"])
def test_reject_missing_catalog_field(field):
    payload = checkpoint_payload()
    del payload["support_catalog"][0][field]
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_unknown_catalog_field():
    payload = checkpoint_payload()
    payload["support_catalog"][0]["metadata"] = {}
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("field", ["rule_id", "support_id"])
@pytest.mark.parametrize("value", ["", None, 1, True, []])
def test_reject_invalid_record_id(field, value):
    payload = checkpoint_payload()
    collection = "rules" if field == "rule_id" else "support_catalog"
    payload[collection][0][field] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("value", ["", None, 1, True, []])
def test_reject_invalid_active_support_id(value):
    payload = checkpoint_payload()
    payload["active_support_ids"][0] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_duplicate_rule_id():
    payload = checkpoint_payload()
    payload["rules"].append(dict(payload["rules"][0]))
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_repeated_catalog_id_even_for_same_fact():
    payload = checkpoint_payload()
    payload["support_catalog"].append(dict(payload["support_catalog"][0]))
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_conflicting_catalog_id():
    payload = checkpoint_payload()
    payload["support_catalog"].append(dict(payload["support_catalog"][0]))
    payload["support_catalog"][1]["fact"] = "Employed(Bob)"
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_duplicate_active_support_id():
    payload = checkpoint_payload()
    payload["active_support_ids"].append("document-v2")
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_reject_unknown_active_support_id():
    payload = checkpoint_payload()
    payload["active_support_ids"] = ["document-v3"]
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize(
    "value",
    ["Employed(?x)", (), (condition for condition in []), []],
    ids=["string", "tuple", "generator", "empty"],
)
def test_reject_invalid_conditions(value):
    payload = checkpoint_payload()
    payload["rules"][0]["conditions"] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("value", [None, 1, True, []])
def test_reject_non_string_condition(value):
    payload = checkpoint_payload()
    payload["rules"][0]["conditions"] = [value]
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("value", [None, 1, True, []])
def test_reject_non_string_conclusion(value):
    payload = checkpoint_payload()
    payload["rules"][0]["conclusion"] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


@pytest.mark.parametrize("value", [None, 1, True, []])
def test_reject_non_string_fact(value):
    payload = checkpoint_payload()
    payload["support_catalog"][0]["fact"] = value
    with pytest.raises(ValidationError):
        decode_checkpoint(payload)


def test_validation_context_uses_field_paths():
    payload = checkpoint_payload()
    payload["session_version"] = "1"
    with pytest.raises(ValidationError) as error:
        decode_checkpoint(payload)
    assert error.value.validation_context["field"] == "session_version"

    payload = checkpoint_payload()
    payload["support_catalog"][1]["support_id"] = payload["support_catalog"][0][
        "support_id"
    ]
    with pytest.raises(ValidationError) as error:
        decode_checkpoint(payload)
    assert error.value.validation_context["field"] == "support_catalog[1].support_id"

    payload = checkpoint_payload()
    payload["rules"][0]["conditions"] = [None]
    with pytest.raises(ValidationError) as error:
        decode_checkpoint(payload)
    assert error.value.validation_context["field"] == "rules[0].conditions[0]"


def test_encode_checkpoint_builds_sorted_detached_payload():
    snapshot = _RuleSnapshot(
        rule_id="eligibility",
        conditions=("Employed(?x)",),
        conclusion="Eligible(?x)",
        parsed_conditions=(("Employed", ("?x",)),),
        parsed_conclusion=("Eligible", ("?x",)),
        head_variables=frozenset(),
        body_variables=frozenset({"?x"}),
        order=(0, "eligibility"),
    )
    catalog = {
        "document-v2": "Employed(Alice)",
        "document-v1": "Employed(Alice)",
    }
    active = ["document-v2", "document-v1"]

    encoded = encode_checkpoint(
        rules=[snapshot],
        support_catalog=catalog,
        active_support_ids=active,
        session_version=4,
    )

    assert encoded == {
        "format_version": 1,
        "session_version": 4,
        "rules": [
            {
                "rule_id": "eligibility",
                "conditions": ["Employed(?x)"],
                "conclusion": "Eligible(?x)",
            }
        ],
        "support_catalog": [
            {"support_id": "document-v1", "fact": "Employed(Alice)"},
            {"support_id": "document-v2", "fact": "Employed(Alice)"},
        ],
        "active_support_ids": ["document-v1", "document-v2"],
    }
    assert encoded["rules"][0]["conditions"] is not snapshot.conditions
    assert encoded["active_support_ids"] is not active

    encoded["rules"][0]["conditions"].append("Injected(?x)")
    encoded["active_support_ids"].append("document-v3")
    encoded["support_catalog"][0]["support_id"] = "changed"

    assert snapshot.conditions == ("Employed(?x)",)
    assert active == ["document-v2", "document-v1"]
    assert catalog == {
        "document-v2": "Employed(Alice)",
        "document-v1": "Employed(Alice)",
    }

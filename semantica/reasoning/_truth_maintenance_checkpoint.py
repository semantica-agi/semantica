"""Private JSON-compatible codec for truth maintenance checkpoints.

The codec owns the fixed v1 payload shape.  It does not duplicate rule or
atom semantics; decoded values are passed to the session for validation and
closure rebuilding.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

from semantica.utils.exceptions import ValidationError

from .reasoner import Rule
from .truth_maintenance_types import FactSupport, _RuleSnapshot

_FORMAT_VERSION = 1
_TOP_LEVEL_FIELDS: FrozenSet[str] = frozenset(
    {
        "format_version",
        "session_version",
        "rules",
        "support_catalog",
        "active_support_ids",
    }
)
_RULE_FIELDS: FrozenSet[str] = frozenset({"rule_id", "conditions", "conclusion"})
_CATALOG_FIELDS: FrozenSet[str] = frozenset({"support_id", "fact"})


@dataclass(frozen=True)
class _DecodedCheckpoint:
    """Internal, detached result of validating a checkpoint payload."""

    session_version: int
    rules: Tuple[Rule, ...]
    catalog_supports: Tuple[FactSupport, ...]
    active_support_ids: Tuple[str, ...]


def _field(location: str, field: str) -> str:
    return f"{location}.{field}" if location else field


def _fail(message: str, field: str, **details: object) -> ValidationError:
    context = {"field": field}
    context.update(details)
    return ValidationError(message, validation_context=context)


def _require_exact_keys(record: dict, expected: FrozenSet[str], location: str) -> None:
    actual = set(record)
    non_string_keys = [key for key in actual if not isinstance(key, str)]
    if non_string_keys:
        raise _fail(
            "checkpoint field names must be strings",
            location or "checkpoint",
            key_types=sorted({type(key).__name__ for key in non_string_keys}),
        )
    missing = expected - actual
    unknown = actual - expected
    if not missing and not unknown:
        return

    details = {
        "missing_fields": sorted(missing),
        "unexpected_fields": sorted(unknown),
    }
    if missing:
        invalid_field = _field(location, sorted(missing)[0])
    else:
        invalid_field = _field(location, sorted(unknown)[0])
    raise _fail(
        "checkpoint fields do not match the required schema",
        invalid_field,
        **details,
    )


def _require_non_empty_string(value: object, field: str, kind: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(f"{kind} must be a non-empty string", field, value=repr(value))
    return value


def _require_list(value: object, field: str) -> list:
    if not isinstance(value, list):
        raise _fail(
            "checkpoint value must be a list",
            field,
            value_type=type(value).__name__,
        )
    return value


def _decode_rules(rules_value: object) -> Tuple[Rule, ...]:
    rules = _require_list(rules_value, "rules")
    decoded: list[Rule] = []
    seen_rule_ids: set[str] = set()

    for index, record in enumerate(rules):
        location = f"rules[{index}]"
        if not isinstance(record, dict):
            raise _fail(
                "rule record must be a dict",
                location,
                value_type=type(record).__name__,
            )
        _require_exact_keys(record, _RULE_FIELDS, location)

        rule_id = _require_non_empty_string(
            record["rule_id"], _field(location, "rule_id"), "rule_id"
        )
        if rule_id in seen_rule_ids:
            raise _fail(
                "duplicate rule_id",
                _field(location, "rule_id"),
                rule_id=rule_id,
            )
        seen_rule_ids.add(rule_id)

        conditions = _require_list(record["conditions"], _field(location, "conditions"))
        if not conditions:
            raise _fail(
                "rule conditions must not be empty",
                _field(location, "conditions"),
                rule_id=rule_id,
            )
        condition_texts: list[str] = []
        for condition_index, condition in enumerate(conditions):
            condition_field = f"{location}.conditions[{condition_index}]"
            if not isinstance(condition, str):
                raise _fail(
                    "rule condition must be a string",
                    condition_field,
                    value=repr(condition),
                )
            condition_texts.append(condition)

        conclusion = record["conclusion"]
        if not isinstance(conclusion, str):
            raise _fail(
                "rule conclusion must be a string",
                _field(location, "conclusion"),
                value=repr(conclusion),
            )

        decoded.append(
            Rule(
                rule_id=rule_id,
                name=rule_id,
                conditions=list(condition_texts),
                conclusion=conclusion,
            )
        )

    return tuple(decoded)


def _decode_catalog(catalog_value: object) -> Tuple[FactSupport, ...]:
    catalog = _require_list(catalog_value, "support_catalog")
    decoded: list[FactSupport] = []
    seen_support_ids: set[str] = set()

    for index, record in enumerate(catalog):
        location = f"support_catalog[{index}]"
        if not isinstance(record, dict):
            raise _fail(
                "support catalog record must be a dict",
                location,
                value_type=type(record).__name__,
            )
        _require_exact_keys(record, _CATALOG_FIELDS, location)

        support_id = _require_non_empty_string(
            record["support_id"], _field(location, "support_id"), "support_id"
        )
        if support_id in seen_support_ids:
            raise _fail(
                "duplicate support_id",
                _field(location, "support_id"),
                support_id=support_id,
            )
        seen_support_ids.add(support_id)

        fact = record["fact"]
        if not isinstance(fact, str):
            raise _fail(
                "support fact must be a string",
                _field(location, "fact"),
                value=repr(fact),
            )
        decoded.append(FactSupport(support_id=support_id, fact=fact))

    return tuple(decoded)


def _decode_active_support_ids(
    active_value: object, catalog_support_ids: FrozenSet[str]
) -> Tuple[str, ...]:
    active_ids = _require_list(active_value, "active_support_ids")
    decoded: list[str] = []
    seen_active_ids: set[str] = set()

    for index, support_id in enumerate(active_ids):
        field = f"active_support_ids[{index}]"
        support_id = _require_non_empty_string(support_id, field, "active support_id")
        if support_id in seen_active_ids:
            raise _fail(
                "duplicate active support_id",
                field,
                support_id=support_id,
            )
        if support_id not in catalog_support_ids:
            raise _fail(
                "active support_id is not present in the support catalog",
                field,
                support_id=support_id,
            )
        seen_active_ids.add(support_id)
        decoded.append(support_id)

    return tuple(decoded)


def decode_checkpoint(payload: object) -> _DecodedCheckpoint:
    """Decode and structurally validate a fixed v1 checkpoint payload."""
    if not isinstance(payload, dict):
        raise _fail(
            "checkpoint must be a dict",
            "checkpoint",
            value_type=type(payload).__name__,
        )
    _require_exact_keys(payload, _TOP_LEVEL_FIELDS, "")

    format_version = payload["format_version"]
    if type(format_version) is not int or format_version != _FORMAT_VERSION:
        raise _fail(
            f"format_version must be {_FORMAT_VERSION}",
            "format_version",
            value=repr(format_version),
        )

    session_version = payload["session_version"]
    if type(session_version) is not int or session_version < 0:
        raise _fail(
            "session_version must be a non-negative integer",
            "session_version",
            value=repr(session_version),
        )

    rules = _decode_rules(payload["rules"])
    catalog_supports = _decode_catalog(payload["support_catalog"])
    if session_version == 0 and catalog_supports:
        raise _fail(
            "session_version cannot be zero when the support catalog is non-empty",
            "session_version",
            catalog_size=len(catalog_supports),
        )

    active_support_ids = _decode_active_support_ids(
        payload["active_support_ids"],
        frozenset(support.support_id for support in catalog_supports),
    )

    # An empty catalog cannot follow an effective commit.  Withdrawing every
    # support requires at least an initial insertion and a final retraction.
    if not catalog_supports and session_version > 0:
        raise _fail(
            "session_version cannot be positive when the support catalog is empty",
            "session_version",
            session_version=session_version,
        )
    if catalog_supports and not active_support_ids and session_version < 2:
        raise _fail(
            "session_version must be at least two when no supports are active",
            "session_version",
            session_version=session_version,
            catalog_size=len(catalog_supports),
        )

    return _DecodedCheckpoint(
        session_version=session_version,
        rules=rules,
        catalog_supports=catalog_supports,
        active_support_ids=active_support_ids,
    )


def encode_checkpoint(
    *,
    rules: Iterable[_RuleSnapshot],
    support_catalog: Mapping[str, str],
    active_support_ids: Iterable[str],
    session_version: int,
) -> Dict[str, object]:
    """Build a new, deterministic v1 payload from internal session data."""
    return {
        "format_version": _FORMAT_VERSION,
        "session_version": session_version,
        "rules": [
            {
                "rule_id": snapshot.rule_id,
                "conditions": list(snapshot.conditions),
                "conclusion": snapshot.conclusion,
            }
            for snapshot in rules
        ],
        "support_catalog": [
            {"support_id": support_id, "fact": support_catalog[support_id]}
            for support_id in sorted(support_catalog)
        ],
        "active_support_ids": sorted(active_support_ids),
    }

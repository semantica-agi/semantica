"""
Integrity Verification Utilities

This module provides utilities for data integrity verification using
SHA-256 checksums, ensuring provenance data has not been tampered with.

Features:
    - SHA-256 checksum computation
    - Checksum verification
    - Data integrity validation
    - Tamper detection

Compliance:
    - FDA 21 CFR Part 11 (electronic records)
    - SOX (Sarbanes-Oxley)
    - HIPAA (healthcare data integrity)

Author: Semantica Contributors
License: MIT
"""

import hashlib
from collections.abc import Mapping
from typing import Any, Callable, Dict, List, Optional
from .schemas import ProvenanceEntry


# Checksum encoding version (issue #2136).
#
# v1 pasted the 16 field strings together with nothing between them, so two
# records that differ only in where a field boundary falls hashed the same.
# v2 length-prefixes every value and tags lists with their element count, so a
# boundary cannot move. The version is recorded per row
# (ProvenanceEntry.checksum_version) instead of being a caller-facing flag:
# defaulting a flag to False would report every existing store as a broken
# chain on upgrade while nothing had been tampered with, and defaulting it to
# True would leave the collision open for good.
CHECKSUM_VERSION = 2
LEGACY_CHECKSUM_VERSION = 1

# The hashed fields, in the fixed order both encodings use. entity_id is
# deliberately absent; see compute_checksum().
_CHECKSUM_FIELDS = (
    ("entity_type", "text"),
    ("activity_id", "text"),
    ("agent_id", "text"),
    ("agent_type", "text"),
    ("source_document", "text"),
    ("timestamp", "text"),
    ("confidence", "float"),
    ("parent_entity_id", "text"),
    ("previous_version_id", "text"),
    ("derived_from_id", "text"),
    ("used_entities", "list"),
    ("previous_checksum", "text"),
    ("invalidated", "bool"),
    ("invalidated_at_time", "text"),
    ("invalidated_by", "text"),
    ("invalidation_reason", "text"),
)

# Encoding tags. Every value is written as <tag><4-byte big-endian length>
# <utf-8 bytes>; a list is written as <tag><count> then each element in the
# same length-prefixed form, so ["a,b"] and ["a", "b"] cannot collide either.
# A null is the tag alone, so a NULL confidence cannot hash like 1.0.
_TAG_SCALAR = b"\x01"
_TAG_LIST = b"\x02"
_TAG_NULL = b"\x03"
_V2_HEADER = b"prov-v2\x00"

_MISSING = object()


def _get(entry: Any, name: str) -> Any:
    """Read a field from a mapping or an object; ``_MISSING`` when absent."""
    if isinstance(entry, Mapping):
        return entry.get(name, _MISSING)
    return getattr(entry, name, _MISSING)


def _raw_field(entry: Any, name: str, default: Any) -> Any:
    """Read a field from a mapping or a dataclass, treating None as absent."""
    value = _get(entry, name)
    return default if value is _MISSING or value is None else value


def _checksum_field_values(entry: Any) -> List[Any]:
    """
    Return the hashed values in ``_CHECKSUM_FIELDS`` order.

    Both the dict and the dataclass path go through this function, so the same
    content always produces the same value vector. v1 did not: a None field
    hashed as ``''`` through ``entry.get('x') or ''`` but as ``'None'`` through
    ``f"{entry.x}"``, so identical records hashed differently depending on how
    they were passed in.
    """
    values: List[Any] = []
    for name, kind in _CHECKSUM_FIELDS:
        if kind == "list":
            raw = _raw_field(entry, name, [])
            if isinstance(raw, (list, tuple)):
                values.append([str(item) for item in raw])
            else:
                # A non-list value (a corrupted row, or a bare string) is
                # hashed as a scalar: the tag keeps it from colliding with any
                # list, so "ab" cannot pass for ["a", "b"], and it is a
                # mismatch rather than a TypeError mid-verify_chain().
                values.append(str(raw))
        elif kind == "float":
            raw = _get(entry, name)
            if raw is _MISSING:
                # An absent confidence is the dataclass default, so a dict
                # without the key hashes like a ProvenanceEntry with 1.0.
                raw = 1.0
            if raw is None:
                # An explicit NULL is not 1.0: hashing it as the default would
                # let `SET confidence = NULL` pass verification.
                values.append(None)
                continue
            try:
                values.append(str(float(raw)))
            except (TypeError, ValueError, OverflowError):
                # A row whose confidence is not numeric must fail verification,
                # not raise while verifying it: verify_checksum() answers a
                # question, and a malformed row is a "no", not an exception.
                # Falling back to the raw text keeps the value hashable and
                # still changes the digest if someone edits it.
                values.append(str(raw))
        elif kind == "bool":
            values.append(str(bool(_raw_field(entry, name, False))))
        else:
            values.append(str(_raw_field(entry, name, "")))
    return values


def _encode_fields(values: List[Any]) -> bytes:
    """Encode a value vector so no two distinct vectors collide (issue #2136)."""
    out = bytearray(_V2_HEADER)
    for value in values:
        if value is None:
            out += _TAG_NULL
        elif isinstance(value, list):
            out += _TAG_LIST
            out += len(value).to_bytes(4, "big")
            for item in value:
                encoded = item.encode("utf-8")
                out += len(encoded).to_bytes(4, "big")
                out += encoded
        else:
            encoded = value.encode("utf-8")
            out += _TAG_SCALAR
            out += len(encoded).to_bytes(4, "big")
            out += encoded
    return bytes(out)


def compute_checksum(entry: Any) -> str:
    """
    Compute SHA-256 checksum for a provenance entry.
    
    Creates a deterministic checksum based on critical provenance fields
    to detect any tampering or corruption of provenance data.

    Includes `previous_checksum` (issue #825, Part A item 2), which chains
    each entry to the prior entry in insertion order (see
    ProvenanceStorage.get_chain_head / ProvenanceManager.verify_chain) —
    wholesale deletion of a row breaks the chain for the entry that used to
    follow it, making the deletion detectable even though per-row checksums
    only prove a surviving row wasn't edited in place. Also includes
    agent_id/agent_type and the lineage-link fields (parent_entity_id,
    previous_version_id, derived_from_id, used_entities) so tampering with
    attribution or lineage is detected, not just tampering with the six
    original fields.

    Deliberately excludes `entity_id` itself: entity_id is the storage
    primary key, and ProvenanceManager.track_entity()'s versioning archives
    a prior value by copying it to a new entity_id (e.g. "X" -> "X:v:...").
    If entity_id were hashed, that relabeling would change the archived
    copy's checksum, permanently orphaning any later entry whose
    previous_checksum had already chained from the pre-relabel value —
    a false-positive "broken chain" for a legitimate rename, not tampering.
    Tampering that swaps a row's entity_id while keeping its content is a
    narrower threat than content tampering, already partially caught by
    verify_chain() (it requires a delete+insert, which breaks the chain for
    whatever the deleted row's successor was).

    The encoding version is recorded on the row when it is written
    (``ProvenanceManager._save_entry``), not here: computing a digest should
    not write to the value it was given, and a read-only comparison on a
    legacy row must not relabel that row in memory. A caller who assigns the
    digest by hand (``entry.checksum = compute_checksum(entry)``, as the
    example below does) never reaches that path, so ``verify_checksum()``
    treats a row with no recorded version as "v2, else v1" rather than
    assuming the old scheme.

    Args:
        entry: ProvenanceEntry or dict to compute checksum for

    Returns:
        SHA-256 checksum as hexadecimal string

    Example:
        >>> entry = ProvenanceEntry(
        ...     entity_id="entity_123",
        ...     entity_type="entity",
        ...     activity_id="extraction",
        ...     source_document="DOI:10.1371/..."
        ... )
        >>> checksum = compute_checksum(entry)
        >>> print(checksum)
        'a3b2c1d4e5f6...'
    """
    return hashlib.sha256(_encode_fields(_checksum_field_values(entry))).hexdigest()


def _recorded_checksum_version(entry: Any) -> Optional[int]:
    """Return the version recorded on ``entry``, or None when it carries none."""
    raw = _raw_field(entry, "checksum_version", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError, OverflowError):
        return None


def checksum_version(entry: Any) -> int:
    """
    Return the checksum encoding version recorded on ``entry``.

    Rows written before issue #2136 carry no version and report v1, so an
    existing store keeps verifying after upgrade without being re-hashed and
    without a caller-facing flag. A digest assigned by hand from
    ``compute_checksum()`` carries no version either, so ``verify_checksum()``
    accepts either encoding on an unversioned row; this helper reports what
    was recorded, not which encoding matched.

    The recorded version is trusted metadata, not an authenticated field: it is
    not one of the hashed values, so a writer who can update a row can relabel a
    v2 row as v1 and have it checked under the collision-prone encoding. That is
    outside what a per-row digest claims to protect — detecting a rewrite is the
    chain's job (``previous_checksum``), not this field's.
    """
    recorded = _recorded_checksum_version(entry)
    return LEGACY_CHECKSUM_VERSION if recorded is None else recorded


def compute_checksum_legacy(entry: Any) -> str:
    """
    Compute the v1 (field-concatenation) checksum, for rows written before
    issue #2136.

    That encoding is not injective — two records that differ only in where a
    field boundary falls hash the same — so it is used only to verify rows
    whose ``checksum_version`` is 1 or absent. New rows always get the v2
    encoding from ``compute_checksum()``.
    """
    if isinstance(entry, dict):
        used_entities = entry.get("used_entities") or []
        data = (
            f"{entry.get('entity_type') or ''}"
            f"{entry.get('activity_id') or ''}"
            f"{entry.get('agent_id') or ''}"
            f"{entry.get('agent_type') or ''}"
            f"{entry.get('source_document') or ''}"
            f"{entry.get('timestamp') or ''}"
            f"{entry.get('confidence') if entry.get('confidence') is not None else 1.0}"
            f"{entry.get('parent_entity_id') or ''}"
            f"{entry.get('previous_version_id') or ''}"
            f"{entry.get('derived_from_id') or ''}"
            f"{','.join(used_entities)}"
            f"{entry.get('previous_checksum') or ''}"
            f"{bool(entry.get('invalidated'))}"
            f"{entry.get('invalidated_at_time') or ''}"
            f"{entry.get('invalidated_by') or ''}"
            f"{entry.get('invalidation_reason') or ''}"
        )
    else:
        used_entities = getattr(entry, "used_entities", None) or []
        data = (
            f"{entry.entity_type}"
            f"{entry.activity_id}"
            f"{getattr(entry, 'agent_id', '') or ''}"
            f"{getattr(entry, 'agent_type', '') or ''}"
            f"{entry.source_document}"
            f"{entry.timestamp}"
            f"{entry.confidence}"
            f"{getattr(entry, 'parent_entity_id', '') or ''}"
            f"{getattr(entry, 'previous_version_id', '') or ''}"
            f"{getattr(entry, 'derived_from_id', '') or ''}"
            f"{','.join(used_entities)}"
            f"{getattr(entry, 'previous_checksum', '') or ''}"
            f"{bool(getattr(entry, 'invalidated', False))}"
            f"{getattr(entry, 'invalidated_at_time', '') or ''}"
            f"{getattr(entry, 'invalidated_by', '') or ''}"
            f"{getattr(entry, 'invalidation_reason', '') or ''}"
        )

    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_checksum(entry: Any, expected_checksum: Optional[str] = None) -> bool:
    """
    Verify checksum for a provenance entry.
    
    Computes the current checksum and compares it with the expected checksum
    to detect tampering or corruption.
    
    Args:
        entry: ProvenanceEntry or dict to verify
        expected_checksum: Expected checksum (uses entry.checksum if None)
        
    Returns:
        True if checksum matches, False otherwise
        
    Example:
        >>> entry = ProvenanceEntry(...)
        >>> entry.checksum = compute_checksum(entry)
        >>> is_valid = verify_checksum(entry)
        >>> print(is_valid)
        True
    """
    if expected_checksum is None:
        expected_checksum = _raw_field(entry, "checksum", None)

    if expected_checksum is None:
        return False

    recorded = _recorded_checksum_version(entry)
    if recorded is None:
        # No version on the row: either it predates the migration (v1) or the
        # digest was assigned by hand from compute_checksum() (v2). The two
        # encodings cannot produce the same digest, so trying both detects
        # exactly what dispatching would. v1 goes first because every row of
        # an unmigrated store is v1.
        return _matches(
            compute_checksum_legacy, entry, expected_checksum
        ) or _matches(compute_checksum, entry, expected_checksum)

    # An unknown version (0, negative, or newer than this code) is a mismatch,
    # not a guess at the nearest encoding.
    compute = _ENCODERS.get(recorded)
    return compute is not None and _matches(compute, entry, expected_checksum)


def _matches(
    compute: Callable[[Any], str], entry: Any, expected_checksum: str
) -> bool:
    """
    True when ``compute(entry)`` equals the expected digest.

    A row too malformed to encode (the v1 encoder raises on non-string
    ``used_entities`` or an object without ``entity_type``) is a "no", so one
    corrupted row is reported by verify_chain() instead of aborting it.
    """
    try:
        return compute(entry) == expected_checksum
    except (TypeError, ValueError, AttributeError, OverflowError):
        return False


# One encoder per recorded version. A new encoding adds an entry here and
# bumps CHECKSUM_VERSION; existing rows keep dispatching to the encoder they
# were written with.
_ENCODERS: Dict[int, Callable[[Any], str]] = {
    LEGACY_CHECKSUM_VERSION: compute_checksum_legacy,
    CHECKSUM_VERSION: compute_checksum,
}


def compute_data_checksum(data: str) -> str:
    """
    Compute SHA-256 checksum for arbitrary data.
    
    Args:
        data: String data to compute checksum for
        
    Returns:
        SHA-256 checksum as hexadecimal string
        
    Example:
        >>> checksum = compute_data_checksum("some data")
        >>> print(checksum)
        'a3b2c1d4e5f6...'
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def verify_data_checksum(data: str, expected_checksum: str) -> bool:
    """
    Verify checksum for arbitrary data.
    
    Args:
        data: String data to verify
        expected_checksum: Expected checksum
        
    Returns:
        True if checksum matches, False otherwise
        
    Example:
        >>> data = "some data"
        >>> checksum = compute_data_checksum(data)
        >>> is_valid = verify_data_checksum(data, checksum)
        >>> print(is_valid)
        True
    """
    current_checksum = compute_data_checksum(data)
    return current_checksum == expected_checksum


def compute_dict_checksum(data: Dict[str, Any]) -> str:
    """
    Compute SHA-256 checksum for dictionary data.
    
    Sorts keys to ensure deterministic checksum computation.
    
    Args:
        data: Dictionary data to compute checksum for
        
    Returns:
        SHA-256 checksum as hexadecimal string
        
    Example:
        >>> data = {"key1": "value1", "key2": "value2"}
        >>> checksum = compute_dict_checksum(data)
        >>> print(checksum)
        'a3b2c1d4e5f6...'
    """
    # Sort keys for deterministic checksum
    sorted_items = sorted(data.items())
    data_str = str(sorted_items)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()


def verify_dict_checksum(data: Dict[str, Any], expected_checksum: str) -> bool:
    """
    Verify checksum for dictionary data.
    
    Args:
        data: Dictionary data to verify
        expected_checksum: Expected checksum
        
    Returns:
        True if checksum matches, False otherwise
        
    Example:
        >>> data = {"key1": "value1", "key2": "value2"}
        >>> checksum = compute_dict_checksum(data)
        >>> is_valid = verify_dict_checksum(data, checksum)
        >>> print(is_valid)
        True
    """
    current_checksum = compute_dict_checksum(data)
    return current_checksum == expected_checksum

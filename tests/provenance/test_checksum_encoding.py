"""Checksum encoding tests (issue #2136).

`compute_checksum()` used to paste the 16 hashed fields together with nothing
between them, so two records differing only in where a field boundary falls
produced the same hash. These tests pin the injective encoding, the per-row
version dispatch that keeps pre-existing stores verifiable, and the end-to-end
detection path through `verify_chain()`.
"""

import sqlite3

from semantica.provenance.integrity import (
    CHECKSUM_VERSION,
    LEGACY_CHECKSUM_VERSION,
    checksum_version,
    compute_checksum,
    compute_checksum_legacy,
    verify_checksum,
)
from semantica.provenance.manager import ProvenanceManager
from semantica.provenance.schemas import ProvenanceEntry


class TestInjectiveEncoding:
    def test_field_boundary_move_changes_checksum(self):
        """`ab` + `c` must not hash like `a` + `bc`."""
        a = {"entity_type": "ab", "activity_id": "c"}
        b = {"entity_type": "a", "activity_id": "bc"}
        assert compute_checksum(a) != compute_checksum(b)

    def test_field_boundary_move_collides_under_legacy(self):
        """Documents the v1 hole the fix closes, so a regression to plain
        concatenation fails here rather than silently passing."""
        a = {"entity_type": "ab", "activity_id": "c"}
        b = {"entity_type": "a", "activity_id": "bc"}
        assert compute_checksum_legacy(a) == compute_checksum_legacy(b)

    def test_list_element_boundary_move_changes_checksum(self):
        """One element containing a comma must not hash like two elements."""
        a = {"used_entities": ["a,b"]}
        b = {"used_entities": ["a", "b"]}
        assert compute_checksum(a) != compute_checksum(b)

    def test_list_element_boundary_collides_under_legacy(self):
        a = {"used_entities": ["a,b"]}
        b = {"used_entities": ["a", "b"]}
        assert compute_checksum_legacy(a) == compute_checksum_legacy(b)

    def test_list_order_is_significant(self):
        a = {"used_entities": ["x", "y"]}
        b = {"used_entities": ["y", "x"]}
        assert compute_checksum(a) != compute_checksum(b)

    def test_empty_list_and_absent_field_agree(self):
        """An absent list field defaults to an empty list, so both spellings
        hash the same — the collision to fix is between a comma inside one
        element and two elements, not between absent and empty."""
        a = {"used_entities": [], "entity_type": "t"}
        b = {"entity_type": "t"}
        assert compute_checksum(a) == compute_checksum(b)

    def test_dict_and_dataclass_agree(self):
        """v1 hashed `None` as `''` through the dict path and as `'None'`
        through the dataclass path. v2 normalises both."""
        entry = ProvenanceEntry(
            entity_id="e1",
            entity_type="entity",
            activity_id="extraction",
            source_document="DOI:10.1/x",
        )
        assert compute_checksum(entry) == compute_checksum(entry.to_dict())

    def test_checksum_is_stable(self):
        entry = {"entity_type": "entity", "activity_id": "a", "used_entities": ["u1"]}
        assert compute_checksum(entry) == compute_checksum(dict(entry))


class TestVersionDispatch:
    def test_new_entry_verifies_without_a_flag(self):
        entry = {"entity_type": "entity", "checksum_version": CHECKSUM_VERSION}
        entry["checksum"] = compute_checksum(entry)
        assert verify_checksum(entry) is True

    def test_legacy_entry_still_verifies(self):
        """A row written before the fix has no version and must keep verifying,
        otherwise every existing store reports a broken chain on upgrade."""
        entry = {"entity_type": "entity", "activity_id": "a"}
        entry["checksum"] = compute_checksum_legacy(entry)
        assert "checksum_version" not in entry
        assert verify_checksum(entry) is True

    def test_legacy_checksum_fails_once_stamped_v2(self):
        entry = {"entity_type": "entity", "activity_id": "a"}
        entry["checksum"] = compute_checksum_legacy(entry)
        entry["checksum_version"] = CHECKSUM_VERSION
        assert verify_checksum(entry) is False

    def test_missing_version_reads_as_legacy(self):
        assert checksum_version({}) == LEGACY_CHECKSUM_VERSION
        assert checksum_version({"checksum_version": None}) == LEGACY_CHECKSUM_VERSION
        assert checksum_version({"checksum_version": "2"}) == CHECKSUM_VERSION

    def test_no_checksum_is_not_valid(self):
        assert verify_checksum({"entity_type": "entity"}) is False

    def test_hand_assigned_checksum_verifies_on_a_dict(self):
        """The documented usage assigns the digest by hand, never passing
        through the manager's stamping path. The row then carries no version,
        so verification has to try v2 as well, or it reads a digest it just
        produced as v1 and rejects it."""
        entry = {"entity_type": "entity", "activity_id": "a"}
        entry["checksum"] = compute_checksum(entry)
        assert "checksum_version" not in entry
        assert verify_checksum(entry) is True

    def test_hand_assigned_checksum_verifies_on_a_dataclass(self):
        entry = ProvenanceEntry(
            entity_id="e1",
            entity_type="entity",
            activity_id="a",
            agent_id="agent",
            agent_type="human",
            source_document="doc",
        )
        entry.checksum = compute_checksum(entry)
        assert entry.checksum_version is None
        assert verify_checksum(entry) is True

    def test_computing_does_not_write_to_the_entry(self):
        """compute_checksum() used to stamp the version onto its argument. A
        function that returns a digest should not modify the value it read,
        and a read-only comparison on a legacy row would relabel it."""
        entry = {"entity_type": "entity", "activity_id": "a"}
        first = compute_checksum(entry)
        second = compute_checksum(entry)
        assert first == second
        assert entry == {"entity_type": "entity", "activity_id": "a"}

    def test_an_unrecorded_version_still_verifies_a_legacy_digest(self):
        entry = {"entity_type": "ab", "activity_id": "c"}
        entry["checksum"] = compute_checksum_legacy(entry)
        assert verify_checksum(entry) is True

    def test_a_non_numeric_confidence_fails_verification_instead_of_raising(self):
        """A malformed row is a "no", not an exception: verification answers a
        question, and a ValueError escaping it turns one bad row into a crash
        for the whole chain walk."""
        entry = {"entity_type": "entity", "activity_id": "a", "confidence": "high"}
        entry["checksum"] = compute_checksum(entry)
        assert verify_checksum(entry) is True

        entry["confidence"] = "low"
        assert verify_checksum(entry) is False


class TestStorageRoundTrip:
    def test_checksum_version_survives_sqlite(self, tmp_path):
        db_path = str(tmp_path / "roundtrip.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("E1", source="doc1")

        reloaded = ProvenanceManager(storage_path=db_path)
        entry = reloaded.storage.retrieve("E1")
        assert entry.checksum_version == CHECKSUM_VERSION
        assert verify_checksum(entry) is True

    def test_verify_chain_passes_on_a_fresh_store(self, tmp_path):
        db_path = str(tmp_path / "clean.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("E1", source="doc1")
        mgr.track_entity("E2", source="doc1")
        assert mgr.verify_chain()["valid"] is True

    def test_verify_chain_passes_with_a_legacy_row_next_to_a_new_one(self, tmp_path):
        """The upgrade path: a row written before issue #2136 keeps its v1
        digest and no version, rows appended after it are v2, and the chain
        across the two still verifies. Without this the migration is only
        argued for in prose."""
        db_path = str(tmp_path / "mixed.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("OLD", source="doc1")

        # Rewrite the first row as the pre-migration code would have left it.
        legacy = mgr.storage.retrieve("OLD")
        legacy_digest = compute_checksum_legacy(legacy)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE provenance SET checksum = ?, checksum_version = NULL "
            "WHERE entity_id = 'OLD'",
            (legacy_digest,),
        )
        conn.commit()
        conn.close()

        # A row appended after the upgrade chains onto the legacy digest.
        mgr.track_entity("NEW", source="doc1")

        reopened = ProvenanceManager(storage_path=db_path)
        old_entry = reopened.storage.retrieve("OLD")
        new_entry = reopened.storage.retrieve("NEW")
        assert old_entry.checksum_version is None
        assert new_entry.checksum_version == CHECKSUM_VERSION
        assert new_entry.previous_checksum == legacy_digest
        assert reopened.verify_chain()["valid"] is True


class TestEndToEndDetection:
    def test_verify_chain_detects_a_char_moved_across_a_field_boundary(self, tmp_path):
        """The attack from issue #2136: move one character from the end of
        `entity_type` to the start of `activity_id`, leave the stored checksum
        alone, and the concatenation is byte-identical. v2 must notice."""
        db_path = str(tmp_path / "boundary.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("E1", source="doc1")

        conn = sqlite3.connect(db_path)
        entity_type, activity_id = conn.execute(
            "SELECT entity_type, activity_id FROM provenance WHERE entity_id = 'E1'"
        ).fetchone()
        assert entity_type and activity_id
        conn.execute(
            "UPDATE provenance SET entity_type = ?, activity_id = ? WHERE entity_id = 'E1'",
            (entity_type[:-1], entity_type[-1] + activity_id),
        )
        conn.commit()
        conn.close()

        result = ProvenanceManager(storage_path=db_path).verify_chain()
        assert result["valid"] is False
        assert any(
            link["reason"] == "checksum_mismatch" for link in result["broken_links"]
        )

    def test_verify_chain_still_detects_a_plain_field_edit(self, tmp_path):
        db_path = str(tmp_path / "edit.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("E1", source="doc1")

        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE provenance SET source_document = 'doc2' WHERE entity_id = 'E1'"
        )
        conn.commit()
        conn.close()

        result = ProvenanceManager(storage_path=db_path).verify_chain()
        assert result["valid"] is False


# Every hashed field set to a non-default value, so a reordered, added or
# re-tagged field changes the digest.
_GOLDEN_ENTRY = {
    "entity_type": "entity",
    "activity_id": "extraction",
    "agent_id": "agent-1",
    "agent_type": "software",
    "source_document": "DOI:10.1/x",
    "timestamp": "2026-01-02T03:04:05+00:00",
    "confidence": 0.75,
    "parent_entity_id": "p",
    "previous_version_id": "pv",
    "derived_from_id": "d",
    "used_entities": ["u1", "u2"],
    "previous_checksum": "abc",
    "invalidated": True,
    "invalidated_at_time": "2026-02-01T00:00:00+00:00",
    "invalidated_by": "rev",
    "invalidation_reason": "retracted",
}


class TestGoldenDigests:
    """Stored rows carry these digests, so they are a format, not an output:
    changing either encoding without bumping CHECKSUM_VERSION would report
    every existing row as tampered."""

    def test_v2_digest_is_pinned(self):
        assert compute_checksum(_GOLDEN_ENTRY) == (
            "a39d79d05d6fbd1f2f4d4ef0f39a68076cd3ebbcadafb64c2b34d53274b24dd6"
        )

    def test_v1_digest_matches_the_pre_2136_encoder(self):
        """The value main's compute_checksum() produced before the fix."""
        assert compute_checksum_legacy(_GOLDEN_ENTRY) == (
            "6af44d3f102ab3e2a5df99a3a4f2ac903e3180a7cdca6b1894d7b6ea2bd1c471"
        )


class TestMalformedInput:
    def test_null_confidence_does_not_hash_like_the_default(self):
        """v1's dataclass path hashed a NULL confidence as 'None', so
        `SET confidence = NULL` was caught; defaulting it to 1.0 would not."""
        base = {"entity_type": "entity", "activity_id": "a"}
        assert compute_checksum({**base, "confidence": None}) != compute_checksum(
            {**base, "confidence": 1.0}
        )

    def test_absent_confidence_still_hashes_like_the_default(self):
        base = {"entity_type": "entity", "activity_id": "a"}
        assert compute_checksum(base) == compute_checksum({**base, "confidence": 1.0})

    def test_verify_chain_detects_confidence_set_to_null(self, tmp_path):
        db_path = str(tmp_path / "null_confidence.db")
        ProvenanceManager(storage_path=db_path).track_entity("E1", source="doc1")

        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE provenance SET confidence = NULL WHERE entity_id = 'E1'")
        conn.commit()
        conn.close()

        assert ProvenanceManager(storage_path=db_path).verify_chain()["valid"] is False

    def test_a_string_used_entities_does_not_hash_like_a_list(self):
        assert compute_checksum({"used_entities": "ab"}) != compute_checksum(
            {"used_entities": ["a", "b"]}
        )

    def test_a_non_iterable_used_entities_fails_instead_of_raising(self):
        entry = {"entity_type": "entity", "used_entities": ["u1"]}
        entry["checksum"] = compute_checksum(entry)
        entry["used_entities"] = 5
        assert verify_checksum(entry) is False

    def test_an_unversioned_row_the_v1_encoder_rejects_fails_instead_of_raising(self):
        """The v1 encoder joins used_entities as strings; non-string items
        would raise out of the legacy fallback."""
        entry = {"entity_type": "entity", "used_entities": [1, 2]}
        entry["checksum"] = "0" * 64
        assert verify_checksum(entry) is False

    def test_verify_chain_reports_a_tampered_unversioned_row_instead_of_raising(
        self, tmp_path
    ):
        db_path = str(tmp_path / "int_items.db")
        mgr = ProvenanceManager(storage_path=db_path)
        mgr.track_entity("E1", source="doc1", used_entities=[1, 2])
        assert mgr.verify_chain()["valid"] is True

        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE provenance SET checksum_version = NULL, source_document = 'doc2' "
            "WHERE entity_id = 'E1'"
        )
        conn.commit()
        conn.close()

        assert ProvenanceManager(storage_path=db_path).verify_chain()["valid"] is False

    def test_an_object_without_the_fields_fails_instead_of_raising(self):
        class Bare:
            checksum = "0" * 64

        assert verify_checksum(Bare()) is False

    def test_overflowing_values_fail_instead_of_raising(self):
        assert (
            verify_checksum(
                {"entity_type": "x", "checksum": "abc", "checksum_version": float("inf")}
            )
            is False
        )
        assert verify_checksum({"confidence": 10**400, "checksum": "abc"}) is False

    def test_a_non_dict_mapping_is_read_by_key(self):
        """A Mapping that is not a dict used to be read with getattr, so every
        such entry hashed to the same digest of defaults."""
        from types import MappingProxyType

        a = MappingProxyType({"entity_type": "x", "activity_id": "y"})
        b = MappingProxyType({"entity_type": "other", "activity_id": "z"})
        assert compute_checksum(a) != compute_checksum(b)
        assert compute_checksum(a) == compute_checksum(dict(a))


class TestUnknownVersions:
    def test_an_unknown_version_fails_instead_of_using_the_nearest_encoder(self):
        entry = {"entity_type": "entity", "activity_id": "a"}
        v2_digest = compute_checksum(entry)
        v1_digest = compute_checksum_legacy(entry)
        for version in (0, -1, CHECKSUM_VERSION + 1):
            for digest in (v1_digest, v2_digest):
                assert (
                    verify_checksum(
                        {**entry, "checksum": digest, "checksum_version": version}
                    )
                    is False
                )

    def test_an_explicit_v1_row_verifies_with_the_legacy_encoder(self):
        entry = {"entity_type": "ab", "activity_id": "c", "checksum_version": 1}
        entry["checksum"] = compute_checksum_legacy(entry)
        assert verify_checksum(entry) is True

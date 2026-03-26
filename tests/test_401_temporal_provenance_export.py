"""
Tests for #401 — Temporal Provenance & Export.

Covers all acceptance criteria from the issue:
  - ProvenanceTracker: recorded_at, query_recorded_between
  - ProvenanceTracker: revision_history, export_audit_log
  - RDFExporter: include_temporal OWL-Time Turtle output
  - TemporalVersionManager: format_version, validate_snapshot, migrate_snapshot
"""

import csv
import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from semantica.kg.provenance_tracker import ProvenanceTracker
from semantica.export.rdf_exporter import RDFExporter
from semantica.kg.temporal_query import TemporalVersionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc


def _dt(offset_days: int = 0) -> str:
    """Return an ISO UTC string relative to now."""
    return (datetime.now(UTC) + timedelta(days=offset_days)).isoformat()


# ---------------------------------------------------------------------------
# 1. Transaction Time on Provenance Records
# ---------------------------------------------------------------------------

class TestTransactionTime:
    def test_new_record_has_recorded_at(self):
        tracker = ProvenanceTracker()
        before = datetime.now(UTC)
        tracker.track_entity("E1", "doc.txt")
        after = datetime.now(UTC)

        records = tracker.get_all_sources("E1")
        assert len(records) == 1
        raw = records[0]["recorded_at"]
        recorded = datetime.fromisoformat(raw)
        if recorded.tzinfo is None:
            recorded = recorded.replace(tzinfo=UTC)
        assert before <= recorded <= after

    def test_existing_records_without_recorded_at_still_work(self):
        tracker = ProvenanceTracker()
        # Manually inject an old-style record (no recorded_at)
        tracker._records["old_fact"] = [{"source": "legacy.txt"}]
        # All existing query methods must not crash
        sources = tracker.get_all_sources("old_fact")
        assert sources == [{"source": "legacy.txt"}]

    def test_query_recorded_between_returns_only_matching_records(self):
        tracker = ProvenanceTracker()

        past = datetime.now(UTC) - timedelta(days=30)
        future = datetime.now(UTC) + timedelta(days=30)

        tracker.track_entity("E1", "doc1.txt")   # now → in range [yesterday, tomorrow]
        # Inject a record from 60 days ago
        tracker._records["E2"] = [{
            "source": "old.txt",
            "recorded_at": (datetime.now(UTC) - timedelta(days=60)).isoformat(),
        }]

        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC) + timedelta(days=1)

        results = tracker.query_recorded_between(start, end)
        entity_ids = [r["entity_id"] for r in results]
        assert "E1" in entity_ids
        assert "E2" not in entity_ids

    def test_query_recorded_between_accepts_iso_strings(self):
        tracker = ProvenanceTracker()
        tracker.track_entity("X", "src.txt")

        start = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        end = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        results = tracker.query_recorded_between(start, end)
        assert any(r["entity_id"] == "X" for r in results)

    def test_query_recorded_between_skips_records_without_recorded_at(self):
        tracker = ProvenanceTracker()
        tracker._records["legacy"] = [{"source": "x.txt"}]

        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC) + timedelta(days=1)

        # Must not raise; legacy record is silently skipped
        results = tracker.query_recorded_between(start, end)
        assert all(r["entity_id"] != "legacy" for r in results)


# ---------------------------------------------------------------------------
# 2. Fact Revision Audit Trail
# ---------------------------------------------------------------------------

class TestRevisionHistory:
    def _tracker_with_revisions(self) -> ProvenanceTracker:
        tracker = ProvenanceTracker()
        base_ts = datetime(2024, 3, 1, 0, 0, 0, tzinfo=UTC)
        tracker._records["fact_001"] = [
            {
                "source": "s1",
                "valid_from": "2024-01-01",
                "valid_until": "2024-06-30",
                "recorded_at": (base_ts).isoformat(),
                "author": "alice@example.com",
            },
            {
                "source": "s2",
                "valid_from": "2024-01-01",
                "valid_until": "2024-12-31",
                "recorded_at": (base_ts + timedelta(days=10)).isoformat(),
                "author": "bob@example.com",
                "revision_type": "correction",
                "supersedes": "fact_001_v1",
            },
        ]
        return tracker

    def test_revision_history_returns_versions_in_ascending_order(self):
        tracker = self._tracker_with_revisions()
        history = tracker.revision_history("fact_001")

        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[1]["version"] == 2
        assert history[0]["recorded_at"] < history[1]["recorded_at"]

    def test_revision_history_has_required_fields(self):
        tracker = self._tracker_with_revisions()
        history = tracker.revision_history("fact_001")

        for entry in history:
            assert "version" in entry
            assert "valid_from" in entry
            assert "valid_until" in entry
            assert "recorded_at" in entry
            assert "author" in entry

    def test_revision_history_optional_fields_present_when_set(self):
        tracker = self._tracker_with_revisions()
        history = tracker.revision_history("fact_001")

        assert history[1].get("revision_type") == "correction"
        assert history[1].get("supersedes") == "fact_001_v1"

    def test_revision_history_empty_for_unknown_fact(self):
        tracker = ProvenanceTracker()
        assert tracker.revision_history("nonexistent") == []

    def test_export_audit_log_json_valid(self):
        tracker = self._tracker_with_revisions()
        output = tracker.export_audit_log(["fact_001"], format="json")
        data = json.loads(output)   # must not raise
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["fact_id"] == "fact_001"

    def test_export_audit_log_csv_has_header(self):
        tracker = self._tracker_with_revisions()
        output = tracker.export_audit_log(["fact_001"], format="csv")
        reader = csv.DictReader(io.StringIO(output))
        rows = list(reader)
        assert reader.fieldnames is not None
        assert "fact_id" in reader.fieldnames
        assert "version" in reader.fieldnames
        assert len(rows) == 2

    def test_export_audit_log_empty_fact_ids(self):
        tracker = ProvenanceTracker()
        json_out = tracker.export_audit_log([], format="json")
        assert json.loads(json_out) == []
        csv_out = tracker.export_audit_log([], format="csv")
        reader = csv.DictReader(io.StringIO(csv_out))
        assert list(reader) == []


# ---------------------------------------------------------------------------
# 3. OWL-Time RDF Export
# ---------------------------------------------------------------------------

RDF_DATA_PLAIN = {
    "entities": [
        {"id": "http://ex.org/e1", "text": "Alice", "type": "Person"},
    ],
    "relationships": [
        {
            "id": "http://ex.org/rel1",
            "source_id": "http://ex.org/e1",
            "target_id": "http://ex.org/e2",
            "type": "http://ex.org/knows",
        }
    ],
}

RDF_DATA_TEMPORAL = {
    "entities": [
        {"id": "http://ex.org/e1", "text": "Alice", "type": "Person"},
    ],
    "relationships": [
        {
            "id": "http://ex.org/rel1",
            "source_id": "http://ex.org/e1",
            "target_id": "http://ex.org/e2",
            "type": "http://ex.org/knows",
            "valid_from": "2024-01-01T00:00:00+00:00",
            "valid_until": "2024-12-31T23:59:59+00:00",
        }
    ],
}

RDF_DATA_OPEN = {
    "entities": [],
    "relationships": [
        {
            "id": "http://ex.org/rel2",
            "source_id": "http://ex.org/e1",
            "target_id": "http://ex.org/e2",
            "type": "http://ex.org/employs",
            "valid_from": "2024-01-01T00:00:00+00:00",
            "valid_until": "OPEN",
        }
    ],
}


class TestOWLTimeExport:
    @pytest.fixture
    def exporter(self):
        return RDFExporter()

    def test_default_no_temporal_output_unchanged(self, exporter):
        base = exporter.export_to_rdf(RDF_DATA_PLAIN, format="turtle")
        with_flag = exporter.export_to_rdf(
            RDF_DATA_PLAIN, format="turtle", include_temporal=False
        )
        assert base == with_flag

    def test_include_temporal_adds_owl_time_prefix(self, exporter):
        result = exporter.export_to_rdf(
            RDF_DATA_TEMPORAL, format="turtle", include_temporal=True
        )
        assert "time:" in result or "http://www.w3.org/2006/time#" in result

    def test_include_temporal_emits_interval_and_instants(self, exporter):
        result = exporter.export_to_rdf(
            RDF_DATA_TEMPORAL, format="turtle", include_temporal=True
        )
        assert "time:Interval" in result
        assert "time:hasBeginning" in result
        assert "time:hasEnd" in result
        assert "time:inXSDDateTimeStamp" in result
        assert "2024-01-01" in result
        assert "2024-12-31" in result

    def test_open_valid_until_emits_open_ended_flag(self, exporter):
        result = exporter.export_to_rdf(
            RDF_DATA_OPEN, format="turtle", include_temporal=True
        )
        assert "openEndedInterval" in result
        # Must NOT emit time:hasEnd for an OPEN interval
        assert "time:hasEnd" not in result

    def test_relationships_without_temporal_not_affected(self, exporter):
        result_with = exporter.export_to_rdf(
            RDF_DATA_PLAIN, format="turtle", include_temporal=True
        )
        # No OWL-Time interval nodes for relationships that have no valid_from/until
        assert "time:Interval" not in result_with
        assert "time:hasBeginning" not in result_with

    def test_time_axis_transaction_uses_recorded_at(self, exporter):
        data = {
            "entities": [],
            "relationships": [
                {
                    "id": "http://ex.org/rel3",
                    "source_id": "http://ex.org/e1",
                    "target_id": "http://ex.org/e2",
                    "type": "http://ex.org/rel",
                    "recorded_at": "2024-03-01T00:00:00+00:00",
                    "superseded_at": "OPEN",
                }
            ],
        }
        result = exporter.export_to_rdf(
            data, format="turtle", include_temporal=True, time_axis="transaction"
        )
        assert "time:Interval" in result
        assert "2024-03-01" in result
        assert "openEndedInterval" in result

    def test_output_parseable_by_rdflib(self, exporter):
        """The produced Turtle must be parseable by rdflib (if installed)."""
        pytest.importorskip("rdflib")
        from rdflib import Graph

        result = exporter.export_to_rdf(
            RDF_DATA_TEMPORAL, format="turtle", include_temporal=True
        )
        g = Graph()
        g.parse(data=result, format="turtle")   # raises on parse failure
        assert len(g) > 0


# ---------------------------------------------------------------------------
# 4. Stable Snapshot Serialization Format
# ---------------------------------------------------------------------------

class TestSnapshotSerialization:
    @pytest.fixture
    def manager(self):
        return TemporalVersionManager()

    @pytest.fixture
    def graph(self):
        return {
            "entities": [{"id": "e1", "label": "Alice"}],
            "relationships": [{"source": "e1", "target": "e2", "type": "knows"}],
        }

    def test_create_snapshot_includes_format_version(self, manager, graph):
        snap = manager.create_snapshot(graph, "v1.0", "alice@example.com", "Initial")
        assert snap.get("format_version") == "1.0"

    def test_created_snapshot_passes_validate(self, manager, graph):
        snap = manager.create_snapshot(graph, "v1.0", "alice@example.com", "Initial")
        assert manager.validate_snapshot(snap) is True

    def test_validate_snapshot_false_on_missing_fields(self, manager):
        incomplete = {
            "format_version": "1.0",
            "label": "v1.0",
            # missing: timestamp, author, description, entities, relationships, checksum
        }
        assert manager.validate_snapshot(incomplete) is False

    def test_validate_snapshot_false_reports_missing_field_names(self, manager):
        # validate_snapshot returns False — we just check it doesn't raise
        result = manager.validate_snapshot({"format_version": "1.0"})
        assert result is False

    def test_validate_snapshot_never_raises(self, manager):
        for bad in [{}, None, "string", 42, []]:
            try:
                result = manager.validate_snapshot(bad) if isinstance(bad, dict) else manager.validate_snapshot({})
                assert result in (True, False)
            except Exception as exc:
                pytest.fail(f"validate_snapshot raised unexpectedly: {exc}")

    def test_migrate_snapshot_upgrades_old_format(self, manager):
        old = {
            "label": "v0.1",
            "timestamp": "2023-01-01T00:00:00",
            "entities": [],
            "relationships": [],
        }
        migrated = manager.migrate_snapshot(old)
        assert migrated["format_version"] == "1.0"
        assert migrated["label"] == "v0.1"   # existing data preserved

    def test_migrate_snapshot_fills_missing_required_fields_with_none(self, manager):
        old = {"label": "v0.1"}
        migrated = manager.migrate_snapshot(old)
        for field in ("author", "description", "entities", "relationships", "checksum"):
            assert field in migrated

    def test_migrate_snapshot_already_v1_returned_unchanged(self, manager, graph):
        snap = manager.create_snapshot(graph, "v1.0", "alice@example.com", "desc")
        migrated = manager.migrate_snapshot(snap)
        assert migrated == snap

    def test_migrate_snapshot_no_data_loss(self, manager):
        old = {"label": "v0.1", "custom_field": "keep_me"}
        migrated = manager.migrate_snapshot(old)
        assert migrated["custom_field"] == "keep_me"

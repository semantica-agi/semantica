"""
Comprehensive tests for Issue #395 — Temporal Semantics.

Covers the sub-issues not fully tested elsewhere:
  #396 — Core Temporal Data Model (BiTemporalFact, parse/serialize helpers)
  #397 — Temporal Query Engine (reconstruct_at_time, consistency validation,
          analyze_evolution, query_time_range aggregation strategies)
  #399 — Context Graph Temporal Awareness (state_at, record_decision validity
          windows, find_precedents as_of, CausalChainAnalyzer.trace_at_time)

Already covered separately:
  #398 — tests/kg/test_temporal_reasoning.py
  #400 — tests/semantic_extract/test_temporal_extraction.py
  #401 — tests/test_401_temporal_provenance_export.py
  #402 — tests/kg/test_temporal_query_rewriter.py + tests/context/test_temporal_retriever.py
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc


def _dt(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def _iso(year: int, month: int = 1, day: int = 1) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}T00:00:00Z"


# ===========================================================================
# #396 — Core Temporal Data Model
# ===========================================================================

class TestTemporalBoundSentinel:
    """TemporalBound.OPEN must be a distinct sentinel, not a datetime."""

    def setup_method(self):
        from semantica.kg.temporal_model import TemporalBound
        self.OPEN = TemporalBound.OPEN

    def test_open_is_not_none(self):
        assert self.OPEN is not None

    def test_open_is_not_datetime(self):
        assert not isinstance(self.OPEN, datetime)

    def test_open_value_is_string_OPEN(self):
        assert self.OPEN.value == "OPEN"

    def test_open_equality_with_self(self):
        from semantica.kg.temporal_model import TemporalBound
        assert self.OPEN is TemporalBound.OPEN

    def test_open_not_equal_to_arbitrary_datetime(self):
        assert self.OPEN != _dt(2024)

    def test_open_string_comparison(self):
        from semantica.kg.temporal_model import TemporalBound
        assert TemporalBound.OPEN.value == "OPEN"


class TestParseTemporalValue:
    """parse_temporal_value handles all supported input types."""

    def setup_method(self):
        from semantica.kg.temporal_model import parse_temporal_value
        self.parse = parse_temporal_value

    def test_none_returns_none(self):
        assert self.parse(None) is None

    def test_datetime_aware_passed_through_as_utc(self):
        dt = _dt(2024, 6, 15)
        result = self.parse(dt)
        assert result == dt
        assert result.tzinfo is not None

    def test_datetime_naive_gains_utc(self):
        naive = datetime(2024, 6, 15)
        result = self.parse(naive)
        assert result.tzinfo == UTC

    def test_iso_string_z_suffix(self):
        result = self.parse("2024-03-01T00:00:00Z")
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 1
        assert result.tzinfo is not None

    def test_iso_string_plus_offset(self):
        result = self.parse("2024-03-01T00:00:00+00:00")
        assert result.year == 2024

    def test_iso_string_single_digit_month_coerced(self):
        # e.g., "2024-1-5" should be coerced to "2024-01-05"
        result = self.parse("2024-1-5")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 5

    def test_unix_timestamp_int(self):
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        result = self.parse(ts)
        assert result.year == 2024
        assert result.tzinfo is not None

    def test_unix_timestamp_float(self):
        ts = 1704067200.0
        result = self.parse(ts)
        assert result.year == 2024

    def test_invalid_string_raises_temporal_validation_error(self):
        from semantica.utils.exceptions import TemporalValidationError
        with pytest.raises(TemporalValidationError):
            self.parse("not-a-date")

    def test_unsupported_type_raises_temporal_validation_error(self):
        from semantica.utils.exceptions import TemporalValidationError
        with pytest.raises(TemporalValidationError):
            self.parse([2024, 1, 1])

    def test_result_always_utc_normalised(self):
        result = self.parse("2024-06-15T12:00:00+05:30")
        assert result.tzinfo == UTC
        assert result.hour == 6  # 12:00 IST → 06:30 UTC → 06 (truncated by fromisoformat)


class TestParseTemporalBound:
    """parse_temporal_bound wraps parse_temporal_value for bound fields."""

    def setup_method(self):
        from semantica.kg.temporal_model import parse_temporal_bound, TemporalBound
        self.parse = parse_temporal_bound
        self.OPEN = TemporalBound.OPEN

    def test_none_returns_default_none(self):
        assert self.parse(None) is None

    def test_none_with_explicit_default(self):
        assert self.parse(None, default=self.OPEN) is self.OPEN

    def test_open_sentinel_enum_value_returns_open(self):
        result = self.parse(self.OPEN)
        assert result is self.OPEN

    def test_open_string_returns_open(self):
        result = self.parse("OPEN")
        assert result is self.OPEN

    def test_valid_datetime_string_returns_datetime(self):
        result = self.parse("2024-01-01T00:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_datetime_object_returned_as_datetime(self):
        dt = _dt(2024)
        result = self.parse(dt)
        assert result == dt


class TestSerializeTemporalHelpers:
    """serialize_temporal_value / serialize_temporal_bound round-trip."""

    def setup_method(self):
        from semantica.kg.temporal_model import (
            serialize_temporal_value,
            serialize_temporal_bound,
            TemporalBound,
        )
        self.sv = serialize_temporal_value
        self.sb = serialize_temporal_bound
        self.OPEN = TemporalBound.OPEN

    def test_serialize_none_is_none(self):
        assert self.sv(None) is None

    def test_serialize_datetime_produces_z_suffix(self):
        result = self.sv(_dt(2024, 6, 1))
        assert result.endswith("Z")
        assert "2024-06-01" in result

    def test_serialize_always_utc(self):
        result = self.sv(_dt(2024, 1, 1))
        assert "+00:00" not in result  # should use Z-form
        assert "2024-01-01" in result

    def test_bound_none_is_none(self):
        assert self.sb(None) is None

    def test_bound_open_is_none(self):
        assert self.sb(self.OPEN) is None

    def test_bound_datetime_serializes_normally(self):
        result = self.sb(_dt(2025, 3, 15))
        assert "2025-03-15" in result


class TestBiTemporalFact:
    """BiTemporalFact construction, from_relationship, to_relationship_fields."""

    def setup_method(self):
        from semantica.kg.temporal_model import BiTemporalFact, TemporalBound
        self.BiTemporalFact = BiTemporalFact
        self.OPEN = TemporalBound.OPEN

    def test_from_relationship_basic(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": "2024-12-31T00:00:00Z",
        })
        assert fact.valid_from.year == 2024
        assert isinstance(fact.valid_until, datetime)
        assert fact.valid_until.year == 2024

    def test_from_relationship_open_valid_until(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": "OPEN",
        })
        assert fact.valid_until is self.OPEN

    def test_from_relationship_none_valid_until_becomes_open(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": None,
        })
        assert fact.valid_until is self.OPEN

    def test_from_relationship_no_recorded_at_falls_back_to_valid_from(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-05-01T00:00:00Z",
        })
        # recorded_at should be set (not None)
        assert fact.recorded_at is not None

    def test_from_relationship_with_recorded_at(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "recorded_at": "2024-03-01T00:00:00Z",
        })
        assert fact.recorded_at.month == 3

    def test_bitemporal_transaction_time_superseded_at_open_by_default(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
        })
        assert fact.superseded_at is self.OPEN

    def test_bitemporal_superseded_at_datetime(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "superseded_at": "2025-01-01T00:00:00Z",
        })
        assert isinstance(fact.superseded_at, datetime)
        assert fact.superseded_at.year == 2025

    def test_to_relationship_fields_round_trips_valid_from(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-06-15T00:00:00Z",
            "valid_until": "2025-06-14T00:00:00Z",
        })
        fields = fact.to_relationship_fields()
        assert "valid_from" in fields
        assert "2024-06-15" in fields["valid_from"]

    def test_to_relationship_fields_open_valid_until_serializes_as_none(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": "OPEN",
        })
        fields = fact.to_relationship_fields()
        assert fields["valid_until"] is None

    def test_to_relationship_fields_recorded_at_present(self):
        fact = self.BiTemporalFact.from_relationship({
            "valid_from": "2024-01-01T00:00:00Z",
            "recorded_at": "2024-02-01T00:00:00Z",
        })
        fields = fact.to_relationship_fields()
        assert "recorded_at" in fields
        assert "2024-02-01" in fields["recorded_at"]

    def test_recorded_at_auto_populated_at_creation_time(self):
        before = datetime.now(UTC)
        fact = self.BiTemporalFact(
            valid_from=_dt(2024),
            valid_until=self.OPEN,
        )
        after = datetime.now(UTC)
        # recorded_at should be between before and after
        assert before <= fact.recorded_at <= after


class TestDeserializeAndJsonReady:
    """deserialize_relationship_temporal_fields and relationship_to_json_ready."""

    def setup_method(self):
        from semantica.kg.temporal_model import (
            deserialize_relationship_temporal_fields,
            relationship_to_json_ready,
            temporal_structure_to_json_ready,
            TemporalBound,
        )
        self.deser = deserialize_relationship_temporal_fields
        self.json_ready = relationship_to_json_ready
        self.structure_ready = temporal_structure_to_json_ready
        self.OPEN = TemporalBound.OPEN

    def test_deserialize_normalizes_single_digit_month(self):
        rel = {"id": "r1", "valid_from": "2024-1-5", "valid_until": None}
        result = self.deser(rel)
        assert "2024-01-05" in result["valid_from"]

    def test_deserialize_preserves_non_temporal_fields(self):
        rel = {"id": "r1", "type": "knows", "valid_from": "2024-01-01T00:00:00Z"}
        result = self.deser(rel)
        assert result["type"] == "knows"
        assert result["id"] == "r1"

    def test_deserialize_open_until_retained_as_sentinel(self):
        rel = {"valid_from": "2024-01-01T00:00:00Z", "valid_until": "OPEN"}
        result = self.deser(rel)
        assert result["valid_until"] is self.OPEN

    def test_json_ready_converts_datetimes_to_strings(self):
        rel = {
            "id": "r1",
            "valid_from": "2024-01-01T00:00:00Z",
            "valid_until": "2024-12-31T00:00:00Z",
        }
        result = self.json_ready(rel)
        assert isinstance(result["valid_from"], str)
        assert isinstance(result["valid_until"], str)

    def test_json_ready_open_until_is_none(self):
        rel = {"valid_from": "2024-01-01T00:00:00Z", "valid_until": "OPEN"}
        result = self.json_ready(rel)
        assert result["valid_until"] is None

    def test_temporal_structure_to_json_ready_recurses_into_dict(self):
        data = {
            "outer": {
                "valid_from": _dt(2024),
                "valid_until": self.OPEN,
            }
        }
        result = self.structure_ready(data)
        assert isinstance(result["outer"]["valid_from"], str)
        assert result["outer"]["valid_until"] is None

    def test_temporal_structure_to_json_ready_recurses_into_list(self):
        data = [_dt(2024), self.OPEN]
        result = self.structure_ready(data)
        assert isinstance(result[0], str)
        assert result[1] is None

    def test_temporal_structure_to_json_ready_primitive_passthrough(self):
        assert self.structure_ready("hello") == "hello"
        assert self.structure_ready(42) == 42
        assert self.structure_ready(None) is None


# ===========================================================================
# #397 — Temporal Query Engine
# ===========================================================================

class TestReconstructAtTime:
    """TemporalGraphQuery.reconstruct_at_time returns a self-consistent subgraph."""

    def setup_method(self):
        from semantica.kg import TemporalGraphQuery
        self.q = TemporalGraphQuery()

    def _graph(self, entities, relationships):
        return {"entities": entities, "relationships": relationships}

    def test_active_entity_and_relationship_included(self):
        graph = self._graph(
            entities=[
                {"id": "A", "valid_from": _iso(2020), "valid_until": _iso(2025)},
                {"id": "B", "valid_from": _iso(2020), "valid_until": _iso(2025)},
            ],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "knows",
                 "valid_from": _iso(2021), "valid_until": _iso(2024)},
            ],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2022))
        assert len(result["entities"]) == 2
        assert len(result["relationships"]) == 1

    def test_expired_entity_excluded(self):
        graph = self._graph(
            entities=[
                {"id": "A", "valid_from": _iso(2010), "valid_until": _iso(2015)},
                {"id": "B", "valid_from": _iso(2020)},
            ],
            relationships=[],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2023))
        ids = {e["id"] for e in result["entities"]}
        assert "A" not in ids
        assert "B" in ids

    def test_future_entity_excluded(self):
        graph = self._graph(
            entities=[
                {"id": "future", "valid_from": _iso(2030)},
                {"id": "present", "valid_from": _iso(2020)},
            ],
            relationships=[],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2024))
        ids = {e["id"] for e in result["entities"]}
        assert "future" not in ids
        assert "present" in ids

    def test_dangling_relationship_removed_when_source_expired(self):
        graph = self._graph(
            entities=[
                {"id": "A", "valid_from": _iso(2010), "valid_until": _iso(2015)},
                {"id": "B", "valid_from": _iso(2010)},
            ],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "rel"},
            ],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2020))
        assert result["relationships"] == []

    def test_dangling_relationship_removed_when_target_expired(self):
        graph = self._graph(
            entities=[
                {"id": "A", "valid_from": _iso(2010)},
                {"id": "B", "valid_from": _iso(2010), "valid_until": _iso(2015)},
            ],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "rel"},
            ],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2020))
        assert result["relationships"] == []

    def test_entity_timeless_always_included(self):
        # Entities with no valid_from/valid_until are always considered active
        graph = self._graph(
            entities=[{"id": "timeless"}],
            relationships=[],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2024))
        assert len(result["entities"]) == 1

    def test_no_entities_filters_only_relationships(self):
        graph = self._graph(
            entities=[],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "t",
                 "valid_from": _iso(2020), "valid_until": _iso(2025)},
                {"id": "r2", "source": "C", "target": "D", "type": "t",
                 "valid_from": _iso(2010), "valid_until": _iso(2015)},
            ],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2022))
        assert len(result["relationships"]) == 1
        assert result["relationships"][0]["id"] == "r1"

    def test_boundary_dates_inclusive(self):
        at = _dt(2024, 6, 1)
        graph = self._graph(
            entities=[],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "t",
                 "valid_from": _iso(2024, 6, 1), "valid_until": _iso(2024, 12, 31)},
            ],
        )
        result = self.q.reconstruct_at_time(graph, at)
        assert len(result["relationships"]) == 1

    def test_result_is_independent_copy(self):
        """Mutating reconstruct_at_time output must not affect original graph."""
        graph = self._graph(
            entities=[{"id": "A"}],
            relationships=[],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2024))
        result["entities"].clear()
        assert len(graph["entities"]) == 1

    def test_transaction_time_axis_filters_by_recorded_at(self):
        graph = self._graph(
            entities=[],
            relationships=[
                {"id": "r1", "source": "A", "target": "B", "type": "t",
                 "recorded_at": _iso(2022), "superseded_at": "OPEN"},
                {"id": "r2", "source": "C", "target": "D", "type": "t",
                 "recorded_at": _iso(2025), "superseded_at": "OPEN"},
            ],
        )
        result = self.q.reconstruct_at_time(graph, _dt(2023), time_axis="transaction")
        ids = {r["id"] for r in result["relationships"]}
        assert "r1" in ids
        assert "r2" not in ids


class TestTemporalConsistencyValidation:
    """TemporalGraphQuery.validate_temporal_consistency detects all issue types."""

    def setup_method(self):
        from semantica.kg import TemporalGraphQuery
        self.q = TemporalGraphQuery()

    def test_valid_graph_has_no_errors(self):
        graph = {
            "entities": [
                {"id": "A", "valid_from": _iso(2020), "valid_until": _iso(2025)},
                {"id": "B", "valid_from": _iso(2020), "valid_until": _iso(2025)},
            ],
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2021), "valid_until": _iso(2024)},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        assert report.errors == []

    def test_inverted_interval_detected_as_error(self):
        graph = {
            "entities": [
                {"id": "A"}, {"id": "B"},
            ],
            "relationships": [
                {"id": "bad", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2025), "valid_until": _iso(2020)},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        error_types = [e["issue_type"] for e in report.errors]
        assert "inverted_interval" in error_types

    def test_missing_source_entity_detected(self):
        graph = {
            "entities": [{"id": "B"}],
            "relationships": [
                {"id": "r1", "source": "MISSING", "target": "B", "type": "rel"},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        error_types = [e["issue_type"] for e in report.errors]
        assert "missing_source_entity" in error_types

    def test_missing_target_entity_detected(self):
        graph = {
            "entities": [{"id": "A"}],
            "relationships": [
                {"id": "r1", "source": "A", "target": "MISSING", "type": "rel"},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        error_types = [e["issue_type"] for e in report.errors]
        assert "missing_target_entity" in error_types

    def test_relationship_outside_entity_lifetime_detected(self):
        graph = {
            "entities": [
                {"id": "A", "valid_from": _iso(2022), "valid_until": _iso(2023)},
                {"id": "B", "valid_from": _iso(2020)},
            ],
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2019), "valid_until": _iso(2021)},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        error_types = [e["issue_type"] for e in report.errors]
        assert "source_lifetime_mismatch" in error_types

    def test_overlapping_same_edge_detected_as_warning(self):
        graph = {
            "entities": [{"id": "A"}, {"id": "B"}],
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2020), "valid_until": _iso(2023)},
                {"id": "r2", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2022), "valid_until": _iso(2025)},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        warning_types = [w["issue_type"] for w in report.warnings]
        assert "overlapping_same_edge" in warning_types

    def test_gap_after_restart_detected_as_warning(self):
        graph = {
            "entities": [{"id": "A"}, {"id": "B"}],
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2020), "valid_until": _iso(2021)},
                {"id": "r2", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2023), "valid_until": _iso(2025)},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        warning_types = [w["issue_type"] for w in report.warnings]
        assert "gap_after_restart" in warning_types

    def test_consistency_report_has_errors_and_warnings_fields(self):
        graph = {"entities": [], "relationships": []}
        report = self.q.validate_temporal_consistency(graph)
        assert hasattr(report, "errors")
        assert hasattr(report, "warnings")

    def test_empty_graph_no_issues(self):
        report = self.q.validate_temporal_consistency({"entities": [], "relationships": []})
        assert report.errors == []
        assert report.warnings == []

    def test_error_entries_have_required_keys(self):
        graph = {
            "entities": [{"id": "A"}],
            "relationships": [
                {"id": "r1", "source": "A", "target": "GONE", "type": "rel"},
            ],
        }
        report = self.q.validate_temporal_consistency(graph)
        assert len(report.errors) > 0
        for err in report.errors:
            assert "message" in err
            assert "fact_id" in err
            assert "issue_type" in err


class TestQueryTimeRangeAggregation:
    """query_time_range aggregation strategies."""

    def setup_method(self):
        from semantica.kg import TemporalGraphQuery
        # Use year granularity so normalization is coarse and predictable
        self.q = TemporalGraphQuery(temporal_granularity="year")
        self.graph = {
            "relationships": [
                # Starts before and ends well after the query window — full coverage
                {"id": "multi-year", "source": "A", "target": "B", "type": "rel",
                 "valid_from": _iso(2021, 1, 1), "valid_until": _iso(2026, 1, 1)},
                # Spans only 2022 — overlaps start of window but does not cover all of it
                {"id": "one-year", "source": "C", "target": "D", "type": "rel",
                 "valid_from": _iso(2022, 1, 1), "valid_until": _iso(2022, 12, 31)},
                # Completely outside
                {"id": "outside", "source": "G", "target": "H", "type": "rel",
                 "valid_from": _iso(2030, 1, 1), "valid_until": _iso(2031, 12, 31)},
            ]
        }
        # Query window: 2022 to 2024
        self.start = _iso(2022, 1, 1)
        self.end = _iso(2024, 12, 31)

    def test_union_returns_all_overlapping(self):
        result = self.q.query_time_range(
            self.graph, "", self.start, self.end,
            temporal_aggregation="union",
        )
        ids = {r["id"] for r in result["relationships"]}
        assert "multi-year" in ids
        assert "one-year" in ids
        assert "outside" not in ids

    def test_intersection_returns_only_full_range_coverage(self):
        result = self.q.query_time_range(
            self.graph, "", self.start, self.end,
            temporal_aggregation="intersection",
        )
        ids = {r["id"] for r in result["relationships"]}
        assert "multi-year" in ids
        # one-year only covers 2022, not the full 2022-2024 window
        assert "one-year" not in ids

    def test_evolution_produces_buckets(self):
        result = self.q.query_time_range(
            self.graph, "", self.start, self.end,
            temporal_aggregation="evolution",
        )
        assert result["relationship_buckets"] is not None

    def test_result_contains_aggregation_field(self):
        for strategy in ("union", "intersection", "evolution"):
            result = self.q.query_time_range(
                self.graph, "", self.start, self.end,
                temporal_aggregation=strategy,
            )
            assert result["aggregation"] == strategy

    def test_outside_range_always_excluded(self):
        result = self.q.query_time_range(
            self.graph, "", self.start, self.end,
        )
        ids = {r["id"] for r in result["relationships"]}
        assert "outside" not in ids


class TestAnalyzeEvolution:
    """TemporalGraphQuery.analyze_evolution returns expected keys and values."""

    def setup_method(self):
        from semantica.kg import TemporalGraphQuery
        self.q = TemporalGraphQuery()
        self.graph = {
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "employs",
                 "valid_from": _iso(2020), "valid_until": _iso(2022)},
                {"id": "r2", "source": "A", "target": "C", "type": "partners_with",
                 "valid_from": _iso(2021), "valid_until": _iso(2023)},
                {"id": "r3", "source": "A", "target": "D", "type": "employs",
                 "valid_from": _iso(2022), "valid_until": _iso(2024)},
            ]
        }

    def test_returns_num_relationships(self):
        result = self.q.analyze_evolution(self.graph)
        assert "num_relationships" in result
        assert result["num_relationships"] == 3

    def test_returns_count_metric(self):
        result = self.q.analyze_evolution(self.graph, metrics=["count"])
        assert "count" in result

    def test_returns_diversity_metric(self):
        result = self.q.analyze_evolution(self.graph, metrics=["diversity"])
        assert "diversity" in result

    def test_returns_stability_metric(self):
        result = self.q.analyze_evolution(self.graph, metrics=["stability"])
        assert "stability" in result

    def test_entity_filter_reduces_relationships(self):
        result = self.q.analyze_evolution(self.graph, entity="A")
        # All have A as source
        assert result["num_relationships"] == 3

    def test_entity_filter_with_nonexistent_entity_returns_zero(self):
        result = self.q.analyze_evolution(self.graph, entity="NOBODY")
        assert result["num_relationships"] == 0

    def test_relationship_type_filter(self):
        result = self.q.analyze_evolution(self.graph, relationship="employs")
        assert result["num_relationships"] == 2

    def test_time_range_filter_reduces_relationships(self):
        result = self.q.analyze_evolution(
            self.graph,
            start_time=_iso(2021),
            end_time=_iso(2022),
        )
        assert result["num_relationships"] >= 1

    def test_time_range_field_present_in_result(self):
        result = self.q.analyze_evolution(
            self.graph,
            start_time=_iso(2020),
            end_time=_iso(2024),
        )
        assert "time_range" in result

    def test_default_metrics_computed_without_explicit_list(self):
        result = self.q.analyze_evolution(self.graph)
        # All three default metrics should be present
        for metric in ("count", "diversity", "stability"):
            assert metric in result


class TestDetectTemporalPatterns:
    """TemporalGraphQuery.query_temporal_pattern exercises pattern detection."""

    def setup_method(self):
        from semantica.kg import TemporalGraphQuery
        self.q = TemporalGraphQuery()
        # Build a graph with a repeating sequence
        self.graph = {
            "relationships": [
                {"id": "r1", "source": "A", "target": "B", "type": "event",
                 "valid_from": _iso(2022, 1), "valid_until": _iso(2022, 3)},
                {"id": "r2", "source": "B", "target": "C", "type": "event",
                 "valid_from": _iso(2022, 2), "valid_until": _iso(2022, 4)},
                {"id": "r3", "source": "C", "target": "A", "type": "event",
                 "valid_from": _iso(2022, 4), "valid_until": _iso(2022, 6)},
            ]
        }

    def test_result_contains_pattern_field(self):
        result = self.q.query_temporal_pattern(self.graph, "sequence")
        assert "pattern" in result
        assert result["pattern"] == "sequence"

    def test_result_contains_patterns_list(self):
        result = self.q.query_temporal_pattern(self.graph, "sequence")
        assert "patterns" in result
        assert isinstance(result["patterns"], (list, dict))

    def test_result_contains_num_patterns(self):
        result = self.q.query_temporal_pattern(self.graph, "sequence")
        assert "num_patterns" in result

    def test_cycle_pattern_type_accepted(self):
        result = self.q.query_temporal_pattern(self.graph, "cycle")
        assert result["pattern"] == "cycle"

    def test_trend_pattern_type_accepted(self):
        result = self.q.query_temporal_pattern(self.graph, "trend")
        assert result["pattern"] == "trend"

    def test_empty_graph_returns_zero_patterns(self):
        result = self.q.query_temporal_pattern({"relationships": []}, "sequence")
        assert result["num_patterns"] == 0


# ===========================================================================
# #399 — Context Graph Temporal Awareness
# ===========================================================================

class TestContextGraphStateAt:
    """ContextGraph.state_at returns snapshot valid at the given timestamp."""

    def setup_method(self):
        from semantica.context import ContextGraph
        self.graph = ContextGraph()

    def test_returns_dict_with_expected_keys(self):
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        for key in ("timestamp", "nodes", "edges", "entities", "relationships", "decisions"):
            assert key in snapshot

    def test_timestamp_in_snapshot_matches_input(self):
        snapshot = self.graph.state_at("2024-06-15T00:00:00Z")
        assert "2024-06-15" in snapshot["timestamp"]

    def test_active_node_included_in_snapshot(self):
        self.graph.add_node(
            node_id="n1",
            node_type="Entity",
            content="Always active",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        ids = {n["id"] for n in snapshot["nodes"]}
        assert "n1" in ids

    def test_future_node_excluded_from_snapshot(self):
        self.graph.add_node(
            node_id="future",
            node_type="Entity",
            content="Not yet",
            valid_from="2030-01-01T00:00:00Z",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        ids = {n["id"] for n in snapshot["nodes"]}
        assert "future" not in ids

    def test_expired_node_excluded_from_snapshot(self):
        self.graph.add_node(
            node_id="expired",
            node_type="Entity",
            content="Old fact",
            valid_from="2010-01-01T00:00:00Z",
            valid_until="2015-01-01T00:00:00Z",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        ids = {n["id"] for n in snapshot["nodes"]}
        assert "expired" not in ids

    def test_state_at_accepts_datetime_object(self):
        snapshot = self.graph.state_at(_dt(2024, 6, 1))
        assert snapshot["timestamp"] is not None

    def test_state_at_accepts_iso_string(self):
        snapshot = self.graph.state_at("2024-06-01T00:00:00Z")
        assert "2024-06-01" in snapshot["timestamp"]

    def test_state_at_accepts_unix_timestamp(self):
        ts = 1704067200  # 2024-01-01 UTC
        snapshot = self.graph.state_at(ts)
        assert "2024-01-01" in snapshot["timestamp"]

    def test_decisions_key_contains_only_decision_nodes(self):
        self.graph.add_node(
            node_id="d1",
            node_type="decision",
            content="Approve loan",
            properties={
                "category": "loan",
                "scenario": "Approve loan",
                "reasoning": "good credit",
                "outcome": "approved",
                "confidence": 0.9,
            },
        )
        self.graph.add_node(
            node_id="e1",
            node_type="Entity",
            content="Bob",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        decision_ids = {d["id"] for d in snapshot["decisions"]}
        assert "d1" in decision_ids
        # entity node should NOT appear in decisions
        assert "e1" not in decision_ids

    def test_dangling_edge_excluded_when_target_node_expired(self):
        self.graph.add_node(
            node_id="A",
            node_type="Entity",
            content="A",
        )
        self.graph.add_node(
            node_id="B_old",
            node_type="Entity",
            content="B old",
            valid_from="2010-01-01T00:00:00Z",
            valid_until="2015-01-01T00:00:00Z",
        )
        self.graph.add_edge(
            source_id="A",
            target_id="B_old",
            relationship_type="knows",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        # Edge should be excluded since B_old is expired
        edge_pairs = {
            (e.get("source_id", e.get("source")), e.get("target_id", e.get("target")))
            for e in snapshot["edges"]
        }
        assert ("A", "B_old") not in edge_pairs


class TestRecordDecisionWithValidityWindows:
    """record_decision() accepts valid_from / valid_until and they appear in state_at."""

    def setup_method(self):
        from semantica.context import ContextGraph
        self.graph = ContextGraph()

    def test_record_decision_returns_id(self):
        did = self.graph.record_decision(
            category="test",
            scenario="some scenario",
            reasoning="because",
            outcome="yes",
            confidence=0.8,
        )
        assert isinstance(did, str)
        assert len(did) > 0

    def test_decision_with_valid_from_appears_in_state_after(self):
        self.graph.record_decision(
            category="policy",
            scenario="new regulation",
            reasoning="legal requirement",
            outcome="implemented",
            confidence=0.95,
            valid_from="2024-01-01T00:00:00Z",
        )
        snapshot = self.graph.state_at("2024-06-01T00:00:00Z")
        assert len(snapshot["decisions"]) >= 1

    def test_decision_with_valid_until_excluded_after_expiry(self):
        self.graph.record_decision(
            category="policy",
            scenario="old regulation",
            reasoning="superseded",
            outcome="revoked",
            confidence=0.9,
            valid_from="2020-01-01T00:00:00Z",
            valid_until="2022-01-01T00:00:00Z",
        )
        snapshot = self.graph.state_at("2024-01-01T00:00:00Z")
        # The expired decision should not appear in the 2024 snapshot
        decision_scenarios = [d["scenario"] for d in snapshot["decisions"]]
        assert "old regulation" not in decision_scenarios

    def test_decision_valid_during_window_appears(self):
        self.graph.record_decision(
            category="approval",
            scenario="drug approval",
            reasoning="phase 3 complete",
            outcome="approved",
            confidence=0.99,
            valid_from="2022-01-01T00:00:00Z",
            valid_until="2026-01-01T00:00:00Z",
        )
        snapshot = self.graph.state_at("2024-06-01T00:00:00Z")
        scenarios = [d["scenario"] for d in snapshot["decisions"]]
        assert "drug approval" in scenarios

    def test_multiple_decisions_time_partitioned(self):
        self.graph.record_decision(
            category="cat",
            scenario="old policy",
            reasoning="r",
            outcome="o",
            confidence=0.8,
            valid_from="2018-01-01T00:00:00Z",
            valid_until="2020-01-01T00:00:00Z",
        )
        self.graph.record_decision(
            category="cat",
            scenario="new policy",
            reasoning="r",
            outcome="o",
            confidence=0.8,
            valid_from="2021-01-01T00:00:00Z",
        )
        old_snapshot = self.graph.state_at("2019-06-01T00:00:00Z")
        new_snapshot = self.graph.state_at("2024-06-01T00:00:00Z")

        old_scenarios = [d["scenario"] for d in old_snapshot["decisions"]]
        new_scenarios = [d["scenario"] for d in new_snapshot["decisions"]]

        assert "old policy" in old_scenarios
        assert "new policy" not in old_scenarios
        assert "new policy" in new_scenarios
        assert "old policy" not in new_scenarios


class TestFindPrecedentsAsOf:
    """find_precedents_by_scenario with as_of filters to decisions recorded by then."""

    def setup_method(self):
        from semantica.context import ContextGraph
        self.graph = ContextGraph()

    def test_as_of_filters_future_decisions(self):
        # Record two decisions with different valid_from
        self.graph.record_decision(
            category="loan",
            scenario="approve loan for Bob",
            reasoning="good credit history",
            outcome="approved",
            confidence=0.9,
            valid_from="2020-01-01T00:00:00Z",
        )
        self.graph.record_decision(
            category="loan",
            scenario="approve loan for Alice",
            reasoning="excellent credit",
            outcome="approved",
            confidence=0.95,
            valid_from="2025-01-01T00:00:00Z",
        )

        # as_of 2022 — Alice's decision doesn't exist yet
        # Use similarity_threshold=0.0 so word-overlap doesn't filter out candidates;
        # find_precedents_by_scenario returns {"decision": {...}, "similarity": ...} dicts.
        precedents = self.graph.find_precedents_by_scenario(
            "approve loan for Carol",
            as_of="2022-01-01T00:00:00Z",
            similarity_threshold=0.0,
        )
        scenarios = [p["decision"]["scenario"] for p in precedents]
        # Bob's decision should be reachable; Alice's should not appear
        assert isinstance(precedents, list)
        assert "approve loan for Bob" in scenarios
        assert "approve loan for Alice" not in scenarios

    def test_find_precedents_no_as_of_returns_list(self):
        self.graph.record_decision(
            category="risk",
            scenario="approve high-risk trade",
            reasoning="hedged position",
            outcome="approved",
            confidence=0.7,
        )
        result = self.graph.find_precedents_by_scenario("approve trade")
        assert isinstance(result, list)


class TestCausalChainAnalyzerTraceAtTime:
    """CausalChainAnalyzer.trace_at_time uses only facts recorded up to at_time."""

    def setup_method(self):
        from semantica.context.causal_analyzer import CausalChainAnalyzer
        from semantica.context import ContextGraph
        self.ContextGraph = ContextGraph
        self.CausalChainAnalyzer = CausalChainAnalyzer

    def test_trace_at_time_with_context_graph_returns_list(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        result = analyzer.trace_at_time("nonexistent_id", "2024-01-01T00:00:00Z")
        assert isinstance(result, list)

    def test_trace_at_time_invalid_direction_raises_value_error(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        with pytest.raises(ValueError, match="Direction"):
            analyzer.trace_at_time("id", "2024-01-01T00:00:00Z", direction="sideways")

    def test_trace_at_time_invalid_max_depth_raises_value_error(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        with pytest.raises(ValueError, match="max_depth"):
            analyzer.trace_at_time("id", "2024-01-01T00:00:00Z", max_depth=0)

    def test_trace_at_time_accepts_datetime_object(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        result = analyzer.trace_at_time("id", _dt(2024))
        assert isinstance(result, list)

    def test_trace_at_time_upstream_direction(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        result = analyzer.trace_at_time("id", "2024-01-01T00:00:00Z", direction="upstream")
        assert isinstance(result, list)

    def test_trace_at_time_downstream_direction(self):
        graph = self.ContextGraph()
        analyzer = self.CausalChainAnalyzer(graph_store=graph)
        result = analyzer.trace_at_time("id", "2024-01-01T00:00:00Z", direction="downstream")
        assert isinstance(result, list)

    def test_trace_at_time_with_execute_query_store_returns_list(self):
        """When graph_store has execute_query, trace_at_time should not crash."""
        mock_store = MagicMock()
        mock_store.execute_query.return_value = {"records": []}
        # Remove nodes/edges to force the execute_query branch
        del mock_store.nodes
        del mock_store.edges
        analyzer = self.CausalChainAnalyzer(graph_store=mock_store)
        result = analyzer.trace_at_time("id", "2024-01-01T00:00:00Z")
        assert isinstance(result, list)

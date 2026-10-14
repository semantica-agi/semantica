"""
Deterministic temporal reasoning primitives for Semantica.

This module is the single source of truth for interval math across temporal KG
features. It performs zero LLM calls: extraction may happen upstream, but all
temporal reasoning here is pure Python and fully deterministic.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from .temporal_model import BiTemporalFact, TemporalBound, parse_temporal_bound, parse_temporal_value


@dataclass(frozen=True)
class TemporalInterval:
    start: datetime
    end: datetime | TemporalBound
    label: Optional[str] = None


class IntervalRelation(Enum):
    BEFORE = "before"
    AFTER = "after"
    MEETS = "meets"
    MET_BY = "met_by"
    OVERLAPS = "overlaps"
    OVERLAPPED_BY = "overlapped_by"
    STARTS = "starts"
    STARTED_BY = "started_by"
    DURING = "during"
    CONTAINS = "contains"
    FINISHES = "finishes"
    FINISHED_BY = "finished_by"
    EQUALS = "equals"


class TemporalReasoningEngine:
    """Pure-Python temporal reasoning engine with Allen interval algebra."""

    SUPPORTED_GRANULARITIES = {"second", "minute", "hour", "day", "week", "month", "year"}

    def relation(self, a: TemporalInterval, b: TemporalInterval) -> IntervalRelation:
        self._validate_interval(a)
        self._validate_interval(b)

        a_end = self._end_value(a.end)
        b_end = self._end_value(b.end)

        if a_end < b.start:
            return IntervalRelation.BEFORE
        if a.start > b_end:
            return IntervalRelation.AFTER
        if a_end == b.start:
            return IntervalRelation.MEETS
        if a.start == b_end:
            return IntervalRelation.MET_BY
        if a.start == b.start and a_end == b_end:
            return IntervalRelation.EQUALS
        if a.start == b.start and a_end < b_end:
            return IntervalRelation.STARTS
        if a.start == b.start and a_end > b_end:
            return IntervalRelation.STARTED_BY
        if a_end == b_end and a.start > b.start:
            return IntervalRelation.FINISHES
        if a_end == b_end and a.start < b.start:
            return IntervalRelation.FINISHED_BY
        if a.start < b.start and a_end > b.start and a_end < b_end:
            return IntervalRelation.OVERLAPS
        if a.start > b.start and a.start < b_end and a_end > b_end:
            return IntervalRelation.OVERLAPPED_BY
        if a.start > b.start and a_end < b_end:
            return IntervalRelation.DURING
        return IntervalRelation.CONTAINS

    def overlaps(self, a: TemporalInterval, b: TemporalInterval) -> bool:
        relation = self.relation(a, b)
        return relation not in {
            IntervalRelation.BEFORE,
            IntervalRelation.AFTER,
            IntervalRelation.MEETS,
            IntervalRelation.MET_BY,
        }

    def contains(self, outer: TemporalInterval, inner: TemporalInterval) -> bool:
        self._validate_interval(outer)
        self._validate_interval(inner)
        return outer.start <= inner.start and self._end_value(outer.end) >= self._end_value(inner.end)

    def active_at(
        self,
        interval: TemporalInterval,
        timestamp: Any,
        *,
        granularity: Optional[str] = None,
    ) -> bool:
        self._validate_interval(interval)
        point = parse_temporal_value(timestamp)
        start = interval.start
        end = interval.end

        if granularity is not None:
            point = self.normalize_timestamp(point, granularity)
            start = self.normalize_timestamp(start, granularity)
            if isinstance(end, datetime):
                end = self.normalize_timestamp(end, granularity)

        return start <= point and (end is TemporalBound.OPEN or point < self._coerce_datetime(end))

    def merge_intervals(self, intervals: Iterable[TemporalInterval]) -> List[TemporalInterval]:
        ordered = sorted((self._validated_copy(i) for i in intervals), key=lambda item: item.start)
        if not ordered:
            return []

        merged: List[TemporalInterval] = [ordered[0]]
        for interval in ordered[1:]:
            current = merged[-1]
            if self._touches_or_overlaps(current, interval):
                new_end = self._max_end(current.end, interval.end)
                merged[-1] = TemporalInterval(start=current.start, end=new_end, label=current.label)
            else:
                merged.append(interval)
        return merged

    def gap_analysis(
        self,
        intervals: Iterable[TemporalInterval],
        domain_start: Any,
        domain_end: Any,
    ) -> List[TemporalInterval]:
        domain = self._make_interval(domain_start, domain_end, label="domain")
        clipped = self._clip_to_domain(intervals, domain)
        merged = self.merge_intervals(clipped)

        gaps: List[TemporalInterval] = []
        cursor = domain.start
        for interval in merged:
            if cursor < interval.start:
                gaps.append(TemporalInterval(start=cursor, end=interval.start, label="gap"))
            cursor = self._max_datetime(cursor, self._end_as_datetime(interval.end, domain.end))
        if cursor < self._coerce_datetime(domain.end):
            gaps.append(TemporalInterval(start=cursor, end=self._coerce_datetime(domain.end), label="gap"))
        return gaps

    def coverage_percentage(
        self,
        intervals: Iterable[TemporalInterval],
        domain_start: Any,
        domain_end: Any,
    ) -> float:
        domain = self._make_interval(domain_start, domain_end, label="domain")
        domain_duration = (self._coerce_datetime(domain.end) - domain.start).total_seconds()
        if domain_duration <= 0:
            return 0.0
        covered = 0.0
        for interval in self.merge_intervals(self._clip_to_domain(intervals, domain)):
            covered += (self._end_as_datetime(interval.end, domain.end) - interval.start).total_seconds()
        return max(0.0, min(1.0, covered / domain_duration))

    def timeline_of(self, entity_id: Any, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        entity_key = str(entity_id)
        events: List[Dict[str, Any]] = []

        for fact in graph.get("entities", []):
            if str(fact.get("id", fact.get("name", ""))) != entity_key:
                continue
            events.extend(self._events_for_fact(fact))

        for fact in graph.get("relationships", []):
            source_key = str(fact.get("source") or fact.get("source_id"))
            target_key = str(fact.get("target") or fact.get("target_id"))
            if source_key != entity_key and target_key != entity_key:
                continue
            events.extend(self._events_for_fact(fact))

        return sorted(events, key=lambda item: (item["timestamp"], item["change_type"]))

    def retroactive_coverage(
        self,
        revision: BiTemporalFact | Dict[str, Any],
        original_facts: Iterable[BiTemporalFact | Dict[str, Any]],
    ) -> Dict[str, List[BiTemporalFact | Dict[str, Any]]]:
        revision_fact = self._coerce_fact(revision)
        revision_interval = self._fact_interval(revision_fact)
        result = {"affected": [], "partial": [], "unaffected": []}

        for fact in original_facts:
            coerced = self._coerce_fact(fact)
            original_interval = self._fact_interval(coerced)
            if self.contains(original_interval, revision_interval):
                result["affected"].append(fact)
            elif self.overlaps(original_interval, revision_interval):
                result["partial"].append(fact)
            else:
                result["unaffected"].append(fact)
        return result

    def normalize_timestamp(self, timestamp: Any, granularity: str) -> datetime:
        granularity = self._validate_granularity(granularity)
        value = parse_temporal_value(timestamp)
        if granularity == "second":
            return value.replace(microsecond=0)
        if granularity == "minute":
            return value.replace(second=0, microsecond=0)
        if granularity == "hour":
            return value.replace(minute=0, second=0, microsecond=0)
        if granularity == "day":
            return value.replace(hour=0, minute=0, second=0, microsecond=0)
        if granularity == "week":
            start_of_week = value - timedelta(days=value.weekday())
            return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        if granularity == "month":
            return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return value.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    def normalize_interval(self, start: Any, end: Any, granularity: str) -> TemporalInterval:
        granularity = self._validate_granularity(granularity)
        normalized_start = self.normalize_timestamp(start, granularity)
        parsed_end = parse_temporal_bound(end, default=TemporalBound.OPEN)
        if parsed_end is TemporalBound.OPEN:
            return TemporalInterval(start=normalized_start, end=TemporalBound.OPEN)
        end_dt = parse_temporal_value(parsed_end)
        normalized_end = self._expand_end(end_dt, granularity)
        return TemporalInterval(start=normalized_start, end=normalized_end)

    def _events_for_fact(self, fact: Dict[str, Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        start = parse_temporal_value(fact.get("valid_from")) if fact.get("valid_from") is not None else None
        end = parse_temporal_bound(fact.get("valid_until"), default=TemporalBound.OPEN)
        recorded_at = parse_temporal_value(fact.get("recorded_at")) if fact.get("recorded_at") is not None else None
        superseded_at = parse_temporal_bound(fact.get("superseded_at"), default=TemporalBound.OPEN)

        if start is not None:
            events.append({"timestamp": start, "change_type": "added", "fact": fact})
        if isinstance(recorded_at, datetime) and (start is None or recorded_at != start):
            events.append({"timestamp": recorded_at, "change_type": "modified", "fact": fact})
        if isinstance(superseded_at, datetime):
            events.append({"timestamp": superseded_at, "change_type": "modified", "fact": fact})
        if isinstance(end, datetime):
            events.append({"timestamp": end, "change_type": "removed", "fact": fact})
        return events

    def _coerce_fact(self, fact: BiTemporalFact | Dict[str, Any]) -> BiTemporalFact:
        if isinstance(fact, BiTemporalFact):
            return fact
        return BiTemporalFact.from_relationship(dict(fact))

    def _fact_interval(self, fact: BiTemporalFact) -> TemporalInterval:
        start = fact.valid_from or datetime.min.replace(tzinfo=timezone.utc)
        end = fact.valid_until if fact.valid_until is not None else TemporalBound.OPEN
        return TemporalInterval(start=start, end=end)

    def _clip_to_domain(
        self,
        intervals: Iterable[TemporalInterval],
        domain: TemporalInterval,
    ) -> List[TemporalInterval]:
        clipped: List[TemporalInterval] = []
        domain_end = self._coerce_datetime(domain.end)
        for interval in intervals:
            candidate = self._validated_copy(interval)
            if not self.overlaps(candidate, domain) and candidate.end != domain.start and candidate.start != domain_end:
                continue
            start = max(candidate.start, domain.start)
            end_dt = min(self._end_as_datetime(candidate.end, domain.end), domain_end)
            if start < end_dt:
                clipped.append(TemporalInterval(start=start, end=end_dt, label=candidate.label))
        return clipped

    def _touches_or_overlaps(self, left: TemporalInterval, right: TemporalInterval) -> bool:
        left_end = self._end_value(left.end)
        return right.start <= left_end

    def _make_interval(self, start: Any, end: Any, *, label: Optional[str] = None) -> TemporalInterval:
        interval = TemporalInterval(
            start=parse_temporal_value(start),
            end=parse_temporal_bound(end, default=TemporalBound.OPEN),
            label=label,
        )
        return self._validated_copy(interval)

    def _validated_copy(self, interval: TemporalInterval) -> TemporalInterval:
        normalized = TemporalInterval(
            start=parse_temporal_value(interval.start),
            end=parse_temporal_bound(interval.end, default=TemporalBound.OPEN),
            label=interval.label,
        )
        self._validate_interval(normalized)
        return normalized

    def _validate_interval(self, interval: TemporalInterval) -> None:
        if isinstance(interval.end, datetime) and interval.start > interval.end:
            raise ValueError("Temporal intervals must satisfy start <= end.")

    def _end_value(self, value: datetime | TemporalBound) -> datetime:
        if value is TemporalBound.OPEN:
            return datetime.max.replace(tzinfo=timezone.utc)
        return self._coerce_datetime(value)

    def _end_as_datetime(self, value: datetime | TemporalBound, fallback: datetime | TemporalBound) -> datetime:
        if value is TemporalBound.OPEN:
            return self._coerce_datetime(fallback)
        return self._coerce_datetime(value)

    def _coerce_datetime(self, value: Any) -> datetime:
        return parse_temporal_value(value)

    def _max_end(self, left: datetime | TemporalBound, right: datetime | TemporalBound) -> datetime | TemporalBound:
        if left is TemporalBound.OPEN or right is TemporalBound.OPEN:
            return TemporalBound.OPEN
        return max(self._coerce_datetime(left), self._coerce_datetime(right))

    def _max_datetime(self, left: datetime, right: datetime) -> datetime:
        return left if left >= right else right

    def _validate_granularity(self, granularity: str) -> str:
        if granularity not in self.SUPPORTED_GRANULARITIES:
            raise ValueError(f"Unsupported temporal granularity: {granularity}")
        return granularity

    def _expand_end(self, value: datetime, granularity: str) -> datetime:
        floor = self.normalize_timestamp(value, granularity)
        if granularity == "second":
            return floor + timedelta(seconds=1) - timedelta(microseconds=1)
        if granularity == "minute":
            return floor + timedelta(minutes=1) - timedelta(microseconds=1)
        if granularity == "hour":
            return floor + timedelta(hours=1) - timedelta(microseconds=1)
        if granularity == "day":
            return floor + timedelta(days=1) - timedelta(microseconds=1)
        if granularity == "week":
            return floor + timedelta(weeks=1) - timedelta(microseconds=1)
        if granularity == "month":
            _, days = calendar.monthrange(floor.year, floor.month)
            return floor.replace(day=days, hour=23, minute=59, second=59, microsecond=999999)
        return floor.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)

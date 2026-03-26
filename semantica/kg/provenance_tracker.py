"""
Provenance Tracker for Knowledge Graph entities.

Tracks the sources and lineage of entities and relationships.
"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ProvenanceTracker:
    """
    Tracks provenance (source lineage) for knowledge graph entities.

    Usage:
        tracker = ProvenanceTracker()
        tracker.track_entity("E1", "doc1.txt", metadata={"type": "file"})
        sources = tracker.get_all_sources("E1")
    """

    def __init__(self):
        self._records: Dict[str, List[Dict[str, Any]]] = {}

    def track_entity(
        self,
        entity_id: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record that entity_id was derived from source."""
        if entity_id not in self._records:
            self._records[entity_id] = []
        entry: Dict[str, Any] = {
            "source": source,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            entry.update(metadata)
        self._records[entity_id].append(entry)

    def get_all_sources(self, entity_id: str) -> List[Dict[str, Any]]:
        """Return all provenance records for entity_id."""
        return self._records.get(entity_id, [])

    def clear(self, entity_id: Optional[str] = None) -> None:
        """Clear provenance records."""
        if entity_id:
            self._records.pop(entity_id, None)
        else:
            self._records.clear()

    def query_recorded_between(
        self, start: Any, end: Any
    ) -> List[Dict[str, Any]]:
        """
        Return all provenance records whose recorded_at falls within [start, end].

        Args:
            start: Start of range — datetime or ISO string (inclusive).
            end: End of range — datetime or ISO string (inclusive).

        Returns:
            Flat list of matching provenance records (each dict includes
            the entity_id under the key "entity_id").
        """
        start_dt = self._parse_dt(start)
        end_dt = self._parse_dt(end)

        results = []
        for entity_id, records in self._records.items():
            for record in records:
                raw = record.get("recorded_at")
                if raw is None:
                    continue
                try:
                    rec_dt = self._parse_dt(raw)
                except (ValueError, TypeError):
                    continue
                if start_dt <= rec_dt <= end_dt:
                    results.append({"entity_id": entity_id, **record})
        return results

    def revision_history(self, fact_id: str) -> List[Dict[str, Any]]:
        """
        Return the complete revision chain for fact_id in ascending recorded_at order.

        Each entry contains at minimum:
            version (int, 1-based), valid_from, valid_until, recorded_at, author
        Optional fields: revision_type, supersedes.

        Returns an empty list for a fact with no recorded provenance.
        """
        records = self._records.get(fact_id, [])
        if not records:
            return []

        # Sort by recorded_at ascending; records without recorded_at sort first
        def sort_key(r: Dict[str, Any]):
            raw = r.get("recorded_at")
            if raw is None:
                return ""
            return raw

        sorted_records = sorted(records, key=sort_key)

        history = []
        for version, record in enumerate(sorted_records, start=1):
            entry: Dict[str, Any] = {
                "version": version,
                "valid_from": record.get("valid_from"),
                "valid_until": record.get("valid_until"),
                "recorded_at": record.get("recorded_at"),
                "author": record.get("author"),
            }
            if "revision_type" in record:
                entry["revision_type"] = record["revision_type"]
            if "supersedes" in record:
                entry["supersedes"] = record["supersedes"]
            history.append(entry)
        return history

    def export_audit_log(self, fact_ids: List[str], format: str = "json") -> str:
        """
        Export audit log for the given fact IDs.

        Args:
            fact_ids: List of fact/entity IDs to include.
            format: "json" or "csv".

        Returns:
            String containing the serialized audit log.
        """
        rows = []
        for fact_id in fact_ids:
            for entry in self.revision_history(fact_id):
                rows.append({"fact_id": fact_id, **entry})

        if format == "json":
            return json.dumps(rows, indent=2, default=str)

        if format == "csv":
            fieldnames = [
                "fact_id", "version", "valid_from", "valid_until",
                "recorded_at", "author", "revision_type", "supersedes",
            ]
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return buf.getvalue()

        raise ValueError(f"Unsupported audit log format: {format!r}. Use 'json' or 'csv'.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dt(value: Any) -> datetime:
        """Parse a datetime or ISO string into an aware datetime (UTC assumed when naive)."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        # String
        s = str(value).strip()
        # Handle trailing 'Z'
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

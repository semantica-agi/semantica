"""
Provenance-enabled wrappers for parsing operations.

Tracks: file parsed, format, structure, parsing method

Usage:
    from semantica.parse.parse_provenance import JSONParserWithProvenance

    parser = JSONParserWithProvenance(provenance=True)
    data = parser.parse("data.json")

Author: Semantica Contributors
License: MIT
"""

from typing import Optional
from datetime import datetime
import uuid


class ParserWithProvenance:
    """Base parser with provenance tracking."""

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **config,
    ):
        from .document_parser import DocumentParser

        self.provenance = provenance
        self._parser = DocumentParser(**config)
        self._prov_manager = None
        self._agent_id = agent_id or self.__class__.__name__
        self._is_automated = is_automated

        if provenance:
            try:
                from semantica.provenance import ProvenanceManager
                self._prov_manager = ProvenanceManager()
            except ImportError:
                self.provenance = False

    def parse(self, file_path: str, **kwargs):
        """Parse file with provenance tracking."""
        activity_started_at_time = datetime.utcnow().isoformat()
        data = self._parser.parse(file_path, **kwargs)
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance and self._prov_manager:
            self._prov_manager.track_entity(
                entity_id=f"parse_{uuid.uuid4().hex[:8]}",
                source=file_path,
                entity_type="parsed_data",
                agent_id=self._agent_id,
                agent_type="software_agent",
                is_automated=self._is_automated,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                metadata={
                    "file_path": file_path,
                    "format": kwargs.get('format', 'unknown')
                }
            )

        return data

    def __getattr__(self, name):
        return getattr(self._parser, name)


__all__ = ['ParserWithProvenance']

"""
Blazegraph Store Module

This module provides Blazegraph integration for RDF storage and SPARQL
querying, enabling connection to Blazegraph instances with namespace
management and bulk loading capabilities.

Key Features:
    - Blazegraph connection and authentication
    - SPARQL query execution
    - Bulk data loading and management
    - Namespace and graph management
    - REST API integration
    - Performance optimization

Main Classes:
    - BlazegraphStore: Main Blazegraph integration store

Example Usage:
    >>> from semantica.triplet_store import BlazegraphStore
    >>> store = BlazegraphStore(endpoint="http://localhost:9999/blazegraph", namespace="kb")
    >>> result = store.execute_sparql(sparql_query)
    >>> load_result = store.bulk_load(triplets)
    >>> namespace_result = store.create_namespace("new_namespace")

Author: Semantica Contributors
License: MIT
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from ..semantic_extract.triplet_extractor import Triplet
from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class BlazegraphStore:
    """
    Blazegraph triplet store backend.

    • Blazegraph connection and authentication
    • SPARQL query execution
    • Bulk data loading and management
    • Namespace and graph management
    • Performance optimization
    • Error handling and recovery
    """

    def __init__(self, endpoint: str, **config):
        """
        Initialize Blazegraph store.

        Args:
            endpoint: Blazegraph endpoint URL
            **config: Additional configuration:
                - namespace: Namespace name (default: "kb")
                - username: Username for authentication
                - password: Password for authentication
                - timeout: Request timeout (default: 30)
        """
        self.logger = get_logger("blazegraph_store")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.endpoint = endpoint.rstrip("/")
        self.namespace = config.get("namespace", "kb")
        self.username = config.get("username")
        self.password = config.get("password")
        self.timeout = config.get("timeout", 30)

        self.connected = False
        self._connect()

    def _connect(self) -> None:
        """Connect to Blazegraph instance."""
        try:
            # Test connection
            sparql_endpoint = self._get_sparql_endpoint()
            response = requests.get(
                sparql_endpoint,
                params={"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"},
                timeout=self.timeout,
                auth=(self.username, self.password)
                if self.username and self.password
                else None,
            )

            if response.status_code == 200:
                self.connected = True
                self.logger.info(f"Connected to Blazegraph: {self.endpoint}")
            else:
                self.logger.warning(
                    f"Blazegraph connection test failed: {response.status_code}"
                )
        except Exception as e:
            self.logger.warning(f"Could not connect to Blazegraph: {e}")

    def _get_sparql_endpoint(self) -> str:
        """Get SPARQL endpoint URL."""
        return urljoin(self.endpoint, f"/blazegraph/namespace/{self.namespace}/sparql")

    def _get_update_endpoint(self) -> str:
        """Get SPARQL Update endpoint URL."""
        return urljoin(self.endpoint, f"/blazegraph/namespace/{self.namespace}/sparql")

    def execute_sparql(self, query: str, **options) -> Dict[str, Any]:
        """
        Execute SPARQL query.

        Args:
            query: SPARQL query string
            **options: Additional options

        Returns:
            Query results
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="triplet_store",
            submodule="BlazegraphStore",
            message="Executing SPARQL query on Blazegraph",
        )

        try:
            if not self.connected:
                self.progress_tracker.stop_tracking(
                    tracking_id, status="failed", message="Not connected to Blazegraph"
                )
                raise ProcessingError("Not connected to Blazegraph")

            sparql_endpoint = self._get_sparql_endpoint()

            self.progress_tracker.update_tracking(
                tracking_id, message="Sending query to Blazegraph endpoint..."
            )
            response = requests.post(
                sparql_endpoint,
                data={"query": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                auth=(self.username, self.password)
                if self.username and self.password
                else None,
            )

            response.raise_for_status()

            # Parse JSON response
            self.progress_tracker.update_tracking(
                tracking_id, message="Parsing query results..."
            )
            result_data = response.json()

            result = {
                "success": True,
                "bindings": result_data.get("results", {}).get("bindings", []),
                "variables": result_data.get("head", {}).get("vars", []),
                "metadata": {"query": query, "endpoint": sparql_endpoint},
            }

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Query executed: {len(result['bindings'])} results",
            )
            return result
        except Exception as e:
            self.logger.error(f"SPARQL query failed: {e}")
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise ProcessingError(f"SPARQL query failed: {e}")

    def bulk_load(self, triplets: List[Triplet], **options) -> Dict[str, Any]:
        """
        Load triplets in bulk.

        Args:
            triplets: List of triplets
            **options: Additional options:
                - format: RDF format (turtle, ntriples, rdfxml)
                - graph: Named graph URI

        Returns:
            Load status
        """
        if not self.connected:
            raise ProcessingError("Not connected to Blazegraph")

        # Convert triplets to RDF format
        format = options.get("format", "turtle")
        rdf_data = self._triplets_to_rdf(triplets, format)

        # Upload endpoint
        upload_endpoint = urljoin(
            self.endpoint, f"/blazegraph/namespace/{self.namespace}/sparql"
        )

        try:
            # Use SPARQL INSERT for bulk loading
            graph = options.get("graph", "")
            graph_clause = f"GRAPH <{graph}>" if graph else ""

            # Build INSERT query
            insert_data = self._build_insert_data(triplets)
            query = f"INSERT DATA {graph_clause} {{ {insert_data} }}"

            response = requests.post(
                upload_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout * 2,  # Longer timeout for bulk operations
                auth=(self.username, self.password)
                if self.username and self.password
                else None,
            )

            response.raise_for_status()

            return {
                "success": True,
                "triplets_loaded": len(triplets),
                "namespace": self.namespace,
            }
        except Exception as e:
            self.logger.error(f"Bulk load failed: {e}")
            raise ProcessingError(f"Bulk load failed: {e}")

    def _triplets_to_rdf(self, triplets: List[Triplet], format: str = "turtle") -> str:
        """Convert triplets to RDF format."""
        if format == "turtle":
            lines = []
            for triplet in triplets:
                lines.append(
                    f"<{triplet.subject}> <{triplet.predicate}> {self._format_object_for_sparql(triplet)} ."
                )
            return "\n".join(lines)
        else:
            # For other formats, use simple turtle conversion
            return self._triplets_to_rdf(triplets, "turtle")

    def _build_insert_data(self, triplets: List[Triplet]) -> str:
        """Build SPARQL INSERT DATA clause."""
        lines = []
        for triplet in triplets:
            lines.append(
                f"<{triplet.subject}> <{triplet.predicate}> {self._format_object_for_sparql(triplet)} ."
            )
        return " ".join(lines)

    # Known prefix expansions for XSD and common RDF vocabularies
    _KNOWN_PREFIXES: Dict[str, str] = {
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "owl": "http://www.w3.org/2002/07/owl#",
        "skos": "http://www.w3.org/2004/02/skos/core#",
    }

    # RFC 5646 language tag: primary subtag optionally followed by '-' + subtags
    _LANG_TAG_RE = re.compile(r"^[a-zA-Z]{1,8}(-[a-zA-Z0-9]{1,8})*$")

    def _format_object_for_sparql(self, triplet: Triplet) -> str:
        """Format triplet object as IRI or literal for SPARQL/N-Triples style syntax."""
        obj = triplet.object
        metadata = triplet.metadata or {}

        if self._is_uri_value(obj):
            if obj.startswith("<") and obj.endswith(">"):
                inner = obj[1:-1]
                if " " in inner or ">" in inner:
                    raise ValueError(f"IRI contains invalid characters: {obj!r}")
                return obj
            return f"<{obj}>"

        escaped = self._escape_literal(obj)
        datatype = metadata.get("datatype") or metadata.get("literal_datatype")
        language = metadata.get("lang") or metadata.get("language")

        if datatype:
            datatype_iri = self._resolve_datatype_iri(datatype)
            return f"\"{escaped}\"^^{datatype_iri}"

        if language:
            if not self._LANG_TAG_RE.match(str(language)):
                raise ValueError(
                    f"Invalid language tag {language!r}: must match RFC 5646 "
                    f"(letters/digits and hyphens only, e.g. 'en', 'en-US')"
                )
            return f"\"{escaped}\"@{language}"

        return f"\"{escaped}\""

    def _resolve_datatype_iri(self, datatype: str) -> str:
        """Expand a datatype string to a validated SPARQL IRI token.

        Accepts:
        - Already-wrapped IRIs: ``<http://...>``
        - Full IRIs:            ``http://...`` / ``https://...`` / ``urn:...``
        - Known prefixed names: ``xsd:integer``, ``rdf:langString``, etc.

        Raises ValueError for anything else.
        """
        datatype = str(datatype)

        # Already angle-bracketed — validate the inner IRI contains no whitespace
        if datatype.startswith("<") and datatype.endswith(">"):
            inner = datatype[1:-1]
            if not inner or re.search(r"[\s<>\"{}|\\^`]", inner):
                raise ValueError(f"Invalid datatype IRI: {datatype!r}")
            return datatype

        # Full absolute IRI without brackets
        parsed = urlparse(datatype)
        if parsed.scheme in {"http", "https", "urn"} and not re.search(r"[\s<>\"{}|\\^`]", datatype):
            return f"<{datatype}>"

        # Prefixed form — expand known prefixes only
        if ":" in datatype:
            prefix, local = datatype.split(":", 1)
            if prefix in self._KNOWN_PREFIXES and re.match(r"^[A-Za-z0-9_\-\.]+$", local):
                return f"<{self._KNOWN_PREFIXES[prefix]}{local}>"

        raise ValueError(
            f"Unsupported datatype {datatype!r}: use a full IRI (http/https/urn), "
            f"an angle-bracketed IRI, or a known prefix (xsd/rdf/rdfs/owl/skos)."
        )

    def _is_uri_value(self, value: str) -> bool:
        """Detect if a value should be serialized as an IRI."""
        if not isinstance(value, str) or not value:
            return False
        if value.startswith("<") and value.endswith(">"):
            return True
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "urn"}:
            return False
        # Reject strings that only look like URIs (e.g. "http not a uri")
        return not re.search(r"\s", value)

    def _escape_literal(self, value: str) -> str:
        """Escape string literal for SPARQL."""
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def add_triplet(self, triplet: Triplet, **options) -> Dict[str, Any]:
        """Add single triplet."""
        return self.bulk_load([triplet], **options)

    def add_triplets(self, triplets: List[Triplet], **options) -> Dict[str, Any]:
        """Add multiple triplets."""
        return self.bulk_load(triplets, **options)

    def get_triplets(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        **options,
    ) -> List[Triplet]:
        """Get triplets matching criteria."""
        # Build SPARQL query
        where_clauses = []
        if subject:
            where_clauses.append(f"?s = <{subject}>")
        if predicate:
            where_clauses.append(f"?p = <{predicate}>")
        if object:
            where_clauses.append(
                f"?o = {self._format_object_for_sparql(Triplet(subject='', predicate='', object=object))}"
            )

        where_clause = " ".join(where_clauses) if where_clauses else ""
        query = f"SELECT ?s ?p ?o WHERE {{ ?s ?p ?o {where_clause} }}"

        result = self.execute_sparql(query, **options)

        # Convert bindings to triplets
        triplets = []
        for binding in result["bindings"]:
            triplets.append(
                Triplet(
                    subject=binding.get("s", {}).get("value", ""),
                    predicate=binding.get("p", {}).get("value", ""),
                    object=binding.get("o", {}).get("value", ""),
                    metadata={"source": "blazegraph"},
                )
            )

        return triplets

    def delete_triplet(self, triplet: Triplet, **options) -> Dict[str, Any]:
        """Delete triplet."""
        if not self.connected:
            raise ProcessingError("Not connected to Blazegraph")

        update_endpoint = self._get_update_endpoint()

        query = (
            f"DELETE DATA {{ <{triplet.subject}> <{triplet.predicate}> "
            f"{self._format_object_for_sparql(triplet)} }}"
        )

        try:
            response = requests.post(
                update_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                auth=(self.username, self.password)
                if self.username and self.password
                else None,
            )

            response.raise_for_status()

            return {"success": True}
        except Exception as e:
            self.logger.error(f"Delete triplet failed: {e}")
            raise ProcessingError(f"Delete triplet failed: {e}")

    def create_namespace(self, namespace: str, **options) -> Dict[str, Any]:
        """
        Create new namespace.

        Args:
            namespace: Namespace name
            **options: Additional options

        Returns:
            Operation status
        """
        # Blazegraph namespace creation via REST API
        create_endpoint = urljoin(self.endpoint, "/blazegraph/namespace")

        try:
            response = requests.post(
                create_endpoint,
                json={"namespace": namespace, **options},
                timeout=self.timeout,
                auth=(self.username, self.password)
                if self.username and self.password
                else None,
            )

            response.raise_for_status()

            return {"success": True, "namespace": namespace}
        except Exception as e:
            self.logger.error(f"Create namespace failed: {e}")
            raise ProcessingError(f"Create namespace failed: {e}")

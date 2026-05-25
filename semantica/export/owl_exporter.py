"""
OWL Exporter Module

This module provides comprehensive OWL (Web Ontology Language) export capabilities
for the Semantica framework, enabling ontology export for semantic modeling.

Key Features:
    - OWL/OWL-XML format export
    - Turtle format export
    - Class definition and hierarchy export
    - Object and data property export
    - OWL 2.0 feature support
    - Ontology validation

Example Usage:
    >>> from semantica.export import OWLExporter
    >>> exporter = OWLExporter(ontology_uri="http://example.org/ontology#")
    >>> exporter.export(ontology, "ontology.owl", format="owl-xml")
    >>> exporter.export_classes(classes, "classes.owl")

Author: Semantica Contributors
License: MIT
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class OWLExporter:
    """
    OWL exporter for semantic modeling and ontology representation.

    This class provides comprehensive OWL export functionality for ontologies,
    including class definitions, hierarchies, and property definitions.

    Features:
        - OWL/OWL-XML format export
        - Turtle format export
        - Class definition and hierarchy export
        - Object and data property export
        - OWL 2.0 feature support
        - Ontology validation

    Example Usage:
        >>> exporter = OWLExporter(
        ...     ontology_uri="http://example.org/ontology#",
        ...     version="1.0",
        ...     format="owl-xml"
        ... )
        >>> exporter.export(ontology, "ontology.owl")
    """

    def __init__(
        self,
        ontology_uri: str = "https://semantica.dev/ontology/",
        version: str = "1.0",
        format: str = "owl-xml",
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize OWL exporter.

        Sets up the exporter with ontology URI, version, and format configuration.

        Args:
            ontology_uri: Base URI for the ontology (default: "https://semantica.dev/ontology/")
            version: Ontology version string (default: "1.0")
            format: Default export format - 'owl-xml' or 'turtle' (default: 'owl-xml')
            config: Optional configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("owl_exporter")
        self.config = config or {}
        self.config.update(kwargs)

        # OWL configuration
        self.ontology_uri = ontology_uri
        self.version = version
        self.format = format

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()

        self.logger.debug(
            f"OWL exporter initialized: uri={ontology_uri}, "
            f"version={version}, format={format}"
        )

    def export(
        self,
        ontology: Dict[str, Any],
        file_path: Union[str, Path],
        format: Optional[str] = None,
        encoding: str = "utf-8",
        **options,
    ) -> None:
        """
        Export ontology to OWL format file.

        This method exports a complete ontology (classes, properties, etc.) to
        OWL format in either OWL-XML or Turtle serialization.

        Supported Formats:
            - "owl-xml": OWL-XML format (RDF/XML-based)
            - "turtle": Turtle format (human-readable)

        Args:
            ontology: Ontology dictionary containing:
                - uri: Ontology URI (optional, uses self.ontology_uri if not provided)
                - name: Ontology name
                - description: Ontology description (optional)
                - version: Ontology version (optional)
                - classes: List of class definitions
                - object_properties: List of object property definitions
                - data_properties: List of data property definitions
            file_path: Output OWL file path
            format: Export format - 'owl-xml' or 'turtle' (default: self.format)
            encoding: File encoding (default: 'utf-8')
            **options: Additional export options

        Raises:
            ValidationError: If format is unsupported

        Example:
            >>> ontology = {
            ...     "name": "MyOntology",
            ...     "classes": [...],
            ...     "object_properties": [...]
            ... }
            >>> exporter.export(ontology, "ontology.owl", format="owl-xml")
        """
        # Track OWL export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="OWLExporter",
            message=f"Exporting ontology to {format or self.format}: {file_path}",
        )

        try:
            file_path = Path(file_path)
            ensure_directory(file_path.parent)

            export_format = format or self.format

            self.logger.debug(
                f"Exporting ontology to {export_format}: {file_path}, "
                f"classes={len(ontology.get('classes', []))}, "
                f"object_properties={len(ontology.get('object_properties', []))}, "
                f"data_properties={len(ontology.get('data_properties', []))}"
            )

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Converting ontology to {export_format}..."
            )
            # Generate OWL content based on format
            if export_format == "owl-xml":
                owl_content = self._export_owl_xml(ontology, **options)
            elif export_format == "turtle":
                owl_content = self._export_owl_turtle(ontology, **options)
            else:
                raise ValidationError(
                    f"Unsupported OWL format: {export_format}. "
                    "Supported formats: owl-xml, turtle"
                )

            self.progress_tracker.update_tracking(
                tracking_id, message="Writing OWL file..."
            )
            # Write OWL file
            with open(file_path, "w", encoding=encoding) as f:
                f.write(owl_content)

            self.logger.info(f"Exported OWL ({export_format}) to: {file_path}")
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Exported OWL ({export_format}) to: {file_path}",
            )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def export_ontology(
        self, ontology: Dict[str, Any], file_path: Union[str, Path], **options
    ) -> None:
        """
        Export complete ontology to OWL.

        Args:
            ontology: Ontology dictionary
            file_path: Output file path
            **options: Additional options
        """
        self.export(ontology, file_path, **options)

    def _export_owl_xml(self, ontology: Dict[str, Any], **options) -> str:
        """
        Export ontology to OWL-XML format.

        OWL-XML is the RDF/XML-based serialization of OWL ontologies. This method
        generates OWL-XML syntax with proper RDF/XML structure.

        Args:
            ontology: Ontology dictionary with classes, properties, etc.
            **options: Additional export options (unused)

        Returns:
            String containing OWL-XML serialization
        """
        ontology_uri = ontology.get("uri") or self.ontology_uri
        ontology_name = ontology.get("name", "SemanticaOntology")
        version = ontology.get("version") or self.version

        lines = ['<?xml version="1.0"?>']
        lines.append('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
        lines.append('         xmlns:owl="http://www.w3.org/2002/07/owl#"')
        lines.append('         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
        lines.append('         xmlns:xsd="http://www.w3.org/2001/XMLSchema#">')
        lines.append("")

        # Ontology declaration
        lines.append(f'  <owl:Ontology rdf:about="{ontology_uri}">')
        lines.append(f"    <rdfs:label>{ontology_name}</rdfs:label>")
        lines.append(f"    <owl:versionInfo>{version}</owl:versionInfo>")
        if ontology.get("description"):
            lines.append(
                f'    <rdfs:comment>{ontology.get("description")}</rdfs:comment>'
            )
        lines.append("  </owl:Ontology>")
        lines.append("")

        # Classes
        classes = ontology.get("classes", [])
        for cls in classes:
            class_uri = cls.get("uri") or cls.get("id", "")
            class_name = cls.get("name") or cls.get("label", "")

            lines.append(f'  <owl:Class rdf:about="{class_uri}">')
            lines.append(f"    <rdfs:label>{class_name}</rdfs:label>")

            if cls.get("comment"):
                lines.append(f'    <rdfs:comment>{cls.get("comment")}</rdfs:comment>')

            # Subclass relationships
            if cls.get("subClassOf"):
                parent = cls.get("subClassOf")
                lines.append(f'    <rdfs:subClassOf rdf:resource="{parent}"/>')

            # Equivalent classes
            if cls.get("equivalentClass"):
                equiv = cls.get("equivalentClass")
                lines.append(f'    <owl:equivalentClass rdf:resource="{equiv}"/>')

            lines.append("  </owl:Class>")
            lines.append("")

        # Object properties
        object_properties = ontology.get("object_properties", [])
        for prop in object_properties:
            prop_uri = prop.get("uri") or prop.get("id", "")
            prop_name = prop.get("name") or prop.get("label", "")

            lines.append(f'  <owl:ObjectProperty rdf:about="{prop_uri}">')
            lines.append(f"    <rdfs:label>{prop_name}</rdfs:label>")

            if prop.get("comment"):
                lines.append(f'    <rdfs:comment>{prop.get("comment")}</rdfs:comment>')

            # Domain
            if prop.get("domain"):
                domain = prop.get("domain")
                if isinstance(domain, list):
                    for d in domain:
                        lines.append(f'    <rdfs:domain rdf:resource="{d}"/>')
                else:
                    lines.append(f'    <rdfs:domain rdf:resource="{domain}"/>')

            # Range
            if prop.get("range"):
                range_val = prop.get("range")
                if isinstance(range_val, list):
                    for r in range_val:
                        lines.append(f'    <rdfs:range rdf:resource="{r}"/>')
                else:
                    lines.append(f'    <rdfs:range rdf:resource="{range_val}"/>')

            lines.append("  </owl:ObjectProperty>")
            lines.append("")

        # Data properties
        data_properties = ontology.get("data_properties", [])
        for prop in data_properties:
            prop_uri = prop.get("uri") or prop.get("id", "")
            prop_name = prop.get("name") or prop.get("label", "")

            lines.append(f'  <owl:DatatypeProperty rdf:about="{prop_uri}">')
            lines.append(f"    <rdfs:label>{prop_name}</rdfs:label>")

            if prop.get("comment"):
                lines.append(f'    <rdfs:comment>{prop.get("comment")}</rdfs:comment>')

            # Domain
            if prop.get("domain"):
                domain = prop.get("domain")
                lines.append(f'    <rdfs:domain rdf:resource="{domain}"/>')

            # Range
            if prop.get("range"):
                range_type = prop.get("range", "xsd:string")
                lines.append(
                    f'    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#{range_type}"/>'
                )

            lines.append("  </owl:DatatypeProperty>")
            lines.append("")

        lines.append("</rdf:RDF>")
        return "\n".join(lines)

    @staticmethod
    def _escape_ttl_str(value: str) -> str:
        """Escape a string value for safe embedding in a Turtle string literal."""
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")

    def _ttl_block(self, subject_uri: str, rdf_type: str, predicates: List[str]) -> str:
        """Build a valid Turtle subject block from accumulated predicate strings."""
        stmt = f"<{subject_uri}> a {rdf_type}"
        for pred in predicates:
            stmt += f" ;\n    {pred}"
        return stmt + " ."

    def _export_owl_turtle(self, ontology: Dict[str, Any], **options) -> str:
        """
        Export ontology to OWL Turtle format.

        Turtle is a human-readable RDF serialization format. This method generates
        OWL ontology in Turtle syntax with namespace declarations and OWL constructs.

        Args:
            ontology: Ontology dictionary with classes, properties, etc.
            **options: Additional export options (unused)

        Returns:
            String containing OWL Turtle serialization
        """
        esc = self._escape_ttl_str
        ontology_uri = ontology.get("uri") or self.ontology_uri
        ontology_name = ontology.get("name", "SemanticaOntology")
        version = ontology.get("version") or self.version

        lines = []

        # Namespace declarations
        lines.append("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
        lines.append("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
        lines.append("@prefix owl: <http://www.w3.org/2002/07/owl#> .")
        lines.append("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
        lines.append(f"@prefix ont: <{ontology_uri}> .")
        lines.append("")

        # Ontology declaration
        onto_predicates = [
            f'rdfs:label "{esc(ontology_name)}"',
            f'owl:versionInfo "{esc(version)}"',
        ]
        description = ontology.get("description")
        if description:
            onto_predicates.append(f'rdfs:comment "{esc(description)}"')
        lines.append(self._ttl_block(ontology_uri, "owl:Ontology", onto_predicates))
        lines.append("")

        # Classes
        for cls in ontology.get("classes", []):
            class_uri = cls.get("uri") or cls.get("id", "")
            class_name = cls.get("name") or cls.get("label", "")
            predicates = [f'rdfs:label "{esc(class_name)}"']
            comment = cls.get("comment")
            if comment:
                predicates.append(f'rdfs:comment "{esc(comment)}"')
            sub_class = cls.get("subClassOf")
            if sub_class:
                predicates.append(f"rdfs:subClassOf <{sub_class}>")
            equiv = cls.get("equivalentClass")
            if equiv:
                predicates.append(f"owl:equivalentClass <{equiv}>")
            lines.append(self._ttl_block(class_uri, "owl:Class", predicates))
            lines.append("")

        # Object properties
        for prop in ontology.get("object_properties", []):
            prop_uri = prop.get("uri") or prop.get("id", "")
            prop_name = prop.get("name") or prop.get("label", "")
            predicates = [f'rdfs:label "{esc(prop_name)}"']
            comment = prop.get("comment")
            if comment:
                predicates.append(f'rdfs:comment "{esc(comment)}"')
            domain = prop.get("domain")
            if domain:
                if isinstance(domain, list):
                    for d in domain:
                        predicates.append(f"rdfs:domain <{d}>")
                else:
                    predicates.append(f"rdfs:domain <{domain}>")
            range_val = prop.get("range")
            if range_val:
                if isinstance(range_val, list):
                    for r in range_val:
                        predicates.append(f"rdfs:range <{r}>")
                else:
                    predicates.append(f"rdfs:range <{range_val}>")
            lines.append(self._ttl_block(prop_uri, "owl:ObjectProperty", predicates))
            lines.append("")

        # Data properties
        for prop in ontology.get("data_properties", []):
            prop_uri = prop.get("uri") or prop.get("id", "")
            prop_name = prop.get("name") or prop.get("label", "")
            predicates = [f'rdfs:label "{esc(prop_name)}"']
            comment = prop.get("comment")
            if comment:
                predicates.append(f'rdfs:comment "{esc(comment)}"')
            domain = prop.get("domain")
            if domain:
                predicates.append(f"rdfs:domain <{domain}>")
            range_type = prop.get("range")
            if range_type:
                predicates.append(f"rdfs:range xsd:{range_type}")
            lines.append(self._ttl_block(prop_uri, "owl:DatatypeProperty", predicates))
            lines.append("")

        return "\n".join(lines)

    def export_classes(
        self,
        classes: List[Dict[str, Any]],
        file_path: Union[str, Path],
        ontology_uri: Optional[str] = None,
        ontology_name: str = "SemanticaOntology",
        **options,
    ) -> None:
        """
        Export class definitions to OWL format.

        This method exports a list of class definitions to OWL format, creating
        a minimal ontology containing only the classes.

        Args:
            classes: List of class definition dictionaries with fields:
                - uri/id: Class URI/identifier
                - name/label: Class name/label
                - comment: Class description (optional)
                - subClassOf: Parent class URI (optional)
                - equivalentClass: Equivalent class URI (optional)
            file_path: Output OWL file path
            ontology_uri: Ontology URI (default: self.ontology_uri)
            ontology_name: Ontology name (default: "SemanticaOntology")
            **options: Additional options passed to export()

        Example:
            >>> classes = [
            ...     {"uri": "http://example.org/Person", "name": "Person"},
            ...     {"uri": "http://example.org/Organization", "name": "Organization"}
            ... ]
            >>> exporter.export_classes(classes, "classes.owl")
        """
        ontology = {
            "classes": classes,
            "uri": ontology_uri or self.ontology_uri,
            "name": ontology_name,
        }
        self.export(ontology, file_path, **options)

    def export_properties(
        self,
        properties: List[Dict[str, Any]],
        file_path: Union[str, Path],
        property_type: str = "object",
        ontology_uri: Optional[str] = None,
        ontology_name: str = "SemanticaOntology",
        **options,
    ) -> None:
        """
        Export property definitions to OWL format.

        This method exports a list of property definitions (object or data properties)
        to OWL format, creating a minimal ontology containing only the properties.

        Args:
            properties: List of property definition dictionaries with fields:
                - uri/id: Property URI/identifier
                - name/label: Property name/label
                - comment: Property description (optional)
                - domain: Domain class URI(s) (optional)
                - range: Range class URI or datatype (optional)
            file_path: Output OWL file path
            property_type: Property type - 'object' or 'data' (default: 'object')
            ontology_uri: Ontology URI (default: self.ontology_uri)
            ontology_name: Ontology name (default: "SemanticaOntology")
            **options: Additional options passed to export()

        Raises:
            ValidationError: If property_type is invalid

        Example:
            >>> properties = [
            ...     {
            ...         "uri": "http://example.org/hasName",
            ...         "name": "hasName",
            ...         "domain": "http://example.org/Person",
            ...         "range": "http://www.w3.org/2001/XMLSchema#string"
            ...     }
            ... ]
            >>> exporter.export_properties(properties, "properties.owl", property_type="data")
        """
        if property_type not in ["object", "data"]:
            raise ValidationError(
                f"Invalid property_type: {property_type}. "
                "Must be 'object' or 'data'."
            )

        ontology = {"uri": ontology_uri or self.ontology_uri, "name": ontology_name}

        # Add properties based on type
        if property_type == "object":
            ontology["object_properties"] = properties
        else:
            ontology["data_properties"] = properties

        self.export(ontology, file_path, **options)

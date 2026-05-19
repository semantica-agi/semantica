"""
XML Ingestion Module

This module provides dedicated XML ingestion for local XML files and directories.
It parses XML into structured dictionaries, extracts namespaces, element hierarchy,
attributes, and document metadata, and can optionally validate documents with XSD
schemas or DTD declarations.

Example Usage:
    >>> from semantica.ingest import XMLIngestor
    >>> ingestor = XMLIngestor()
    >>> data = ingestor.ingest_file("catalog.xml")
    >>> data.root_tag
    'catalog'
    >>> data.metadata["element_count"]
    12
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from lxml import etree

from ..utils.constants import FILE_SIZE_LIMITS
from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


@dataclass
class XMLIngestionData:
    """Structured XML ingestion result."""

    root: Dict[str, Any]
    elements: List[Dict[str, Any]]
    namespaces: Dict[str, str]
    source_path: str
    root_tag: str
    validation: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=datetime.now)


class XMLIngestor:
    """
    Dedicated XML file ingestion handler.

    Features:
        - XML parsing into nested and flat structures
        - Namespace and prefix extraction
        - Element and attribute metadata extraction
        - Optional XSD schema validation
        - Optional DTD validation
        - Directory ingestion for local XML files
    """

    SUPPORTED_EXTENSIONS = {".xml"}

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize XML ingestor.

        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration values
        """
        self.logger = get_logger("xml_ingestor")
        self.config = config or {}
        self.config.update(kwargs)
        self.progress_tracker = get_progress_tracker()
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.debug("XML ingestor initialized")

    def ingest(
        self, source: Union[str, Path], **options
    ) -> Union[XMLIngestionData, List[XMLIngestionData]]:
        """
        Ingest an XML file or directory.

        Args:
            source: XML file or directory path
            **options: Additional ingestion options

        Returns:
            XMLIngestionData for a file, or a list for a directory
        """
        source_path = Path(source)
        if source_path.is_dir():
            return self.ingest_directory(source_path, **options)
        return self.ingest_file(source_path, **options)

    def ingest_file(self, file_path: Union[str, Path], **options) -> XMLIngestionData:
        """
        Ingest and parse a single XML file.

        Args:
            file_path: Path to an XML file
            **options: Ingestion options:
                - schema_path/xsd_path/schema: Optional XSD schema file or XML string
                - validate_schema: Validate against XSD when schema is provided
                - validate_dtd: Validate against document DTD
                - fail_on_validation_error: Raise on validation failure (default: True)
                - include_tree: Include nested tree in result root (default: True)
                - include_elements: Include flat element list (default: True)
                - recover: Let lxml recover malformed XML when possible (default: False)
                - include_comments: Include XML comments in the tree (default: False)

        Returns:
            XMLIngestionData: Parsed XML data and metadata
        """
        file_path = Path(file_path)
        self._validate_file(file_path)

        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="ingest",
            submodule="XMLIngestor",
            message=f"Ingesting XML: {file_path.name}",
        )

        try:
            xml_bytes = file_path.read_bytes()
            data = self._ingest_bytes(
                xml_bytes,
                source=str(file_path),
                source_type="file",
                file_path=file_path,
                **options,
            )

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested XML: {file_path.name}",
            )
            return data

        except (ValidationError, ProcessingError):
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message="XML ingestion failed"
            )
            raise
        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            self.logger.error(f"Failed to ingest XML {file_path}: {exc}")
            raise ProcessingError(f"Failed to ingest XML: {exc}") from exc

    def ingest_string(
        self,
        xml_content: Union[str, bytes],
        source: str = "string",
        **options,
    ) -> XMLIngestionData:
        """
        Ingest XML content from a string or bytes object.

        Args:
            xml_content: XML content
            source: Source label to include in metadata
            **options: Additional ingestion options

        Returns:
            XMLIngestionData: Parsed XML data and metadata
        """
        if isinstance(xml_content, str):
            xml_bytes = xml_content.encode(options.get("encoding", "utf-8"))
        else:
            xml_bytes = xml_content

        return self._ingest_bytes(
            xml_bytes,
            source=source,
            source_type="string",
            file_path=None,
            **options,
        )

    def ingest_directory(
        self,
        directory_path: Union[str, Path],
        recursive: bool = True,
        **options,
    ) -> List[XMLIngestionData]:
        """
        Ingest XML files from a directory.

        Args:
            directory_path: Directory path
            recursive: Whether to search subdirectories
            **options: Additional ingestion options

        Returns:
            List[XMLIngestionData]: Parsed XML files
        """
        directory_path = Path(directory_path)
        if not directory_path.exists():
            raise ValidationError(f"XML directory not found: {directory_path}")
        if not directory_path.is_dir():
            raise ValidationError(f"Path is not a directory: {directory_path}")

        tracking_id = self.progress_tracker.start_tracking(
            file=str(directory_path),
            module="ingest",
            submodule="XMLIngestor",
            message=f"Ingesting XML directory: {directory_path.name}",
        )

        try:
            xml_files = self._xml_files(directory_path, recursive=recursive)
            results = []

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Processing {len(xml_files)} XML files"
            )

            for index, xml_file in enumerate(xml_files, 1):
                try:
                    results.append(self.ingest_file(xml_file, **options))
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=index,
                        total=len(xml_files),
                        message=f"Processing {index}/{len(xml_files)}: {xml_file.name}",
                    )
                except Exception as exc:
                    self.logger.error(f"Failed to ingest XML file {xml_file}: {exc}")
                    if self.config.get("fail_fast", False) or options.get(
                        "fail_fast", False
                    ):
                        raise ProcessingError(
                            f"Failed to ingest XML file: {exc}"
                        ) from exc

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Ingested {len(results)} XML files",
            )
            return results

        except Exception as exc:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(exc)
            )
            raise

    def validate_file(
        self,
        file_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
        validate_dtd: bool = False,
        **options,
    ) -> Dict[str, Any]:
        """
        Validate an XML file and return a validation report.

        Args:
            file_path: XML file path
            schema_path: Optional XSD schema path
            validate_dtd: Whether to validate document DTD
            **options: Additional parser options

        Returns:
            Dict[str, Any]: Validation report
        """
        if schema_path is not None:
            options["schema_path"] = schema_path

        schema_source = self._schema_source(options)
        options.setdefault("validate_schema", schema_source is not None)
        options["validate_dtd"] = validate_dtd
        options["fail_on_validation_error"] = False
        options.setdefault("include_tree", False)
        options.setdefault("include_elements", False)

        return self.ingest_file(file_path, **options).validation

    def extract_metadata(
        self, file_path: Union[str, Path], **options
    ) -> Dict[str, Any]:
        """
        Extract XML document metadata without requiring callers to inspect the tree.

        Args:
            file_path: XML file path
            **options: Additional ingestion options

        Returns:
            Dict[str, Any]: XML metadata
        """
        options.setdefault("include_tree", False)
        options.setdefault("include_elements", False)
        return self.ingest_file(file_path, **options).metadata

    def _ingest_bytes(
        self,
        xml_bytes: bytes,
        source: str,
        source_type: str,
        file_path: Optional[Path],
        **options,
    ) -> XMLIngestionData:
        tree, parser_errors = self._parse_tree(xml_bytes, source, options)
        validation = self._validate_tree(tree, source, options)

        root = tree.getroot()
        namespaces = self._collect_namespaces(root)
        prefix_by_namespace = self._prefix_by_namespace(namespaces)
        root_data, elements, structure_metadata = self._build_structures(
            root,
            namespaces=namespaces,
            prefix_by_namespace=prefix_by_namespace,
            options=options,
        )

        metadata = self._document_metadata(
            tree=tree,
            source=source,
            source_type=source_type,
            file_path=file_path,
            namespaces=namespaces,
            structure_metadata=structure_metadata,
            validation=validation,
            parser_errors=parser_errors,
        )

        return XMLIngestionData(
            root=root_data,
            elements=elements,
            namespaces=namespaces,
            source_path=source,
            root_tag=root_data["tag"],
            validation=validation,
            metadata=metadata,
        )

    def _parse_tree(
        self, xml_bytes: bytes, source: str, options: Dict[str, Any]
    ) -> Tuple[Any, List[str]]:
        validate_dtd = bool(
            options.get("validate_dtd", self.config.get("validate_dtd", False))
        )
        parser = etree.XMLParser(
            remove_blank_text=bool(
                options.get(
                    "remove_blank_text", self.config.get("remove_blank_text", True)
                )
            ),
            remove_comments=not bool(options.get("include_comments", False)),
            resolve_entities=False,
            no_network=not bool(options.get("allow_network", False)),
            load_dtd=bool(options.get("load_dtd", validate_dtd)),
            dtd_validation=False,
            recover=bool(options.get("recover", self.config.get("recover", False))),
            huge_tree=bool(
                options.get("huge_tree", self.config.get("huge_tree", False))
            ),
        )

        try:
            tree = etree.parse(io.BytesIO(xml_bytes), parser)
        except etree.XMLSyntaxError as exc:
            message = self._format_xml_error(exc)
            raise ProcessingError(f"Malformed XML in {source}: {message}") from exc

        parser_errors = [str(error) for error in parser.error_log]
        return tree, parser_errors

    def _validate_tree(
        self, tree: Any, source: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        schema_source = self._schema_source(options)
        validate_schema_option = options.get("validate_schema")
        validate_schema = (
            schema_source is not None
            if validate_schema_option is None
            else bool(validate_schema_option)
        )
        validate_dtd = bool(
            options.get("validate_dtd", self.config.get("validate_dtd", False))
        )
        fail_on_error = bool(options.get("fail_on_validation_error", True))

        validation = {
            "is_valid": True,
            "schema": {
                "validated": False,
                "valid": None,
                "source": self._schema_label(schema_source),
                "errors": [],
            },
            "dtd": {
                "validated": False,
                "valid": None,
                "name": None,
                "system_url": None,
                "public_id": None,
                "errors": [],
            },
        }

        if validate_schema:
            if schema_source is None:
                raise ValidationError(
                    "XML schema validation requested but no XSD schema was provided",
                    validation_context={"source": source},
                )

            schema = self._load_schema(schema_source)
            schema_valid = schema.validate(tree)
            schema_errors = [str(error) for error in schema.error_log]
            validation["schema"].update(
                {
                    "validated": True,
                    "valid": schema_valid,
                    "errors": schema_errors,
                }
            )
            validation["is_valid"] = validation["is_valid"] and schema_valid

            if not schema_valid and fail_on_error:
                raise ValidationError(
                    self._validation_message(
                        "XML schema validation failed", source, schema_errors
                    ),
                    validation_context={"source": source},
                    errors=schema_errors,
                )

        if validate_dtd:
            dtd = tree.docinfo.internalDTD or tree.docinfo.externalDTD
            if dtd is None:
                dtd_valid = False
                dtd_errors = ["No DTD declaration found in XML document."]
            else:
                dtd_valid = dtd.validate(tree)
                dtd_errors = [str(error) for error in dtd.error_log]
                validation["dtd"].update(
                    {
                        "name": getattr(dtd, "name", None),
                        "system_url": getattr(dtd, "system_url", None),
                        "public_id": getattr(dtd, "public_id", None),
                    }
                )

            validation["dtd"].update(
                {"validated": True, "valid": dtd_valid, "errors": dtd_errors}
            )
            validation["is_valid"] = validation["is_valid"] and dtd_valid

            if not dtd_valid and fail_on_error:
                raise ValidationError(
                    self._validation_message(
                        "XML DTD validation failed", source, dtd_errors
                    ),
                    validation_context={"source": source},
                    errors=dtd_errors,
                )

        return validation

    def _build_structures(
        self,
        root: Any,
        namespaces: Dict[str, str],
        prefix_by_namespace: Dict[str, str],
        options: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
        elements: List[Dict[str, Any]] = []
        stats = {
            "element_count": 0,
            "attribute_count": 0,
            "max_depth": 0,
            "tag_counts": {},
            "element_limit_reached": False,
        }

        root_data = self._element_to_dict(
            root,
            parent_path="",
            depth=0,
            namespaces=namespaces,
            prefix_by_namespace=prefix_by_namespace,
            elements=elements,
            stats=stats,
            options=options,
        )

        unique_tags = sorted(stats["tag_counts"].keys())
        metadata = {
            "element_count": stats["element_count"],
            "attribute_count": stats["attribute_count"],
            "max_depth": stats["max_depth"],
            "unique_tags": unique_tags,
            "tag_counts": stats["tag_counts"],
            "flat_element_count": len(elements),
            "element_limit_reached": stats["element_limit_reached"],
        }

        return root_data, elements, metadata

    def _element_to_dict(
        self,
        element: Any,
        parent_path: str,
        depth: int,
        namespaces: Dict[str, str],
        prefix_by_namespace: Dict[str, str],
        elements: List[Dict[str, Any]],
        stats: Dict[str, Any],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        tag_info = self._name_info(element.tag, prefix_by_namespace)
        path = (
            f"{parent_path}/{tag_info['tag']}" if parent_path else f"/{tag_info['tag']}"
        )
        attributes, attribute_details = self._attributes_to_dict(
            element.attrib,
            prefix_by_namespace,
        )
        text = element.text or ""
        if options.get("strip_text", True):
            text = text.strip()

        child_elements = [child for child in element if isinstance(child.tag, str)]

        element_data = {
            "tag": tag_info["tag"],
            "local_name": tag_info["local_name"],
            "namespace": tag_info["namespace"],
            "prefix": tag_info["prefix"],
            "text": text,
            "attributes": attributes,
            "attribute_details": attribute_details,
            "path": path,
            "depth": depth,
            "child_count": len(child_elements),
        }

        stats["element_count"] += 1
        stats["attribute_count"] += len(attributes)
        stats["max_depth"] = max(stats["max_depth"], depth)
        stats["tag_counts"][tag_info["tag"]] = (
            stats["tag_counts"].get(tag_info["tag"], 0) + 1
        )

        if options.get("include_elements", True):
            max_elements = options.get("max_elements")
            if max_elements is None or len(elements) < max_elements:
                flat_element = dict(element_data)
                flat_element.pop("children", None)
                elements.append(flat_element)
            else:
                stats["element_limit_reached"] = True

        children = [
            self._element_to_dict(
                child,
                parent_path=path,
                depth=depth + 1,
                namespaces=namespaces,
                prefix_by_namespace=prefix_by_namespace,
                elements=elements,
                stats=stats,
                options=options,
            )
            for child in child_elements
        ]

        if options.get("include_tree", True):
            element_data["children"] = children

        return element_data

    def _attributes_to_dict(
        self, attributes: Dict[str, str], prefix_by_namespace: Dict[str, str]
    ) -> Tuple[Dict[str, str], Dict[str, Dict[str, Optional[str]]]]:
        values = {}
        details = {}

        for raw_name, value in attributes.items():
            name_info = self._name_info(raw_name, prefix_by_namespace)
            display_name = name_info["tag"]
            values[display_name] = value
            details[display_name] = {
                "value": value,
                "local_name": name_info["local_name"],
                "namespace": name_info["namespace"],
                "prefix": name_info["prefix"],
            }

        return values, details

    def _name_info(
        self, raw_name: Any, prefix_by_namespace: Dict[str, str]
    ) -> Dict[str, Optional[str]]:
        if not isinstance(raw_name, str):
            return {
                "tag": str(raw_name),
                "local_name": str(raw_name),
                "namespace": None,
                "prefix": None,
            }

        if raw_name.startswith("{"):
            qname = etree.QName(raw_name)
            namespace = qname.namespace
            local_name = qname.localname
        else:
            namespace = None
            local_name = raw_name

        prefix = prefix_by_namespace.get(namespace) if namespace else None
        if namespace == XML_NAMESPACE:
            prefix = "xml"

        if prefix and prefix != "default":
            tag = f"{prefix}:{local_name}"
        else:
            tag = local_name

        return {
            "tag": tag,
            "local_name": local_name,
            "namespace": namespace,
            "prefix": prefix,
        }

    def _collect_namespaces(self, root: Any) -> Dict[str, str]:
        namespaces: Dict[str, str] = {}

        for element in root.iter():
            if not isinstance(element.tag, str):
                continue

            for prefix, uri in (element.nsmap or {}).items():
                if not uri:
                    continue
                key = prefix or "default"
                self._add_namespace(namespaces, key, uri)

            for raw_name in element.attrib:
                if isinstance(raw_name, str) and raw_name.startswith(
                    f"{{{XML_NAMESPACE}}}"
                ):
                    self._add_namespace(namespaces, "xml", XML_NAMESPACE)

        return namespaces

    def _add_namespace(self, namespaces: Dict[str, str], prefix: str, uri: str) -> None:
        if prefix not in namespaces:
            namespaces[prefix] = uri
            return

        if namespaces[prefix] == uri:
            return

        index = 2
        while f"{prefix}_{index}" in namespaces:
            index += 1
        namespaces[f"{prefix}_{index}"] = uri

    def _prefix_by_namespace(self, namespaces: Dict[str, str]) -> Dict[str, str]:
        prefix_by_namespace: Dict[str, str] = {}
        for prefix, uri in namespaces.items():
            prefix_by_namespace.setdefault(uri, prefix)
        return prefix_by_namespace

    def _document_metadata(
        self,
        tree: Any,
        source: str,
        source_type: str,
        file_path: Optional[Path],
        namespaces: Dict[str, str],
        structure_metadata: Dict[str, Any],
        validation: Dict[str, Any],
        parser_errors: List[str],
    ) -> Dict[str, Any]:
        root = tree.getroot()
        docinfo = tree.docinfo
        has_dtd = bool(docinfo.internalDTD or docinfo.externalDTD)
        prefix_by_namespace = self._prefix_by_namespace(namespaces)
        root_info = self._name_info(root.tag, prefix_by_namespace)

        metadata = {
            "format": "xml",
            "source": source,
            "source_type": source_type,
            "root_tag": root_info["tag"],
            "root_element": root_info["local_name"],
            "root_namespace": root_info["namespace"],
            "root_prefix": root_info["prefix"],
            "namespace_count": len(namespaces),
            "namespaces": namespaces,
            "has_dtd": has_dtd,
            "dtd_name": docinfo.root_name,
            "dtd_system_url": docinfo.system_url,
            "dtd_public_id": docinfo.public_id,
            "xml_version": docinfo.xml_version,
            "encoding": docinfo.encoding,
            "parser_errors": parser_errors,
            "schema_validated": validation["schema"]["validated"],
            "dtd_validated": validation["dtd"]["validated"],
            "validation_passed": validation["is_valid"],
            **structure_metadata,
        }

        if file_path is not None:
            metadata.update(
                {
                    "file": str(file_path),
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "extension": file_path.suffix,
                }
            )

        return metadata

    def _schema_source(self, options: Dict[str, Any]) -> Any:
        return (
            options.get("schema_path")
            or options.get("xsd_path")
            or options.get("schema")
            or self.config.get("schema_path")
            or self.config.get("xsd_path")
            or self.config.get("schema")
        )

    def _schema_label(self, schema_source: Any) -> Optional[str]:
        if schema_source is None:
            return None
        if isinstance(schema_source, (str, Path)):
            text = str(schema_source)
            if text.lstrip().startswith("<"):
                return "inline"
            return text
        return type(schema_source).__name__

    def _load_schema(self, schema_source: Any) -> Any:
        if isinstance(schema_source, etree.XMLSchema):
            return schema_source

        parser = etree.XMLParser(resolve_entities=False, no_network=True)

        if isinstance(schema_source, Path):
            if not schema_source.exists():
                raise ValidationError(f"XSD schema file not found: {schema_source}")
            schema_doc = etree.parse(str(schema_source), parser)
            return etree.XMLSchema(schema_doc)

        if isinstance(schema_source, bytes):
            schema_doc = etree.fromstring(schema_source, parser)
            return etree.XMLSchema(schema_doc)

        if isinstance(schema_source, str):
            if schema_source.lstrip().startswith("<"):
                schema_doc = etree.fromstring(schema_source.encode("utf-8"), parser)
                return etree.XMLSchema(schema_doc)

            schema_path = Path(schema_source)
            if not schema_path.exists():
                raise ValidationError(f"XSD schema file not found: {schema_source}")
            schema_doc = etree.parse(str(schema_path), parser)
            return etree.XMLSchema(schema_doc)

        raise ValidationError(
            f"Unsupported XSD schema source: {type(schema_source).__name__}"
        )

    def _validation_message(self, prefix: str, source: str, errors: List[str]) -> str:
        first_error = errors[0] if errors else "No detailed validation error available."
        return f"{prefix} for {source}: {first_error}"

    def _format_xml_error(self, exc: etree.XMLSyntaxError) -> str:
        if exc.error_log:
            return str(exc.error_log.last_error)
        return str(exc)

    def _validate_file(self, file_path: Path) -> None:
        if not file_path.exists():
            raise ValidationError(f"XML file not found: {file_path}")
        if not file_path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}")
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValidationError(f"File is not an XML file: {file_path}")

        max_size = FILE_SIZE_LIMITS.get("MAX_DOCUMENT_SIZE", 104857600)
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise ValidationError(
                f"File size {file_size:,} bytes exceeds maximum {max_size:,} bytes "
                f"({file_path.name})"
            )

    def _xml_files(self, directory_path: Path, recursive: bool) -> List[Path]:
        iterator = directory_path.rglob("*") if recursive else directory_path.iterdir()
        return sorted(
            path
            for path in iterator
            if path.is_file() and path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        )

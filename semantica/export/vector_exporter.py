"""
Vector Exporter Module

This module provides comprehensive vector embedding export capabilities for the
Semantica framework, enabling export to various formats for vector stores and
embedding systems.

Key Features:
    - Multiple vector format export (JSON, NumPy, Binary, FAISS)
    - Vector store integration (Weaviate, Qdrant, FAISS)
    - Metadata and document association
    - Batch vector export
    - Multi-dimensional vector support

Example Usage:
    >>> from semantica.export import VectorExporter
    >>> exporter = VectorExporter(format="json", include_metadata=True)
    >>> exporter.export(vectors, "vectors.json")
    >>> exporter.export_for_vector_store(vectors, "weaviate.json", vector_store_type="weaviate")

Author: Semantica Contributors
License: MIT
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from ..utils.exceptions import ProcessingError, ValidationError
from ..utils.helpers import ensure_directory, write_json_file
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker


class VectorExporter:
    """
    Vector exporter for embeddings and vector data.

    This class provides comprehensive vector embedding export functionality for
    various formats and vector store systems.

    Features:
        - Multiple vector format export (JSON, NumPy, Binary, FAISS)
        - Vector store integration (Weaviate, Qdrant, FAISS)
        - Metadata and document association
        - Batch vector export
        - Multi-dimensional vector support

    Example Usage:
        >>> exporter = VectorExporter(
        ...     format="json",
        ...     include_metadata=True,
        ...     include_text=True
        ... )
        >>> exporter.export(vectors, "vectors.json")
    """

    def __init__(
        self,
        format: str = "json",
        include_metadata: bool = True,
        include_text: bool = True,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize vector exporter.

        Sets up the exporter with specified format and inclusion options.

        Args:
            format: Default export format - 'json', 'numpy', 'binary', or 'faiss'
                   (default: 'json')
            include_metadata: Whether to include metadata in export (default: True)
            include_text: Whether to include original text in export (default: True)
            config: Optional configuration dictionary (merged with kwargs)
            **kwargs: Additional configuration options
        """
        self.logger = get_logger("vector_exporter")
        self.config = config or {}
        self.config.update(kwargs)

        # Vector export configuration
        self.format = format
        self.include_metadata = include_metadata
        self.include_text = include_text

        # Initialize progress tracker
        self.progress_tracker = get_progress_tracker()

        self.logger.debug(
            f"Vector exporter initialized: format={format}, "
            f"include_metadata={include_metadata}, include_text={include_text}"
        )

    def export(
        self,
        vectors: Union[List[Dict[str, Any]], Dict[str, Any]],
        file_path: Union[str, Path],
        format: Optional[str] = None,
        **options,
    ) -> None:
        """
        Export vectors to file in specified format.

        This method exports vector embeddings to various formats suitable for
        different use cases (JSON for human-readable, NumPy for Python, FAISS for
        similarity search, etc.).

        Supported Formats:
            - "json": JSON format (human-readable, includes metadata)
            - "numpy": NumPy compressed format (.npz)
            - "binary": Binary format (raw float32 array)
            - "faiss": FAISS index format (for similarity search)

        Args:
            vectors: Vector data:
                - List of dicts: Each dict with 'id', 'vector', 'text', 'metadata'
                - Dict: With 'vectors' key containing list, and optional 'metadata'
            file_path: Output file path
            format: Export format - 'json', 'numpy', 'binary', or 'faiss'
                   (default: self.format)
            **options: Additional format-specific options

        Raises:
            ValidationError: If format is unsupported

        Example:
            >>> vectors = [
            ...     {"id": "v1", "vector": [0.1, 0.2, ...], "text": "text1"},
            ...     {"id": "v2", "vector": [0.3, 0.4, ...], "text": "text2"}
            ... ]
            >>> exporter.export(vectors, "vectors.json", format="json")
        """
        # Track vector export
        tracking_id = self.progress_tracker.start_tracking(
            file=str(file_path),
            module="export",
            submodule="VectorExporter",
            message=f"Exporting vectors to {format or self.format}: {file_path}",
        )

        try:
            file_path = Path(file_path)
            ensure_directory(file_path.parent)

            export_format = format or self.format

            self.logger.debug(
                f"Exporting vectors to {export_format}: {file_path}, "
                f"include_metadata={self.include_metadata}, include_text={self.include_text}"
            )

            self.progress_tracker.update_tracking(
                tracking_id, message="Normalizing input data..."
            )
            # Normalize input data
            if isinstance(vectors, dict):
                vector_list = vectors.get("vectors", [])
                metadata = vectors.get("metadata", {})
            else:
                vector_list = vectors
                metadata = {}

            self.progress_tracker.update_tracking(
                tracking_id, message=f"Exporting in {export_format} format..."
            )
            # Export based on format
            if export_format == "json":
                self._export_json(vector_list, file_path, metadata, **options)
            elif export_format == "numpy":
                self._export_numpy(vector_list, file_path, **options)
            elif export_format == "binary":
                self._export_binary(vector_list, file_path, **options)
            elif export_format == "faiss":
                self._export_faiss(vector_list, file_path, **options)
            else:
                raise ValidationError(
                    f"Unsupported vector format: {export_format}. "
                    "Supported formats: json, numpy, binary, faiss"
                )

            self.logger.info(f"Exported vectors ({export_format}) to: {file_path}")
            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Exported vectors ({export_format}) to: {file_path}",
            )

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

    def export_embeddings(
        self,
        embeddings: List[Dict[str, Any]],
        file_path: Union[str, Path],
        format: Optional[str] = None,
        **options,
    ) -> None:
        """
        Export embeddings to file.

        Args:
            embeddings: List of embedding dictionaries with 'id', 'vector', 'text', etc.
            file_path: Output file path
            format: Export format
            **options: Additional options
        """
        self.export(embeddings, file_path, format=format, **options)

    def _export_json(
        self,
        vectors: List[Dict[str, Any]],
        file_path: Path,
        metadata: Dict[str, Any],
        **options,
    ) -> None:
        """
        Export vectors to JSON format.

        This method exports vectors to JSON format with metadata, text, and
        vector data. Suitable for human-readable export and integration with
        systems that consume JSON.

        Args:
            vectors: List of vector dictionaries
            file_path: Output JSON file path
            metadata: Additional metadata to include in export
            **options: Additional options (unused)
        """
        export_data = {
            "vectors": [],
            "metadata": {"vector_count": len(vectors), "dimension": None, **metadata},
        }

        for vec_data in vectors:
            vector_entry = {
                "id": vec_data.get("id") or vec_data.get("vector_id", ""),
                "vector": vec_data.get("vector") or vec_data.get("embedding", []),
            }

            # Add text if requested and available
            if self.include_text and "text" in vec_data:
                vector_entry["text"] = vec_data["text"]

            # Add metadata if requested and available
            if self.include_metadata and "metadata" in vec_data:
                vector_entry["metadata"] = vec_data["metadata"]

            # Determine dimension from first vector
            vector = vector_entry["vector"]
            if isinstance(vector, list) and len(vector) > 0:
                if export_data["metadata"]["dimension"] is None:
                    export_data["metadata"]["dimension"] = len(vector)

            export_data["vectors"].append(vector_entry)

        write_json_file(export_data, file_path, indent=2)

        self.logger.debug(
            f"Exported {len(vectors)} vector(s) to JSON: "
            f"dimension={export_data['metadata']['dimension']}"
        )

    def _export_numpy(
        self, vectors: List[Dict[str, Any]], file_path: Path, **options
    ) -> None:
        """
        Export vectors to NumPy format.

        This method exports vectors to NumPy compressed format (.npz) with
        optional text and metadata arrays. Also saves metadata as separate JSON.

        Args:
            vectors: List of vector dictionaries
            file_path: Output .npz file path
            **options: Additional options (unused)

        Raises:
            ImportError: If NumPy is not installed
            ValidationError: If no vectors to export
        """
        try:
            import numpy as np
        except (ImportError, OSError):
            raise ImportError("NumPy not installed. Install with: pip install numpy")

        # Extract vectors and associated data
        vector_list = []
        ids = []
        texts = []
        metadata_list = []

        for vec_data in vectors:
            vector = vec_data.get("vector") or vec_data.get("embedding", [])
            if vector:
                vector_list.append(vector)
                ids.append(vec_data.get("id") or vec_data.get("vector_id", ""))

                # Add text if requested
                if self.include_text and "text" in vec_data:
                    texts.append(vec_data["text"])
                else:
                    texts.append(None)

                # Add metadata if requested
                if self.include_metadata and "metadata" in vec_data:
                    metadata_list.append(vec_data["metadata"])
                else:
                    metadata_list.append(None)

        if not vector_list:
            raise ValidationError("No vectors to export. Vector list is empty.")

        # Convert to numpy array
        vector_array = np.array(vector_list)

        # Build save dictionary
        save_dict = {"vectors": vector_array, "ids": np.array(ids)}

        # Add texts if any present
        if any(t for t in texts if t):
            save_dict["texts"] = np.array(texts, dtype=object)

        # Add metadata if any present
        if any(m for m in metadata_list if m):
            save_dict["metadata"] = np.array(metadata_list, dtype=object)

        # Save as compressed NumPy format
        np.savez_compressed(file_path, **save_dict)

        # Save metadata separately as JSON for easy access
        metadata_file = file_path.parent / f"{file_path.stem}_metadata.json"
        metadata = {
            "vector_count": len(vector_list),
            "dimension": (
                vector_array.shape[1]
                if len(vector_array.shape) > 1
                else vector_array.shape[0]
            ),
            "shape": list(vector_array.shape),
        }
        write_json_file(metadata, metadata_file)

        self.logger.debug(
            f"Exported {len(vector_list)} vector(s) to NumPy: "
            f"shape={vector_array.shape}, metadata={metadata_file}"
        )

    def _export_binary(
        self, vectors: List[Dict[str, Any]], file_path: Path, **options
    ) -> None:
        """Export to binary format."""
        try:
            import numpy as np
        except (ImportError, OSError):
            raise ImportError("NumPy not installed. Install with: pip install numpy")

        # Extract vectors
        vector_list = []
        for vec_data in vectors:
            vector = vec_data.get("vector") or vec_data.get("embedding", [])
            if vector:
                vector_list.append(vector)

        if not vector_list:
            raise ValidationError("No vectors to export")

        # Convert to numpy array
        vector_array = np.array(vector_list, dtype=np.float32)

        # Save as binary
        vector_array.tofile(file_path)

        # Save metadata
        metadata_file = file_path.parent / f"{file_path.stem}_metadata.json"
        metadata = {
            "vector_count": len(vector_list),
            "dimension": vector_array.shape[1]
            if len(vector_array.shape) > 1
            else vector_array.shape[0],
            "shape": list(vector_array.shape),
            "dtype": "float32",
        }
        write_json_file(metadata, metadata_file)

    def _export_faiss(
        self,
        vectors: List[Dict[str, Any]],
        file_path: Path,
        normalize: bool = False,
        **options,
    ) -> None:
        """
        Export vectors to FAISS index format.

        This method exports vectors to FAISS index format for efficient similarity
        search. Creates a FAISS index and saves it along with ID mapping.

        Args:
            vectors: List of vector dictionaries
            file_path: Output FAISS index file path
            normalize: Whether to normalize vectors before indexing (default: False)
            **options: Additional options (unused)

        Raises:
            ImportError: If FAISS is not installed
            ValidationError: If no vectors to export

        Example:
            >>> vectors = [{"id": "v1", "vector": [0.1, 0.2, ...]}, ...]
            >>> exporter._export_faiss(vectors, "index.faiss", normalize=True)
        """
        try:
            import faiss
            import numpy as np
        except (ImportError, OSError):
            raise ImportError(
                "FAISS not installed. Install with: pip install 'semantica[vectorstore-faiss]' (or 'semantica[gpu]' for CUDA)"
            )

        # Extract vectors and IDs
        vector_list = []
        ids = []

        for vec_data in vectors:
            vector = vec_data.get("vector") or vec_data.get("embedding", [])
            if vector:
                vector_list.append(vector)
                ids.append(vec_data.get("id") or vec_data.get("vector_id", ""))

        if not vector_list:
            raise ValidationError("No vectors to export. Vector list is empty.")

        # Convert to numpy array
        vector_array = np.array(vector_list, dtype=np.float32)
        dimension = vector_array.shape[1]

        self.logger.debug(
            f"Creating FAISS index: {len(vector_list)} vector(s), "
            f"dimension={dimension}, normalize={normalize}"
        )

        # Create FAISS index (L2 distance)
        index = faiss.IndexFlatL2(dimension)

        # Normalize vectors if requested
        if normalize:
            faiss.normalize_L2(vector_array)
            self.logger.debug("Normalized vectors for FAISS index")

        # Add vectors to index
        index.add(vector_array)

        # Save FAISS index
        faiss.write_index(index, str(file_path))

        # Save ID mapping for vector retrieval
        id_file = file_path.parent / f"{file_path.stem}_ids.json"
        id_mapping = {"ids": ids, "vector_count": len(ids), "dimension": dimension}
        write_json_file(id_mapping, id_file)

        self.logger.debug(f"Exported FAISS index: {file_path}, ID mapping={id_file}")

    def export_for_vector_store(
        self,
        vectors: List[Dict[str, Any]],
        file_path: Union[str, Path],
        vector_store_type: str = "weaviate",
        **options,
    ) -> None:
        """
        Export in format suitable for specific vector store.

        Args:
            vectors: List of vector dictionaries
            file_path: Output file path
            vector_store_type: Vector store type ('weaviate', 'qdrant', 'faiss')
            **options: Additional options
        """
        if vector_store_type == "weaviate":
            self._export_weaviate_format(vectors, file_path, **options)
        elif vector_store_type == "qdrant":
            self._export_qdrant_format(vectors, file_path, **options)
        elif vector_store_type == "faiss":
            self._export_faiss(vectors, file_path, **options)
        else:
            # Default to JSON
            self._export_json(vectors, Path(file_path), {}, **options)

    def _export_weaviate_format(
        self, vectors: List[Dict[str, Any]], file_path: Path, **options
    ) -> None:
        """Export in Weaviate format."""
        weaviate_data = []

        for vec_data in vectors:
            vector_id = vec_data.get("id") or vec_data.get("vector_id", "")
            vector = vec_data.get("vector") or vec_data.get("embedding", [])

            weaviate_obj = {"id": vector_id, "vector": vector}

            if "text" in vec_data and self.include_text:
                weaviate_obj["text"] = vec_data["text"]

            if "metadata" in vec_data and self.include_metadata:
                weaviate_obj.update(vec_data["metadata"])

            weaviate_data.append(weaviate_obj)

        export_data = {"objects": weaviate_data}
        write_json_file(export_data, file_path, indent=2)

    def _export_qdrant_format(
        self, vectors: List[Dict[str, Any]], file_path: Path, **options
    ) -> None:
        """Export in Qdrant format."""
        qdrant_data = []

        for vec_data in vectors:
            vector_id = vec_data.get("id") or vec_data.get("vector_id", "")
            vector = vec_data.get("vector") or vec_data.get("embedding", [])
            payload = vec_data.get("metadata", {})

            if "text" in vec_data and self.include_text:
                payload["text"] = vec_data["text"]

            qdrant_data.append({"id": vector_id, "vector": vector, "payload": payload})

        export_data = {"points": qdrant_data}
        write_json_file(export_data, file_path, indent=2)

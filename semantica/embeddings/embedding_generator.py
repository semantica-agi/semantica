"""
Embedding Generation Module

This module provides comprehensive embedding generation capabilities for text,
images, audio, and multi-modal content, with support for multiple embedding
models and optimization strategies.

Key Features:
    - Text embedding generation (multiple models: sentence-transformers, OpenAI, BGE, FastEmbed, etc.)
    - Image embedding generation
    - Batch processing for efficiency
    - Similarity comparison utilities

Example Usage:
    >>> from semantica.embeddings import EmbeddingGenerator
    >>> generator = EmbeddingGenerator()
    >>> embeddings = generator.generate_embeddings("Hello world", data_type="text")
    >>> similarity = generator.compare_embeddings(emb1, emb2, method="cosine")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from .text_embedder import TextEmbedder


class EmbeddingGenerator:
    """
    Main embedding generation handler.

    This class provides a unified interface for generating embeddings from
    text data using multiple embedding models.
    It handles batch processing and similarity calculations.

    Supported Models:
        - sentence-transformers: High-quality sentence embeddings
        - openai: OpenAI text-embedding models
        - bge: BAAI General Embedding models
        - fastembed: Fast and efficient text embeddings

    Example Usage:
        >>> generator = EmbeddingGenerator()
        >>> # Single text embedding
        >>> emb = generator.generate_embeddings("Hello world", data_type="text")
        >>> # Batch processing
        >>> embs = generator.process_batch(["text1", "text2", "text3"])
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize embedding generator.

        Sets up embedders for different data types.
        Configuration can be provided via config dict or keyword arguments.

        Args:
            config: Configuration dictionary with keys:
                - text: Text embedder configuration
            **kwargs: Additional configuration (merged into config)
        """
        self.logger = get_logger("embedding_generator")

        # Merge configuration
        self.config = dict(config or {})
        self.config.update(kwargs)

        # Initialize embedders for different data types
        # These are lazy-loaded and only initialized when needed
        text_config = dict(self.config.get("text", {}))
        # EmbeddingGenerator(method=..., model_name=...) is the obvious way to
        # pick a model, but only config["text"] used to reach the TextEmbedder,
        # so those were dropped and the default fastembed model (or the hash
        # fallback) was used instead. Forward them unless "text" sets them too.
        for key in ("method", "model_name", "device", "normalize"):
            if key in self.config and key not in text_config:
                text_config[key] = self.config[key]

        self.text_embedder = TextEmbedder(**text_config)

        # List of supported embedding models
        self.supported_models = ["sentence-transformers", "openai", "bge", "fastembed"]

        # Initialize progress tracker
        from ..utils.progress_tracker import get_progress_tracker

        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.logger.info("Embedding generator initialized")

    def set_text_model(self, method: str, model_name: str, **config) -> None:
        """
        Set the text embedding model dynamically.

        Args:
            method: Embedding method ("sentence_transformers", "fastembed")
            model_name: Model name
            **config: Additional configuration
        """
        self.text_embedder.set_model(method, model_name, **config)
        self.logger.info(f"Switched text model to: {method}/{model_name}")

    def get_text_method(self) -> str:
        """
        Get the active text embedding method being used.

        Returns:
            str: Active text embedding method name

        Example:
            >>> generator = EmbeddingGenerator()
            >>> method = generator.get_text_method()
            >>> print(f"Text method: {method}")
        """
        return self.text_embedder.get_method()

    def get_methods_info(self) -> Dict[str, Any]:
        """
        Get detailed information about all active embedding methods.

        Returns:
            dict: Dictionary containing information about text embedder

        Example:
            >>> generator = EmbeddingGenerator()
            >>> info = generator.get_methods_info()
            >>> print(f"Text method: {info['text']['method']}")
        """
        return {
            "text": self.text_embedder.get_model_info(),
        }

    def generate_embeddings(
        self,
        data: Union[str, Path, List[Union[str, Path, Any]]],
        data_type: Optional[str] = None,
        **options,
    ) -> np.ndarray:
        """
        Generate embeddings for input data.

        This method automatically detects the data type if not specified and
        routes to the appropriate embedder. Supports both single items and batches.

        Args:
            data: Input data to embed:
                - str: Text string
                - List: Batch of texts or FileObjects
            data_type: Explicit data type ("text")
                      If None, defaults to "text"
            **options: Additional generation options passed to embedder

        Returns:
            np.ndarray: Generated embeddings
                - For single input: 1D array
                - For batch input: 2D array (batch_size, embedding_dim)

        Raises:
            ProcessingError: If data type is unsupported or embedding fails

        Example:
            >>> # Single text
            >>> emb = generator.generate_embeddings("Hello world")
            >>> # Batch of texts
            >>> embs = generator.generate_embeddings(["text1", "text2"])
        """
        # Default to text if not provided
        if data_type is None:
            data_type = "text"
            self.logger.debug(f"Using data type: {data_type}")

        # Pre-process list if it contains FileObjects or dicts
        if isinstance(data, list):
            processed_data = []
            for item in data:
                if isinstance(item, str):
                    processed_data.append(item)
                elif hasattr(item, "content") and item.content:
                    # Handle FileObject or similar
                    if isinstance(item.content, bytes):
                        try:
                            processed_data.append(item.content.decode("utf-8"))
                        except Exception:
                            # Fallback or skip
                            processed_data.append("")
                    else:
                        processed_data.append(str(item.content))
                elif isinstance(item, dict) and "content" in item:
                    # Handle parsed/normalized doc
                    processed_data.append(str(item["content"]))
                else:
                    # Try converting to string
                    try:
                        processed_data.append(str(item))
                    except Exception:
                        processed_data.append("")
            
            # Update data to be list of strings
            data = processed_data

        # Route to appropriate embedder based on data type
        if data_type == "text":
            if isinstance(data, str):
                return self.text_embedder.embed_text(data, **options)
            elif isinstance(data, list):
                return self.text_embedder.embed_batch(data, **options)
        else:
            error_msg = (
                f"Unsupported data type: {data_type}. "
                f"Supported types: text"
            )
            raise ProcessingError(error_msg)


    def compare_embeddings(
        self, embedding1: np.ndarray, embedding2: np.ndarray, **options
    ) -> float:
        """
        Compare embeddings for similarity.

        Args:
            embedding1: First embedding
            embedding2: Second embedding
            **options: Comparison options:
                - method: Similarity method ("cosine", "euclidean")

        Returns:
            float: Similarity score (0-1)
        """
        method = options.get("method", "cosine")

        if method == "cosine":
            return self._cosine_similarity(embedding1, embedding2)
        elif method == "euclidean":
            return self._euclidean_similarity(embedding1, embedding2)
        else:
            return self._cosine_similarity(embedding1, embedding2)

    def _cosine_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity."""
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    def _euclidean_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute Euclidean similarity (converted to 0-1 scale)."""
        distance = np.linalg.norm(emb1 - emb2)
        # Normalize to 0-1 (simple approach)
        max_distance = np.linalg.norm(emb1) + np.linalg.norm(emb2)
        similarity = 1.0 - (distance / max_distance) if max_distance > 0 else 0.0
        return max(0.0, min(1.0, similarity))

    def process_batch(
        self, data_items: List[Union[str, Path]], pipeline_id: Optional[str] = None, **options
    ) -> Dict[str, Any]:
        """
        Process multiple data items for embedding generation.

        Args:
            data_items: List of data items
            pipeline_id: Optional pipeline ID for progress tracking
            **options: Processing options

        Returns:
            dict: Batch processing results
        """
        # Track batch processing
        tracking_id = self.progress_tracker.start_tracking(
            module="embeddings",
            submodule="EmbeddingGenerator",
            message=f"Batch of {len(data_items)} items",
            pipeline_id=pipeline_id,
        )

        try:
            results = {"embeddings": [], "successful": [], "failed": []}

            for idx, item in enumerate(data_items, 1):
                try:
                    # Use update_progress for ETA display
                    self.progress_tracker.update_progress(
                        tracking_id,
                        processed=idx,
                        total=len(data_items),
                        message=f"Processing item {idx}/{len(data_items)}"
                    )
                    embedding = self.generate_embeddings(item, **options)
                    results["embeddings"].append(embedding)
                    results["successful"].append(str(item))
                except Exception as e:
                    results["failed"].append({"item": str(item), "error": str(e)})

            results["total"] = len(data_items)
            results["success_count"] = len(results["successful"])
            results["failure_count"] = len(results["failed"])

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Processed {results['success_count']}/{len(data_items)} items successfully",
            )
            return results

        except Exception as e:
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            raise

"""
Unified Text Splitter Module

This module provides a unified interface for all text splitting and chunking methods,
enabling easy switching between different splitting strategies with a consistent API.

Supported Methods:
    - All methods from methods.py (recursive, token, sentence, paragraph, etc.)
    - All KG/ontology methods (entity_aware, relation_aware, graph_based, etc.)
    - Integration with existing chunkers (SemanticChunker, StructuralChunker, etc.)

Algorithms Used:
    - Strategy Pattern: Method selection and delegation
    - Factory Pattern: Unified creation of appropriate splitter
    - Fallback Chain: Automatic fallback to alternative methods
    - Integration Pattern: Integration with existing chunker classes

Key Features:
    - Unified interface for all splitting methods
    - Method parameter support (string or list for fallback chain)
    - Integration with existing chunkers
    - Backward compatibility with existing API
    - Automatic method fallback
    - Consistent Chunk output format

Main Classes:
    - TextSplitter: Unified text splitter with method parameter

Example Usage:
    >>> from semantica.split import TextSplitter
    >>> splitter = TextSplitter(method="recursive", chunk_size=1000, chunk_overlap=200)
    >>> chunks = splitter.split(text)
    >>> 
    >>> # Entity-aware for GraphRAG
    >>> splitter = TextSplitter(method="entity_aware", ner_method="llm", chunk_size=1000)
    >>> chunks = splitter.split(text)

Author: Semantica Contributors
License: MIT
"""

from typing import Any, Dict, List, Optional, Union
import os

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from .config import split_config
from .methods import get_split_method, list_available_methods
from .semantic_chunker import Chunk

logger = get_logger("text_splitter")


class TextSplitter:
    """
    Unified text splitter with support for multiple splitting methods.

    This class provides a single interface for all splitting methods, allowing
    easy switching between different strategies while maintaining backward
    compatibility with existing chunkers.
    """

    def __init__(
        self,
        method: Union[str, List[str]] = "recursive",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs,
    ):
        """
        Initialize text splitter.

        Args:
            method: Splitting method name or list of methods for fallback chain
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            **kwargs: Additional method-specific options:
                - ner_method: NER method for entity_aware splitting
                - relation_method: Relation extraction method for relation_aware
                - provider: LLM provider for llm-based methods
                - model: Model name for LLM or transformer methods
                - tokenizer: Tokenizer name for token-based splitting
                - separators: Separator list for recursive splitting
                - strategy: Strategy for graph_based splitting
                - algorithm: Algorithm name for graph/community methods
        """
        self.logger = get_logger("text_splitter")

        # Normalize method parameter
        if isinstance(method, str):
            self.methods = [method]
        else:
            self.methods = method if isinstance(method, list) else ["recursive"]

        # Set default parameters
        self.chunk_size = chunk_size or split_config.get("chunk_size", 1000)
        self.chunk_overlap = (
            split_config.get("chunk_overlap", 200)
            if chunk_overlap is None
            else chunk_overlap
        )

        # Store additional options
        self.options = kwargs

        # Load method-specific config
        self._load_method_configs()

    def _load_method_configs(self):
        """Load method-specific configurations from config."""
        for method in self.methods:
            method_config = split_config.get_method_config(method)
            if method_config:
                # Merge method config into options (method config takes precedence)
                for key, value in method_config.items():
                    if key not in self.options:
                        self.options[key] = value

    def split(self, text: str, **override_options) -> List[Chunk]:
        """
        Split text into chunks using the specified method(s).

        Args:
            text: Input text to split
            **override_options: Options to override for this split call

        Returns:
            List of Chunk objects

        Raises:
            ProcessingError: If all methods fail
        """
        if not text:
            return []

        # Merge override options
        options = {**self.options, **override_options}
        options["chunk_size"] = options.get("chunk_size", self.chunk_size)
        options["chunk_overlap"] = options.get("chunk_overlap", self.chunk_overlap)

        # Try each method in fallback chain
        last_error = None
        for method_name in self.methods:
            try:
                self.logger.debug(f"Attempting to split using method: {method_name}")

                # Get method function
                method_func = get_split_method(method_name)
                if not method_func:
                    self.logger.warning(
                        f"Method '{method_name}' not found, trying next method"
                    )
                    continue

                # Call method with text and options
                chunks = method_func(text, **options)

                if chunks:
                    self.logger.info(
                        f"Successfully split text into {len(chunks)} chunks using method: {method_name}"
                    )
                    return chunks
                else:
                    self.logger.warning(
                        f"Method '{method_name}' returned no chunks, trying next method"
                    )

            except Exception as e:
                self.logger.warning(
                    f"Method '{method_name}' failed: {e}, trying next method"
                )
                last_error = e
                continue

        # All methods failed
        error_msg = f"All splitting methods failed: {', '.join(self.methods)}"
        if last_error:
            error_msg += f". Last error: {last_error}"

        raise ProcessingError(error_msg)

    def split_batch(self, texts: List[str], **override_options) -> List[List[Chunk]]:
        """
        Split multiple texts into chunks.

        Args:
            texts: List of input texts
            **override_options: Options to override for this split call

        Returns:
            List of chunk lists (one per input text)
        """
        results = []
        for text in texts:
            chunks = self.split(text, **override_options)
            results.append(chunks)
        return results

    def get_available_methods(self) -> List[str]:
        """
        Get list of available splitting methods.

        Returns:
            List of method names
        """
        return list_available_methods()

    def set_method(self, method: Union[str, List[str]]):
        """
        Change the splitting method(s).

        Args:
            method: Method name or list of methods for fallback chain
        """
        if isinstance(method, str):
            self.methods = [method]
        else:
            self.methods = method if isinstance(method, list) else ["recursive"]
        self._load_method_configs()

    def update_options(self, **options):
        """
        Update splitting options.

        Args:
            **options: Options to update
        """
        self.options.update(options)
        self._load_method_configs()

    def split_documents(self, documents: List[Any], **override_options) -> List[Chunk]:
        """
        Split a list of documents into chunks.

        Args:
            documents: List of document objects (must have text/content/page_content attribute)
            **override_options: Options to override for this split call

        Returns:
            List of Chunk objects
        """
        all_chunks = []
        for doc in documents:
            text = ""
            # Duck typing to extract text
            if isinstance(doc, str):
                text = doc
            elif hasattr(doc, "text"):
                text = doc.text
            elif hasattr(doc, "page_content"):
                text = doc.page_content
            elif hasattr(doc, "content"):
                content = doc.content
                if isinstance(content, bytes):
                    try:
                        text = content.decode("utf-8")
                    except Exception:
                        text = content.decode("utf-8", errors="ignore")
                elif isinstance(content, str):
                    text = content
                elif content is None and hasattr(doc, "path") and doc.path:
                     # Try reading from path if content is missing
                     try:
                        if os.path.exists(doc.path):
                            with open(doc.path, "r", encoding="utf-8") as f:
                                text = f.read()
                     except Exception as e:
                        self.logger.warning(f"Could not read file {doc.path}: {e}")
                        continue
                else:
                    text = str(content) if content is not None else ""
            
            if not text:
                continue

            try:
                # Split text
                chunks = self.split(text, **override_options)
                
                # Merge metadata
                doc_metadata = getattr(doc, "metadata", {})
                if doc_metadata:
                    for chunk in chunks:
                        chunk.metadata = {**doc_metadata, **chunk.metadata}
                
                all_chunks.extend(chunks)
            except Exception as e:
                self.logger.warning(f"Failed to split document: {e}")
                continue
            
        return all_chunks

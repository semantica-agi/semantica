"""
Embeddings Generation Module

This module provides comprehensive embedding generation and management capabilities
for the Semantica framework, supporting text content with multiple embedding models
and similarity calculations.

Algorithms Used:

Embedding Generation:
    - Sentence-transformers Encoding: Transformer-based sentence embedding generation using pre-trained models
    - FastEmbed Encoding: Fast and efficient embedding generation using FastEmbed library
    - Hash-based Fallback Embeddings: SHA-256 hash-based deterministic embeddings (128-dimensional)
    - Batch Processing: Vectorized processing for multiple items simultaneously

Similarity Calculation:
    - Cosine Similarity: Dot product divided by vector norms for normalized similarity (0-1 range)
    - Euclidean Similarity: L2 norm distance converted to similarity score (0-1 range)

Pooling Strategies:
    - Mean Pooling: Arithmetic mean across embedding dimension
    - Max Pooling: Element-wise maximum across embedding dimension
    - CLS Token Pooling: First token/embedding extraction (for transformer models)
    - Attention-based Pooling: Softmax-weighted sum using dot product attention scores
    - Hierarchical Pooling: Two-level pooling (chunk-level then global-level mean pooling)

Provider Stores:
    - OpenAI API Integration: REST API-based embedding generation
    - BGE Model Integration: Sentence-transformers wrapper for BAAI General Embedding models
    - FastEmbed Integration: Fast and efficient embedding generation using FastEmbed library
    - Sentence-transformers Integration: Hugging Face transformers-based embedding models

Key Features:
    - Text embedding generation
    - Multiple embedding models and providers
    - Similarity calculation and comparison
    - Pooling strategies for aggregation
    - Method registry for extensibility
    - Configuration management with environment variables and config files

Main Classes:
    - EmbeddingGenerator: Main embedding generation handler
    - TextEmbedder: Text embedding generation
    - VectorEmbeddingManager: Embedding management for vector databases
    - GraphEmbeddingManager: Embedding management for graph databases
    - MethodRegistry: Registry for custom embedding methods
    - EmbeddingsConfig: Configuration manager for embeddings module

Convenience Functions:
    - generate_embeddings: Generate embeddings with method dispatch
    - embed_text: Text embedding wrapper
    - calculate_similarity: Similarity calculation wrapper
    - pool_embeddings: Pooling strategy wrapper

Example Usage:
    >>> from semantica.embeddings import embed_text, calculate_similarity
    >>> # Using method functions
    >>> text_emb = embed_text("Hello world", method="sentence_transformers")
    >>> text_emb2 = embed_text("Hi there", method="fastembed")
    >>> similarity = calculate_similarity(text_emb, text_emb2, method="cosine")
    >>> # Using classes directly
    >>> from semantica.embeddings import EmbeddingGenerator
    >>> generator = EmbeddingGenerator()
    >>> embeddings = generator.generate_embeddings("Hello world", data_type="text")

Author: Semantica Contributors
License: MIT
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from .config import EmbeddingsConfig, embeddings_config
from .embedding_generator import EmbeddingGenerator
from .methods import (
    calculate_similarity,
    check_available_providers,
    embed_text,
    generate_embeddings,
    get_embedding_method,
    list_available_methods,
    pool_embeddings,
)
from .pooling_strategies import (
    AttentionPooling,
    CLSPooling,
    HierarchicalPooling,
    MaxPooling,
    MeanPooling,
    PoolingStrategy,
    PoolingStrategyFactory,
)
from .graph_embedding_manager import GraphEmbeddingManager
from .provider_stores import (
    BGEStore,
    FastEmbedStore,
    LlamaStore,
    OpenAIStore,
    ProviderStore,
    ProviderStoreFactory,
)
from .vector_embedding_manager import VectorEmbeddingManager
from .registry import MethodRegistry, method_registry
from .text_embedder import TextEmbedder
from .text_reranker import TextReranker

__all__ = [
    # Core Classes
    "EmbeddingGenerator",
    "TextEmbedder",
    "TextReranker",
    # Provider stores
    "ProviderStore",
    "ProviderStoreFactory",
    "OpenAIStore",
    "BGEStore",
    "FastEmbedStore",
    "LlamaStore",
    # Embedding managers
    "VectorEmbeddingManager",
    "GraphEmbeddingManager",
    # Pooling strategies
    "PoolingStrategy",
    "MeanPooling",
    "MaxPooling",
    "CLSPooling",
    "AttentionPooling",
    "HierarchicalPooling",
    "PoolingStrategyFactory",
    # Registry and Methods
    "MethodRegistry",
    "method_registry",
    "generate_embeddings",
    "embed_text",
    "calculate_similarity",
    "pool_embeddings",
    "get_embedding_method",
    "list_available_methods",
    "check_available_providers",
    # Configuration
    "EmbeddingsConfig",
    "embeddings_config",
]

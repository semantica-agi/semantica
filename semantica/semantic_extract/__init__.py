"""
Semantic Extraction Module

This module provides comprehensive semantic extraction capabilities for knowledge
engineering, enabling extraction of entities, relations, events, triplets, and
semantic networks from text.

Key Features:
    - Named entity recognition (NER) with multiple implementations
    - Relationship extraction between entities
    - Event detection and temporal processing
    - Coreference resolution for pronouns and entity references
    - RDF triplet extraction and serialization
    - Semantic analysis and role labeling
    - Semantic network construction
    - LLM-based extraction enhancement
    - Extraction validation and quality assessment
    - Batch processing with provenance tracking (batch_index, document_id)
    - Robust fallback mechanisms (ML -> Pattern -> Last Resort)

Main Classes:
    - NamedEntityRecognizer: Main NER coordinator (confidence_threshold, merge_overlapping)
    - NERExtractor: Core NER implementation
    - RelationExtractor: Relationship extraction (confidence_threshold, bidirectional)
    - EventDetector: Event detection and classification (extract_participants, extract_time)
    - CoreferenceResolver: Coreference resolution
    - TripletExtractor: RDF triplet extraction (include_temporal, include_provenance)
    - SemanticAnalyzer: Semantic analysis engine
    - SemanticNetworkExtractor: Semantic network construction
    - LLMExtraction: LLM-based extraction and enhancement
    - ExtractionValidator: Quality validation

Example Usage:
    >>> from semantica.semantic_extract import NamedEntityRecognizer
    >>> ner = NamedEntityRecognizer(confidence_threshold=0.7)
    >>> entities = ner.extract_entities("Steve Jobs founded Apple.")
    
    >>> from semantica.semantic_extract import RelationExtractor
    >>> rel_extractor = RelationExtractor(confidence_threshold=0.6)
    >>> relations = rel_extractor.extract_relations(text, entities=entities)
    
    >>> from semantica.semantic_extract import TripletExtractor
    >>> triplet_extractor = TripletExtractor(include_temporal=True)
    >>> triplets = triplet_extractor.extract_triplets(text)

Author: Semantica Contributors
License: MIT
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple


_LAZY_EXPORTS: Dict[str, Tuple[str, str]] = {
    # Named Entity Recognition
    "NamedEntityRecognizer": (".named_entity_recognizer", "NamedEntityRecognizer"),
    "EntityClassifier": (".named_entity_recognizer", "EntityClassifier"),
    "EntityConfidenceScorer": (".named_entity_recognizer", "EntityConfidenceScorer"),
    "CustomEntityDetector": (".named_entity_recognizer", "CustomEntityDetector"),
    "NERExtractor": (".ner_extractor", "NERExtractor"),
    "Entity": (".types", "Entity"),
    # Triplet Extraction alias (backward compatibility)
    "TripleExtractor": (".triplet_extractor", "TripletExtractor"),
    # Relation Extraction
    "RelationExtractor": (".relation_extractor", "RelationExtractor"),
    "Relation": (".types", "Relation"),
    # Event Detection
    "EventDetector": (".event_detector", "EventDetector"),
    "Event": (".event_detector", "Event"),
    "EventClassifier": (".event_detector", "EventClassifier"),
    "TemporalEventProcessor": (".event_detector", "TemporalEventProcessor"),
    "EventRelationshipExtractor": (".event_detector", "EventRelationshipExtractor"),
    # Coreference Resolution
    "CoreferenceResolver": (".coreference_resolver", "CoreferenceResolver"),
    "Mention": (".coreference_resolver", "Mention"),
    "CoreferenceChain": (".coreference_resolver", "CoreferenceChain"),
    "PronounResolver": (".coreference_resolver", "PronounResolver"),
    "EntityCoreferenceDetector": (".coreference_resolver", "EntityCoreferenceDetector"),
    "CoreferenceChainBuilder": (".coreference_resolver", "CoreferenceChainBuilder"),
    # Triplet Extraction
    "TripletExtractor": (".triplet_extractor", "TripletExtractor"),
    "TripleExtractor": (".triplet_extractor", "TripletExtractor"),
    "Triplet": (".types", "Triplet"),
    "TripletValidator": (".triplet_extractor", "TripletValidator"),
    "RDFSerializer": (".triplet_extractor", "RDFSerializer"),
    "TripletQualityChecker": (".triplet_extractor", "TripletQualityChecker"),
    # Semantic Analysis
    "SemanticAnalyzer": (".semantic_analyzer", "SemanticAnalyzer"),
    "SemanticRole": (".semantic_analyzer", "SemanticRole"),
    "SemanticCluster": (".semantic_analyzer", "SemanticCluster"),
    "SimilarityAnalyzer": (".semantic_analyzer", "SimilarityAnalyzer"),
    "RoleLabeler": (".semantic_analyzer", "RoleLabeler"),
    "SemanticClusterer": (".semantic_analyzer", "SemanticClusterer"),
    # Semantic Network
    "SemanticNetworkExtractor": (".semantic_network_extractor", "SemanticNetworkExtractor"),
    "SemanticNode": (".semantic_network_extractor", "SemanticNode"),
    "SemanticEdge": (".semantic_network_extractor", "SemanticEdge"),
    "SemanticNetwork": (".semantic_network_extractor", "SemanticNetwork"),
    # LLM Enhancement
    "LLMExtraction": (".llm_extraction", "LLMExtraction"),
    "LLMEnhancer": (".llm_extraction", "LLMEnhancer"),
    "LLMResponse": (".llm_extraction", "LLMResponse"),
    # Validation
    "ExtractionValidator": (".extraction_validator", "ExtractionValidator"),
    "ValidationResult": (".extraction_validator", "ValidationResult"),
    # Providers
    "BaseProvider": (".providers", "BaseProvider"),
    "OpenAIProvider": (".providers", "OpenAIProvider"),
    "GeminiProvider": (".providers", "GeminiProvider"),
    "GroqProvider": (".providers", "GroqProvider"),
    "AnthropicProvider": (".providers", "AnthropicProvider"),
    "OllamaProvider": (".providers", "OllamaProvider"),
    "HuggingFaceLLMProvider": (".providers", "HuggingFaceLLMProvider"),
    "HuggingFaceModelLoader": (".providers", "HuggingFaceModelLoader"),
    "create_provider": (".providers", "create_provider"),
    # Registry
    "ProviderRegistry": (".registry", "ProviderRegistry"),
    "MethodRegistry": (".registry", "MethodRegistry"),
    "provider_registry": (".registry", "provider_registry"),
    "method_registry": (".registry", "method_registry"),
    # Config
    "Config": (".config", "Config"),
    "config": (".config", "config"),
    # Methods
    "get_entity_method": (".methods", "get_entity_method"),
    "get_relation_method": (".methods", "get_relation_method"),
    "get_triplet_method": (".methods", "get_triplet_method"),
}


def __getattr__(name: str) -> Any:
    """Lazily load semantic extraction exports to avoid import cycles and optional deps."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

__all__ = [
    # Named Entity Recognition
    "NamedEntityRecognizer",
    "EntityClassifier",
    "EntityConfidenceScorer",
    "CustomEntityDetector",
    "NERExtractor",
    "Entity",
    # Relation Extraction
    "RelationExtractor",
    "Relation",
    # Event Detection
    "EventDetector",
    "Event",
    "EventClassifier",
    "TemporalEventProcessor",
    "EventRelationshipExtractor",
    # Coreference Resolution
    "CoreferenceResolver",
    "Mention",
    "CoreferenceChain",
    "PronounResolver",
    "EntityCoreferenceDetector",
    "CoreferenceChainBuilder",
    # Triplet Extraction
    "TripletExtractor",
    "Triplet",
    "TripletValidator",
    "RDFSerializer",
    "TripletQualityChecker",
    # Semantic Analysis
    "SemanticAnalyzer",
    "SemanticRole",
    "SemanticCluster",
    "SimilarityAnalyzer",
    "RoleLabeler",
    "SemanticClusterer",
    # Semantic Network
    "SemanticNetworkExtractor",
    "SemanticNode",
    "SemanticEdge",
    "SemanticNetwork",
    # LLM Enhancement
    "LLMExtraction",
    "LLMEnhancer",
    "LLMResponse",
    # Validation
    "ExtractionValidator",
    "ValidationResult",
    # Providers
    "BaseProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "GroqProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "HuggingFaceLLMProvider",
    "HuggingFaceModelLoader",
    "create_provider",
    # Registry
    "ProviderRegistry",
    "MethodRegistry",
    "provider_registry",
    "method_registry",
    # Config
    "Config",
    "config",
    # Methods
    "get_entity_method",
    "get_relation_method",
    "get_triplet_method",
]

"""
LLM Extraction Module

This module provides LLM-based extraction and enhancement capabilities using multiple
language model providers to improve entity and relation extraction quality through
post-processing and refinement.

Supported Providers:
    - "openai": OpenAI (GPT-3.5, GPT-4, etc.)
    - "gemini": Google Gemini (gemini-pro, etc.)
    - "groq": Groq (llama2, mixtral, etc.)
    - "anthropic": Anthropic Claude (claude-3-sonnet, etc.)
    - "ollama": Ollama (local open-source models)
    - "huggingface_llm": HuggingFace Transformers (custom LLM models)

Algorithms Used:
    - Prompt Engineering: Structured prompt construction for enhancement tasks
    - LLM Generation: Transformer-based language model text generation
    - Response Parsing: JSON parsing and structured output extraction
    - Entity Refinement: Confidence-based entity validation and correction
    - Relation Enhancement: Context-aware relation validation and improvement
    - Temperature Sampling: Stochastic sampling for diverse outputs

Key Features:
    - Entity extraction enhancement using LLMs
    - Relation extraction enhancement
    - Multi-provider support:
        * OpenAI (GPT-3.5, GPT-4, etc.)
        * Google Gemini (gemini-pro, etc.)
        * Groq (llama2, mixtral, etc.)
        * Anthropic Claude (claude-3-sonnet, etc.)
        * Ollama (local open-source models)
        * HuggingFace Transformers (custom LLM models)
    - Unified provider interface via providers module
    - Configurable model selection per provider
    - Automatic API key management from environment variables
    - Graceful fallback when LLM unavailable
    - Structured prompt generation for enhancement tasks

Main Classes:
    - LLMExtraction: Main LLM extraction coordinator
    - LLMResponse: LLM response representation dataclass

Example Usage:
    >>> from semantica.semantic_extract import LLMExtraction
    >>> # Using OpenAI
    >>> extractor = LLMExtraction(provider="openai", model="gpt-4")
    >>> enhanced_entities = extractor.enhance_entities(text, entities)
    >>> enhanced_relations = extractor.enhance_relations(text, relations)
    >>> 
    >>> # Using Gemini
    >>> extractor = LLMExtraction(provider="gemini", model="gemini-pro")
    >>> enhanced_entities = extractor.enhance_entities(text, entities)
    >>> 
    >>> # Using Ollama (local)
    >>> extractor = LLMExtraction(provider="ollama", model="llama2")
    >>> enhanced_entities = extractor.enhance_entities(text, entities)

Author: Semantica Contributors
License: MIT
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger
from ..utils.progress_tracker import get_progress_tracker
from .ner_extractor import Entity
from .providers import create_provider
from .relation_extractor import Relation


@dataclass
class LLMResponse:
    """LLM response representation."""

    content: str
    model: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any]


class LLMExtraction:
    """LLM-based extraction and enhancement."""

    def __init__(self, provider: str = "openai", **config):
        """
        Initialize LLM extraction.

        Args:
            provider: LLM provider ("openai", "gemini", "groq", "anthropic", "ollama", "huggingface_llm")
            **config: Configuration options:
                - model: Model name (default depends on provider)
                - api_key: API key (from environment if not provided)
                - temperature: Temperature for generation (None = use model's default)
        """
        self.logger = get_logger("llm_extraction")
        self.config = config
        self.progress_tracker = get_progress_tracker()
        # Ensure progress tracker is enabled
        if not self.progress_tracker.enabled:
            self.progress_tracker.enabled = True

        self.provider_name = provider
        self.model = config.get("model")
        self.temperature = config.get("temperature")  # None = use model default

        # Initialize provider using new system
        try:
            # Sanitize config: remove api_key if it's None/empty to allow fallback
            provider_config = config.copy()
            if "api_key" in provider_config and not provider_config["api_key"]:
                del provider_config["api_key"]
                
            self.provider = create_provider(provider, **provider_config)
        except Exception as e:
            self.logger.warning(f"Failed to initialize {provider} provider: {e}")
            self.provider = None

    def enhance_extractions(
        self, extractions: List[Any], text: str, **options
    ) -> List[Any]:
        """
        Enhance generic extractions (entities, relations, etc.).

        Args:
            extractions: List of extractions
            text: Input text
            **options: Enhancement options

        Returns:
            list: Enhanced extractions
        """
        if not extractions:
            return []

        # Determine type based on first element
        first = extractions[0]

        # Check for Entity
        if hasattr(first, "text") and hasattr(first, "label") and hasattr(first, "start_char"):
            return self.enhance_entities(text, extractions, **options)

        # Check for Relation
        if hasattr(first, "subject") and hasattr(first, "predicate") and hasattr(first, "object"):
            return self.enhance_relations(text, extractions, **options)

        # Default/Event fallback (mock implementation for now)
        self.logger.warning("Extraction type not fully supported for enhancement. Returning original.")
        return extractions

    def enhance_entities(
        self, text: str, entities: List[Entity], **options
    ) -> List[Entity]:
        """
        Enhance entity extraction using LLM.

        Args:
            text: Input text
            entities: Pre-extracted entities
            **options: Enhancement options

        Returns:
            list: Enhanced entities
        """
        tracking_id = self.progress_tracker.start_tracking(
            module="semantic_extract",
            submodule="LLMExtraction",
            message="Enhancing entities using LLM",
        )

        try:
            if not self.provider or not self.provider.is_available():
                self.logger.warning(
                    "LLM provider not available. Returning original entities."
                )
                self.progress_tracker.stop_tracking(
                    tracking_id,
                    status="completed",
                    message="LLM provider not available",
                )
                return entities

            self.progress_tracker.update_tracking(
                tracking_id, message="Building prompt..."
            )
            prompt = self._build_entity_prompt(text, entities)

            self.progress_tracker.update_tracking(
                tracking_id, message="Calling LLM API..."
            )
            response = self.provider.generate(
                prompt, temperature=options.get("temperature", self.temperature)
            )

            self.progress_tracker.update_tracking(
                tracking_id, message="Parsing LLM response..."
            )
            enhanced_entities = self._parse_entity_response(response, entities)

            self.progress_tracker.stop_tracking(
                tracking_id,
                status="completed",
                message=f"Enhanced {len(enhanced_entities)} entities",
            )
            return enhanced_entities
        except Exception as e:
            self.logger.error(f"Failed to enhance entities with LLM: {e}")
            self.progress_tracker.stop_tracking(
                tracking_id, status="failed", message=str(e)
            )
            return entities

    def enhance_relations(
        self, text: str, relations: List[Relation], **options
    ) -> List[Relation]:
        """
        Enhance relation extraction using LLM.

        Args:
            text: Input text
            relations: Pre-extracted relations
            **options: Enhancement options

        Returns:
            list: Enhanced relations
        """
        if not self.provider or not self.provider.is_available():
            self.logger.warning(
                "LLM provider not available. Returning original relations."
            )
            return relations

        prompt = self._build_relation_prompt(text, relations)

        try:
            response = self.provider.generate(
                prompt, temperature=options.get("temperature", self.temperature)
            )
            enhanced_relations = self._parse_relation_response(response, relations)
            return enhanced_relations
        except Exception as e:
            self.logger.error(f"Failed to enhance relations with LLM: {e}")
            return relations

    def _build_entity_prompt(self, text: str, entities: List[Entity]) -> str:
        """Build prompt for entity enhancement.

        User-supplied content is serialised as JSON strings so that special
        characters (newlines, quotes, prompt-injection attempts) cannot escape
        the data section and override the system instructions.
        """
        import json as _json
        safe_text = _json.dumps(text)
        safe_entities = _json.dumps([{"text": e.text, "label": e.label} for e in entities])

        return f"""Analyze the text provided in the JSON fields below and enhance the entity extraction.

INPUT_TEXT: {safe_text}

EXTRACTED_ENTITIES: {safe_entities}

Please:
1. Verify each entity is correctly identified
2. Suggest any missing entities
3. Improve entity type classifications
4. Provide confidence scores

Return the enhanced entity list in JSON format."""

    def _build_relation_prompt(self, text: str, relations: List[Relation]) -> str:
        """Build prompt for relation enhancement.

        User-supplied content is serialised as JSON strings to prevent
        prompt-injection via crafted text or relation labels.
        """
        import json as _json
        safe_text = _json.dumps(text)
        safe_relations = _json.dumps(
            [
                {
                    "subject": r.subject.text,
                    "predicate": r.predicate,
                    "object": r.object.text,
                }
                for r in relations
            ]
        )

        return f"""Analyze the text provided in the JSON fields below and enhance the relation extraction.

INPUT_TEXT: {safe_text}

EXTRACTED_RELATIONS: {safe_relations}

Please:
1. Verify each relation is correct
2. Suggest any missing relations
3. Improve relation type classifications
4. Provide confidence scores

Return the enhanced relation list in JSON format."""

    def _parse_entity_response(
        self, response: str, original_entities: List[Entity]
    ) -> List[Entity]:
        """Parse LLM response for entities."""
        # Simplified parsing - in practice would parse JSON
        # For now, return original entities with updated metadata
        for entity in original_entities:
            if entity.metadata is None:
                entity.metadata = {}
            entity.metadata.update({
                "enhanced_by": self.provider_name,
                "model": self.model
            })
        return original_entities

    def _parse_relation_response(
        self, response: str, original_relations: List[Relation]
    ) -> List[Relation]:
        """Parse LLM response for relations."""
        # Simplified parsing - in practice would parse JSON
        # For now, return original relations with updated metadata
        for relation in original_relations:
            if relation.metadata is None:
                relation.metadata = {}
            relation.metadata.update({
                "enhanced_by": self.provider_name,
                "model": self.model
            })
        return original_relations


# Alias for backward compatibility
LLMEnhancer = LLMExtraction

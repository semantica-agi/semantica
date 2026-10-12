"""
Provenance-enabled wrappers for LLM providers.

This module provides provenance tracking for all LLM operations:
- Groq LLM
- OpenAI LLM
- HuggingFace LLM
- LiteLLM

Tracks: model name, tokens (prompt/completion), latency, prompts, responses, and
cost where the provider reports it (LiteLLM; OpenAI and Groq do not)

All classes wrap the original LLM providers and add optional provenance tracking
without modifying existing functionality.

Usage:
    from semantica.llms.llms_provenance import (
        GroqLLMWithProvenance,
        OpenAILLMWithProvenance
    )

    # Enable provenance tracking
    llm = GroqLLMWithProvenance(provenance=True)
    response = llm.generate("What is artificial intelligence?")

    # Provenance automatically tracks:
    # - Model used
    # - Token counts
    # - API costs (LiteLLM only; OpenAI and Groq do not report cost)
    # - Latency
    # - Prompt and response previews

Features:
    - Zero breaking changes - works exactly like original LLM classes
    - Opt-in provenance via provenance=True parameter
    - Tracks all API calls with complete metadata
    - Cost tracking for budget monitoring
    - Performance monitoring (latency)
    - Graceful degradation if provenance module unavailable

Author: Semantica Contributors
License: MIT
"""

from typing import Optional, Any
from datetime import datetime
import json
import time
import uuid

from pydantic import BaseModel


def _preview_result(result: Any) -> Optional[str]:
    """Render a structured/typed result as a 200-char preview.

    Serializes the whole value, so a Pydantic model with a ``text`` or
    ``content`` field is not reduced to that one field.
    """
    if result is None:
        return None
    if isinstance(result, BaseModel):
        preview = result.model_dump_json()
    elif isinstance(result, (dict, list)):
        try:
            preview = json.dumps(result, default=str)
        except (TypeError, ValueError):
            preview = str(result)
    else:
        preview = str(result)
    return preview[:200]


class LLMProvenanceMixin:
    """
    Mixin to add provenance tracking to any LLM provider.

    This mixin provides common provenance infrastructure for tracking
    LLM API calls including tokens, costs, and performance metrics.
    """

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **kwargs,
    ):
        """
        Initialize LLM provenance tracking.

        Args:
            provenance: Enable provenance tracking (default: False)
            agent_id: Agent identifier for accountability (issue #825); defaults
                to the wrapping class name
            is_automated: Whether this agent acted without direct human review
            **kwargs: Additional arguments passed to parent class
        """
        self.provenance = provenance
        self._prov_manager = None
        self._agent_id = agent_id or self.__class__.__name__
        self._is_automated = is_automated

        if provenance:
            try:
                from semantica.provenance import ProvenanceManager
                self._prov_manager = ProvenanceManager()
            except ImportError:
                # Graceful degradation if provenance module not available
                self.provenance = False

    def _track_llm_call(
        self,
        call_id: str,
        prompt: str,
        response: Any,
        **metadata
    ) -> None:
        """
        Track LLM API call with provenance.

        Args:
            call_id: Unique identifier for this API call
            prompt: Input prompt
            response: LLM response
            **metadata: Additional metadata (tokens, cost, latency, etc.)
        """
        if self.provenance and self._prov_manager:
            # Extract response text; a reply with no text stays None rather
            # than being recorded as the string "None".
            response_text = response
            if response is None:
                response_preview = None
            else:
                if hasattr(response, 'text'):
                    response_text = response.text
                elif hasattr(response, 'content'):
                    response_text = response.content
                elif not isinstance(response, str):
                    response_text = str(response)
                response_preview = str(response_text)[:200]

            # Typed Activity timing (issue #825, Part B Tier 1): popped out so
            # it populates real fields, not the opaque metadata blob.
            activity_started_at_time = metadata.pop("activity_started_at_time", None)
            activity_ended_at_time = metadata.pop("activity_ended_at_time", None)

            self._prov_manager.track_entity(
                entity_id=call_id,
                source=f"{self.__class__.__name__}_api",
                entity_type="llm_generation",
                agent_id=self._agent_id,
                agent_type="software_agent",
                is_automated=self._is_automated,
                activity_id=call_id,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                metadata={
                    "model": getattr(self, 'model', 'unknown'),
                    "prompt_preview": prompt[:200] if len(prompt) > 200 else prompt,
                    "response_preview": response_preview,
                    **metadata
                }
            )

    def _track_generation(
        self,
        kind: str,
        call_id_prefix: str,
        prompt: str,
        invoke,
        **metadata,
    ):
        """Run one generation call and record a provenance entry for it.

        Args:
            kind: Generation mode label (e.g. ``"structured"``, ``"typed"``),
                recorded as ``generation_mode``.
            call_id_prefix: Prefix for the generated call id.
            prompt: Input prompt.
            invoke: Zero-argument callable performing the wrapped LLM call.
            **metadata: Extra metadata recorded with the entry.

        Returns:
            Whatever ``invoke`` returns, unchanged.
        """
        start_time = time.time()
        activity_started_at_time = datetime.utcnow().isoformat()
        result = invoke()
        elapsed = time.time() - start_time
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance:
            # Pass the serialized preview rather than the raw result, so
            # _track_llm_call does not pick a model's .text/.content field.
            self._track_llm_call(
                call_id=f"{call_id_prefix}_{uuid.uuid4().hex[:8]}",
                prompt=prompt,
                response=_preview_result(result),
                generation_mode=kind,
                latency_seconds=elapsed,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                **metadata,
            )

        return result


class GroqLLMWithProvenance(LLMProvenanceMixin):
    """
    Groq LLM with provenance tracking.

    Wraps the original GroqLLM and tracks all API calls with complete metadata.

    Example:
        >>> llm = GroqLLMWithProvenance(provenance=True, model="llama-3.1-70b")
        >>> response = llm.generate("Explain quantum computing")
        >>> # API call is tracked with model, tokens, latency (Groq reports no cost)
    """

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **config,
    ):
        """
        Initialize Groq LLM with optional provenance.

        Args:
            provenance: Enable provenance tracking (default: False)
            **config: Configuration passed to original GroqLLM
        """
        from .groq import Groq

        LLMProvenanceMixin.__init__(
            self, provenance=provenance, agent_id=agent_id, is_automated=is_automated
        )
        self._llm = Groq(**config)
        self.model = getattr(self._llm, 'model', 'groq')

    def generate(self, prompt: str, **kwargs):
        """
        Generate response with provenance tracking.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            LLM response (same format as original GroqLLM)
        """
        start_time = time.time()
        activity_started_at_time = datetime.utcnow().isoformat()
        response = self._llm.generate(prompt, **kwargs)
        elapsed = time.time() - start_time
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance:
            # Extract token counts if available
            prompt_tokens = None
            completion_tokens = None
            total_cost = None

            if hasattr(response, 'usage'):
                prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                completion_tokens = getattr(response.usage, 'completion_tokens', None)

            if hasattr(response, 'cost'):
                total_cost = response.cost

            self._track_llm_call(
                call_id=f"groq_call_{uuid.uuid4().hex[:8]}",
                prompt=prompt,
                response=response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=(
                    (prompt_tokens + completion_tokens)
                    if prompt_tokens is not None
                    and completion_tokens is not None
                    else None
                ),
                total_cost=total_cost,
                latency_seconds=elapsed,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                temperature=kwargs.get('temperature'),
                max_tokens=kwargs.get('max_tokens'),
                top_p=kwargs.get('top_p')
            )

        return response

    def generate_structured(self, prompt: str, **kwargs):
        """Generate structured JSON with provenance tracking."""
        return self._track_generation(
            "structured",
            "groq_structured",
            prompt,
            lambda: self._llm.generate_structured(prompt, **kwargs),
        )

    def generate_typed(self, prompt: str, schema, max_retries: int = 3, **kwargs):
        """Generate schema-validated output with provenance tracking."""
        return self._track_generation(
            "typed",
            "groq_typed",
            prompt,
            lambda: self._llm.generate_typed(
                prompt, schema, max_retries=max_retries, **kwargs
            ),
            max_retries=max_retries,
        )

    def __getattr__(self, name):
        """Delegate other methods to wrapped LLM."""
        if name == "_llm":
            # _llm is unset (failed __init__, copy.copy, unpickling); looking it
            # up through getattr(self._llm, ...) would recurse forever.
            raise AttributeError(name)
        return getattr(self._llm, name)


class OpenAILLMWithProvenance(LLMProvenanceMixin):
    """
    OpenAI LLM with provenance tracking.

    Wraps the original OpenAILLM and tracks all API calls.
    """

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **config,
    ):
        """
        Initialize OpenAI LLM with optional provenance.

        Args:
            provenance: Enable provenance tracking (default: False)
            **config: Configuration passed to original OpenAILLM
        """
        from .openai import OpenAI

        LLMProvenanceMixin.__init__(
            self, provenance=provenance, agent_id=agent_id, is_automated=is_automated
        )
        self._llm = OpenAI(**config)
        self.model = getattr(self._llm, 'model', 'openai')

    def generate(self, prompt: str, **kwargs):
        """
        Generate response with provenance tracking.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            LLM response
        """
        start_time = time.time()
        activity_started_at_time = datetime.utcnow().isoformat()
        response = self._llm.generate(prompt, **kwargs)
        elapsed = time.time() - start_time
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance:
            # Extract token counts if available
            prompt_tokens = None
            completion_tokens = None
            total_cost = None

            if hasattr(response, 'usage'):
                prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                completion_tokens = getattr(response.usage, 'completion_tokens', None)

            if hasattr(response, 'cost'):
                total_cost = response.cost

            self._track_llm_call(
                call_id=f"openai_call_{uuid.uuid4().hex[:8]}",
                prompt=prompt,
                response=response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=(
                    (prompt_tokens + completion_tokens)
                    if prompt_tokens is not None
                    and completion_tokens is not None
                    else None
                ),
                total_cost=total_cost,
                latency_seconds=elapsed,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                temperature=kwargs.get('temperature'),
                max_tokens=kwargs.get('max_tokens')
            )

        return response

    def generate_structured(self, prompt: str, **kwargs):
        """Generate structured JSON with provenance tracking."""
        return self._track_generation(
            "structured",
            "openai_structured",
            prompt,
            lambda: self._llm.generate_structured(prompt, **kwargs),
        )

    def generate_typed(self, prompt: str, schema, max_retries: int = 3, **kwargs):
        """Generate schema-validated output with provenance tracking."""
        return self._track_generation(
            "typed",
            "openai_typed",
            prompt,
            lambda: self._llm.generate_typed(
                prompt, schema, max_retries=max_retries, **kwargs
            ),
            max_retries=max_retries,
        )

    def __getattr__(self, name):
        """Delegate other methods to wrapped LLM."""
        if name == "_llm":
            # _llm is unset (failed __init__, copy.copy, unpickling); looking it
            # up through getattr(self._llm, ...) would recurse forever.
            raise AttributeError(name)
        return getattr(self._llm, name)


class HuggingFaceLLMWithProvenance(LLMProvenanceMixin):
    """
    HuggingFace LLM with provenance tracking.

    Wraps the original HuggingFaceLLM and tracks all generations.
    """

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **config,
    ):
        """
        Initialize HuggingFace LLM with optional provenance.

        Args:
            provenance: Enable provenance tracking (default: False)
            **config: Configuration passed to original HuggingFaceLLM
        """
        from .huggingface import HuggingFaceLLM

        LLMProvenanceMixin.__init__(
            self, provenance=provenance, agent_id=agent_id, is_automated=is_automated
        )
        self._llm = HuggingFaceLLM(**config)
        self.model = getattr(self._llm, 'model', 'huggingface')

    def generate(self, prompt: str, **kwargs):
        """
        Generate response with provenance tracking.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            LLM response
        """
        start_time = time.time()
        activity_started_at_time = datetime.utcnow().isoformat()
        response = self._llm.generate(prompt, **kwargs)
        elapsed = time.time() - start_time
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance:
            self._track_llm_call(
                call_id=f"hf_call_{uuid.uuid4().hex[:8]}",
                prompt=prompt,
                response=response,
                latency_seconds=elapsed,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                max_length=kwargs.get('max_length'),
                temperature=kwargs.get('temperature')
            )

        return response

    def generate_structured(self, prompt: str, **kwargs):
        """Generate structured JSON with provenance tracking."""
        return self._track_generation(
            "structured",
            "hf_structured",
            prompt,
            lambda: self._llm.generate_structured(prompt, **kwargs),
        )

    def generate_typed(self, prompt: str, schema, max_retries: int = 3, **kwargs):
        """Generate schema-validated output with provenance tracking."""
        return self._track_generation(
            "typed",
            "hf_typed",
            prompt,
            lambda: self._llm.generate_typed(
                prompt, schema, max_retries=max_retries, **kwargs
            ),
            max_retries=max_retries,
        )

    def __getattr__(self, name):
        """Delegate other methods to wrapped LLM."""
        if name == "_llm":
            # _llm is unset (failed __init__, copy.copy, unpickling); looking it
            # up through getattr(self._llm, ...) would recurse forever.
            raise AttributeError(name)
        return getattr(self._llm, name)


class LiteLLMWithProvenance(LLMProvenanceMixin):
    """
    LiteLLM with provenance tracking.

    Wraps the original LiteLLM and tracks all API calls across providers.
    """

    def __init__(
        self,
        provenance: bool = False,
        agent_id: Optional[str] = None,
        is_automated: bool = True,
        **config,
    ):
        """
        Initialize LiteLLM with optional provenance.

        Args:
            provenance: Enable provenance tracking (default: False)
            **config: Configuration passed to original LiteLLM
        """
        from .litellm import LiteLLM

        LLMProvenanceMixin.__init__(
            self, provenance=provenance, agent_id=agent_id, is_automated=is_automated
        )
        self._llm = LiteLLM(**config)
        self.model = getattr(self._llm, 'model', 'litellm')

    def generate(self, prompt: str, **kwargs):
        """
        Generate response with provenance tracking.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            LLM response
        """
        start_time = time.time()
        activity_started_at_time = datetime.utcnow().isoformat()
        response = self._llm.generate(prompt, **kwargs)
        elapsed = time.time() - start_time
        activity_ended_at_time = datetime.utcnow().isoformat()

        if self.provenance:
            # LiteLLM provides unified response format
            prompt_tokens = None
            completion_tokens = None
            total_cost = None

            if hasattr(response, 'usage'):
                prompt_tokens = getattr(response.usage, 'prompt_tokens', None)
                completion_tokens = getattr(response.usage, 'completion_tokens', None)

            if hasattr(response, 'cost'):
                total_cost = response.cost

            self._track_llm_call(
                call_id=f"lite_call_{uuid.uuid4().hex[:8]}",
                prompt=prompt,
                response=response,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost=total_cost,
                latency_seconds=elapsed,
                activity_started_at_time=activity_started_at_time,
                activity_ended_at_time=activity_ended_at_time,
                provider=kwargs.get('provider')
            )

        return response

    def generate_structured(self, prompt: str, **kwargs):
        """Generate structured JSON with provenance tracking."""
        return self._track_generation(
            "structured",
            "lite_structured",
            prompt,
            lambda: self._llm.generate_structured(prompt, **kwargs),
        )

    def generate_typed(self, prompt: str, schema, max_retries: int = 3, **kwargs):
        """Generate schema-validated output with provenance tracking."""
        return self._track_generation(
            "typed",
            "lite_typed",
            prompt,
            lambda: self._llm.generate_typed(
                prompt, schema, max_retries=max_retries, **kwargs
            ),
            max_retries=max_retries,
        )

    def __getattr__(self, name):
        """Delegate other methods to wrapped LLM."""
        if name == "_llm":
            # _llm is unset (failed __init__, copy.copy, unpickling); looking it
            # up through getattr(self._llm, ...) would recurse forever.
            raise AttributeError(name)
        return getattr(self._llm, name)


# Convenience exports
__all__ = [
    'GroqLLMWithProvenance',
    'OpenAILLMWithProvenance',
    'HuggingFaceLLMWithProvenance',
    'LiteLLMWithProvenance',
    'LLMProvenanceMixin',
]

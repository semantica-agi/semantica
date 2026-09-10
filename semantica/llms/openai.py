"""
OpenAI LLM Provider

Wrapper for OpenAI API provider with clean interface.
"""

from typing import Any, Dict, Optional

from ..semantic_extract.providers import OpenAIProvider
from ..utils.exceptions import ProcessingError
from ..utils.logging import get_logger

logger = get_logger("llms.openai")


class OpenAI:
    """
    OpenAI LLM provider wrapper.
    
    Provides clean interface to OpenAI API for text generation.
    
    Example:
        >>> from semantica.llms import OpenAI
        >>> openai = OpenAI(model="gpt-4", api_key="your-key")
        >>> response = openai.generate("What is AI?")
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: Model name (default: "gpt-3.5-turbo")
            api_key: OpenAI API key (default: from OPENAI_API_KEY env var)
            **kwargs: Additional provider options
        """
        self.provider = OpenAIProvider(api_key=api_key, model=model, **kwargs)
        self.model = model
        self.api_key = api_key

    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        return self.provider.is_available()

    def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate text from prompt.

        Args:
            prompt: Input prompt text
            **kwargs: Generation options (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            ProcessingError: If provider is not available or generation fails
        """
        if not self.is_available():
            raise ProcessingError(
                "OpenAI provider not available. Set OPENAI_API_KEY or pass api_key."
            )
        return self.provider.generate(prompt, **kwargs)

    def generate_structured(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: Input prompt text
            **kwargs: Generation options

        Returns:
            Parsed JSON response as dictionary

        Raises:
            ProcessingError: If provider is not available or parsing fails
        """
        if not self.is_available():
            raise ProcessingError(
                "OpenAI provider not available. Set OPENAI_API_KEY or pass api_key."
            )
        return self.provider.generate_structured(prompt, **kwargs)

    def generate_typed(self, prompt: str, schema: Any, max_retries: int = 3, **kwargs) -> Any:
        """
        Generate output validated against a Pydantic schema.

        Args:
            prompt: Input prompt text
            schema: Pydantic model class to validate the output against
            max_retries: Number of retries if validation fails (default: 3)
            **kwargs: Generation options

        Returns:
            An instance of `schema`, populated from the model's response

        Raises:
            ProcessingError: If provider is not available or generation fails
        """
        if not self.is_available():
            raise ProcessingError(
                "OpenAI provider not available. Set OPENAI_API_KEY or pass api_key."
            )
        return self.provider.generate_typed(prompt, schema, max_retries=max_retries, **kwargs)


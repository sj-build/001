"""LLM client interface and implementations."""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract interface for LLM generation."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response from a prompt."""
        ...


class NoLLMClient(LLMClient):
    """Template-based reasoning without any LLM API calls.

    This is the default client that produces structured output
    using only the provided context (summary + memories).
    """

    def generate(self, prompt: str) -> str:
        """Pass through the prompt as-is (template already built)."""
        return prompt

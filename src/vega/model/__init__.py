"""Model routing — multi-provider LLM routing with ordered fallback."""

from vega.model.providers import OllamaProvider, OpenAIProvider, OpenRouterProvider
from vega.model.router import ModelRouter, ModelRouterError

__all__ = [
    "ModelRouter",
    "ModelRouterError",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
]

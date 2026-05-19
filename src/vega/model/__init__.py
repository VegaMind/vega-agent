"""Model routing — multi-provider LLM routing with ordered fallback."""

from vega.model.providers import OpenAIProvider, OpenRouterProvider
from vega.model.router import ModelRouter, ModelRouterError

__all__ = [
    "ModelRouter",
    "ModelRouterError",
    "OpenAIProvider",
    "OpenRouterProvider",
]

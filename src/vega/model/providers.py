"""LLM provider implementations — OpenRouter and OpenAI.

Each provider is a stateless class with a ``supports_config``
classmethod and a ``complete`` classmethod.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 120.0


class OpenRouterProvider:
    """Provider that routes requests through OpenRouter's API."""

    @classmethod
    def supports_config(cls, config: dict) -> bool:
        """Return True if *config* points at OpenRouter."""
        return config.get("name") == "openrouter"

    @classmethod
    def complete(
        cls,
        messages: list[dict],
        config: dict,
        api_key: str,
        **kwargs: Any,
    ) -> dict:
        """Send a chat completion request to OpenRouter.

        Returns a dict with keys: ``content``, ``model``, ``provider``, ``usage``.
        """
        if not api_key:
            raise ValueError(
                "OpenRouter requires an API key — run `vega init` or set one in ~/.vega/.api_key"
            )
        model = config.get("model", "")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vega-agent.local",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.debug("OpenRouter request: model=%s, messages=%d", model, len(messages))

        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(OPENROUTER_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        result = _parse_response(data)
        result["provider"] = "openrouter"
        logger.debug(
            "OpenRouter response: model=%s, usage=%s", result["model"], result["usage"]
        )
        return result


class OpenAIProvider:
    """Provider that sends requests directly to OpenAI's API."""

    @classmethod
    def supports_config(cls, config: dict) -> bool:
        """Return True if *config* points at OpenAI."""
        return config.get("name") == "openai"

    @classmethod
    def complete(
        cls,
        messages: list[dict],
        config: dict,
        api_key: str,
        **kwargs: Any,
    ) -> dict:
        """Send a chat completion request to OpenAI.

        Returns a dict with keys: ``content``, ``model``, ``provider``, ``usage``.
        """
        if not api_key:
            raise ValueError(
                "OpenAI requires an API key — run `vega init` or set one in ~/.vega/.api_key"
            )
        model = config.get("model", "")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.debug("OpenAI request: model=%s, messages=%d", model, len(messages))

        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(OPENAI_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        result = _parse_response(data)
        result["provider"] = "openai"
        logger.debug(
            "OpenAI response: model=%s, usage=%s", result["model"], result["usage"]
        )
        return result


def _parse_response(data: dict) -> dict:
    """Extract common fields from an OpenAI-compatible chat completion response."""
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    model = data.get("model", "")
    usage_raw = data.get("usage", {})
    usage = {
        "prompt_tokens": usage_raw.get("prompt_tokens", 0),
        "completion_tokens": usage_raw.get("completion_tokens", 0),
        "total_tokens": usage_raw.get("total_tokens", 0),
    }
    return {"content": content, "model": model, "usage": usage}


class OllamaProvider:
    """Provider for local Ollama models."""

    @classmethod
    def supports_config(cls, config: dict) -> bool:
        """Return True if *config* points at Ollama."""
        return config.get("name") == "ollama"

    @classmethod
    def complete(
        cls,
        messages: list[dict],
        config: dict,
        api_key: str = "",
        **kwargs: Any,
    ) -> dict:
        """Send a chat completion request to a local Ollama instance.

        Returns a dict with keys: ``content``, ``model``, ``provider``, ``usage``.
        """
        model = config.get("model", "")
        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 4096)
        timeout = kwargs.get("timeout", 120.0)

        from vega.model.ollama_helper import ollama_chat

        result = ollama_chat(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        return result

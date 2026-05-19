"""ModelRouter — multi-provider LLM routing with ordered fallback.

Iterates configured providers in order, tries each one, and falls
back on failure. Raises ``ModelRouterError`` if all providers fail.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vega.model.providers import OllamaProvider, OpenAIProvider, OpenRouterProvider

logger = logging.getLogger(__name__)

# Ordered list of supported provider classes
PROVIDER_CLASSES = [OpenRouterProvider, OpenAIProvider, OllamaProvider]


class ModelRouterError(Exception):
    """Raised when all configured providers fail to produce a response."""

    def __init__(self, message: str, failures: list[dict] | None = None):
        self.failures = failures or []
        super().__init__(message)


class ModelRouter:
    """Routes chat completion requests across providers with fallback."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict],
        api_key: str = "",
        **kwargs: Any,
    ) -> dict:
        """Send *messages* through the first working provider.

        Parameters
        ----------
        messages:
            List of dicts with ``role`` and ``content`` keys.
        api_key:
            API key override.  If empty we attempt to read it from
            ``~/.vega/.api_key``.
        **kwargs:
            Additional overrides (e.g. ``temperature``, ``max_tokens``).

        Returns
        -------
        dict
            ``{content, model, provider, usage}`` — identical to what
            individual providers return.

        Raises
        ------
        ModelRouterError
            When *all* configured providers fail.
        """
        resolved_key = self._resolve_api_key(api_key)

        provider_configs = self._get_provider_configs()
        if not provider_configs:
            raise ModelRouterError(
                "No providers configured — add a 'model.providers' list or "
                "'model.provider' + 'model.name' to your config."
            )

        model_section = self.config.get("model", {})
        temperature = kwargs.pop("temperature", model_section.get("temperature", 0.7))
        max_tokens = kwargs.pop("max_tokens", model_section.get("max_tokens", 4096))

        failures: list[dict] = []

        for pcfg in provider_configs:
            provider_cls = self._match_provider(pcfg)
            if provider_cls is None:
                logger.warning("No provider class matched config: %s", pcfg)
                failures.append(
                    {"config": pcfg, "error": "No matching provider class"}
                )
                continue

            logger.info(
                "Trying %s with model=%s", pcfg["name"], pcfg.get("model", "")
            )
            try:
                result = provider_cls.complete(
                    messages=messages,
                    config=pcfg,
                    api_key=resolved_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                logger.info(
                    "Success from %s: model=%s", pcfg["name"], result.get("model", "")
                )
                return result
            except Exception as exc:
                logger.warning(
                    "Provider %s failed: %s: %s",
                    pcfg["name"],
                    type(exc).__name__,
                    exc,
                )
                failures.append(
                    {"config": pcfg, "error": f"{type(exc).__name__}: {exc}"}
                )

        # All providers failed
        msg = (
            f"All providers failed ({len(failures)} tried). "
            f"Last error: {failures[-1]['error'] if failures else 'N/A'}"
        )
        raise ModelRouterError(msg, failures=failures)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_api_key(key: str) -> str:
        """Return *key* if non-empty, otherwise read from ``~/.vega/.api_key``."""
        if key:
            return key
        key_path = Path.home() / ".vega" / ".api_key"
        if key_path.exists():
            return key_path.read_text().strip()
        return ""

    def _get_provider_configs(self) -> list[dict]:
        """Extract the list of provider config dicts from *self.config*.

        Handles both the new ``model.providers`` list format and the old
        flat ``model.provider`` + ``model.name`` format.
        """
        model = self.config.get("model", {})

        # New format: list of dicts
        if "providers" in model and isinstance(model["providers"], list):
            return model["providers"]

        # Old format: flat keys
        provider_name = model.get("provider")
        model_name = model.get("name")
        if provider_name and model_name:
            return [{"name": provider_name, "model": model_name}]

        return []

    @staticmethod
    def _match_provider(config: dict) -> type | None:
        """Return the first provider class whose ``supports_config`` returns True."""
        for cls in PROVIDER_CLASSES:
            if cls.supports_config(config):
                return cls
        return None

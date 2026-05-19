"""Vega Config — YAML configuration loader and validator.

Auto-creates ``~/.vega/config.yaml`` with sensible defaults on first
invocation of ``vega init``.

Config sections:

* **privacy** — telemetry, cloud sync, local models, encryption
* **model** — provider, name, temperature, max_tokens
* **paths** — data dir, chromadb dir, context tree db
* **features** — memory, context tree, shell history, audit log
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "privacy": {
        "telemetry": False,
        "cloud_sync": False,
        "local_models_only": False,
        "encryption_enabled": False,
        "encryption_key_path": "~/.vega/encryption.key",
        "audit_log": True,
    },
    "model": {
        "provider": "openrouter",
        "name": "deepseek/deepseek-v4-flash",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "paths": {
        "data_dir": "~/.vega/data",
        "chromadb_dir": "~/.vega/chromadb",
        "context_tree_db": "~/.vega/context_tree.db",
    },
    "features": {
        "memory": True,
        "context_tree": True,
        "shell_history": True,
        "audit_log": True,
    },
}

REQUIRED_TOP_LEVEL = {"privacy", "model", "paths", "features"}

REQUIRED_FIELDS: Dict[str, set] = {
    "privacy": {"telemetry", "cloud_sync", "local_models_only", "audit_log"},
    "model": {"provider", "name"},
    "paths": {"data_dir"},
    "features": {"memory", "context_tree"},
}


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------


class Config:
    """Encapsulates the Vega YAML configuration.

    Attributes:
        path: Filesystem path to the config YAML file.
        data: The parsed configuration dictionary (top-level keys only).
    """

    def __init__(self, path: Optional[Path | str] = None) -> None:
        """Load config from *path* (default ``~/.vega/config.yaml``).

        Args:
            path: Explicit path to the config file.  If ``None``, uses
                ``~/.vega/config.yaml``.

        Raises:
            FileNotFoundError: If the config file does not exist.
            ValueError: If the config is malformed or missing required fields.
        """
        self.path = Path(path).expanduser() if path else _default_config_path()
        if not self.path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.path}\n"
                "Run `vega init` to create one."
            )
        with open(self.path, "r", encoding="utf-8") as f:
            raw: Any = yaml.safe_load(f) or {}

        if not isinstance(raw, dict):
            raise ValueError(f"Config file must contain a YAML mapping (dict), got {type(raw).__name__}")

        self.data: Dict[str, Any] = raw
        self._validate()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Check that required top-level keys and fields are present.

        Missing optional fields are filled from ``DEFAULT_CONFIG``.
        Missing *required* fields raise ``ValueError``.
        """
        # Ensure all top-level sections exist
        missing_top = REQUIRED_TOP_LEVEL - set(self.data.keys())
        if missing_top:
            raise ValueError(
                f"Config is missing required top-level section(s): {', '.join(sorted(missing_top))}"
            )

        for section, required_fields in REQUIRED_FIELDS.items():
            section_data = self.data.get(section, {})
            missing = required_fields - set(section_data.keys())
            if missing:
                raise ValueError(
                    f"Config section '{section}' is missing required field(s): "
                    f"{', '.join(sorted(missing))}"
                )
            # Fill optional defaults for this section
            defaults = DEFAULT_CONFIG.get(section, {})
            for key, default_val in defaults.items():
                if key not in section_data:
                    section_data[key] = default_val

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific config value.

        Args:
            section: Top-level section name (e.g. ``"model"``).
            key: Key within that section.
            default: Fallback if the key is not found.

        Returns:
            The config value, or *default*.
        """
        return self.data.get(section, {}).get(key, default)

    def section(self, name: str) -> Dict[str, Any]:
        """Return an entire config section as a dict.

        Args:
            name: Section name.

        Returns:
            The section dict, or an empty dict if the section doesn't exist.
        """
        return dict(self.data.get(name, {}))

    @property
    def privacy(self) -> Dict[str, Any]:
        """Shortcut to the ``privacy`` section."""
        return self.section("privacy")

    @property
    def model(self) -> Dict[str, Any]:
        """Shortcut to the ``model`` section."""
        return self.section("model")

    @property
    def paths(self) -> Dict[str, Any]:
        """Shortcut to the ``paths`` section."""
        return self.section("paths")

    @property
    def features(self) -> Dict[str, Any]:
        """Shortcut to the ``features`` section."""
        return self.section("features")

    # ------------------------------------------------------------------
    # Path resolution helpers
    # ------------------------------------------------------------------

    def resolve_path(self, key: str, default: str = "") -> Path:
        """Resolve a path key from the ``paths`` section, expanding ``~``.

        Args:
            key: Key under ``paths`` (e.g. ``"data_dir"``).
            default: Fallback if key is not present.

        Returns:
            An absolute ``Path``.
        """
        raw = self.paths.get(key, default)
        return Path(raw).expanduser()

    @property
    def data_dir(self) -> Path:
        """``data_dir`` from ``paths``, fully resolved."""
        return self.resolve_path("data_dir", "~/.vega/data")

    @property
    def chromadb_dir(self) -> Path:
        """``chromadb_dir`` from ``paths``, fully resolved."""
        return self.resolve_path("chromadb_dir", "~/.vega/chromadb")

    @property
    def context_tree_db_path(self) -> Path:
        """``context_tree_db`` from ``paths``, fully resolved."""
        return self.resolve_path("context_tree_db", "~/.vega/context_tree.db")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, path: Optional[Path | str] = None) -> None:
        """Write the current config back to disk as YAML.

        Args:
            path: Override output path (defaults to ``self.path``).
        """
        p = Path(path).expanduser() if path else self.path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.data, f, default_flow_style=False, sort_keys=False)
        self.path = p

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_default(cls, path: Optional[Path | str] = None) -> "Config":
        """Create a new ``Config`` with defaults and write it to disk.

        Args:
            path: Where to write the config (default ``~/.vega/config.yaml``).

        Returns:
            A ``Config`` instance backed by the newly written file.
        """
        dest = Path(path).expanduser() if path else _default_config_path()
        dest.parent.mkdir(parents=True, exist_ok=True)

        # Deep-copy the defaults so mutations don't leak
        import copy

        data = copy.deepcopy(DEFAULT_CONFIG)
        with open(dest, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

        cfg = cls.__new__(cls)
        cfg.path = dest
        cfg.data = data
        return cfg

    def __repr__(self) -> str:
        return f"Config(path={self.path!r})"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_config_path() -> Path:
    return Path.home() / ".vega" / "config.yaml"
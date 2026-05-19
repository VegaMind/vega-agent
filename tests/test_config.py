"""Tests for the Vega config system (``vega.config``)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from vega.config import (
    Config,
    DEFAULT_CONFIG,
    REQUIRED_TOP_LEVEL,
    REQUIRED_FIELDS,
)


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_config_dir() -> Path:
    """Return a temporary directory to simulate ``~/.vega/``."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def valid_config_dict() -> dict:
    """Return a valid minimal config dict."""
    return {
        "privacy": {
            "telemetry": False,
            "cloud_sync": False,
            "local_models_only": False,
            "audit_log": True,
        },
        "model": {
            "provider": "openrouter",
            "name": "deepseek/deepseek-v4-flash",
        },
        "paths": {
            "data_dir": "~/.vega/data",
        },
        "features": {
            "memory": True,
            "context_tree": True,
        },
    }


@pytest.fixture
def valid_config_path(tmp_config_dir: Path, valid_config_dict: dict) -> Path:
    """Write a valid config file and return its path."""
    path = tmp_config_dir / "config.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(valid_config_dict, f)
    return path


# ═════════════════════════════════════════════════════════════════════════
# Loading
# ═════════════════════════════════════════════════════════════════════════


class TestConfigLoading:
    def test_load_valid_config(self, valid_config_path: Path):
        """Loading a valid config should succeed."""
        cfg = Config(valid_config_path)
        assert cfg.path == valid_config_path
        assert cfg.get("model", "provider") == "openrouter"

    def test_file_not_found(self):
        """Loading a non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            Config(Path("/nonexistent/vega/config.yaml"))

    def test_not_a_dict(self, tmp_config_dir: Path):
        """Config with a non-dict root should raise ValueError."""
        path = tmp_config_dir / "config.yaml"
        with open(path, "w") as f:
            f.write("just a string\n")
        with pytest.raises(ValueError, match="YAML mapping"):
            Config(path)

    def test_missing_top_level_section(self, tmp_config_dir: Path, valid_config_dict: dict):
        """Missing a top-level section should raise ValueError."""
        bad = dict(valid_config_dict)
        del bad["privacy"]
        path = tmp_config_dir / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(bad, f)
        with pytest.raises(ValueError, match="privacy"):
            Config(path)

    def test_missing_required_field(self, tmp_config_dir: Path, valid_config_dict: dict):
        """Missing a required field inside a section should raise ValueError."""
        bad = dict(valid_config_dict)
        del bad["model"]["provider"]
        path = tmp_config_dir / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(bad, f)
        with pytest.raises(ValueError, match="provider"):
            Config(path)


# ═════════════════════════════════════════════════════════════════════════
# Defaults
# ═════════════════════════════════════════════════════════════════════════


class TestConfigDefaults:
    def test_optional_fields_filled(self, tmp_config_dir: Path, valid_config_dict: dict):
        """Optional fields not present in the file should be filled from defaults."""
        minimal = {
            "privacy": {"telemetry": False, "cloud_sync": False, "local_models_only": False, "audit_log": True},
            "model": {"provider": "openrouter", "name": "deepseek/deepseek-v4-flash"},
            "paths": {"data_dir": "~/.vega/data"},
            "features": {"memory": True, "context_tree": True},
        }
        path = tmp_config_dir / "config.yaml"
        with open(path, "w") as f:
            yaml.safe_dump(minimal, f)
        cfg = Config(path)
        # Should have default temperature and max_tokens
        assert cfg.get("model", "temperature") == 0.7
        assert cfg.get("model", "max_tokens") == 4096
        # Should have default chromadb_dir
        assert "chromadb_dir" in cfg.paths

    def test_create_default(self, tmp_config_dir: Path):
        """create_default should write a full config with defaults."""
        path = tmp_config_dir / "config.yaml"
        cfg = Config.create_default(path)
        assert path.exists()
        assert cfg.get("model", "provider") == "openrouter"
        assert cfg.get("privacy", "telemetry") is False
        assert cfg.get("features", "memory") is True

    def test_create_default_no_path(self, monkeypatch):
        """create_default with no path should use ~/.vega/config.yaml."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td)
            monkeypatch.setattr(Path, "home", lambda: fake_home)
            cfg = Config.create_default()
            expected = fake_home / ".vega" / "config.yaml"
            assert cfg.path == expected
            assert expected.exists()


# ═════════════════════════════════════════════════════════════════════════
# Accessors
# ═════════════════════════════════════════════════════════════════════════


class TestConfigAccessors:
    def test_get(self, valid_config_path: Path):
        cfg = Config(valid_config_path)
        assert cfg.get("model", "provider") == "openrouter"
        assert cfg.get("nonexistent", "key", "fallback") == "fallback"

    def test_section(self, valid_config_path: Path):
        cfg = Config(valid_config_path)
        model = cfg.section("model")
        assert model["provider"] == "openrouter"
        assert cfg.section("nonexistent") == {}

    def test_properties(self, valid_config_path: Path):
        cfg = Config(valid_config_path)
        assert cfg.privacy["telemetry"] is False
        assert cfg.model["name"] == "deepseek/deepseek-v4-flash"
        assert cfg.features["memory"] is True
        assert "data_dir" in cfg.paths

    def test_resolve_path(self, valid_config_path: Path, tmp_config_dir: Path):
        """resolve_path should expand ~ to home."""
        cfg = Config(valid_config_path)
        resolved = cfg.resolve_path("data_dir")
        assert str(resolved).startswith("/")
        assert "vega" in str(resolved)


# ═════════════════════════════════════════════════════════════════════════
# Save
# ═════════════════════════════════════════════════════════════════════════


class TestConfigSave:
    def test_save(self, valid_config_path: Path):
        """Saving should persist changes to disk."""
        cfg = Config(valid_config_path)
        cfg.data["model"]["provider"] = "anthropic"
        cfg.save()
        # Reload
        cfg2 = Config(valid_config_path)
        assert cfg2.get("model", "provider") == "anthropic"

    def test_save_to_new_path(self, valid_config_path: Path, tmp_config_dir: Path):
        """Saving to a different path should write there."""
        cfg = Config(valid_config_path)
        new_path = tmp_config_dir / "new_config.yaml"
        cfg.save(new_path)
        assert new_path.exists()
        cfg2 = Config(new_path)
        assert cfg2.get("model", "provider") == "openrouter"


# ═════════════════════════════════════════════════════════════════════════
# DEFAULT_CONFIG structure
# ═════════════════════════════════════════════════════════════════════════


class TestDefaultsStructure:
    def test_default_has_required_sections(self):
        assert set(DEFAULT_CONFIG.keys()) == REQUIRED_TOP_LEVEL

    def test_default_has_required_fields(self):
        for section, fields in REQUIRED_FIELDS.items():
            for field in fields:
                assert field in DEFAULT_CONFIG[section], (
                    f"Required field '{field}' missing from DEFAULT_CONFIG['{section}']"
                )

    def test_default_is_deep_copyable(self):
        import copy
        d = copy.deepcopy(DEFAULT_CONFIG)
        d["model"]["provider"] = "changed"
        assert DEFAULT_CONFIG["model"]["provider"] == "openrouter"
"""Tests for the Vega CLI (``vega.cli``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from vega import __version__
from vega.cli import main

# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def runner() -> CliRunner:
    """Return a Click CliRunner for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def fake_vega_dir(tmp_path: Path) -> Path:
    """Create a minimal fake ~/.vega with a usable config."""
    vega_dir = tmp_path / ".vega"
    vega_dir.mkdir(parents=True)
    (vega_dir / "data").mkdir()
    (vega_dir / "audit").mkdir()
    (vega_dir / "chromadb").mkdir()

    import yaml
    config = {
        "privacy": {
            "telemetry": False,
            "cloud_sync": False,
            "local_models_only": False,
            "encryption_enabled": False,
            "audit_log": True,
        },
        "model": {
            "provider": "openrouter",
            "name": "deepseek/deepseek-v4-flash",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        "paths": {
            "data_dir": str(vega_dir / "data"),
            "chromadb_dir": str(vega_dir / "chromadb"),
        },
        "features": {
            "memory": True,
            "context_tree": True,
            "shell_history": True,
            "audit_log": True,
        },
    }
    config_path = vega_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)

    return vega_dir


# ═════════════════════════════════════════════════════════════════════════
# --version
# ═════════════════════════════════════════════════════════════════════════


class TestVersion:
    def test_version_flag(self, runner: CliRunner):
        """``vega --version`` should print the version and exit."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


# ═════════════════════════════════════════════════════════════════════════
# vega init
# ═════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_init_auto(self, runner: CliRunner, tmp_path: Path):
        """``vega init --auto`` should create ~/.vega/config.yaml."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = runner.invoke(main, ["init", "--auto"])
            assert result.exit_code == 0, result.output
            config_path = tmp_path / ".vega" / "config.yaml"
            assert config_path.exists(), f"Config not found at {config_path}"
            assert (tmp_path / ".vega" / "data").is_dir()
            assert (tmp_path / ".vega" / "audit").is_dir()
            assert (tmp_path / ".vega" / "chromadb").is_dir()

    def test_init_auto_idempotent(self, runner: CliRunner, monkeypatch, tmp_path: Path):
        """Running init --auto twice should be safe."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result1 = runner.invoke(main, ["init", "--auto"])
        assert result1.exit_code == 0
        result2 = runner.invoke(main, ["init", "--auto"])
        assert result2.exit_code == 0
        # The second invocation should prompt — but with auto it should just re-create
        config_path = tmp_path / ".vega" / "config.yaml"
        assert config_path.exists()

    def test_init_creates_directories(self, runner: CliRunner, monkeypatch, tmp_path: Path):
        """``vega init --auto`` should create all required directories."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(main, ["init", "--auto"])
        assert result.exit_code == 0
        assert (tmp_path / ".vega").is_dir()
        assert (tmp_path / ".vega" / "data").is_dir()
        assert (tmp_path / ".vega" / "audit").is_dir()
        assert (tmp_path / ".vega" / "chromadb").is_dir()

    def test_init_auto_writes_valid_yaml(self, runner: CliRunner, monkeypatch, tmp_path: Path):
        """The config written by init --auto should be valid YAML."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        runner.invoke(main, ["init", "--auto"])
        import yaml
        config_path = tmp_path / ".vega" / "config.yaml"
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "privacy" in data
        assert "model" in data
        assert "paths" in data
        assert "features" in data


# ═════════════════════════════════════════════════════════════════════════
# vega status
# ═════════════════════════════════════════════════════════════════════════


class TestStatus:
    def test_status_without_config(self, runner: CliRunner):
        """``vega status`` should work even without a config (graceful fallback)."""
        result = runner.invoke(main, ["status"])
        # Should not crash
        assert result.exit_code == 0, result.output
        assert "Vega" in result.output or "Version" in result.output or "Status" in result.output

    def test_status_with_config(self, runner: CliRunner, monkeypatch, fake_vega_dir: Path):
        """``vega status`` should show config details when available."""
        monkeypatch.setattr(Path, "home", lambda: fake_vega_dir.parent)
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0, result.output
        assert "Version" in result.output
        assert "openrouter" in result.output or "OpenRouter" in result.output


# ═════════════════════════════════════════════════════════════════════════
# vega audit
# ═════════════════════════════════════════════════════════════════════════


class TestAudit:
    def test_audit_no_entries(self, runner: CliRunner):
        """``vega audit`` should handle empty audit gracefully."""
        result = runner.invoke(main, ["audit"])
        assert result.exit_code == 0
        # May show "no entries" or just empty output
        assert result.exit_code == 0

    def test_audit_list_files(self, runner: CliRunner):
        """``vega audit --all`` should show log files."""
        result = runner.invoke(main, ["audit", "--all"])
        assert result.exit_code == 0

    def test_audit_count(self, runner: CliRunner):
        """``vega audit --count`` should work."""
        result = runner.invoke(main, ["audit", "--count"])
        assert result.exit_code == 0


# ═════════════════════════════════════════════════════════════════════════
# vega privacy
# ═════════════════════════════════════════════════════════════════════════


class TestPrivacy:
    def test_privacy(self, runner: CliRunner):
        """``vega privacy`` should display privacy status."""
        result = runner.invoke(main, ["privacy"])
        assert result.exit_code == 0, result.output
        assert "Privacy" in result.output or "Status" in result.output or "local" in result.output

    def test_privacy_shows_scope_info(self, runner: CliRunner):
        """Privacy command should mention data boundary scopes."""
        result = runner.invoke(main, ["privacy"])
        assert result.exit_code == 0
        assert "local" in result.output or "shareable" in result.output


# ═════════════════════════════════════════════════════════════════════════
# vega encrypt
# ═════════════════════════════════════════════════════════════════════════


class TestEncrypt:
    def test_encrypt_gen_key(self, runner: CliRunner):
        """``vega encrypt --gen-key`` should print a Fernet key."""
        result = runner.invoke(main, ["encrypt", "--gen-key"])
        assert result.exit_code == 0
        assert "Fernet key" in result.output or "key" in result.output.lower()

    def test_encrypt_no_args(self, runner: CliRunner):
        """``vega encrypt`` without args should show usage."""
        result = runner.invoke(main, ["encrypt"])
        assert result.exit_code != 0  # should error
        assert "Usage" in result.output or "encrypt" in result.output.lower()


# ═════════════════════════════════════════════════════════════════════════
# vega migrate
# ═════════════════════════════════════════════════════════════════════════


class TestMigrate:
    def test_migrate_no_args(self, runner: CliRunner):
        """``vega migrate`` without args should show error."""
        result = runner.invoke(main, ["migrate"])
        assert result.exit_code != 0  # requires --from-obsidian

    def test_migrate_not_a_vault(self, runner: CliRunner, tmp_path: Path):
        """``vega migrate --from-obsidian /path`` to a non-vault should error."""
        empty_dir = tmp_path / "not_a_vault"
        empty_dir.mkdir()
        result = runner.invoke(main, ["migrate", "--from-obsidian", str(empty_dir)])
        # Should detect it's not a vault and exit with error
        assert result.exit_code == 1
        assert "doesn't look" in result.output or "no" in result.output.lower()

    def test_migrate_dry_run(self, runner: CliRunner, tmp_path: Path):
        """``vega migrate --from-obsidian /path --dry-run`` should list files."""
        vault = tmp_path / "my_vault"
        vault.mkdir()
        (vault / ".obsidian").mkdir()
        (vault / "note1.md").write_text("# Hello\nThis is a note.")
        (vault / "note2.md").write_text("# World\nAnother note.")

        result = runner.invoke(main, ["migrate", "--from-obsidian", str(vault), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Dry run" in result.output
        assert "note1.md" in result.output or "Markdown" in result.output


# ═════════════════════════════════════════════════════════════════════════
# vega ask
# ═════════════════════════════════════════════════════════════════════════


class TestAsk:
    def test_ask_no_api_key(self, runner: CliRunner, monkeypatch, tmp_path: Path):
        """``vega ask`` without API key should show error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(main, ["ask", "Hello"])
        assert result.exit_code != 0
        assert "API key" in result.output


# ═════════════════════════════════════════════════════════════════════════
# vega shell
# ═════════════════════════════════════════════════════════════════════════


class TestShell:
    def test_shell_no_api_key(self, runner: CliRunner, monkeypatch, tmp_path: Path):
        """``vega shell`` without API key should show error."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        result = runner.invoke(main, ["shell"], input="/exit\n")
        assert result.exit_code != 0
        assert "API key" in result.output


# ═════════════════════════════════════════════════════════════════════════
# Help
# ═════════════════════════════════════════════════════════════════════════


class TestHelp:
    def test_main_help(self, runner: CliRunner):
        """``vega --help`` should list all commands."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        # Check for all required commands
        for cmd in ["init", "ask", "shell", "status", "audit", "privacy", "encrypt", "migrate"]:
            assert cmd in result.output, f"Command '{cmd}' not found in help output"

    def test_command_help(self, runner: CliRunner):
        """Each command should have a --help flag."""
        for cmd in ["init", "status", "audit", "privacy", "encrypt", "migrate"]:
            result = runner.invoke(main, [cmd, "--help"])
            assert result.exit_code == 0, f"{cmd} --help failed: {result.output}"

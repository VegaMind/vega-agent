"""Comprehensive tests for the Vega Privacy Layer + Audit system."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from vega.privacy import (
    ALL_SCOPES,
    SCOPE_CONTEXT_FOR_LLM,
    SCOPE_LOCAL,
    SCOPE_SHAREABLE,
    AgentOutput,
    UserData,
    count_entries,
    decrypt,
    decrypt_file,
    derive_key,
    encrypt,
    encrypt_file,
    generate_key,
    list_log_files,
    log_audit,
    read_all,
    read_recent,
)
from vega.privacy.audit import _ensure_audit_dir, _todays_log_path
from vega.gateway import (
    EXTERNAL_TARGETS,
    LOCAL_TARGETS,
    GatewayResult,
    route_llm_call,
    route_tool_call,
)


# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _isolate_audit(monkeypatch, tmp_path):
    """Redirect audit log to a temp directory so tests don't pollute ~/.vega."""
    fake_dir = tmp_path / ".vega" / "audit"
    fake_dir.mkdir(parents=True)

    def mock_ensure_dir():
        return fake_dir

    def mock_todays():
        date_str = "2026-05-19"
        return fake_dir / f"{date_str}.jsonl"

    monkeypatch.setattr("vega.privacy.audit._ensure_audit_dir", mock_ensure_dir)
    monkeypatch.setattr("vega.privacy.audit._todays_log_path", mock_todays)
    yield


# ═════════════════════════════════════════════════════════════════════════
# Boundary: UserData
# ═════════════════════════════════════════════════════════════════════════


class TestUserData:
    def test_default_scope(self):
        ud = UserData()
        assert ud.scope == SCOPE_SHAREABLE

    def test_valid_scopes(self):
        for s in ALL_SCOPES:
            ud = UserData(scope=s, content="hello")
            assert ud.scope == s

    def test_invalid_scope_raises(self):
        with pytest.raises(ValueError, match="Invalid scope"):
            UserData(scope="forbidden")

    def test_content_summary_short(self):
        ud = UserData(content="Hello, world!")
        assert ud.content_summary() == "Hello, world!"

    def test_content_summary_long(self):
        long_text = "A" * 200
        ud = UserData(content=long_text)
        summary = ud.content_summary(max_chars=80)
        assert len(summary) == 80
        assert summary.endswith("...")

    def test_content_hash(self):
        ud = UserData(content="hello")
        h = ud.content_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_content_hash_deterministic(self):
        ud1 = UserData(content="same data")
        ud2 = UserData(content="same data")
        assert ud1.content_hash() == ud2.content_hash()

    def test_source_and_tag(self):
        ud = UserData(content="x", source="test", tag="my-tag")
        assert ud.source == "test"
        assert ud.tag == "my-tag"


# ═════════════════════════════════════════════════════════════════════════
# Boundary: AgentOutput
# ═════════════════════════════════════════════════════════════════════════


class TestAgentOutput:
    def test_defaults(self):
        ao = AgentOutput()
        assert ao.output_type == "text"
        assert ao.target == ""
        assert ao.content_hash == ""
        assert ao.llm_used is None

    def test_from_content(self):
        ao = AgentOutput.from_content("hello world", target="stdout")
        assert ao.output_type == "text"
        assert ao.target == "stdout"
        assert ao.llm_used is None
        assert len(ao.content_hash) == 64

    def test_from_content_with_llm(self):
        ao = AgentOutput.from_content("response", llm_used="gpt-4")
        assert ao.llm_used == "gpt-4"
        assert ao.content_hash != ""

    def test_timestamp_iso(self):
        ao = AgentOutput()
        # ISO 8601 format check
        assert "T" in ao.timestamp
        assert ao.timestamp.endswith("+00:00") or "+" in ao.timestamp


# ═════════════════════════════════════════════════════════════════════════
# Audit log
# ═════════════════════════════════════════════════════════════════════════


class TestAuditLog:
    def test_log_creates_entry(self):
        audit_id = log_audit(
            action="test_action",
            target="test_target",
            model_used="test-model",
            data_summary="test data",
            why="testing",
        )
        assert len(audit_id) == 12
        assert all(c in "0123456789abcdef" for c in audit_id)

    def test_log_writes_to_file(self):
        log_audit(action="test", target="tgt")
        path = _todays_log_path()
        assert path.exists()
        content = path.read_text()
        assert "test" in content

    def test_read_recent_returns_entries(self):
        for i in range(5):
            log_audit(action=f"action_{i}", target=f"tgt_{i}")
        entries = read_recent(lines=3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0]["action"] == "action_4"

    def test_read_recent_empty_when_no_file(self):
        entries = read_recent(lines=10)
        assert entries == []

    def test_read_all_generator(self):
        for i in range(3):
            log_audit(action=f"gen_{i}", target="t")
        entries = list(read_all())
        assert len(entries) == 3
        # Oldest first
        assert entries[0]["action"] == "gen_0"

    def test_list_log_files(self):
        log_audit(action="a", target="t")
        files = list_log_files()
        assert len(files) >= 1
        assert all(f.suffix == ".jsonl" for f in files)

    def test_count_entries(self):
        assert count_entries() == 0
        log_audit(action="a", target="t")
        assert count_entries() == 1
        log_audit(action="b", target="t")
        assert count_entries() == 2

    def test_entry_structure(self):
        audit_id = log_audit(
            action="llm_invoke",
            target="openai-chat",
            model_used="gpt-4",
            data_summary="user prompt",
            why="User asked a question",
            extra={"tokens": 150},
        )
        path = _todays_log_path()
        with open(path) as f:
            entry = json.loads(f.readline())

        assert entry["audit_id"] == audit_id
        assert entry["action"] == "llm_invoke"
        assert entry["target"] == "openai-chat"
        assert entry["model_used"] == "gpt-4"
        assert entry["data_summary"] == "user prompt"
        assert entry["why"] == "User asked a question"
        assert entry["tokens"] == 150
        assert "timestamp" in entry

    def test_extra_optional(self):
        log_audit(action="simple", target="t")
        path = _todays_log_path()
        with open(path) as f:
            entry = json.loads(f.readline())
        assert entry["action"] == "simple"


# ═════════════════════════════════════════════════════════════════════════
# Gateway
# ═════════════════════════════════════════════════════════════════════════


class TestGateway:
    def test_route_tool_call_returns_audit_id(self):
        result = route_tool_call(
            action="llm_invoke",
            target="openai-chat",
            data="hello world",
            model_used="gpt-4",
            why="testing",
        )
        assert isinstance(result, GatewayResult)
        assert result.ok is True
        assert result.blocked is False
        assert len(result.audit_id) == 12
        assert result.data == "hello world"

    def test_route_tool_call_with_userdata_shareable(self):
        ud = UserData(scope=SCOPE_SHAREABLE, content="share this", source="test")
        result = route_tool_call(
            action="tool_call",
            target="openai-chat",
            data=ud,
            why="sharing data",
        )
        assert result.ok is True
        assert result.blocked is False

    def test_route_tool_call_block_local_to_external(self):
        ud = UserData(scope=SCOPE_LOCAL, content="my secret key", source="config")
        result = route_tool_call(
            action="tool_call",
            target="openai-chat",
            data=ud,
            why="trying to send secret",
        )
        assert result.ok is False
        assert result.blocked is True
        assert "cannot be sent" in result.reason
        assert "blocked" in result.reason.lower()

    def test_route_tool_call_context_for_llm_to_local_ok(self):
        ud = UserData(
            scope=SCOPE_CONTEXT_FOR_LLM,
            content="personal notes",
            source="user-input",
        )
        result = route_tool_call(
            action="llm_invoke",
            target="local-llm",
            data=ud,
            why="local inference",
        )
        assert result.ok is True
        assert result.blocked is False

    def test_route_llm_call_external(self):
        result = route_llm_call(
            prompt="Hello, how are you?",
            target="openrouter-chat",
            model="deepseek/deepseek-v4",
        )
        assert result.ok is True
        assert result.blocked is False
        assert result.audit_id != ""

    def test_route_llm_call_local(self):
        result = route_llm_call(
            prompt="Summarize my notes",
            target="local-llm",
            model="llama-3.2-3b",
        )
        assert result.ok is True
        assert result.blocked is False

    def test_gateway_audits_blocked_action(self):
        ud = UserData(scope=SCOPE_LOCAL, content="secret")
        result = route_tool_call(
            action="tool_call",
            target="openai-chat",
            data=ud,
            why="should be blocked",
        )
        assert result.blocked is True
        # Check that it was logged as a blocked action
        entries = read_recent(lines=1)
        assert len(entries) == 1
        assert "blocked" in entries[0]["action"]

    def test_route_with_raw_string_local_target(self):
        result = route_tool_call(
            action="file_read",
            target="file-read",
            data="/etc/passwd",
            why="checking file",
        )
        assert result.ok is True

    def test_route_with_raw_string_to_external(self):
        result = route_tool_call(
            action="api_call",
            target="external-api",
            data="some data",
            why="api test",
        )
        assert result.ok is True

    def test_gateway_preserves_data(self):
        data = {"key": "value", "nested": [1, 2, 3]}
        result = route_tool_call(
            action="json_test",
            target="local-llm",
            data=str(data),
            why="data preservation test",
        )
        assert result.data == str(data)
        assert result.ok is True


# ═════════════════════════════════════════════════════════════════════════
# Encryption
# ═════════════════════════════════════════════════════════════════════════


class TestEncryption:
    def test_generate_key(self):
        key = generate_key()
        assert isinstance(key, bytes)
        assert len(key) > 0

    def test_encrypt_decrypt_roundtrip(self):
        key = generate_key()
        plaintext = "Hello, Vega!"
        token = encrypt(plaintext, key)
        assert token != plaintext.encode("utf-8")
        decrypted = decrypt(token, key)
        assert decrypted.decode("utf-8") == plaintext

    def test_encrypt_decrypt_bytes(self):
        key = generate_key()
        plaintext = b"bytes data"
        token = encrypt(plaintext, key)
        decrypted = decrypt(token, key)
        assert decrypted == plaintext

    def test_derive_key(self):
        key, salt = derive_key("mypassword")
        assert isinstance(key, bytes)
        assert len(salt) == 16

    def test_derive_key_deterministic(self):
        key1, salt1 = derive_key("samepass", salt=b"0123456789abcdef")
        key2, salt2 = derive_key("samepass", salt=b"0123456789abcdef")
        assert key1 == key2

    def test_derive_key_different_salt(self):
        key1, _ = derive_key("password")
        key2, _ = derive_key("password")
        assert key1 != key2  # different random salts

    def test_encrypt_file_roundtrip(self, tmp_path):
        src = tmp_path / "secret.txt"
        src.write_text("This is a secret message.")
        key = generate_key()
        enc_path = tmp_path / "secret.txt.encrypted"

        encrypt_file(str(src), str(enc_path), key)
        assert enc_path.exists()
        assert enc_path.read_bytes() != src.read_bytes()

        decrypted = decrypt_file(str(enc_path), key)
        assert decrypted.decode("utf-8") == "This is a secret message."

    def test_decrypt_file_to_disk(self, tmp_path):
        src = tmp_path / "notes.txt"
        src.write_text("private notes")
        key = generate_key()
        enc = tmp_path / "notes.enc"
        encrypt_file(str(src), str(enc), key)

        out = tmp_path / "notes_decrypted.txt"
        decrypt_file(str(enc), key, str(out))
        assert out.read_text() == "private notes"


# ═════════════════════════════════════════════════════════════════════════
# Integration: end-to-end audit flow
# ═════════════════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_flow(self):
        """A realistic scenario: route several calls and verify audit trail."""
        # 1. Route a shareable LLM call
        r1 = route_llm_call(
            prompt="What is the weather?",
            target="openrouter-chat",
            model="deepseek/deepseek-v4",
            why="User asked about weather",
        )
        assert r1.ok is True

        # 2. Route a local file read
        r2 = route_tool_call(
            action="file_read",
            target="file-read",
            data="/home/user/notes.md",
            why="Read user notes",
        )
        assert r2.ok is True

        # 3. Try to send local data externally (should be blocked)
        ud = UserData(scope=SCOPE_LOCAL, content="api_key_12345", source="env")
        r3 = route_tool_call(
            action="llm_invoke",
            target="openai-chat",
            data=ud,
            why="Attempt to send API key",
        )
        assert r3.ok is False
        assert r3.blocked is True

        # 4. Verify audit trail has all 3 entries
        entries = read_recent(lines=10)
        assert len(entries) == 3

        actions = [e["action"] for e in entries]
        assert "llm_invoke" in actions
        assert "file_read" in actions
        assert "blocked_llm_invoke" in actions

    def test_multiple_days_logging(self, monkeypatch, tmp_path):
        """Simulate entries on different dates."""
        import datetime

        fake_dir = tmp_path / ".vega" / "audit"
        fake_dir.mkdir(parents=True, exist_ok=True)

        day1_path = fake_dir / "2026-01-01.jsonl"
        day2_path = fake_dir / "2026-01-02.jsonl"

        # Write entries manually
        import json
        import uuid

        for path in [day1_path, day2_path]:
            with open(path, "w") as f:
                entry = {
                    "audit_id": uuid.uuid4().hex[:12],
                    "timestamp": "2026-01-01T00:00:00",
                    "action": "test",
                    "target": "t",
                    "model_used": None,
                    "data_summary": "",
                    "why": "",
                }
                f.write(json.dumps(entry) + "\n")

        # Mock list_log_files to use our fake dir
        monkeypatch.setattr(
            "vega.privacy.audit._ensure_audit_dir",
            lambda: fake_dir,
        )

        files = list_log_files()
        assert len(files) == 2
        assert all(isinstance(f, Path) for f in files)
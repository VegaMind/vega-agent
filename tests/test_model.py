"""Tests for vega.model — multi-provider LLM routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vega.model.providers import OpenAIProvider, OpenRouterProvider
from vega.model.router import ModelRouter, ModelRouterError

# ═════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.Client so no real HTTP calls are made."""
    with patch.object(httpx, "Client", autospec=True) as mock:
        # httpx.Client() returns a context manager
        context_mgr = mock.return_value
        # with ... as client: yields the context manager's __enter__
        client_instance = context_mgr.__enter__.return_value

        # Default successful response
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": "Hello from mock!"}}],
            "model": "mock-model",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        client_instance.post.return_value = response
        yield mock


@pytest.fixture
def mock_api_key_file(tmp_path: Path) -> Path:
    """Create a temporary ~/.vega/.api_key file."""
    vega_dir = tmp_path / ".vega"
    vega_dir.mkdir(parents=True)
    key_file = vega_dir / ".api_key"
    key_file.write_text("sk-test-api-key-from-file\n")
    return key_file


@pytest.fixture
def old_format_config() -> dict:
    """Old flat config format."""
    return {
        "model": {
            "provider": "openrouter",
            "name": "deepseek/deepseek-v4-flash",
            "temperature": 0.7,
            "max_tokens": 4096,
        }
    }


@pytest.fixture
def new_format_config() -> dict:
    """New providers-list config format."""
    return {
        "model": {
            "providers": [
                {"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                {"name": "openai", "model": "gpt-4o"},
            ],
            "temperature": 0.5,
            "max_tokens": 2048,
        }
    }


@pytest.fixture
def success_response_json():
    """Standard successful OpenAI-compatible response."""

    def _make(content: str = "Mock response") -> dict:
        return {
            "choices": [{"message": {"content": content}}],
            "model": "mock-model",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

    return _make


# ═════════════════════════════════════════════════════════════════════════
# Provider: supports_config
# ═════════════════════════════════════════════════════════════════════════


class TestProviderSelection:
    """Test that each provider correctly identifies its config."""

    def test_openrouter_supports_openrouter_config(self):
        """OpenRouterProvider should match config with name='openrouter'."""
        config = {"name": "openrouter", "model": "deepseek/deepseek-v4-flash"}
        assert OpenRouterProvider.supports_config(config) is True

    def test_openrouter_rejects_openai_config(self):
        """OpenRouterProvider should NOT match config with name='openai'."""
        config = {"name": "openai", "model": "gpt-4o"}
        assert OpenRouterProvider.supports_config(config) is False

    def test_openai_supports_openai_config(self):
        """OpenAIProvider should match config with name='openai'."""
        config = {"name": "openai", "model": "gpt-4o"}
        assert OpenAIProvider.supports_config(config) is True

    def test_openai_rejects_openrouter_config(self):
        """OpenAIProvider should NOT match config with name='openrouter'."""
        config = {"name": "openrouter", "model": "deepseek/deepseek-v4-flash"}
        assert OpenAIProvider.supports_config(config) is False

    def test_both_reject_unknown_provider(self):
        """Neither provider should match an unknown name."""
        config = {"name": "unknown", "model": "some-model"}
        assert OpenRouterProvider.supports_config(config) is False
        assert OpenAIProvider.supports_config(config) is False


# ═════════════════════════════════════════════════════════════════════════
# Provider: complete (mocked HTTP)
# ═════════════════════════════════════════════════════════════════════════


class TestOpenRouterProvider:
    """Test OpenRouterProvider.complete with mocked HTTP."""

    def test_successful_complete(self, mock_httpx_client, success_response_json):
        """A successful call returns content, model, provider, usage."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = (
            success_response_json("Hello from OpenRouter!")
        )

        result = OpenRouterProvider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
            api_key="sk-test-key",
        )

        assert result["content"] == "Hello from OpenRouter!"
        assert result["provider"] == "openrouter"
        assert result["model"] == "mock-model"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 5
        assert result["usage"]["total_tokens"] == 15

    def test_posts_correct_url_and_headers(self, mock_httpx_client):
        """Verify the HTTP request is sent to the right endpoint with expected headers."""
        OpenRouterProvider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
            api_key="sk-test-key",
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        # Should have called __enter__ context manager
        client.post.assert_called_once()
        call_args = client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "openrouter.ai" in str(url)

    def test_timeout_raises_exception(self, mock_httpx_client):
        """Timeout should propagate as an exception."""

        def _timeout(*args, **kwargs):
            raise httpx.TimeoutException("Request timed out")

        mock_httpx_client.return_value.__enter__.return_value.post.side_effect = _timeout

        with pytest.raises(httpx.TimeoutException):
            OpenRouterProvider.complete(
                messages=[{"role": "user", "content": "Hi"}],
                config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                api_key="sk-test-key",
            )

    def test_http_error_raises_exception(self, mock_httpx_client):
        """HTTP errors should propagate."""

        def _http_error(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=MagicMock(status_code=401),
            )

        mock_httpx_client.return_value.__enter__.return_value.post.side_effect = _http_error

        with pytest.raises(httpx.HTTPStatusError):
            OpenRouterProvider.complete(
                messages=[{"role": "user", "content": "Hi"}],
                config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                api_key="sk-test-key",
            )


class TestOpenAIProvider:
    """Test OpenAIProvider.complete with mocked HTTP."""

    def test_successful_complete(self, mock_httpx_client, success_response_json):
        """A successful call returns content, model, provider, usage."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = (
            success_response_json("Hello from OpenAI!")
        )

        result = OpenAIProvider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            config={"name": "openai", "model": "gpt-4o"},
            api_key="sk-test-key",
        )

        assert result["content"] == "Hello from OpenAI!"
        assert result["provider"] == "openai"
        assert result["model"] == "mock-model"
        assert result["usage"]["prompt_tokens"] == 10

    def test_posts_correct_url(self, mock_httpx_client):
        """Verify the HTTP request is sent to OpenAI's endpoint."""
        OpenAIProvider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            config={"name": "openai", "model": "gpt-4o"},
            api_key="sk-test-key",
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        client.post.assert_called_once()
        call_args = client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
        assert "api.openai.com" in str(url)


# ═════════════════════════════════════════════════════════════════════════
# Router: old format config
# ═════════════════════════════════════════════════════════════════════════


class TestRouterOldFormat:
    """ModelRouter with old flat config format."""

    def test_old_format_routes_to_correct_provider(
        self, mock_httpx_client, old_format_config, success_response_json
    ):
        """Old flat config should route to OpenRouterProvider."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = (
            success_response_json("Success with old format!")
        )

        router = ModelRouter(config=old_format_config)
        result = router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="sk-test-key",
        )

        assert result["content"] == "Success with old format!"
        assert result["provider"] == "openrouter"

    def test_old_format_without_api_key_uses_file(
        self, mock_httpx_client, old_format_config, success_response_json, tmp_path
    ):
        """When no api_key param given, reads from ~/.vega/.api_key."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = (
            success_response_json("Key from file!")
        )

        # Create the api key file in tmp_path and patch Path.home()
        vega_dir = tmp_path / ".vega"
        vega_dir.mkdir(parents=True)
        key_file = vega_dir / ".api_key"
        key_file.write_text("sk-from-file\n")

        with patch.object(Path, "home", return_value=tmp_path):
            router = ModelRouter(config=old_format_config)
            result = router.complete(
                messages=[{"role": "user", "content": "Hi"}],
            )

        assert result["content"] == "Key from file!"
        # Verify the key was actually passed to the provider
        client = client_instance
        client.post.assert_called_once()
        call_kwargs = client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-from-file"


# ═════════════════════════════════════════════════════════════════════════
# Router: new format config
# ═════════════════════════════════════════════════════════════════════════


class TestRouterNewFormat:
    """ModelRouter with new providers-list config format."""

    def test_new_format_uses_first_provider(
        self, mock_httpx_client, new_format_config, success_response_json
    ):
        """With providers list, first matching provider should be used."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.return_value.json.return_value = (
            success_response_json("First provider wins!")
        )

        router = ModelRouter(config=new_format_config)
        result = router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="sk-test-key",
        )

        assert result["content"] == "First provider wins!"
        # Should have used openrouter (first in list)
        assert result["provider"] == "openrouter"

    def test_ordered_fallback_first_fails_second_succeeds(
        self, mock_httpx_client, new_format_config, success_response_json
    ):
        """If first provider fails, fallback to second."""
        # Create a mock response for the second (success) call
        second_response = MagicMock(spec=httpx.Response)
        second_response.status_code = 200
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = success_response_json("OpenAI fallback!")

        responses = iter(
            [
                # First call fails
                Exception("OpenRouter down"),
                # Second call succeeds
                second_response,
            ]
        )

        def side_effect(*args, **kwargs):
            resp = next(responses)
            if isinstance(resp, Exception):
                raise resp
            return resp

        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.side_effect = side_effect

        router = ModelRouter(config=new_format_config)
        # Override: the side_effect should trigger fallback
        result = router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="sk-test-key",
        )

        assert result["content"] == "OpenAI fallback!"
        assert result["provider"] == "openai"
        # Should have been called twice
        assert client_instance.post.call_count == 2

    def test_all_providers_fail_raises_error(
        self, mock_httpx_client, new_format_config
    ):
        """When all providers fail, ModelRouterError should be raised."""
        client_instance = mock_httpx_client.return_value.__enter__.return_value
        client_instance.post.side_effect = Exception("Provider down")

        router = ModelRouter(config=new_format_config)

        with pytest.raises(ModelRouterError) as exc_info:
            router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                api_key="sk-test-key",
            )

        assert "All providers failed" in str(exc_info.value)
        # Should have tried both providers
        assert client_instance.post.call_count == 2

    def test_no_providers_configured_raises_error(self):
        """If no providers section and no flat provider, raise error."""
        config = {"model": {}}
        router = ModelRouter(config=config)

        with pytest.raises(ModelRouterError) as exc_info:
            router.complete(
                messages=[{"role": "user", "content": "Hi"}],
                api_key="sk-test-key",
            )

        assert "No providers configured" in str(exc_info.value)


# ═════════════════════════════════════════════════════════════════════════
# Router: temperature and max_tokens from config
# ═════════════════════════════════════════════════════════════════════════


class TestRouterConfigParams:
    """Verify temperature and max_tokens are passed from config."""

    def test_temperature_and_max_tokens_passed_to_provider(
        self, mock_httpx_client, new_format_config
    ):
        """Temperature and max_tokens from config should be sent in request body."""
        # Configure a custom temp/max_tokens
        config = {
            "model": {
                "providers": [
                    {"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                ],
                "temperature": 0.3,
                "max_tokens": 512,
            }
        }

        router = ModelRouter(config=config)
        router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="sk-test-key",
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        call_kwargs = client.post.call_args[1]
        json_body = call_kwargs.get("json", {})
        assert json_body.get("temperature") == 0.3
        assert json_body.get("max_tokens") == 512

    def test_default_temperature_and_max_tokens(
        self, mock_httpx_client, new_format_config
    ):
        """If config doesn't specify, defaults should be used."""
        config = {
            "model": {
                "providers": [
                    {"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
                ],
            }
        }

        router = ModelRouter(config=config)
        router.complete(
            messages=[{"role": "user", "content": "Hi"}],
            api_key="sk-test-key",
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        call_kwargs = client.post.call_args[1]
        json_body = call_kwargs.get("json", {})
        assert json_body.get("temperature") == 0.7
        assert json_body.get("max_tokens") == 4096


# ═════════════════════════════════════════════════════════════════════════
# Provider: request body structure
# ═════════════════════════════════════════════════════════════════════════


class TestProviderRequestBody:
    """Verify the JSON request body is correctly structured."""

    def test_openrouter_request_body(self, mock_httpx_client):
        """OpenRouter sends messages, model, temperature, max_tokens."""
        OpenRouterProvider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
            api_key="sk-test-key",
            temperature=0.5,
            max_tokens=100,
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        call_kwargs = client.post.call_args[1]
        json_body = call_kwargs.get("json", {})

        assert json_body["model"] == "deepseek/deepseek-v4-flash"
        assert json_body["messages"] == [{"role": "user", "content": "Hello"}]
        assert json_body["temperature"] == 0.5
        assert json_body["max_tokens"] == 100

    def test_openai_request_body(self, mock_httpx_client):
        """OpenAI sends messages, model, temperature, max_tokens."""
        OpenAIProvider.complete(
            messages=[{"role": "user", "content": "Hello"}],
            config={"name": "openai", "model": "gpt-4o"},
            api_key="sk-test-key",
            temperature=0.8,
            max_tokens=200,
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        call_kwargs = client.post.call_args[1]
        json_body = call_kwargs.get("json", {})

        assert json_body["model"] == "gpt-4o"
        assert json_body["messages"] == [{"role": "user", "content": "Hello"}]
        assert json_body["temperature"] == 0.8
        assert json_body["max_tokens"] == 200

    def test_openrouter_sends_referer_header(self, mock_httpx_client):
        """OpenRouter must include HTTP-Referer header."""
        OpenRouterProvider.complete(
            messages=[{"role": "user", "content": "Hi"}],
            config={"name": "openrouter", "model": "deepseek/deepseek-v4-flash"},
            api_key="sk-test-key",
        )

        client = mock_httpx_client.return_value.__enter__.return_value
        call_kwargs = client.post.call_args[1]
        headers = call_kwargs.get("headers", {})
        assert headers.get("HTTP-Referer") == "https://vega-agent.local"

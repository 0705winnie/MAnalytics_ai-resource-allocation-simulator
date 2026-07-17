"""
API-backed assistant client with mock fallback.

API keys are loaded from environment variables or a local `.env` file. Never
commit a real API key. The `.env` file is intentionally git-ignored.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .mock_agent import get_mock_response
    from .prompt_templates import build_system_prompt, build_user_prompt
except ImportError:
    from mock_agent import get_mock_response
    from prompt_templates import build_system_prompt, build_user_prompt


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AZURE_API_VERSION = "v1"
DEFAULT_MAX_OUTPUT_TOKENS = 500
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AssistantClientConfig:
    """Configuration for the API-backed assistant."""

    provider: str
    api_key: str | None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_version: str = DEFAULT_AZURE_API_VERSION
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


def load_env_file(env_path: str | Path | None = None) -> None:
    """
    Load simple KEY=VALUE pairs from `.env` without requiring python-dotenv.

    Existing environment variables are not overwritten.
    """
    path = Path(env_path) if env_path else _default_env_path()
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def get_config() -> AssistantClientConfig:
    """Read assistant configuration from environment variables."""
    load_env_file()
    provider = os.getenv("OPENAI_PROVIDER", "openai").strip().lower()
    if provider == "azure":
        return AssistantClientConfig(
            provider=provider,
            api_key=os.getenv("AZURE_OPENAI_API_KEY") or None,
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT", DEFAULT_MODEL),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT") or None,
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT") or None,
            azure_api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION",
                DEFAULT_AZURE_API_VERSION,
            ),
        )

    return AssistantClientConfig(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY") or None,
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )


def is_api_configured() -> bool:
    """Return whether a non-empty API key is available."""
    config = get_config()
    if config.provider == "azure":
        return bool(
            config.api_key
            and config.azure_endpoint
            and config.azure_deployment
        )
    return bool(config.api_key)


def get_assistant_response(
    student_message: str,
    *,
    extra_context: str | None = None,
    use_mock_on_failure: bool = True,
) -> dict[str, Any]:
    """
    Return an assistant response using the OpenAI API when configured.

    If no API key is available, or if the API call fails and fallback is enabled,
    the mock agent is used instead.
    """
    config = get_config()
    if not _has_required_config(config):
        fallback = get_mock_response(student_message)
        fallback["source"] = "mock"
        fallback["fallback_reason"] = f"missing_{config.provider}_configuration"
        return fallback

    try:
        message = _call_openai_chat(
            student_message=student_message,
            config=config,
            extra_context=extra_context,
        )
        return {
            "message": message,
            "topic": "llm",
            "follow_up_questions": [],
            "source": config.provider,
            "model": config.model,
        }
    except Exception as exc:
        if not use_mock_on_failure:
            raise

        fallback = get_mock_response(student_message)
        fallback["source"] = "mock"
        fallback["fallback_reason"] = f"api_error: {type(exc).__name__}"
        return fallback


def _call_openai_chat(
    *,
    student_message: str,
    config: AssistantClientConfig,
    extra_context: str | None,
) -> str:
    """Call the configured chat completions endpoint using the standard library."""
    url = _chat_completions_url(config)
    payload = {
        "messages": [
            {"role": "system", "content": build_system_prompt(extra_context)},
            {"role": "user", "content": build_user_prompt(student_message)},
        ],
        "temperature": 0.3,
        "max_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
    }
    if config.provider == "openai" or _uses_azure_v1_endpoint(config):
        payload["model"] = config.model

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=_request_headers(config),
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=config.timeout_seconds,
        ) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    parsed = json.loads(body)
    return parsed["choices"][0]["message"]["content"].strip()


def _has_required_config(config: AssistantClientConfig) -> bool:
    """Return whether the selected provider has enough config to make a call."""
    if config.provider == "azure":
        return bool(
            config.api_key
            and config.azure_endpoint
            and config.azure_deployment
        )
    return bool(config.api_key)


def _chat_completions_url(config: AssistantClientConfig) -> str:
    """Build the provider-specific chat completions URL."""
    if config.provider == "azure":
        endpoint = (config.azure_endpoint or "").rstrip("/")
        deployment = config.azure_deployment or ""
        if _uses_azure_v1_endpoint(config):
            return f"{endpoint}/chat/completions?api-version={config.azure_api_version}"

        return (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={config.azure_api_version}"
        )

    return f"{config.base_url.rstrip('/')}/chat/completions"


def _request_headers(config: AssistantClientConfig) -> dict[str, str]:
    """Build provider-specific request headers."""
    headers = {"Content-Type": "application/json"}
    if config.provider == "azure":
        headers["api-key"] = config.api_key or ""
    else:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def _uses_azure_v1_endpoint(config: AssistantClientConfig) -> bool:
    """Return whether Azure endpoint already includes `/openai/v1`."""
    endpoint = (config.azure_endpoint or "").rstrip("/")
    return endpoint.endswith("/openai/v1")




def _default_env_path() -> Path:
    """Return the repository-level `.env` path."""
    return Path(__file__).resolve().parents[2] / ".env"


if __name__ == "__main__":
    print("Assistant API configured:", is_api_configured())
    while True:
        try:
            message = input("\nStudent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting assistant client.")
            break

        response = get_assistant_response(message)
        print(f"\nAssistant [{response['source']}]> {response['message']}")

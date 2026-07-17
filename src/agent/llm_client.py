"""
API-backed assistant client with mock fallback.

The OpenAI API key is loaded from environment variables or a local `.env` file.
Never commit a real API key. The `.env` file is intentionally git-ignored.
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
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AssistantClientConfig:
    """Configuration for the API-backed assistant."""

    api_key: str | None
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
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
    return AssistantClientConfig(
        api_key=os.getenv("OPENAI_API_KEY") or None,
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        base_url=os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )


def is_api_configured() -> bool:
    """Return whether a non-empty API key is available."""
    return bool(get_config().api_key)


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
    if not config.api_key:
        fallback = get_mock_response(student_message)
        fallback["source"] = "mock"
        fallback["fallback_reason"] = "missing_api_key"
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
            "source": "openai",
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
    """Call OpenAI's chat completions endpoint using the standard library."""
    url = f"{config.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": build_system_prompt(extra_context)},
            {"role": "user", "content": build_user_prompt(student_message)},
        ],
        "temperature": 0.3,
    }

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
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


def _default_env_path() -> Path:
    """Return the repository-level `.env` path."""
    return Path(__file__).resolve().parents[2] / ".env"


if __name__ == "__main__":
    print("OpenAI API configured:", is_api_configured())
    while True:
        try:
            message = input("\nStudent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting assistant client.")
            break

        response = get_assistant_response(message)
        print(f"\nAssistant [{response['source']}]> {response['message']}")

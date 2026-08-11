"""
LLM client wrapper for the dashboard AI assistant.

The frontend never sees API keys. The backend chooses the provider from
LLM_PROVIDER:
    LLM_PROVIDER=mock   -> deterministic rule-based assistant
    LLM_PROVIDER=azure  -> Azure OpenAI / Azure AI Foundry
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.mock_agent import get_mock_response
from app.services.prompt_templates import build_system_prompt


class LLMError(Exception):
    """Raised when an LLM call fails in a way the API endpoint should handle."""


@dataclass(frozen=True)
class LLMResult:
    content: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseLLMClient(ABC):
    """Shared interface for real and mock assistant clients."""

    @abstractmethod
    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
        max_output_tokens: int = 500,
    ) -> LLMResult:
        """Return public content/provider plus internal token usage."""


class AzureLLMClient(BaseLLMClient):
    """Calls Azure OpenAI using the official openai Python package."""

    def __init__(self) -> None:
        self._endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        self._api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
        self._api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01").strip()

        if not self._endpoint:
            raise LLMError(
                "AZURE_OPENAI_ENDPOINT is not set. Add it to your .env file, "
                "or set LLM_PROVIDER=mock to run locally."
            )
        if not self._api_key:
            raise LLMError(
                "AZURE_OPENAI_API_KEY is not set. Add it to your .env file, "
                "or set LLM_PROVIDER=mock to run locally."
            )

        try:
            from openai import AzureOpenAI, OpenAI
        except ImportError as e:
            raise LLMError("The 'openai' package is not installed. Run: pip install openai") from e

        if self._uses_azure_v1_endpoint():
            self._client = OpenAI(base_url=self._endpoint, api_key=self._api_key)
        else:
            self._client = AzureOpenAI(
                azure_endpoint=self._endpoint,
                api_key=self._api_key,
                api_version=self._api_version,
            )

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        messages = build_llm_messages(message, history, context)

        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=max_output_tokens,
                temperature=0.3,
            )
        except Exception as e:
            raise LLMError(f"Azure OpenAI API call failed: {e}") from e

        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        return LLMResult(
            content=content.strip(),
            provider="azure",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )

    def _uses_azure_v1_endpoint(self) -> bool:
        return self._endpoint.endswith("/openai/v1")


class MockLLMClient(BaseLLMClient):
    """Uses the comprehensive rule-based Stream D mock agent."""

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
        max_output_tokens: int = 500,
    ) -> LLMResult:
        response = get_mock_response(message)
        content = _format_mock_content(response, context)
        return LLMResult(content=content, provider="mock")


def build_llm_messages(
    message: str,
    history: list[dict] | None = None,
    context: dict | None = None,
) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": build_system_prompt(context)}]
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": message})
    return messages


def estimate_text_tokens(value: str) -> int:
    """Count with the configured model tokenizer, with a modern safe fallback."""

    import tiktoken

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
    try:
        encoding = tiktoken.encoding_for_model(deployment)
    except KeyError:
        # Azure deployment aliases may not be public model names. Current 4o/4.1
        # families use o200k_base, making it the most reliable local fallback.
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(value))


def estimate_input_tokens(
    message: str,
    history: list[dict] | None = None,
    context: dict | None = None,
) -> int:
    # Four tokens per message plus a small assistant-priming allowance follows
    # OpenAI's documented chat-message counting convention.
    messages = build_llm_messages(message, history, context)
    return 2 + sum(4 + estimate_text_tokens(item["content"]) for item in messages)


def _format_mock_content(response: dict[str, object], context: dict | None = None) -> str:
    """Convert the structured mock-agent response into dashboard chat text."""
    parts: list[str] = []

    if context and context.get("current_month"):
        parts.append(f"*(Month {context['current_month']} - mock mode)*")

    message = str(response.get("message", "")).strip()
    if message:
        parts.append(message)

    follow_ups = response.get("follow_up_questions") or []
    if follow_ups:
        parts.append(
            "Questions to consider:\n"
            + "\n".join(f"- {question}" for question in follow_ups)
        )

    return "\n\n".join(parts).strip()


def get_llm_client() -> BaseLLMClient:
    """Read LLM_PROVIDER and return the matching client."""
    provider = get_llm_provider_name()

    if provider == "mock":
        return MockLLMClient()
    if provider == "azure":
        return AzureLLMClient()

    raise LLMError(f"Unknown LLM_PROVIDER='{provider}'. Valid values: 'azure', 'mock'.")


def get_llm_provider_name() -> str:
    provider = os.environ.get("LLM_PROVIDER", "azure").strip().lower()
    if provider not in {"azure", "mock"}:
        raise LLMError(f"Unknown LLM_PROVIDER='{provider}'. Valid values: 'azure', 'mock'.")
    return provider

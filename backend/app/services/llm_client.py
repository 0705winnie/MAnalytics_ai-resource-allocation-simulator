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

from app.services.mock_agent import get_mock_response
from app.services.prompt_templates import build_system_prompt


class LLMError(Exception):
    """Raised when an LLM call fails in a way the API endpoint should handle."""


class BaseLLMClient(ABC):
    """Shared interface for real and mock assistant clients."""

    @abstractmethod
    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        """Return {"content": str, "provider": str}."""


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
        messages = [{"role": "system", "content": build_system_prompt(context)}]
        for turn in history or []:
            role = turn.get("role")
            content = turn.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                max_tokens=600,
                temperature=0.3,
            )
        except Exception as e:
            raise LLMError(f"Azure OpenAI API call failed: {e}") from e

        content = response.choices[0].message.content or ""
        return {"content": content.strip(), "provider": "azure"}

    def _uses_azure_v1_endpoint(self) -> bool:
        return self._endpoint.endswith("/openai/v1")


class MockLLMClient(BaseLLMClient):
    """Uses the comprehensive rule-based Stream D mock agent."""

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
    ) -> dict:
        response = get_mock_response(message)
        content = _format_mock_content(response, context)
        return {"content": content, "provider": "mock"}


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
    provider = os.environ.get("LLM_PROVIDER", "azure").strip().lower()

    if provider == "mock":
        return MockLLMClient()
    if provider == "azure":
        return AzureLLMClient()

    raise LLMError(f"Unknown LLM_PROVIDER='{provider}'. Valid values: 'azure', 'mock'.")

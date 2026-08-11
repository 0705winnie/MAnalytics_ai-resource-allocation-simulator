"""Azure/OpenAI client wrapper for the student AI assistant."""

from __future__ import annotations

import inspect
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.core.config import DEFAULT_LLM_OUTPUT_TOKEN_SAFETY_CEILING
from app.services.prompt_templates import build_system_prompt


class LLMError(Exception):
    """Base class for safe application-level LLM failures."""


class LLMConfigurationError(LLMError):
    """The real provider cannot be called because local configuration is invalid."""


class LLMProviderError(LLMError):
    """A sanitized provider failure suitable for structured server logging."""

    def __init__(
        self,
        *,
        exception_class: str,
        status_code: int | None,
        provider_code: str | None,
        sanitized_message: str,
    ) -> None:
        super().__init__("AI provider request failed")
        self.exception_class = exception_class
        self.status_code = status_code
        self.provider_code = provider_code
        self.sanitized_message = sanitized_message


@dataclass(frozen=True)
class LLMResult:
    content: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None


class BaseLLMClient(ABC):
    """Shared contract retained for a small, testable provider boundary."""

    @abstractmethod
    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
        max_output_tokens: int = DEFAULT_LLM_OUTPUT_TOKEN_SAFETY_CEILING,
    ) -> LLMResult:
        """Generate one real-provider response."""


class AzureLLMClient(BaseLLMClient):
    """Call Azure OpenAI using the official OpenAI Python package."""

    def __init__(self) -> None:
        self._endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        self._api_key = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
        self._api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01").strip()

        if not self._endpoint:
            raise LLMConfigurationError("AZURE_OPENAI_ENDPOINT is not configured")
        if not self._api_key:
            raise LLMConfigurationError("AZURE_OPENAI_API_KEY is not configured")
        if not self._deployment:
            raise LLMConfigurationError("AZURE_OPENAI_DEPLOYMENT is not configured")

        try:
            from openai import AzureOpenAI, OpenAI
        except ImportError as exc:
            raise LLMConfigurationError("The OpenAI provider package is unavailable") from exc

        try:
            if self._uses_azure_v1_endpoint():
                self._client = OpenAI(base_url=self._endpoint, api_key=self._api_key)
            else:
                self._client = AzureOpenAI(
                    azure_endpoint=self._endpoint,
                    api_key=self._api_key,
                    api_version=self._api_version,
                )
        except Exception as exc:
            raise LLMConfigurationError(
                f"Provider client initialization failed ({type(exc).__name__})"
            ) from exc

    def generate_response(
        self,
        message: str,
        history: list[dict] | None = None,
        context: dict | None = None,
        max_output_tokens: int = DEFAULT_LLM_OUTPUT_TOKEN_SAFETY_CEILING,
    ) -> LLMResult:
        messages = build_llm_messages(message, history, context)
        token_limit = (
            {"max_completion_tokens": max_output_tokens}
            if self._uses_azure_v1_endpoint()
            else {"max_tokens": max_output_tokens}
        )

        try:
            response = self._client.chat.completions.create(
                model=self._deployment,
                messages=messages,
                temperature=0.3,
                **token_limit,
            )
        except Exception as exc:
            raise _provider_error(exc) from exc

        try:
            choice = response.choices[0]
            content = choice.message.content or ""
            usage = getattr(response, "usage", None)
            return LLMResult(
                content=content.strip(),
                provider="azure",
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                finish_reason=getattr(choice, "finish_reason", None),
            )
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                exception_class=type(exc).__name__,
                status_code=None,
                provider_code="invalid_provider_response",
                sanitized_message="Provider returned an unexpected response shape",
            ) from exc

    def _uses_azure_v1_endpoint(self) -> bool:
        return self._endpoint.endswith("/openai/v1")


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


def validate_llm_client_request(
    client: BaseLLMClient,
    *,
    message: str,
    history: list[dict] | None,
    context: dict | None,
    max_output_tokens: int,
) -> None:
    """Catch adapter-contract errors before a paid-call reservation is committed."""

    try:
        inspect.signature(client.generate_response).bind(
            message=message,
            history=history,
            context=context,
            max_output_tokens=max_output_tokens,
        )
    except TypeError as exc:
        raise LLMConfigurationError(
            "Provider adapter does not satisfy the application request contract"
        ) from exc


def estimate_text_tokens(value: str) -> int:
    """Count with the configured deployment tokenizer and a modern fallback."""

    import tiktoken

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini").strip()
    try:
        encoding = tiktoken.encoding_for_model(deployment)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(value))


def estimate_messages_tokens(messages: list[dict[str, str]]) -> int:
    return 2 + sum(4 + estimate_text_tokens(item["content"]) for item in messages)


def estimate_input_tokens(
    message: str,
    history: list[dict] | None = None,
    context: dict | None = None,
) -> int:
    return estimate_messages_tokens(build_llm_messages(message, history, context))


def get_llm_client() -> AzureLLMClient:
    """Return the product's only production provider."""

    return AzureLLMClient()


def _provider_error(exc: Exception) -> LLMProviderError:
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)

    provider_code = getattr(exc, "code", None)
    body = getattr(exc, "body", None)
    if provider_code is None and isinstance(body, dict):
        nested = body.get("error")
        provider_code = (
            nested.get("code")
            if isinstance(nested, dict)
            else body.get("code")
        )

    return LLMProviderError(
        exception_class=type(exc).__name__,
        status_code=int(status_code) if status_code is not None else None,
        provider_code=str(provider_code) if provider_code is not None else None,
        sanitized_message=_sanitize_provider_message(str(exc)),
    )


def _sanitize_provider_message(message: str) -> str:
    sanitized = " ".join(message.split())
    for name in (
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "DATABASE_URL",
        "JWT_SECRET",
    ):
        value = os.environ.get(name)
        if value:
            sanitized = sanitized.replace(value, "[REDACTED]")
    sanitized = re.sub(r"https?://[^\s]+", "[REDACTED_URL]", sanitized)
    return sanitized[:400]

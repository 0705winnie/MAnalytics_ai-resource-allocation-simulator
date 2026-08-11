"""Authenticated, student-specific Azure AI assistant routes."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_student
from app.core.config import LLMQuotaSettings, get_llm_quota_settings
from app.db.session import get_db
from app.services.llm_client import (
    LLMConfigurationError,
    LLMProviderError,
    build_llm_messages,
    estimate_messages_tokens,
    estimate_text_tokens,
    get_llm_client,
    validate_llm_client_request,
)
from app.services.llm_quota import (
    LLMQuotaExceeded,
    UsageStatus,
    get_usage_status,
    reconcile_llm_call,
    reserve_llm_call,
)
from app.services.student_ai_context import StudentAIContextAssembler


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai-assistant", tags=["AI Assistant"])
MAX_CONVERSATION_TURNS = 6


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=10_000)


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=10_000)
    history: list[ChatMessage] = Field(default_factory=list)
    draft_policy_code: str = Field(..., min_length=1, max_length=50_000)
    draft_params: dict[str, float] = Field(default_factory=dict)

    @field_validator("draft_params")
    @classmethod
    def require_finite_params(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(parameter) for parameter in value.values()):
            raise ValueError("Draft policy parameters must be finite numbers")
        return value


class AssistantUsageResponse(BaseModel):
    calls_used: int
    calls_limit: int
    resets_at: datetime
    metered: bool

    @classmethod
    def from_status(cls, value: UsageStatus) -> "AssistantUsageResponse":
        return cls(
            calls_used=value.calls_used,
            calls_limit=value.calls_limit,
            resets_at=value.resets_at,
            metered=value.metered,
        )


class AssistantResponse(BaseModel):
    content: str
    provider: Literal["azure"]
    response_limited: bool
    usage: AssistantUsageResponse


def bounded_complete_history(history: list[ChatMessage]) -> list[dict[str, str]]:
    """Return only the latest six complete user/assistant turns."""

    turns: list[tuple[ChatMessage, ChatMessage]] = []
    index = 0
    while index < len(history) - 1:
        first = history[index]
        second = history[index + 1]
        if first.role == "user" and second.role == "assistant":
            turns.append((first, second))
            index += 2
        else:
            index += 1
    bounded = turns[-MAX_CONVERSATION_TURNS:]
    return [
        {"role": message.role, "content": message.content}
        for turn in bounded
        for message in turn
    ]


def _temporarily_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="AI Assistant is temporarily unavailable. Please try again.",
    )


@router.get("/usage", response_model=AssistantUsageResponse)
def usage(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
    settings: Annotated[LLMQuotaSettings, Depends(get_llm_quota_settings)],
) -> AssistantUsageResponse:
    return AssistantUsageResponse.from_status(
        get_usage_status(db, context.user.id, settings, metered=True)
    )


@router.post("", response_model=AssistantResponse)
def chat(
    request: AssistantRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
    settings: Annotated[LLMQuotaSettings, Depends(get_llm_quota_settings)],
) -> AssistantResponse:
    """Build authoritative context, meter one real call, and return Azure output."""

    history = bounded_complete_history(request.history)

    try:
        client = get_llm_client()
        student_context = StudentAIContextAssembler(db).build(
            context,
            message=request.message,
            draft_policy_code=request.draft_policy_code,
            draft_params=request.draft_params,
        )
        prepared_messages = build_llm_messages(
            request.message,
            history,
            student_context,
        )
        estimated_input = estimate_messages_tokens(prepared_messages)
        validate_llm_client_request(
            client,
            message=request.message,
            history=history,
            context=student_context,
            max_output_tokens=settings.llm_output_token_safety_ceiling,
        )
    except LLMConfigurationError as exc:
        logger.error(
            "AI provider configuration/preflight failed",
            extra={"exception_class": type(exc.__cause__ or exc).__name__},
        )
        raise _temporarily_unavailable() from None
    except Exception:
        db.rollback()
        logger.exception("Student AI context preparation failed")
        raise _temporarily_unavailable() from None

    try:
        reservation = reserve_llm_call(
            db,
            context.user.id,
            estimated_input,
            settings,
        )
    except LLMQuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "daily_ai_limit_reached",
                "limit_type": exc.limit_type,
                "message": str(exc),
                "resets_at": exc.resets_at.isoformat(),
            },
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI usage accounting is temporarily unavailable.",
        ) from None

    try:
        result = client.generate_response(
            message=request.message,
            history=history,
            context=student_context,
            max_output_tokens=settings.llm_output_token_safety_ceiling,
        )
    except LLMProviderError as exc:
        logger.error(
            "Azure AI provider request failed",
            extra={
                "exception_class": exc.exception_class,
                "provider_status": exc.status_code,
                "provider_code": exc.provider_code,
                "provider_message": exc.sanitized_message,
            },
        )
        raise _temporarily_unavailable() from None
    except Exception as exc:
        # The prompt and adapter signature were preflighted before reservation.
        # This guard prevents unstructured errors without logging request data.
        logger.error(
            "AI provider dispatch failed unexpectedly",
            extra={"exception_class": type(exc).__name__},
        )
        raise _temporarily_unavailable() from None

    actual_input = result.input_tokens or estimated_input
    actual_output = result.output_tokens
    if actual_output is None:
        actual_output = estimate_text_tokens(result.content)
    try:
        reconcile_llm_call(
            db,
            reservation,
            actual_input_tokens=actual_input,
            actual_output_tokens=actual_output,
            settings=settings,
        )
    except SQLAlchemyError:
        # The committed worst-case reservation remains a conservative record.
        db.rollback()

    current_usage = get_usage_status(
        db,
        context.user.id,
        settings,
        metered=True,
    )
    return AssistantResponse(
        content=result.content,
        provider="azure",
        response_limited=result.finish_reason == "length",
        usage=AssistantUsageResponse.from_status(current_usage),
    )

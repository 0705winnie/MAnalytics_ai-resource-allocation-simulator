"""
AI assistant endpoint.

POST /ai-assistant
  Receives the student's message (plus optional conversation history and
  dashboard context), returns the AI assistant's reply.

The frontend calls this as POST /api/ai-assistant.
Vite's dev proxy strips /api and forwards to /ai-assistant here.
"""

from datetime import datetime
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, require_student
from app.core.config import LLMQuotaSettings, get_llm_quota_settings
from app.db.session import get_db
from app.services.llm_client import (
    LLMError,
    estimate_input_tokens,
    estimate_text_tokens,
    get_llm_client,
    get_llm_provider_name,
)
from app.services.llm_quota import (
    LLMQuotaExceeded,
    UsageStatus,
    get_usage_status,
    reconcile_llm_call,
    reserve_llm_call,
)

router = APIRouter(prefix="/ai-assistant", tags=["AI Assistant"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str     # "user" or "assistant"
    content: str


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The student's message")
    history: List[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation turns, oldest first"
    )
    context: Optional[Dict] = Field(
        default=None,
        description=(
            "Optional dashboard state. Supported keys: "
            "current_month (int), "
            "remaining_capacity (dict[str, int]), "
            "monthly_result (dict)"
        ),
    )


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
    provider: str   # "azure" or "mock"
    usage: AssistantUsageResponse


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get("/usage", response_model=AssistantUsageResponse)
def usage(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
    settings: Annotated[LLMQuotaSettings, Depends(get_llm_quota_settings)],
) -> AssistantUsageResponse:
    try:
        provider = get_llm_provider_name()
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return AssistantUsageResponse.from_status(
        get_usage_status(
            db,
            context.user.id,
            settings,
            metered=provider != "mock",
        )
    )


@router.post("", response_model=AssistantResponse)
def chat(
    request: AssistantRequest,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_student)],
    settings: Annotated[LLMQuotaSettings, Depends(get_llm_quota_settings)],
) -> AssistantResponse:
    """
    Main AI assistant endpoint.

    The backend picks the LLM provider (Azure or mock) from the
    LLM_PROVIDER environment variable — the frontend never touches
    credentials.
    """
    history = [message.model_dump() for message in request.history]
    try:
        client = get_llm_client()
        provider = get_llm_provider_name()
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None

    reservation = None
    estimated_input = 0
    if provider != "mock":
        estimated_input = estimate_input_tokens(
            request.message,
            history,
            request.context,
        )
        try:
            reservation = reserve_llm_call(
                db,
                context.user.id,
                estimated_input,
                settings,
            )
        except LLMQuotaExceeded as exc:
            raise HTTPException(
                status_code=429,
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
                status_code=503,
                detail="AI usage accounting is temporarily unavailable.",
            ) from None

    try:
        result = client.generate_response(
            message=request.message,
            history=history,
            context=request.context,
            max_output_tokens=settings.max_llm_output_tokens_per_call,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if reservation is not None:
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
            # The committed worst-case reservation remains a safe conservative
            # record if post-provider reconciliation is temporarily unavailable.
            db.rollback()

    current_usage = get_usage_status(
        db,
        context.user.id,
        settings,
        metered=provider != "mock",
    )
    return AssistantResponse(
        content=result.content,
        provider=result.provider,
        usage=AssistantUsageResponse.from_status(current_usage),
    )

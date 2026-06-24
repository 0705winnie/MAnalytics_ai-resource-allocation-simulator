"""
AI assistant endpoint.

POST /ai-assistant
  Receives the student's message (plus optional conversation history and
  dashboard context), returns the AI assistant's reply.

The frontend calls this as POST /api/ai-assistant.
Vite's dev proxy strips /api and forwards to /ai-assistant here.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_client import LLMError, get_llm_client

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


class AssistantResponse(BaseModel):
    content: str
    provider: str   # "azure" or "mock"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("", response_model=AssistantResponse)
async def chat(request: AssistantRequest) -> AssistantResponse:
    """
    Main AI assistant endpoint.

    The backend picks the LLM provider (Azure or mock) from the
    LLM_PROVIDER environment variable — the frontend never touches
    credentials.
    """
    client = get_llm_client()

    try:
        result = client.generate_response(
            message=request.message,
            history=[m.model_dump() for m in request.history],
            context=request.context,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return AssistantResponse(**result)

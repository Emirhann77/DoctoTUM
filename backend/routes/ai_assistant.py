from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import AIChatRequest, AIChatResponse, TriageRequest, TriageResponse
from backend.services import ai_responses

router = APIRouter()


@router.post("/ai_assistant/chat", response_model=AIChatResponse)
def ai_chat(body: AIChatRequest):
    return ai_responses.chat(body.user_message, body.user_id)


@router.post("/ai_assistant/triage", response_model=TriageResponse)
def ai_triage(body: TriageRequest):
    return ai_responses.triage(
        body.symptoms,
        body.age,
        list(body.known_conditions),
        body.duration,
    )

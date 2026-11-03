"""
Cedric AI - Chat Route
========================

One endpoint: POST /api/chat/message. It's a protected route (requires
a valid login) - Cedric AI is meant to be personalized per student, so
every AI interaction should be tied to a real, authenticated user from
day one, even before there's anything user-specific to personalize
with yet.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError

from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.context_engine import build_student_context
from app.services.gemini_client import get_gemini_client

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
def send_message(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        client = get_gemini_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    messages = [m.model_dump() for m in payload.messages]
    # Phase 13: personalize with the student's saved memory, if any.
    system_instruction = build_student_context(db, current_user.id)

    try:
        reply = client.generate_reply(messages, system_instruction=system_instruction)
    except APIError as exc:
        # Don't leak raw SDK/HTTP internals to the client - translate
        # to a clean 502 (Bad Gateway: "the upstream service failed").
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc

    return ChatResponse(reply=reply)

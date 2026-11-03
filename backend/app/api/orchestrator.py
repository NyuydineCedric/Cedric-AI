"""
Cedric AI - Orchestrator Route (Phase 14)
=============================================

  POST /api/orchestrator/chat - the "smart assistant": Gemini itself
                                  decides whether to just answer, or
                                  call tools first (search files, ask
                                  documents, read/save memory).

Distinct from /api/chat/message (Phase 3, always plain conversation)
and /api/rag/ask (Phase 7-9, always document-grounded Q&A) - this
endpoint is where the model chooses between those capabilities (and
memory) itself, per request.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.orchestrator import OrchestratorRequest, OrchestratorResponse
from app.services.orchestrator import run_orchestrated_chat

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])


@router.post("/chat", response_model=OrchestratorResponse)
def orchestrated_chat(
    payload: OrchestratorRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    messages = [m.model_dump() for m in payload.messages]

    try:
        result = run_orchestrated_chat(db, current_user.id, messages)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc

    return OrchestratorResponse(**result)

"""
Cedric AI - RAG Route
=======================

  POST /api/rag/ask - answer a question grounded in the student's own
                       uploaded documents, with citations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.rag import RagAskRequest, RagAskResponse
from app.services.rag import answer_question

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/ask", response_model=RagAskResponse)
def ask(
    payload: RagAskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = answer_question(db, current_user.id, payload.question)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc

    return RagAskResponse(**result)

"""
Cedric AI - Proactive Assistance Route (Phase 24)
=====================================================

GET /api/proactive/deadlines - the student's own upcoming deadlines,
parsed from their saved Memory. Pull-based, called when the frontend
wants to show this - not a push notification.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.proactive import UpcomingDeadline
from app.services.proactive import get_upcoming_deadlines

router = APIRouter(prefix="/api/proactive", tags=["proactive"])


@router.get("/deadlines", response_model=list[UpcomingDeadline])
def deadlines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_upcoming_deadlines(db, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc
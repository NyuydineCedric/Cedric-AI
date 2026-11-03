"""
Cedric AI - Quiz Route (Phase 20)
=====================================

POST /api/quiz/generate - topic-based or document-grounded quiz.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.quiz import QuizRequest, QuizResponse
from app.services.quiz import QuizGenerationError, generate_quiz

from app.models.quiz_attempt import QuizAttempt
from app.schemas.quiz_attempt import QuizAttemptCreate, QuizAttemptOut

from app.schemas.quiz_attempt import QuizProgressEntry
from app.services.quiz import get_progress_summary

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizResponse)
def generate(
    payload: QuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = generate_quiz(
            db,
            current_user.id,
            payload.topic,
            payload.document_id,
            payload.num_questions,
            payload.difficulty,
        )
    except QuizGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini API error: {exc.message}",
        ) from exc

    return QuizResponse(**result)

@router.post("/attempts", response_model=QuizAttemptOut, status_code=status.HTTP_201_CREATED)
def record_attempt(
    payload: QuizAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.correct_count > payload.num_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="correct_count cannot exceed num_questions.",
        )

    attempt = QuizAttempt(
        owner_id=current_user.id,
        topic=payload.topic,
        document_id=payload.document_id,
        difficulty=payload.difficulty,
        num_questions=payload.num_questions,
        correct_count=payload.correct_count,
        score_ratio=payload.correct_count / payload.num_questions,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/attempts", response_model=list[QuizAttemptOut])
def list_attempts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(QuizAttempt)
        .filter(QuizAttempt.owner_id == current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
    
@router.get("/progress", response_model=list[QuizProgressEntry])
def progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_progress_summary(db, current_user.id)
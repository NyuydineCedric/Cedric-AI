from datetime import datetime

from pydantic import BaseModel, Field


class QuizAttemptCreate(BaseModel):
    topic: str | None = None
    document_id: int | None = None
    difficulty: str
    num_questions: int = Field(ge=1)
    correct_count: int = Field(ge=0)


class QuizAttemptOut(BaseModel):
    id: int
    topic: str | None
    document_id: int | None
    difficulty: str
    num_questions: int
    correct_count: int
    score_ratio: float
    created_at: datetime

    model_config = {"from_attributes": True}
    
class QuizProgressEntry(BaseModel):
    topic: str | None
    document_id: int | None
    document_filename: str | None
    attempts: int
    average_score: float
    suggested_difficulty: str
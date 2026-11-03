from typing import Literal

from pydantic import BaseModel, Field


class QuizRequest(BaseModel):
    # Provide exactly one of these - a free topic, or one of the
    # student's own documents to quiz them on.
    topic: str | None = None
    document_id: int | None = None
    num_questions: int = Field(default=5, ge=1, le=15)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]

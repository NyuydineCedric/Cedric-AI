"""
Cedric AI - Quiz Attempt Model (Phase 21a)
==============================================

Phase 20's quiz generation was stateless - a quiz was generated,
graded in the browser, and then gone. Adaptive learning (Phase 21b)
needs a history to adapt to, so this table is the first piece: one
row per completed quiz, not per question - individual question/answer
detail isn't needed for "which topics is this student weak in", and
storing it would be exactly the kind of data the project spec warns
against hoarding without a clear purpose.
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Exactly one of these was the quiz's source - mirrors QuizRequest.
    topic = Column(String, nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    difficulty = Column(String, nullable=False)
    num_questions = Column(Integer, nullable=False)
    correct_count = Column(Integer, nullable=False)
    score_ratio = Column(Float, nullable=False)  # correct_count / num_questions, precomputed for easy querying

    created_at = Column(DateTime(timezone=True), server_default=func.now())
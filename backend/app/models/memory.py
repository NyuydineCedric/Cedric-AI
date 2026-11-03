"""
Cedric AI - Memory Model (Phase 12)
======================================

Three different things the project spec is careful to keep separate,
and this codebase mirrors that separation in three different places:

  SHORT-TERM CONVERSATION CONTEXT
    -> lives only in the frontend's React state (ChatPanel.jsx) for
       the current session. Not stored in the database at all yet.

  RAG KNOWLEDGE
    -> the DocumentChunk table (Phase 5/6) - facts extracted from the
       student's own uploaded material, retrieved by semantic search.

  LONG-TERM MEMORY (this table)
    -> a small, deliberately-curated set of facts ABOUT the student
       that should persist and inform future interactions: goals,
       preferences, current projects, deadlines. NOT a transcript of
       everything ever said - see api/memory.py for why entries are
       created explicitly rather than by auto-logging every message.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base

# Deliberately a short, fixed set of categories rather than free-form
# tags - keeps memory browsable/editable instead of an unstructured
# pile, and gives the future context engine (Phase 13) an easy way to
# decide what's relevant to pull into a given prompt.
MEMORY_CATEGORIES = {"goal", "preference", "deadline", "project", "other"}


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    category = Column(String, nullable=False, default="other")
    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

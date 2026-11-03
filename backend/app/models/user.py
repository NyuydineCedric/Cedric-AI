"""
Cedric AI - User Model
========================

The `User` table is intentionally minimal in Phase 2: just what's
needed to authenticate someone. Richer profile data (programme,
academic level, enrolled courses, learning preferences - "Student
Profile" and "Personal Memory" from the architecture doc) belongs to
later phases, once we actually build features that use it. Adding
speculative columns now would be exactly the kind of premature
abstraction the project rules warn against.
"""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    # Never store plaintext passwords - only the bcrypt hash.
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

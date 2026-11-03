"""
Cedric AI - Document Model
============================

Phase 4 scope: store the *file* and *who owns it*. No text extraction,
chunking, or embeddings yet - that's Phase 5 (processing) and Phase 6
(embeddings/vector DB). Keeping "store a file" and "understand a
file's contents" as separate phases means each one is independently
testable.

`owner_id` is the single most important column in this table from a
security standpoint: every query against Document MUST filter by it.
That's what stops one student's documents from ever appearing in
another student's list - see api/documents.py for where that's
enforced.
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The name the student uploaded it as (shown in the UI).
    filename = Column(String, nullable=False)
    # A UUID-based name used on disk, so two students uploading
    # "notes.pdf" never collide and a filename can't be used to guess
    # or overwrite another file.
    stored_filename = Column(String, nullable=False, unique=True)

    content_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)

    # Phase 5: text extraction / chunking status.
    #   pending      - not processed yet (shouldn't normally be seen -
    #                  we process synchronously right after upload)
    #   completed    - chunks were created successfully
    #   unsupported  - file type has no extractor yet (e.g. images,
    #                  until the vision phase adds OCR)
    #   failed       - extraction raised an error (see processing_error)
    processing_status = Column(String, nullable=False, default="pending")
    processing_error = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Phase 6: embedding status, same states as processing_status plus
    # "unavailable" for "no GEMINI_API_KEY configured at upload time".
    embedding_status = Column(String, nullable=False, default="pending")
    embedding_error = Column(String, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    visibility = Column(String, nullable=False, default="personal")  # "personal" or "university"

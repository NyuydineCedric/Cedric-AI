"""
Cedric AI - Document Chunk Model
===================================

A "chunk" is a piece of a document small enough to embed and retrieve
individually (Phase 6/7), but large enough to still make sense read on
its own. Splitting is done per structural unit first - PDF page, DOCX
section under a heading, PPTX slide - and only sub-split further if
that unit is still too long. This is what "structure-aware chunking"
in the project spec means, as opposed to blindly cutting text every
N characters regardless of where a page or heading falls.

`owner_id` is denormalized here (duplicated from the parent Document)
rather than requiring a join for every permission check. Retrieval in
Phase 7 will run frequently and needs to filter "only this student's
chunks" as cheaply as possible - see api/documents.py for the same
ownership-filtering pattern used elsewhere.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    chunk_index = Column(Integer, nullable=False)  # order within the document
    content = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False)

    # Structural metadata - whichever applies to the source format.
    page_number = Column(Integer, nullable=True)     # PDF pages, PPTX slides
    section_title = Column(String, nullable=True)     # nearest DOCX heading

    # Phase 6: the embedding vector, stored as raw float32 bytes (see
    # services/embeddings.py for why - short version: no pgvector
    # available in this dev environment, so vectors live in a plain
    # SQLite BLOB and get compared with brute-force cosine similarity
    # instead of a proper ANN index).
    embedding = Column(LargeBinary, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

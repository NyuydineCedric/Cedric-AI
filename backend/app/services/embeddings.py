"""
Cedric AI - Embeddings & Vector Search
==========================================

AI ENGINEERING DATA FLOW:

  INPUT           -> chunk text (Phase 5 output) or a user's question
  PREPROCESSING    -> none needed - the embedding model takes raw text
  AI/MODEL         -> Gemini's embedding model turns text into a fixed
                       -length vector (a point in "meaning space" -
                       texts with similar meaning end up as nearby
                       points, regardless of exact wording)
  POSTPROCESSING   -> serialize to bytes for storage (write path), or
                       compute cosine similarity against stored vectors
                       to rank the closest matches (read path)
  OUTPUT           -> a stored vector, or a ranked list of chunks

VECTOR STORAGE DECISION:
A production setup would use pgvector (Postgres) or a dedicated vector
database with an approximate-nearest-neighbor index, so similarity
search stays fast at millions of vectors. Neither Postgres nor a
vector DB is available in this dev environment, so vectors are stored
as raw float32 bytes in a SQLite BLOB column and compared with
brute-force cosine similarity in Python/numpy. For one student's
document collection (dozens to low hundreds of chunks) that's
genuinely fast enough and gives *correct* results - it's just not
indexed for internet-scale data. Swapping to pgvector later means
changing the functions in this file, not the API routes that call
them.
"""

import numpy as np
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.gemini_client import get_gemini_client

from sqlalchemy import or_
from app.models.document import Document


def _serialize(vector: list[float]) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _deserialize(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32)


def embed_document_chunks(db: Session, document: Document) -> None:
    """Generate and store an embedding for every chunk of `document`."""
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )

    if not chunks:
        # Nothing to embed (e.g. an unsupported file type) - not a
        # failure, just nothing to do.
        document.embedding_status = "completed"
        db.commit()
        return

    try:
        client = get_gemini_client()
        vectors = client.embed_texts([c.content for c in chunks])
    except RuntimeError:
        # No GEMINI_API_KEY configured. Don't fail the upload over
        # this - the file and its extracted text are still saved and
        # usable; only semantic search over it won't work yet.
        document.embedding_status = "unavailable"
        db.commit()
        return
    except Exception as exc:  # noqa: BLE001 - any embedding-call failure
        document.embedding_status = "failed"
        document.embedding_error = str(exc)[:500]
        db.commit()
        return

    for chunk, vector in zip(chunks, vectors):
        chunk.embedding = _serialize(vector)

    document.embedding_status = "completed"
    document.embedding_error = None
    db.commit()


def embed_query(query: str) -> np.ndarray:
    client = get_gemini_client()
    [query_vector] = client.embed_texts([query])
    return np.asarray(query_vector, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def chunk_similarity_to(query_vec: np.ndarray, chunk: DocumentChunk) -> float:
    """
    Cosine similarity between an already-embedded query and one chunk.
    Returns 0.0 for a chunk with no stored embedding (e.g. it was only
    ever found via keyword search, or its document was uploaded before
    GEMINI_API_KEY was configured) rather than raising.
    """
    if chunk.embedding is None:
        return 0.0
    return cosine_similarity(query_vec, _deserialize(chunk.embedding))


def search_similar_chunks(
    db: Session, owner_id: int, query: str, top_k: int = 5, query_vec: np.ndarray | None = None
) -> list[tuple[DocumentChunk, float]]:
    if query_vec is None:
        query_vec = embed_query(query)

    # PERMISSION-AWARE RETRIEVAL (Phase 23): a chunk is visible if
    # this student owns it, OR its parent document is marked
    # 'university' (shared institutional material) - never anyone
    # else's personal upload. The join to Document is required here
    # because 'visibility' lives on the document, not denormalized
    # onto the chunk the way owner_id is.
    chunks = (
        db.query(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(
            DocumentChunk.embedding.isnot(None),
            or_(DocumentChunk.owner_id == owner_id, Document.visibility == "university"),
        )
        .all()
    )

    scored = [
        (chunk, cosine_similarity(query_vec, _deserialize(chunk.embedding)))
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
"""
Cedric AI - Semantic File Search (Phase 11)
===============================================

Different question from Phase 7-9's RAG: instead of "answer this
question using my documents," this is "find the actual FILE where I
wrote about X" - e.g. "the PDF where I wrote about PID controllers."
The student wants the document itself (to open/download), not a
generated answer.

Implementation reuses Phase 9's hybrid chunk search, then groups
matches by document and keeps each document's single best-matching
chunk as the "why this matched" explanation - exactly what the
project spec asks for: filename, match reason, and the relevant
section.

The LLM reranking step (Phase 9) is skipped here on purpose: it's
tuned for "which passage best answers this question," which is the
right question for Q&A but not for "which files are relevant" - and
skipping it saves one Gemini call per search. Vector + keyword fusion
alone is enough signal to rank documents.
"""

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.retrieval import hybrid_search


def search_documents_by_meaning(db: Session, owner_id: int, query: str, top_k: int = 5) -> list[dict]:
    # Search more chunks than the number of documents we want back,
    # since several top chunks often belong to the same document.
    ranked_chunks = hybrid_search(db, owner_id, query, top_k=15, rerank=False)

    best_per_document: dict[int, tuple[DocumentChunk, float]] = {}
    for chunk, score in ranked_chunks:
        current = best_per_document.get(chunk.document_id)
        if current is None or score > current[1]:
            best_per_document[chunk.document_id] = (chunk, score)

    ranked_documents = sorted(
        best_per_document.items(), key=lambda item: item[1][1], reverse=True
    )[:top_k]

    results = []
    for document_id, (chunk, score) in ranked_documents:
        document = db.get(Document, document_id)
        results.append(
            {
                "document_id": document.id,
                "filename": document.filename,
                "similarity": round(score, 3),
                "matched_snippet": chunk.content[:280],
                "page_number": chunk.page_number,
                "section_title": chunk.section_title,
            }
        )
    return results

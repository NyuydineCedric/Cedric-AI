"""
Cedric AI - RAG (Retrieval-Augmented Generation)
====================================================

  USER QUERY
     |
  QUERY PROCESSING     -> none extra yet (Phase 9 adds keyword search
     |                     fused with this vector search)
  RETRIEVAL             -> embed the question, cosine-similarity
     |                     search over ONLY this user's chunks
  RERANKING              -> none yet (Phase 9)
     |
  CONTEXT CONSTRUCTION  -> keep only chunks above a relevance
     |                     threshold, label each with its source
     |                     document/page so both the model and the
     |                     citations we return can point back to it
  GEMINI                 -> generate an answer constrained to ONLY
     |                     use the provided context
  VALIDATION             -> if nothing cleared the relevance bar,
     |                     skip the model call entirely and say so -
     |                     this is the difference between RAG and
     |                     "paste documents into a prompt and hope"
  CITED RESPONSE          -> answer text + the exact chunks it's
                             grounded in (Phase 8)

This is deliberately a much smaller, more constrained prompt than the
free-form Phase 3 chat: general chat is a helpful assistant with the
model's own knowledge, while /api/rag/ask is specifically "answer only
from what this student has actually uploaded, and admit it when you
can't." Keeping them as separate endpoints (rather than one blended
mode) is what lets the UI - and the student - always know which kind
of answer they're getting.
"""

from sqlalchemy.orm import Session

from app.models.document import Document
from app.services.context_engine import build_student_context
from app.services.gemini_client import get_gemini_client
from app.services.retrieval import hybrid_search

# Below this cosine-similarity score, a chunk is treated as "not
# actually relevant" rather than force-fed to the model as context.
# This is a starting heuristic, not a tuned constant - Phase 26 (RAG
# evaluation) is where thresholds like this get measured properly
# instead of guessed.
RELEVANCE_THRESHOLD = 0.5

NO_EVIDENCE_ANSWER = (
    "I couldn't find anything in your uploaded documents that answers "
    "this. Try rephrasing, or upload material that covers this topic."
)


def answer_question(db: Session, owner_id: int, question: str) -> dict:
    # Phase 9: retrieval is now hybrid (vector + keyword, fused and
    # reranked) rather than vector-only - see services/retrieval.py.
    # The chunk/score shape returned is identical, so nothing else
    # below needed to change.
    ranked = hybrid_search(db, owner_id, question, top_k=5)
    relevant = [pair for pair in ranked if pair[1] >= RELEVANCE_THRESHOLD]

    if not relevant:
            return {
            "answer": NO_EVIDENCE_ANSWER,
            "sources": [],
            "grounded": False,
            "fully_verified": None,
            "unsupported_claims": [],
        }

    document_cache: dict[int, Document] = {}

    def get_document(document_id: int) -> Document:
        if document_id not in document_cache:
            document_cache[document_id] = db.get(Document, document_id)
        return document_cache[document_id]

    context_blocks = []
    for i, (chunk, _score) in enumerate(relevant, start=1):
        document = get_document(chunk.document_id)
        location = (
            f"page {chunk.page_number}" if chunk.page_number else chunk.section_title or ""
        )
        label = f"{document.filename}" + (f", {location}" if location else "")
        context_blocks.append(f"[Source {i}: {label}]\n{chunk.content}")

    prompt = (
        "You are answering a student's question using ONLY the "
        "numbered sources below - do not use outside knowledge. Cite "
        "sources inline like [Source 1] next to the claims they "
        "support. If the sources don't fully answer the question, say "
        "plainly what's missing instead of guessing.\n\n"
        + "\n\n".join(context_blocks)
        + f"\n\nQuestion: {question}"
    )

    client = get_gemini_client()
    # Phase 13: personalization is allowed to shape tone/depth, but
    # notice it's layered on top of the "only use the sources above"
    # instruction, not a replacement for it - grounding still wins.
    system_instruction = build_student_context(db, owner_id)
    answer = client.generate_reply(
        [{"role": "user", "content": prompt}], system_instruction=system_instruction
    )

    sources = [
        {
            "document_id": chunk.document_id,
            "filename": get_document(chunk.document_id).filename,
            "page_number": chunk.page_number,
            "section_title": chunk.section_title,
            "snippet": chunk.content[:240],
            "similarity": round(score, 3),
        }
        for chunk, score in relevant
    ]

    verification = verify_groundedness(answer, context_blocks)

    return {
        "answer": answer,
        "sources": sources,
        "grounded": True,
        "fully_verified": verification["fully_grounded"],
        "unsupported_claims": verification["unsupported_claims"],
    }

"""
Phase 25: groundedness verification. Runs AFTER generation, as an
independent check - the verifier model only sees the answer and the
sources, not the reasoning that produced the answer, so it isn't just
the same model re-endorsing its own output.
"""

VERIFICATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "fully_grounded": {"type": "boolean"},
        "unsupported_claims": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["fully_grounded", "unsupported_claims"],
}


def verify_groundedness(answer: str, context_blocks: list[str]) -> dict:
    prompt = (
        "You are a strict fact-checker. Below are SOURCES, followed by an "
        "ANSWER that was supposed to be based only on those sources. "
        "Identify any specific claim in the ANSWER that is NOT actually "
        "supported by the SOURCES - do not flag reasonable summarization "
        "or phrasing differences, only claims introducing information the "
        "sources don't contain. If every claim is supported, "
        "fully_grounded should be true and unsupported_claims empty.\n\n"
        + "\n\n".join(context_blocks)
        + f"\n\nANSWER:\n{answer}"
    )

    client = get_gemini_client()
    try:
        return client.generate_structured(prompt, VERIFICATION_JSON_SCHEMA)
    except Exception:  # noqa: BLE001
        # Verification failing shouldn't hide the answer the student
        # already has - fail open with "unverified," not silently
        # crash the whole request over a check that was extra to
        # begin with.
        return {"fully_grounded": None, "unsupported_claims": []}

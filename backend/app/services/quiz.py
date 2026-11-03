"""
Cedric AI - Quiz Generation (Phase 20: Study Coach, 21a/21b: adaptive)
==========================================================================

  INPUT           -> a topic (free text) OR one of the student's own
                      document_ids
  PREPROCESSING   -> if document_id was given, pull that document's
                      extracted chunks (Phase 5) as grounding material,
                      so the quiz is actually about what the student
                      uploaded, not the model's general knowledge of
                      the subject
  AI/MODEL         -> generate_structured() - Gemini's native JSON-
                      schema output mode, not "ask for prose and hope
                      it parses"
  POSTPROCESSING   -> validate the model's response actually matches
                      what we asked for (right number of questions,
                      every correct_index in range) before it reaches
                      the student - a malformed quiz is worse than no
                      quiz
  OUTPUT           -> QuizResponse

WHY VALIDATE RATHER THAN TRUST THE SCHEMA:
`response_schema` makes Gemini's output *structurally* JSON-shaped,
but it doesn't guarantee the *values* are sane - e.g. correct_index=7
on a 4-option question would silently break the frontend. This is the
project spec's "AI hallucination/verification layer" idea applied at
small scale: check the model's own output before it becomes truth.

PHASE 21B ADDITION: get_progress_summary turns quiz-attempt history
into a weak-topic signal and a difficulty suggestion - a plain
heuristic, not an LLM call, since averaging a handful of numbers
doesn't need a model.
"""

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.quiz_attempt import QuizAttempt
from app.services.gemini_client import get_gemini_client

QUIZ_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correct_index": {"type": "integer"},
                    "explanation": {"type": "string"},
                },
                "required": ["question", "options", "correct_index", "explanation"],
            },
        },
    },
    "required": ["questions"],
}

# Cap how much document text goes into one prompt. A handful of
# chunks is plenty of material for a 5-15 question quiz; sending an
# entire large document isn't needed and just burns context.
MAX_CHUNKS = 20


class QuizGenerationError(Exception):
    """Raised when the model's output can't be trusted - route turns this into a 502."""


def _document_grounding_text(db: Session, owner_id: int, document_id: int) -> str:
    # PERMISSION-AWARE (Phase 23): accessible if this student owns it,
    # OR it's a shared 'university' document - never anyone else's
    # personal upload.
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            or_(Document.owner_id == owner_id, Document.visibility == "university"),
        )
        .first()
    )
    if document is None:
        raise QuizGenerationError("Document not found.")

    # Chunks belong to whoever uploaded the document, not the viewer -
    # same reasoning as list_document_chunks in api/documents.py
    # (Phase 22a). Filtering chunks by owner_id here would silently
    # return zero chunks for a university document uploaded by
    # someone else.
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        raise QuizGenerationError(
            "This document has no extracted text yet to quiz you on."
        )

    joined = "\n\n".join(c.content for c in chunks[:MAX_CHUNKS])
    return f"Document: {document.filename}\n\n{joined}"


def generate_quiz(
    db: Session,
    owner_id: int,
    topic: str | None,
    document_id: int | None,
    num_questions: int,
    difficulty: str,
) -> dict:
    if not topic and not document_id:
        raise QuizGenerationError("Provide either a topic or a document_id.")

        if document_id:
            grounding = _document_grounding_text(db, owner_id, document_id)
        source_instruction = (
            "Base every question ONLY on the substantive academic/technical "
            "content in the material below - do not introduce facts it "
            "doesn't contain. Do NOT ask about the document's title, "
            "filename, page count, page numbers, headers, footers, "
            "watermarks, scan/copyright notices, or any other metadata - "
            "only test understanding of the actual subject matter being "
            "taught.\n\n" + grounding
        )
    else:
        source_instruction = f"Topic: {topic}"

    prompt = (
        f"Create a {difficulty}-difficulty multiple-choice quiz with exactly "
        f"{num_questions} questions for a university student. Each question "
        "needs exactly 4 options, one correct_index (0-3), and a short "
        "explanation of why that answer is correct.\n\n" + source_instruction
    )

    client = get_gemini_client()
    result = client.generate_structured(prompt, QUIZ_JSON_SCHEMA)

    # POSTPROCESSING / VALIDATION - see module docstring for why this
    # isn't optional just because response_schema was used.
    questions = result.get("questions", [])
    if len(questions) != num_questions:
        raise QuizGenerationError(
            f"Expected {num_questions} questions but the model returned {len(questions)}."
        )
    for q in questions:
        options = q.get("options", [])
        correct_index = q.get("correct_index")
        if not isinstance(correct_index, int) or not (0 <= correct_index < len(options)):
            raise QuizGenerationError("The model returned an invalid question - please try again.")

    return {"questions": questions}


def _suggest_difficulty(average_score: float) -> str:
    if average_score >= 0.8:
        return "harder"
    if average_score < 0.5:
        return "easier"
    return "same"


def get_progress_summary(db: Session, owner_id: int) -> list[dict]:
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.owner_id == owner_id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )

    groups: dict[str, list[QuizAttempt]] = defaultdict(list)
    for attempt in attempts:
        key = attempt.topic if attempt.topic else f"document:{attempt.document_id}"
        groups[key].append(attempt)

    document_cache: dict[int, str] = {}

    def document_filename(document_id: int) -> str:
        if document_id not in document_cache:
            document = db.get(Document, document_id)
            document_cache[document_id] = document.filename if document else "Deleted document"
        return document_cache[document_id]

    summary = []
    for key, group in groups.items():
        average_score = sum(a.score_ratio for a in group) / len(group)
        # group[0] is the most recent attempt (query was ordered
        # newest-first), so its topic/document identity represents
        # this group correctly even if wording varied slightly.
        latest = group[0]
        summary.append(
            {
                "topic": latest.topic,
                "document_id": latest.document_id,
                "document_filename": document_filename(latest.document_id) if latest.document_id else None,
                "attempts": len(group),
                "average_score": round(average_score, 3),
                "suggested_difficulty": _suggest_difficulty(average_score),
            }
        )

    # Weakest average score first - that's the point of "surfacing" it.
    summary.sort(key=lambda s: s["average_score"])
    return summary
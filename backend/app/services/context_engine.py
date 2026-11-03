"""
Cedric AI - Context Engine (Phase 13)
=========================================

Before any message reaches Gemini, this decides what the model
actually needs to know about the student - not everything the
database could provide. Right now that means curated long-term memory
(Phase 12); RAG's document context is assembled separately in
services/rag.py since it's specific to one question, not a general
"who is this student" backdrop.

WHY NOT JUST SEND EVERYTHING:
Two real reasons, not just API cost: (1) Gemini's context window is
finite and irrelevant information measurably hurts response quality,
so "more context" isn't free even when it technically fits; (2) it's
a genuine privacy boundary - only this student's own data should ever
enter a prompt about them, and only the parts actually relevant to
answering.

WHY A SYSTEM INSTRUCTION, NOT AN EXTRA CHAT MESSAGE:
Gemini's API has a dedicated `system_instruction` slot for background
guidance that shapes behavior without being a visible turn in the
conversation. Using it (rather than prepending a fake "user" message
to the history) keeps the actual conversation clean and is the
technically correct tool for this job - see gemini_client.py.
"""

from sqlalchemy.orm import Session

from app.models.memory import Memory


def build_student_context(db: Session, owner_id: int) -> str | None:
    """
    Returns a compact system-instruction string summarizing what's
    remembered about this student, or None if there's nothing yet -
    callers should skip adding an empty/useless instruction.
    """
    memories = (
        db.query(Memory)
        .filter(Memory.owner_id == owner_id)
        .order_by(Memory.created_at.desc())
        .all()
    )
    if not memories:
        return None

    lines = [f"- ({m.category}) {m.content}" for m in memories]
    return (
        "You are Cedric AI, a friendly, patient study companion for a "
        "university student. Here is what's known about this student "
        "from their saved memory - use it to personalize tone and "
        "relevance, but don't just repeat it back verbatim, and don't "
        "treat it as ground truth for factual questions:\n" + "\n".join(lines)
    )

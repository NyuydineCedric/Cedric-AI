"""
Cedric AI - Proactive Assistance: Upcoming Deadlines (Phase 24)
====================================================================

  INPUT           -> this student's own Memory entries with
                      category='deadline' - never another student's,
                      same ownership boundary as everywhere else
  PREPROCESSING    -> none - raw text goes straight to the model
  AI/MODEL         -> generate_structured(): given today's date, parse
                      each deadline's free-text content into an actual
                      date the code can sort/compare
  POSTPROCESSING   -> entries the model couldn't confidently parse a
                      date from are dropped, not guessed at - a wrong
                      reminder is worse than no reminder; then sort by
                      nearest date first
  OUTPUT           -> ranked list of upcoming deadlines

This is deliberately PULL, not PUSH: the frontend asks for this list
when the student opens the app. No background scheduler, no email/
push notifications - see module-level discussion in the phase plan
for why that's a separate, larger infrastructure decision.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.services.gemini_client import get_gemini_client

DEADLINE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "deadlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "integer"},
                    "label": {"type": "string"},
                    # ISO date string, or null if the text genuinely
                    # doesn't specify a parseable date.
                    "date": {"type": "string", "nullable": True},
                },
                "required": ["memory_id", "label", "date"],
            },
        },
    },
    "required": ["deadlines"],
}


def get_upcoming_deadlines(db: Session, owner_id: int) -> list[dict]:
    memories = (
        db.query(Memory)
        .filter(Memory.owner_id == owner_id, Memory.category == "deadline")
        .all()
    )
    if not memories:
        return []

    today = date.today().isoformat()
    listing = "\n".join(f"{m.id}: {m.content}" for m in memories)
    prompt = (
        f"Today's date is {today}. Below are a student's saved deadline "
        "notes, each with an id. For each one, extract a short label and "
        "the actual date it refers to (as YYYY-MM-DD), resolving relative "
        "or vague phrasing (e.g. 'next Friday', 'Dec 12') against today's "
        "date. If a note genuinely doesn't specify a date you can "
        "determine, set date to null rather than guessing.\n\n" + listing
    )

    client = get_gemini_client()
    result = client.generate_structured(prompt, DEADLINE_JSON_SCHEMA)

    parsed = []
    for entry in result.get("deadlines", []):
        raw_date = entry.get("date")
        if not raw_date:
            continue
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError:
            # Model returned something that isn't actually a valid
            # ISO date - treat the same as "couldn't parse."
            continue

        days_remaining = (parsed_date - date.today()).days
        parsed.append(
            {
                "memory_id": entry["memory_id"],
                "label": entry["label"],
                "date": raw_date,
                "days_remaining": days_remaining,
            }
        )

    parsed.sort(key=lambda d: d["date"])
    return parsed
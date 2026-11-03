from sqlalchemy.orm import Session

from app.models.memory import MEMORY_CATEGORIES, Memory
from app.services.rag import answer_question
from app.services.semantic_search import search_documents_by_meaning
from app.services.gemini_client import get_gemini_client  # add to existing imports
from app.services.web_fetch import FetchError, UnsafeUrlError, fetch_url_text


def tool_search_documents(db: Session, owner_id: int, query: str) -> dict:
    return {"results": search_documents_by_meaning(db, owner_id, query, top_k=5)}


def tool_search_web(db: Session, owner_id: int, query: str) -> dict:
    client = get_gemini_client()
    return client.search_web(query)

def tool_ask_documents(db: Session, owner_id: int, question: str) -> dict:
    return answer_question(db, owner_id, question)


def tool_get_memory(db: Session, owner_id: int, category: str | None = None) -> dict:
    query = db.query(Memory).filter(Memory.owner_id == owner_id)
    if category:
        query = query.filter(Memory.category == category)
    memories = query.order_by(Memory.created_at.desc()).all()
    return {"memories": [{"category": m.category, "content": m.content} for m in memories]}


def tool_save_memory(db: Session, owner_id: int, category: str, content: str) -> dict:
    if category not in MEMORY_CATEGORIES:
        category = "other"
    memory = Memory(owner_id=owner_id, category=category, content=content)
    db.add(memory)
    db.commit()
    return {"saved": True, "category": category, "content": content}

def tool_fetch_url(db: Session, owner_id: int, url: str) -> dict:
    try:
        text = fetch_url_text(url)
    except (UnsafeUrlError, FetchError) as exc:
        return {"error": str(exc)}
    return {"url": url, "content": text}

def tool_create_sketch(db: Session, owner_id: int, description: str) -> dict:
    client = get_gemini_client()
    svg = client.generate_sketch(description)
    if not svg.startswith("<svg"):
        return {"error": "Could not generate a valid sketch for this request."}
    return {"svg": svg}


# --------------------------------------------------------------------
# What Gemini sees: name, description, JSON-schema parameters.
# Descriptions are written for the MODEL to read, not a human - be
# explicit about when each tool should (and shouldn't) be used.
# --------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "search_documents",
        "description": (
            "Find the student's own uploaded FILES matching a natural-"
            "language description, e.g. 'the PDF about PID controllers'. "
            "Returns filenames and matching excerpts - not a generated "
            "answer. Use this when the student wants to locate a "
            "specific file, not have a question answered."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, in the student's own words."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "ask_documents",
        "description": (
            "Answer a question using ONLY the student's own uploaded "
            "documents, with citations. Use this when the student asks "
            "something that should be answered from their course notes/"
            "materials specifically, not from general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
    {
        "name": "get_memory",
        "description": (
            "Look up saved facts about the student (goals, preferences, "
            "deadlines, current projects). Optionally filter by category."
        ),
        "parameters": {
            "type": "object",
            "properties": {"category": {"type": "string", "enum": sorted(MEMORY_CATEGORIES)}},
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a new fact about the student for future conversations. "
            "Only call this when the student clearly states something "
            "worth remembering long-term (a goal, deadline, or "
            "preference) - not for routine conversational content."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": sorted(MEMORY_CATEGORIES)},
                "content": {"type": "string"},
            },
            "required": ["category", "content"],
        },
    },
    {
        "name": "search_web",
        "description": (
            "Search the live web for current, external information when "
            "the student has NOT given a specific URL - news, facts that "
            "change over time, general 'what is the latest on X'. Do NOT "
            "use this if the student gave you an actual link - use "
            "fetch_url for that instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch and read the actual text content of ONE SPECIFIC "
            "web page the student has given you a URL for - e.g. "
            "'summarize this article: <link>' or 'what does this "
            "page say: <link>'. Use this whenever the student's "
            "message contains an actual URL/link. Do NOT use this "
            "for open-ended queries with no specific URL - use "
            "search_web for those instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The exact URL to fetch."}},
            "required": ["url"],
        },
    },
    
        {
        "name": "create_sketch",
        "description": (
            "Draw a simple SVG sketch or diagram to visually "
            "demonstrate something - a labeled diagram, a flowchart, "
            "a simple illustration of a concept. NOT for photorealistic "
            "images, only simple line-art/diagram sketches. Use this "
            "when the student asks you to 'draw', 'sketch', 'show me a "
            "diagram of', or 'illustrate' something."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "What to sketch, described clearly."}
            },
            "required": ["description"],
        },
    },
]

TOOL_IMPLEMENTATIONS = {
    "search_documents": tool_search_documents,
    "ask_documents": tool_ask_documents,
    "get_memory": tool_get_memory,
    "save_memory": tool_save_memory,
    "search_web": tool_search_web,
    "fetch_url": tool_fetch_url,
}

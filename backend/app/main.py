"""
Cedric AI - Backend Entry Point
================================

PHASE 1 gave us the plumbing: React <-> FastAPI over HTTP, verified
with a health check.

PHASE 2 adds the first real feature: authentication. The
`auth_router` below provides /api/auth/register, /login, and /me. On
startup we also call `Base.metadata.create_all(engine)`, which creates
any database tables that don't exist yet (currently just `users`).

Still intentionally absent:
- Gemini / AI calls
- RAG / retrieval
- Voice / vision processing

Those remain future phases.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.memory import router as memory_router
from app.api.orchestrator import router as orchestrator_router
from app.api.quiz import router as quiz_router
from app.api.rag import router as rag_router
from app.api.vision import router as vision_router
from app.db.database import Base, SessionLocal, engine
from app.models import document as _document_model  # noqa: F401 - registers the model
from app.models import document_chunk as _document_chunk_model  # noqa: F401
from app.models import memory as _memory_model  # noqa: F401
from app.models import user as _user_model  # noqa: F401 - registers the model with Base
from app.services.retrieval import ensure_fts_table

from app.api.proactive import router as proactive_router

from app.api.evaluation import router as evaluation_router

from app.api import debug



# -----------------------------------------------------------------------
# 1. Create the FastAPI application instance.
#    This object is the core of the backend - every route we define
#    gets attached to it, and it's what uvicorn runs.
# -----------------------------------------------------------------------
app = FastAPI(
    title="Cedric AI Backend",
    description="Backend API for Cedric AI - AI Student Companion",
    version="0.1.0",
)


app.include_router(debug.router, tags=["debug"])

# -----------------------------------------------------------------------
# 2. CORS (Cross-Origin Resource Sharing) configuration.
#
#    WHY THIS IS NEEDED:
#    The React dev server runs on http://localhost:5173 and the FastAPI
#    backend runs on http://localhost:8000. From a browser's point of
#    view, those are two different "origins" (different ports count as
#    different origins). By default, browsers BLOCK JavaScript on one
#    origin from calling an API on a different origin, unless that API
#    explicitly says "this origin is allowed" via CORS headers.
#
#    Without this middleware, the frontend's fetch() call to the backend
#    would fail with a CORS error in the browser console, even though
#    the backend itself works fine (e.g. curl would still succeed).
#
#    In production this list should be tightened to the real deployed
#    frontend URL instead of "*".
# -----------------------------------------------------------------------
origins = [
    "http://localhost:5173",  # Vite dev server default port
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------
# 2b. Create database tables on startup (Phase 2).
#
#    `Base.metadata.create_all` looks at every model class that
#    inherits from `Base` (currently just `User`) and issues
#    `CREATE TABLE IF NOT EXISTS` for each one. This is a fine
#    approach while the schema is small and evolving quickly. Once
#    the schema stabilizes (and once we move to Postgres in Phase 6),
#    we'll switch to Alembic migrations, which track schema changes
#    incrementally instead of only ever creating from scratch.
# -----------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# Phase 9: the SQLite full-text-search table isn't a SQLAlchemy model
# (FTS5 virtual tables don't fit the ORM), so it's created separately
# via a raw SQL statement - see services/retrieval.py.
with SessionLocal() as _startup_db:
    ensure_fts_table(_startup_db)

# -----------------------------------------------------------------------
# 2c. Register feature routers.
#
#    Each feature area (auth, later: documents, chat, etc.) gets its
#    own router module instead of piling every route into this file.
# -----------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(memory_router)
app.include_router(orchestrator_router)
app.include_router(vision_router)
app.include_router(quiz_router)
app.include_router(proactive_router)
app.include_router(evaluation_router)



# -----------------------------------------------------------------------
# 3. Health-check endpoint.
#
#    This is the simplest possible endpoint: it takes no input and
#    returns a fixed JSON payload. Its only purpose is to answer the
#    question "is the backend alive and reachable?" - both for us
#    while developing, and later for monitoring/deployment tooling.
# -----------------------------------------------------------------------
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "cedric-ai-backend",
        "message": "Backend is running and reachable.",
    }


# -----------------------------------------------------------------------
# 4. Root endpoint - just a friendly landing message if someone opens
#    the backend URL directly in a browser.
# -----------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Cedric AI backend. See /docs for the API explorer."}

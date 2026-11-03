"""
Cedric AI - Database Engine & Session
========================================

SQLAlchemy setup. Three things are defined here:

- `engine`: the low-level connection to the database file/server.
- `SessionLocal`: a factory that produces a new "conversation" with
  the database per request (a Session tracks pending changes and
  commits/rolls them back as a unit).
- `Base`: the parent class every ORM model (e.g. `User`) inherits
  from, so SQLAlchemy knows which Python classes map to which tables.

`get_db()` is a FastAPI dependency: for every request that needs
database access, FastAPI calls it, hands the route function the
yielded Session, and - critically - runs the code after `yield` (the
`finally: db.close()`) once the request is done, even if it raised an
exception. This guarantees connections are never leaked.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# SQLite needs check_same_thread=False because FastAPI can handle
# requests on different threads, and SQLite's default driver assumes
# a connection is only ever used by the thread that created it. This
# flag is a no-op for other databases (e.g. Postgres), so it's safe
# to apply conditionally like this.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

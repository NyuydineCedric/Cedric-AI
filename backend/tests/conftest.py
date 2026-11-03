"""
Cedric AI - Test Configuration (Phase 28)
=============================================

Every test gets its own isolated SQLite database (a fresh temp file
per test, via pytest's `tmp_path`) and its own isolated storage
folder for uploaded files - tests never touch `backend/cedric.db` or
`backend/storage/`, the real dev data. This is done by overriding
FastAPI's `get_db` dependency, the same mechanism the app itself uses
for request-scoped database sessions - see app/db/database.py.
"""

import io
import sys
from pathlib import Path

# Make the `app` package importable when pytest is run from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.services.retrieval import ensure_fts_table


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        ensure_fts_table(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, email: str, password: str = "password123") -> str:
    client.post(
        "/api/auth/register",
        json={"email": email, "full_name": email.split("@")[0], "password": password},
    )
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


@pytest.fixture()
def student_token(client) -> str:
    return register_and_login(client, "student@test.com")


@pytest.fixture()
def other_token(client) -> str:
    return register_and_login(client, "other@test.com")


def make_text_file(name: str, content: bytes = b"Sample content about PID controllers."):
    return {"file": (name, io.BytesIO(content), "text/plain")}

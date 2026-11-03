from sqlalchemy import text
from app.db.database import engine

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE documents ADD COLUMN visibility VARCHAR NOT NULL DEFAULT 'personal'"))
    conn.commit()

print("Migration complete.")
from sqlalchemy import text
from app.db.database import engine

with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info(documents)"))
    for row in result:
        print(row)
# app/create_tables.py
from sqlalchemy import text
from app.database import engine

# Gemini's text-embedding-004 model outputs 768-dimension vectors,
# so our vector column MUST be VECTOR(768) to match.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS runbooks (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768)
);
"""

CREATE_INCIDENTS_SQL = """
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    error_message TEXT NOT NULL,
    matched_runbook TEXT,
    diagnosis TEXT,
    action_taken TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

def create_tables():
    with engine.connect() as connection:
        connection.execute(text(CREATE_TABLE_SQL))
        connection.execute(text(CREATE_INCIDENTS_SQL))    # incidents
        connection.commit()   # Must commit or the change is discarded
        print("Tables 'runbooks' and 'incidents' are ready.")

if __name__ == "__main__":
    create_tables()


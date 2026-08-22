# app/database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from app.embeddings import embed_text

# Load variables from the .env file into the environment
load_dotenv()

# Read the connection string we defined in .env
DATABASE_URL = os.getenv("DATABASE_URL")

# The "engine" is SQLAlchemy's core connection manager to the database
engine = create_engine(DATABASE_URL)

def test_connection():
    """A tiny function to prove we can talk to the database."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT version();"))
        print("Connected! PostgreSQL says:")
        print(result.fetchone()[0])

def search_runbooks(query: str, top_k: int = 1):
    """Find the runbook(s) most similar in meaning to the query text."""
    query_vector = embed_text(query)

    # The '<=>' operator is pgvector's cosine-distance operator.
    # Smaller distance = more similar. We ORDER BY it and take the top match.
    sql = text(
        "SELECT title, content, embedding <=> :qvec AS distance "
        "FROM runbooks "
        "ORDER BY distance ASC "
        "LIMIT :k"
    )
    with engine.connect() as connection:
        rows = connection.execute(
            sql, {"qvec": str(query_vector), "k": top_k}
        ).fetchall()

    return [{"title": r[0], "content": r[1], "distance": r[2]} for r in rows]

def log_incident(state: dict):
    """Save one completed agent run to the incidents table."""
    sql = text(
        "INSERT INTO incidents (error_message, matched_runbook, diagnosis, action_taken) "
        "VALUES (:error_message, :matched_runbook, :diagnosis, :action_taken)"
    )
    with engine.connect() as connection:
        connection.execute(sql, {
            "error_message": state.get("error_message", ""),
            "matched_runbook": state.get("matched_runbook", ""),
            "diagnosis": state.get("diagnosis", ""),
            "action_taken": state.get("action_taken", ""),
        })
        connection.commit()

def get_incidents():
    """Return all past incidents, newest first."""
    sql = text(
        "SELECT id, error_message, matched_runbook, diagnosis, action_taken, created_at "
        "FROM incidents ORDER BY created_at DESC"
    )
    columns = ["id", "error_message", "matched_runbook", "diagnosis", "action_taken", "created_at"]
    with engine.connect() as connection:
        rows = connection.execute(sql).fetchall()
    return [dict(zip(columns, row)) for row in rows]


if __name__ == "__main__":
    test_connection()


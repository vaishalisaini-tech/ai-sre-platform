# app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from app.agent.graph import build_graph
from app.database import log_incident, get_incidents
from fastapi.middleware.cors import CORSMiddleware

# Create the web app
app = FastAPI(title="AI-SRE Platform")

# Allow the React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],   # allow GET, POST, etc.
    allow_headers=["*"],
)

# Build the agent graph ONCE when the server starts (not per request)
agent_graph = build_graph()

# Defines the shape of the JSON body we expect on POST /incident
class IncidentRequest(BaseModel):
    error_message: str

@app.get("/")
def health_check():
    """Simple check that the server is alive."""
    return {"status": "ok", "service": "AI-SRE Platform"}

@app.post("/incident")
def handle_incident(request: IncidentRequest):
    """Receive an error, run the agent, log it, and return the result."""
    initial_state = {
        "error_message": request.error_message,
        "matched_runbook": "",
        "diagnosis": "",
        "action_taken": "",
    }
    # Run the whole detect -> diagnose graph
    result = agent_graph.invoke(initial_state)

    # Save the run to the database
    log_incident(result)

    # Send the result back to the caller as JSON
    return result

@app.get("/incidents")
def list_incidents():
    """Return all logged incidents (this feeds the dashboard later)."""
    return get_incidents()


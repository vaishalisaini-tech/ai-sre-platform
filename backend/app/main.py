# app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from app.agent.graph import build_graph
from app.database import log_incident, get_incidents
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends
from app.auth import require_api_key
from app.models.alerts import AlertmanagerWebhook


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

@app.post("/incident", dependencies=[Depends(require_api_key)])
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


@app.post("/api/v1/alerts")
def receive_alerts(payload: AlertmanagerWebhook):
    """Webhook target for Alertmanager. Runs each firing alert through the agent."""
    processed = []

    for alert in payload.alerts:
        # Only act on alerts that are actively firing
        if alert.status != "firing":
            continue

        # Extract the fields the agent needs from labels/annotations
        pod = alert.labels.get("pod", "unknown")
        namespace = alert.labels.get("namespace", "default")
        alertname = alert.labels.get("alertname", "UnknownAlert")
        severity = alert.labels.get("severity", "unknown")
        description = (
            alert.annotations.get("description")
            or alert.annotations.get("summary")
            or alertname
        )

        # Build a structured error message for the agent
        error_message = (
            f"[{severity.upper()}] {alertname} on pod '{pod}' "
            f"in namespace '{namespace}': {description}"
        )

        # The deployment to potentially remediate = the "app" label or the pod name
        target = alert.labels.get("app") or alert.labels.get("deployment") or pod

        # Run the SAME LangGraph agent you already built
        initial_state = {
            "error_message": error_message,
            "target_deployment": target,
            "matched_runbook": "",
            "diagnosis": "",
            "action_taken": "",
        }
        result = agent_graph.invoke(initial_state)
        log_incident(result)

        processed.append({
            "pod": pod,
            "alertname": alertname,
            "action_taken": result["action_taken"],
        })

    return {"received": len(payload.alerts), "processed": processed}


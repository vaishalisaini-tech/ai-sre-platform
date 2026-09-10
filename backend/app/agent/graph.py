# app/agent/graph.py
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.database import search_runbooks
import os
from app.k8s_actions import restart_deployment,scale_deployment, increase_memory_limit
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger("ai-sre")
from app.notify import notify


# The Gemini chat model for reasoning. Reads GOOGLE_API_KEY from env.
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")

AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "false").lower() == "true"


class AgentState(TypedDict):
    error_message: str
    target_deployment: str
    matched_runbook: str
    diagnosis: str
    action_taken: str
    strategy: str


# module-level, near AUTO_REMEDIATE
_remediation_counts = {}
MAX_AUTO_RESTARTS = 2

def _classify(error_message: str) -> str:
    """Decide the remediation strategy from the alert text."""
    e = error_message.lower()
    if "memory" in e or "oom" in e or "exit code 137" in e:
        return "memory"
    if "cpu" in e:
        return "cpu"
    if "crashloop" in e or "restart" in e:
        return "restart"
    return "restart"


def act_node(state: AgentState) -> AgentState:
    print("NODE: Acting...")
    deployment = state.get("target_deployment")
    if not deployment:
        state["action_taken"] = "No action: could not identify a target deployment."
        return state

    strategy = _classify(state["error_message"])
    state["strategy"] = strategy   # record what we decided (see Step 4)

    if not AUTO_REMEDIATE:
        recommendation = {
            "memory":  f"increase memory limit or scale '{deployment}'",
            "cpu":     f"scale out '{deployment}' with more replicas",
            "restart": f"restart deployment '{deployment}'",
        }[strategy]
        state["action_taken"] = f"PENDING APPROVAL [{strategy}]: recommended action is to {recommendation}. (AUTO_REMEDIATE off.)"
        return state

    try:
        if strategy == "memory":
            result = increase_memory_limit(deployment, "512Mi")
        elif strategy == "cpu":
            result = scale_deployment(deployment, replicas=3)
        else:  # restart, with the storm guardrail
            count = _remediation_counts.get(deployment, 0)
            if count >= MAX_AUTO_RESTARTS:
                state["action_taken"] = f"ESCALATED: '{deployment}' restarted {count}x and still failing — needs human intervention."
                return state
            result = restart_deployment(deployment)
            _remediation_counts[deployment] = count + 1
            result = f"({count + 1}/{MAX_AUTO_RESTARTS}) {result}"

        state["action_taken"] = f"EXECUTED [{strategy}]: {result}"
    except Exception as e:
        state["action_taken"] = f"FAILED [{strategy}] on '{deployment}': {e}"
    
    notify(
        f":robot_face: *AI-SRE Action*\n"
        f"*Incident:* {state['error_message']}\n"
        f"*Strategy:* {state.get('strategy', 'n/a')}\n"
        f"*Runbook:* {state.get('matched_runbook', 'n/a')}\n"
        f"*Result:* {state['action_taken']}"
    )

    return state


def _extract_text(response) -> str:
    """Newer Gemini models return content as a list of blocks.
    This safely pulls out just the text."""
    content = response.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, dict):
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts).strip()

def detect_node(state: AgentState) -> AgentState:
    log.info("NODE: Detecting incident...")
    # If an error was passed in (via the API), keep it.
    # Only use a fake one when running this file directly for testing.
    if not state.get("error_message"):
        state["error_message"] = "Container terminated with exit code 137"
    return state


def diagnose_node(state: AgentState) -> AgentState:
    log.info("NODE: Diagnosing with RAG...")
    error = state["error_message"]

    # 1. RETRIEVE: find the most relevant runbook via vector search
    results = search_runbooks(error, top_k=1)
    best = results[0]
    state["matched_runbook"] = best["title"]
    log.info(f"   Matched runbook: {best['title']} (distance={best['distance']:.4f})")

    # 2. AUGMENT + GENERATE: ask Gemini to produce a fix using that runbook
    prompt = (
        "You are an autonomous Site Reliability Engineering (SRE) agent. "
        "You are triggered by structured telemetry alerts from Prometheus Alertmanager "
        "(for example: high CPU, memory pressure, OOM risk, pod restarts, or "
        "availability alerts) — NOT by raw application text logs.\n\n"
        f"INCIDENT ALERT:\n{error}\n\n"
        f"RELEVANT RUNBOOK ('{best['title']}'):\n{best['content']}\n\n"
        "The alert has already been parsed into a severity, alert name, affected pod, "
        "and namespace. Based ONLY on the runbook above, provide a short, concrete "
        "remediation recommendation appropriate for an infrastructure/resource alert. "
        "If the alert indicates resource pressure (CPU/memory), consider whether a "
        "restart, a resource-limit change, or scaling is the correct response, and say which."
    )

    response = llm.invoke(prompt)

    state["diagnosis"] = _extract_text(response)
    state["action_taken"] = "Fix recommended (dry-run, not yet executed)."
    return state

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("detect", detect_node)
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("act", act_node)               
    workflow.set_entry_point("detect")
    workflow.add_edge("detect", "diagnose")
    workflow.add_edge("diagnose", "act")             
    workflow.add_edge("act", END)                    

    return workflow.compile()

if __name__ == "__main__":
    graph = build_graph()
    initial_state = {
        "error_message": "",
        "matched_runbook": "",
        "diagnosis": "",
        "action_taken": "",
    }
    final_state = graph.invoke(initial_state)

    log.info("\n--- FINAL STATE ---")
    log.info(f"Error:     {final_state['error_message']}")
    log.info(f"Matched:   {final_state['matched_runbook']}")
    log.info(f"Diagnosis: {final_state['diagnosis']}")
    log.info(f"Action:    {final_state['action_taken']}")


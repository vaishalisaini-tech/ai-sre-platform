# app/agent/graph.py
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.database import search_runbooks
import os
from app.k8s_actions import restart_deployment

# The Gemini chat model for reasoning. Reads GOOGLE_API_KEY from env.
llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash")

AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "false").lower() == "true"


class AgentState(TypedDict):
    error_message: str
    target_deployment: str
    matched_runbook: str
    diagnosis: str
    action_taken: str

def act_node(state: AgentState) -> AgentState:
    print("NODE: Acting...")
    deployment = state.get("target_deployment")

    if not deployment:
        state["action_taken"] = "No action: could not identify a target deployment."
        return state

    if AUTO_REMEDIATE:
        try:
            result = restart_deployment(deployment)
            state["action_taken"] = f"EXECUTED: {result}"
        except Exception as e:
            state["action_taken"] = f"FAILED to restart '{deployment}': {e}"
    else:
        # Safe default: recommend but do not execute
        state["action_taken"] = (
            f"PENDING APPROVAL: recommended action is to restart "
            f"deployment '{deployment}'. (AUTO_REMEDIATE is off — dry-run.)"
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
    print("NODE: Detecting incident...")
    # If an error was passed in (via the API), keep it.
    # Only use a fake one when running this file directly for testing.
    if not state.get("error_message"):
        state["error_message"] = "Container terminated with exit code 137"
    return state


def diagnose_node(state: AgentState) -> AgentState:
    print("NODE: Diagnosing with RAG...")
    error = state["error_message"]

    # 1. RETRIEVE: find the most relevant runbook via vector search
    results = search_runbooks(error, top_k=1)
    best = results[0]
    state["matched_runbook"] = best["title"]
    print(f"   Matched runbook: {best['title']} (distance={best['distance']:.4f})")

    # 2. AUGMENT + GENERATE: ask Gemini to produce a fix using that runbook
    prompt = (
        f"You are an SRE assistant. An incident occurred:\n'{error}'\n\n"
        f"Here is the relevant runbook titled '{best['title']}':\n"
        f"{best['content']}\n\n"
        "Based ONLY on this runbook, give a short, concrete recommended fix."
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

    print("\n--- FINAL STATE ---")
    print(f"Error:     {final_state['error_message']}")
    print(f"Matched:   {final_state['matched_runbook']}")
    print(f"Diagnosis: {final_state['diagnosis']}")
    print(f"Action:    {final_state['action_taken']}")


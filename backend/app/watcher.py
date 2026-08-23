# app/watcher.py
from kubernetes import client, config, watch
from app.agent.graph import build_graph
from app.database import log_incident
import time
from urllib3.exceptions import ProtocolError

def _load_config():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

def diagnose_pod_problem(pod):
    """Return a human-readable reason if the pod is unhealthy, else None."""
    for cs in (pod.status.container_statuses or []):
        waiting = cs.state.waiting
        if waiting and waiting.reason in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"):
            return waiting.reason
        terminated = cs.state.terminated
        if terminated and terminated.reason == "OOMKilled":
            return "Container terminated with exit code 137 (OOMKilled)"
    return None


def main():
    _load_config()
    v1 = client.CoreV1Api()
    graph = build_graph()
    handled = set()

    print("SRE agent watcher started. Watching pods in 'default'...", flush=True)
    w = watch.Watch()

    while True:                                    # reconnect forever
        try:
            for event in w.stream(v1.list_namespaced_pod,
                                  namespace="default",
                                  timeout_seconds=60):
                pod = event["object"]
                reason = diagnose_pod_problem(pod)
                if not reason:
                    continue

                key = f"{pod.metadata.name}:{reason}"
                if key in handled:
                    continue
                handled.add(key)

                target = (pod.metadata.labels or {}).get("app", "")
                error_message = f"Pod '{pod.metadata.name}' problem: {reason}"
                print("INCIDENT:", error_message, flush=True)

                state = {
                    "error_message": error_message,
                    "target_deployment": target,
                    "matched_runbook": "",
                    "diagnosis": "",
                    "action_taken": "",
                }
                try:
                    result = graph.invoke(state)
                    log_incident(result)
                    print("  ->", result["action_taken"], flush=True)
                except Exception as e:
                    print("  ERROR handling incident:", e, flush=True)
                    handled.discard(key)           # allow a retry next time

        except (ProtocolError, Exception) as e:
            print("Watch stream ended, reconnecting...", e, flush=True)
            time.sleep(2)                          # brief pause, then reconnect

if __name__ == "__main__":
    main()

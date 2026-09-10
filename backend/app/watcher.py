# app/watcher.py
from kubernetes import client, config, watch
from app.agent.graph import build_graph
from app.database import log_incident
import time
from urllib3.exceptions import ProtocolError

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
log = logging.getLogger("ai-sre")


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

    log.info("SRE agent watcher started. Watching pods in 'default'...")
    w = watch.Watch()

    while True:                                    
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
                log.info("INCIDENT: %s", error_message)

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
                    log.info("  -> %s", result["action_taken"])
                except Exception as e:
                    log.info("  ERROR handling incident: %s", e)
                    handled.discard(key)           # allow a retry next time

        except (ProtocolError, Exception) as e:
            log.warning("Watch stream ended, reconnecting...: %s", e)
            time.sleep(2)                          

if __name__ == "__main__":
    main()

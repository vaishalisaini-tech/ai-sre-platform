# app/k8s_actions.py
import datetime
from kubernetes import client, config

def _load_config():
    """Use in-cluster credentials when running in a pod;
    fall back to local kubeconfig when testing on your laptop."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()

def restart_deployment(name: str, namespace: str = "default") -> str:
    """Trigger a rolling restart of a deployment (same as `kubectl rollout restart`)."""
    _load_config()
    apps = client.AppsV1Api()
    now = datetime.datetime.utcnow().isoformat()
    # Patching an annotation forces Kubernetes to recreate the pods
    body = {
        "spec": {"template": {"metadata": {"annotations": {
            "kubectl.kubernetes.io/restartedAt": now
        }}}}
    }
    apps.patch_namespaced_deployment(name, namespace, body)
    return f"Restarted deployment '{name}' at {now}"


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

def scale_deployment(name: str, replicas: int, namespace: str = "default") -> str:
    """Scale a deployment to N replicas (horizontal scaling)."""
    _load_config()
    apps = client.AppsV1Api()
    body = {"spec": {"replicas": replicas}}
    apps.patch_namespaced_deployment_scale(name, namespace, body)
    return f"Scaled deployment '{name}' to {replicas} replicas"

def increase_memory_limit(name: str, new_limit: str = "512Mi", namespace: str = "default") -> str:
    """Raise the memory limit on a deployment's first container."""
    _load_config()
    apps = client.AppsV1Api()
    body = {
        "spec": {"template": {"spec": {"containers": [
            {"name": name, "resources": {"limits": {"memory": new_limit}}}
        ]}}}
    }
    apps.patch_namespaced_deployment(name, namespace, body)
    return f"Increased memory limit of '{name}' to {new_limit}"


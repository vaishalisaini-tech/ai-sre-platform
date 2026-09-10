# app/models/alerts.py
from typing import Optional
from pydantic import BaseModel

class Alert(BaseModel):
    """A single alert inside the batch Alertmanager sends."""
    status: str                      # "firing" or "resolved"
    labels: dict[str, str] = {}      # key/value tags: alertname, pod, namespace, severity...
    annotations: dict[str, str] = {} # human-readable text: summary, description...
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    fingerprint: Optional[str] = None  # a unique ID for this alert instance

class AlertmanagerWebhook(BaseModel):
    """The top-level payload Alertmanager POSTs to our webhook."""
    version: Optional[str] = None
    status: str                      # overall group status: "firing"/"resolved"
    receiver: Optional[str] = None
    groupLabels: dict[str, str] = {}
    commonLabels: dict[str, str] = {}
    commonAnnotations: dict[str, str] = {}
    alerts: list[Alert]              # the list of individual alerts


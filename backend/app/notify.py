# app/notify.py
import os
import requests

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

def notify(message: str) -> None:
    """Post a message to Slack. Silently no-ops if not configured."""
    if not SLACK_WEBHOOK_URL:
        return
    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=5)
    except Exception as e:
        print(f"Slack notify failed: {e}", flush=True)


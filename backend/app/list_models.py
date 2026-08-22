# app/list_models.py
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Models that support embeddings:")
for m in client.models.list():
    actions = getattr(m, "supported_actions", []) or []
    if "embedContent" in actions:
        print(f"  {m.name}")


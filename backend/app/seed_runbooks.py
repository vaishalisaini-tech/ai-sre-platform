# app/seed_runbooks.py
from sqlalchemy import text
from app.database import engine
from app.embeddings import embed_text

# A few sample runbooks. In a real system these would be dozens of
# markdown docs written by your SRE team.
SAMPLE_RUNBOOKS = [
    {
        "title": "Fix CrashLoopBackOff",
        "content": (
            "When a pod is in CrashLoopBackOff, the container keeps crashing "
            "on startup. Check logs with 'kubectl logs <pod>'. Common causes: "
            "bad config, missing environment variable, or a failing health check. "
            "Fix the config and restart the deployment with 'kubectl rollout restart'."
        ),
    },
    {
        "title": "Handle Out-Of-Memory (OOMKilled)",
        "content": (
            "If a container is terminated with exit code 137, it was OOMKilled "
            "(ran out of memory). Increase the memory limit in the deployment "
            "resources section, or fix the memory leak in the application."
        ),
    },
    {
        "title": "Resolve ImagePullBackOff",
        "content": (
            "ImagePullBackOff means Kubernetes cannot download the container image. "
            "Check the image name and tag for typos, verify the image exists in the "
            "registry, and confirm the imagePullSecret credentials are correct."
        ),
    },
]

def seed():
    with engine.connect() as connection:
        for rb in SAMPLE_RUNBOOKS:
            # 1. Turn the runbook content into a vector via Gemini
            vector = embed_text(rb["content"])

            # 2. Insert title, content, and the vector into Postgres.
            #    pgvector accepts the vector as a string like '[0.1, 0.2, ...]'
            connection.execute(
                text(
                    "INSERT INTO runbooks (title, content, embedding) "
                    "VALUES (:title, :content, :embedding)"
                ),
                {
                    "title": rb["title"],
                    "content": rb["content"],
                    "embedding": str(vector),
                },
            )
            print(f"Inserted: {rb['title']}")
        connection.commit()
        print("Done seeding runbooks.")

if __name__ == "__main__":
    seed()


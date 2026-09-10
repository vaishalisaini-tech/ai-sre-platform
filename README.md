# Autonomous AI-SRE Platform

An autonomous Site Reliability Engineering (SRE) agent that detects failing Kubernetes workloads and metric-based alerts, retrieves the correct remediation from a vector database using Retrieval-Augmented Generation (RAG), decides on a signal-appropriate fix, and executes it automatically — with safety guardrails and a full human-visible audit trail.

The system closes the complete SRE loop: **Observe → Detect → Decide → Act → Report.**

> Status: Complete and working end-to-end on Google Kubernetes Engine (GKE). The cluster is cost-managed (torn down when idle), so there is no permanent public demo URL. See the Demo section for how to run it live.

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [Architecture](#architecture)
* [Technology Stack](#technology-stack)
* [How It Works](#how-it-works)
* [Repository Structure](#repository-structure)
* [Prerequisites](#prerequisites)
* [Local Development](#local-development)
* [Cloud Deployment (GKE)](#cloud-deployment-gke)
* [Observability](#observability)
* [Operations (Start / Stop / Deploy)](#operations-start--stop--deploy)
* [Testing](#testing)
* [CI/CD](#cicd)
* [Security](#security)
* [Configuration](#configuration)
* [Engineering Challenges](#engineering-challenges)
* [Future Enhancements](#future-enhancements)
* [License](#license)

## Overview

Traditional monitoring pages a human when something breaks. This project asks a different question: can an AI agent handle the first line of response the way an on-call engineer would — read the signal, look up the runbook, apply the right fix, and report what it did?

The platform watches a Kubernetes cluster in two ways:

1. **Event-driven** — a watcher subscribes to the Kubernetes API and reacts to pod-level failures such as `CrashLoopBackOff` and `OOMKilled`.
2. **Telemetry-driven** — Prometheus alert rules (e.g. high memory, high CPU, repeated restarts) fire through Alertmanager into a FastAPI webhook.

Either trigger feeds the same reasoning core: a LangGraph agent that performs RAG over a library of runbooks stored in PostgreSQL with the pgvector extension, produces a diagnosis with Google Gemini, and selects a remediation strategy. Actions are applied through the Kubernetes API and every decision is logged to a React dashboard and announced to Slack.

## Key Features

* Autonomous incident detection from both Kubernetes events and Prometheus telemetry.
* Retrieval-Augmented Generation over runbooks using pgvector cosine-similarity search (768-dimension Gemini embeddings).
* Signal-aware remediation: restart for crash loops, horizontal scale-out for CPU saturation, memory-limit increase for memory pressure.
* Safety guardrails: recommend-only mode by default, opt-in auto-remediation, a restart-storm cap that escalates to humans after repeated failures.
* Graceful degradation: if the LLM quota is exhausted, the agent falls back to the retrieved runbook so remediation still proceeds.
* Full observability: Prometheus, Alertmanager, Grafana, and kube-state-metrics.
* Human-visible audit trail: live React dashboard plus Slack write-back on every action.
* Infrastructure as Code with Terraform; automated build-and-deploy with Jenkins.
* Least-privilege RBAC scoped to exactly the verbs the agent needs.

## Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │            Google Kubernetes Engine            │
                          │                                                │
  metrics   ┌──────────┐  │  ┌────────────┐   fire   ┌──────────────┐      │
  scrape ──▶│Prometheus│──┼─▶│ Alert rules│─────────▶│ Alertmanager │      │
            └──────────┘  │  └────────────┘          └──────┬───────┘      │
                 ▲        │                                  │ webhook      │
     kube-state- │        │                                  ▼              │
     metrics /   │        │   K8s events         ┌───────────────────────┐ │
     cAdvisor    │        │   ┌───────────┐      │  FastAPI backend      │ │
                 │        │   │  Watcher  │─────▶│  /api/v1/alerts       │ │
   ┌─────────┐   │        │   └───────────┘      │  /incident            │ │
   │ Grafana │───┘        │                      └───────────┬───────────┘ │
   └─────────┘            │                                  │             │
                          │                                  ▼             │
                          │                    ┌───────────────────────┐   │
                          │                    │  LangGraph agent      │   │
                          │                    │  detect → diagnose →  │   │
                          │                    │           act         │   │
                          │                    └───┬──────────┬────────┘   │
                          │        RAG query        │          │ remediate  │
                          │                         ▼          ▼            │
                          │            ┌──────────────────┐  ┌───────────┐  │
                          │            │ PostgreSQL +     │  │ K8s API   │  │
                          │            │ pgvector         │  │ (restart/ │  │
                          │            │ (runbooks +      │  │  scale/   │  │
                          │            │  incidents)      │  │  patch)   │  │
                          │            └──────────────────┘  └───────────┘  │
                          │                     │                           │
                          └─────────────────────┼───────────────────────────┘
                                                │
                    ┌───────────────┐           │           ┌──────────────┐
                    │ React         │◀──────────┘           │    Slack     │
                    │ dashboard     │   incidents log       │  write-back  │
                    └───────────────┘                       └──────────────┘

  External signals:  Google Gemini (embeddings + diagnosis)
  Build & deliver:   Docker → Artifact Registry → Jenkins → GKE
  Provisioning:      Terraform (GKE cluster, node pool, Artifact Registry)
```

## Technology Stack

| Category | Technologies |
| --- | --- |
| Language | Python 3.12, TypeScript/JavaScript |
| Backend & AI | FastAPI, LangGraph, Google Gemini (chat + embeddings), RAG |
| Database | PostgreSQL 16 with the pgvector extension |
| Frontend | React (Vite), served by nginx |
| Containerization | Docker, Docker Compose, multi-stage builds |
| Orchestration | Kubernetes on Google Kubernetes Engine (GKE) |
| Infrastructure as Code | Terraform |
| CI/CD | Jenkins (build → push → rolling deploy) |
| Cloud | Google Cloud Platform — GKE, Artifact Registry, Load Balancing |
| Observability | Prometheus, Alertmanager, Grafana, kube-state-metrics |
| Notifications | Slack incoming webhooks |
| Security | Kubernetes Secrets, least-privilege RBAC, keyless CI authentication |

## How It Works

The agent is a LangGraph state machine with three nodes that pass a shared state object between them.

1. **detect** — receives an incident. The source is either the Kubernetes watcher (an unhealthy pod) or the Alertmanager webhook (a parsed telemetry alert). It normalizes the signal into a structured error message plus a target deployment.
2. **diagnose (RAG)** — embeds the incident text with Gemini, runs a cosine-similarity search against the `runbooks` table in pgvector to retrieve the most relevant runbook, and asks Gemini to produce a concrete remediation grounded in that runbook. If the LLM is rate-limited, it falls back to the runbook content directly.
3. **act** — classifies the incident (memory / CPU / crash-loop) and applies the appropriate action through the Kubernetes API: a rolling restart, a horizontal scale-up, or a memory-limit patch. In the default recommend-only mode it logs the recommendation without executing. A restart cap prevents storms and escalates persistent failures to a human.

Every run is written to the `incidents` table (surfaced on the dashboard) and announced to Slack.

## Repository Structure

```
ai-sre-platform/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app: /incident, /incidents, /api/v1/alerts
│   │   ├── database.py          # SQLAlchemy engine, RAG search, incident logging
│   │   ├── embeddings.py        # Gemini embedding client (768-dim)
│   │   ├── create_tables.py     # Schema: runbooks + incidents, pgvector index
│   │   ├── seed_runbooks.py     # Seeds sample + metric-specific runbooks
│   │   ├── watcher.py           # Kubernetes event watcher (autonomous trigger)
│   │   ├── k8s_actions.py       # restart / scale / increase-memory actions
│   │   ├── notify.py            # Slack write-back
│   │   ├── auth.py              # API-key dependency
│   │   ├── models/alerts.py     # Pydantic models for the Alertmanager payload
│   │   └── agent/graph.py       # LangGraph agent: detect → diagnose → act
│   ├── tests/                   # pytest suite (mocked Gemini + DB)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/                     # React dashboard (stats, chart, filters, theme)
│   ├── nginx.conf               # Serves the app + proxies /api to the backend
│   └── Dockerfile               # Multi-stage build (node build → nginx serve)
├── k8s/
│   ├── rbac.yaml                # ServiceAccount + least-privilege Role/Binding
│   ├── postgres.yaml            # Deployment + PVC + Service
│   ├── backend.yaml             # Deployment + Service (probes, limits, secrets)
│   ├── frontend.yaml            # Deployment + LoadBalancer Service
│   ├── watcher.yaml             # Watcher Deployment (uses sre-agent SA)
│   ├── test-crash.yaml          # A deliberately crashing pod for testing
│   └── monitoring/              # Prometheus, Alertmanager, Grafana, rules
├── infra/                       # Terraform: GKE cluster, node pool, Artifact Registry
├── Jenkinsfile                  # CI/CD pipeline
├── docker-compose.yml           # Local stack (db + backend + frontend)
├── restart.sh / stop.sh         # Bring the whole platform up / tear it down
├── deploy.sh / status.sh        # Rebuild-and-roll / at-a-glance state check
├── .env.example
└── README.md
```

## Prerequisites

* Docker and Docker Compose
* Python 3.12 and Node.js 20 (for local development outside containers)
* A Google Gemini API key
* For cloud deployment: a GCP project with billing enabled, plus `gcloud`, `kubectl`, the GKE auth plugin, and `terraform`

## Local Development

Run the entire stack on your machine with Docker Compose.

```bash
# 1. Provide secrets
cp .env.example .env
# edit .env and set GOOGLE_API_KEY and a strong DB password

# 2. Start database, backend, and frontend
docker compose up --build

# 3. Initialize the database (first run only)
docker exec -it ai_sre_db psql -U sre_user -d sre_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker exec -it ai_sre_backend python -m app.create_tables
docker exec -it ai_sre_backend python -m app.seed_runbooks
```

The dashboard is then available at `http://localhost:3000` and the API docs at `http://localhost:8000/docs`.

## Cloud Deployment (GKE)

The infrastructure is defined as code. Provisioning and deployment are two steps.

```bash
# 1. Provision the cluster + Artifact Registry
cd infra
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"
cd ..

# 2. Bring the platform up (deploys app + monitoring, seeds the DB)
./restart.sh
```

`restart.sh` connects `kubectl` to the cluster, grants the node service account read access to Artifact Registry, recreates all secrets, applies every manifest, waits for pods to become ready, and seeds the database. It prints the external IP and Grafana credentials at the end.

Because a fresh LoadBalancer is assigned on each rebuild, the external IP changes every time — read the new value from the script output.

## Observability

The monitoring stack runs in a dedicated `monitoring` namespace.

* **Prometheus** scrapes kube-state-metrics and cAdvisor, and evaluates alert rules (`PodRestartingTooOften`, `HighMemoryUsage`, `HighCPUUsage`).
* **Alertmanager** groups firing alerts and posts them to the backend at `/api/v1/alerts`.
* **Grafana** visualizes cluster metrics; the Prometheus data source is auto-provisioned.

Access the UIs via port-forward:

```bash
kubectl port-forward -n monitoring svc/prometheus   9090:9090
kubectl port-forward -n monitoring svc/alertmanager 9093:9093
kubectl port-forward -n monitoring svc/grafana      3000:3000
```

## Operations (Start / Stop / Deploy)

Four scripts manage the full lifecycle so the platform can be run only when needed, keeping cloud cost near zero when idle.

| Command | Purpose |
| --- | --- |
| `./status.sh` | Read-only: shows whether the cluster is running (and billing), pod health, external IP, Grafana password, and secret presence. |
| `./stop.sh` | Deletes all Kubernetes resources (releasing the LoadBalancer and disk), then `terraform destroy`, then verifies no billable resources remain. |
| `terraform apply` then `./restart.sh` | Rebuilds the cluster and brings the whole platform back up. |
| `./deploy.sh` | Rebuilds both images with a unique tag and rolls out backend, watcher, and frontend after code changes. |

To test the autonomous loop, apply the crashing test pod and watch an incident appear on the dashboard and in Slack without any human action:

```bash
kubectl apply -f k8s/test-crash.yaml
kubectl logs deploy/agent-watcher -f
# clean up when done:
kubectl delete -f k8s/test-crash.yaml
```

## Testing

The backend has a pytest suite that mocks the Gemini and database boundaries, so it runs with no API key and no running database — suitable for CI.

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest --cov=app --cov-report=term-missing
```

Coverage includes the API endpoints (health, incident submission with validation, incident listing), the agent nodes (detect defaults, dry-run vs. auto-execute, restart cap, no-target handling), and the Kubernetes action module.

## CI/CD

A Jenkins pipeline (`Jenkinsfile`) authenticates to GCP, runs the tests, builds and pushes the backend and frontend images to Artifact Registry, and performs a rolling deployment to GKE. Image tags use the build number so every deploy is uniquely traceable, and `kubectl rollout status` gates the pipeline on healthy pods.

Authentication is keyless: Jenkins runs locally and reuses the developer's mounted `gcloud` credentials, avoiding downloaded service-account keys (which are blocked by organization policy in many corporate GCP environments).

## Security

* Secrets (Gemini key, Slack webhook, database URL, Grafana password) are stored in Kubernetes Secrets, never in code or images.
* The agent's ServiceAccount uses a least-privilege RBAC Role granting only `get`/`list`/`watch` on pods and `get`/`list`/`patch` on deployments and the scale subresource.
* The API supports an API-key dependency; the alert webhook is kept cluster-internal rather than exposed publicly.
* Auto-remediation is off by default (recommend-only), with a restart cap that escalates persistent failures instead of looping.
* CI uses keyless authentication.

Never commit a real `.env`, `*.tfvars`, `*.tfstate*`, or any webhook/key. Use `.env.example` as the committed template.

## Configuration

Configuration is supplied through environment variables (see `.env.example`).

| Variable | Purpose |
| --- | --- |
| `GOOGLE_API_KEY` | Gemini API key for embeddings and diagnosis. |
| `DATABASE_URL` | PostgreSQL connection string (host is `localhost` locally, `postgres` in-cluster). |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for action write-back (optional; no-ops if unset). |
| `AUTO_REMEDIATE` | `false` (default) recommends only; `true` executes remediations. |
| `API_KEY` | Optional API key required by protected endpoints. |

## Engineering Challenges

* **Grounding the LLM.** Free-form LLM answers hallucinate fixes. RAG over a curated runbook library grounds every diagnosis in real operational knowledge, and cosine-similarity search matches semantically even when wording differs (for example, "exit code 137" maps to the out-of-memory runbook).
* **Signal-aware remediation.** Restarting an out-of-memory pod only delays the next failure. The agent classifies the alert type and chooses restart, scale-out, or a memory-limit increase accordingly.
* **Preventing runaway automation.** Restarting a pod creates a new pod name, which naively looks like a brand-new incident and can trigger an infinite restart storm. A per-deployment remediation cap escalates to a human after repeated failures.
* **Ephemeral-cluster cost management.** Because `terraform destroy` removes the cluster, LoadBalancer, and database disk, restart requires re-creating secrets and re-seeding data. Scripted automation makes teardown and rebuild a single command each while keeping idle cost near zero.
* **Resilient watching and graceful degradation.** The Kubernetes watch stream closes periodically; the watcher reconnects automatically. When the Gemini quota is exhausted, the agent falls back to the retrieved runbook so remediation still completes.

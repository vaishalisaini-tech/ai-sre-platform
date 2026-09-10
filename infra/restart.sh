#!/bin/bash
# restart.sh — Bring the AI-SRE project back to life AFTER `terraform apply`.
# Assumes: cd infra && terraform apply -var="project_id=..." has already recreated the cluster.
set -e

PROJECT_ID=ai-sre-platform-506305
REGION=us-central1
CLUSTER=ai-sre-cluster
REPO_NAME=ai-sre-images

# ---- EDIT THESE (or export them before running) ----
GOOGLE_API_KEY="${GOOGLE_API_KEY:-your_gemini_api_key_here}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-your_slack_webhook_url_here}"
DB_PASSWORD="${DB_PASSWORD:-8nACzESeF2MqzlpSleCIsfYl6y6NEOYt}"
GRAFANA_PASSWORD="${GRAFANA_PASSWORD:-$(openssl rand -base64 16)}"

echo "==> [1/7] Connecting kubectl to the cluster..."
gcloud container clusters get-credentials $CLUSTER --region $REGION

echo "==> [2/7] Granting nodes read access to Artifact Registry (fixes ImagePullBackOff)..."
NODE_SA=$(gcloud container node-pools describe primary-node-pool \
  --cluster $CLUSTER --region $REGION --format="value(config.serviceAccount)")
if [ "$NODE_SA" = "default" ]; then
  PROJECT_NUM=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
  NODE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
fi
echo "    Node service account: $NODE_SA"
gcloud artifacts repositories add-iam-policy-binding $REPO_NAME \
  --location=$REGION --project=$PROJECT_ID \
  --member="serviceAccount:$NODE_SA" \
  --role="roles/artifactregistry.reader" || true

echo "==> [3/7] Creating secrets (|| true = ignore if they already exist)..."
kubectl create secret generic gemini-secret \
  --from-literal=GOOGLE_API_KEY="$GOOGLE_API_KEY" || true
kubectl create secret generic slack-secret \
  --from-literal=SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" || true
kubectl create secret generic db-secret \
  --from-literal=DATABASE_URL="postgresql://sre_user:${DB_PASSWORD}@postgres:5432/sre_db" \
  --from-literal=POSTGRES_PASSWORD="$DB_PASSWORD" || true

echo "==> [4/7] Deploying application manifests..."
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/watcher.yaml

echo "==> [5/7] Deploying monitoring stack (Prometheus, Alertmanager, Grafana)..."
kubectl create namespace monitoring || true
kubectl create secret generic grafana-secret -n monitoring \
  --from-literal=password="$GRAFANA_PASSWORD" || true
# kube-state-metrics (Prometheus scrape target)
kubectl apply -f https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard/cluster-role.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard/cluster-role-binding.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard/service-account.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard/deployment.yaml
kubectl apply -f https://raw.githubusercontent.com/kubernetes/kube-state-metrics/main/examples/standard/service.yaml
kubectl apply -f k8s/monitoring/

echo "==> [6/7] Waiting for core pods to be ready..."
kubectl wait --for=condition=ready pod --all --timeout=240s || true

echo "==> [7/7] Initializing the database (fresh volume after teardown)..."
kubectl exec deploy/postgres -- psql -U sre_user -d sre_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
kubectl exec deploy/backend -- python -m app.create_tables
kubectl exec deploy/backend -- python -m app.seed_runbooks

echo ""
echo "DONE. Grafana admin password: $GRAFANA_PASSWORD"
echo "Frontend external IP (may take 1-2 min to appear):"
kubectl get service frontend


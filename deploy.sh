#!/bin/bash
# deploy.sh — Rebuild + push images and roll them out. Run after ANY code change.
# Requires the cluster to be up and kubectl pointed at it (run restart.sh first).
set -e

PROJECT_ID=ai-sre-platform-506305
REGION=us-central1
REPO=$REGION-docker.pkg.dev/$PROJECT_ID/ai-sre-images
TAG=$(date +%Y%m%d-%H%M%S)   # unique tag forces a fresh pull every time

echo "==> Building with tag: $TAG"
gcloud auth configure-docker $REGION-docker.pkg.dev --quiet

echo "==> Backend..."
docker build -t $REPO/backend:$TAG ./backend
docker push $REPO/backend:$TAG

echo "==> Frontend..."
docker build -t $REPO/frontend:$TAG ./frontend
docker push $REPO/frontend:$TAG

echo "==> Rolling out (backend image is shared by API + watcher)..."
kubectl set image deployment/backend       backend=$REPO/backend:$TAG
kubectl set image deployment/agent-watcher  watcher=$REPO/backend:$TAG
kubectl set image deployment/frontend      frontend=$REPO/frontend:$TAG

kubectl rollout status deployment/backend
kubectl rollout status deployment/agent-watcher
kubectl rollout status deployment/frontend

echo "==> Deployed (tag: $TAG)"
kubectl get pods


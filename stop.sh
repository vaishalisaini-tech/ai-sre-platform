#!/bin/bash
# stop.sh — Tear down the AI-SRE project to reach ~zero GCP cost.
# Order matters: delete K8s resources FIRST (releases LoadBalancer + disks),
# THEN destroy the cluster, THEN verify nothing billable is orphaned.
set -e

PROJECT_ID=ai-sre-platform-506305
REGION=us-central1

echo "==> [1/4] Deleting app + monitoring K8s resources (releases LoadBalancer + disks)..."
kubectl delete -f k8s/ --ignore-not-found || true
kubectl delete -f k8s/monitoring/ --ignore-not-found || true
kubectl delete namespace monitoring --ignore-not-found || true
echo "    Waiting 20s for GCP to release the load balancer..."
sleep 20

echo "==> [2/4] Destroying the GKE cluster with Terraform..."
cd infra
terraform destroy -var="project_id=$PROJECT_ID" -auto-approve
cd ..

echo "==> [3/4] Checking for orphaned billable resources (should all be EMPTY)..."
echo "--- Forwarding rules (LoadBalancers):"
gcloud compute forwarding-rules list --project=$PROJECT_ID
echo "--- Disks:"
gcloud compute disks list --project=$PROJECT_ID
echo "--- Static IP addresses:"
gcloud compute addresses list --project=$PROJECT_ID
echo "--- Clusters:"
gcloud container clusters list --project=$PROJECT_ID

echo "==> [4/4] (Optional) stop local Jenkins to free your laptop:"
echo "    docker stop jenkins"
echo ""
echo "DONE. If anything is listed above, delete it manually. Otherwise cost is ~zero."
echo "Kept (near-free): Artifact Registry images, your GCP project, local code/Git."


#!/bin/bash
# status.sh — quick at-a-glance state of the AI-SRE project.
# Read-only: it never changes anything. Safe to run anytime.

PROJECT_ID=ai-sre-platform-506305
REGION=us-central1
CLUSTER=ai-sre-cluster

echo "=================================================="
echo "  AI-SRE Platform — Status Check"
echo "=================================================="

# 1. Is the GKE cluster running (i.e. is it BILLING)?
echo ""
echo "1) CLUSTER (billing indicator)"
CLUSTER_STATUS=$(gcloud container clusters list \
  --project="$PROJECT_ID" \
  --filter="name=$CLUSTER" \
  --format="value(status)" 2>/dev/null)

if [ -z "$CLUSTER_STATUS" ]; then
  echo "   STOPPED  ->  No cluster found. Cost ~zero. (run terraform apply + restart.sh to start)"
  echo ""
  echo "=================================================="
  echo "  Nothing else to check while cluster is down."
  echo "=================================================="
  exit 0
else
  echo "   RUNNING  ->  status: $CLUSTER_STATUS   (this is COSTING money — run ./stop.sh when done)"
fi

# Make sure kubectl points at this cluster before pod checks
gcloud container clusters get-credentials "$CLUSTER" --region "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1

# 2. App pods
echo ""
echo "2) APP PODS (default namespace)"
kubectl get pods -n default --no-headers 2>/dev/null | awk '{printf "   %-38s %s  restarts:%s\n", $1, $3, $4}' || echo "   (unable to read pods)"

# 3. Monitoring pods
echo ""
echo "3) MONITORING PODS (monitoring namespace)"
kubectl get pods -n monitoring --no-headers 2>/dev/null | awk '{printf "   %-38s %s  restarts:%s\n", $1, $3, $4}' || echo "   (none / namespace missing)"

# 4. External IP of the dashboard
echo ""
echo "4) FRONTEND EXTERNAL IP"
IP=$(kubectl get svc frontend -n default -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
if [ -n "$IP" ]; then
  echo "   http://$IP"
else
  echo "   <pending or not deployed>"
fi

# 5. Grafana admin password (from the secret)
echo ""
echo "5) GRAFANA LOGIN"
GPASS=$(kubectl get secret grafana-secret -n monitoring -o jsonpath='{.data.password}' 2>/dev/null | base64 -d)
if [ -n "$GPASS" ]; then
  echo "   user: admin"
  echo "   pass: $GPASS"
  echo "   access: kubectl port-forward -n monitoring svc/grafana 3000:3000"
else
  echo "   (grafana-secret not found)"
fi

# 6. Secrets present?
echo ""
echo "6) SECRETS"
for s in gemini-secret slack-secret db-secret; do
  if kubectl get secret "$s" -n default >/dev/null 2>&1; then
    echo "   [ok]      $s (default)"
  else
    echo "   [MISSING] $s (default)"
  fi
done
if kubectl get secret grafana-secret -n monitoring >/dev/null 2>&1; then
  echo "   [ok]      grafana-secret (monitoring)"
else
  echo "   [MISSING] grafana-secret (monitoring)"
fi

# 7. Local Jenkins
echo ""
echo "7) LOCAL JENKINS (no GCP cost either way)"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^jenkins$'; then
  echo "   RUNNING  ->  http://localhost:8080   (stop with: docker stop jenkins)"
else
  echo "   stopped"
fi

echo ""
echo "=================================================="
echo "  Reminder: cluster is UP = billing. ./stop.sh to save cost."
echo "=================================================="


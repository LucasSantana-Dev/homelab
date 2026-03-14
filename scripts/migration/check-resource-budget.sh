#!/usr/bin/env bash
# Quick resource budget snapshot for the migration namespaces.

set -euo pipefail

echo "Namespace resource quotas"
kubectl get resourcequota -A

echo
echo "Top pods by memory"
kubectl top pods -A --sort-by=memory 2>/dev/null | head -n 20 || echo "kubectl top unavailable"

echo
echo "Node usage"
kubectl top node 2>/dev/null || echo "kubectl top unavailable"

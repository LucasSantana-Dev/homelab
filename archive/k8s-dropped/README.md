# K3s Migration Assets

This directory contains baseline manifests and Helm charts for the 90-day hybrid migration.

## Baseline

```bash
kubectl apply -f k8s/namespaces/namespaces.yaml
kubectl apply -f k8s/policies/limit-ranges.yaml
kubectl apply -f k8s/policies/resource-quotas.yaml
```

## Wave A

```bash
helm upgrade --install homepage k8s/helm/homepage -n apps
helm upgrade --install blackbox-exporter k8s/helm/blackbox-exporter -n observability
```

## Wave B

```bash
helm upgrade --install filebrowser k8s/helm/filebrowser -n apps
```

Use the compose edge (`nginx` + `cloudflared`) as entrypoint during phase 1, then progressively route traffic to these services.

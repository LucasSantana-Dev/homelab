# Homelab k3s Operations

Day-to-day Kubernetes operations for the homelab k3s cluster.

## When to Use

- Inspecting pod status, logs, or resource usage
- Deploying or upgrading Helm releases
- Debugging image pull failures or scheduling issues
- Verifying network policies and ingress routes
- Managing PVCs and storage

## Cluster Facts

- **Node**: single-node, `server-do-luk`
- **Version**: k3s v1.34.5+k3s1
- **Ingress**: Traefik (hosts use `.k3s.local` suffix for internal access)
- **Storage**: local-path provisioner for PVCs

## Access

The `/etc/rancher/k3s/k3s.yaml` kubeconfig is root-only. Use the user copy:

```bash
export KUBECONFIG=~/.kube/config
```

Add to shell profile to avoid setting it every session.

## Tool Paths

```bash
kubectl          # system PATH
~/.local/bin/helm
export PATH="$HOME/.local/bin:$PATH"
```

## Namespaces

| Namespace     | Purpose                          |
|---------------|----------------------------------|
| apps          | User-facing services             |
| observability | Monitoring and probing           |
| platform      | Cluster infrastructure           |
| kube-system   | k3s system components            |

## Resource Quotas

| Namespace     | CPU Request | Mem Request | CPU Limit | Mem Limit |
|---------------|-------------|-------------|-----------|-----------|
| apps          | 1           | 2Gi         | 1.5       | 3Gi       |
| observability | 500m        | 1Gi         | 1         | 1.5Gi     |

## Deployed Helm Releases

| Release          | Namespace     |
|------------------|---------------|
| traefik          | kube-system   |
| homepage         | apps          |
| blackbox-exporter| observability |

## Common Commands

```bash
# Pod status
kubectl get pods -A
kubectl get pods -n apps
kubectl rollout status deployment/<name> -n apps

# Resource usage
kubectl top pods -A
kubectl top nodes

# Helm
helm list -A
helm upgrade --install <release> <chart> -f <values> -n <namespace>
helm rollback <release> -n <namespace>

# Logs and debugging
kubectl logs <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous
kubectl describe pod <pod> -n <namespace>
kubectl exec -it <pod> -n <namespace> -- sh
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

## Network Policies

`default-deny-ingress` is active on `apps` and `observability`. Pods in those
namespaces will not receive traffic unless an explicit NetworkPolicy allows it.
Check policies before adding new services:

```bash
kubectl get networkpolicy -n apps
kubectl get networkpolicy -n observability
```

## Image Pull Issues

Docker Hub enforces rate limits on anonymous pulls. Prefer alternative
registries when available:

- `quay.io` — Red Hat / community images
- `ghcr.io` — GitHub Container Registry

`k3s ctr images import` requires `sudo` and is not available to the `luk-server`
user. Work around by using a registry mirror or referencing an image already
present on the node.

### Docker Hub Rate Limits — Solutions

Create an `imagePullSecret` in each namespace that needs Docker Hub access:

```bash
kubectl create secret docker-registry dockerhub-creds \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<user> \
  --docker-password="$(python3 -c "import json,base64; a=json.load(open('/home/luk-server/.docker/config.json')).get('auths',{}).get('https://index.docker.io/v1/',{}).get('auth',''); print(base64.b64decode(a).decode().split(':',1)[1]) if a else ''")" \
  -n <namespace>
```

Wire it into the Helm chart:

- `values.yaml`: add `image.pullSecret: dockerhub-creds`
- Deployment template `spec`: add `imagePullSecrets: [{name: "{{ .Values.image.pullSecret }}"}]` behind `{{- if .Values.image.pullSecret }}`

### Known Alternative Mirrors

| Image | Mirror |
|-------|--------|
| blackbox-exporter | `quay.io/prometheus/blackbox-exporter:v0.25.0` |
| homepage | `ghcr.io/gethomepage/homepage:v0.10.9` (already on ghcr.io) |
| filebrowser | No quay/ghcr mirror — use `dockerhub-creds` secret |

### DB Restore for Stateful Services

```bash
POD=$(kubectl get pod -n <ns> -l app.kubernetes.io/instance=<release> -o name | head -1 | cut -d/ -f2)
kubectl cp <backup.db> "<ns>/$POD:/database/filebrowser.db"
kubectl rollout restart deployment/<name> -n <ns>
```

## Traefik Ingress

Internal services are exposed via `IngressRoute` with hosts ending in `.k3s.local`.
To inspect routes:

```bash
kubectl get ingressroute -A
kubectl describe ingressroute <name> -n <namespace>
```

## Storage (local-path)

PVCs are provisioned by the `local-path` StorageClass. Data lives under
`/var/lib/rancher/k3s/storage/` on the node.

```bash
kubectl get pvc -A
kubectl describe pvc <name> -n <namespace>
```

## Safety Rules

- Always `export KUBECONFIG=~/.kube/config` before running kubectl/helm
- Check resource quota headroom before deploying new workloads
- Account for `default-deny-ingress` when wiring up new services
- Use registry mirrors to avoid Docker Hub rate-limit failures

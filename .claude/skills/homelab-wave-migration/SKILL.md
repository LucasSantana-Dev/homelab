# Homelab Wave Migration (Compose → k3s)

Execute phased migration of services from Docker Compose to k3s.

## When to Use

- Migrating any service from Docker Compose to k3s
- Running migration gates and preflight checks
- Cutover and rollback procedures
- Debugging Traefik ingress + NetworkPolicy issues

## Prerequisites

- k3s running: `k3s --version` and `kubectl get nodes`
- Terraform phase-1 complete (DNS records managed)
- SOPS + age validated (secrets workflow)
- Burn-in health: 12h window PASS
- Swap: ideally below 2.0 GiB (structural ~3 GiB is acceptable for low-risk services)

## Wave Definitions

### Wave A (stateless, low-risk) — COMPLETE ✅
- **homepage**: dashboard service
- **blackbox-exporter**: probe monitoring

### Wave B (stateful, restore drill required) — COMPLETE ✅
- **filebrowser**: NAS-like file management with bbolt DB

### Wave C (stateful, important services) — COMPLETE ✅
- **uptime-kuma**: monitoring dashboard (SQLite DB)
- **vaultwarden**: password manager (SQLite + RSA key)

### Wave D (next — complex stateful)
- **n8n**: workflow automation (SQLite, requires careful data migration)
- **pihole**: DNS sinkhole (custom config files)

### Not Suitable for k3s (requires docker.sock)
- **portainer**: container management
- **whats-up-docker**: container update monitor

## Migration Workflow

### 1. Pre-flight
```bash
make migration-preflight
bash scripts/migration/wave-a-status.sh
```

### 2. Build Helm Chart
Copy from existing chart pattern (e.g. `k8s/helm/filebrowser`):
- `Chart.yaml` — name, version, description
- `values.yaml` — image, service, ingress, resources, persistence
- `templates/_helpers.tpl` — name/fullname helpers
- `templates/deployment.yaml` — pod spec, probes, volumeMounts
- `templates/service.yaml` — ClusterIP service
- `templates/ingress.yaml` — Traefik ingress with `host: <name>.k3s.local`
- `templates/pvc.yaml` — local-path PVC

```bash
helm template <name> k8s/helm/<name> -n apps  # validate before deploy
```

### 3. Resource Quota Check
Quota for `apps` namespace: `limits.cpu=4000m, limits.memory=6Gi`

```bash
kubectl get resourcequota apps-budget -n apps
```

If exceeded, patch:
```bash
kubectl patch resourcequota apps-budget -n apps --type merge \
  -p '{"spec":{"hard":{"limits.cpu":"<new-value>","limits.memory":"<new-value>"}}}'
```

### 4. Deploy
```bash
export PATH="$HOME/.local/bin:$PATH" KUBECONFIG=~/.kube/config
helm upgrade --install <name> k8s/helm/<name> -n apps
```

### 5. Network Policy (CRITICAL)
Every pod needs a network policy to allow Traefik ingress, otherwise 502 Bad Gateway.
Add to `k8s/base/network-policies.yaml`:

```yaml
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-traefik-ingress-<name>
  namespace: apps
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: <name>
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              app.kubernetes.io/name: traefik
      ports:
        - protocol: TCP
          port: <containerPort>
```

```bash
kubectl apply -f k8s/base/network-policies.yaml
```

### 6. Data Migration (stateful services)

```bash
# Scale down target deployment
kubectl scale deployment <name>-<name> -n apps --replicas=0

# Create temp pod to access PVC
kubectl run data-restore --image=busybox --restart=Never -n apps \
  --overrides='{"spec":{"volumes":[{"name":"data","persistentVolumeClaim":{"claimName":"<name>-<name>-data"}}],"containers":[{"name":"restore","image":"busybox","command":["sleep","3600"],"volumeMounts":[{"name":"data","mountPath":"/data"}]}]}}'

# Copy data
kubectl cp /path/to/source/file apps/data-restore:/data/file

# Cleanup
kubectl delete pod data-restore -n apps
kubectl scale deployment <name>-<name> -n apps --replicas=1
```

### 7. nginx Cutover

Update `config/nginx/conf.d/tailscale-domains.conf`:
- Replace `proxy_pass http://<docker-service>:<port>;` with:
  ```nginx
  proxy_pass http://192.168.1.121:80;
  proxy_set_header Host <name>.k3s.local;
  ```
- Remove `proxy_set_header Host $host;` from location blocks with fixed Host override

```bash
docker exec nginx-proxy nginx -t && docker exec nginx-proxy nginx -s reload
```

### 8. Verify and Decommission

```bash
curl -s -w "\nHTTP_CODE:%{http_code}\n" https://<subdomain>.luk-homeserver.com.br -o /dev/null
bash scripts/migration/wave-a-status.sh
docker stop <container> && docker rm <container>
```

## Key Files

- `k8s/helm/*/` — Helm charts for each service
- `k8s/base/network-policies.yaml` — Traefik ingress allow rules (REQUIRED per service)
- `k8s/helm/environments/lab-values.yaml` — environment-specific values
- `k8s/namespaces/namespaces.yaml` — namespace definitions
- `config/nginx/conf.d/tailscale-domains.conf` — nginx reverse proxy config
- `scripts/migration/wave-a-status.sh` — health check for all migrated services

## Safety Rules

- Never migrate during active swap pressure event
- Always validate helm template before deploy: `helm template <name> k8s/helm/<name>`
- Network policy MUST be applied before testing via browser — missing policy = 502
- Keep Docker compose service definitions until burn-in confirmed
- Stateful: always scale to 0, copy data, scale to 1
- Run `wave-a-status.sh` after each migration

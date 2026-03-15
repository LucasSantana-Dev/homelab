# Homelab Wave Migration (Compose → k3s)

Execute phased migration of services from Docker Compose to k3s.

## When to Use

- Executing Wave A (homepage, blackbox-exporter) or Wave B (filebrowser) migration
- Running migration gates and preflight checks
- Cutover and rollback procedures

## Prerequisites

- k3s running: `k3s --version` and `kubectl get nodes`
- Terraform phase-1 complete (DNS records managed)
- SOPS + age validated (secrets workflow)
- Burn-in health: 12h window PASS
- Swap: ideally below 2.0 GiB (structural ~3 GiB is known but acceptable for low-risk services)

## Wave Definitions

### Wave A (low-risk, stateless)

- **homepage**: dashboard service
- **blackbox-exporter**: probe monitoring

### Wave B (stateful, requires restore drill)

- **filebrowser**: NAS-like file management with persistent data

## Migration Workflow

### 1. Pre-flight

```bash
make migration-preflight     # or: bash scripts/migration/preflight.sh
make migration-budget         # check resource budget
bash scripts/migration/wave-a-gate.sh  # run wave-a gate
```

### 2. Helm Chart Deployment

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
helm upgrade --install homepage k8s/helm/homepage -f k8s/helm/environments/lab-values.yaml -n apps
helm upgrade --install blackbox k8s/helm/blackbox-exporter -f k8s/helm/environments/lab-values.yaml -n monitoring
```

### 3. SOPS Secrets

```bash
export PATH="$HOME/.local/bin:$PATH"
export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
# Decrypt and apply
sops -d k8s/secrets/homepage-env.secret.enc.yaml | kubectl apply -f -
```

### 4. Cutover Checks

```bash
bash scripts/migration/cutover-checks.sh
```

### 5. Rollback (if needed)

```bash
bash scripts/migration/rollback-checks.sh
# Then restore compose service:
docker compose up -d --no-deps homepage
```

## Key Files

- `k8s/helm/*/` — Helm charts for each service
- `k8s/helm/environments/lab-values.yaml` — environment-specific values
- `k8s/namespaces/namespaces.yaml` — namespace definitions
- `k8s/policies/` — network policies, resource quotas, limit ranges
- `k8s/secrets/` — SOPS-encrypted secrets and templates
- `scripts/migration/` — all migration scripts

## Safety Rules

- Never migrate during active swap pressure event
- Always run cutover-checks before and after
- Keep compose service definitions intact until burn-in confirms k3s stability
- Rollback plan must be tested before cutover
- Wave B (stateful) requires documented restore drill

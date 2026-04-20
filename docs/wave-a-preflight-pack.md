# Wave A Preflight Pack (Homepage + Blackbox)

Prepared on March 14, 2026.

This cycle is preflight-only. Wave A deployment is deferred to a separate maintenance window after Terraform post-gate checks are clean.

## Current Preconditions

- Runtime health is green (`./scripts/homelab health`).
- Burn-in is passing (`./scripts/maintenance/burnin-status.sh`).
- Kubernetes API/context is reachable and stable.
- `apps` and `observability` namespaces exist with resource quotas.
- Helm lint/template sanity was captured in:
  - `/tmp/homelab-wave-a-preflight-20260314_121221`

## Preflight Refresh Commands (No Cutover)

Use these during the watch/apply window to keep preflight current without deploying:

```bash
cd /home/luk-server/homelab

helm lint ./k8s/helm/homepage
helm lint ./k8s/helm/blackbox-exporter
helm template homepage ./k8s/helm/homepage -n apps -f ./k8s/helm/environments/lab-values.yaml >/tmp/wave-a-homepage-template.yaml
helm template blackbox-exporter ./k8s/helm/blackbox-exporter -n observability -f ./k8s/helm/environments/lab-values.yaml >/tmp/wave-a-blackbox-template.yaml
make migration-preflight
make migration-budget
```

## Release Command Set

Preferred deploy commands for Wave A:

```bash
cd /home/luk-server/homelab

helm upgrade --install homepage ./k8s/helm/homepage \
  -n apps --create-namespace \
  -f ./k8s/helm/environments/lab-values.yaml \
  --set ingress.host=home.luk-homeserver.com.br

helm upgrade --install blackbox-exporter ./k8s/helm/blackbox-exporter \
  -n observability --create-namespace \
  -f ./k8s/helm/environments/lab-values.yaml \
  --set ingress.host=blackbox.luk-homeserver.com.br
```

Notes:
- `lab-values.yaml` keeps phase-1 shared settings (ingress class/edge mode).
- Explicit host overrides align Wave A ingress hosts with planned Terraform DNS names.

## Burn-In/Gate Command Set

Use this only in the later Wave A deployment window:

```bash
cd /home/luk-server/homelab
BURNIN_MINUTES=30 CHECK_INTERVAL_SECONDS=60 make wave-a-gate
```

If host pressure is borderline, run with a shorter observation first, then rerun full gate.

## Cutover Check Prerequisites

After deploy (in the separate Wave A window, before declaring cutover complete):

```bash
cd /home/luk-server/homelab

./scripts/migration/cutover-checks.sh apps homepage https://home.luk-homeserver.com.br
./scripts/migration/cutover-checks.sh observability blackbox-exporter https://blackbox.luk-homeserver.com.br
```

## Rollback Command Set

Rollback commands are pre-validated for both releases:

```bash
cd /home/luk-server/homelab

make wave-rollback NS=apps RELEASE=homepage REV=1
make wave-rollback NS=observability RELEASE=blackbox-exporter REV=1
```

Direct Helm fallback:

```bash
helm rollback -n apps homepage 1
helm rollback -n observability blackbox-exporter 1
```

## Execution Guardrails

- Do not run Wave A deploy/gate in this cycle.
- Only schedule Wave A window after:
  - T+24 pressure checkpoint is `GREENLIGHT`
  - Terraform apply path completes with post-plan no-op
  - Post-apply health, burn-in, migration-budget, and migration-preflight are green
- If swap trend worsens above ~2.0 Gi with upward trend or burn-in degrades, pause Wave A and schedule phase-2 host maintenance.
- Keep compose edge (`caddy-lan`, `cloudflared`) running for rollback safety. nginx-proxy was retired in PR #34; caddy-lan now owns :80 and routes to k3s Traefik.

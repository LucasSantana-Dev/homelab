# Wave A Preflight Pack (Homepage + Blackbox)

Prepared on March 14, 2026 for execution after the active host-pressure watch.

## Current Preconditions

- Runtime health is green (`./scripts/homelab health`).
- Burn-in is passing (`./scripts/maintenance/burnin-status.sh`).
- Kubernetes API/context is reachable and stable.
- `apps` and `observability` namespaces exist with resource quotas.
- Helm lint/template sanity was captured in:
  - `/tmp/homelab-wave-a-preflight-20260314_121221`

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

Use the existing gate for rollout/endpoints stability:

```bash
cd /home/luk-server/homelab
BURNIN_MINUTES=30 CHECK_INTERVAL_SECONDS=60 make wave-a-gate
```

If host pressure is borderline, run with a shorter observation first, then rerun full gate.

## Cutover Check Prerequisites

After deploy (before declaring cutover complete):

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

- Do not run Wave A deploy/gate before the pressure-watch T+24 checkpoint is accepted.
- If swap trend worsens above ~2.0 Gi with upward trend or burn-in degrades, pause Wave A and schedule phase-2 host maintenance.
- Keep compose edge (`nginx-proxy`, `cloudflared`) running for rollback safety.

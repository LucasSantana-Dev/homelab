# 90-Day Hybrid Migration Roadmap

## Target State (Day 90)

- Compose remains source of truth for critical stateful workloads.
- k3s runs low-risk workloads (`homepage`, `blackbox-exporter`, `filebrowser`).
- Terraform manages phase-1 DNS and declaration state for tunnel/network policy.
- SOPS + age is the default secret workflow for Kubernetes manifests.

## Phase Checklist

### Week 1: Serena + Foundations

- Run `scripts/deployment/setup-serena-mcp.sh`.
- Validate Serena memory files under `.serena/memories`.
- Run `scripts/migration/preflight.sh` and fix blockers.

### Weeks 1-4: Terraform Infra-first

- Configure `infra/terraform/terraform.tfvars`.
- Run `terraform fmt -check`, `terraform validate`, and `terraform plan`.
- Keep compose edge ingress (`nginx` + `cloudflared`) unchanged.

### Weeks 3-6: K3s Baseline

- Run `scripts/migration/bootstrap-k3s.sh`.
- Apply namespace quotas and default limits.
- Configure SOPS age key and test encrypt/decrypt cycle.

### Weeks 5-10: Migration Waves

- Wave A:
  - Deploy `homepage` chart in `apps`.
  - Deploy `blackbox-exporter` chart in `observability`.
  - Run `scripts/migration/cutover-checks.sh` for both.
- Wave B:
  - Deploy `filebrowser` in `apps` with local-path PVC.
  - Run backup/restore drill before traffic shift.

### Weeks 10-13: Stabilization

- Run rollback drills with `scripts/migration/rollback-checks.sh`.
- Confirm resource cap trend: no worsening swap pressure.
- Review ADRs and decide phase-2 entry for stateful workloads.

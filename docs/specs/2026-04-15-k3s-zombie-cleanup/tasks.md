# tasks — k3s-zombie-cleanup

- [x] Verify `archive/k8s-dropped/` is a complete snapshot (diff -rq k8s archive/k8s-dropped → empty).
- [x] Delete live `k8s/` tree.
- [x] Delete `scripts/migration/`, bootstrap k3s-secret scripts, `import-wave-g-images.sh`.
- [x] Delete `scripts/systemd/homelab-k3s-health.{service,timer}`.
- [x] Delete `.claude/skills/homelab-{k3s-ops,wave-migration}/`.
- [x] Delete `docs/wave-a-preflight-pack.md`, `docs/k3s-restart-baseline.md`, `docs/k8s-terraform-migration-roadmap.md`, `docs/k8s-phase2-readiness-gate.md`.
- [x] Prune k3s/kubectl/helm/wave-* targets from `Makefile`.
- [x] Remove k3s systemd entries from `scripts/deployment/install-systemd-services.sh`.
- [x] Strip kubectl checks from `scripts/maintenance/post-reboot-validate.sh` and `stabilize-host-prep.sh`.
- [x] Remove "Hybrid Migration" section + `k8s/` tree line from `README.md`.
- [x] Prune migration entries from `scripts/README.md`.
- [x] Remove `k8s/helm/.*/templates/` from `.pre-commit-config.yaml` excludes (keep `archive/k8s-dropped/`).
- [x] Mark this spec `status: shipped`, add PR URL.
- [x] Move spec entry in `docs/roadmap.md` from "Next (proposed)" to "Recently shipped".
- [x] Add CHANGELOG `[Unreleased] ### Removed` entry citing ADR 0004.
- [ ] Merge PR #38.

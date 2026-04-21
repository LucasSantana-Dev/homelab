---
status: shipped
created: 2026-04-15
shipped: 2026-04-20
owner: lucassantana
pr: https://github.com/LucasSantana-Dev/homelab/pull/39
tags: k3s,cleanup,audit-p0
---

# k3s-zombie-cleanup

## Goal
Excise k3s from the live repo per [ADR 0004](../../adr/0004-drop-k3s.md). All workloads consolidated on Docker Compose; k8s artifacts preserved under `archive/k8s-dropped/` for audit.

## Context
Audit P0 item #2. Original proposal ("pick Compose vs Helm per app") was superseded by ADR 0004 — the decision is that Compose wins every app. This spec tracks the *repo-level* teardown: deleting live k8s tree, migration scripts, systemd timer, Claude skills, and migration docs.

## Approach
1. Preserve `archive/k8s-dropped/` (already complete snapshot; verified via `diff -rq`).
2. Delete `k8s/`, `scripts/migration/`, `scripts/bootstrap/create-*-secrets.sh`, `scripts/maintenance/import-wave-g-images.sh`, `scripts/systemd/homelab-k3s-health.{service,timer}`, `.claude/skills/homelab-{k3s-ops,wave-migration}/`, `docs/wave-a-preflight-pack.md`, `docs/k3s-restart-baseline.md`, `docs/k8s-terraform-migration-roadmap.md`, `docs/k8s-phase2-readiness-gate.md`.
3. Prune k3s/kubectl/helm/wave-* references in `Makefile`, `README.md`, `scripts/README.md`, `scripts/deployment/install-systemd-services.sh`, `scripts/maintenance/post-reboot-validate.sh`, `scripts/maintenance/stabilize-host-prep.sh`, `.pre-commit-config.yaml`.
4. Update this spec (shipped), roadmap (Recently shipped), and CHANGELOG.

## Verification
- `grep -rEn "k3s|kubectl|\bhelm\b|k8s/" --exclude-dir=.git --exclude-dir=archive --exclude-dir=docs/adr --exclude=CHANGELOG.md` returns empty (or references only in audit/changelog/ADR context).
- `make help` shows no k3s/migration/wave targets.
- `bash -n scripts/deployment/install-systemd-services.sh` passes and has no `homelab-k3s-health` entries.
- `archive/k8s-dropped/` retains the full k8s snapshot including `secrets/`.

## Out of scope
- Host-side k3s uninstall (ADR 0004 assumes the host is already compose-only).
- `docs/adr/0001-0003` — kept as historical record.

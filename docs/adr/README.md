# Architecture Decision Records

Decisions about the homelab live here. Each ADR captures context, the decision
itself, alternatives considered, consequences, and a revisit-when trigger.

New ADRs use the next sequential number and copy the structure of any recent
file in this directory.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-compose-vs-k3s-boundary.md) | Compose vs K3s Boundary | Superseded by 0004 |
| [0002](0002-storage-boundary-local-path.md) | Storage Boundary (local-path) | Accepted |
| [0003](0003-ingress-boundary-compose-edge.md) | Ingress Boundary During Phase 1 | Accepted |
| [0004](0004-drop-k3s.md) | Drop K3s | Accepted |
| [0005](0005-media-stack-stremio-realdebrid.md) | Media stack — keep Stremio + RealDebrid, defer *arr migration | Accepted (revisit 2026-05-27) |
| [0006](0006-wol-via-shell-endpoint-not-gui-container.md) | Wake-on-LAN: shell endpoint + Homepage customapi, no GUI container | Accepted |
| [0007](0007-homelab-manager-clients-package.md) | `homelab_manager.clients` package: one owner per external dependency | Accepted |
| [0008](0008-wave4-compose-hygiene-image-pinning.md) | Wave 4: Compose Hygiene (Dead Anchors + Image Tag Pinning) | Accepted |
| [0024](0024-complete-k3s-decommission.md) | Complete the k3s decommission (staged, backup-first) | Accepted |
| [0025](0025-ops-alert-hub-simplest-first.md) | Ops alert hub — Alertmanager-direct + n8n aggregation; defer the LLM layer | Accepted |
| [0026](0026-notification-deadman-switch.md) | Catch silent notification failure with a dead-man-switch, not just a metric | Accepted |
| [0036](0036-host-config-management.md) | Host config git-first flow with dirty-file gate on `make deploy` | Accepted |
| [0037](0037-agent-box-resilient-boot-and-deploy-runbook.md) | Agent-box: non-fatal repo clones + SOPS/compose/deploy runbook (post-incident) | Accepted |

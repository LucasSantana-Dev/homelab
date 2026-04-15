---
status: proposed
created: 2026-04-15
owner: lucassantana
pr:
tags: k3s,cleanup,audit-p0
---

# k3s-zombie-cleanup

## Goal
Remove the broken k3s Helm stack that's been Pending/Error for 23h+ across authentik, filebrowser, homeassistant, homepage, jellyfin, nextcloud, pihole, vaultwarden, uptime-kuma, grafana, loki, prometheus, alertmanager, blackbox-exporter.

## Context
Audit P0 item #2. 15+ zombie pods churn etcd and disk. Every app that lives in Compose is duplicated as a broken Helm release; pick one runtime per app.

## Approach
1. Decide runtime per app (Compose vs Helm) — open ADR.
2. For each "Compose wins" app: `kubectl scale deployment/<name> --replicas=0` then delete Helm release.
3. For each "Helm wins" app: decommission Compose service, fix Helm.
4. Prune dangling PVCs only after 7-day cooldown.

## Verification
- `kubectl get pods -A --no-headers | awk '$4 != "Running" && $4 != "Completed"' | wc -l` → 0.
- No duplicate deployments for the 8 dual-runtime apps.

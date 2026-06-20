# ADR-0024: Complete the k3s decommission (staged, backup-first)

**Status:** Accepted
**Date:** 2026-06-20
**Deciders:** Lucas (solo operator)
**Relates:** [[ADR-0004]] (Drop K3s — Accepted but never executed), [[ADR-0020]] (Grafana/SSO via tinyauth, replacing Authentik)

## Context

[[ADR-0004]] decided to drop k3s and consolidate on Docker Compose, but the cluster was never actually removed. The 2026-06-20 health check found k3s still running on the host:

- **Workloads:** authentik (server, worker, postgresql, redis — 4 pods, 61d uptime) + the control plane (k3s-server, coredns, traefik, local-path-provisioner, metrics-server). metrics-server has restarted **541×** (crash-looping).
- **Cost:** authentik ~930Mi RAM; k3s-server ~524Mi + **~11% CPU sustained**; ~1.5–2GB RAM total. The host runs load 5–7 on 4 cores with active swapping — k3s is the largest single consumer and the driver of the only remaining firing Prometheus alert (`HighLoadAverage`).
- **Nothing routes to it.** Verified three ways: the Caddyfile sends `auth.<domain>` → `127.0.0.1:3030` (tinyauth, docker); `cloudflared/config.yml` routes **all 20 hostnames** → `http://host.docker.internal:80` (= caddy-lan); zero `reverse_proxy`/ingress lines point to k3s/traefik/any ClusterIP. The "k3s via Traefik ClusterIP" text in both files is a **stale comment**. SSO is tinyauth ([[ADR-0020]]); authentik is unreachable.

**The blocker (surfaced by a `decision-critic` review):** the authentik DB holds **3 users + 15 configured OAuth2 providers** in a k3s local-path-provisioner PV that **kopia does not back up**. Running `k3s-uninstall.sh` would destroy that config irreversibly — a load-bearing risk the "just uninstall it" framing ignored.

## Decision

**Decommission k3s, staged backup-first.** Not "uninstall now," not "keep."

1. **Back up authentik before removing anything** (DONE 2026-06-20): logical `pg_dump` of the authentik DB → `appdata/authentik-backup/authentik-db-20260620.sql` (2.8M, 165 tables, the 3 users + 15 providers). It lives in `appdata/`, which **is** in kopia's scope, so it is restorable and future-snapshotted.
2. **Then** `sudo /usr/local/bin/k3s-uninstall.sh` (operator-run — single destructive step, reserved for the operator).
3. Post-uninstall: confirm no k3s processes remain, verify host load/swap drop, re-test a tinyauth login.

The `decision-critic`'s additional steps (dry-run on a staging cluster, LVM snapshot, provider-parity matrix) were judged **over-engineered for a single-operator homelab** and dropped — the logical DB dump already makes the action reversible, and routing was verified clear.

## Alternatives considered

1. **Uninstall now (no backup)** — rejected: irreversible destruction of unbacked authentik config; one mis-assumption from a P1.
2. **Keep k3s** — rejected: pays ~1.5–2GB RAM + 11% CPU + a perpetual crash-loop indefinitely to host config nothing routes to; leaves [[ADR-0004]] permanently unfulfilled.
3. **Migrate authentik to Docker Compose** — rejected: the stack deliberately moved *away* from authentik to tinyauth ([[ADR-0020]]); re-homing an IdP nobody routes to is effort for no user.

## Consequences

**Positive:** frees ~1.5–2GB RAM + ~11% CPU, clears the `HighLoadAverage` alert, completes [[ADR-0004]], removes the crash-looping metrics-server and a whole second orchestrator's operational surface.

**Negative:** loses authentik as a live IdP (already unrouted, so no functional loss); restoring it later means standing up authentik fresh and importing the dump — a deliberate, non-trivial step.

**Neutral:** the `pg_dump` is a point-in-time copy; since authentik is unrouted, its config is static, so staleness is a non-issue.

## Revisit when

- A future need arises for a **full IdP** (richer SSO than tinyauth's forward-auth: SAML, per-app RBAC, OAuth2-provider role). Then: restore authentik from the dump onto Docker Compose (not k3s), or pick another IdP.
- A **multi-host / 50+ container** requirement appears (the original [[ADR-0004]] revisit trigger for k3s itself).
- If, after uninstall, host load does **not** drop materially → the attribution was wrong; investigate the next-largest consumer (Prometheus/Grafana/HA) instead.

## Prevention note

The authentik PV was never in kopia's scope — a backup gap that would recur if any k3s/non-docker workload is re-introduced. Rule: any stateful service **not** on Docker named-volumes / `appdata` / `config` must add an explicit backup path before it holds data.

# Homelab Audit — 2026-04-14

Six-domain audit run after the LAN-wide rollout (PR #9). Raw reports in this directory; this README is the prioritized backlog.

## Top 20 Actions (ordered by P0 → P2, risk × blast radius)

### P0 — Security / correctness (ship this week)

1. **Plaintext secrets in scripts** — `scripts/maintenance/recover-lucky-db.sh:9`, `scripts/maintenance/update-containers.sh:18-19,32` embed DB / Forge-MCP passwords inline. Move to `.env` + `source`; rotate leaked values.
2. **k3s cluster is broken fleet-wide** — authentik, filebrowser, homeassistant, homepage, jellyfin, nextcloud, pihole, vaultwarden, uptime-kuma, grafana, loki, prometheus, alertmanager, blackbox-exporter — all have Pending replicas ≥ 23h + Error/Evicted/ContainerStatusUnknown on old ones. Decide: fix (requires investigating node scheduling + PVC binding) or **scale every Deployment to 0** and delete daemonset PVCs that aren't recoverable. Leaving zombies burns disk + etcd churn.
3. **RDP (3389/tcp) open to `Anywhere`** in UFW. Scope to `192.168.0.0/24` or remove.
4. **23 services on `:latest`** across compose (n8n, mariadb, nextcloud, cloudflared, homepage, portainer, whats-up-docker, filebrowser, stremio, jellyfin, grafana, alertmanager, blackbox, prometheus, node-exporter, cadvisor, netdata, loki, promtail, pihole, vaultwarden, authentik-server×2). Pin to digests for everything, or at least to major.minor tags.
5. **8 apps duplicated across Compose AND k3s Helm** (authentik, filebrowser, homeassistant, homepage, jellyfin, nextcloud, pihole, vaultwarden). Pick one runtime per app — drift guarantees outage.

### P1 — Perf / ops quality

6. **16 compose services missing healthcheck**: homeassistant, cloudflared, homepage, uptime-kuma, portainer, whats-up-docker, filebrowser, dev-dashboard, stremio, grafana, prometheus, node-exporter, netdata, promtail, pihole, authentik-worker. Add `healthcheck:` block per service; without it, `restart: unless-stopped` can't detect hangs.
7. **Most services missing resource limits** (`deploy.resources.limits`) — OOM storm risk on the shared host. Add 512M / 0.5 CPU defaults; per-service tune for jellyfin / nextcloud.
8. **Python God-objects** — `cli/commands.py` (315 LOC) + `services/containers.py` (312 LOC). Split `commands.py` by verb group (containers / updates / health); split `containers.py` by concern (lifecycle / inspect / logs).
9. **Python deps far out of date** — astroid 3→4 (major), black 25→26, isort 6→8, imagesize 1→2, mypy 1.18→1.20, bandit 1.8→1.9. Bump dev extras, run lint, fix fallout in a single PR.
10. **12 scripts missing `set -euo pipefail`** (list in `scripts.md`). Adding it is a 1-line change per file; silent-failure blast radius is huge for backup/deployment scripts.
11. **`cloudflared` + `caddy-lan` have no resource limits**. Cap at 128M / 0.25 CPU — cheap win.
12. **Compose YAML repetition** — logging + healthcheck blocks repeat dozens of times. Extract to YAML anchors in `compose/base.yml`; saves ~120 LOC and centralizes changes.

### P2 — Polish / maintenance hygiene

13. **No Renovate / Dependabot config.** Draft minimal `renovate.json` with auto-merge on patch for `docker-image` + `github-actions`, manual for `python-dev`.
14. **Shellcheck hotspots**: `scripts/maintenance/update-containers.sh` (6 warnings), `scripts/security/security-scan.sh` (5), `scripts/maintenance/automated-backup.sh` (4). Fix + enable `shellcheck` in CI.
15. **Test coverage on `core/`, `utils/`, `models/` is 0 test files referencing them.** Add smoke tests for `config.py` validators + `service.py` models before the refactor in item 8.
16. **`compose/apps.yml` trusted-proxy env vars** still use `${TAILSCALE_IP}` (NEXTCLOUD_TRUSTED_DOMAINS, TRUSTED_PROXIES, PAPERLESS_TRUSTED_PROXIES). After LAN-wide flip, add `192.168.0.11` to each trust list.
17. **Apt upgradable** — run on host; capture reboot-required state before any refactor lands.
18. **GH Actions unpinned refs** — check `.github/workflows/*.yml` for floating `@v4` style tags; pin to SHAs at least for ci.yml's third-party actions.
19. **`scripts/lib/` is sparse (1 file).** Refactor duplicated prelude across `diagnose-*.sh` / `fix-*.sh` into `scripts/lib/common.sh`; source it everywhere.
20. **Dockerfiles** — audit for USER directive + HEALTHCHECK + multi-stage builds. (Detail in `compose.md`.)

## Reports
- [python.md](python.md) — LOC, complexity, dead code, test gaps
- [compose.md](compose.md) — image pins, healthchecks, resource limits
- [kubernetes.md](kubernetes.md) — zombie pods, chart inventory, duplication
- [scripts.md](scripts.md) — shellcheck, missing `set -euo`, credential patterns
- [security.md](security.md) — UFW, listeners, bandit, env-key classification
- [updates.md](updates.md) — pip outdated, image/compose/helm/apt version drift

## What's NOT in this audit
- Full Gitleaks history scan (only HEAD was covered). Plan in a separate session — force-push may be needed for genuine old leaks.
- Trivy per-image CVE rollup (deferred — slow + noisy). Run on demand via `trivy image <img>`.
- Actual refactor / migration decision between Compose and k3s — item 5 identifies the conflict; the decision is a separate design doc.

## Ship plan (wave 1)
- Item 1 (secrets out of scripts) — `fix/scripts-secret-hygiene` PR.
- Item 3 (UFW RDP scope) — 2-line `chore/ufw-scope-rdp` PR.
- Item 10 (`set -euo`) — mechanical `chore/scripts-strict-mode` PR.
- Item 13 (Renovate) — `chore/add-renovate` PR with auto-merge groups.
- Item 18 (pin GH Actions) — `chore/pin-gh-actions-sha`.
- This README + the six report files — `chore/audit-2026-04-14-reports` PR.

Target: 6 PRs opened within 48h, all CI-green, auto-squash merged.

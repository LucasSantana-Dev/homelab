# Changelog

All notable changes to Luk's Homelab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.6.0] - 2026-05-30

### Fixed

- **kopia backup container crash-loop** — removed the invalid
  `--without-password=false` flag from `compose/backup.yml`. In kopia 0.21.x
  `--without-password` is a no-value boolean; `=false` made kopia parse `false`
  as a stray positional (`unexpected false`) and exit 1, looping 4861× — so
  offsite B2 backups had never actually run. Password auth is the default when
  `--server-password` is set; added a guard comment. (ADR-0015)

### Added

- **ADR-0015** — hotfix lane reserved for active incidents, not long-standing
  broken features ("important" ≠ "urgent").
- **Prometheus alerting for Kopia backup service** — two new critical-severity
  alerts to catch backup container failures immediately:
  - `KopiaBackupDown`: fires when the kopia container is not seen by cAdvisor
    for >5m (container down, crashed, or unreachable).
  - `KopiaBackupRestartLoop`: fires when the kopia container restarts >3 times
    in a 15-minute window (catches crash-loops like the 4861-restart incident).
    Both alerts route via `severity: critical` to pagerduty/slack; existing
    cadvisor metrics provide the signal (no additional scrape job needed).
- **ADR-0016** — keep kopia server-mode (reject CLI-timer / restic migration on
  pull-signal grounds); add backup-verification roadmap (B2 Object Lock,
  snapshot-freshness alert, `verify --verify-files-percent=1`).
- **ADR-0017** — Portainer keeps read-write `docker.sock` (accepted risk;
  `:ro` breaks it, socket-proxy is theater for a Tailscale-only solo host).
  Inline defending-comments added on `compose/core.yml` (Portainer socket) and
  `homelab_manager/utils/validators.py` (intentional ADR-0007 shim, test-backed)
  so future audits reconcile via comment instead of re-flagging.

## [2.5.1] - 2026-05-28

Patch batch hardening homelab-manager error handling (no raw subprocess/
exception strings reach the HTTP API or CLI) and removing the redundant Snyk
SaaS layer in favour of the existing OSS scanning stack. Batches PRs #161, #162.

### Fixed

- **homelab-manager: subprocess/exception error messages are now scrubbed at
  every egress site** (M1 hardening, ADR-0007), closing paths where raw stderr
  or exception strings — env values, tokens, socket paths, checked URLs — could
  reach the HTTP API / CLI:
  - `deploy`/`restart` route compose failures through a new `ComposeCLI`
    seam method (`run_result`); `deployment.py` no longer has inline
    `try`/`except`/`run()` — the seam owns error handling.
  - `CommandSequence.run()` (backup/restore) scrubs both the
    `CalledProcessError` and generic-exception branches.
  - `HealthMonitor.check_container_health` and `check_service` scrub their
    Docker and HTTP error branches.

### Removed

- **homelab-manager: dead `utils/display.py` (`DisplayManager`)** — zero
  importers, zero tests; CLI builds Rich tables inline. Removed from
  `utils/__init__` exports.
- **Snyk (SaaS) security scanning** — removed the `.snyk` policy and the
  `snyk/` `.dockerignore` entry. Snyk's coverage is fully redundant with the
  free/OSS stack already in CI: CodeQL (SAST), Trivy (dependency + container +
  compose-config CVEs), gitleaks + GitGuardian (secrets), Socket (supply chain).
  The `code/snyk` check had been quota-failing on every PR. The `.snyk` path
  exclusions (`archive/**`, `dockerfiles/paperless-ngx/**`) are now mirrored into
  the Trivy `fs` step via `skip-dirs`. See ADR-0014. (Operator: uninstall the
  Snyk GitHub App to clear the `security/snyk` + `code/snyk` checks.)

### Added

- **ADR-0014** — replace Snyk with the existing OSS scanning stack; records the
  redundancy analysis, the Trivy exclusion migration, and revisit triggers.

## [2.5.0] - 2026-05-28

Minor release adding Lucky bot monitoring (Prometheus scrape + alert rules +
Grafana dashboard), Pi-hole v6 and CrowdSec connectivity fixes, vaultwarden
retirement, and a batch of CI dependency bumps. Batches PRs #135, #149–#159.

### Added

- **Lucky bot monitoring** — Prometheus scrape targets, alert rules, and a
  Grafana dashboard for the Lucky Discord bot and its backend. (#135)
- **ADR-0012** — polish the existing Grafana stack post-netdata; defer ML
  anomaly detection. (#150)
- **ADR-0013** — auto-deploy pipeline: host-side systemd timer that polls git
  for new `v*.*.*` tags and redeploys. (#149)

### Fixed

- **Pi-hole v6 compatibility** — set `listeningMode=ALL` and read drop-in
  configs from `/etc/dnsmasq.d`. (#151)
- **CrowdSec API port** bumped to 8091 to avoid a host-port collision with
  lucky-nginx (silent-orphan symptom). (#152)

### Removed

- **vaultwarden** — operator no longer uses the self-hosted Bitwarden vault.
  Service block removed from `compose/apps.yml`; declaration removed from
  `homelab_manager/data/services.yaml`; env vars (`VAULTWARDEN_ADMIN_TOKEN`,
  `IMG_VAULTWARDEN`, `VAULTWARDEN_PORT`, and the vaultwarden-scoped `SMTP_*`
  block) removed from `.env.example`. Server-side: stop + remove container,
  retain `appdata/vaultwarden` directory until the operator confirms data
  doesn't need to be exported. K8s helm chart already archived under
  `archive/k8s-dropped/helm/vaultwarden/` and is untouched.

### Changed

- CI dependency bumps: `actions/setup-python` 5.6.0→6.2.0 (#154),
  `codecov/codecov-action` 6.0.0→6.0.1 (#155), `github/codeql-action`
  4.35.4→4.36.0 (#156, #157), `hashicorp/setup-terraform` 3.1.2→4.0.1 (#158),
  `docker/setup-buildx-action` 3.12.0→4.1.0 (#159).

## [2.4.4] - 2026-05-16

Patch batch retiring netdata per ADR-0011 and shipping the baked-image
homelab-manager per ADR-0010. New deploy contract: source changes to
homelab-manager require `docker compose up -d --build homelab-manager`.
Post-deploy: drop the stale `homelab_netdataconfig`, `homelab_netdatalib`,
`homelab_netdatacache` volumes.

### Changed

- **homelab-manager now ships as a baked image** built locally via compose
  `build:` — replaces the runtime pip-install pattern (ADR-0010). Source
  changes require `docker compose up -d --build homelab-manager`. (#147)

### Removed

- **netdata service and homepage widget** — replaced by Prometheus + Grafana
  + node-exporter + cadvisor stack. See ADR-0011 for full rationale. (#146)
- homelab-manager's runtime pip-install command and `../:/app:ro` bind
  mount. (#147)

### Added

- **docs/runbooks/fallback-observability.md** — direct-scrape fallback
  queries for node-exporter and cadvisor when Prometheus or Grafana is
  unavailable. (#146)
- **ADR-0011** — full rationale for retiring netdata: CAP_FOWNER root
  cause, 90% capability/feature overlap with cadvisor + node-exporter,
  revisit triggers. (#146)

## [2.4.3] - 2026-05-16

Patch batch hot-fixing the v2.4.2 homelab-manager regression and recording the
packaging decision that retires the runtime pip-install pattern.

### Fixed

- **homelab-manager: copy only build artifacts, not the entire repo** — PR #141's
  `cp -r /app /tmp/build` copied the full `../:/app:ro` bind mount. On the live
  server that mount includes `appdata/` (Nextcloud, Paperless, etc.) and weighs
  **22 GB**, so `cp` hung and the container went unhealthy after `start_period`.
  Switch to a selective copy of `pyproject.toml`, `README.md`, and
  `homelab_manager/` only. Hot-patched on the server with `sed -i` during the
  v2.4.2 deploy; this release makes the fix durable. (#143)

### Documentation

- **ADR-0010: homelab-manager local Dockerfile build over runtime pip-install** —
  records the decision to retire the runtime pip-install pattern (which produced
  two release-impacting bugs in 24 h) in favour of a baked image built locally
  via compose `build:`. Includes seven alternatives considered, five revisit
  triggers (multi-server deployment, build time > 2 min, source > 50 MB,
  hot-reload workflow, base-image CVE), and implementation guidance for the
  follow-up PR. Decision is accepted; the Dockerfile rewrite ships in a later
  version under task #26. (#144)

## [2.4.2] - 2026-05-16

Patch batch addressing dashboard widget regressions discovered during v2.4.1
post-deploy QA, plus a Snyk policy to suppress dead-code noise.

### Fixed

- **Pi-hole healthcheck hits unauth endpoint** — PR #132's switch to
  `/api/info/version` regressed because Pi-hole v6 requires auth on all `/api/*`
  endpoints, returning 401 to `curl --fail`. Switch healthcheck to `/admin/`
  (returns 302, passes `--fail`). Container now reports healthy. (#139)
- **homelab-manager pip install fails on read-only mount** — `../:/app:ro` mount
  combined with pip's `egg_info` step writing into source tree caused
  `Cannot update time stamp of directory 'homelab_manager.egg-info'` and a
  restart loop. Copy `/app` to a writable tmpfs dir before invoking pip.
  Read-only mount preserved for security. (#141)
- **Homepage widget URLs use container-name routing for same-network services** —
  `host.docker.internal:<port>` only works for services bound to `0.0.0.0` on
  the host. `homelab-manager` and `netdata` are on the same `default` docker
  network as homepage; use their container names directly. `pihole` remains on
  `host.docker.internal` because it uses `network_mode: host`. Resolves
  `<!DOCTYPE` JSON-parse errors and `ECONNREFUSED 172.17.0.1:19999`. (#141)
- **Gatus healthcheck fails because image is distroless** — `twinproduction/gatus`
  ships only the `gatus` binary; no `curl`, `wget`, or `sh` for the
  `curl --fail` healthcheck. Container reported `(unhealthy)` despite serving
  traffic. Disable docker-level healthcheck; Gatus self-monitors via its own
  check loop. (#141)

### Changed

- **Snyk policy** — added `.snyk` excluding `archive/**` (k3s historical per
  ADR-0004), `dockerfiles/paperless-ngx/**` (upstream image), virtualenvs,
  test caches, and `claude-env/`. Eliminates ~80% of dashboard noise from
  third-party Helm charts and upstream-owned images. Fresh `snyk monitor`
  snapshots confirm 0 live vulns in scope. (#140)

## [2.4.1] - 2026-05-15

Patch batch covering Pi-hole DNS/healthcheck/widget fixes, cross-compose hostname
resolution, and removal of deprecated services from the dashboard.

### Fixed

- **Pi-hole host networking** — switched Pi-hole to `network_mode: host` for LAN-wide
  DNS resolution. Removes Docker bridge isolation that prevented LAN clients from using
  Pi-hole as their DNS server. Fixes `listeningMode` (`all` → `local`), adds explicit
  `FTLCONF_webserver_port=8054`, updates Homepage widget URL to
  `http://host.docker.internal:8054`, and adds `host.docker.internal:host-gateway`
  extra_hosts to Homepage container so the widget can reach the host-networked Pi-hole.
  (#131)
- **Pi-hole v6 healthcheck endpoint** — container reported `(unhealthy)` because the
  legacy `/api/` endpoint returns 404 in Pi-hole v6. Healthcheck now probes
  `/api/info/version`, which returns 200 on a working FTL instance. (#132)
- **Cross-compose widget hostnames** — Homepage widgets for `homelab-manager`,
  `netdata`, and `pihole` were hitting ENOTFOUND because containers in separate
  Compose files cannot resolve each other by service name. Widget URLs now use
  `http://host.docker.internal:<port>` consistently. (#133)
- **Pi-hole widget API key** — `HOMEPAGE_VAR_PIHOLE_KEY` was wired to
  `${PIHOLE_WEB_PASSWORD}`, which made the widget post the web-UI password to the v6
  API and receive HTML back instead of JSON. Renamed to `${PIHOLE_API_KEY:-}` so the
  widget uses a Pi-hole App Password generated under Settings → API. Server-side
  manual step: generate the App Password and set `PIHOLE_API_KEY` in `.env`. (#134)

### Removed

- **Deprecated services pruned** — `linkding`, `miniflux` (+ `miniflux-db`), `forgejo`,
  and `open-webui` removed from `compose/apps.yml` and the Homepage dashboard. None
  were in active use; their presence caused dashboard noise and stale healthcheck
  warnings. n8n confirmed in use and retained. (#136)

## [2.4.0] - 2026-05-15

Second release under the release-branch model. Batches 7 PRs (#115–#121) covering
security hardening, deploy reliability, dashboard expansion, HTTP API, test
coverage uplift, and code quality.

### Added

- **Homepage Projects tab** — new `pages:` tab with GitHub release + commit-activity
  widgets for `homelab` and `ai-dev-toolkit` repos. Requires `HOMEPAGE_GITHUB_TOKEN`
  (5 000 req/hr vs 15/hr unauthenticated). Closes #107, #108. (#117)
- **Gatus uptime widget** — Homepage header now shows live endpoint-status summary
  from the Gatus container (no additional network wiring needed). Closes #110. (#118)
- **`homelab_manager` HTTP API server** — lightweight stdlib HTTP server with
  `/health`, `/status`, and `/summary` endpoints on `127.0.0.1:8765` (loopback-only;
  Caddy + Authentik forward-auth is the pre-condition for external exposure per
  ADR-0009). Adds `homelab serve` CLI command and a `homelab-manager` compose service
  in `compose/core.yml`. Homepage customapi widget shows total/healthy/unhealthy
  service counts with 60 s auto-refresh. Closes #112. (#120)
- **`homelab_manager` package restructure (R1)** — new `clients/` subpackage owns
  Docker SDK + `docker compose` CLI invocations (`DockerClientFactory`, `ComposeCLI`).
  H6 registry allowlist + M1 stderr-scrubbing lifted into `ComposeCLI.logs()` and
  `core/errors.scrub_subprocess_error()`. (`docs/adr/0007-homelab-manager-clients-package.md`)
- **Closed M4 coverage gap** — `core/config.py` 62% → 100% via 21 new tests.
  Whole-package coverage 81% → 86%; suite 233 → 284 passed.

### Changed

- **`DeploymentManager` migrated to `ComposeCLI`** — drops `CommandSequence`/`Step`
  dependency; constructor-injected `ComposeCLI` enables clean unit testing without
  import-path patching. `ComposeCLI.run()` gains a `cwd` kwarg. Closes #113. (#121)
- **15 real automation unit tests** — replaces placeholder boilerplate in
  `tests/unit/test_automation.py` with `TestConfigValidator` (9), `TestRestartAutomationService` (3),
  and `TestHealthMonitorHTTP` (3). Closes #111. (#119)

### Fixed

- **Stale volume mounts removed** — four dead bind-mounts in `compose/core.yml`
  (`cloudflared` config dir, nginx/certbot path for homepage/portainer/whats-up-docker)
  caused bind-mount errors on fresh deploys. Closes #105, #109. (#116)

### Security

- **n8n basic-auth dead vars removed** — `N8N_BASIC_AUTH_ACTIVE/USER/PASSWORD` env
  vars are silently no-ops in n8n v1.0+ (basic auth removed in favour of built-in
  user management); removed from `compose/apps.yml` and `.env.example`. Port 5678
  now bound to `127.0.0.1` only (was `0.0.0.0`) — eliminates direct LAN bypass of
  Caddy+Tinyauth. Closes #104, #106. (#115)
- **Latent M1 violation closed in `services/updates.py`** — all 4 error handlers
  now use `scrub_subprocess_error(exc, context=...)` instead of echoing raw
  `e.stderr` (could leak env values / paths).

## [2.3.0] - 2026-05-14

First release cut under the release-branch model. Batches 9 PRs (#77 → #85)
focused on audit-deep remediation: security hardening, supply-chain pinning,
test coverage, CI gate enforcement, and stale-config cleanup.

### Added

- **Dependabot configuration** — `.github/dependabot.yml` enables weekly Monday audits for pip, docker, and github-actions ecosystems. Bot PRs target the `release` branch (matching the release-branch model) so `/dep-sweep` can batch them. Closes audit-deep HIGH H4.
- **ADR 0005 — Media stack: Stremio + RealDebrid (conditional)** — documents the decision to keep Stremio+RealDebrid as the primary media surface, reject Plex permanently, and defer Jellyfin+*arr migration. Conditional on 4 pre-conditions (deadline 2026-05-27) and 7 operational revisit triggers. (`docs/adr/0005-media-stack-stremio-realdebrid.md`)
- **Unit test coverage for previously untested modules** — closes audit-deep H5+H7. New files: `tests/unit/test_command_sequence.py` (13 tests), `tests/unit/test_backup_manager.py` (8 tests), `tests/unit/test_deployment.py` (10 tests), `tests/unit/test_status.py` (13 tests). Per-module coverage: command_sequence 50→100%, backup_manager 32→100%, deployment 48→100%, status 29→98%. Suite-wide: 71→80%.

### Security

- **Cleanup + supply-chain pin pass** — closes audit-deep v2 **C2 + H3 + H4 + H5**.
  - **C2** Removed dangling `nginx` service block from `compose/core.yml` (PR #78 deleted `config/nginx/` but left the service referencing 5 non-existent bind mounts; fresh `docker compose up` now succeeds).
  - **H4** Pinned 4 floating Docker tags: `home-assistant:stable`→`:2025.5`, `netdata:stable`→`:v1.48.0`, `paperless-ngx:latest`→`:2.13`, `redis:alpine`→`:7.4-alpine`. All overridable via existing `IMG_*` env vars.
  - **H3** Fixed `.github/dependabot.yml`: replaced ineffective `docker` ecosystem at `/` with `docker-compose` ecosystem at `/compose` so image-tag updates actually get auto-PR'd.
  - **H5** SHA-pinned `github/codeql-action/upload-sarif@v3` (2 instances in `.github/workflows/ci.yml`) to v3.35.4 commit `7fd177f` to close the action-tag-moving supply-chain vector.
- **`status.py` hardened** — closes audit-deep v2 **H6 + M1**.
  - **H6** `get_service_logs` now allowlists `service_name` against `ServiceRegistry` before invoking `docker compose logs`. Closes the CLI argument-injection vector (an unvalidated name like `--no-log-prefix` would otherwise become a docker-compose flag). Also clamps `lines` to 1..10000 and rejects non-integer input.
  - **M1** Docker SDK exception details are no longer echoed to console — only the exception type name surfaces; full traceback is logged at DEBUG via stdlib `logging`. Prevents auth tokens / socket paths / env values from leaking into user-visible output. 9 new tests added (suite: 227→233, coverage 80→81%).
- **ADR 0006 — Wake-on-LAN via shell endpoint** — Accepted (2026-05-14). Documents the WoL approach: shell endpoint + Homepage `customapi` widget, no GUI container.
- **`update-containers.py` exec() removed + n8n chown documented** — closes audit-deep v2 **M2 + M3**.
  - **M2** `scripts/maintenance/update-containers.py` no longer uses `exec(open(activate_script).read())` for venv activation. Now uses `os.execv` to re-exec into the venv's `python` binary if invoked outside it — same effect, no code-exec risk if the venv is tampered with.
  - **M3** Created `docs/deployment-prerequisites.md` documenting the n8n `sudo chown -R 1000:1000 appdata/n8n` step required after PR #81's UID-1000 switch. Also captures the pending Cloudflare tunnel rotation (audit-deep v2 C1) and Homepage server-side v0.10.9→v1.0.3 bump.

### Changed (CI)

- **Pytest gate enforced** — closes audit-deep H6. Removed `continue-on-error: true` from `.github/workflows/ci.yml`. Test failures now fail CI.
- **`test_cpu_below_warning_threshold` reclassified as opt-in smoke check** — closes audit-deep M7. Test is brittle when pytest itself dominates CPU. Skips unless `HOMELAB_HEALTH_CHECK=1` is set; median-of-5 sampling retained when enabled.

### Security

- **Docker container hardening** — closes audit-deep HIGH H1+H2+H3 and MEDIUM M2+M3.
  - agent-box: `/var/run/docker.sock` now mounted `:ro` (read-only).
  - n8n: dropped `user: "root"`, runs as UID 1000 (image's default `node` user). Server prerequisite: `chown -R 1000:1000 ../appdata/n8n`.
  - Home Assistant: `user: root` retained (USB device passthrough requirement) with inline justification comment; also dropped stale nginx certbot mount missed in PR #78.
  - cadvisor: replaced `privileged: true` with explicit `cap_add: [DAC_READ_SEARCH, SYS_PTRACE]` + `cap_drop: ALL` + `no-new-privileges`.
  - netdata: explicit `cap_drop: ALL` + scoped caps; `apparmor:unconfined` retained per upstream requirement with inline rationale; added `no-new-privileges`.
  - Loki: removed `${BIND_IP:-0.0.0.0}:3100` binding (Grafana reaches Loki over internal docker network); only `127.0.0.1:3100` retained for host debugging.

### Changed

- **Docs sweep — strip stale Authentik/nginx/Vaultwarden references** — README, `docs/access-layers.md`, `docs/public-release-hardening.md`, and `Makefile` updated to reflect the current Tinyauth + Caddy + Cloudflared stack. Three dead Makefile targets (`sso-register-apps`, `sso-register-dry-run`, `sso-register-status`) and `scripts/maintenance/authentik-register-apps.sh` archived under `archive/scripts-dropped/`. Closes audit-deep HIGH H8.

### Removed

- **nginx-proxy service + `config/nginx/` tree + stale Authentik nginx include configs** — Caddy and Cloudflared own all ingress now. The nginx-proxy service had been dead code with broken mount paths since the Authentik removal in PR #63; `/audit-deep` flagged this as 2 CRITICAL findings (missing mount dirs that broke fresh deploys + stale Authentik outpost configs hardcoding `192.168.1.121`). Archives: `docs/authentik-sso-setup.md` → `archive/docs-dropped/`, `config/k3s/registries.yaml.example` → `archive/k8s-dropped/k3s/`.

- **k3s / Hybrid Migration tooling** - Executed [ADR 0004](docs/adr/0004-drop-k3s.md): all workloads consolidated on Docker Compose. Deleted live `k8s/` tree, `scripts/migration/`, bootstrap k3s-secret scripts, `homelab-k3s-health.{service,timer}`, `.claude/skills/homelab-{k3s-ops,wave-migration}/`, plus migration docs (`wave-a-preflight-pack.md`, `k3s-restart-baseline.md`, `k8s-terraform-migration-roadmap.md`, `k8s-phase2-readiness-gate.md`). Pruned k3s/kubectl/helm references from `Makefile`, `README.md`, `scripts/README.md`, deployment/maintenance scripts, and `.pre-commit-config.yaml`. Historical snapshot preserved under `archive/k8s-dropped/`.

### Added (Operations)

- **Lucky DB recovery runbook** - Added `docs/lucky-db-recovery-runbook.md` with backup-only and full-recovery workflows for `ERR_DB_SCHEMA_MISSING`, including verification commands and backup location checks.
- **k3s restart baseline note** - Added `docs/k3s-restart-baseline.md` to classify historical restart counts vs actionable incidents after migration waves.

### Fixed (Database Reliability)

- **Lucky Postgres persistence guardrail** - Documented and operationalized `PGDATA=/var/lib/postgresql/data` requirement for `postgres:18-alpine` to prevent schema/data drift outside mounted volume.

### Added (Automation and Registry)

- **Nextcloud as Primary NAS Service** - Enhanced Nextcloud configuration and documentation for Network Attached Storage use case
  - Updated service description to highlight NAS capabilities and mobile app support
  - Added comprehensive mobile app setup documentation (iOS and Android)
  - Documented NAS features: file sync, sharing, external storage (SMB/CIFS, NFS, WebDAV), automatic photo backup
  - Updated homepage configuration to emphasize NAS and mobile app capabilities
  - Mobile app links: [iOS App Store](https://apps.apple.com/app/nextcloud/id1125420102) and [Google Play Store](https://play.google.com/store/apps/details?id=com.nextcloud.client)

- **Cursor Rules, Agents, and Skills** - Comprehensive AI assistance framework for homelab management
  - **New Rules** (`.cursor/rules/`):
    - `python-patterns.mdc` - Python code patterns: ServiceRegistry usage, DI patterns, type hints, Rich console
    - `docker-compose-patterns.mdc` - Docker Compose standards: networks, volumes, health checks, resource limits
    - `service-registry.mdc` - Service registry as single source of truth enforcement
    - `testing-patterns.mdc` - Testing standards: mocking patterns, test structure, fixtures
  - **New Skills** (`.cursor/skills/`):
    - `service-deployment/` - Service deployment workflow with templates and checklists
    - `health-checks/` - Health check automation with Prometheus/Grafana templates
    - `backup-restore/` - Backup/restore procedures with retention policies
    - `service-troubleshooting/` - Systematic troubleshooting workflow
    - `configuration-management/` - Configuration validation and change management
  - **Cursor Sub-Agents** (`.cursor/agents/`):
    - `service-management.yml` - Specialized agent for service operations
    - `monitoring.yml` - Observability and health monitoring agent
    - `security-audit.yml` - Security compliance and audit agent
  - **Docker Agents** (`agents/docker/`):
    - `service-deployment.yml` - Automated deployment with validation and rollback
    - `health-monitoring.yml` - Continuous health monitoring with alerting
    - `backup-restore.yml` - Automated backup/restore with retention
    - `update-management.yml` - Safe container updates with health checks

### Changed (CI and Build)

- **Container Updates** - Updated all homelab containers to latest versions (2026-01-01)
  - **Core Services**: nginx, homepage, portainer, uptime-kuma, whats-up-docker, filebrowser
  - **Monitoring Stack**: prometheus, grafana, loki, promtail, alertmanager, netdata, blackbox-exporter, node-exporter, cadvisor
  - **Media Services**: jellyfin, stremio
  - **Application Services**: n8n, nextcloud, nextcloud-db, nextcloud-redis, paperless-ngx, paperless-db, paperless-redis
  - **Security Services**: pihole, vaultwarden, authentik-server, authentik-worker, authentik-db, authentik-redis
  - **Automation Services**: homeassistant
  - All containers restarted to apply latest image updates

### Added

- **Automated Weekly Container Updates** - Cron job for automatic container updates
  - Weekly cron job runs every Sunday at 3:00 AM
  - Uses safe rolling update script with health checks
  - Wrapper script (`update-containers-cron.sh`) ensures correct environment
  - Fixed HOMELAB_DIR path calculation in update script
  - Logs to `logs/update-cron.log`
  - Prevents concurrent updates with lock file mechanism

- **Complete ServiceRegistry Integration** - All service managers now use the centralized registry
  - `HealthMonitor` refactored to use `ServiceRegistry` for health checks
  - `UpdateManager` refactored to use `ServiceRegistry` for service validation
  - CLI `urls` command now dynamically generates URLs from registry
  - Added new `services` command to list all registered services by category

- **Dependency Injection in CLI** - Improved testability with DI pattern
  - `create_app()` now accepts optional manager instances for testing
  - All managers (config, container, health, update) can be injected
  - ServiceRegistry can be shared across managers

- **Dynamic Version Management** - Single source of truth for version
  - Version now read from installed package metadata via `importlib.metadata`
  - Fallback to hardcoded version for development mode
  - Eliminates version drift between `__init__.py` and `pyproject.toml`

- **Environment Validation Script** - New `scripts/security/validate-env.sh`
  - Validates required environment variables (TAILSCALE_IP, DOMAIN, etc.)
  - Checks for placeholder values in configuration
  - Optional strict mode for CI/CD pipelines
  - Color-coded output for easy reading

- **Modular Docker Compose Architecture** - Split monolithic docker-compose.yml into domain-specific modules
  - `compose/base.yml` - Networks and volumes definitions
  - `compose/core.yml` - Nginx, Homepage, Portainer, Uptime Kuma, What's Up Docker, FileBrowser
  - `compose/monitoring.yml` - Prometheus, Grafana, Loki, Alertmanager, Netdata, Node-exporter, cAdvisor
  - `compose/media.yml` - Jellyfin, Stremio
  - `compose/apps.yml` - n8n, Paperless-ngx, Nextcloud (with databases and Redis)
  - `compose/security.yml` - Authentik, Vaultwarden, Pi-hole
  - `compose/automation.yml` - Home Assistant
  - Main `docker-compose.yml` now uses `include:` directive for unified deployment
  - Selective module deployment: `docker compose -f compose/core.yml up -d`

- **Service Registry** - Declarative service definitions in YAML
  - New `homelab_manager/data/services.yaml` with all 31 services
  - Service model with category, port, health endpoint, sensitivity flag
  - Python dataclass in `homelab_manager/models/service.py`
  - Container manager now uses registry instead of hardcoded values

- **Consolidated Dependency Management** - Single source of truth for Python dependencies
  - Updated `pyproject.toml` with all dependencies and optional groups
  - Removed duplicate `scripts/requirements.txt` and `scripts/requirements-dev.txt`
  - Optional dependency groups: `[dev]`, `[docs]`, `[profile]`
  - Install with: `pip install -e ".[dev]"`

- **Reorganized Scripts Directory** - Functional subdirectories for better organization
  - `scripts/deployment/` - startup-services.sh, shutdown-services.sh, install-systemd-services.sh
  - `scripts/maintenance/` - automated-backup.sh, update-containers.sh, update-containers.py
  - `scripts/monitoring/` - container-status.py, status-services.sh
  - `scripts/security/` - security-scan.sh
  - `scripts/systemd/` - Service unit files (renamed from systemd-services)
  - `scripts/hacs/` - Home Assistant specific scripts
  - Added `scripts/README.md` documenting the new structure

### Changed (Tooling)

- **CI/CD Pipeline** - Updated to use pyproject.toml
  - Uses `pip install -e ".[dev]"` for dependency installation
  - Runs pre-commit hooks for code quality
  - Updated cache keys to use pyproject.toml hash

- **Makefile** - Updated script paths for reorganized structure
  - Backup: `scripts/maintenance/automated-backup.sh`
  - Security: `scripts/security/security-scan.sh`
  - Updates: `scripts/maintenance/update-containers.sh`
  - Systemd: `scripts/systemd/` directory

- **Configuration Management** - Enhanced with service registry
  - `core/config.py` now uses ServiceRegistry for URL generation
  - Dynamic service URL generation from registry

### Fixed (Home Assistant and Updates)

- **Network Conflicts** - Removed duplicate network definitions in compose modules
- **Systemd Service** - Updated homelab-update.service with new script path

### Changed

- **Pre-commit Hooks Updated** - Synchronized versions with pyproject.toml
  - black: 23.7.0 -> 24.8.0
  - isort: 5.12.0 -> 5.13.2
  - flake8: 6.0.0 -> 7.1.1
  - mypy: 1.5.1 -> 1.11.2
  - bandit: 1.7.5 -> 1.7.9
  - shellcheck: 0.9.0.6 -> 0.10.0.1
  - yamllint: 1.32.0 -> 1.35.1
  - markdownlint: 0.35.0 -> 0.41.0
  - commitizen: 3.13.0 -> 3.29.0

### Removed

- **Duplicate Test Files** - Removed broken `test_*_simple.py` files
  - `test_container_manager_simple.py` - referenced non-existent modules
  - `test_updates_simple.py` - referenced non-existent modules
- **Backup Files** - Cleaned up `docker-compose.yml.backup` and `docker-compose.yml.pre-modularization.backup`
  - Added backup file patterns to `.gitignore`

### Smart Home Integrations (Previous) - Comprehensive Home Assistant integration setup

- Configured Xiaomi Home integration (4 devices: 3 Yeelight bulbs, 1 robot vacuum)
- Configured LG ThinQ integration (1 device: air conditioner)
- Configured Tuya integration (2 devices: smart switches)
- Installed HACS add-ons: Adaptive Lighting, Node-RED Companion, Auto Backup, card-mod, Mushroom
- Created voice assistant templates for Google Assistant and Amazon Alexa
- Created comprehensive automations for climate, lighting, energy, and media
- Created dashboard YAML configurations (main, energy, climate, security, media)
- Fixed Home Assistant configuration syntax errors in YAML files
- Updated secrets.yaml with placeholder values for all integrations
- Created integration setup documentation at `docs/homeassistant-integrations-guide.md`

### Fixed (Auth, Containers, and DNS)

- **Home Assistant Configuration** - Fixed multiple YAML configuration issues
  - Fixed recorder.yaml structure (removed nested key issue)
  - Fixed input_helpers.yaml by splitting into separate files (input_boolean, input_number, input_select)
  - Fixed energy.yaml by splitting into energy_sensors.yaml and utility_meters.yaml
  - Fixed automations.yaml to use persistent_notification instead of placeholder device names
  - Fixed scripts.yaml with valid notification services
  - Removed invalid configuration parameters from mobile_app include
  - Fixed Docker Compose network_mode and networks conflict

- **Automated Container Updates** - Safe rolling update system with systemd timer
  - New `scripts/update-containers.sh` script with safe update orchestration
  - Updates containers in priority groups: databases → core → apps → monitoring → utilities
  - Health checks between each container restart to ensure service stability
  - Pre-update backup of critical configuration files
  - Discord webhook notifications for update start/completion/failures
  - Systemd timer runs every 5 days at 3:00 AM with randomized delay
  - Dry-run mode for preview without making changes
  - New Makefile targets: `update-safe`, `update-dry-run`, `update-timer-install`, `update-timer-status`, `update-logs`
  - Lock file prevents concurrent update runs

- **Auto-Start Services** - Configured automatic startup for all Docker Compose stacks on boot
  - Created systemd services for homelab-docker, satisfactory-server, and lukbot
  - Services automatically start after Docker and Tailscale are ready
  - All services configured with proper dependencies and startup delays
  - Helper scripts for manual service management (startup, shutdown, status)
  - BIOS power-on configuration guide for Intel N100 systems
  - Installation script for easy systemd service setup
  - See `docs/bios-power-on-setup.md` for BIOS configuration instructions

### Fixed

- **Authentik Healthcheck** - Fixed Authentik server healthcheck failure
  - Replaced `curl`-based healthcheck with Python-based check (curl not available in container)
  - Updated healthcheck to accept HTTP 200 or 204 status codes from `/-/health/live/` endpoint
  - Authentik server now reports healthy status correctly

- **Container Updates** - Updated 25 outdated homelab containers to latest versions (2025-12-23)
  - Updated 23 homelab compose services: alertmanager, authentik-db, authentik-redis, blackbox-exporter, filebrowser, grafana, homeassistant, homepage, jellyfin, loki, n8n, netdata, nextcloud, nextcloud-db, nextcloud-redis, nginx-proxy, paperless-db, paperless-redis, pihole, portainer, prometheus, promtail, stremio-server
  - Removed 2 orphan cloudflared containers (silly_hoover, pedantic_brahmagupta) that were using outdated images
  - Pulled latest images using `docker compose pull` and recreated containers with `docker compose up -d --remove-orphans`
  - Cleaned up 10.79GB of unused Docker images
  - All containers verified healthy and running latest available versions

- **Authentik DNS Resolution and Access** - Fixed network isolation and IP restrictions preventing access to Authentik
  - Added `frontend` network to nginx service in docker-compose.yml for Nginx-Authentik communication
  - Removed redundant nginx IP restrictions (services already bound to Tailscale IP at Docker level)
  - Fixed 403 Forbidden errors caused by Docker bridge network IPs being blocked
  - Created comprehensive DNS setup guide at `docs/dns-setup.md`
  - Documented three DNS configuration options: Tailscale MagicDNS (recommended), local /etc/hosts, DuckDNS
  - Resolved permission issues with Authentik Redis and PostgreSQL by restarting services
  - Authentik SSO now fully accessible at <https://auth.homelab.example.com>

### Security

- **Removed Hardcoded IP Addresses** - Enhanced security by removing exposed Tailscale IP from codebase
  - Replaced hardcoded IPs in nginx config comments with reference to `.env` file
  - Updated DNS documentation to use `<YOUR_TAILSCALE_IP>` placeholders
  - Updated README examples to reference `.env` variables
  - All sensitive IPs now only stored in `.env` file (git-ignored)

## [3.0.0] - Future Enhancements - Network Segmentation, Authentik SSO & Paperless-ngx

### Added

- **Network Segmentation Guide** - Manual deployment guide for service-to-network assignments
  - Created `docs/network-migration-guide.md` with detailed migration steps
  - 4 networks defined: frontend (172.20.0.0/24), backend (172.21.0.0/24), monitoring (172.22.0.0/24), database (172.23.0.0/24)
  - Database networks configured as internal-only (no internet access)
  - Service connectivity validation checklist and rollback procedures
  - **DEFERRED**: Network assignment to maintenance window (requires service disruption)

- **Authentik SSO** - Enterprise single sign-on identity provider
  - Created `docs/authentik-sso-setup.md` with complete OAuth2/OIDC integration guide
  - PostgreSQL 15 database for user data
  - Redis cache for session management
  - Configured for Grafana, Portainer, and n8n OAuth2/OIDC integration
  - Accessible at <https://auth.homelab.example.com> (Tailscale only)
  - Ports: 9100 (HTTP), 9443 (HTTPS) - Changed from 9000 to avoid conflict with Portainer
  - Resource limits: Server (1G RAM max, 1.0 CPU max), Worker (512M RAM max, 0.5 CPU max), DB (512M RAM max, 0.5 CPU max), Redis (128M RAM max, 0.25 CPU max)
  - Total additional resources: ~1.5GB RAM, ~1.5 CPU cores

- **Paperless-ngx** - Document management system with OCR
  - PostgreSQL 15 database for metadata
  - Redis broker for async tasks
  - OCR support for English and Portuguese languages
  - Accessible at <https://docs.homelab.example.com> (Tailscale only)
  - Consume directory for automatic document import: `appdata/paperless/consume`
  - Resource limits: Paperless (2G RAM max, 1.5 CPU max), DB (512M RAM max, 0.5 CPU max), Redis (128M RAM max, 0.25 CPU max)
  - Total additional resources: ~2.5GB RAM, ~2 CPU cores
  - Client upload size limit: 100M (for large document files)

### Changed

- **Homepage Dashboard**: Reorganized with new sections
  - Added "Security & Identity" section with Authentik
  - Added "Document Management" section with Paperless-ngx
  - Added "Storage" section with Nextcloud (moved from Management Tools)

- **Docker Compose**: Added 7 new services (authentik-db, authentik-redis, authentik-server, authentik-worker, paperless-db, paperless-redis, paperless-ngx)

- **Nginx Proxy**: Added reverse proxy configurations for Authentik and Paperless with Tailscale-only IP restrictions

- **Environment Variables**: Added configuration for Authentik and Paperless in `.env` and `.env.example`

### Security

- **Network Segmentation Design**: Infrastructure prepared for 4-tier network isolation (pending maintenance window deployment)
  - Frontend network for user-facing services
  - Backend network for processing services (internal-only)
  - Monitoring network for observability stack
  - Database network for data services (internal-only)

### Manual Actions Required

**CRITICAL - Complete these steps before deploying:**

1. **Create Required Directories**:

   ```bash
   cd /home/luk-server/homelab
   sudo mkdir -p appdata/authentik/{db,redis,media,certs,custom-templates}
   sudo mkdir -p appdata/paperless/{db,redis,data,media,export,consume}
   sudo chown -R $USER:$USER appdata/authentik appdata/paperless
   ```

2. **Deploy Services**:

   ```bash
   # Deploy Authentik
   docker compose up -d authentik-db authentik-redis authentik-server authentik-worker

   # Deploy Paperless
   docker compose up -d paperless-db paperless-redis paperless-ngx
   ```

3. **Test Nginx Configuration**:

   ```bash
   docker exec nginx-proxy nginx -t
   docker compose restart nginx
   ```

4. **Configure Authentik SSO** (see `docs/authentik-sso-setup.md`):
   - Access <https://auth.homelab.example.com>
   - Create admin account
   - Create OAuth2 providers for Grafana, Portainer, n8n
   - Update service configurations with OAuth credentials

5. **Apply Network Segmentation** (see `docs/network-migration-guide.md`):
   - Schedule maintenance window (30-60 minutes)
   - Follow step-by-step migration guide
   - Validate service connectivity
   - **OPTIONAL**: Can be deferred to future maintenance window

### Notes

- **Total New Resources**: ~4GB RAM, ~3.5 CPU cores across 7 new containers
- **Network Segmentation**: Documented but not yet applied (requires downtime)
- **Authentik Configuration**: Requires manual OAuth setup after initial deployment
- **Paperless Default Credentials**: admin / see `PAPERLESS_ADMIN_PASSWORD` in `.env`

## [Unreleased - Previous Features]

### Added

- **Alertmanager** - Alert routing and notification management
  - Accessible at <https://alertmanager.homelab.example.com> (Tailscale only)
  - Integrated with Prometheus for alert management
  - Configured for Discord/Email/Slack webhook notifications (webhook URL must be configured in .env)
  - Alert grouping by severity (critical/warning) with smart repeat intervals
  - Inhibition rules to prevent alert flooding
  - Resource limits: 256M RAM max, 0.25 CPU max

- **Blackbox Exporter** - HTTP/TCP endpoint monitoring
  - Probes service availability and response times
  - Configured for HTTP 2xx status checks, POST requests, and TCP connectivity
  - Integrated with Prometheus for endpoint monitoring
  - Resource limits: 128M RAM max, 0.1 CPU max

- **Nextcloud** - Self-hosted cloud storage and productivity platform
  - Accessible at <https://cloud.homelab.example.com> (Tailscale only)
  - Integrated with MariaDB for database and Redis for caching
  - Configured with trusted domains and proxy settings
  - Resource limits: Nextcloud (1G RAM max, 1.0 CPU max), MariaDB (512M RAM max, 0.5 CPU max), Redis (128M RAM max, 0.25 CPU max)

### Fixed

- **Vaultwarden Health Check**: Changed from `wget` to `curl` for health check compatibility
- **Promtail**: Recreated container to clear unhealthy status (no health endpoint by design)
- **Container Cleanup**: Removed old Discord bot containers (discord-bot, discord-bot-postgres, discord-bot-redis)
- **Nextcloud SSL**: Updated nginx configuration to use correct SSL certificate paths (`/etc/nginx/ssl/`)

### Changed

- **Prometheus Configuration**: Enhanced with Alertmanager integration and new scrape targets
  - Added alerting configuration pointing to Alertmanager (alertmanager:9093)
  - Added Alertmanager metrics scraping (15s interval)
  - Added Blackbox Exporter scraping (30s interval)
  - Prepared for Nginx Exporter integration (commented out, pending deployment)

- **Promtail Log Processing**: Significantly enhanced log parsing capabilities
  - Added log level extraction (ERROR, WARN, INFO, DEBUG)
  - Added HTTP status code detection and labeling
  - Added structured labels for better filtering (container_name, log_level, status_code)
  - Added multiline log support for stack traces and exceptions
  - Added timestamp parsing from logs
  - Added JSON log parsing for Docker container logs

- **Homepage Dashboard**: Updated monitoring section to include Alertmanager

- **Security Updates**: Updated Python dependencies to fix vulnerabilities
  - requests: 2.31.0 → 2.32.3 (fixes CVE-2024-35195)
  - typer: 0.9.0 → 0.12.5
  - rich: 13.7.0 → 13.8.1
  - docker: 7.0.0 → 7.1.0
  - pytest: 7.4.3 → 8.3.3
  - Other development dependencies updated to latest stable versions

- **Certbot SSL**: Documented incompatibility with Tailscale-only DNS setup
  - Certbot requires public DNS resolution for HTTP-01 challenge
  - Domain `homelab.example.com` is intentionally private (Tailscale-only)
  - Current setup uses existing wildcard SSL certificates
  - Future: Configure DNS-01 challenge with DNS provider API integration

## [2.2.0] - 2025-11-02

### 🚀 Major Expansion: New Services and Infrastructure Improvements

#### Added

- **Vaultwarden** - Self-hosted password manager (Bitwarden-compatible)
  - Accessible at <https://vault.homelab.example.com> (Tailscale only)
  - Admin panel with token authentication
  - WebSocket support for real-time notifications
  - Resource limits: 256M RAM max, 0.25 CPU max

- **Jellyfin** - Media server for streaming content
  - Accessible at <https://jellyfin.homelab.example.com> (Tailscale only)
  - Read-only media directory mounting
  - WebSocket support for live interface updates
  - Optimized proxy settings for streaming (no buffering, 300s timeouts)
  - Resource limits: 2G RAM max, 1.0 CPU max

- **n8n** - Workflow automation platform (configuration ready)
  - Accessible at <https://n8n.homelab.example.com> (Tailscale only)
  - Basic authentication enabled
  - WebSocket support for real-time workflow updates
  - Resource limits: 512M RAM max, 0.5 CPU max
  - Deployment pending Docker Hub rate limit reset

#### Fixed

- **SSL Certificate Renewal** - Added Let's Encrypt ACME challenge exception to nginx IP restrictions
- **Prometheus Monitoring** - Removed FileBrowser from scrape targets (no metrics endpoint)
- **Container Updates** - Updated all 11 existing containers to latest versions
- **Security** - Enhanced nginx IP restrictions to allow only Tailscale network and localhost access

#### Manual Tasks Required

- **Home Assistant**: Xiaomi OAuth integration requires token refresh via UI (Settings > Devices & Services)
- **Uptime Kuma**: Monitor timeout adjustments needed via UI for Home Page monitor (increase to 120s)

### Infrastructure Notes

- All new services bound exclusively to Tailscale IP for secure access
- Nginx reverse proxy configured for all new subdomains with SSL support
- Health checks and resource limits applied to all new services
- Comprehensive logging configured for all services

## [2.1.0] - 2025-01-09

### 🔧 Bug Fixes and Improvements

#### Removed

- **DuckDNS Integration**: Completely removed DuckDNS cron job and dependencies
- **Legacy Scripts**: Removed DuckDNS update script and log files
- **Environment Variables**: Cleaned up DuckDNS token from system environment
- **Cron Jobs**: Streamlined crontab to only include homelab automation tasks

#### Fixed

- **Security Issue**: Replaced `os.system()` with `subprocess.run()` for better security
- **Test Issues**: Fixed hardcoded paths in test classes to use test directories
- **Type Annotations**: Added missing type annotations for better type checking
- **Test Mocking**: Improved test fixtures and mocking for more reliable tests

#### Added

- **Development Documentation**: Comprehensive development guide with best practices
- **Fixed Test Files**: Separate test files with proper test directory handling
- **Security Improvements**: Better subprocess handling and input validation

#### Changed

- **Test Architecture**: Tests now properly use temporary directories
- **Security Scanning**: Enhanced security checks with better subprocess handling
- **Development Workflow**: Improved development commands and documentation

## [2.0.0] - 2025-01-09

### 🎉 Major Release: Python-Based Automation System

#### Added

- **Python Automation System** - Complete rewrite in Python for better maintainability
- **Rich CLI Interface** - Beautiful, colored command-line interface
- **Comprehensive Health Monitoring** - Service health checks with system resource monitoring
- **Advanced Update Management** - Automated update checking and deployment
- **Configuration Validation** - Environment variable validation with security checks
- **Automated Backup System** - Docker volume backups with retention policies
- **Cron Integration** - Automated task scheduling for maintenance
- **Service Version Tracking** - Current version monitoring for all services

#### Changed

- **Converted from Shell to Python** - All automation scripts now use Python
- **Simplified Architecture** - Removed overkill components (Terraform, Ansible, complex monitoring)
- **Enhanced Error Handling** - Comprehensive exception handling and user feedback
- **Improved Logging** - Structured logging with file and console output
- **Better Documentation** - Comprehensive README with examples and architecture

#### Removed

- **Terraform Infrastructure** - Too complex for homelab use case
- **Ansible Playbooks** - Overkill for single-server deployment
- **Complex Monitoring Stack** - ELK stack, Alertmanager, complex Prometheus alerts
- **GitHub Actions CI/CD** - Not needed for personal homelab
- **Shell Scripts** - Converted to Python equivalents
- **DevOps Analysis Documentation** - Analysis complete, no longer needed

#### Fixed

- **Environment Variable Loading** - Safer parsing with special character support
- **Docker Container Management** - Better error handling and status reporting
- **Backup System** - Improved reliability and error handling
- **Service Health Checks** - More robust HTTP endpoint checking

#### Security

- **Environment Variable Validation** - Comprehensive validation with security checks
- **Secure Configuration Templates** - `.env.example` with placeholder values
- **Improved Secret Management** - All sensitive data in environment variables
- **Docker Security** - Non-root execution and network isolation
- **Zero Hardcoded Secrets** - All sensitive data properly externalized
- **Password Strength Validation** - Automatic password complexity checks
- **Token Format Validation** - Ensures proper API token formats
- **Secure Subprocess Handling** - Uses `subprocess.run()` instead of `os.system()`

## [1.0.0] - 2025-01-09

### 🏠 Initial Release: Home Assistant Dashboard Setup

#### Added

- **Home Assistant Dashboard** - Custom dashboard with HACS components
- **HACS Integration** - Home Assistant Community Store setup
- **Mushroom Cards** - Modern card collection for Lovelace
- **Button Card** - Highly customizable button card
- **Mini Graph Card** - Minimalistic graph card for sensor data
- **UI Lovelace Minimalist** - Clean theme and card collection
- **Docker Compose Setup** - Container orchestration for homelab services
- **Environment Configuration** - Secure environment variable management
- **Basic Automation** - Shell scripts for container management

#### Services

- **Home Assistant** - Home automation hub
- **Grafana** - Monitoring and dashboards
- **Portainer** - Container management
- **Pi-hole** - Network-wide ad blocking
- **Uptime Kuma** - Uptime monitoring
- **Prometheus** - Metrics collection
- **What's Up Docker** - Container update monitoring

#### Features

- **Dashboard Configuration** - YAML-based dashboard setup
- **Theme Integration** - Brazilian theme for Home Assistant
- **Service Health Monitoring** - Basic health checks
- **Backup System** - Manual backup functionality
- **Update Management** - Container update checking

---

## Version History

- **v2.0.0** - Python-based automation system with comprehensive features
- **v1.0.0** - Initial Home Assistant dashboard setup with basic automation

## Migration Guide

### From v1.0.0 to v2.0.0

1. **Environment Variables** - No changes needed, all existing variables are compatible
2. **Docker Compose** - No changes needed, same configuration
3. **Application Data** - No changes needed, all data preserved
4. **New Commands** - Use `./homelab` instead of individual scripts
5. **Python Dependencies** - Run `pip install -r scripts/requirements.txt` in virtual environment

### Breaking Changes

- **Shell Scripts Removed** - All shell automation scripts converted to Python
- **Terraform/Ansible Removed** - Infrastructure as Code components removed
- **Complex Monitoring Removed** - ELK stack and complex monitoring removed

### New Features

- **Rich CLI** - Beautiful command-line interface
- **Automated Tasks** - Cron job integration
- **Configuration Validation** - Environment variable validation
- **Service Version Tracking** - Current version monitoring
- **Enhanced Health Monitoring** - Comprehensive service health checks

## Future Roadmap

### Planned Features

- **Web Dashboard** - Web-based management interface
- **Mobile App** - Mobile management application
- **Advanced Monitoring** - Custom Grafana dashboards
- **Backup Encryption** - Encrypted backup storage
- **Service Dependencies** - Dependency-aware updates
- **Health Alerts** - Email/Discord notifications
- **Performance Metrics** - Detailed performance monitoring

### Potential Improvements

- **Kubernetes Support** - Optional Kubernetes deployment
- **Multi-Node Support** - Distributed homelab setup
- **Advanced Security** - Security scanning and hardening
- **Backup Verification** - Automated backup testing
- **Service Discovery** - Automatic service detection
- **Plugin System** - Extensible automation system

---

*This changelog follows [Keep a Changelog](https://keepachangelog.com/) format and [Semantic Versioning](https://semver.org/) principles.*

## [2.3.0] - Infrastructure Cleanup and Security Hardening

### Removed

- **nginx-proxy-manager** - Redundant reverse proxy service (consumed resources, exposed public ports)
- **certbot** service - Incompatible with Tailscale-only DNS setup
- **28 dangling Docker volumes** - Reclaimed ~2GB disk space
- **Orphaned containers** - Removed 2 github-mcp-server containers
- **Lukbot resources** - Removed old Discord bot volumes (postgres_data, redis_data) and network

### Added

- **Network Segmentation** - Advanced Docker network architecture:
  - `frontend` (172.20.0.0/24) - User-facing services
  - `backend` (172.21.0.0/24, internal) - Processing services with no internet access
  - `monitoring` (172.22.0.0/24) - Observability stack
  - `database` (172.23.0.0/24, internal) - Database services with no internet access

### Security

- **Sentry Token** - Moved hardcoded token from Grafana datasources to environment variable
- **What's Up Docker Authentication** - Added HTTP Basic Auth (requires htpasswd setup)
  - Manual setup required: `sudo htpasswd -c config/nginx/auth/wud.htpasswd admin`
  - Critical: WUD has Docker socket access and can trigger container updates

### Changed

- Cleaned up 4 duplicate volumes (portainer_data, prometheus_data, uptime_kuma_data, whats_up_docker_data)
- Removed unused Docker networks

### Manual Actions Required

1. Generate WUD htpasswd file: `cd /home/luk-server/homelab && sudo htpasswd -c config/nginx/auth/wud.htpasswd admin`
2. Reload Nginx after htpasswd creation: `docker compose restart nginx-proxy`
3. Service network assignments pending (to be applied in next maintenance window)

### Notes

- Backup created: `backups/homelab_pre-cleanup_TIMESTAMP.tar.gz`
- Docker cleanup savings: ~2GB disk space, reduced from 50 to 14 volumes
- Network segmentation defined but service assignments deferred to prevent disruption

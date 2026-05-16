# 0013 — Auto-deploy pipeline: host-side systemd timer + git poll on tag

- **Status:** Accepted
- **Date:** 2026-05-16
- **Deciders:** Lucas Santana
- **Related:** ADR-0010 (homelab-manager baked image — defines what is built;
  this ADR defines when/where that build runs at deploy time), ADR-0004
  (drop k3s — single-host operating posture), ADR-0008 (image pinning).

## Context

Deploys today are manual: SSH to the homelab host, `git pull`, `docker compose
up -d --build`. With the release-branch cadence now in steady state (v2.4.2,
v2.4.3, v2.4.4 all shipped in 24 h), the per-release SSH step is friction that
will only grow.

The repo uses the release-branch model: `/release-cut` produces a tagged
release on `main` (e.g. `v2.4.4`). **Tag push is the natural deploy trigger.**

A plan exists at `.claude/plans/auto-deploy-pipeline-2026-05-14.md` (Draft,
Phase 0 not started). This ADR formalises the Phase 0 decision and unblocks
Phases 1–6.

Constraints:
- Single-host Docker homelab.
- Tailscale-only inbound (no public ingress; GitHub cannot reach the host).
- Sole operator (Lucas); private repo; no external contributors.
- ADR-0010 just decided homelab-manager builds locally via Dockerfile.
- No customer-facing SLA; releases are operator-paced.

## Decision

**Adopt Option B — host-side systemd timer + git poll on tag.**

- `homelab-deploy.timer` fires every 60 s, runs `homelab-deploy.sh`.
- Script: `git fetch --tags --prune`, resolve highest `v[0-9]*.[0-9]*.[0-9]*`
  tag, compare to `/var/lib/homelab/deployed-tag`, exit clean if equal.
- On new tag: snapshot digests → `git switch --detach <tag>` →
  `docker compose pull && docker compose up -d --build --remove-orphans` →
  verify (Gatus + `docker compose ps`) → on success write new state file +
  Discord notify; on fail roll back to snapshotted digests + Discord notify.
- Lock via `flock /var/lock/homelab-deploy.lock` to prevent concurrent runs.
- `set -euo pipefail`; allow override via `HOMELAB_DEPLOY_FORCE_TAG=v2.4.4`
  for manual reruns or rollback drills.

**Build location:** host builds the homelab-manager image at deploy time via
the `--build` flag. (Not pushed to GHCR.) Per ADR-0010 the build is 11 s on
the host; the GHCR push variant was evaluated and rejected — see alternatives.

## Alternatives considered

| Option | Rejection reason |
|---|---|
| **A. GitHub Actions self-hosted runner on the host.** Workflow on tag push, runner runs `make deploy`. | Persistent agent with `docker.sock` access. Sysdig (2026) documented active in-the-wild abuse of self-hosted runners as persistent C2 backdoors masked as systemd services. Risk constrained for a private repo / single-operator / Tailscale-only host, but B's "no persistent agent, pull-based, no inbound surface" posture is architecturally the safer default and there is no offsetting benefit for a 60 s latency tolerance. |
| **B-hybrid. B's trigger + GH Actions builds homelab-manager and pushes to GHCR; host pulls images only (no `--build`).** | Critic argued for consistency with the rest of the stack (every other service uses pinned upstream images). Counter: ADR-0010 just decided local-build with full knowledge of this tradeoff — 11 s build on the host, 159 MB image, no GHCR credentials to manage, no upstream registry to depend on at deploy time. Adopting B-hybrid would also add 1–2 min to every `/release-cut` for the build + push step. Re-evaluate when build time > 2 min or when a second host is added (then the GHCR-pull pattern saves N×11 s every deploy). |
| **C. Watchtower.** Auto-update containers when registry images change. | Upstream project was discontinued in 2026. Even before that, it didn't fit because Watchtower watches registries — homelab-manager isn't in a registry. |
| **D. Komodo orchestration UI.** Web app for deploys + monitoring across hosts. | Adds a long-running web UI (inbound surface), a Periphery agent on the host, and operator-time to learn the UI. Designed for multi-host fleets; a single-host homelab pays the complexity cost without using the multi-host features. Revisit if a second host is added. |
| **E. Podman Quadlet AutoUpdate.** 2026 default per upstream community; declarative `.container` files with `AutoUpdate=registry`. | Requires migrating the entire stack off Docker to Podman. Cost vastly exceeds the deploy-friction problem this ADR solves. Not in scope. |
| **F. GitHub webhook → host-side receiver.** Sub-variant of A without a full runner. | Homelab is Tailscale-only inbound; GitHub can't reach the host without exposing a public endpoint, which contradicts the network model. Would require Cloudflare Tunnel or similar to make work, paying complexity for sub-second latency that no SLA requires. |
| **G. Manual deploy only — document the steps.** | Already the status quo. Doesn't solve the growing friction across release cycles. |

## Consequences

**Positive:**

- No inbound surface; the host pulls only. Survives a GitHub outage (the host
  just keeps running the last-deployed tag until the next poll succeeds).
- Reuses an existing pattern (`homelab-update.timer` already on the host).
  Operator already understands systemd timers.
- Zero idle resource use — timer ticks every 60 s, the script exits fast when
  the tag is unchanged.
- Failure mode is local: stuck deploy means the host shows a stale tag in the
  audit log; operator fixes it on the host without round-tripping GitHub
  Actions UI.
- Pairs cleanly with the rollback path the plan already specifies (Phase 5):
  snapshot digests on entry, restore on verify-failure.

**Negative:**

- Up to 60 s latency between tag push and deploy start. Acceptable for a
  homelab without an SLA.
- Tag-detection logic lives on the host. Two tags landing in the same 60 s
  window: the script picks the highest (sort -V), so the older is skipped.
  Acceptable for the operator-paced cadence.
- Build happens on the host every deploy. 11 s today; could grow if the
  Dockerfile gains complexity. Captured as a revisit trigger.
- The `flock`, GitHub API rate-limit backoff, disk-full guard, and stale
  state-file checksum that the critic identified must be in Phase 1's script
  — *not* deferred. The plan was light on these; flagging here so they don't
  drop on the floor.

**Neutral:**

- Discord notification reuses the existing `LUCKY_NOTIFY_URL` pattern; no new
  secret to manage.
- `homelab-update.timer` (the older image-pull-on-clock timer) stays in
  place as a safety net for any remaining floating tags; can retire it after
  one full release cycle on auto-deploy.

## Implementation

The 2026-05-14 plan stands as the implementation playbook
(`.claude/plans/auto-deploy-pipeline-2026-05-14.md`). Updated requirements
based on this ADR + critic feedback:

1. **Phase 1 script** must include: `flock`, GitHub API rate-limit backoff
   (skip the tick if `git fetch` fails with `403`/`429`), `df -h` guard
   pre-pull (abort + Discord notify if free space < 5 GB), state-file
   checksum validation before applying rollback digests, and `set -euo
   pipefail` + `-o errtrace`.
2. **Compose invocation** is `docker compose up -d --build --remove-orphans`
   (the `--build` flag is the new contract per ADR-0010).
3. **Phase 4 GH-side workflow** is announce + audit-trail only; never
   triggers the deploy itself.
4. **Phase 5 rollback rehearsal** must pass before Phase 6 cut-over; do not
   enable the timer permanently until rollback is verified end-to-end on a
   live (but harmless) tag.

## Revisit triggers

Re-open ADR-0013 if any of the following becomes true:

1. **Build time on host exceeds 2 minutes.** Local-build becomes the deploy
   bottleneck; B-hybrid (GH Actions build + GHCR push) gets cheaper than
   carrying the build on every deploy. Revisit Option B-hybrid.
2. **A second host is added.** N×11 s per deploy across hosts justifies
   building once in CI and pulling everywhere. Revisit B-hybrid.
3. **Deploys exceed 5 per day.** 60 s latency starts to compound; revisit
   Option A (GH Actions runner) with the security guidance from Sysdig
   (ephemeral runners, jobs in containers, rootless docker).
4. **Homelab gains a public ingress** for any service. The network-model
   constraint that makes B's "no inbound surface" load-bearing falls away;
   webhook-based variants (F) become viable.
5. **Customer-facing SLA appears.** Sub-60 s deploy + auto-rollback with
   independent observability stops being optional. Revisit A or B-hybrid.
6. **Phase 5 rollback rehearsal fails twice.** Don't enable; reconsider the
   trigger-and-rollback design before retrying.

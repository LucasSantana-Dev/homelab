# ADR 0037: Agent-Box Resilient Boot + Deploy/Secret Runbook

- **Status:** Accepted
- **Date:** 2026-07-02
- **Deciders:** Lucas (solo operator)
- **Supersedes:** —
- **Superseded by:** —
- **Related:** [ADR-0036](./0036-host-config-management.md) (host config git-first flow), [ADR-0022](./0022-release-branch-model.md) (release-branch model), [ADR-0018](./0018-healthcheck-probes-must-use-tools-the-image-ships.md) (distroless probe constraint), [ADR-0015](./0015-hotfix-lane-reserved-for-active-incidents.md) (hotfix lane)

---

## Context

On 2026-07-02, `agent-box` (the autonomous-agent container) was found **crash-looping** — `Restarting (128)`, `RestartCount` ~1388, ~2 s per boot, offline for hours.

**Root cause (two layers):**

1. **Credential:** `AGENT_GITHUB_TOKEN` (the fine-grained PAT stored in `secrets/agent-box.secrets.yaml.age`) had lost access to the private `claude-env` repo. `gh auth` still succeeded (token valid), but `git clone https://x-access-token:$AGENT_GITHUB_TOKEN@github.com/LucasSantana-Dev/claude-env.git` returned **HTTP 403 "Write access to repository not granted"** — the classic signature of a fine-grained PAT whose repo list no longer covers a repo.
2. **Fragility:** `config/agent-box/entrypoint.sh` cloned `claude-env` (and the working repos via `clone_repo`) under `set -euo pipefail` with **no fallback**. A single repo's 403 exited the entrypoint (code 128) → Docker's restart policy relaunched it → infinite loop. One repo's access failure took the whole container down.

The incident surfaced while trying to smoke-test an unrelated PR (#348). The token rotation resolved the outage; the fragility fix prevents recurrence.

## Decision

**1. Repo clones in the agent-box entrypoint are non-fatal.** (Shipped in PR #354.) The `claude-env` clone and every `clone_repo` invocation now log a WARNING and continue on failure instead of aborting boot. The container comes up **functional with whatever repos it could reach**; a missing/inaccessible repo degrades one capability rather than downing the agent.

```bash
su -c "git clone …/claude-env.git $CLAUDE_ENV_DIR 2>&1" agent \
    || log "WARN: claude-env clone failed (token access or network) — continuing without it"
```

**2. This ADR is the durable runbook** for agent-box boot, secret rotation, and deploy — the operational knowledge that cost hours to re-derive during the incident.

## Consequences / Runbook

### Delivery model (know before you touch it)

- **`entrypoint.sh` is BAKED into `agent-box:latest`** (locally built via `compose/agent-box.yml` `build:`), **not** bind-mounted. An entrypoint change requires an **image rebuild** (`docker compose build`), not a restart.
- **Secrets ARE bind-mounted** (`../secrets/agent-box.secrets.yaml.age:/run/secrets/...:ro`, decrypted at entrypoint runtime). A **token/secret change only needs a restart** — no rebuild.
- **Repo clones are guarded by `[[ ! -d .git ]]`** — already-cloned repos on the persistent `agent_workspace` / `agent_claude_state` volumes are skipped. A fresh volume forces re-clone of all repos, which is when a missing-repo PAT gap bites.

### Secret rotation (SOPS) — exact procedure

The secret file has **no `.sops.yaml` creation rule** (`.sops.yaml` only matches `.env.enc`, `config/**.enc.yaml`, `docker-compose.*.enc.yml` — **not** `secrets/*.yaml.age`). Consequences:

- `sops set` / `sops --set` fail with **`error loading config: no matching creation rules found`** on write.
- The `.age` extension also breaks input-type detection → **`Error unmarshalling input json`** unless you pass `--input-type yaml`.

**Working rotation** (run on the deploy host, where the age key lives at `~/.config/sops/age/keys.txt`):

```bash
cd ~/homelab
export SOPS_AGE_KEY_FILE=$HOME/.config/sops/age/keys.txt
RECIP=age19pjf4fw094vcsmrwr8usm3gvqmlvz8elt23zk52ltaavv03y7s8qgg906q   # from .sops.yaml / file metadata
trap 'shred -u /tmp/.sec.yaml 2>/dev/null; rm -f /tmp/.sec.enc' EXIT   # never leave plaintext
sops --config /dev/null --input-type yaml --output-type yaml -d secrets/agent-box.secrets.yaml.age > /tmp/.sec.yaml
sed -i "s|^AGENT_GITHUB_TOKEN:.*|AGENT_GITHUB_TOKEN: <newtoken>|" /tmp/.sec.yaml
sops --config /dev/null --input-type yaml --output-type yaml --age "$RECIP" -e /tmp/.sec.yaml > /tmp/.sec.enc
mv /tmp/.sec.enc secrets/agent-box.secrets.yaml.age
docker restart agent-box   # bind-mounted secret re-decrypts on boot; no rebuild needed
```

- **`--config /dev/null` + explicit `--age $RECIP`** are both required (bypass the missing creation rule).
- The file is **git-ignored** — the rotation is host-local, no commit.
- **Verify without echoing the value:** compare the SHA256 of the decrypted `AGENT_GITHUB_TOKEN` to the SHA256 of the new token; check `docker logs agent-box` for `Secrets loaded.` and `gh auth status`.

### PAT scope

`AGENT_GITHUB_TOKEN` must grant access to **all** repos the entrypoint clones: `claude-env`, `Lucky`, `homelab`, `Craftvaria`. A fine-grained PAT missing any of them 403s (or 404s) that clone. With the non-fatal fix this now degrades gracefully instead of crash-looping, but the affected repo will be absent from the workspace.

### Deploy / recreate — compose project name

`agent-box` runs under compose project **`homelab`** (network `homelab_agent`). Running `docker compose -f compose/agent-box.yml up -d` from `~/homelab` **without `-p`** defaults the project to `compose` → tries to create `compose_agent` → **`failed to create network compose_agent: Pool overlaps`**, and does **not** touch the real container. Always:

```bash
docker compose -p homelab -f compose/agent-box.yml build
docker compose -p homelab -f compose/agent-box.yml up -d
```

`make deploy` sets the project correctly; ad-hoc single-file compose commands must pass `-p homelab`.

### Rollback

Before a risky agent-box rebuild, tag the current image: `docker tag "$(docker inspect agent-box --format '{{.Image}}')" agent-box:rollback`. On a bad boot, `docker tag agent-box:rollback agent-box:latest && docker compose -p homelab -f compose/agent-box.yml up -d`.

## Revisit when

- The agent-box PAT is migrated to a GitHub App / deploy keys (removes the fine-grained-PAT-scope footgun).
- `secrets/*.yaml.age` gains a `.sops.yaml` creation rule (then `sops set` works and this runbook's `--config /dev/null` dance is unnecessary).
- agent-box moves to a pull-based image (registry) instead of local build (changes the entrypoint-baked delivery model).

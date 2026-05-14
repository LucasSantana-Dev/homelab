# Deployment Prerequisites

One-time host-side steps that must be done before (or right after) certain
PRs land. Each entry is keyed to the PR that introduced the requirement so
a server operator can audit `git log --oneline` against this list.

## n8n bind-mount ownership (since PR #81)

**Symptom if skipped:** n8n container starts, then crash-loops immediately
with `EACCES: permission denied, open '/home/node/.n8n/config'` or similar
permission errors. `docker logs n8n` shows the failure.

**Why:** PR #81 dropped n8n from `user: "root"` to `user: "1000:1000"` as
part of audit-deep H2 container hardening. The bind-mount `../appdata/n8n`
was previously written as root, so a UID 1000 process cannot read or write
it until ownership is corrected.

**Fix (one-time, on the homelab host):**

```bash
sudo chown -R 1000:1000 /path/to/homelab/appdata/n8n
docker compose -f compose/apps.yml up -d --force-recreate n8n
docker logs --tail 50 n8n   # verify clean start
```

The 1000:1000 pair matches the `node` user inside the official `n8nio/n8n`
image and the `PUID=1000 / PGID=1000` env vars already set in
`compose/apps.yml`.

## Cloudflare tunnel UUID rotation (audit-deep v2 C1, in flight)

**Symptom if skipped:** `config/cloudflared/config.yml` still contains the
plaintext UUID exposed in the public repo. Anyone with repo access can
correlate it with a leaked credentials.json.

**Fix (one-time, in Cloudflare dashboard + server):**

1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → delete the old
   tunnel, create a new one.
2. Copy the new credentials.json to `~/homelab/config/cloudflared/credentials.json`
   (server-side, NOT tracked in repo).
3. Add `CF_TUNNEL_ID=<new-uuid>` to `~/homelab/.env`.
4. Update `config/cloudflared/config.yml` in the repo to reference
   `${CF_TUNNEL_ID}` instead of the hardcoded UUID.
5. `docker compose restart cloudflared`.

## Homepage server-side version (in flight)

**Symptom if skipped:** Homepage server is still on v0.10.9 while
`compose/core.yml` declares v1.0.3. Blocks the Phase 2 widget integration
PR because v1.x has a different widget schema.

**Fix:** `docker compose pull homepage && docker compose up -d homepage`
on the server. Verify with `docker exec homepage cat /app/package.json`.

## When to update this doc

Add an entry when a PR introduces a host-side step that fresh-deploy
documentation alone won't cover. Reference the PR number so the operator
can audit `git log` against this list.

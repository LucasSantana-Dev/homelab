# 0010 — homelab-manager packaging: local Dockerfile build over runtime pip-install

- **Status:** Accepted
- **Date:** 2026-05-16
- **Deciders:** Lucas Santana
- **Related:** ADR-0009 (homelab-manager loopback binding), PRs #120, #121, #141, #143

## Context

The `homelab-manager` container (introduced in v2.4.0 via PR #120) currently runs from `python:3.11-slim` with the source mounted read-only and pip installed at container startup. The entrypoint sequence is:

```
sh -c "mkdir -p /tmp/build && cp /app/pyproject.toml /app/README.md /tmp/build/ \
  && cp -r /app/homelab_manager /tmp/build/ \
  && cd /tmp/build \
  && pip install --target /tmp/site-packages . --quiet \
  && PYTHONPATH=/tmp/site-packages python -m homelab_manager serve --host 0.0.0.0 --port 8765"
```

Two release-impacting bugs in 24 hours pointed at this packaging strategy:

1. **PR #141 (in v2.4.2):** `cp -r /app /tmp/build` copied the entire `../:/app:ro` bind mount, which on the live server is **22 GB** because it includes `appdata/` (Nextcloud, Paperless, etc). Container hung indefinitely. Caught post-deploy.
2. **PR #143 (in flight for v2.4.3):** The selective-copy fix above. But the underlying pattern — pip-installing at startup from a read-only source mount — is fragile to several other failure modes (egg-info perm, build cache invalidation, slow startup, no version pin).

The runtime pip-install pattern was originally chosen to avoid managing a separate image build pipeline. With two failures in 24 hours, that trade-off needs to be revisited.

## Decision

**Switch homelab-manager to a baked image built locally via compose `build:` directive.**

```yaml
homelab-manager:
  build:
    context: ..
    dockerfile: dockerfiles/homelab-manager/Dockerfile
  image: homelab-manager:local
  # remove: ../:/app:ro mount, runtime cp+pip command
```

Dockerfile copies only the package source (`pyproject.toml`, `README.md`, `homelab_manager/`) and runs `pip install --no-cache-dir .` at build time. Container starts in <10s instead of 60-90s. The `../:/app:ro` mount is removed entirely.

## Alternatives Considered

| Option | Rejected because |
|---|---|
| **A — Status quo** (runtime pip-install with selective cp from #143) | Pattern has shipped 2 bugs in 24h; fragile to mount/perm/size changes; 60-90s startup; no version pin |
| **B2 — GHCR-hosted image with CI/CD** | Homelab has no CI/CD that builds and publishes images; would require new infra; single-host deployment doesn't justify it |
| **C — Narrow the bind mount** to just `homelab_manager/` + `pyproject.toml` | Solves the 22GB problem but keeps the egg-info perm class of bugs and slow startup. Half-measure. |
| **D — Sidecar wheel-build container** | Adds compose complexity; two containers to coordinate; the local-Dockerfile approach achieves the same caching with one container |
| **E — Drop container, run as host systemd service** | Deviates from "everything in compose" pattern; harder to enforce 127.0.0.1 binding consistently; complicates `homelab` CLI which already runs on the host |
| **F — Writable volume over egg-info path** | Mount wizardry; brittle; doesn't fix slow startup; not a serious option |

## Consequences

### Positive

- Startup time drops from ~60-90s to ~5-10s
- Eliminates the entire class of "read-only mount + pip install" bugs (PRs #141, #143)
- Image content is reproducible from a tagged commit (image timestamp = source freshness)
- Source changes require explicit `--build` flag, making "did the new code actually deploy?" verifiable

### Negative

- User must remember `docker compose up -d --build homelab-manager` when changing `homelab_manager/*.py` (mitigation: bake `--build` into `homelab deploy` helper if it exists)
- Adds one Dockerfile to maintain (~15 lines, low churn)
- One-time migration: rebuild image on server during the v2.4.3 deploy

### Neutral

- Image lives as `homelab-manager:local` on the host; not pushed to a registry. Multi-server deployments would need GHCR.

## Revisit when

Re-open this decision if **any** of the following occur:

1. **Multi-server deployment** — if homelab-manager needs to run on more than one host, GHCR-hosted images become worth the CI/CD setup.
2. **Build time exceeds 2 minutes** — currently <30s. If source grows or dependency tree explodes, switch to multistage Dockerfile with wheel cache.
3. **Source >50MB** — currently <1MB. At >50MB, bind-mount-with-runtime-install becomes attractive again for fast dev iteration.
4. **User starts hot-reloading source during dev** — if iterating on `homelab_manager` from a non-server context (e.g., live-coding on the server), an editable mount + runtime pip might be better than rebuilding the image on every change.
5. **Image security scanning surfaces unfixable CVEs in `python:3.11-slim`** — switch to `python:3.12-slim` or distroless variant.

## Implementation reference

Initial PR cuts the Dockerfile + compose change. Server-side migration is a single `docker compose up -d --build homelab-manager`. No data migration; `homelab-manager` is stateless except for `/var/run/docker.sock:ro` access.

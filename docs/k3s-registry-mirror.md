# k3s Registry Mirror (Docker Hub Rate-Limit Mitigation)

## Why

After disk pressure or a node restart, k3s re-pulls every image its
pods need. Anonymous Docker Hub pulls are capped at **100 per 6 hours
per IP**. On a homelab with ~20 k8s pods, one full restart exceeds
the quota and leaves pods stuck in `ImagePullBackOff` until the
window resets.

Symptom observed 2026-04-20 during the disk-pressure incident:
> `Failed to pull image "redis:alpine": pull QPS exceeded`

## Approach

Two cheap fixes, either one is sufficient:

| Option | What | Effort | Capacity |
|---|---|---|---|
| **Mirror** | Reconfigure `local-registry:5000` as a pull-through cache | low | unlimited after first pull per image |
| **Auth** | Add a Docker Hub free-tier account | lowest | 200 pulls / 6h |

The repo template at `config/k3s/registries.yaml.example` supports
both — mirror first, auth fallback.

## Apply (on homelab)

```bash
# 1. Install the k3s containerd registry config
sudo mkdir -p /etc/rancher/k3s
sudo cp config/k3s/registries.yaml.example /etc/rancher/k3s/registries.yaml

# 2. (Optional) fill in Docker Hub credentials in that file if you
#    want the 2x rate-limit bump. Otherwise the `auth` block stays
#    commented out.

# 3. Reconfigure the existing local-registry container as a
#    pull-through cache for docker.io. This is idempotent.
docker stop local-registry && docker rm local-registry
docker run -d --restart=unless-stopped \
  --name local-registry \
  -p 127.0.0.1:5000:5000 \
  -v local-registry-data:/var/lib/registry \
  -e REGISTRY_PROXY_REMOTEURL=https://registry-1.docker.io \
  registry:2

# 4. Restart k3s so containerd picks up the new registries.yaml
sudo systemctl restart k3s

# 5. Verify — the first pull of a new image should hit the mirror:
sudo k3s crictl pull redis:alpine
docker logs local-registry 2>&1 | grep -i "proxy" | tail -5
```

## Verify

```bash
# Subsequent pulls of the same image are served from cache (fast):
time sudo k3s crictl pull redis:alpine   # 2nd run should be ~instant

# Mirror storage growth:
docker exec local-registry du -sh /var/lib/registry
```

## Rollback

```bash
sudo rm /etc/rancher/k3s/registries.yaml
sudo systemctl restart k3s
# Optional: restore plain local-registry (no proxy) per whatever compose
# file originally defined it.
```

## Related

- `config/k3s/registries.yaml.example` — the config file template
- `Makefile` target `k3s-registry-mirror` — runs steps 3-5 above in one shot
- [ADR 0004 — drop k3s](adr/0004-drop-k3s.md) — the long-term plan is
  to remove k3s entirely; until then, this mitigation prevents pull
  failures after the disk-pressure incident of 2026-04-20.

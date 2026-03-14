# Cloudflare Tunnel Phase 1 Host Exposure

This rollout exposes only the selected phase-1 set through `cloudflared`.

## Included Public Hostnames

- `luk-homeserver.com.br`
- `www.luk-homeserver.com.br`
- `homeassistant.luk-homeserver.com.br`
- `grafana.luk-homeserver.com.br`
- `portainer.luk-homeserver.com.br`
- `n8n.luk-homeserver.com.br`
- `cloud.luk-homeserver.com.br`
- `docs.luk-homeserver.com.br`
- `vault.luk-homeserver.com.br`
- `auth.luk-homeserver.com.br`

These are defined in:
- `config/cloudflared/config.yml`

## Explicitly Not Exposed in Phase 1

- `pihole.luk-homeserver.com.br`
- `prometheus.luk-homeserver.com.br`
- `netdata.luk-homeserver.com.br`
- `cadvisor.luk-homeserver.com.br`
- `alertmanager.luk-homeserver.com.br`

## Runtime Validation

```bash
cd /home/luk-server/homelab
docker compose config
make sso-status
make sso-smoke-test
```

## DNS Guardrail

For hostnames exposed through Cloudflare Tunnel, do not publish direct `A` records to your
Tailscale IP. Route those hostnames through Cloudflare/tunnel only, otherwise clients may hit
the origin directly and receive certificate or reachability errors.

## Rollback

```bash
cd /home/luk-server/homelab
docker compose stop cloudflared
docker compose rm -f cloudflared
```

This immediately returns the stack to Tailscale-only ingress behavior.

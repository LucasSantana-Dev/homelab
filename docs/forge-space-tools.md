# Forge Space Tools on Homelab

This homelab uses a lightweight Forge Space-compatible deployment with IBM Context Forge.

## Scope

- Service: `forge-mcp-gateway`
- Compose profile: `forge-space`
- Exposure: `127.0.0.1:${FORGE_MCP_GATEWAY_PORT}` and `${TAILSCALE_IP}:${FORGE_MCP_GATEWAY_PORT}` only
- Admin UI: `http://<tailscale-ip>:4444/admin`

## 1) Configure Environment

Copy `.env.example` to `.env` and set:

- `FORGE_MCP_JWT_SECRET_KEY` (minimum 32 chars)
- `FORGE_MCP_BASIC_AUTH_PASSWORD`
- `FORGE_MCP_ADMIN_PASSWORD`
- optional: `FORGE_MCP_GATEWAY_PORT`, `FORGE_MCP_BASIC_AUTH_USER`, `FORGE_MCP_ADMIN_EMAIL`

## 2) Start Gateway

```bash
make forge-space-up
make forge-space-status
make forge-space-logs
```

## 3) Create Virtual Server and Token

1. Open Forge admin UI (`/admin`) over Tailscale.
2. Create a virtual MCP server.
3. Copy its URL (`/servers/<UUID>/mcp`) and generate a token/JWT.
4. Export:

```bash
export FORGE_MCP_SERVER_URL="http://127.0.0.1:4444/servers/<UUID>/mcp"
export FORGE_MCP_JWT="<jwt>"
```

## 4) Register Codex MCP Bridge

```bash
make forge-space-mcp-setup
codex mcp list
codex mcp get forge-space --json
```

The setup uses a Dockerized stdio bridge:

- image: `ghcr.io/ibm/mcp-context-forge:1.0.0-BETA-2`
- command: `python -m mcpgateway.wrapper --url=... --auth="Bearer ..."`

## 5) Stop / Roll Back

```bash
make forge-space-down
codex mcp remove forge-space
```

## Troubleshooting

- `FORGE_MCP_SERVER_URL still contains <UUID>`: replace with a real virtual server UUID.
- `FORGE_MCP_JWT is empty`: generate token/JWT from Forge admin and export it.
- MCP tools still failing after successful registration: restart the Codex session to refresh MCP transport state.

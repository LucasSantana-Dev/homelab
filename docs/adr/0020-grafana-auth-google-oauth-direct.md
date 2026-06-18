# ADR-0020 — Grafana auth: Google OAuth direct (no OIDC middleware)

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Lucas Santana

---

## Context

Grafana was wired to an Authentik OIDC provider (`/application/o/authorize/`) that was
never deployed. Only Tinyauth (forward-auth, not an OIDC provider) runs at
`auth.${DOMAIN}`. The mismatch locked Grafana out completely when
`GF_AUTH_DISABLE_LOGIN_FORM=true` was set. Emergency fix: OAuth disabled, form
re-enabled (2026-06-17).

The server runs at ~300 MB free RAM. Grafana is already behind Tinyauth Caddy
forward-auth on every public request — the auth layer at the edge is solved.
The question was what to use for Grafana's *own* user management (roles, session
identity).

---

## Decision

**Wire Grafana's `generic_oauth` directly to Google's OIDC endpoints**, reusing the
`GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` already in `.env`.

Implementation:
```yaml
# compose/monitoring.yml — grafana environment
- GF_AUTH_GENERIC_OAUTH_ENABLED=${GRAFANA_OAUTH_ENABLED:-true}
- GF_AUTH_GENERIC_OAUTH_NAME=Google
- GF_AUTH_GENERIC_OAUTH_CLIENT_ID=${GOOGLE_CLIENT_ID}
- GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
- GF_AUTH_GENERIC_OAUTH_SCOPES=openid profile email
- GF_AUTH_GENERIC_OAUTH_AUTH_URL=https://accounts.google.com/o/oauth2/v2/auth
- GF_AUTH_GENERIC_OAUTH_TOKEN_URL=https://oauth2.googleapis.com/token
- GF_AUTH_GENERIC_OAUTH_API_URL=https://openidconnect.googleapis.com/v1/userinfo
- GF_AUTH_GENERIC_OAUTH_USE_PKCE=true
- GF_AUTH_GENERIC_OAUTH_EMAIL_ATTRIBUTE_PATH=email
- GF_AUTH_GENERIC_OAUTH_NAME_ATTRIBUTE_PATH=name
- GF_AUTH_GENERIC_OAUTH_LOGIN_ATTRIBUTE_PATH=email
- GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH=contains(email, '${ADMIN_EMAIL}') && 'Admin' || 'Viewer'
- GF_AUTH_DISABLE_LOGIN_FORM=${GRAFANA_DISABLE_LOGIN_FORM:-false}
```

Google Cloud Console must have `https://grafana.${DOMAIN}/login/generic_oauth`
added to the OAuth 2.0 client's Authorized Redirect URIs.

---

## Alternatives considered

| Option | Rejected because |
|---|---|
| **Deploy Authentik** | ~400–600 MB RAM; server has ~300 MB free; complex schema/migration; overkill for solo-op. |
| **Deploy Authelia** | ~100–150 MB RAM; adds another moving part; no current multi-service OIDC demand to justify it. |
| **Forgejo as OIDC provider** | Forgejo is not deployed on this server. Would tie auth to a Git host, creating a cascade-failure cone if Forgejo restarts. Multi-service OIDC is not on the roadmap. |
| **Keep basic form only** | Leaves no user identity in Grafana sessions; no role mapping; weaker audit trail for a monitoring system. |
| **Cloudflare Access** | Adds CF vendor dependency for internal auth; free tier lacks group-sync; Caddy+Tinyauth already handles edge security. |

---

## Consequences

**Positive:**
- Zero new containers, zero RAM cost.
- Credentials already present in `.env`.
- Form fallback (`GF_AUTH_DISABLE_LOGIN_FORM=false`) ensures Grafana is accessible even if Google is unreachable.
- Standard Grafana `generic_oauth` — well-documented, stable API.

**Negative:**
- Grafana-only scope: doesn't provide OIDC for other services.
- Depends on Google's OAuth service; an external dependency.
- Requires a manual step in Google Cloud Console (add redirect URI) before deploying.

**Neutral:**
- Google credentials are shared with Tinyauth. Rotating them requires updating both services.

---

## Revisit when

- Multi-service OIDC is explicitly roadmapped (e.g., adding OIDC to Prometheus, Loki UI, or custom apps).
- Forgejo is deployed and stabilized; re-evaluate Option B cost/benefit.
- Google API project is migrated or deprecated.
- Server RAM budget grows (e.g., RAM upgrade) — Authelia becomes viable without pressure.

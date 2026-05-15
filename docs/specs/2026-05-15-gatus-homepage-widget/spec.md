# Spec: Gatus Uptime Widget in Homepage Header

**Created:** 2026-05-15  
**Effort:** xs (<1h)  
**Severity:** low  

---

## Goal

Surface the existing Gatus uptime monitor as a Homepage header widget so service status is visible at a glance without navigating to a separate URL.

## Context

- Gatus is running at port 8095 (`compose/monitoring.yml:386-423`), healthcheck on `/api/v1/config`.
- Gatus exposes a REST API at `/api/v1/endpoints/statuses` for programmatic status queries.
- `config/homepage/widgets.yaml` currently has: logo, resources, datetime, search. No Gatus entry.
- Homepage supports a `gatus` widget type natively (as of v0.7+). Current deployment is v1.0.3 — confirmed supported.
- Adding a status overview widget requires no new infra — Gatus is already deployed on the same Docker network.

## Approach

1. Add a `gatus` widget entry to `config/homepage/widgets.yaml`:
   ```yaml
   - gatus:
       url: http://gatus:8095
   ```
2. Ensure the homepage container can reach the gatus container — both are on the `default` network in their respective compose files. Verify with `docker network inspect` or by checking compose network declarations.
3. If cross-stack network access is needed, add a shared `monitoring` network or use `host.docker.internal` as the URL.
4. Test: dashboard header shows Gatus status summary (up/down counts or percentage).

## Verification

- [ ] Homepage header displays the Gatus widget with at least one endpoint status shown
- [ ] Widget correctly reflects up/down state (validate by checking Gatus dashboard directly)
- [ ] No errors in homepage container logs related to Gatus widget fetch
- [ ] Widget loads within the standard Homepage timeout (no hanging requests)

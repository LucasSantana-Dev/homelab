# ADR 0006 — Wake-on-LAN: shell endpoint + Homepage customapi, no GUI container

**Status:** Accepted
**Date:** 2026-05-14
**Owner:** Lucas
**Deciders:** Lucas (operator), critic agent (review)
**Supersedes:** none
**Related:** Plan `homepage-customization-2026-05-13.md` Phase 8

---

## Context

Dashboard Phase 8 requires WoL controls for ~5 LAN machines (Bogan, PVE3, P-NAS, unRAID, Pimox) visible on the Homepage dashboard. Inspiration image showed `gptwol` as a candidate WoL GUI container.

Current state:
- `/usr/bin/wakeonlan` already on the homelab host.
- No WoL container running.
- All services already gated behind Caddy + tinyauth.
- Homepage v1.0.3 is in `compose/core.yml`.
- Wake frequency: rare/ad-hoc, not scheduled.

## Decision

Build a minimal HTTP endpoint that wraps the existing `wakeonlan` CLI, expose it behind the existing Caddy + tinyauth gate, render it on Homepage via the `customapi` widget. **Do not deploy `gptwol` or any other dedicated WoL GUI container.**

## Alternatives considered

| Option | Why rejected |
|---|---|
| `Misterbabou/gptwol` (Python + Docker, built-in auth, cron, ARP scan) | Adds second auth surface alongside tinyauth (ambiguity, audit burden); host-net mode for ARP scan = unnecessary blast radius; cron scheduling solves a problem we don't have. Overkill. |
| `Trugamr/wol` (Go, single binary) | Lightweight but no error reporting — silent WoL failures invisible to Homepage. Removes one feature without removing the container. |
| `szabodanika/wake-pc` (PHP) | Stale, PHP toolchain unwanted here. |
| Skip WoL entirely (keep CLI-only) | Dashboard becomes inconsistent with inspiration screenshot. Cost of the chosen option is ~30 lines of code; skipping saves only that. |

## Consequences

**Positive**
- Zero new auth surface — endpoint sits behind Caddy + tinyauth.
- Single failure mode: `wakeonlan` exit code → HTTP status. Trivial to debug with `curl`.
- ~30 LOC + 1 Homepage group; swap-in cost for Home Assistant later is near-zero (move endpoint logic, not UI).
- No host-net Docker container running indefinitely.

**Negative**
- Loses gptwol features we don't currently want: auto-wake cron, sleep-on-LAN, ARP-based availability check.
- One more bespoke service to maintain (vs picking a maintained upstream).

**Neutral**
- Endpoint will live in `compose/edge.yml` (or new `compose/utility.yml`) as a small FastAPI/Python container OR a systemd-managed Python script — implementation detail decided at build time.

## Revisit triggers

Reopen this decision if any one is true:
1. Wake frequency exceeds **3x/week sustained for 4 weeks** → power-mgmt orchestration justifies Home Assistant (preferred) or gptwol.
2. Machine count passes **10** → centralized GUI with ARP scan becomes useful.
3. We adopt Home Assistant for any other purpose → migrate WoL into HA scenes, retire the endpoint.
4. Caddy + tinyauth gate is removed or downgraded → gptwol's built-in auth becomes a fallback.

## Implementation hand-off

- Add to `homepage-customization-2026-05-13.md` Phase 8 (already in plan).
- New compose service: `wol-api` in `compose/utility.yml` (or scripts/wol-server.py + systemd unit).
- Homepage `services.yaml`: new `Wake-on-LAN` group with one entry per machine using `widget: type: customapi`, `method: POST`, `url: http://wol-api:8000/wake/{name}`.
- MAC addresses + machine names live in `config/homepage/wol-targets.yaml` (gitignored if any IPs are sensitive; otherwise tracked).

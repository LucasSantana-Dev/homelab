# ADR 0003: Ingress Boundary During Phase 1

## Status
Accepted

## Decision
Keep `nginx + cloudflared` on compose as the public edge while k3s workloads are introduced behind it.

## Rationale
- Preserves existing trusted edge controls.
- Minimizes public DNS/tunnel blast radius during learning waves.
- Enables fast fallback to compose services during rollback.

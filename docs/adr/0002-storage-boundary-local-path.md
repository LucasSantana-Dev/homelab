# ADR 0002: Storage Boundary (local-path)

## Status
Accepted

## Decision
Use `local-path` storage class for phase-1 and phase-1.5 pilot workloads.

## Rationale
- Lowest operational complexity on single-node k3s.
- Sufficient for pilot workloads and backup drills.
- Defer distributed storage until phase-2 readiness criteria are met.

# ADR 0001: Compose vs K3s Boundary

## Status
Accepted

## Decision
Use a hybrid model for 90 days: keep critical stateful workloads on compose, migrate low-risk workloads to k3s.

## Rationale
- Current host resources are constrained.
- Existing compose automation is production-proven.
- This approach maximizes learning with controlled risk.

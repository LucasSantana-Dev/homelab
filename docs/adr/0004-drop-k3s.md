# ADR 0004: Drop K3s

## Status
Accepted

## Decision
Drop k3s entirely and consolidate all workloads onto Docker Compose.

## Context
- Single-host deployment with 24GB RAM cap (practical ceiling ~12GB headroom for OS + apps)
- 19 containerized services running post-reboot on Compose with 1.7GB usage
- No multi-host scaling requirements
- Compose automation already battle-tested in production
- K3s adds operational overhead without corresponding benefit

## Rationale
1. **Resource Efficiency**: Compose has minimal footprint; K3s kubelet + etcd + CoreDNS overhead not justified for single-host
2. **Operational Simplicity**: Compose YAML already familiar to team; no need for kubectl, helm, or K3s-specific troubleshooting
3. **Proven Stability**: 90-day hybrid experiment (ADR 0001) showed Compose handles stateful workloads reliably
4. **Clear Boundary**: All services on Compose = no distributed debugging across two orchestrators
5. **Scalability is a non-requirement**: No plans for multi-node cluster; single-host + external backups sufficient

## Alternatives Considered
1. **Keep k3s for future growth**: Deferred. Complexity budget exceeded; revisit if 50+ host cluster planned
2. **Use Nomad**: Overkill; Consul + Nomad agent overhead > K3s overhead; same multi-node complexity
3. **Use Docker Swarm**: EOL/unmaintained; Swarm Mode not production-safe for stateful services
4. **Continue hybrid model**: ADR 0001 terminating; context switch cost > consolidation cost

## Migration Plan
1. **Inventory**: Audit all k3s manifests under `kubernetes/` or `k8s/` dirs; map each to Compose equiv
2. **Archive**: Move manifests to `archive/k8s/` (preserve for audit trail, not delete)
3. **Delete k3s-specific config**: Remove kubeconfig, k3s systemd units, kubelet config
4. **Verify**: All services running on Compose post-PR; health check endpoints responding
5. **Documentation**: Update DEVELOPMENT.md, AUTO_START_SETUP.md to reflect Compose-only setup

## Consequences
- **Positive**: Simplified operations, lower RAM usage, clearer troubleshooting
- **Negative**: If multi-host needed in future, migration path requires new architecture (not intra-K3s cluster growth)
- **Neutral**: Compose Swarm Mode (stacks) not used; native Compose sufficient

## References
- ADR 0001: Compose vs K3s Boundary (90-day experiment complete)
- ADR 0002: Storage Boundary (Local Path Provisioner → Compose volumes)
- ADR 0003: Ingress Boundary (Caddy reverse proxy → no K3s Ingress needed)

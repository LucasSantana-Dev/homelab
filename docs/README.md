# Homelab Documentation

This directory contains detailed documentation for specific components and features of the homelab setup.

## 📚 Documentation Index

### Core Setup & Configuration

- **[Access Layers](access-layers.md)** - **START HERE.** Canonical service × layer matrix (LAN / Tailscale / Cloudflare Tunnel) with DNS invariant
- **[Tailscale Setup](tailscale-setup.md)** - Complete Tailscale configuration and security setup
- **[Tailscale Friends Sharing](tailscale-friends-sharing.md)** - Give friends scoped access to Jellyfin/Stremio/Craftvaria via node sharing + ACL
- **[Tailscale Features Checklist](tailscale-features-checklist.md)** - Full feature activation (HTTPS, SSH, subnet router, exit node, tailnet lock, ACL sync)
- **[Interactive CLI](interactive-cli.md)** - Comprehensive interactive console application
- **[Project Structure](project-structure.md)** - Improved project organization and structure

### Hybrid Migration (K3s + Terraform)

- **[90-Day Migration Roadmap](k8s-terraform-migration-roadmap.md)** - Staged hybrid migration execution plan
- **[Phase-2 Readiness Gate](k8s-phase2-readiness-gate.md)** - Entry criteria before migrating critical stateful workloads
- **[ADR 0001](adr/0001-compose-vs-k3s-boundary.md)** - Compose/K3s boundary decision
- **[ADR 0002](adr/0002-storage-boundary-local-path.md)** - Storage strategy decision
- **[ADR 0003](adr/0003-ingress-boundary-compose-edge.md)** - Ingress boundary decision

### MCP / AI Tooling

- **[Forge Space Tools](forge-space-tools.md)** - Deploy and operate Forge Space-compatible MCP gateway on homelab

### Public Release & Security Hygiene

- **[Public Release Hardening](public-release-hardening.md)** - Credential rotation, public-safe sanitization, and history rewrite workflow

### Testing & Results

- **[Tailscale Test Results](tailscale-test-results.md)** - Security verification and test results

## 🚀 Quick Start

For basic setup and usage, see the main [README.md](../README.md) in the project root.

## 📖 Documentation Guidelines

- Keep documentation focused and specific
- Only create separate docs for complex or scoped topics
- Reference main README for general information
- Update this index when adding new documentation

## 🔧 Contributing

When adding new documentation:

1. Consider if it belongs in the main README first
2. Only create separate docs for complex topics
3. Update this index
4. Keep docs focused and well-organized

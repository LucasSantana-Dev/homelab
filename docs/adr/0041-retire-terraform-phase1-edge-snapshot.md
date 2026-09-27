# ADR 0041: Retire Terraform Phase-1; the Cloudflare edge is recorded by a read-only snapshot

- **Status:** Accepted
- **Date:** 2026-09-26
- **Deciders:** Lucas (solo operator)
- **Supersedes:** none
- **Superseded by:** none
- **Related:** [ADR-0039](./0039-ai-review-not-a-required-approval-gate.md) (required checks), [ADR-0036](./0036-host-config-management.md) (git-first deploy)

---

## Context

`infra/terraform/` ("Phase-1") managed DNS records through `cloudflare_dns_record`
and declared tunnel routes and host network rules as `terraform_data` resources
that mutate nothing. Measured on 2026-09-26:

- Last change 2026-03-15; `terraform.tfvars` and `terraform.tfstate` lived only on
  the host (not in git, no remote state). The tfvars covered 6 DNS records; the
  tunnel serves 27 hostnames (28 ingress rules with the 404 catch-all).
- The tunnel is remotely managed (dashboard), so Terraform never owned the part
  that matters: which hostnames are public.
- Adding `rclone.${DOMAIN}` that day needed a Caddy block (git), a
  dashboard route and an Access bypass app; Terraform was not usable for any of it.
- Nothing on the host ran the Terraform scripts (no cron, timer or unit), and
  `terraform-check` was required only on `main` (ADR 0039), not on `release`
  where PRs land; it was removed from `main` protection with this change.

A three-lens debate (operating cost, disaster recovery, security) converged: the
homelab's IaC is already compose + Caddyfile + sops-encrypted `.env.enc`; the gap
is the Cloudflare edge, and Terraform does not close it more cheaply than a
read-only export.

## Decision

1. Remove `infra/terraform/`, the `terraform-check` CI job, the
   `post-t24-terraform-apply` / `schedule-post-t24-terraform-apply` Make targets,
   and `scripts/maintenance/{post-t24-terraform-apply,terraform-state-backup}.sh`.
2. The record of the edge is `config/cloudflared/edge-snapshot.json`, written by
   `scripts/maintenance/cloudflare-edge-snapshot.py` (GET only; account and tunnel
   discovered through the API; record contents redacted by allowlist since the
   repo is public). Refresh it after any dashboard change.
3. `config/cloudflared/config.yml` keeps only the routing shape and points at the
   snapshot, instead of a host list that drifts.
4. No Cloudflare token with DNS or tunnel edit scope is added to CI.

## Alternatives considered

- **Promote Terraform to own the edge** (`cloudflare_zero_trust_tunnel_cloudflared_config`
  plus all DNS, remote state): four objects that rarely change do not justify
  state handling, provider v5 breaking changes and an edit-scope token for a
  single operator. State in a public repo, even encrypted, was rejected.
- **Keep Phase-1 as is:** it documented 6 of 27 hostnames and gave false
  confidence; stale declarations are worse than none.

## Consequences

**Positive:** one fewer toolchain and CI job; the edge is recoverable from git
(snapshot) instead of memory; drift is a `git diff` after a refresh.

**Negative / neutral:** DNS and tunnel changes are still dashboard clicks; the
snapshot detects drift, it does not prevent it. The host still has the old
untracked `infra/terraform/` files (state, tfvars); delete them by hand after
this merges.

## Revisit when

- The tunnel moves to local management (`config.yml` + credentials via sops): that
  makes ingress a PR, and this ADR's step 3 changes.
- A second host, VMs or another provider appear, where a planner earns its cost.

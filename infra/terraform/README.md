# Terraform Phase-1 (DNS + Tunnel + Network Declarations)

## Overview

This Terraform configuration implements **phase-1 of the homelab infrastructure migration**: explicit DNS and tunnel routing declarations without committing runtime state. The design prioritizes visibility and drift detection while keeping the runtime edge (Caddy, Cloudflared) in Docker Compose.

### Phase-1 Strategy

- **No state files committed** — Terraform state is intentionally kept local and .gitignored. State is computed per-run from Cloudflare's live API.
- **Plan-only declarations** — DNS and tunnel routes are declared via `terraform_data` resources (no remote state management). This gives visibility to routing changes without mutation risk.
- **Drift detection** — Running `terraform plan` twice should yield a no-op second plan, proving the declared state matches reality.
- **Runtime unchanged** — Service routing is still managed by `compose/core.yml` (Caddy LAN, Cloudflared tunnels). Terraform documents these routes but does not control their deployment.

### Why This Approach?

1. **Safety**: No risk of Terraform destroying or modifying live DNS/tunnel routes on apply mistakes.
2. **Clarity**: All routing decisions are explicit and version-controlled in `.tf` files.
3. **Flexibility**: Easy to promote to full IaC later (add remote state, service provisioning) without refactoring.
4. **Auditability**: Git history shows who changed what routes and when.

## Configuration Files

- `main.tf` — Cloudflare DNS records + tunnel/network route declarations
- `variables.tf` — Input variables (account ID, zone ID, routes)
- `terraform.tfvars.example` — Template for secrets (copy to `terraform.tfvars`, never commit)
- `outputs.tf` — Exported values (route summary, DNS record status)
- `versions.tf` — Provider requirements (Cloudflare provider version)

## Usage

### First-time Setup

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your Cloudflare account ID, zone ID, and routes
terraform init
terraform fmt -check
terraform validate
terraform plan
```

### Regular Operations

Verify no drift:
```bash
terraform plan
terraform plan   # Should output "No changes. Your infrastructure matches the configuration."
```

Add a new DNS record or route:
1. Edit `terraform.tfvars` to add the new route/record
2. Run `terraform plan` to preview
3. Run `terraform apply` to register (Cloudflare API update only)
4. Commit `terraform.tfvars` changes

### Rollback or Removal

To remove a route from Terraform management:
1. Remove it from `terraform.tfvars`
2. Run `terraform plan` to confirm it will be removed from Cloudflare
3. Run `terraform apply`

**Note**: If the route is active in compose (e.g., a live Caddy ingress), the service will stop responding to that route after Terraform removes it from DNS. Coordinate with the ops team.

## State Management

- **State file location** — `.terraform/terraform.tfstate` (local, .gitignored)
- **No remote state** — Intentional. To upgrade to remote state in the future, add a `cloud {}` block in `versions.tf` and run `terraform cloud login`.
- **Secrets** — `terraform.tfvars` contains `account_id` and API token (if using static creds; recommended: use Cloudflare API token with least-privilege scope).

## Drift Detection

Phase-1 uses `terraform_data` to track route declarations without managing remote state. To detect drift:

1. Run a plan after any manual Cloudflare console changes:
   ```bash
   terraform plan
   ```
2. If routes in `terraform.tfvars` differ from live Cloudflare DNS/tunnel config, the plan will show removals and additions.
3. Either update `terraform.tfvars` to match live state, or apply Terraform to correct live state.

## Future: Phase-2 and Beyond

- **Phase-2**: Add Cloudflare Tunnel ingress provisioning (create/update tunnels themselves).
- **Phase-3**: Import Docker Compose state, provision services from Terraform.
- **Phase-4**: Multi-environment (dev/prod), remote state backend, OIDC or Workload Identity.

For now, phase-1 remains plan-only to reduce operational risk.

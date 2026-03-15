# Homelab Terraform Operations

Run Terraform validation, planning, and apply operations for the homelab Cloudflare infrastructure.

## When to Use

- Terraform plan/apply/validate operations
- DNS record changes via Cloudflare provider
- Drift detection and state reconciliation
- Adding new services to Terraform management

## Prerequisites

- Terraform binary: `~/.local/bin/terraform`
- Cloudflare API token: `CLOUDFLARE_API_TOKEN` from `.env`
- Config dir: `infra/terraform/`
- State: local at `infra/terraform/terraform.tfstate` (no remote backend)

## Workflow

### 1. Pre-checks

```bash
cd infra/terraform
~/.local/bin/terraform fmt -check -diff
~/.local/bin/terraform validate
```

### 2. Plan

```bash
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' /home/luk-server/homelab/.env | cut -d= -f2-)
~/.local/bin/terraform plan -input=false -detailed-exitcode -no-color
# Exit 0 = no changes, Exit 2 = changes pending, Exit 1 = error
```

### 3. Apply (requires GREENLIGHT or operator approval)

```bash
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' /home/luk-server/homelab/.env | cut -d= -f2-)
~/.local/bin/terraform apply -input=false -auto-approve -no-color
```

### 4. Post-apply verification

```bash
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' /home/luk-server/homelab/.env | cut -d= -f2-)
~/.local/bin/terraform plan -input=false -detailed-exitcode -no-color
# Must exit 0 (no-op)
```

## Key Files

- `infra/terraform/main.tf` — resource definitions (DNS records, terraform_data declarations)
- `infra/terraform/variables.tf` — input variable definitions
- `infra/terraform/terraform.tfvars` — values (gitignored, contains real IDs)
- `infra/terraform/outputs.tf` — output values
- `infra/terraform/versions.tf` — provider and version constraints
- `.sops.yaml` — SOPS encryption rules for k8s secrets

## Safety Rules

- Never commit `terraform.tfvars` or `terraform.tfstate*` (gitignored)
- Always run `plan` before `apply`
- Post-apply must show exit 0 (no drift)
- DNS changes are reversible but affect production routing
- The `lifecycle { ignore_changes = [comment] }` block prevents Cloudflare API null/empty drift

## Adding a New DNS Record

1. Add entry to `terraform.tfvars` `dns_records` map
2. Optionally add tunnel route to `tunnel_routes` map
3. Run plan to verify expected changes
4. Apply and verify no-op

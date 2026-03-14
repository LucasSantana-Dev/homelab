# Terraform Phase-1 (DNS + Tunnel + Network Declarations)

This root is the **infra-first** scope for the 90-day hybrid migration:

- Manage Cloudflare DNS records needed for migration waves.
- Track tunnel route declarations in Terraform state.
- Track host-network rule declarations in Terraform state.
- Keep runtime edge (`nginx` + `cloudflared` in compose) unchanged in phase 1.

## Usage

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan
```

For drift checks, run `terraform plan` twice and ensure the second plan is no-op.

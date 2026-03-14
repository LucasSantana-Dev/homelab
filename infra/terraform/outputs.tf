output "managed_dns_records" {
  description = "Managed DNS record IDs and hostnames."
  value = {
    for key, record in cloudflare_dns_record.dns_records : key => {
      id      = record.id
      name    = record.name
      type    = record.type
      content = record.content
      proxied = record.proxied
    }
  }
}

output "tunnel_route_declarations" {
  description = "Phase-1 tunnel route declarations stored in state."
  value = {
    for key, decl in terraform_data.tunnel_route_declarations : key => decl.output
  }
}

output "host_network_rule_declarations" {
  description = "Phase-1 host network rule declarations stored in state."
  value = {
    for key, decl in terraform_data.host_network_rule_declarations : key => decl.output
  }
}

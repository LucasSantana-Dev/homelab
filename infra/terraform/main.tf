resource "cloudflare_dns_record" "dns_records" {
  for_each = var.dns_records

  zone_id = var.zone_id
  name    = each.value.name
  type    = upper(each.value.type)
  content = each.value.content
  proxied = try(each.value.proxied, true)
  ttl     = try(each.value.ttl, 1)
  comment = try(each.value.comment, "")
}

# Phase-1 intentionally tracks tunnel routing declarations in Terraform state
# while keeping runtime ingress on compose nginx + cloudflared.
resource "terraform_data" "tunnel_route_declarations" {
  for_each = var.tunnel_routes

  input = {
    account_id = var.account_id
    tunnel_id  = var.tunnel_id
    hostname   = each.value.hostname
    service    = each.value.service
    path       = try(each.value.path, "")
  }
}

# Phase-1 host-network declarations for policy visibility and drift tracking.
resource "terraform_data" "host_network_rule_declarations" {
  for_each = var.host_network_rules

  input = {
    description = each.value.description
    source      = each.value.source
    destination = each.value.destination
    protocol    = lower(each.value.protocol)
    ports       = each.value.ports
    action      = lower(each.value.action)
  }
}

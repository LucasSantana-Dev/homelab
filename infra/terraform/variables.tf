variable "cloudflare_api_token" {
  description = "Cloudflare API token. Prefer CLOUDFLARE_API_TOKEN env var in CI/local shell."
  type        = string
  default     = ""
  sensitive   = true
}

variable "account_id" {
  description = "Cloudflare account ID used for tunnel and Zero Trust declarations."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for DNS records."
  type        = string
}

variable "tunnel_id" {
  description = "Cloudflare tunnel UUID used by the existing cloudflared deployment."
  type        = string
}

variable "dns_records" {
  description = "DNS records managed in phase 1."
  type = map(object({
    name    = string
    type    = string
    content = string
    proxied = optional(bool, true)
    ttl     = optional(number, 1)
    comment = optional(string, "")
  }))
  default = {}
}

variable "tunnel_routes" {
  description = "Tunnel hostname/service declarations tracked in Terraform state."
  type = map(object({
    hostname = string
    service  = string
    path     = optional(string, "")
  }))
  default = {}
}

variable "host_network_rules" {
  description = "Host-level network rule declarations for migration governance."
  type = map(object({
    description = string
    source      = string
    destination = string
    protocol    = string
    ports       = list(number)
    action      = string
  }))
  default = {}
}

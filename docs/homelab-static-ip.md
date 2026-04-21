# Homelab Static IP (192.168.0.11)

## Why

Router DHCP leases rotate after reboots. Every downstream reference
hardcodes `192.168.0.11`:

- Pi-hole `*.home` dnsmasq records (`config/pihole/etc-dnsmasq.d/02-local-home.conf`)
- Caddy-LAN routes (LAN proxy to the homelab host)
- Memory + docs (`memory/homelab-network.md`, `docs/dns-setup.md`)

When the lease rotates to, say, `192.168.0.4`, nothing on the LAN can
reach the homelab by name anymore — only Tailscale works. A static IP
at the host level prevents this class of outage without depending on
the router's reservation UI (TP-Link DHCP reservations have been
unreliable historically).

## What

`config/netplan/60-homelab-static.yaml.example` — a netplan drop-in
that fixes `enp1s0` at `192.168.0.11/24`, gateway `192.168.0.1`,
DNS pointing at local Pi-hole + upstream fallbacks.

## Apply (one-time, on the homelab host)

```bash
sudo cp config/netplan/60-homelab-static.yaml.example /etc/netplan/60-homelab-static.yaml
sudo chmod 600 /etc/netplan/60-homelab-static.yaml
sudo netplan apply
```

Verify from another LAN device:

```bash
ping -c 2 192.168.0.11          # should respond in <10ms
dig @192.168.0.11 stremio.home  # should return 192.168.0.6 (dnsmasq alias)
```

## Rollback

```bash
sudo rm /etc/netplan/60-homelab-static.yaml
sudo netplan apply              # back to DHCP via 50-cloud-init.yaml
```

## Interaction with existing netplan files

The cloud-init default at `/etc/netplan/50-cloud-init.yaml` sets
`dhcp4: true`. The static drop-in has a higher filename number (60 > 50),
so netplan's last-wins merging applies the static config and ignores the
DHCP request. If both needed to coexist, rename the static file lower
than 50.

## Related

- `scripts/security/apply-ufw-baseline.sh` — firewall rules keyed to LAN range.
- `memory/homelab-network.md` — overall topology.
- Router-side DHCP reservation is still recommended as a belt-and-suspenders
  fallback; this host-side static is just the most reliable of the two.

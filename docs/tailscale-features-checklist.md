# Tailscale Feature Activation Checklist

Flips every Tailscale feature worth having on this tailnet. Most of
this is admin-console UI; a few steps are host-side `tailscale up` flags.

Legend: `[ ]` not done · `[x]` done · `[~]` partial / verify.

## 1. Identity & policy

- [ ] **Apply ACL** — paste `tailscale/acl.hujson` into
      [admin/acls](https://login.tailscale.com/admin/acls).
- [ ] **GitHub ACL sync** —
      [admin/settings/tailnet-policy](https://login.tailscale.com/admin/settings/general)
      → "Sync ACL from GitHub" → point at this repo + branch `main` +
      path `tailscale/acl.hujson`. Once enabled, merges to `main`
      auto-push policy.
- [ ] **Tailnet lock** —
      [admin/settings/tailnet-lock](https://login.tailscale.com/admin/settings/tailnet-lock).
      Nice for paranoia; blocks compromised coordination-server from
      adding rogue nodes. Needs one signing key per trusted device.
- [ ] **Device key expiry** —
      [admin/settings/keys](https://login.tailscale.com/admin/settings/keys).
      Set to **90 days** with auto-renewal on active devices.

## 2. DNS

- [~] **MagicDNS** — enabled per memory; verify at
      [admin/dns](https://login.tailscale.com/admin/dns).
- [~] **Search domain** — `homelab.example.com` per
      `docs/tailscale-dns-records-setup.md`.
- [ ] **Split DNS for `*.home`** — add local-only records so
      `jellyfin.home` resolves via the homelab Pi-hole from tailnet
      clients too (currently LAN-only). Add `home` nameserver →
      `100.64.0.10:53` in admin DNS page.
- [ ] **DNS A records** for `homelab.example.com` +
      `*.homelab.example.com` → `100.64.0.10`. Already documented in
      `docs/tailscale-dns-records-setup.md` — apply if not yet done.
- **⚠ DNS guardrail** — never publish Tailscale A records for
  `*.luk-homeserver.com.br`. That domain is Cloudflare-tunneled;
  overlapping records would bypass Cloudflare Access. See
  [`access-layers.md`](access-layers.md) for the canonical
  service × layer matrix.

## 3. HTTPS certificates

- [ ] **Enable HTTPS** —
      [admin/dns](https://login.tailscale.com/admin/dns) → **Enable
      HTTPS**. Free LE cert per node on `<hostname>.<tailnet>.ts.net`.
- [ ] **Issue per-service cert** on homelab host:

      ```bash
      sudo tailscale cert homelab.<your-tailnet>.ts.net
      ```

- [ ] Wire Caddy to read those certs instead of self-signed ones so
      browser warnings go away.

## 4. Connectivity & routing

- [ ] **Subnet router** — homelab advertises `192.168.0.0/24` so
      tailnet clients can reach LAN-only devices (TV, printer):

      ```bash
      sudo tailscale up --advertise-routes=192.168.0.0/24 --reset
      ```

      Auto-approval for `tag:homelab` is already in the ACL's
      `autoApprovers.routes`.
- [ ] **Exit node** — homelab offers itself as an exit node for when
      you're on hostile WiFi:

      ```bash
      sudo tailscale up --advertise-exit-node --reset
      ```

      Auto-approval is already in the ACL's `autoApprovers.exitNode`.
- [ ] **Use exit node on laptop / phone**:
      `tailscale up --exit-node=homelab`.

## 5. SSH

- [ ] **Tailscale SSH on homelab**:

      ```bash
      sudo tailscale up --ssh --reset
      ```

      Once active, you can `ssh homelab` with zero key management —
      Tailscale identity authenticates. Keep OpenSSH as a fallback.
- [ ] **Verify ACL rule** already accepts `autogroup:admin → autogroup:self`.
- [ ] Remove any friend / stale keys from `~/.ssh/authorized_keys`.

## 6. File sharing

- [ ] **Taildrop** — already available; test:

      ```bash
      tailscale file cp README.md homelab:
      ```

      On homelab, files land in `/var/lib/tailscale/files`.

## 7. Tailscale Serve (HTTPS proxy, private)

- [ ] Apply `tailscale/serve.json` on homelab:

      ```bash
      sudo tailscale serve --set-path=/etc/tailscale/serve.json \
        < tailscale/serve.json
      ```

      Then https://homelab.<tailnet>.ts.net/grafana/ etc. work with
      valid certs, reachable only from tailnet.

## 8. Tailscale Funnel (public HTTPS — selective use)

- [ ] **Public status page only** (e.g. Uptime Kuma status at
      `https://status.<tailnet>.ts.net`):

      ```bash
      sudo tailscale funnel --bg 3001
      ```

      Do **not** funnel any auth'd service. ACL blocks this by default;
      confirm `AllowFunnel` stays empty for critical services.

## 9. Per-device tags (via `tailscale up --advertise-tags=`)

| Device         | Tags                                               |
|----------------|----------------------------------------------------|
| homelab host   | `tag:homelab,tag:homelab-friends-exposed`          |
| MacBook        | `tag:laptop`                                       |
| Phone          | `tag:mobile`                                       |
| GitHub Actions | `tag:ci` *(via tailscale/github-action OIDC)*      |

Each tag must exist in `tailscale/acl.hujson` → `tagOwners` first.

## 10. GitHub Actions ↔ Tailscale (optional)

- [ ] Use
      [`tailscale/github-action`](https://github.com/tailscale/github-action)
      with OIDC so deploy workflows reach homelab over the tailnet
      without shipping SSH keys. Tag the ephemeral runner as `tag:ci`.

## 11. Audit & monitoring

- [ ] **Logstream** — admin/settings/logs → route Tailscale audit
      events to Grafana Loki (once loki is confirmed kept after the
      service audit, PR #28).
- [ ] **SSH session recording** — admin/settings → SSH session
      recording → store in tailnet-local S3-compatible bucket.
- [ ] **Monthly audit review** — check admin/logs for unexpected
      friend connections.

## 12. Plan tier

- [~] **Personal Pro vs Free** — Free plan caps: 100 devices, 3 users,
      3 shared-node invites. If friend count exceeds 3 or tailnet
      lock / session recording isn't available, consider upgrade.

---

## Order-of-operations

1. **Now (Phase 1 — this PR):** codify ACL + serve + this checklist.
2. **Phase 2 (browser, needs auth):** Playwright walks admin console
   and flips every toggle in sections 1–3, 11. A separate session
   drives this with your help accepting consent prompts.
3. **Phase 3 (host-side):** ssh homelab and run the `tailscale up …`
   flags from sections 4, 5, 7. One command, reset, verify.

See `docs/tailscale-friends-sharing.md` for the friend-onboarding side.

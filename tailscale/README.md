# Tailscale ACL

Source of truth for the tailnet access policy. The admin console UI
is *not* authoritative — edit this file and apply it.

## Files

- `acl.hujson` — the policy. HuJSON = JSON with comments + trailing commas.

## Apply

**Recommended — GitHub integration:** enable
[Tailscale ↔ GitHub sync](https://tailscale.com/kb/1207/acl-github) so
merges to `main` auto-push this file. One-time setup in the admin console.

**Manual:**

1. Copy the contents of `acl.hujson`.
2. Paste into https://login.tailscale.com/admin/acls.
3. Click **Save** — Tailscale validates + runs the `tests` block.

## Tag the homelab host

The ACL references `tag:homelab-friends-exposed`. Apply it once on the
host running the friend-facing services (Jellyfin / Stremio / Craftvaria):

```bash
sudo tailscale up --advertise-tags=tag:homelab-friends-exposed --reset
```

## Onboard a friend

Pick one path — node sharing is preferred for close friends.

### Path A — Node sharing (recommended)

Friend stays on their own tailnet. Zero seats on yours.

1. Admin console → **Machines** → homelab host → **Share** →
   enter friend's Tailscale email → send invite.
2. Friend accepts → homelab host appears in their tailnet as a shared node.
3. ACL via `autogroup:shared` restricts them to Jellyfin/Stremio/Minecraft.

### Path B — Guest user on this tailnet

1. Admin console → **Users** → **Invite external users** → email.
2. Add their email to `group:friends` in `acl.hujson` → commit → apply.

## Revoke

- Path A: admin console → **Sharing** → revoke.
- Path B: remove their email from `group:friends` → commit → apply. Done.

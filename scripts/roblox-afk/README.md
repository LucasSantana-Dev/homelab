# Roblox AFK rig (headless Ubuntu)

Runs Roblox unattended on a headless server (via **Sober**, the Android Roblox
build) inside a **labwc** Wayland session, viewable over **wayvnc** on loopback,
with an **anti-AFK pointer jiggle** that defeats Roblox's 20-minute idle
disconnect **without disturbing the running game**.

Built for the `homelab` server (Intel N100 iGPU, Ubuntu 25.04). Full build log +
rationale: `.claude/plans/roblox-anti-afk-2026-07-08.md`.

## How the anti-AFK works

`roblox-antiafk.sh` loops every **5–17 min** (randomized, always under the 20-min
kick) and does a tiny **virtual-pointer jiggle** — a few pixels out and back via
`wlrctl`, **no click, net-zero, keyboard untouched**. Mouse motion resets
Roblox's idle timer; because nothing is clicked and the cursor returns to origin,
an auto-farming game (the target is a fishing/idle sim with "Auto" enabled) keeps
running and the avatar never moves off its spot.

Deliberately **not** arrow/WASD keys — those move the character in Roblox and
could walk it off a farm spot.

## Components

| Unit | Role |
|------|------|
| `labwc.service` | headless Wayland compositor (`WLR_BACKENDS=headless`, iGPU gles2), `wayland-0` |
| `wayvnc.service` | VNC server, **127.0.0.1:5900 only** |
| `sober.service` | Sober / Roblox client |
| `roblox-antiafk.service` | the pointer-jiggle loop |

`udev/99-roblox-dri.rules` gives the rig user durable iGPU access (the DRM nodes
otherwise come up inaccessible → Sober aborts with "couldn't find a supported
graphics device"). `install.sh` also installs `xdg-desktop-portal-wlr`/`-gtk`
(without a portal backend the GTK launcher hangs 120s and never shows a window).

## Install

```sh
./install.sh          # apt + flatpak + udev + portal + systemd user units (idempotent)
```

Then first run (interactive Roblox login required once):

```sh
systemctl --user start labwc wayvnc sober
# from your machine:
ssh -L 5900:127.0.0.1:5900 luk-server@homelab
# open TigerVNC -> localhost:5900   (macOS Screen Sharing can't speak wayvnc)
# sign into Roblox, join your idle game, then:
systemctl --user start roblox-antiafk
```

After the first login the token is cached, so a **reboot brings the whole rig
back automatically** (linger + enabled units).

## Operate

```sh
ssh homelab journalctl --user -u roblox-antiafk -f     # watch each nudge
ssh homelab systemctl --user stop  roblox-antiafk       # pause anti-AFK
ssh homelab systemctl --user restart sober              # relaunch the client
ssh homelab systemctl --user stop  sober wayvnc labwc   # tear down session
```

## Security

- **wayvnc is loopback-only.** Reach it through the SSH tunnel above; never bind
  it to LAN/Tailscale, and type Roblox credentials only over that tunnel.
- No client modification/injection — Sober runs the stock Roblox APK; this uses
  only OS-level virtual input.

## ToS

Anti-AFK circumvents Roblox's intended 20-minute idle disconnect. OS-level input
macros are not platform-banned, and Sober's Android build is outside the
Hyperion anti-cheat's client-tamper scope — but per-game rules vary (competitive
experiences often ban macros) and **account risk is the operator's informed
choice**. Intended for idle/grind sims only.

## Troubleshooting

- **Black VNC / "couldn't find a supported graphics device"** — iGPU access lost.
  Check `test -w /dev/dri/renderD128`; the udev rule + `render` group fix it on
  boot (re-run `install.sh`, then re-login the user session).
- **Launcher hangs, no window** — portal backend missing; ensure
  `xdg-desktop-portal-wlr` is running in the session.
- **Wrong `WAYLAND_DISPLAY`** — labwc normally takes `wayland-0` on a clean boot;
  confirm with `ls /run/user/1000/wayland-*` and adjust unit env if it differs.
- **Stale Sober won't relaunch** — kill by exact name only:
  `pkill -u luk-server -x sober; pkill -u luk-server -x bwrap`. Never
  `pkill -f sober` from an SSH command (it matches your own shell).

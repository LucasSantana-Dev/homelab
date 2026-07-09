#!/usr/bin/env bash
# install.sh — provision the Roblox AFK rig on a headless Ubuntu host.
# Idempotent: safe to re-run. Does NOT restart an already-running session.
#
# Prereqs assumed present (installed during first setup): flatpak + Sober,
# labwc, wayvnc, wlrctl, xdg-desktop-portal-wlr/-gtk. Re-run apt lines below to
# be sure. Run as the rig user (luk-server); uses sudo for system bits.
set -euo pipefail

RIG_USER="${RIG_USER:-$(id -un)}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> apt packages"
sudo apt-get install -y labwc wayvnc wlrctl wtype grim \
  xdg-desktop-portal-wlr xdg-desktop-portal-gtk

echo "==> flatpak Sober"
sudo flatpak install -y flathub org.vinegarhq.Sober || true

echo "==> GPU render-node access (udev, durable — replaces volatile setfacl)"
sudo install -m 0644 "$HERE/udev/99-roblox-dri.rules" /etc/udev/rules.d/99-roblox-dri.rules
sudo usermod -aG render "$RIG_USER"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=drm

echo "==> desktop portal preference"
mkdir -p "$HOME/.config/xdg-desktop-portal"
printf '[preferred]\ndefault=wlr;gtk\norg.freedesktop.impl.portal.FileChooser=gtk\n' \
  > "$HOME/.config/xdg-desktop-portal/portals.conf"

echo "==> systemd user units"
install -d "$HOME/.config/systemd/user"
install -m 0644 "$HERE"/systemd/*.service "$HOME/.config/systemd/user/"
sudo loginctl enable-linger "$RIG_USER"
systemctl --user daemon-reload
systemctl --user enable labwc.service wayvnc.service sober.service roblox-antiafk.service

cat <<EOF

Done. Units enabled for boot (auto-start via linger).

First run needs an interactive Roblox login:
  1) start now without reboot:  systemctl --user start labwc wayvnc sober
  2) tunnel + view:             ssh -L 5900:127.0.0.1:5900 $RIG_USER@<host>   # then TigerVNC -> localhost:5900
  3) sign into Roblox, join your idle game
  4) start the loop:            systemctl --user start roblox-antiafk

After that, a reboot brings the whole rig back automatically (login stays cached).
Note: 'render' group membership applies to the user manager on next login/boot;
the currently-running session keeps whatever access it already had.
EOF

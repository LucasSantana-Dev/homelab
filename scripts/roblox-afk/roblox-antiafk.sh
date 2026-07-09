#!/usr/bin/env bash
# roblox-antiafk.sh — defeat Roblox's 20-minute idle disconnect on the headless
# labwc/Sober rig WITHOUT disturbing the running game.
#
# Input method: a tiny virtual-pointer jiggle (move a few px, then move back) via
# wlrctl. Mouse MOTION resets Roblox's idle timer; we never click and the cursor
# returns to origin, so an auto-farming game (e.g. a fishing/idle sim with "Auto"
# enabled) keeps running and the avatar never moves. Deliberately NOT arrow/WASD
# keys — those move the character in Roblox and could walk it off its farm spot.
#
# Session env (Path B): compositor labwc, WAYLAND_DISPLAY=wayland-0.
# Requirements: wlrctl (apt). Runs inside the luk-server user session.
#
# ToS note: anti-AFK circumvents Roblox's intended idle disconnect. OS-level input
# is not platform-banned and Sober's Android build is outside Hyperion's client-
# tamper scope, but per-game rules vary and account risk is the operator's choice.
# Suits idle/grind sims; do not use in competitive experiences.
#
# Usage: WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 ./roblox-antiafk.sh
#        (Ctrl+C / `systemctl --user stop roblox-antiafk` to stop)

set -euo pipefail

: "${XDG_RUNTIME_DIR:=/run/user/1000}"
: "${WAYLAND_DISPLAY:=wayland-0}"
export XDG_RUNTIME_DIR WAYLAND_DISPLAY

MIN_SLEEP=300 # 5 min floor
JITTER=720    # + up to 12 min -> 5-17 min, always under the 20-min idle kick

log() { printf '[%s] %s\n' "$(date '+%F %H:%M:%S')" "$*" >&2; }

command -v wlrctl >/dev/null 2>&1 || { log "wlrctl not found (apt install wlrctl)"; exit 1; }
[ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] || { log "no wayland socket at $XDG_RUNTIME_DIR/$WAYLAND_DISPLAY"; exit 1; }

trap 'log "stopped"; exit 0' INT TERM

log "anti-afk started (pointer jiggle, no clicks; $WAYLAND_DISPLAY)"

while true; do
  sleep_s=$((MIN_SLEEP + RANDOM % JITTER))
  log "next nudge in $((sleep_s / 60))m$((sleep_s % 60))s"
  sleep "$sleep_s"
  # random small offset, then return to origin -> net-zero cursor movement
  dx=$((4 + RANDOM % 9))
  dy=$((4 + RANDOM % 9))
  wlrctl pointer move "$dx" "$dy"
  sleep 1
  wlrctl pointer move "-$dx" "-$dy"
  log "nudged pointer (+$dx,+$dy -> back)"
done

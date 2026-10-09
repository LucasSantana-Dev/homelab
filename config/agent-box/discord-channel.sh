#!/bin/bash
# Keep the Discord channel session (claude --channels, official plugin) alive in tmux.
# Runs as agent, started in the background by entrypoint.sh. Fails closed: the session
# only starts when the token, the plugin and an allowlist-only access.json are all present.
# Stop it: touch ~/discord-channel-off (resume: rm it). Attach: tmux attach -t discord
set -uo pipefail

SESSION=discord
PLUGIN=discord@claude-plugins-official
STATE_DIR=$HOME/.claude/channels/discord
RULES=/opt/agent-config/discord-channel.md
INTERVAL=${DISCORD_CHANNEL_INTERVAL:-30}

log() { echo "$(date -Is) [discord-channel] $*"; }
LAST=""
# Log a not-ready reason once per change, not every interval.
why() { [[ "$1" == "$LAST" ]] || log "$1"; LAST=$1; }

# 0 when access.json pins DMs to a non-empty allowlist and no guild channel is open.
access_ok() {
    python3 - "$STATE_DIR/access.json" <<'PY'
import json, sys
try:
    a = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
ok = (a.get("dmPolicy") == "allowlist"
      and isinstance(a.get("allowFrom"), list) and len(a["allowFrom"]) > 0
      and all(str(u).isdigit() for u in a["allowFrom"])
      and not a.get("groups"))
sys.exit(0 if ok else 1)
PY
}

ready() {
    [[ ! -e $HOME/discord-channel-off ]] || { why "off: ~/discord-channel-off exists"; return 1; }
    [[ -s $STATE_DIR/.env ]] || { why "waiting: no token in $STATE_DIR/.env"; return 1; }
    grep -q "\"$PLUGIN\"" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null \
        || { why "waiting: plugin $PLUGIN not installed"; return 1; }
    access_ok || { why "waiting: access.json is not allowlist-only"; return 1; }
    LAST=""
}

start() {
    log "starting tmux session $SESSION"
    # static: access.json is read once at boot and never written, so pairing is off and
    # nothing said in the chat can widen the allowlist.
    tmux new-session -d -s "$SESSION" -c /workspace \
        "source /etc/profile.d/agent-env.sh 2>/dev/null; unset ANTHROPIC_API_KEY CLAUDE_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX; \
DISCORD_ACCESS_MODE=static exec claude --channels plugin:$PLUGIN \
--append-system-prompt \"\$(cat $RULES)\""
}

while true; do
    if ! tmux has-session -t "$SESSION" 2>/dev/null && ready; then
        start || log "tmux start failed"
    fi
    sleep "$INTERVAL"
done

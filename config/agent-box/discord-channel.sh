#!/bin/bash
# Keep the Discord channel session (claude --channels, official plugin) alive in tmux.
# Runs as agent, started in the background by entrypoint.sh. Fails closed: the session
# only starts when the token, the plugin and an access.json that allows exactly the owner
# (root-owned OWNER_FILE, from SOPS) are all present.
# Stop it: touch ~/discord-channel-off (resume: rm it). Attach: tmux attach -t discord
set -uo pipefail

SESSION=discord
PLUGIN=discord@claude-plugins-official
STATE_DIR=$HOME/.claude/channels/discord
OWNER_FILE=${DISCORD_OWNER_FILE:-/etc/agent-box/discord-owner-id}
CONF=/opt/agent-config
EXIT_LOG=$HOME/discord-channel.exit
INTERVAL=${DISCORD_CHANNEL_INTERVAL:-30}
MAX_BACKOFF=900

log() { echo "$(date +%FT%T%z) [discord-channel] $*"; }
LAST=""
# Log a state once per change, not every interval.
why() { [[ "$1" == "$LAST" ]] || log "$1"; LAST=$1; }

# 0 when access.json allows DMs from exactly the owner and no guild channel is open.
# The owner ID comes from a root-owned file, so a same-uid process cannot widen it.
access_ok() {
    python3 - "$STATE_DIR/access.json" "$OWNER_FILE" <<'PY'
import json, sys
try:
    a = json.load(open(sys.argv[1]))
    owner = open(sys.argv[2]).read().strip()
except Exception:
    sys.exit(1)
ok = (owner.isdigit()
      and a.get("dmPolicy") == "allowlist"
      and a.get("allowFrom") == [owner]
      and not a.get("groups"))
sys.exit(0 if ok else 1)
PY
}

ready() {
    [[ ! -e $HOME/discord-channel-off ]] || { why "off: ~/discord-channel-off exists"; return 1; }
    [[ -s $STATE_DIR/.env ]] || { why "waiting: no token in $STATE_DIR/.env"; return 1; }
    grep -q "\"$PLUGIN\"" "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null \
        || { why "waiting: plugin $PLUGIN not installed"; return 1; }
    access_ok || { why "waiting: access.json does not allow exactly the owner"; return 1; }
}

# Accept the /workspace trust dialog so an unattended start does not hang on it.
trust_workspace() {
    python3 - "$HOME/.claude.json" <<'PY'
import json, os, sys, tempfile
p = sys.argv[1]
try:
    d = json.load(open(p))
except Exception:
    sys.exit(0)  # no login state yet; the stall check reports it
proj = d.setdefault("projects", {}).setdefault("/workspace", {})
if proj.get("hasTrustDialogAccepted"):
    sys.exit(0)
proj["hasTrustDialogAccepted"] = True
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p))
with os.fdopen(fd, "w") as f:
    json.dump(d, f, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, p)
PY
}

start() {
    trust_workspace || log "could not pre-accept workspace trust"
    log "starting tmux session $SESSION"
    # static: access.json is read once at start and never written, so pairing is off and
    # nothing said in the chat can widen the allowlist. The settings file enables the
    # plugin for this session only and pins prompts on (no auto mode).
    tmux new-session -d -s "$SESSION" -c /workspace \
        "source /etc/profile.d/agent-env.sh 2>/dev/null; \
unset DISCORD_BOT_TOKEN ANTHROPIC_API_KEY CLAUDE_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX; \
DISCORD_ACCESS_MODE=static claude --channels plugin:$PLUGIN \
--settings $CONF/discord-channel-settings.json --permission-mode default \
--append-system-prompt \"\$(cat $CONF/discord-channel.md)\"; \
echo \"\$(date +%FT%T%z) claude exited \$?\" >> $EXIT_LOG"
}

STARTED=0 FAILS=0 NEXT=0
while true; do
    now=$(date +%s)
    if tmux has-session -t "$SESSION" 2>/dev/null; then
        pane=$(tmux capture-pane -p -t "$SESSION" 2>/dev/null || true)
        if grep -qiE 'do you trust|trust this folder|select login|log ?in to|press enter to continue' <<<"$pane"; then
            why "stalled: claude is waiting for input (tmux attach -t $SESSION)"
        elif (( now - STARTED > 120 )) && ! pgrep -u "$(id -u)" -f 'bun.*server\.ts' >/dev/null; then
            why "warning: discord MCP server (bun) is not running"
        else
            why "running"
        fi
    elif (( now >= NEXT )) && ready; then
        if (( STARTED > 0 )); then
            log "session ended: $(tail -n1 "$EXIT_LOG" 2>/dev/null || echo 'no exit record')"
            # Back off on fast exits (crash loop); reset after a session that lived 2 min.
            if (( now - STARTED < 120 )); then FAILS=$((FAILS + 1)); else FAILS=0; fi
            delay=$(( INTERVAL * (1 << (FAILS < 5 ? FAILS : 5)) ))
            (( delay > MAX_BACKOFF )) && delay=$MAX_BACKOFF
            if (( FAILS > 0 )); then
                NEXT=$((now + delay)); STARTED=0
                log "fast exit #$FAILS, next start in ${delay}s"
                continue
            fi
        fi
        if start; then STARTED=$now; else log "tmux start failed"; fi
    fi
    sleep "$INTERVAL"
done

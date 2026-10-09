#!/bin/bash
set -euo pipefail
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

log() { echo "[agent-box] $*"; }

# Everything under /home/agent is writable by the agent uid, so a link planted there would
# make a root write land anywhere (for example /entrypoint.sh at the next boot). Root never
# writes into agent paths: these steps run as agent, where a planted link gains nothing.
as_agent() { su -s /bin/bash agent -c "$1"; }

# --- Decrypt secrets ---
SECRETS_FILE=/run/secrets/agent-box.secrets.yaml
AGE_KEY_FILE=/run/secrets/age.key
if [[ -f "$SECRETS_FILE" && -f "$AGE_KEY_FILE" ]]; then
    log "Decrypting secrets..."
    # Load secrets from dotenv output without eval (security hardening #338)
    # sops dotenv emits raw KEY=VALUE (no quotes, no escaping)
    # Use temp file to preserve sops exit code (process substitution doesn't propagate it)
    SOPS_TEMP=$(mktemp)
    # shellcheck disable=SC2064
    trap "rm -f '$SOPS_TEMP'" EXIT
    if ! SOPS_AGE_KEY_FILE="$AGE_KEY_FILE" sops --config /dev/null --output-type dotenv -d "$SECRETS_FILE" > "$SOPS_TEMP"; then
        log "ERROR: SOPS decryption failed"
        exit 1
    fi
    while IFS='=' read -r _sk _sv; do
      # skip blank lines and sops comment lines
      [ -z "$_sk" ] && continue
      case "$_sk" in \#*) continue ;; esac
      # only accept valid shell identifier keys
      [[ "$_sk" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      # raw literal assignment (no eval, no quote stripping)
      export "$_sk=$_sv"
    done < "$SOPS_TEMP"
    rm -f "$SOPS_TEMP"
    {
        echo "export ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'"
        echo "export AGENT_DISCORD_WEBHOOK='${AGENT_DISCORD_WEBHOOK:-}'"
        echo "export DISCORD_WEBHOOK='${AGENT_DISCORD_WEBHOOK:-}'"  # alias for notify.sh
        echo "export AGENT_GITHUB_TOKEN='${AGENT_GITHUB_TOKEN:-}'"
        echo "export GITHUB_TOKEN='${AGENT_GITHUB_TOKEN:-}'"
        echo "export CLAUDE_API_KEY='${ANTHROPIC_API_KEY:-}'"
        echo "export CLAUDE_DIR='/home/agent/.claude'"
        echo "export LANG=en_US.UTF-8"
        echo "export LC_ALL=en_US.UTF-8"
    } > /etc/profile.d/agent-env.sh
    # Root login shells source /etc/profile.d too, so the agent must not be able to edit it.
    chown root:agent /etc/profile.d/agent-env.sh
    chmod 640 /etc/profile.d/agent-env.sh
    log "Secrets loaded."
else
    log "WARNING: Secrets file not found."
fi

# --- Git + gh config ---
as_agent 'git config --global user.name agent-box &&
    git config --global user.email lucas.diassantana@gmail.com &&
    git config --global init.defaultBranch main'
if [[ -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
    # gh is the single token holder; git asks gh for credentials.
    rm -f /home/agent/.git-credentials
    echo "$AGENT_GITHUB_TOKEN" | su -c \
        "gh auth login --with-token --hostname github.com" agent 2>/dev/null || true
    su -c "gh auth setup-git --hostname github.com" agent || log "WARN: gh auth setup-git failed"
    log "gh CLI authenticated."
fi

# --- Bootstrap claude-env (first run or update) ---
CLAUDE_ENV_DIR="/home/agent/.claude-env"
if [[ -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
    if [[ ! -d "$CLAUDE_ENV_DIR/.git" ]]; then
        log "Cloning claude-env..."
        su -c "git clone https://github.com/LucasSantana-Dev/claude-env.git $CLAUDE_ENV_DIR 2>&1" agent \
            || log "WARN: claude-env clone failed (token access or network) — continuing without it"
    else
        log "Pulling claude-env updates..."
        su -c "cd $CLAUDE_ENV_DIR && git remote set-url origin https://github.com/LucasSantana-Dev/claude-env.git && git pull --ff-only 2>&1 || true" agent
    fi
    if [[ -f "$CLAUDE_ENV_DIR/bin/sync" ]]; then
        log "Syncing claude environment..."
        su -c "HOME=/home/agent CLAUDE_DIR=/home/agent/.claude $CLAUDE_ENV_DIR/bin/sync pull 2>&1 || true" agent
    fi
fi

# --- Agent config (runs as agent; see as_agent) ---
# Overrides are security-critical and must run after the claude-env sync.
as_agent 'bash -s' <<'AGENT'
set -euo pipefail
umask 022
log() { echo "[agent-box] $*"; }
C=/opt/agent-config
cd /home/agent
# install replaces the destination file instead of writing through it.
install -D -m 644 "$C/settings.json" .claude/settings.json
install -D -m 644 "$C/mcp.json"      .claude/mcp.json

# .claude.json (OAuth session) lives outside the volume: back it up there, or restore it.
# Rotates claude-json-backup.json (latest), .1 (prev), .2 (oldest).
J=.claude.json B=.claude/claude-json-backup.json
if [[ -f $J && $(wc -c < $J) -gt 100 ]]; then
    [[ -f $B.1 ]] && install -m 600 "$B.1" "$B.2"
    [[ -f $B ]] && install -m 600 "$B" "$B.1"
    install -m 600 "$J" "$B"
    log ".claude.json backed up (rotated)."
else
    for b in "$B" "$B.1" "$B.2"; do
        if [[ -f $b && $(wc -c < "$b") -gt 100 ]]; then
            install -m 600 "$b" "$J"
            log "Restored .claude.json from ${b##*/}."
            break
        fi
    done
fi

for h in protect-homelab secret-write-guard tag-deploy-guard bash-secret-guard; do
    install -D -m 755 "$C/hooks/$h.sh" ".claude/hooks/$h.sh"
done
log "Guardrail hooks installed."
install -D -m 644 "$C/CLAUDE.md" .claude/CLAUDE.md

# Codex: config and MCP are always overwritten; OAuth auth.json in the volume is kept.
install -D -m 644 "$C/codex-config.toml" .codex/config.toml
install -D -m 644 "$C/codex-mcp.json"    .codex/mcp.json
install -D -m 644 "$C/codex-agents.md"   .codex/AGENTS.md
log "Codex config installed."
install -D -m 644 "$C/opencode.jsonc" .config/opencode/opencode.jsonc

install -d -m 700 .ssh
install -m 600 "$C/authorized_keys" .ssh/authorized_keys
AGENT

# --- Discord channel (official plugin; values from SOPS, never in agent-env.sh) ---
# The owner ID file is root-owned so the agent uid cannot change who may talk to the
# channel; access.json is re-rendered from it on every boot (written as agent).
install -d -m 755 /etc/agent-box
as_agent 'install -d -m 700 ~/.claude/channels ~/.claude/channels/discord &&
    rm -f ~/.claude/channels/discord/.env ~/.claude/channels/discord/access.json'
if [[ -n "${DISCORD_BOT_TOKEN:-}" ]]; then
    printf 'DISCORD_BOT_TOKEN=%s\n' "$DISCORD_BOT_TOKEN" \
        | as_agent 'umask 077; cat > ~/.claude/channels/discord/.env'
fi
if [[ "${DISCORD_OWNER_ID:-}" =~ ^[0-9]{15,22}$ ]]; then
    printf '%s\n' "$DISCORD_OWNER_ID" > /etc/agent-box/discord-owner-id
    chmod 644 /etc/agent-box/discord-owner-id
    printf '{"dmPolicy": "allowlist", "allowFrom": ["%s"], "groups": {}}\n' "$DISCORD_OWNER_ID" \
        | as_agent 'umask 077; cat > ~/.claude/channels/discord/access.json'
else
    rm -f /etc/agent-box/discord-owner-id
fi
# Nothing started below needs the token in its environment; the plugin reads .env.
unset DISCORD_BOT_TOKEN
su -s /bin/bash agent -c /opt/agent-config/discord-channel.sh &
log "Discord channel supervisor started."

# --- Clone working repos on first run ---
clone_repo() {
    local repo="$1" dir="$2"
    if [[ ! -d "/workspace/$dir/.git" && -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
        log "Cloning $repo..."
        su -c "git clone https://github.com/${repo}.git /workspace/$dir 2>&1" agent \
            || log "WARN: $repo clone failed (token access or network) — continuing without it"
    elif [[ -d "/workspace/$dir/.git" ]]; then
        # Auth comes from the credential helper; a token baked into the remote
        # URL would outlive PAT rotation.
        su -c "git -C /workspace/$dir remote set-url origin https://github.com/${repo}.git" agent || true
    fi
}
clone_repo "LucasSantana-Dev/Lucky"     "Lucky"
clone_repo "LucasSantana-Dev/homelab"   "homelab"
clone_repo "LucasSantana-Dev/cojam"     "cojam"

# --- Fix Docker socket GID ---
if [[ -S /var/run/docker.sock ]]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
    groupmod -g "$DOCKER_GID" docker 2>/dev/null || true
    log "Docker socket GID: $DOCKER_GID"
fi

# --- WUD classify HTTP endpoint (port 8080) ---
# n8n calls POST /wud-classify with WUD payload; hermes returns classification JSON.
cat > /tmp/wud-server.py << 'PYEOF'
import http.server, json, subprocess

CLASSIFY_CMD = [
    'su', '-s', '/bin/bash', 'agent', '-c',
    'source /etc/profile.d/agent-env.sh 2>/dev/null; exec bash /workspace/homelab/scripts/agent-tasks/hermes-wud-classify.sh'
]
FALLBACK = json.dumps({'safe_to_schedule': True, 'urgency': 'low', 'reason': 'hermes unavailable'}).encode()
MAX_BODY = 64 * 1024  # WUD payloads are ~1-2KB; cap to avoid resource exhaustion (#310)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        ok = self.path == '/healthz'
        self.send_response(200 if ok else 404)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        if ok:
            self.wfile.write(b'ok')
    def do_POST(self):
        if self.path != '/wud-classify':
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
        except (TypeError, ValueError):
            length = -1
        if length < 0 or length > MAX_BODY:
            self.send_response(413)
            self.end_headers()
            return
        body = self.rfile.read(length)
        try:
            r = subprocess.run(CLASSIFY_CMD, input=body, capture_output=True, timeout=120)
            out = r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else FALLBACK
        except Exception:
            out = FALLBACK
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(out)

http.server.HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
PYEOF
python3 /tmp/wud-server.py &
log "WUD classify endpoint started on :8080"

# --- Start SSH ---
log "Starting SSH daemon..."
exec /usr/sbin/sshd -D -e

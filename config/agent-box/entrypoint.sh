#!/bin/bash
set -euo pipefail
export LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

log() { echo "[agent-box] $*"; }

# --- Decrypt secrets ---
SECRETS_FILE=/run/secrets/agent-box.secrets.yaml
AGE_KEY_FILE=/run/secrets/age.key
if [[ -f "$SECRETS_FILE" && -f "$AGE_KEY_FILE" ]]; then
    log "Decrypting secrets..."
    eval "$(SOPS_AGE_KEY_FILE=$AGE_KEY_FILE sops --config /dev/null --output-type dotenv -d "$SECRETS_FILE")"
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
    chmod 644 /etc/profile.d/agent-env.sh
    log "Secrets loaded."
else
    log "WARNING: Secrets file not found."
fi

# --- Git + gh config ---
git config --global user.name "agent-box"
git config --global user.email "lucas.diassantana@gmail.com"
git config --global init.defaultBranch main
if [[ -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
    git config --global credential.helper store
    printf 'https://x-access-token:%s@github.com\n' "$AGENT_GITHUB_TOKEN" \
        > /home/agent/.git-credentials
    chmod 600 /home/agent/.git-credentials
    chown agent:agent /home/agent/.git-credentials
    echo "$AGENT_GITHUB_TOKEN" | su -c \
        "gh auth login --with-token --hostname github.com" agent 2>/dev/null || true
    log "gh CLI authenticated."
fi

# --- Bootstrap claude-env (first run or update) ---
CLAUDE_ENV_DIR="/home/agent/.claude-env"
if [[ -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
    if [[ ! -d "$CLAUDE_ENV_DIR/.git" ]]; then
        log "Cloning claude-env..."
        su -c "git clone https://x-access-token:${AGENT_GITHUB_TOKEN}@github.com/LucasSantana-Dev/claude-env.git $CLAUDE_ENV_DIR 2>&1" agent
    else
        log "Pulling claude-env updates..."
        su -c "cd $CLAUDE_ENV_DIR && git pull --ff-only 2>&1 || true" agent
    fi
    if [[ -f "$CLAUDE_ENV_DIR/bin/sync" ]]; then
        log "Syncing claude environment..."
        su -c "HOME=/home/agent CLAUDE_DIR=/home/agent/.claude $CLAUDE_ENV_DIR/bin/sync pull 2>&1 || true" agent
    fi
fi

# --- Apply server-specific overrides (guardrails + MCP config) ---
# These overwrite what sync pulled — security-critical, must run after sync
mkdir -p /home/agent/.claude
cp /opt/agent-config/settings.json /home/agent/.claude/settings.json
cp /opt/agent-config/mcp.json      /home/agent/.claude/mcp.json
chown -R agent:agent /home/agent/.claude/settings.json \
                      /home/agent/.claude/mcp.json


# --- Preserve/restore claude OAuth session (.claude.json lives outside named volume) ---
# Rotates backups: claude-json-backup.json (latest) .1 (prev) .2 (oldest)
CLAUDE_JSON=/home/agent/.claude.json
CLAUDE_JSON_BACKUP=/home/agent/.claude/claude-json-backup.json

if [[ -f "$CLAUDE_JSON" && $(wc -c < "$CLAUDE_JSON") -gt 100 ]]; then
    # Rotate: .1 → .2, backup → .1, then write new backup
    [[ -f "${CLAUDE_JSON_BACKUP}.1" ]] && cp "${CLAUDE_JSON_BACKUP}.1" "${CLAUDE_JSON_BACKUP}.2"
    [[ -f "$CLAUDE_JSON_BACKUP" ]] && cp "$CLAUDE_JSON_BACKUP" "${CLAUDE_JSON_BACKUP}.1"
    cp "$CLAUDE_JSON" "$CLAUDE_JSON_BACKUP"
    chown agent:agent "$CLAUDE_JSON_BACKUP" "${CLAUDE_JSON_BACKUP}".* 2>/dev/null || true
    log ".claude.json backed up (rotated)."
else
    # Restore from most recent valid backup
    for BACKUP in "$CLAUDE_JSON_BACKUP" "${CLAUDE_JSON_BACKUP}.1" "${CLAUDE_JSON_BACKUP}.2"; do
        if [[ -f "$BACKUP" && $(wc -c < "$BACKUP") -gt 100 ]]; then
            cp "$BACKUP" "$CLAUDE_JSON"
            chown agent:agent "$CLAUDE_JSON"
            log "Restored .claude.json from ${BACKUP##*/}."
            break
        fi
    done
fi

# --- Install guardrail hooks ---
mkdir -p /home/agent/.claude/hooks
cp /opt/agent-config/hooks/protect-homelab.sh    /home/agent/.claude/hooks/protect-homelab.sh
cp /opt/agent-config/hooks/secret-write-guard.sh /home/agent/.claude/hooks/secret-write-guard.sh
cp /opt/agent-config/hooks/tag-deploy-guard.sh   /home/agent/.claude/hooks/tag-deploy-guard.sh
chmod +x /home/agent/.claude/hooks/protect-homelab.sh          /home/agent/.claude/hooks/secret-write-guard.sh          /home/agent/.claude/hooks/tag-deploy-guard.sh
chown agent:agent /home/agent/.claude/hooks/protect-homelab.sh                   /home/agent/.claude/hooks/secret-write-guard.sh                   /home/agent/.claude/hooks/tag-deploy-guard.sh
log "Guardrail hooks installed."
cp /opt/agent-config/CLAUDE.md /home/agent/.claude/CLAUDE.md
chown agent:agent /home/agent/.claude/CLAUDE.md

# --- Codex CLI setup ---
mkdir -p /home/agent/.codex
# Always overwrite config/mcp (OAuth auth.json in volume is preserved)
cp /opt/agent-config/codex-config.toml /home/agent/.codex/config.toml
cp /opt/agent-config/codex-mcp.json    /home/agent/.codex/mcp.json
cp /opt/agent-config/codex-agents.md   /home/agent/.codex/AGENTS.md
chown -R agent:agent /home/agent/.codex
log "Codex config installed."
# --- Apply opencode config ---
mkdir -p /home/agent/.config/opencode
cp /opt/agent-config/opencode.jsonc /home/agent/.config/opencode/opencode.jsonc
chown -R agent:agent /home/agent/.config/opencode

# --- SSH authorized keys ---
mkdir -p /home/agent/.ssh && chmod 700 /home/agent/.ssh
cp /opt/agent-config/authorized_keys /home/agent/.ssh/authorized_keys
chmod 600 /home/agent/.ssh/authorized_keys
chown -R agent:agent /home/agent/.ssh

# --- Clone working repos on first run ---
clone_repo() {
    local repo="$1" dir="$2"
    if [[ ! -d "/workspace/$dir/.git" && -n "${AGENT_GITHUB_TOKEN:-}" ]]; then
        log "Cloning $repo..."
        su -c "git clone https://x-access-token:${AGENT_GITHUB_TOKEN}@github.com/${repo}.git /workspace/$dir 2>&1" agent
    fi
}
clone_repo "LucasSantana-Dev/Lucky"     "Lucky"
clone_repo "LucasSantana-Dev/homelab"   "homelab"
clone_repo "LucasSantana-Dev/Craftvaria" "Craftvaria"

# --- Fix Docker socket GID ---
if [[ -S /var/run/docker.sock ]]; then
    DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
    groupmod -g "$DOCKER_GID" docker 2>/dev/null || true
    log "Docker socket GID: $DOCKER_GID"
fi

# --- Start SSH ---
log "Starting SSH daemon..."
exec /usr/sbin/sshd -D -e

#!/usr/bin/env bash
# Shared helpers for agent-pr-gate.sh and agent-worker.sh (the autonomous dev loop).
# Source after common.sh. Policy and thresholds: config/agent-box/agent-gate.json.

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE_PY="$AGENT_DIR/agent_gate.py"
AGENT_REPOS="${AGENT_REPOS:-LucasSantana-Dev/Lucky}"
AGENT_DRY_RUN="${AGENT_DRY_RUN:-0}"
AGENT_MAX_RUNS_PER_DAY="${AGENT_MAX_RUNS_PER_DAY:-6}"
AGENT_STATE_DIR="${AGENT_STATE_DIR:-/home/luk-server/agent-state}"

cfg() { python3 "$GATE_PY" get --repo "$1" --key "$2"; }

# Pause switch lives inside agent-box so the Discord channel session can flip it.
# Fail closed: anything but an explicit "running" (ssh down, etc.) counts as paused.
agent_paused() {
    [[ "$(run_on_agent "test -e ~/agent-paused && echo paused || echo running")" != "running" ]]
}

# Run a command on agent-box, or only print it when AGENT_DRY_RUN=1.
act() {
    if [[ "$AGENT_DRY_RUN" == "1" ]]; then
        echo "DRY-RUN: $1"
    else
        run_on_agent "$1"
    fi
}

# Best-effort write (labels, comments): a failure is logged, never aborts the run.
try_act() { act "$1" || echo "WARN: failed: $1"; }

notify() {
    if [[ "$AGENT_DRY_RUN" == "1" ]]; then
        echo "DRY-RUN notify: $*"
    else
        $NOTIFY "$@" || true
    fi
}

# Daily claude -p budget shared by worker and gate autofix. Returns 1 when spent.
# Serialized by the flock both scripts take.
budget_take() {
    mkdir -p "$AGENT_STATE_DIR"
    local f used
    f="$AGENT_STATE_DIR/runs-$(date +%Y%m%d)"
    used=$(cat "$f" 2>/dev/null || echo 0)
    if (( used >= AGENT_MAX_RUNS_PER_DAY )); then
        echo "daily budget spent ($used/$AGENT_MAX_RUNS_PER_DAY)"
        return 1
    fi
    [[ "$AGENT_DRY_RUN" == "1" ]] || echo $((used + 1)) > "$f"
}

# Headless claude on the official binary with the Max OAuth login: every API or
# alternate-provider env var is dropped so a run never bills the API by accident.
claude_cmd() {
    local workdir="$1" prompt="$2" qprompt
    printf -v qprompt '%q' "$prompt"
    echo "cd $workdir && env -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY -u ANTHROPIC_AUTH_TOKEN" \
        "-u ANTHROPIC_BASE_URL -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX" \
        "timeout 45m claude -p --max-turns 60 $qprompt"
}

workdir_clean() { [[ -z "$(run_on_agent "cd $1 && git status --porcelain")" ]]; }

# Open agent PRs: labelled `agent` OR on an agent/ branch (the label is set by the
# model and may be missing). JSON array.
open_agent_prs() {
    run_on_agent "gh pr list --repo $1 --state open --limit 100 --json number,headRefName,closingIssuesReferences,labels" \
        | jq '[.[] | select((.headRefName | startswith("agent/")) or any(.labels[]; .name == "agent"))]'
}

ensure_labels() {
    local repo="$1" have
    have=$(run_on_agent "gh label list --repo $repo --limit 200 --json name -q '.[].name'") || return 0
    for l in agent agent-failed needs-human needs-split agent-fix-1 agent-fix-2; do
        grep -qx "$l" <<<"$have" || try_act "gh label create $l --repo $repo --color BFD4F2"
    done
}

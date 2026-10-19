#!/bin/bash
# pr-automerge: the only way an agent-box session merges a PR. Runs on agent-box as `agent`
# (image copy: /usr/local/bin/pr-automerge, root-owned, with agent_gate.py and agent-gate.json).
#
#   pr-automerge <owner/repo> <pr>   check the PR (agent_gate.py merge-check), then queue a
#                                    squash auto-merge pinned to the checked head commit
#   pr-automerge --sweep             re-check every PR this tool queued; turn auto-merge off on
#                                    the ones that no longer pass (run by agent-pr-gate.sh)
#
# A queued merge fires when the base ruleset is satisfied (required checks green, threads
# resolved where the ruleset asks for it), without a new check. GitHub keeps it queued across
# pushes, so automerge-push-guard.sh turns it off before every push from the agent, and the
# agent runs pr-automerge again after the push; --sweep catches what is left. Never --admin.
# Exit: 0 queued or nothing to do, 1 refused or error, 3 (--sweep) a PR was turned off or
# could not be checked (the output says which).
set -euo pipefail

SELF=$(/usr/bin/readlink -f "$0")  # absolute: PATH is the caller's until reset below
HERE=${SELF%/*}
GATE_PY="$HERE/agent_gate.py"
if [[ "$HERE" == /opt/agent-config ]]; then
    # Image copy: ignore the caller's environment, so a session cannot point the check at
    # its own config, registry or binaries.
    export PATH=/usr/local/bin:/usr/bin:/bin
    CONFIG=/opt/agent-config/agent-gate.json
    STATE=/home/agent/.local/state/pr-automerge
else
    CONFIG="${AGENT_GATE_CONFIG:-$HERE/../../config/agent-box/agent-gate.json}"
    STATE="${PR_AUTOMERGE_STATE:-$HOME/.local/state/pr-automerge}"
fi
THREADS_QUERY='query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { pullRequest(number: $number) { reviewThreads(first: 100) { pageInfo { hasNextPage } nodes { id isResolved comments(first: 50) { totalCount nodes { author { __typename login } } } } } } } }'
FIELDS=number,state,isDraft,isCrossRepository,baseRefName,headRefOid,author,commits,files,changedFiles,comments,reviews,autoMergeRequest,closingIssuesReferences

say() { echo "pr-automerge: $*"; }
die() { echo "pr-automerge: $*" >&2; exit 1; }

entry() { echo "$STATE/${1//\//_}-$2"; }  # repo pr -> registry file

# {"pr": PR JSON with review threads, "issues": [issues it closes]}, or nothing and status 1.
load() {  # repo pr
    local pr threads issues="[]" issue url
    pr=$(gh pr view "$2" -R "$1" --json "$FIELDS") || return 1
    threads=$(gh api graphql -f query="$THREADS_QUERY" -F owner="${1%/*}" -F name="${1#*/}" \
        -F number="$2" --jq .data.repository.pullRequest.reviewThreads) || return 1
    jq -e '.nodes | type == "array"' <<<"$threads" >/dev/null 2>&1 || return 1
    for url in $(jq -r '.closingIssuesReferences[]?.url' <<<"$pr"); do
        issue=$(gh issue view "$url" --json author,comments) || return 1
        issues=$(jq -c --argjson i "$issue" '. + [$i]' <<<"$issues")
    done
    jq -c --argjson t "$threads" --argjson i "$issues" '{pr: (.reviewThreads = $t), issues: $i}' <<<"$pr"
}

# Returns 0 when the PR is (still) fine or gone, 1 when it was refused, turned off or not checked.
handle() {  # mode(queue|sweep) repo pr
    local mode="$1" repo="$2" n="$3" data verdict sha queued
    data=$(load "$repo" "$n") || { say "$repo#$n: could not load the PR, its review threads or its issues"; return 1; }
    queued=$(jq -r '.pr.autoMergeRequest != null' <<<"$data")
    if [[ "$(jq -r .pr.state <<<"$data")" != "OPEN" || ( "$mode" == "sweep" && "$queued" != "true" ) ]]; then
        rm -f "$(entry "$repo" "$n")"
        [[ "$mode" == "sweep" ]] && return 0
        say "$repo#$n: not open"
        return 1
    fi
    verdict=$(python3 -I "$GATE_PY" merge-check --config "$CONFIG" --repo "$repo" <<<"$data") \
        || { say "$repo#$n: gate check failed to run"; return 1; }
    if ! jq -e '.ok == true' <<<"$verdict" >/dev/null; then
        say "$repo#$n: refused: $(jq -r '.reasons | join("; ")' <<<"$verdict")"
        if [[ "$queued" == "true" ]]; then
            if ! gh pr merge "$n" -R "$repo" --disable-auto; then
                # Keep the registry entry: the next sweep tries again.
                say "$repo#$n: could not turn auto-merge off, it is STILL QUEUED"
                return 1
            fi
            say "$repo#$n: auto-merge turned off"
        fi
        rm -f "$(entry "$repo" "$n")"
        return 1
    fi
    [[ "$mode" == "sweep" ]] && return 0
    sha=$(jq -r .pr.headRefOid <<<"$data")
    [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { say "$repo#$n: unexpected head sha"; return 1; }
    if [[ "$queued" != "true" ]]; then
        gh pr merge "$n" -R "$repo" --squash --auto --match-head-commit "$sha" || { say "$repo#$n: gh pr merge failed"; return 1; }
    fi
    mkdir -p "$STATE" && echo "$sha" > "$(entry "$repo" "$n")"
    say "$repo#$n: auto-merge queued on $sha; GitHub merges it when the required checks pass"
}

if [[ "${1:-}" == "--sweep" && $# -eq 1 ]]; then
    rc=0
    shopt -s nullglob
    for f in "$STATE"/*; do
        name=$(basename "$f")
        # Owner names have no underscore, so the first one splits owner from repo.
        [[ "$name" =~ ^([A-Za-z0-9-]+)_([A-Za-z0-9_.-]+)-([0-9]+)$ ]] || continue
        handle sweep "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}" || rc=3
    done
    exit "$rc"
fi

[[ $# -eq 2 ]] || die "usage: pr-automerge <owner/repo> <pr-number> | pr-automerge --sweep"
[[ "$1" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$ ]] || die "bad repo: $1"
[[ "$2" =~ ^[0-9]+$ ]] || die "bad PR number: $2"
handle queue "$1" "$2"

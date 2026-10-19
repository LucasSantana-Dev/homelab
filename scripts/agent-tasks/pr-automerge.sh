#!/bin/bash
# pr-automerge: the only way an agent-box session merges a PR. Runs on agent-box as `agent`
# (image copy: /usr/local/bin/pr-automerge, root-owned, with agent_gate.py and agent-gate.json).
#
#   pr-automerge <owner/repo> <pr>   check the PR (agent_gate.py merge-check), then queue a
#                                    squash auto-merge pinned to the checked head commit
#   pr-automerge <owner/repo> <pr> --threads
#                                    print the open review threads as JSON (id, bot_only, comments)
#   pr-automerge <owner/repo> <pr> --replies <file>
#                                    post the session's replies to bot-only threads as the owner,
#                                    resolve the ones fixed in a pushed commit, then queue as above
#   pr-automerge --sweep             re-check every PR this tool queued; turn auto-merge off on
#                                    the ones that no longer pass (run by agent-pr-gate.sh)
#
# A queued merge fires when the base ruleset is satisfied (required checks green, threads
# resolved where the ruleset asks for it), without a new check. GitHub keeps it queued across
# pushes, so automerge-push-guard.sh turns it off before every push from the agent, and the
# agent runs pr-automerge again after the push; --sweep catches what is left. Never --admin.
# Exit: 0 queued or nothing to do, 1 refused or error, 3 (--sweep) a PR was turned off or
# could not be checked (the output says which).
# The session may not call gh api (a GraphQL mutation can merge), so thread replies go through
# --replies: agent_gate.py thread-replies decides what is posted; humans' threads are never touched.
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
THREADS_QUERY='query($owner: String!, $name: String!, $number: Int!) { repository(owner: $owner, name: $name) { pullRequest(number: $number) { reviewThreads(first: 100) { pageInfo { hasNextPage } nodes { id isResolved path line comments(first: 50) { totalCount nodes { author { __typename login } body originalCommit { oid } } } } } } } }'
REPLY_MUTATION='mutation($id: ID!, $body: String!) { addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $id, body: $body}) { comment { id } } }'
RESOLVE_MUTATION='mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { isResolved } } }'
MAX_REPLIES_BYTES=65536
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

# Post the replies agent_gate.py allows. Returns 1 when it refused or could not run.
answer() {  # repo pr file
    local repo="$1" n="$2" file="$3" raw replies data plan actions a id body posted=0 total
    # Read once, so the size cap holds for what is parsed.
    if ! raw=$(head -c $((MAX_REPLIES_BYTES + 1)) -- "$file" 2>/dev/null) \
        || (( $(printf %s "$raw" | wc -c) > MAX_REPLIES_BYTES )) \
        || ! replies=$(jq -cs 'if length == 1 then .[0] else null end' <<<"$raw" 2>/dev/null); then
        say "$repo#$n: replies file missing, over $MAX_REPLIES_BYTES bytes or not JSON"
        return 1
    fi
    data=$(load "$repo" "$n") || { say "$repo#$n: could not load the PR, its review threads or its issues"; return 1; }
    plan=$(jq -c --argjson r "$replies" '. + {replies: $r}' <<<"$data" \
        | python3 -I "$GATE_PY" thread-replies --config "$CONFIG" --repo "$repo") \
        || { say "$repo#$n: the gate check failed to run"; return 1; }
    if ! jq -e '.ok == true' <<<"$plan" >/dev/null; then
        say "$repo#$n: replies refused: $(jq -r '.reasons | join("; ")' <<<"$plan")"
        return 1
    fi
    actions=$(jq -c '.actions[]' <<<"$plan") || { say "$repo#$n: unreadable gate plan"; return 1; }
    total=$(jq '.actions | length' <<<"$plan")
    jq -r '.skipped | to_entries[] | "thread \(.key) skipped: \(.value)"' <<<"$plan" | while IFS= read -r a; do say "$repo#$n: $a"; done
    while IFS= read -r a; do
        [[ -n "$a" ]] || continue
        id=$(jq -r .id <<<"$a")
        body=$(jq -r .reply <<<"$a")
        if ! gh api graphql -f query="$REPLY_MUTATION" -f id="$id" -f body="$body" >/dev/null; then
            say "$repo#$n: reply to thread $id failed, left open"
            continue
        fi
        posted=$((posted + 1))
        if [[ "$(jq -r .resolve <<<"$a")" != "true" ]]; then
            say "$repo#$n: replied to thread $id, left open for the owner"
        elif gh api graphql -f query="$RESOLVE_MUTATION" -f id="$id" >/dev/null; then
            say "$repo#$n: replied to thread $id and resolved it"
        else
            say "$repo#$n: replied to thread $id, could not resolve it"
        fi
    done <<<"$actions"
    say "$repo#$n: $posted of $total replies posted"
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

USAGE="usage: pr-automerge <owner/repo> <pr-number> [--threads | --replies <file>] | pr-automerge --sweep"
[[ $# -eq 2 || ( $# -eq 3 && "$3" == "--threads" ) || ( $# -eq 4 && "$3" == "--replies" ) ]] || die "$USAGE"
[[ "$1" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$ ]] || die "bad repo: $1"
[[ "$2" =~ ^[0-9]+$ ]] || die "bad PR number: $2"
if [[ "${3:-}" == "--threads" ]]; then
    data=$(load "$1" "$2") || die "$1#$2: could not load the PR, its review threads or its issues"
    python3 -I "$GATE_PY" open-threads --config "$CONFIG" --repo "$1" <<<"$data"
    exit
fi
if [[ "${3:-}" == "--replies" ]]; then
    answer "$1" "$2" "$4" || exit 1
fi
handle queue "$1" "$2"

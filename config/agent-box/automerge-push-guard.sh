#!/bin/bash
# automerge-push-guard: PreToolUse(Bash) hook on agent-box. GitHub keeps a queued auto-merge
# through new pushes, so before a `git push` this turns auto-merge off on the open PR of the
# pushed branch; the session runs pr-automerge again after the push (ADR 0042). Blocks the
# push (exit 2) when it cannot tell which PR it is or cannot turn auto-merge off.
set -uo pipefail

input=$(cat)
block() { echo "BLOCK: $* (automerge-push-guard)" >&2; exit 2; }

cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || block "cannot read the hook input"
dir=$(jq -r '.cwd // "."' <<<"$input" 2>/dev/null) || block "cannot read the hook input"

# Pushes look like `git -C <repo> push origin <branch>` here (discord-channel.md).
re='(^|[;&|[:space:]])git[[:space:]]+(-C[[:space:]]+([^[:space:];&|]+)[[:space:]]+)?push([[:space:]]+([^;&|]*))?'
[[ "$cmd" =~ $re ]] || exit 0
[[ -n "${BASH_REMATCH[3]}" ]] && dir=${BASH_REMATCH[3]}
dir=${dir//[\"\']/}
read -ra words <<<"${BASH_REMATCH[5]}"
args=()
for w in "${words[@]}"; do [[ "$w" == -* ]] || args+=("$w"); done
remote=${args[0]:-origin}
branch=${args[1]:-HEAD}
branch=${branch##*:}
branch=${branch#refs/heads/}
if [[ "$branch" == HEAD ]]; then
    branch=$(git -C "$dir" symbolic-ref --short HEAD 2>/dev/null) \
        || block "cannot tell which branch is pushed; use git -C <repo> push origin <branch>"
fi

urls=$(git -C "$dir" remote get-url --push --all "$remote" 2>/dev/null) || block "unknown remote $remote in $dir"
(( $(wc -l <<<"$urls") == 1 )) || block "$remote has more than one push URL; push to a remote with one"
url=$urls
[[ "$url" =~ github\.com[:/]([A-Za-z0-9-]+/[A-Za-z0-9_.-]+)$ ]] || exit 0
repo=${BASH_REMATCH[1]%.git}

prs=$(gh pr list -R "$repo" --head "$branch" --state open --json number,autoMergeRequest \
    --jq '.[] | select(.autoMergeRequest != null) | .number') \
    || block "could not check auto-merge on $repo $branch, retry the push"
for n in $prs; do
    gh pr merge "$n" -R "$repo" --disable-auto >/dev/null \
        || block "could not turn auto-merge off on $repo#$n, retry the push"
    echo "auto-merge turned off on $repo#$n: run pr-automerge $repo $n after the push" >&2
done
exit 0

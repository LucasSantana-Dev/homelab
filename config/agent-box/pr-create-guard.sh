#!/bin/bash
# pr-create-guard: PreToolUse(Bash) hook on agent-box. Before `gh pr create` it checks that the
# PR targets the repo's base from agent-gate.json (homelab: release) and that the branch was cut
# from a freshly fetched origin/<base>: it has commits of its own and does not sit on another
# branch. A stacked branch reds every PR above one bad commit (Lucky #2886-#2890). Blocks
# (exit 2) when a check fails or cannot run. The gate's branch check is the backstop (ADR 0042).
set -uo pipefail

HERE=$(/usr/bin/dirname "$(/usr/bin/readlink -f "$0")")
CONFIG=/opt/agent-config/agent-gate.json  # root-owned image copy
[[ -f "$CONFIG" ]] || CONFIG="$HERE/agent-gate.json"  # repo checkout (tests)

block() { echo "BLOCK: $* (pr-create-guard)" >&2; exit 2; }

input=$(cat)
cmd=$(jq -r '.tool_input.command // empty' <<<"$input" 2>/dev/null) || block "cannot read the hook input"
dir=$(jq -r '.cwd // "."' <<<"$input" 2>/dev/null) || block "cannot read the hook input"
[[ "$cmd" == *gh* ]] || exit 0

# Shell-aware parse (quoted titles and bodies stay one word). Prints one line per gh call that
# opens a PR: "create<TAB>repo<TAB>base<TAB>head<TAB>cd-dir", or "api", or "error".
parsed=$(python3 -I - "$cmd" <<'PY'
import shlex, sys

try:
    lex = shlex.shlex(sys.argv[1], posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    toks = list(lex)
except ValueError:
    print("error" if "pr create" in sys.argv[1] or "pulls" in sys.argv[1] else "")
    sys.exit()

cmds, cur = [], []
for t in toks:
    if t and all(c in ";&|()" for c in t):
        cmds.append(cur)
        cur = []
    else:
        cur.append(t)
cmds.append(cur)

FLAGS = {"-R": "repo", "--repo": "repo", "-B": "base", "--base": "base", "-H": "head", "--head": "head"}
cd = ""
for c in cmds:
    while c and "=" in c[0] and not c[0].startswith("-"):
        c = c[1:]  # VAR=value prefixes
    if not c:
        continue
    if c[0] == "cd" and len(c) > 1:
        cd = c[1]
    if c[0].rsplit("/", 1)[-1] != "gh":
        continue
    args = c[1:]
    if args[:1] == ["api"] and any(a.rstrip("/").endswith("/pulls") for a in args):
        print("api")
    if args[:2] != ["pr", "create"]:
        continue
    got = {"repo": "", "base": "", "head": ""}
    i = 2
    while i < len(args):
        a = args[i]
        name, _, val = a.partition("=")
        if a.startswith("--") and name in FLAGS and _:
            got[FLAGS[name]] = val
        elif a in FLAGS:
            got[FLAGS[a]] = args[i + 1] if i + 1 < len(args) else ""
            i += 1
        elif a[:2] in FLAGS and not a.startswith("--") and len(a) > 2:
            got[FLAGS[a[:2]]] = a[2:].lstrip("=")
        i += 1
    print("\t".join(["create", got["repo"], got["base"], got["head"], cd]))
PY
) || block "cannot parse the command"
[[ -n "$parsed" ]] || exit 0
! grep -qx error <<<"$parsed" || block "cannot parse the command: check its quoting"
! grep -qx api <<<"$parsed" || block "open PRs with gh pr create -R <repo> --base <base>, not gh api"
(( $(grep -c '^create' <<<"$parsed") == 1 )) || block "open one PR per command"
IFS=$'\t' read -r _ repo base head cd_dir <<<"$parsed"
[[ -n "$cd_dir" ]] && dir=$cd_dir

repo_of() {  # dir -> owner/repo of its origin, or status 1
    local url
    url=$(git -C "$1" remote get-url origin 2>/dev/null) || return 1
    [[ "$url" =~ github\.com[:/]([A-Za-z0-9-]+/[A-Za-z0-9_.-]+)$ ]] || return 1
    echo "${BASH_REMATCH[1]%.git}"
}
conf() {  # repo field -> value from the repo's entry (GitHub names ignore case)
    jq -r --arg r "$1" --arg f "$2" \
        '.repos | to_entries[] | select((.key | ascii_downcase) == ($r | ascii_downcase)) | .value[$f] // empty' \
        "$CONFIG"
}
same_repo() { [[ "$(tr '[:upper:]' '[:lower:]' <<<"$1")" == "$(tr '[:upper:]' '[:lower:]' <<<"$2")" ]]; }

[[ -n "$repo" ]] || repo=$(repo_of "$dir") || block "cannot tell the repo: pass -R <owner/repo>"
want=$(conf "$repo" base) || block "cannot read $CONFIG"
[[ -n "$want" ]] || exit 0  # not a repo the agents work on
[[ "$base" == "$want" ]] || block "$repo PRs target $want: pass --base $want"

# The session's cwd when it is a checkout of this repo (a worktree too), else the repo workdir.
if ! same_repo "$(repo_of "$dir")" "$repo"; then
    dir=$(conf "$repo" workdir)
fi
if [[ -z "$dir" ]] || ! git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
    block "no checkout of $repo to check the branch in"
fi
head=${head##*:}  # owner:branch
[[ -n "$head" ]] || head=$(git -C "$dir" symbolic-ref --short HEAD 2>/dev/null) \
    || block "cannot tell the head branch: pass --head <branch>"
[[ "$head" =~ ^[A-Za-z0-9._/-]+$ && "$head" != -* ]] || block "bad branch name: $head"

git -C "$dir" fetch -q origin "$want" || block "git fetch origin $want failed, retry"
# gh opens the PR from the pushed branch; the local one counts only when it is not pushed.
if git -C "$dir" fetch -q origin "$head" 2>/dev/null; then
    ref=refs/remotes/origin/$head
else
    git -C "$dir" ls-remote --exit-code --heads origin "$head" >/dev/null 2>&1
    [[ $? -eq 2 ]] || block "git fetch origin $head failed, retry"
    ref=refs/heads/$head
fi
tip=$(git -C "$dir" rev-parse -q --verify "$ref^{commit}") || block "branch $head not found in $dir"

own=$(git -C "$dir" rev-list "origin/$want..$tip") || block "git rev-list failed"
[[ -n "$own" ]] || block "$head has no commits on top of origin/$want"
oldest=$(tail -n 1 <<<"$own")

# Another branch that holds part of this range and is not a descendant of this branch is the
# branch this one was cut from (or an old copy of it): the PR would carry its commits too.
stacked=()
while read -r other; do
    case "$other" in "" | "$head" | "origin/$head" | origin | origin/HEAD) continue ;; esac
    mb=$(git -C "$dir" merge-base "$other" "$tip") || block "git merge-base failed"
    [[ "$mb" == "$tip" ]] || stacked+=("$other")
done < <(git -C "$dir" for-each-ref --format='%(refname:short)' --contains "$oldest" \
    refs/heads refs/remotes/origin)
if (( ${#stacked[@]} )); then
    block "$head shares commits with ${stacked[*]}: it must hold only its own commits on" \
        "origin/$want. Run git -C $dir fetch origin, git -C $dir switch -c <new-branch>" \
        "origin/$want, cherry-pick only this change's commits, push and open the PR from it"
fi
exit 0

#!/bin/bash
# preflight-pull.sh
#
# Run before `git pull --ff-only` in `make pull-deploy`. On 2026-09-27, three
# manual deploys had `git pull` stop halfway: some tracked dirs (observability/,
# tailscale/, a few files) were root-owned, git hit "unable to unlink old ...
# Permission denied" partway through, and HEAD stayed on the old commit while
# ~22 files were already overwritten with the new content. This script catches
# that class of failure *before* the pull starts, so the tree is never left in
# a half-updated state.
#
# Fails (and never runs sudo itself) if:
#   - any directory containing a tracked file (including the repo root, `.`,
#     for top-level tracked files) is not writable by the current user. A
#     pull replacing a file is an unlink+create in its *parent directory*,
#     which is the actual permission git needs, so a read-only file inside a
#     writable directory is not a real blocker and is intentionally not
#     checked (git unlinks and recreates it).
#   - the working tree has local modifications to tracked files (a dirty pull
#     is a separate, already-handled case (see ADR-0036), but we check it
#     here too since it also blocks a clean --ff-only pull)
set -uo pipefail

# Operates on the current working directory's repo (Make always runs recipe
# commands from the Makefile's directory, i.e. the repo root; tests point
# this at a temporary repo the same way).
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ preflight-pull: not inside a git repository ($(pwd))" >&2
    exit 1
fi

errors=0
current_user="$(id -un)"
current_group="$(id -gn)"

echo "🔎 preflight-pull: checking tracked-directory ownership and working-tree state..."

# 1. Local modifications to tracked files block a clean --ff-only pull anyway,
#    but surface them here with the same class of fix-it guidance.
dirty_files="$(git diff --name-only HEAD -- 2>/dev/null || true)"
if [[ -n "$dirty_files" ]]; then
    echo "❌ Working tree has local modifications to tracked files:"
    echo "$dirty_files" | sed 's/^/   /'
    echo "   Commit or discard them before pulling."
    errors=$((errors + 1))
fi

# Portable owner lookup: GNU stat first (Linux hosts), BSD stat as fallback
# (macOS dev machines).
owner_of() {
    stat -c '%U' "$1" 2>/dev/null || stat -f '%Su' "$1" 2>/dev/null
}

# 2. Every directory that directly contains a tracked file (the repo root
#    included, for top-level tracked files) must be writable by the current
#    user.
unwritable_dirs=()
declare -A seen_dirs=()

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    dir="$(dirname "$f")"
    if [[ -z "${seen_dirs[$dir]:-}" ]]; then
        seen_dirs["$dir"]=1
        if [[ -e "$dir" && ! -w "$dir" ]]; then
            unwritable_dirs+=("$dir")
        fi
    fi
done < <(git ls-files)

if [[ ${#unwritable_dirs[@]} -gt 0 ]]; then
    echo "❌ Found tracked directories not writable by ${current_user}:"
    chown_paths=()
    chmod_paths=()
    for d in "${unwritable_dirs[@]}"; do
        owner="$(owner_of "$d")"
        echo "   dir: $d (owner: ${owner:-unknown})"
        if [[ "$owner" == "$current_user" ]]; then
            chmod_paths+=("$d")
        else
            chown_paths+=("$d")
        fi
    done
    echo ""
    if [[ ${#chown_paths[@]} -gt 0 ]]; then
        echo "   Fix (owned by someone else; this script never runs sudo itself):"
        # Non-recursive: only the directory entry's own permissions gate
        # unlink+create inside it. -R would also rewrite ownership/mode on
        # every unrelated descendant file, which is not what's broken here.
        printf '   sudo chown %s:%s' "$current_user" "$current_group"
        for p in "${chown_paths[@]}"; do
            printf ' %q' "$p"
        done
        printf '\n'
    fi
    if [[ ${#chmod_paths[@]} -gt 0 ]]; then
        echo "   Fix (already owned by you, just missing the write bit):"
        printf '   chmod u+w'
        for p in "${chmod_paths[@]}"; do
            printf ' %q' "$p"
        done
        printf '\n'
    fi
    errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
    echo ""
    echo "❌ preflight-pull FAILED: fix the above, then re-run \`git pull\` / \`make pull-deploy\`."
    exit 1
fi

echo "✅ preflight-pull: tracked directories clean and writable."
exit 0

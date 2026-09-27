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
#   - any tracked file is not writable by the current user
#   - any directory directly containing a tracked file is not writable
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

echo "🔎 preflight-pull: checking tracked-file ownership and working-tree state..."

# 1. Local modifications to tracked files block a clean --ff-only pull anyway,
#    but surface them here with the same class of fix-it guidance.
dirty_files="$(git diff --name-only HEAD -- 2>/dev/null || true)"
if [[ -n "$dirty_files" ]]; then
    echo "❌ Working tree has local modifications to tracked files:"
    echo "$dirty_files" | sed 's/^/   /'
    echo "   Commit or discard them before pulling."
    errors=$((errors + 1))
fi

# 2. Every tracked file, and the directory that directly contains it, must be
#    writable by the current user. `git pull` replacing a file is an
#    unlink+create in its parent directory, so a root-owned directory (not
#    just a root-owned file) is enough to abort the pull halfway through.
unwritable_files=()
unwritable_dirs=()
declare -A seen_dirs=()

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ -e "$f" && ! -w "$f" ]]; then
        unwritable_files+=("$f")
    fi
    dir="$(dirname "$f")"
    if [[ "$dir" != "." && -e "$dir" && ! -w "$dir" && -z "${seen_dirs[$dir]:-}" ]]; then
        seen_dirs["$dir"]=1
        unwritable_dirs+=("$dir")
    fi
done < <(git ls-files)

if [[ ${#unwritable_files[@]} -gt 0 || ${#unwritable_dirs[@]} -gt 0 ]]; then
    echo "❌ Found tracked paths not writable by ${current_user}:"
    fix_paths=()
    for f in "${unwritable_files[@]}"; do
        echo "   file: $f"
        fix_paths+=("$f")
    done
    for d in "${unwritable_dirs[@]}"; do
        echo "   dir:  $d"
        fix_paths+=("$d")
    done
    echo ""
    echo "   Fix on the host (this script never runs sudo itself):"
    printf '   sudo chown -R %s:%s' "$current_user" "$current_group"
    for p in "${fix_paths[@]}"; do
        printf ' %q' "$p"
    done
    printf '\n'
    errors=$((errors + 1))
fi

if [[ $errors -gt 0 ]]; then
    echo ""
    echo "❌ preflight-pull FAILED: fix the above, then re-run \`git pull\` / \`make pull-deploy\`."
    exit 1
fi

echo "✅ preflight-pull: tracked files clean and writable."
exit 0

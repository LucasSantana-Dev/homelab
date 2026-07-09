#!/usr/bin/env bash
# install-liveness-crontab.sh — rewrite the user crontab so every homelab
# scheduled job runs under hc-run.sh (Healthchecks liveness). Idempotent:
# already-wrapped lines are left untouched. Backs up the current crontab first.
#
# Prereq: HEALTHCHECKS_PING_KEY set in ~/homelab/.env (see docs/job-liveness.md).
# Run on the host as the job owner (luk-server). Review the diff it prints
# before it installs (it asks for confirmation unless --yes is passed).
set -euo pipefail

HOMELAB_DIR="${HOMELAB_DIR:-$HOME/homelab}"
HC_RUN="$HOMELAB_DIR/scripts/maintenance/hc-run.sh"
ASSUME_YES=0
[[ "${1:-}" == "--yes" ]] && ASSUME_YES=1

# job slug  <TAB>  substring that identifies the crontab line to wrap
JOBS=$(cat <<'MAP'
containers-weekly-update	update-containers-cron.sh
lucky-db-backup	recover-lucky-db.sh
docker-weekly-cleanup	docker-prune.sh
MAP
)

[[ -x "$HC_RUN" ]] || { echo "ERROR: $HC_RUN not found/executable" >&2; exit 1; }

cur="$(crontab -l 2>/dev/null || true)"
[[ -n "$cur" ]] || { echo "ERROR: empty crontab — nothing to wrap" >&2; exit 1; }

backup="$HOMELAB_DIR/logs/crontab.$(date +%Y%m%d-%H%M%S).bak"
mkdir -p "$HOMELAB_DIR/logs"
printf '%s\n' "$cur" > "$backup"
echo "Backed up current crontab → $backup"

new="$cur"
while IFS=$'\t' read -r slug needle; do
  [[ -n "$slug" ]] || continue
  # skip if this job is already wrapped
  if printf '%s\n' "$new" | grep -qE "hc-run\.sh ${slug} "; then
    echo "  already wrapped: $slug"; continue
  fi
  # wrap the command portion (everything after the schedule) for the matching
  # line, leaving redirects in place after the wrapped command. Handles both
  # 5-field schedules and `@macro` schedules (@daily/@weekly/@reboot/…).
  prev="$new"
  new="$(printf '%s\n' "$new" | awk -v n="$needle" -v hc="$HC_RUN" -v slug="$slug" '
    index($0,n) && $0 !~ /^#/ && $0 !~ /hc-run\.sh/ {
      if ($1 ~ /^@/) { start=2; sched=$1 }
      else           { start=6; sched=$1" "$2" "$3" "$4" "$5 }
      cmd=""; for(i=start;i<=NF;i++) cmd=cmd (i>start?" ":"") $i
      print sched" "hc" "slug" -- "cmd; next
    }
    { print }
  ')"
  if [[ "$new" == "$prev" ]]; then
    echo "  WARN: no crontab line matched needle '$needle' for '$slug' — job NOT wrapped (no liveness coverage)" >&2
  else
    echo "  wrapped: $slug"
  fi
done <<< "$JOBS"

echo "----- proposed crontab -----"
diff <(printf '%s\n' "$cur") <(printf '%s\n' "$new") || true
echo "----------------------------"

if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Install this crontab? [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "Aborted (backup kept at $backup)."; exit 0; }
fi
printf '%s\n' "$new" | crontab -
echo "Installed. Restore with: crontab $backup"

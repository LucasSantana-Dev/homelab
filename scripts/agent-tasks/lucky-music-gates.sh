#!/usr/bin/env bash
set -euo pipefail
LOG_FILE="/home/luk-server/agent-logs/lucky-music-gates-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[$(date)] Starting Lucky music-first gates report..."

# shellcheck source=./common.sh
source "$(dirname "$0")/common.sh"

# The gates decide on 2026-12-20; after that the report has nothing to say.
if [[ "$(date +%Y-%m-%d)" > "2026-12-20" ]]; then
    echo "[$(date)] Decision date passed, nothing to report. Disable lucky-music-gates.timer."
    exit 0
fi

# Definitions follow Lucky scripts/music-first-gates.sql (source of truth):
# test-named guilds are excluded by substring, as the ADR requires, and day 8
# means any activity at or after join + 7 days.

# grafana_ro: read-only Postgres role used by Grafana dashboards (per issue #2869)
run_psql() {
    # shellcheck disable=SC2016  # $POSTGRES_DB expands inside the container
    docker exec -i lucky-postgres sh -c 'psql -U grafana_ro -d "$POSTGRES_DB" -t -A -F","'
}

WAG_SQL=$(mktemp)
COHORT_SQL=$(mktemp)
trap 'rm -f "$WAG_SQL" "$COHORT_SQL"' EXIT

# ── WAG gate (3 fixed decision weeks) ─────────────────────────────────────────
cat > "$WAG_SQL" << 'EOSQL'
WITH excluded AS (
    SELECT unnest('{110373943822540800,333949691962195969,1541452011466268704}'::text[]) AS g
    UNION SELECT "discordId" FROM guilds
          WHERE name ILIKE '%test%' AND "discordId" IS NOT NULL
    UNION SELECT "guildDiscordId" FROM guild_membership_events
          WHERE "guildName" ILIKE '%test%' AND "guildDiscordId" IS NOT NULL
),
wag_windows AS (
    SELECT week_start
    FROM (VALUES (DATE '2026-11-23'), (DATE '2026-11-30'), (DATE '2026-12-07')) AS v(week_start)
),
activity AS (
    SELECT date_trunc('week', "playedAt")::date AS wk, "guildId" AS g
    FROM track_history
    WHERE "playedAt" >= (SELECT min(week_start) FROM wag_windows)
    UNION
    SELECT date_trunc('week', "occurredAt")::date, "guildId"
    FROM command_events
    WHERE "guildId" IS NOT NULL
      AND "occurredAt" >= (SELECT min(week_start) FROM wag_windows)
)
SELECT w.week_start::text,
       count(DISTINCT a.g)::text,
       (count(DISTINCT a.g) >= 20)::text,
       (w.week_start + 7 <= now()::date)::text
FROM wag_windows w
LEFT JOIN activity a
       ON a.wk = w.week_start AND a.g NOT IN (SELECT g FROM excluded)
GROUP BY w.week_start
ORDER BY w.week_start;
EOSQL

# ── Cohort gates: 1st-hour play, day-8 return, removal <5 min ────────────────
cat > "$COHORT_SQL" << 'EOSQL'
WITH excluded AS (
    SELECT unnest('{110373943822540800,333949691962195969,1541452011466268704}'::text[]) AS g
    UNION SELECT "discordId" FROM guilds
          WHERE name ILIKE '%test%' AND "discordId" IS NOT NULL
    UNION SELECT "guildDiscordId" FROM guild_membership_events
          WHERE "guildName" ILIKE '%test%' AND "guildDiscordId" IS NOT NULL
),
counted_joins AS (
    SELECT g, t FROM (
        SELECT "guildDiscordId" AS g, "occurredAt" AS t,
               lag("occurredAt") OVER (PARTITION BY "guildDiscordId" ORDER BY "occurredAt") AS prev
        FROM guild_membership_events
        WHERE kind = 'JOIN'
    ) j
    WHERE prev IS NULL OR t - prev > interval '30 days'
),
cohort AS (
    SELECT j.g, j.t,
        EXISTS (SELECT 1 FROM track_history th
                WHERE th."guildId" = j.g
                  AND th."playedAt" BETWEEN j.t AND j.t + interval '1 hour') AS heard_1h,
        j.t <= now() - interval '1 hour' AS h1_eligible,
        j.t <= now() - interval '8 days' AS d8_eligible,
        (EXISTS (SELECT 1 FROM track_history th
                 WHERE th."guildId" = j.g
                   AND th."playedAt" >= j.t + interval '7 days')
         OR EXISTS (SELECT 1 FROM command_events ce
                    WHERE ce."guildId" = j.g
                      AND ce."occurredAt" >= j.t + interval '7 days')) AS active_d8,
        j.t <= now() - interval '5 minutes' AS rm_eligible,
        EXISTS (SELECT 1 FROM guild_membership_events l
                WHERE l."guildDiscordId" = j.g
                  AND l.kind = 'LEAVE'
                  AND l."occurredAt" >= j.t
                  AND l."occurredAt" < j.t + interval '5 minutes') AS removed_lt5m
    FROM counted_joins j
    WHERE j.t > now() - interval '28 days'
      AND j.g NOT IN (SELECT g FROM excluded)
)
SELECT
    count(*)::text,
    coalesce((100.0 * count(*) FILTER (WHERE h1_eligible AND heard_1h)
        / nullif(count(*) FILTER (WHERE h1_eligible), 0))::text, 'N/A'),
    coalesce((100.0 * count(*) FILTER (WHERE d8_eligible AND active_d8)
        / nullif(count(*) FILTER (WHERE d8_eligible), 0))::text, 'N/A'),
    coalesce((100.0 * count(*) FILTER (WHERE rm_eligible AND removed_lt5m)
        / nullif(count(*) FILTER (WHERE rm_eligible), 0))::text, 'N/A')
FROM cohort;
EOSQL

# psql errors go to stderr, which the tee above keeps in the log and journal.
FAILED=""
WAG_RESULT=$(run_psql < "$WAG_SQL") || FAILED="${FAILED} WAG"
COHORT_RESULT=$(run_psql < "$COHORT_SQL") || FAILED="${FAILED} cohort"

echo "WAG result: $WAG_RESULT"
echo "Cohort result: $COHORT_RESULT"

# A partial report would look valid, so any failed query stops the run.
if [[ -n "$FAILED" ]]; then
    $NOTIFY --title "⚠️ Music-First Gates: query failed" \
            --body "psql failed for:${FAILED}. Check lucky-postgres, the grafana_ro role and ${LOG_FILE}." \
            --urgency alert || true
    echo "[$(date)] Query failed:${FAILED}, alerted."
    exit 1
fi

# ── Build WAG section ─────────────────────────────────────────────────────────
WAG_LINES=""
WAG_ALL_PASS="true"
while IFS=',' read -r week_start wag meets_gate closed; do
    [[ -z "$week_start" ]] && continue
    week_end=$(date -d "${week_start} + 6 days" +%Y-%m-%d 2>/dev/null || echo "?")
    if [[ "$closed" == "true" ]]; then
        if [[ "$meets_gate" == "true" ]]; then
            mark="✅"
        else
            mark="❌"
            WAG_ALL_PASS="false"
        fi
        status_note=""
    else
        mark="·"
        status_note=" (open)"
    fi
    WAG_LINES="${WAG_LINES}  ${week_start} to ${week_end}: ${wag} guilds ${mark}${status_note}\n"
done <<< "$WAG_RESULT"

# ── Parse cohort ──────────────────────────────────────────────────────────────
IFS=',' read -r JOINS H1_PCT D8_PCT REMOVAL_PCT <<< "$COHORT_RESULT" || true
JOINS="${JOINS:-?}"
H1_PCT="${H1_PCT:-?}"
D8_PCT="${D8_PCT:-?}"
REMOVAL_PCT="${REMOVAL_PCT:-?}"

# SQL returns unrounded percentages: the goals compare those, the report shows
# one decimal. meets_goal 34.95 ge 35 fails.
meets_goal() {
    awk -v v="$1" -v op="$2" -v goal="$3" \
        'BEGIN {
            if (op == "ge") exit !(v + 0 >= goal)
            if (op == "lt") exit !(v + 0 < goal)
            exit 2
        }'
}

# Truncates a percentage to one decimal for the report, so the shown number
# agrees with its mark (34.95 shows 34.9%, not 35.0%); ? and N/A get no %.
fmt_pct() {
    if [[ "$1" == "?" || "$1" == "N/A" ]]; then
        echo "$1"
    elif [[ "$1" == *.* ]]; then
        local frac="${1#*.}"
        echo "${1%%.*}.${frac:0:1}%"
    else
        echo "$1%"
    fi
}

h1_mark="·"; d8_mark="·"; rm_mark="·"
URGENCY="info"
if [[ "$WAG_ALL_PASS" == "false" ]]; then
    URGENCY="warn"
fi

if [[ "$H1_PCT" != "?" && "$H1_PCT" != "N/A" ]]; then
    if meets_goal "$H1_PCT" ge 35; then
        h1_mark="✅"
    else
        h1_mark="❌"; URGENCY="warn"
    fi
fi
if [[ "$D8_PCT" != "?" && "$D8_PCT" != "N/A" ]]; then
    if meets_goal "$D8_PCT" ge 15; then
        d8_mark="✅"
    else
        d8_mark="❌"; URGENCY="warn"
    fi
fi
if [[ "$REMOVAL_PCT" != "?" && "$REMOVAL_PCT" != "N/A" ]]; then
    if meets_goal "$REMOVAL_PCT" lt 15; then
        rm_mark="✅"
    else
        rm_mark="❌"; URGENCY="warn"
    fi
fi

# ── Compose message ───────────────────────────────────────────────────────────
TODAY=$(date +%Y-%m-%d)
BODY="Music-First Gates, ${TODAY}

WAG (goal ≥20/week, decision on 2026-12-20):
$(printf '%b' "$WAG_LINES")
Cohort: ${JOINS} new guilds (last 28 days):
  1st-hour play:  $(fmt_pct "$H1_PCT")  (goal ≥35%) ${h1_mark}
  Day-8 return:   $(fmt_pct "$D8_PCT")  (goal ≥15%) ${d8_mark}
  Removal <5 min: $(fmt_pct "$REMOVAL_PCT")  (goal <15%) ${rm_mark}"

echo "$BODY"
$NOTIFY --title "📊 Lucky Music-First Gates" --body "$BODY" --urgency "$URGENCY" || true
echo "[$(date)] Music-first gates report complete."

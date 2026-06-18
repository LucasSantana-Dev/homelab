#!/bin/bash
# kopia-snapshot-freshness.sh
# Queries kopia snapshot list and exports last-snapshot timestamp to node-exporter textfile.
# Runs as a systemd timer (every ~6-12h) and writes atomically to the textfile collector dir.
#
# Metrics exported:
#   kopia_last_snapshot_timestamp_seconds   — epoch seconds of latest snapshot start time
#   kopia_snapshot_list_ok                  — 1 if snapshot list succeeded, 0 otherwise

set -euo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="${TEXTFILE_DIR}/kopia-snapshot-freshness.prom"
TEMP_FILE="${METRIC_FILE}.tmp"

# Ensure the textfile dir exists
mkdir -p "${TEXTFILE_DIR}"

# Helper: write metrics atomically (temp + mv)
write_metrics() {
    cat > "${TEMP_FILE}"
    mv "${TEMP_FILE}" "${METRIC_FILE}"
}

# Helper: format a datetime string to epoch seconds
# Kopia's JSON uses ISO8601 format (e.g., "2024-05-31T17:42:15Z")
datetime_to_epoch() {
    local dt="$1"
    # Use POSIX date if available (macOS), else GNU date (Linux)
    if date --version >/dev/null 2>&1; then
        # GNU date (Linux)
        date -d "${dt}" +%s 2>/dev/null || echo "0"
    else
        # BSD date (macOS)
        date -f "%Y-%m-%dT%H:%M:%SZ" -j "${dt}" +%s 2>/dev/null || echo "0"
    fi
}

# Query kopia and extract last snapshot timestamp
query_kopia() {
    local snapshot_json
    local latest_timestamp
    local epoch_seconds

    # Run `docker exec kopia kopia snapshot list --json` and parse
    if ! snapshot_json=$(docker exec kopia kopia snapshot list --json 2>/dev/null); then
        # snapshot list failed — kopia container down, repo unreachable, or no auth
        {
            cat <<'EOF'
# HELP kopia_snapshot_list_ok Kopia snapshot list command success
# TYPE kopia_snapshot_list_ok gauge
kopia_snapshot_list_ok 0
# HELP kopia_last_snapshot_timestamp_seconds Epoch seconds of latest snapshot start time
# TYPE kopia_last_snapshot_timestamp_seconds gauge
kopia_last_snapshot_timestamp_seconds 0
EOF
        } | write_metrics
        return
    fi

    # Extract the latest snapshot's startTime. `kopia snapshot list --json`
    # emits a top-level JSON array of snapshot manifests (no `.snapshots`
    # wrapper), each with a `.startTime`. On an empty array max_by → null →
    # `// empty` yields "" so the no-snapshots branch below writes 0.
    latest_timestamp=$(echo "${snapshot_json}" | \
        jq -r 'max_by(.startTime) | .startTime // empty' 2>/dev/null || echo "")

    if [ -z "${latest_timestamp}" ]; then
        # No snapshots found
        epoch_seconds=0
    else
        # Convert ISO8601 to epoch
        epoch_seconds=$(datetime_to_epoch "${latest_timestamp}")
        if [ "${epoch_seconds}" = "0" ] || [ -z "${epoch_seconds}" ]; then
            epoch_seconds=0
        fi
    fi

    # Write metrics
    {
        cat <<EOF
# HELP kopia_snapshot_list_ok Kopia snapshot list command success
# TYPE kopia_snapshot_list_ok gauge
kopia_snapshot_list_ok 1
# HELP kopia_last_snapshot_timestamp_seconds Epoch seconds of latest snapshot start time (0 if no snapshots)
# TYPE kopia_last_snapshot_timestamp_seconds gauge
kopia_last_snapshot_timestamp_seconds ${epoch_seconds}
EOF
    } | write_metrics
}

# Main
query_kopia

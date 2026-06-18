#!/bin/bash
# version-drift-exporter.sh
# Exports "running deployed version vs latest released tag" drift to the
# node-exporter textfile collector, so production silently falling behind a
# release becomes a loud Prometheus signal (ADR-0023).
#
# Metrics exported:
#   homelab_running_version_info{version="X.Y.Z"}   1   (label-only info metric)
#   homelab_latest_version_info{version="X.Y.Z"}    1
#   homelab_running_version_known                   1 if /health answered, else 0
#   homelab_latest_version_known                    1 if a semver tag was found, else 0
#   homelab_version_up_to_date                      1 if running == latest, else 0
#   homelab_version_exporter_last_run_timestamp_seconds   (meta-healthcheck: detect a dead exporter)

set -euo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="${TEXTFILE_DIR}/homelab-version-drift.prom"
TEMP_FILE="${METRIC_FILE}.tmp"
REPO_DIR="${REPO_DIR:-/home/luk-server/homelab}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8765/health}"

mkdir -p "${TEXTFILE_DIR}"
now="$(date +%s)"

# Running version: the homelab-manager /health endpoint reports __version__.
running=""
running_known=0
if resp="$(curl -s --max-time 5 "${HEALTH_URL}" 2>/dev/null)"; then
    running="$(printf '%s' "${resp}" | jq -r '.version // empty' 2>/dev/null || echo "")"
    [ -n "${running}" ] && running_known=1
fi

# Latest released version: highest *semver* tag only. Non-semver tags
# (e.g. backup-pre-public-*) MUST be excluded or they poison "latest".
latest=""
latest_known=0
if [ -d "${REPO_DIR}/.git" ]; then
    git -C "${REPO_DIR}" fetch --tags --quiet 2>/dev/null || true
    latest="$(git -C "${REPO_DIR}" tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname 2>/dev/null | head -1 | sed 's/^v//')"
    [ -n "${latest}" ] && latest_known=1
fi

# Up to date only when both sides are known and equal.
up_to_date=0
if [ "${running_known}" -eq 1 ] && [ "${latest_known}" -eq 1 ] && [ "${running}" = "${latest}" ]; then
    up_to_date=1
fi

{
    echo "# HELP homelab_running_version_info Currently deployed homelab-manager version (from /health)"
    echo "# TYPE homelab_running_version_info gauge"
    [ -n "${running}" ] && echo "homelab_running_version_info{version=\"${running}\"} 1"
    echo "# HELP homelab_latest_version_info Latest released semver tag in the repo"
    echo "# TYPE homelab_latest_version_info gauge"
    [ -n "${latest}" ] && echo "homelab_latest_version_info{version=\"${latest}\"} 1"
    echo "# HELP homelab_running_version_known 1 if the running version was successfully read"
    echo "# TYPE homelab_running_version_known gauge"
    echo "homelab_running_version_known ${running_known}"
    echo "# HELP homelab_latest_version_known 1 if a latest semver tag was found"
    echo "# TYPE homelab_latest_version_known gauge"
    echo "homelab_latest_version_known ${latest_known}"
    echo "# HELP homelab_version_up_to_date 1 if running version equals latest release tag, else 0"
    echo "# TYPE homelab_version_up_to_date gauge"
    echo "homelab_version_up_to_date ${up_to_date}"
    echo "# HELP homelab_version_exporter_last_run_timestamp_seconds Unix time of the last export run"
    echo "# TYPE homelab_version_exporter_last_run_timestamp_seconds gauge"
    echo "homelab_version_exporter_last_run_timestamp_seconds ${now}"
} > "${TEMP_FILE}"

mv "${TEMP_FILE}" "${METRIC_FILE}"

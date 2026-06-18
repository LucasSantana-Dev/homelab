#!/bin/bash
# record-deploy-health.sh
# Run at the end of `make deploy`: verify homelab-manager came up, and record a
# deploy-health Prometheus textfile metric so a *failed or never-run* deploy is
# visible — not just version drift (ADR-0023).
#
# Exit non-zero if the manager did not report healthy, so `make deploy` fails
# loudly instead of printing "complete" over a broken deploy.

set -uo pipefail

TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC_FILE="${TEXTFILE_DIR}/homelab-last-deploy.prom"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8765/health}"
now="$(date +%s)"

version=""
success=0
if resp="$(curl -s --max-time 8 "${HEALTH_URL}" 2>/dev/null)"; then
    status="$(printf '%s' "${resp}" | jq -r '.status // empty' 2>/dev/null || echo "")"
    version="$(printf '%s' "${resp}" | jq -r '.version // empty' 2>/dev/null || echo "")"
    [ "${status}" = "ok" ] && success=1
fi

# Best-effort metric write (textfile dir is root-owned; skip silently if not writable).
if [ -w "${TEXTFILE_DIR}" ] || { [ -d "${TEXTFILE_DIR}" ] && touch "${TEXTFILE_DIR}/.w" 2>/dev/null && rm -f "${TEXTFILE_DIR}/.w"; }; then
    tmp="${METRIC_FILE}.tmp"
    {
        echo "# HELP homelab_last_deploy_timestamp_seconds Unix time of the last make-deploy run"
        echo "# TYPE homelab_last_deploy_timestamp_seconds gauge"
        echo "homelab_last_deploy_timestamp_seconds ${now}"
        echo "# HELP homelab_last_deploy_success 1 if the manager reported healthy after deploy, else 0"
        echo "# TYPE homelab_last_deploy_success gauge"
        echo "homelab_last_deploy_success ${success}"
        echo "# HELP homelab_last_deploy_version_info Version reported by the manager after the last deploy"
        echo "# TYPE homelab_last_deploy_version_info gauge"
        [ -n "${version}" ] && echo "homelab_last_deploy_version_info{version=\"${version}\"} 1"
    } > "${tmp}" && mv "${tmp}" "${METRIC_FILE}"
fi

if [ "${success}" -eq 1 ]; then
    echo "  ✓ deploy health: homelab-manager ${version:-?} reported ok"
    exit 0
else
    echo "  ✗ deploy health: homelab-manager did not report healthy at ${HEALTH_URL}" >&2
    exit 1
fi

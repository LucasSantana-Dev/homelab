#!/usr/bin/env bash
# Run gated Terraform phase-1 apply after pressure-watch T+24 data is available.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
WATCH_DIR="${WATCH_DIR:-/tmp/homelab-pressure-watch-20260314_115740}"
SWAP_THRESHOLD_GIB="${SWAP_THRESHOLD_GIB:-2.0}"
EXPECTED_PLAN_ADDS="${EXPECTED_PLAN_ADDS:-7}"
LOG_DIR="${PROJECT_ROOT}/logs/terraform-phase1"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/post-t24-apply-${TIMESTAMP}.log"
BUNDLE_DIR="/tmp/homelab-terraform-apply-${TIMESTAMP}"
DONE_MARKER="${WATCH_DIR}/post-t24-terraform-apply.done"

mkdir -p "${LOG_DIR}" "${BUNDLE_DIR}"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

require_file() {
  local f="$1"
  if [[ ! -f "${f}" ]]; then
    log "Missing required file: ${f}"
    return 1
  fi
}

if [[ -f "${DONE_MARKER}" ]]; then
  log "Already completed (${DONE_MARKER}); exiting."
  exit 0
fi

T24_SWAP="${WATCH_DIR}/TPLUS24H-swapon-show.txt"
T24_BURNIN="${WATCH_DIR}/TPLUS24H-burnin-30m.txt"
T24_META="${WATCH_DIR}/TPLUS24H-meta.txt"
TF_DIR="${PROJECT_ROOT}/infra/terraform"

require_file "${T24_SWAP}"
require_file "${T24_BURNIN}"
require_file "${T24_META}"

log "Evaluating T+24 gate token from watch artifacts"
set +e
gate_output="$(
  WATCH_DIR="${WATCH_DIR}" \
    LABEL="TPLUS24H" \
    PREV_LABEL="TPLUS6H" \
    SWAP_THRESHOLD_GIB="${SWAP_THRESHOLD_GIB}" \
    "${PROJECT_ROOT}/scripts/maintenance/pressure-checkpoint-gate.sh" 2>&1
)"
gate_exit=$?
set -e
printf '%s\n' "${gate_output}" > "${BUNDLE_DIR}/tplus24-gate.txt"

gate_token="$(awk -F= '/^GATE_TOKEN=/{print $2}' <<< "${gate_output}" | tail -n1)"
gate_reason="$(awk -F= '/^REASON=/{print $2}' <<< "${gate_output}" | tail -n1)"
log "T+24 gate token=${gate_token:-unknown} reason=${gate_reason:-unknown}"

if [[ "${gate_exit}" -eq 2 || "${gate_token}" == "BLOCKED" ]]; then
  log "T+24 checkpoint is BLOCKED. Escalation: phase-2 maintenance window (server-mode-apply + reboot + post-reboot validate)."
  exit 22
fi
if [[ "${gate_exit}" -ne 0 ]]; then
  log "T+24 gate evaluation failed unexpectedly (exit=${gate_exit})."
  exit 21
fi
if [[ "${gate_token}" != "GREENLIGHT" ]]; then
  log "T+24 gate token is ${gate_token:-unknown}; expected GREENLIGHT."
  exit 20
fi

if [[ -n "$(git -C "${PROJECT_ROOT}" status --porcelain)" ]]; then
  log "Working tree is not clean. Blocking apply until repo drift is reconciled."
  exit 23
fi

log "Capturing pre-apply evidence bundle: ${BUNDLE_DIR}"
git -C "${PROJECT_ROOT}" status --short > "${BUNDLE_DIR}/git-status-short.txt"
git -C "${PROJECT_ROOT}" rev-parse HEAD > "${BUNDLE_DIR}/git-head.txt"
free -h > "${BUNDLE_DIR}/free-h.txt"
swapon --show > "${BUNDLE_DIR}/swapon-show.txt"
"${PROJECT_ROOT}/scripts/homelab" health > "${BUNDLE_DIR}/homelab-health.txt"
"${PROJECT_ROOT}/scripts/maintenance/burnin-status.sh" --since '24 hours ago' > "${BUNDLE_DIR}/burnin-24h.txt"
make -C "${PROJECT_ROOT}" migration-budget > "${BUNDLE_DIR}/migration-budget.txt"
make -C "${PROJECT_ROOT}" migration-preflight > "${BUNDLE_DIR}/migration-preflight.txt"

DOMAIN="$(grep '^DOMAIN=' "${PROJECT_ROOT}/.env" | cut -d= -f2-)"
CLOUDFLARE_API_TOKEN="$(grep '^CLOUDFLARE_API_TOKEN=' "${PROJECT_ROOT}/.env" | cut -d= -f2-)"
ZONE_ID="$(awk -F'"' '/^zone_id/{print $2}' "${TF_DIR}/terraform.tfvars")"
TUNNEL_ID="$(awk -F'"' '/^tunnel_id/{print $2}' "${TF_DIR}/terraform.tfvars")"
EXPECTED_CONTENT="${TUNNEL_ID}.cfargotunnel.com"

log "Running Terraform fmt -check and validate"
set +e
(
  cd "${TF_DIR}"
  terraform fmt -check -no-color
  terraform validate -no-color
) > "${BUNDLE_DIR}/terraform-prechecks.txt" 2>&1
precheck_exit=$?
set -e

if [[ "${precheck_exit}" -ne 0 ]]; then
  log "Terraform prechecks failed (fmt/validate)."
  exit 24
fi

log "Running Terraform pre-apply plan (detailed exit code)"
set +e
(
  cd "${TF_DIR}"
  CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN}" terraform plan -input=false -detailed-exitcode -no-color
) > "${BUNDLE_DIR}/terraform-plan-preapply.txt" 2>&1
plan_exit=$?
set -e

if [[ "${plan_exit}" -eq 1 ]]; then
  log "Terraform pre-apply plan failed."
  exit 30
fi

if [[ "${plan_exit}" -ne 2 ]]; then
  log "Terraform pre-apply plan exit=${plan_exit}. Expected exit=2 before apply."
  exit 32
fi

plan_summary="$(grep -E '^Plan: [0-9]+ to add, [0-9]+ to change, [0-9]+ to destroy\.$' "${BUNDLE_DIR}/terraform-plan-preapply.txt" | tail -n1 || true)"
if [[ -z "${plan_summary}" ]]; then
  log "Terraform pre-apply plan summary line not found."
  exit 33
fi

actual_adds="$(awk '{print $2}' <<< "${plan_summary}")"
actual_changes="$(awk '{print $5}' <<< "${plan_summary}")"
actual_destroy="$(awk '{print $8}' <<< "${plan_summary}" | tr -d '.')"
if [[ "${actual_adds}" != "${EXPECTED_PLAN_ADDS}" || "${actual_changes}" != "0" || "${actual_destroy}" != "0" ]]; then
  log "Unexpected Terraform pre-apply plan summary: ${plan_summary}"
  log "Expected: Plan: ${EXPECTED_PLAN_ADDS} to add, 0 to change, 0 to destroy."
  exit 34
fi

log "Executing terraform apply"
(
  cd "${TF_DIR}"
  CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN}" terraform apply -input=false -auto-approve -no-color
) > "${BUNDLE_DIR}/terraform-apply.txt" 2>&1

log "Running Terraform post-apply no-op check"
set +e
(
  cd "${TF_DIR}"
  CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN}" terraform plan -input=false -detailed-exitcode -no-color
) > "${BUNDLE_DIR}/terraform-plan-postapply.txt" 2>&1
post_plan_exit=$?
set -e

if [[ "${post_plan_exit}" -ne 0 ]]; then
  log "Post-apply plan is not no-op (exit=${post_plan_exit})."
  exit 31
fi

log "Verifying DNS record outcomes"
for name in home blackbox files; do
  fqdn="${name}.${DOMAIN}"
  response="$(curl -sS -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records?name=${fqdn}")"
  count="$(jq -r '.result | length' <<< "${response}")"
  if [[ "${count}" -lt 1 ]]; then
    log "Missing DNS record: ${fqdn}"
    exit 40
  fi
  actual_content="$(jq -r '.result[0].content' <<< "${response}")"
  actual_proxied="$(jq -r '.result[0].proxied' <<< "${response}")"
  {
    echo "${fqdn} content=${actual_content} proxied=${actual_proxied}"
  } >> "${BUNDLE_DIR}/dns-verification.txt"
  if [[ "${actual_content}" != "${EXPECTED_CONTENT}" ]]; then
    log "DNS content mismatch for ${fqdn}: expected ${EXPECTED_CONTENT}, got ${actual_content}"
    exit 41
  fi
  if [[ "${actual_proxied}" != "true" ]]; then
    log "DNS proxied flag mismatch for ${fqdn}: expected true, got ${actual_proxied}"
    exit 42
  fi
done

log "Running post-apply safety gate"
"${PROJECT_ROOT}/scripts/homelab" health > "${BUNDLE_DIR}/postapply-health.txt"
"${PROJECT_ROOT}/scripts/maintenance/burnin-status.sh" --since '24 hours ago' > "${BUNDLE_DIR}/postapply-burnin-24h.txt"
make -C "${PROJECT_ROOT}" migration-budget > "${BUNDLE_DIR}/postapply-migration-budget.txt"
make -C "${PROJECT_ROOT}" migration-preflight > "${BUNDLE_DIR}/postapply-migration-preflight.txt"

date --iso-8601=seconds > "${DONE_MARKER}"
log "Post-T+24 Terraform apply workflow completed successfully."
log "Evidence bundle: ${BUNDLE_DIR}"
log "Done marker: ${DONE_MARKER}"

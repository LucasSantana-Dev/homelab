#!/usr/bin/env bash
# Back up Terraform state file to a timestamped location.
# Run this before and after terraform apply operations.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "${SCRIPT_DIR}")")"
TF_DIR="${PROJECT_ROOT}/infra/terraform"
BACKUP_DIR="${PROJECT_ROOT}/logs/terraform-state-backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "${BACKUP_DIR}"

STATE_FILE="${TF_DIR}/terraform.tfstate"
if [[ ! -f "${STATE_FILE}" ]]; then
  echo "No state file found at ${STATE_FILE}"
  exit 0
fi

BACKUP_FILE="${BACKUP_DIR}/terraform.tfstate.${TIMESTAMP}"
cp "${STATE_FILE}" "${BACKUP_FILE}"
echo "Backed up: ${BACKUP_FILE} ($(stat -c%s "${BACKUP_FILE}") bytes)"

KEEP_COUNT=10
BACKUPS=$(ls -1t "${BACKUP_DIR}"/terraform.tfstate.* 2>/dev/null | tail -n +$((KEEP_COUNT + 1)))
if [[ -n "${BACKUPS}" ]]; then
  echo "${BACKUPS}" | xargs rm -f
  echo "Pruned old backups (keeping last ${KEEP_COUNT})"
fi

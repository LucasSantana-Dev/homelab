#!/usr/bin/env bash
# Create safety checkpoint artifacts before public history rewrite.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${ROOT_DIR}/backups/public-release/${TIMESTAMP}"
MIRROR_BACKUP_DIR="${BACKUP_ROOT}/homelab.git.mirror"
INVENTORY_FILE="${BACKUP_ROOT}/credential-inventory.md"
BRANCH_NAME="backup/pre-public-${TIMESTAMP}"
TAG_NAME="backup-pre-public-${TIMESTAMP}"

mkdir -p "${BACKUP_ROOT}"

echo "Creating pre-release safety checkpoint..."
echo "Repository: ${ROOT_DIR}"
echo "Backup root: ${BACKUP_ROOT}"

git -C "${ROOT_DIR}" branch "${BRANCH_NAME}"
git -C "${ROOT_DIR}" tag "${TAG_NAME}"
echo "Created backup branch: ${BRANCH_NAME}"
echo "Created backup tag: ${TAG_NAME}"

origin_url="$(git -C "${ROOT_DIR}" remote get-url origin)"
git clone --mirror "${origin_url}" "${MIRROR_BACKUP_DIR}"
echo "Created mirror backup: ${MIRROR_BACKUP_DIR}"

{
  echo "# Credential Rotation Inventory"
  echo
  echo "- Generated: $(date -Iseconds)"
  echo "- Source: .env.example"
  echo
  echo "## Variables Requiring Rotation Before Public Release"
  echo
  echo "| Variable | Rotation Required | Owner | Notes |"
  echo "|---|---|---|---|"
  grep -E 'TOKEN=|PASSWORD=|SECRET=|WEBHOOK|API_KEY|CLIENT_SECRET|AUTH_TOKEN' "${ROOT_DIR}/.env.example" \
    | sed 's/=.*//' \
    | sed 's/^/| `/' \
    | sed 's/$/` | yes | ops | rotate and verify cutover |/'
  echo
  echo "## Merge Freeze Checklist"
  echo
  echo "- [ ] Freeze direct merges to \`main\`"
  echo "- [ ] Notify collaborators about upcoming history rewrite and re-clone requirement"
  echo "- [ ] Confirm rotated values are active before any public push"
} > "${INVENTORY_FILE}"

echo "Wrote credential inventory: ${INVENTORY_FILE}"
echo "Pre-release checkpoint completed"

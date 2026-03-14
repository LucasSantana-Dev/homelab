#!/usr/bin/env bash
# Initialize local age key material for SOPS-managed Kubernetes secrets.

set -euo pipefail

KEY_DIR="${HOME}/.config/sops/age"
KEY_FILE="${KEY_DIR}/keys.txt"

mkdir -p "${KEY_DIR}"
chmod 700 "${KEY_DIR}"

if [[ ! -f "${KEY_FILE}" ]]; then
  age-keygen -o "${KEY_FILE}"
  chmod 600 "${KEY_FILE}"
  echo "Created ${KEY_FILE}"
else
  echo "Age key already exists: ${KEY_FILE}"
fi

PUB_KEY="$(grep '^# public key:' "${KEY_FILE}" | awk '{print $4}')"
echo "Public key: ${PUB_KEY}"

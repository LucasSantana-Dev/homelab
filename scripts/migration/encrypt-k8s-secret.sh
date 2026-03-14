#!/usr/bin/env bash
# Encrypt a Kubernetes secret manifest into k8s/secrets/*.enc.yaml via SOPS.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <input.yaml> <output.enc.yaml>"
  exit 1
fi

INPUT="$1"
OUTPUT="$2"

sops --encrypt --filename-override "${OUTPUT}" "${INPUT}" > "${OUTPUT}"
echo "Encrypted secret written to ${OUTPUT}"

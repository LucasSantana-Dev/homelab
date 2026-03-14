#!/usr/bin/env bash
# Install k3s (if needed), synchronize kubeconfig, and apply baseline policies.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
READY_TIMEOUT_SECONDS="${K3S_READY_TIMEOUT_SECONDS:-180}"
K3S_KUBECONFIG="/etc/rancher/k3s/k3s.yaml"
LOCAL_KUBECONFIG_DIR="${HOME}/.kube"
LOCAL_KUBECONFIG="${LOCAL_KUBECONFIG_DIR}/config"
LOCAL_UID="$(id -u)"
LOCAL_GID="$(id -g)"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  SUDO_CMD=()
else
  SUDO_CMD=(sudo)
fi

run_sudo() {
  if [[ ${#SUDO_CMD[@]} -gt 0 ]]; then
    "${SUDO_CMD[@]}" "$@"
  else
    "$@"
  fi
}

wait_for_k3s_ready() {
  local start_ts now elapsed
  start_ts="$(date +%s)"
  echo "Waiting for k3s API readiness (timeout: ${READY_TIMEOUT_SECONDS}s)..."

  until run_sudo k3s kubectl get --raw=/readyz >/dev/null 2>&1; do
    now="$(date +%s)"
    elapsed="$((now - start_ts))"
    if (( elapsed >= READY_TIMEOUT_SECONDS )); then
      echo "k3s API did not become ready within ${READY_TIMEOUT_SECONDS}s"
      run_sudo systemctl status k3s --no-pager -l | sed -n '1,120p' || true
      return 1
    fi
    sleep 3
  done

  echo "k3s API is ready"
}

sync_kubeconfig() {
  local backup_file

  if ! run_sudo test -f "${K3S_KUBECONFIG}"; then
    echo "Missing k3s kubeconfig at ${K3S_KUBECONFIG}"
    return 1
  fi

  mkdir -p "${LOCAL_KUBECONFIG_DIR}"

  if [[ -f "${LOCAL_KUBECONFIG}" ]]; then
    backup_file="${LOCAL_KUBECONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    mv "${LOCAL_KUBECONFIG}" "${backup_file}"
    echo "Backed up existing kubeconfig to ${backup_file}"
  fi

  run_sudo cp "${K3S_KUBECONFIG}" "${LOCAL_KUBECONFIG}"
  run_sudo chown "${LOCAL_UID}:${LOCAL_GID}" "${LOCAL_KUBECONFIG}"
  chmod 600 "${LOCAL_KUBECONFIG}"

  export KUBECONFIG="${LOCAL_KUBECONFIG}"
  echo "Synchronized kubeconfig to ${LOCAL_KUBECONFIG}"
}

if ! command -v k3s >/dev/null 2>&1; then
  echo "Installing k3s..."
  curl -sfL https://get.k3s.io | run_sudo sh -
else
  echo "k3s already installed"
fi

if ! systemctl is-active --quiet k3s 2>/dev/null; then
  echo "Starting k3s service..."
  run_sudo systemctl start k3s
fi

wait_for_k3s_ready
sync_kubeconfig

echo "Applying namespaces and policies..."
kubectl apply -f "${ROOT_DIR}/k8s/namespaces/namespaces.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/policies/limit-ranges.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/policies/resource-quotas.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/policies/default-deny.yaml"

echo
echo "Verification"
echo "Current context: $(kubectl config current-context)"
kubectl get nodes -o wide
echo
kubectl get ns platform observability apps

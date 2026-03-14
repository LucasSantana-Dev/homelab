#!/usr/bin/env bash
# Install migration CLI prerequisites into ~/.local/bin without sudo.

set -euo pipefail

BIN_DIR="${HOME}/.local/bin"
ARCH="$(uname -m)"
OS="linux"

case "${ARCH}" in
  x86_64)
    ARCH_K8S="amd64"
    ARCH_HELM="amd64"
    ARCH_SOPS="amd64"
    ARCH_AGE="amd64"
    ;;
  aarch64|arm64)
    ARCH_K8S="arm64"
    ARCH_HELM="arm64"
    ARCH_SOPS="arm64"
    ARCH_AGE="arm64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH}"
    exit 1
    ;;
esac

KUBECTL_VERSION="${KUBECTL_VERSION:-$(curl -fsSL https://dl.k8s.io/release/stable.txt)}"
HELM_VERSION="${HELM_VERSION:-v3.15.4}"
SOPS_VERSION="${SOPS_VERSION:-v3.9.3}"
AGE_VERSION="${AGE_VERSION:-v1.2.1}"

mkdir -p "${BIN_DIR}"

install_kubectl() {
  echo "Installing kubectl ${KUBECTL_VERSION}..."
  curl -fsSL "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/${OS}/${ARCH_K8S}/kubectl" -o "${BIN_DIR}/kubectl"
  chmod +x "${BIN_DIR}/kubectl"
}

install_helm() {
  echo "Installing helm ${HELM_VERSION}..."
  tmpdir="$(mktemp -d)"
  curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-${OS}-${ARCH_HELM}.tar.gz" -o "${tmpdir}/helm.tgz"
  tar -xzf "${tmpdir}/helm.tgz" -C "${tmpdir}"
  install -m 0755 "${tmpdir}/${OS}-${ARCH_HELM}/helm" "${BIN_DIR}/helm"
  rm -rf "${tmpdir}"
}

install_sops() {
  echo "Installing sops ${SOPS_VERSION}..."
  curl -fsSL "https://github.com/getsops/sops/releases/download/${SOPS_VERSION}/sops-${SOPS_VERSION}.${OS}.${ARCH_SOPS}" -o "${BIN_DIR}/sops"
  chmod +x "${BIN_DIR}/sops"
}

install_age() {
  echo "Installing age ${AGE_VERSION}..."
  tmpdir="$(mktemp -d)"
  curl -fsSL "https://github.com/FiloSottile/age/releases/download/${AGE_VERSION}/age-${AGE_VERSION}-${OS}-${ARCH_AGE}.tar.gz" -o "${tmpdir}/age.tgz"
  tar -xzf "${tmpdir}/age.tgz" -C "${tmpdir}"
  install -m 0755 "${tmpdir}/age/age" "${BIN_DIR}/age"
  install -m 0755 "${tmpdir}/age/age-keygen" "${BIN_DIR}/age-keygen"
  rm -rf "${tmpdir}"
}

install_kubectl
install_helm
install_sops
install_age

echo
echo "Installed binaries in ${BIN_DIR}:"
for tool in kubectl helm sops age age-keygen; do
  "${BIN_DIR}/${tool}" --help >/dev/null 2>&1 && echo "  - ${tool}"
done

if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  echo
  echo "Add ${BIN_DIR} to PATH if needed:"
  echo "  export PATH=\"${BIN_DIR}:\$PATH\""
fi

#!/usr/bin/env bash

set -euo pipefail

SYFT_VERSION="${SYFT_VERSION:-1.9.0}"
GRYPE_VERSION="${GRYPE_VERSION:-0.99.1}"
COSIGN_VERSION="${COSIGN_VERSION:-2.4.3}"
INSTALL_ROOT="${1:-/tmp/polisyos-supply-chain-tools}"
BIN_DIR="${INSTALL_ROOT}/bin"
TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/polisyos-supply-chain-tools.XXXXXX")"

cleanup() {
  rm -rf "$TMP_DIR"
}

trap cleanup EXIT

case "$(uname -s)" in
  Linux) os="linux" ;;
  Darwin) os="darwin" ;;
  *)
    echo "Unsupported OS for supply-chain tool installer: $(uname -s)" >&2
    exit 1
    ;;
esac

case "$(uname -m)" in
  x86_64 | amd64) arch="amd64" ;;
  arm64 | aarch64) arch="arm64" ;;
  *)
    echo "Unsupported architecture for supply-chain tool installer: $(uname -m)" >&2
    exit 1
    ;;
esac

mkdir -p "${BIN_DIR}"

download_and_extract() {
  local url="$1"
  local target_name="$2"
  local archive_name
  archive_name="$(basename "${url}")"
  curl -fsSL "${url}" -o "${TMP_DIR}/${archive_name}"
  tar -xzf "${TMP_DIR}/${archive_name}" -C "${BIN_DIR}" "${target_name}"
}

download_and_extract \
  "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_${os}_${arch}.tar.gz" \
  "syft"
download_and_extract \
  "https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/grype_${GRYPE_VERSION}_${os}_${arch}.tar.gz" \
  "grype"

curl -fsSL \
  "https://github.com/sigstore/cosign/releases/download/v${COSIGN_VERSION}/cosign-${os}-${arch}" \
  -o "${BIN_DIR}/cosign"
chmod +x "${BIN_DIR}/cosign"

echo "${BIN_DIR}"

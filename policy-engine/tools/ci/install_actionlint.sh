#!/usr/bin/env bash

set -euo pipefail

VERSION="${ACTIONLINT_VERSION:-1.7.12}"
INSTALL_ROOT="${1:-/tmp/actionlint}"

case "$(uname -s)" in
  Linux) os="linux" ;;
  Darwin) os="darwin" ;;
  *)
    echo "Unsupported OS for actionlint installer: $(uname -s)" >&2
    exit 1
    ;;
esac

case "$(uname -m)" in
  x86_64|amd64) arch="amd64" ;;
  arm64|aarch64) arch="arm64" ;;
  *)
    echo "Unsupported architecture for actionlint installer: $(uname -m)" >&2
    exit 1
    ;;
esac

ARCHIVE="actionlint_${VERSION}_${os}_${arch}.tar.gz"
DOWNLOAD_URL="https://github.com/rhysd/actionlint/releases/download/v${VERSION}/${ARCHIVE}"

mkdir -p "${INSTALL_ROOT}"
curl -fsSL "${DOWNLOAD_URL}" -o "/tmp/${ARCHIVE}"
tar -xzf "/tmp/${ARCHIVE}" -C "${INSTALL_ROOT}" actionlint

echo "${INSTALL_ROOT}/actionlint"

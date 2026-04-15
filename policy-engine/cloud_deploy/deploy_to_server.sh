#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export POLISYOS_CLOUD_ASSETS_DIR="${SCRIPT_DIR}"
exec bash "${ROOT}/tools/cloud/deploy/deploy_to_server.sh" "$@"

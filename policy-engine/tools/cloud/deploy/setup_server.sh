#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/cloud/deploy/setup_server.sh` is a compatibility wrapper; use `tools/ops/cloud/deploy/setup_server.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../../ops/cloud/deploy/setup_server.sh" "$@"

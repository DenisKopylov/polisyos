#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/cloud/check_progress.sh` is a compatibility wrapper; use `tools/ops/cloud/check_progress.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../ops/cloud/check_progress.sh" "$@"

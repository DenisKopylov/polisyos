#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/cloud/pipeline/run_diagnostic.sh` is a compatibility wrapper; use `tools/ops/cloud/pipeline/run_diagnostic.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../../ops/cloud/pipeline/run_diagnostic.sh" "$@"

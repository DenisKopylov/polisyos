#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/validation/run_benchmark_contours.sh` is a compatibility wrapper; use `tools/quality/validation/run_benchmark_contours.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../quality/validation/run_benchmark_contours.sh" "$@"

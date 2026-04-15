#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/benchmarks/run_all_benchmarks.sh` is a compatibility wrapper; use `tools/research/benchmarks/run_all_benchmarks.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../research/benchmarks/run_all_benchmarks.sh" "$@"

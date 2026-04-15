#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

printf '%s\n' 'DEPRECATED: `benchmarks/run_all_benchmarks.sh` is a compatibility wrapper; use `polisyos-tools benchmarks run-all` instead.' >&2
exec python3 -m tools.cli benchmarks run-all "$@"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
printf '%s\n' 'DEPRECATED: `benchmarks/run_local_sota_profile.sh` is a compatibility wrapper; use `polisyos-tools benchmarks run-local-sota-profile` instead.' >&2
exec bash "${SCRIPT_DIR}/../tools/research/benchmarks/run_local_sota_profile.sh" "$@"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-governance}"
printf '%s\n' 'DEPRECATED: `scripts/mutation_test_scientist.sh` is a compatibility wrapper; use `polisyos-tools testing mutation --suite scientist --target <target>` instead.' >&2
exec python3 -m tools.cli testing mutation --suite scientist --target "${TARGET}"

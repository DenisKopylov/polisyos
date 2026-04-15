#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-backends}"
printf '%s\n' 'DEPRECATED: `scripts/mutation_test.sh` is a compatibility wrapper; use `polisyos-tools testing mutation --suite foundry --target <target>` instead.' >&2
exec python3 -m tools.cli testing mutation --suite foundry --target "${TARGET}"

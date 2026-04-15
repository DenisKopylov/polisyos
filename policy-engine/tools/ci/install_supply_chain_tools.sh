#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' 'DEPRECATED: `tools/ci/install_supply_chain_tools.sh` is a compatibility wrapper; use `tools/quality/ci/install_supply_chain_tools.sh` instead.' >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../quality/ci/install_supply_chain_tools.sh" "$@"

#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "PolicyOS install.sh now delegates to the canonical workspace bootstrap."
echo "Use --profile minimal|docs|runtime|research to select the dependency tier."

exec ./scripts/bootstrap "$@"

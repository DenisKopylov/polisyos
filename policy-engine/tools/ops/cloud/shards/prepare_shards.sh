#!/usr/bin/env bash
# =============================================================================
# Prepare topic shards for multi-server deployment.
#
# Usage:
#   bash tools/cloud/prepare_shards.sh /path/to/filtered_topics.csv [--deploy-dir /path/to/out]
#
# Creates:
#   topics_shard_1.csv, topics_shard_2.csv, topics_shard_3.csv
#   .env.server_1.example, .env.server_2.example, .env.server_3.example
#
# Note:
#   This script no longer writes live secrets or generated deploy helpers.
#   Fill in the example env files manually before deployment.
# =============================================================================

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/cloud/prepare_shards.sh /path/to/filtered_topics.csv [--deploy-dir /path/to/out]
EOF
}

cleanup() {
  if [[ -n "${TMP_DIR:-}" && -d "${TMP_DIR:-}" ]]; then
    rm -rf "$TMP_DIR"
  fi
}

trap cleanup EXIT

TOPICS_CSV=""
DEPLOY_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-dir)
      DEPLOY_DIR="${2:?--deploy-dir requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$TOPICS_CSV" ]]; then
        TOPICS_CSV="$1"
        shift
      else
        echo "ERROR: unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [[ -z "$TOPICS_CSV" ]]; then
  usage >&2
  exit 2
fi

TOPICS_CSV="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=True))' "$TOPICS_CSV")"
if [[ ! -f "$TOPICS_CSV" ]]; then
  echo "ERROR: File not found: $TOPICS_CSV" >&2
  exit 1
fi

if [[ -z "$DEPLOY_DIR" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  DEPLOY_DIR="${SCRIPT_DIR}/../deploy/assets"
fi
DEPLOY_DIR="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$DEPLOY_DIR")"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/polisyos-shards.XXXXXX")"
mkdir -p "$DEPLOY_DIR"

TOTAL="$(python3 -c 'import csv, sys; from pathlib import Path; rows=list(csv.reader(Path(sys.argv[1]).open("r", encoding="utf-8", newline=""))); print(max(len(rows)-1, 0))' "$TOPICS_CSV")"
echo "Input: $TOPICS_CSV ($TOTAL topics)"

python3 - "$TOPICS_CSV" "$DEPLOY_DIR" <<'PY'
import csv
import random
import sys
from pathlib import Path

source = Path(sys.argv[1])
deploy_dir = Path(sys.argv[2])

with source.open("r", encoding="utf-8", newline="") as handle:
    rows = list(csv.reader(handle))

if not rows:
    raise SystemExit("Input CSV is empty")

header, body = rows[0], rows[1:]
random.Random(0).shuffle(body)

chunk_size = (len(body) + 2) // 3 if body else 0
chunks = [body[i * chunk_size : (i + 1) * chunk_size] for i in range(3)] if chunk_size else [[], [], []]
while len(chunks) < 3:
    chunks.append([])

for index, chunk in enumerate(chunks[:3], start=1):
    out_path = deploy_dir / f"topics_shard_{index}.csv"
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(chunk)
    print(f"  Shard {index}: {len(chunk)} topics -> {out_path}")
PY

echo ""
echo "=== Creating env templates ==="

for server in 1 2 3; do
  cat > "$DEPLOY_DIR/.env.server_${server}.example" <<EOF
# Server ${server} environment template.
# Fill in real values before deployment.
GONKA_API_KEY=
GONKA_API_KEY_1=
GONKA_API_KEY_2=
GONKA_API_KEY_3=
GONKA_API_KEY_4=

UNPAYWALL_EMAIL=

# Linux VPS settings
JAX_PLATFORM_NAME=cpu
XLA_PYTHON_CLIENT_PREALLOCATE=false
DUCKDB_MEMORY_LIMIT=3GB
DUCKDB_THREADS=2
OMP_NUM_THREADS=2
OPENBLAS_NUM_THREADS=2
EOF
  echo "  Created .env.server_${server}.example"
done

cat > "$DEPLOY_DIR/DEPLOYMENT_NOTES.txt" <<EOF
Prepared shard CSVs and env templates in:
  $DEPLOY_DIR

Before deployment:
1. Copy .env.server_N.example -> .env.server_N and fill in secrets manually.
2. Upload topics_shard_N.csv to each server's topics directory.
3. Upload the reviewed .env.server_N to each server as .env.

Automated deploy helper generation is intentionally disabled in Phase 0 until the workflow has an explicit reviewed path for secret handling and rollback.
EOF

echo ""
echo "=== All files ready in $DEPLOY_DIR ==="
ls -la "$DEPLOY_DIR"

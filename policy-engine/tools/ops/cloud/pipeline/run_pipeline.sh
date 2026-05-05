#!/usr/bin/env bash
# =============================================================================
# PolicyOS Production Pipeline Runner (inside tmux on cloud server)
# =============================================================================

set -euo pipefail

usage() {
  cat << 'EOF'
Usage:
  bash tools/ops/cloud/run_pipeline.sh --dry-run
  bash tools/ops/cloud/run_pipeline.sh --yes [--run-id RUN_ID] [--snapshot-root PATH] [--resume]

Options:
  --dry-run           Preview snapshot root, command, and resume mode without running the pipeline
  --yes               Confirm the pipeline run or resume
  --run-id RUN_ID     Stable run identifier; reusing an existing run id resumes its snapshot root
  --snapshot-root P   Explicit snapshot root; if it already exists the script switches to resume mode
  --resume            Require resume semantics against an existing snapshot root
  --topics-dir P      Override topics directory (default: \$POLISYOS_TOPICS_DIR or /data/topics)
  -h, --help          Show this help
EOF
}

generate_run_id() {
  python3 - << 'PY'
from datetime import datetime, timezone
import re
import secrets
import socket

host = re.sub(r"[^a-z0-9]+", "-", socket.gethostname().lower()).strip("-") or "host"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"{host}-{stamp}-{secrets.token_hex(4)}")
PY
}

REPO_ROOT="${POLISYOS_REPO_ROOT:-/opt/polisyos/policy-engine}"
DATA_ROOT="${POLISYOS_DATA_ROOT:-/data}"
TOPICS_DIR="${POLISYOS_TOPICS_DIR:-${DATA_ROOT}/topics}"
DRY_RUN=0
YES=0
RESUME=0
RUN_ID=""
SNAPSHOT_ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      YES=1
      shift
      ;;
    --resume)
      RESUME=1
      shift
      ;;
    --run-id)
      RUN_ID="${2:?--run-id requires a value}"
      shift 2
      ;;
    --snapshot-root)
      SNAPSHOT_ROOT="${2:?--snapshot-root requires a value}"
      shift 2
      ;;
    --topics-dir)
      TOPICS_DIR="${2:?--topics-dir requires a value}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$DRY_RUN" -eq 0 && "$YES" -eq 0 ]]; then
  echo "ERROR: refusing to run blindly. Pass --dry-run for preview or --yes to execute." >&2
  exit 2
fi

cd "$REPO_ROOT"

if [[ ! -d .venv ]]; then
  echo "ERROR: .venv not found in $REPO_ROOT" >&2
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
  echo "Loaded .env"
else
  echo "ERROR: .env not found in $REPO_ROOT" >&2
  exit 1
fi

export PYTHONPATH=src
export PYTHONUNBUFFERED=1

TOPICS_DIR="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$TOPICS_DIR")"
if [[ ! -d "$TOPICS_DIR" ]]; then
  echo "ERROR: topics directory not found: $TOPICS_DIR" >&2
  exit 1
fi

TOPICS_FILE="$(find "$TOPICS_DIR" -maxdepth 1 -type f -name 'relevant_topics_*.csv' | sort | head -1)"
if [[ -z "$TOPICS_FILE" ]]; then
  echo "ERROR: No relevant_topics_*.csv found in $TOPICS_DIR" >&2
  exit 1
fi

TOPIC_COUNT="$(python3 -c 'import sys; from pathlib import Path; print(max(sum(1 for _ in Path(sys.argv[1]).open("r", encoding="utf-8")) - 1, 0))' "$TOPICS_FILE")"
echo "Topics file: $TOPICS_FILE ($TOPIC_COUNT topics)"

KEY_COUNT=0
for var in GONKA_API_KEY GONKA_API_KEY_1 GONKA_API_KEY_2 GONKA_API_KEY_3 GONKA_API_KEY_4; do
  if [[ -n "${!var:-}" ]]; then
    KEY_COUNT=$((KEY_COUNT + 1))
  fi
done
echo "Gonka API keys: $KEY_COUNT"

if [[ "$KEY_COUNT" -eq 0 ]]; then
  echo "ERROR: No Gonka API keys found in .env" >&2
  exit 1
fi

if [[ -z "$SNAPSHOT_ROOT" ]]; then
  if [[ -n "$RUN_ID" ]]; then
    SNAPSHOT_ROOT="${DATA_ROOT}/output/policyos_snapshot_${RUN_ID}"
  else
    RUN_ID="$(generate_run_id)"
    SNAPSHOT_ROOT="${DATA_ROOT}/output/policyos_snapshot_${RUN_ID}"
  fi
fi

SNAPSHOT_ROOT="$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve(strict=False))' "$SNAPSHOT_ROOT")"
if [[ -z "$RUN_ID" ]]; then
  RUN_ID="$(basename "$SNAPSHOT_ROOT")"
  RUN_ID="${RUN_ID#policyos_snapshot_}"
fi

if [[ -d "$SNAPSHOT_ROOT" ]]; then
  RESUME=1
fi

if [[ "$RESUME" -eq 1 && ! -d "$SNAPSHOT_ROOT" ]]; then
  echo "ERROR: --resume requires an existing snapshot root: $SNAPSHOT_ROOT" >&2
  exit 1
fi

if [[ -d "$SNAPSHOT_ROOT" && "$RESUME" -eq 0 ]]; then
  echo "ERROR: snapshot root already exists. Re-run with --resume or choose a new --run-id/--snapshot-root." >&2
  exit 1
fi

CMD=(
  python3 -m polisyos.data_forge.domains.academic.cli run
  --snapshot-root "$SNAPSHOT_ROOT"
  --run-id "$RUN_ID"
  --topics-dir "$TOPICS_DIR"
  --target-per-topic 500
  --article-prefetch-candidates-per-topic 800
  --article-target-fulltext-per-topic 50
  --fulltext-acquisition-mode v7_http_metadata
  --fulltext-metadata-resolvers-enabled
  --fulltext-metadata-resolver-order "unpaywall,crossref,semanticscholar"
  --fulltext-shared-cache-dir "${DATA_ROOT}/cache"
  --fulltext-unpaywall-email "${UNPAYWALL_EMAIL:-}"
  --fulltext-metadata-timeout-seconds 20
  --fulltext-max-candidate-urls-per-work 20
  --fulltext-min-usable-chars 1500
  --fulltext-min-soft-usable-chars 700
  --fulltext-soft-usable-requires-section-cues
  --openalex-max-rps 10
  --openalex-max-concurrent 5
  --openalex-per-page 200
  --article-max-completion-tokens 8192
  --article-evidence-bundle-sentence-budget 28
  --fulltext-max-concurrent-fetches 16
  --article-max-concurrent-llm 40
  --article-rate-limit-rps 9
  --article-max-retries 8
  --article-connect-timeout-seconds 15
  --article-read-timeout-seconds 180
  --article-total-timeout-seconds 240
  --provider-circuit-breaker-failures 8
  --provider-circuit-breaker-reset-seconds 90
  --track-b-enabled
  --track-c-enabled
  --transport-target-country-codes UA
  --stages "topic_select,harvest,parse,resolve_extract,merge_dedup,graph_load,graph_index,transport_score,qc,publish"
)

if [[ "$RESUME" -eq 1 ]]; then
  CMD+=(--resume)
fi

echo ""
echo "=== Pipeline Preview ==="
echo "  Run ID:      $RUN_ID"
echo "  Topics:      $TOPIC_COUNT"
echo "  Gonka keys:  $KEY_COUNT"
echo "  Snapshot:    $SNAPSHOT_ROOT"
echo "  Resume:      $([[ "$RESUME" -eq 1 ]] && echo yes || echo no)"
printf '  Command:     %q' "${CMD[0]}"
for ((i = 1; i < ${#CMD[@]}; i++)); do
  printf ' %q' "${CMD[$i]}"
done
printf '\n'

if [[ "$DRY_RUN" -eq 1 ]]; then
  exit 0
fi

mkdir -p "$SNAPSHOT_ROOT"

echo ""
echo "=== Starting PRODUCTION pipeline ==="
echo "  Run ID:      $RUN_ID"
echo "  Topics:      $TOPIC_COUNT"
echo "  Gonka keys:  $KEY_COUNT"
echo "  Snapshot:    $SNAPSHOT_ROOT"
echo "  Resume:      $([[ "$RESUME" -eq 1 ]] && echo yes || echo no)"
echo "  Started:     $(date)"
echo ""

TEE_ARGS=()
if [[ "$RESUME" -eq 1 ]]; then
  TEE_ARGS+=(-a)
fi

if "${CMD[@]}" 2>&1 | tee "${TEE_ARGS[@]}" "$SNAPSHOT_ROOT/pipeline.log"; then
  echo ""
  echo "=== Pipeline finished ==="
  echo "  Ended:    $(date)"
  echo "  Snapshot: $SNAPSHOT_ROOT"
else
  exit_code=$?
  echo ""
  echo "=== Pipeline failed ===" >&2
  echo "  Ended:    $(date)" >&2
  echo "  Snapshot: $SNAPSHOT_ROOT" >&2
  exit "$exit_code"
fi

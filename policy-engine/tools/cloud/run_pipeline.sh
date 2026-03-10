#!/bin/bash
# =============================================================================
# PolicyOS Production Pipeline Runner (inside tmux on cloud server)
# Usage: bash run_pipeline.sh
# =============================================================================
set -euo pipefail

cd /opt/polisyos/policy-engine
source .venv/bin/activate

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "Loaded .env"
else
    echo "ERROR: .env not found"
    exit 1
fi

export PYTHONPATH=src
export PYTHONUNBUFFERED=1

# Validate topics directory (load_topics looks for relevant_topics_*.csv)
TOPICS_DIR="/data/topics"
TOPICS_FILE=$(ls "$TOPICS_DIR"/relevant_topics_*.csv 2>/dev/null | head -1)
if [ -z "$TOPICS_FILE" ]; then
    echo "ERROR: No relevant_topics_*.csv found in $TOPICS_DIR"
    exit 1
fi

TOPIC_COUNT=$(($(wc -l < "$TOPICS_FILE") - 1))
echo "Topics file: $TOPICS_FILE ($TOPIC_COUNT topics)"

# Validate Gonka keys
KEY_COUNT=0
for var in GONKA_API_KEY GONKA_API_KEY_1 GONKA_API_KEY_2 GONKA_API_KEY_3 GONKA_API_KEY_4; do
    if [ -n "${!var:-}" ]; then
        KEY_COUNT=$((KEY_COUNT + 1))
    fi
done
echo "Gonka API keys: $KEY_COUNT"

if [ "$KEY_COUNT" -eq 0 ]; then
    echo "ERROR: No Gonka API keys found in .env"
    exit 1
fi

# Generate snapshot path
RUN_ID="$(hostname)-$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_ROOT="/data/output/policyos_snapshot_${RUN_ID}"
mkdir -p "$SNAPSHOT_ROOT"

echo ""
echo "=== Starting PRODUCTION pipeline ==="
echo "  Run ID:      $RUN_ID"
echo "  Topics:      $TOPIC_COUNT"
echo "  Gonka keys:  $KEY_COUNT"
echo "  Snapshot:    $SNAPSHOT_ROOT"
echo "  Started:     $(date)"
echo ""

python3 -m polisyos.academic.batch.cli run \
  --snapshot-root "$SNAPSHOT_ROOT" \
  --topics-dir "$TOPICS_DIR" \
  --target-per-topic 500 \
  --article-prefetch-candidates-per-topic 800 \
  --article-target-fulltext-per-topic 50 \
  --fulltext-acquisition-mode v7_http_metadata \
  --fulltext-metadata-resolvers-enabled \
  --fulltext-metadata-resolver-order unpaywall,crossref,semanticscholar \
  --fulltext-shared-cache-dir /data/cache \
  --fulltext-unpaywall-email "${UNPAYWALL_EMAIL:-}" \
  --fulltext-metadata-timeout-seconds 20 \
  --fulltext-max-candidate-urls-per-work 20 \
  --fulltext-min-usable-chars 1500 \
  --fulltext-min-soft-usable-chars 700 \
  --fulltext-soft-usable-requires-section-cues \
  --openalex-max-rps 10 \
  --openalex-max-concurrent 5 \
  --openalex-per-page 200 \
  --article-max-completion-tokens 8192 \
  --article-evidence-bundle-sentence-budget 28 \
  --fulltext-max-concurrent-fetches 16 \
  --article-max-concurrent-llm 40 \
  --article-rate-limit-rps 9 \
  --article-max-retries 8 \
  --article-connect-timeout-seconds 15 \
  --article-read-timeout-seconds 180 \
  --article-total-timeout-seconds 240 \
  --provider-circuit-breaker-failures 8 \
  --provider-circuit-breaker-reset-seconds 90 \
  --track-b-enabled \
  --track-c-enabled \
  --transport-target-country-codes UA \
  --stages topic_select,harvest,parse,resolve_extract,merge_dedup,graph_load,graph_index,transport_score,qc,publish \
  2>&1 | tee "$SNAPSHOT_ROOT/pipeline.log"

echo ""
echo "=== Pipeline finished ==="
echo "  Ended:    $(date)"
echo "  Snapshot: $SNAPSHOT_ROOT"

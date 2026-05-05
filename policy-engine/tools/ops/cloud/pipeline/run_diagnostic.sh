#!/bin/bash
# =============================================================================
# PolicyOS Diagnostic Pipeline Run
# Purpose: Quick informative run after code changes to verify pipeline health
# Expected duration: 20-40 minutes
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

# Validate topics
TOPICS_DIR="/data/topics"
TOPIC_FILE_COUNT=$(ls "$TOPICS_DIR"/relevant_topics_*.csv 2> /dev/null | wc -l)
if [ "$TOPIC_FILE_COUNT" -eq 0 ]; then
  echo "ERROR: No relevant_topics_*.csv found in $TOPICS_DIR"
  exit 1
fi
echo "Topics directory: $TOPICS_DIR ($TOPIC_FILE_COUNT domain files)"

# Count Gonka keys
KEY_COUNT=0
for var in GONKA_API_KEY GONKA_API_KEY_1 GONKA_API_KEY_2 GONKA_API_KEY_3 GONKA_API_KEY_4 GONKA_API_KEY_5; do
  if [ -n "${!var:-}" ]; then
    KEY_COUNT=$((KEY_COUNT + 1))
  fi
done
echo "Gonka API keys: $KEY_COUNT"

# Generate snapshot path
RUN_ID="diag-$(date -u +%Y%m%dT%H%M%SZ)"
SNAPSHOT_ROOT="/data/output/policyos_snapshot_${RUN_ID}"
mkdir -p "$SNAPSHOT_ROOT"

echo ""
echo "=== Starting DIAGNOSTIC pipeline run ==="
echo "  Run ID:      $RUN_ID"
echo "  Gonka keys:  $KEY_COUNT"
echo "  Snapshot:    $SNAPSHOT_ROOT"
echo "  Started:     $(date)"
echo ""
echo "=== LLM Parameters ==="
echo "  Concurrent per key:  28  (70% of 40 limit)"
echo "  RPS per key:         6.5 (72% of 9 limit)"
echo "  5 keys → 140 concurrent, ~32.5 effective RPS"
echo "  Circuit breaker:     6 failures / 60s reset"
echo ""
echo "=== Sample Parameters ==="
echo "  Topics:              8   (diverse policy domains)"
echo "  Works per topic:     100 (enough for statistical signal)"
echo "  Fulltext target:     50/topic"
echo "  Expected: ~400-600 papers, ~200 with fulltext"
echo ""

python3 -m polisyos.data_forge.domains.academic.cli run \
  --snapshot-root "$SNAPSHOT_ROOT" \
  --topics-dir "$TOPICS_DIR" \
  --topic-limit 8 \
  --target-per-topic 100 \
  --selected-unique-budget 2000 \
  --usable-fulltext-target 500 \
  --article-prefetch-candidates-per-topic 150 \
  --article-target-fulltext-per-topic 50 \
  --fulltext-acquisition-mode v7_http_metadata \
  --fulltext-metadata-resolvers-enabled \
  --fulltext-metadata-resolver-order unpaywall,crossref,semanticscholar \
  --fulltext-shared-cache-dir /data/cache \
  --fulltext-metadata-timeout-seconds 20 \
  --fulltext-max-candidate-urls-per-work 20 \
  --fulltext-min-usable-chars 1500 \
  --fulltext-min-soft-usable-chars 700 \
  --fulltext-soft-usable-requires-section-cues \
  --fulltext-max-concurrent-fetches 12 \
  --openalex-max-rps 8 \
  --openalex-max-concurrent 4 \
  --openalex-per-page 200 \
  --article-max-completion-tokens 8192 \
  --article-evidence-bundle-sentence-budget 28 \
  --article-max-concurrent-llm 28 \
  --article-rate-limit-rps 6.5 \
  --article-max-retries 7 \
  --article-connect-timeout-seconds 15 \
  --article-read-timeout-seconds 180 \
  --article-total-timeout-seconds 240 \
  --provider-circuit-breaker-failures 6 \
  --provider-circuit-breaker-reset-seconds 60 \
  --track-b-enabled \
  --track-c-enabled \
  --fulltext-max-pdf-pages 50 \
  --fulltext-extract-html-tables \
  --doc-infra-enable-grobid \
  --doc-grobid-base-url http://localhost:8070 \
  --doc-infra-enable-pub2tei \
  --doc-pub2tei-base-url http://localhost:8074 \
  --doc-infra-timeout-seconds 45 \
  --doc-infra-precedence publisher_xml,pdf,text \
  --transport-target-country-codes UA \
  --stages topic_select,harvest,parse,resolve_extract,merge_dedup,claim_adjudicate,resolve_finalize,graph_load,edge_synthesize,graph_index,transport_score,benchmark,qc \
  2>&1 | tee "$SNAPSHOT_ROOT/pipeline.log"

echo ""
echo "=== Diagnostic pipeline finished ==="
echo "  Ended:    $(date)"
echo "  Snapshot: $SNAPSHOT_ROOT"
echo ""
echo "=== Key output files ==="
echo "  Log:       $SNAPSHOT_ROOT/pipeline.log"
echo "  Benchmark: $SNAPSHOT_ROOT/benchmark/"
echo "  QC:        $SNAPSHOT_ROOT/qc/"
echo "  Graph:     $SNAPSHOT_ROOT/graph/"

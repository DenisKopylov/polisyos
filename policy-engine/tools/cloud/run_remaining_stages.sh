#!/bin/bash
# =============================================================================
# PolicyOS — Run remaining academic pipeline stages (post resolve_extract)
# Skips topic_select, harvest, parse, resolve_extract entirely.
# Uses 20 Gonka API keys for parallel LLM adjudication.
# Expected runtime: ~1-2.5 hours on CX53 (16 vCPU / 32 GB)
# =============================================================================
set -euo pipefail

cd /opt/polisyos/policy-engine
source .venv/bin/activate

# Load base environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "OK Loaded .env"
else
    echo "ERROR: .env not found"
    exit 1
fi

# Clear any keys from .env first
unset GONKA_API_KEY 2>/dev/null || true
for i in $(seq 1 30); do unset "GONKA_API_KEY_$i" 2>/dev/null || true; done

# Account 1: repairkyiv4@gmail.com
export GONKA_API_KEY_1=gp-2Tm79IvYtWL00SdmUwVF39f36AXGZUaV
export GONKA_API_KEY_2=gp-FvlpRS7YrpjJSHagciFbsL7wQ7ZeGNhU
export GONKA_API_KEY_3=gp-a6ccyzHXlDwsRmQuLN99875CECqadKSN
export GONKA_API_KEY_4=gp-0Cc5RcerGXiDRqMpjzKrC3fJSd7xkb9A
export GONKA_API_KEY_5=gp-VvKFSMTw72Bo9myCten29ie9f8ufqEEo
# Account 2: skvidvard167m@gmail.com
export GONKA_API_KEY_6=gp-897otZsYtVPSD0gTaDKEFG5DmjrWjKmL
export GONKA_API_KEY_7=gp-uTfUQuOvAm2AFRRhy7lNOVxsKf2VXrRE
export GONKA_API_KEY_8=gp-TyE5pCd1CnHYUuMRfjVd99MhFKU5M9m5
export GONKA_API_KEY_9=gp-R4PJtXfN0CNamUoyax0Omb6WgceKPXOQ
export GONKA_API_KEY_10=gp-BbFsoECE8hinAUg6KZjxLteXDAY9Hok5
# Account 3: natashka2201@gmail.com
export GONKA_API_KEY_11=gp-bIllBq3TCbGNzyHElrT5MCj7wtYN14ha
export GONKA_API_KEY_12=gp-PlhDwITs6EiY2TWKiL7i7KsFU3Y6Krph
export GONKA_API_KEY_13=gp-Xys3QWv4vPuCuzO0BXrQ2OsIwxCDnmdE
export GONKA_API_KEY_14=gp-wTrICdLUKvfRgAcgdTom405iarMzEBNS
# Account 4: nironovsergej01@gmail.com
export GONKA_API_KEY_15=gp-n2DdgdiaJQruDHz9CGv24zhhW1Im1DUF
export GONKA_API_KEY_16=gp-NSI9JMImTwfooEDGHlgtp5jyoJSHYXeO
export GONKA_API_KEY_17=gp-4sNFOm5RwWtH0lGngsi4K0WlpI3wc9IU
export GONKA_API_KEY_18=gp-reikH3visbvdd5ixP2EtI6sYMkEiRcKn
export GONKA_API_KEY_19=gp-YeJn3fZQ09TeayxYeU3Y74XmjsghOMN8

export PYTHONPATH=src
export PYTHONUNBUFFERED=1

# Maximize server resources (16 vCPU / 32 GB RAM)
export DUCKDB_MEMORY_LIMIT="20GB"
export DUCKDB_THREADS=14
export OMP_NUM_THREADS=14
export OPENBLAS_NUM_THREADS=14
export NUMEXPR_NUM_THREADS=14

SNAPSHOT_ROOT="/data/output/policyos_fullprod_1000t_20260324"
LOG="$SNAPSHOT_ROOT/pipeline_remaining.log"

# Pre-flight checks
if [ ! -f "$SNAPSHOT_ROOT/academic/article_extraction_results.jsonl" ]; then
    echo "ERROR: article_extraction_results.jsonl not found in $SNAPSHOT_ROOT/academic/"
    exit 1
fi
EXTRACTION_LINES=$(wc -l < "$SNAPSHOT_ROOT/academic/article_extraction_results.jsonl")
echo "OK article_extraction_results.jsonl: $EXTRACTION_LINES lines"

# Count loaded keys
KEY_COUNT=0
for i in $(seq 1 30); do
    varname="GONKA_API_KEY_$i"
    val="${!varname:-}"
    [ -n "$val" ] && KEY_COUNT=$((KEY_COUNT + 1))
done
echo "OK Gonka API keys loaded: $KEY_COUNT"

echo ""
echo "=========================================="
echo "  REMAINING STAGES (post merge_dedup)"
echo "=========================================="
echo "  Snapshot:   $SNAPSHOT_ROOT"
echo "  Gonka keys: $KEY_COUNT (accounts 1-4)"
echo "  LLM conc:   12, RPS/key: 0.7"
echo "  Stages:     claim_adjudicate -> publish"
echo "  Started:    $(date)"
echo "=========================================="
echo ""

python3 -m polisyos.academic.batch.cli run \
  --snapshot-root "$SNAPSHOT_ROOT" \
  --topics-dir /data/topics \
  --target-per-topic 5000 \
  --article-target-fulltext-per-topic 1000 \
  --stages claim_adjudicate,conflict_resolve,graph_load,edge_synthesize,graph_index,transport_score,benchmark,qc,publish \
  --resume \
  --no-fail-fast \
  --article-max-concurrent-llm 12 \
  --article-rate-limit-rps 0.7 \
  --article-max-retries 3 \
  --transport-target-country-codes UA \
  --track-b-enabled \
  --track-c-enabled \
  2>&1 | tee -a "$LOG"

EXIT_CODE=$?
echo ""
echo "=========================================="
echo "  Pipeline remaining stages finished"
echo "  Exit code: $EXIT_CODE"
echo "  Ended:     $(date)"
echo "  Snapshot:  $SNAPSHOT_ROOT"
echo "=========================================="

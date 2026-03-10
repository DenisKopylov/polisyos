#!/bin/bash
# =============================================================================
# Prepare topic shards and .env files for 3-server deployment
#
# Usage: bash prepare_shards.sh /path/to/filtered_1000_topics.csv
#
# Creates in ./cloud_deploy/:
#   topics_shard_1.csv, topics_shard_2.csv, topics_shard_3.csv
#   .env.server_1, .env.server_2, .env.server_3
# =============================================================================
set -euo pipefail

TOPICS_CSV="${1:?Usage: bash prepare_shards.sh /path/to/filtered_topics.csv}"

if [ ! -f "$TOPICS_CSV" ]; then
    echo "ERROR: File not found: $TOPICS_CSV"
    exit 1
fi

TOTAL=$(($(wc -l < "$TOPICS_CSV") - 1))
echo "Input: $TOPICS_CSV ($TOTAL topics)"

DEPLOY_DIR="$(pwd)/cloud_deploy"
mkdir -p "$DEPLOY_DIR"

# --- 1. Split topics into 3 shards ---
echo ""
echo "=== Splitting topics into 3 shards ==="

HEADER=$(head -1 "$TOPICS_CSV")
SHARD_SIZE=$(( (TOTAL + 2) / 3 ))  # round up

# Shuffle for even distribution across policy domains
tail -n +2 "$TOPICS_CSV" | sort -R > "$DEPLOY_DIR/_shuffled.tmp"

split -l "$SHARD_SIZE" "$DEPLOY_DIR/_shuffled.tmp" "$DEPLOY_DIR/_chunk_"

i=1
for chunk in "$DEPLOY_DIR"/_chunk_*; do
    OUT="$DEPLOY_DIR/topics_shard_${i}.csv"
    echo "$HEADER" > "$OUT"
    cat "$chunk" >> "$OUT"
    COUNT=$(($(wc -l < "$OUT") - 1))
    echo "  Shard $i: $COUNT topics -> $OUT"
    rm "$chunk"
    i=$((i + 1))
done
rm -f "$DEPLOY_DIR/_shuffled.tmp"

# --- 2. Create .env files for each server ---
echo ""
echo "=== Creating .env files ==="
echo "NOTE: Fill in UNPAYWALL_EMAIL below if needed."

# Server 1 — repairkyiv4@gmail.com
cat > "$DEPLOY_DIR/.env.server_1" << 'ENV1'
# Server 1 — repairkyiv4@gmail.com
GONKA_API_KEY=gp-2Tm79IvYtWL00SdmUwVF39f36AXGZUaV
GONKA_API_KEY_1=gp-FvlpRS7YrpjJSHagciFbsL7wQ7ZeGNhU
GONKA_API_KEY_2=gp-a6ccyzHXlDwsRmQuLN99875CECqadKSN
GONKA_API_KEY_3=gp-0Cc5RcerGXiDRqMpjzKrC3fJSd7xkb9A
GONKA_API_KEY_4=gp-VvKFSMTw72Bo9myCten29ie9f8ufqEEo

UNPAYWALL_EMAIL=repairkyiv4@gmail.com

# Linux VPS settings (no thermal throttling, no Metal GPU)
JAX_PLATFORM_NAME=cpu
XLA_PYTHON_CLIENT_PREALLOCATE=false
DUCKDB_MEMORY_LIMIT=3GB
DUCKDB_THREADS=2
OMP_NUM_THREADS=2
OPENBLAS_NUM_THREADS=2
ENV1

# Server 2 — skvidvard167m@gmail.com
cat > "$DEPLOY_DIR/.env.server_2" << 'ENV2'
# Server 2 — skvidvard167m@gmail.com
GONKA_API_KEY=gp-897otZsYtVPSD0gTaDKEFG5DmjrWjKmL
GONKA_API_KEY_1=gp-uTfUQuOvAm2AFRRhy7lNOVxsKf2VXrRE
GONKA_API_KEY_2=gp-TyE5pCd1CnHYUuMRfjVd99MhFKU5M9m5
GONKA_API_KEY_3=gp-R4PJtXfN0CNamUoyax0Omb6WgceKPXOQ
GONKA_API_KEY_4=gp-BbFsoECE8hinAUg6KZjxLteXDAY9Hok5

UNPAYWALL_EMAIL=skvidvard167m@gmail.com

# Linux VPS settings
JAX_PLATFORM_NAME=cpu
XLA_PYTHON_CLIENT_PREALLOCATE=false
DUCKDB_MEMORY_LIMIT=3GB
DUCKDB_THREADS=2
OMP_NUM_THREADS=2
OPENBLAS_NUM_THREADS=2
ENV2

# Server 3 — natashka2201@gmail.com
cat > "$DEPLOY_DIR/.env.server_3" << 'ENV3'
# Server 3 — natashka2201@gmail.com
GONKA_API_KEY=gp-bIllBq3TCbGNzyHElrT5MCj7wtYN14ha
GONKA_API_KEY_1=gp-PlhDwITs6EiY2TWKiL7i7KsFU3Y6Krph
GONKA_API_KEY_2=gp-3Rv2v1ggQzoy81mT8RMDY3AOsFyI4feс
GONKA_API_KEY_3=gp-Xys3QWv4vPuCuzO0BXrQ2OsIwxCDnmdE
GONKA_API_KEY_4=gp-wTrICdLUKvfRgAcgdTom405iarMzEBNS

UNPAYWALL_EMAIL=natashka2201@gmail.com

# Linux VPS settings
JAX_PLATFORM_NAME=cpu
XLA_PYTHON_CLIENT_PREALLOCATE=false
DUCKDB_MEMORY_LIMIT=3GB
DUCKDB_THREADS=2
OMP_NUM_THREADS=2
OPENBLAS_NUM_THREADS=2
ENV3

echo "  Created .env.server_1 (repairkyiv4)"
echo "  Created .env.server_2 (skvidvard167m)"
echo "  Created .env.server_3 (natashka2201)"

# --- 3. Create deploy helper ---
cat > "$DEPLOY_DIR/deploy_to_server.sh" << 'DEPLOY'
#!/bin/bash
# Upload everything to one server.
# Usage: bash deploy_to_server.sh <server_number> <server_ip>
# Example: bash deploy_to_server.sh 1 49.12.34.56
set -euo pipefail

N="${1:?Usage: bash deploy_to_server.sh <1|2|3> <server_ip>}"
IP="${2:?Usage: bash deploy_to_server.sh <1|2|3> <server_ip>}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying shard $N to $IP ==="

# Upload project code
echo "[1/5] Uploading project code (this takes a few minutes first time)..."
rsync -azP --exclude='.venv' --exclude='__pycache__' --exclude='.git' \
  --exclude='node_modules' --exclude='storybook-static' --exclude='test-results' \
  --exclude='output' --exclude='data' \
  "$(dirname "$(dirname "$DIR")")/" "root@${IP}:/opt/polisyos/policy-engine/"

# Upload .env
echo "[2/5] Uploading .env..."
scp "$DIR/.env.server_${N}" "root@${IP}:/opt/polisyos/policy-engine/.env"

# Upload topics shard
echo "[3/5] Uploading topics shard..."
ssh "root@${IP}" "mkdir -p /data/topics"
scp "$DIR/topics_shard_${N}.csv" "root@${IP}:/data/topics/topics.csv"

# Upload shared cache (if exists)
CACHE_DIR="${CACHE_PATH:-}"
if [ -d "$CACHE_DIR" ]; then
    echo "[4/5] Uploading shared cache (can take a while)..."
    rsync -azP "$CACHE_DIR/" "root@${IP}:/data/cache/"
else
    echo "[4/5] No cache dir specified (set CACHE_PATH env var to upload cache)"
    ssh "root@${IP}" "mkdir -p /data/cache"
fi

# Upload and run setup script
echo "[5/5] Running server setup..."
scp "$DIR/../setup_server.sh" "root@${IP}:/root/setup_server.sh"
ssh "root@${IP}" "bash /root/setup_server.sh"

echo ""
echo "=== Server $N ($IP) ready! ==="
echo ""
echo "To start the pipeline:"
echo "  ssh root@${IP}"
echo "  tmux new -s pipeline"
echo "  bash /opt/polisyos/policy-engine/tools/cloud/run_pipeline.sh"
echo ""
echo "To detach from tmux:  Ctrl+B, then D"
echo "To reconnect later:   ssh root@${IP} -t 'tmux attach -t pipeline'"
DEPLOY

chmod +x "$DEPLOY_DIR/deploy_to_server.sh"

echo ""
echo "=== All files ready in $DEPLOY_DIR/ ==="
echo ""
echo "Files created:"
ls -la "$DEPLOY_DIR/"
echo ""
echo "Next: deploy to each server with:"
echo "  cd $DEPLOY_DIR"
echo "  bash deploy_to_server.sh 1 <SERVER_1_IP>"
echo "  bash deploy_to_server.sh 2 <SERVER_2_IP>"
echo "  bash deploy_to_server.sh 3 <SERVER_3_IP>"

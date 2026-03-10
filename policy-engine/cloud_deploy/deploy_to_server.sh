#!/bin/bash
# =============================================================================
# Deploy shard to a Hetzner server.
# Usage: bash deploy_to_server.sh <server_number> <server_ip>
# Example: bash deploy_to_server.sh 1 49.12.34.56
#
# Optional: set CACHE_PATH to upload shared cache:
#   CACHE_PATH=/path/to/ext_shared_cache bash deploy_to_server.sh 1 49.12.34.56
# =============================================================================
set -euo pipefail

N="${1:?Usage: bash deploy_to_server.sh <1|2|3> <server_ip>}"
IP="${2:?Usage: bash deploy_to_server.sh <1|2|3> <server_ip>}"
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$DIR")"

echo "=== Deploying shard $N to root@${IP} ==="
echo ""

# --- 0. Wait for cloud-init to finish ---
echo "[0/5] Checking cloud-init status..."
for attempt in 1 2 3 4 5 6; do
    if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "root@${IP}" "test -f /root/cloud-init-done.txt" 2>/dev/null; then
        echo "  Cloud-init complete!"
        break
    fi
    if [ "$attempt" -eq 6 ]; then
        echo "  WARNING: cloud-init may not be done yet. Continuing anyway..."
    else
        echo "  Cloud-init not ready, waiting 30s... (attempt $attempt/6)"
        sleep 30
    fi
done

# --- 1. Upload project code ---
echo "[1/5] Uploading project code..."
ssh "root@${IP}" "mkdir -p /opt/polisyos"
rsync -azP --timeout=60 \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='storybook-static' \
    --exclude='test-results' \
    --exclude='output' \
    --exclude='data' \
    --exclude='cloud_deploy' \
    --exclude='coverage' \
    --exclude='.mypy_cache' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    "$PROJECT_ROOT/" "root@${IP}:/opt/polisyos/policy-engine/"

# --- 2. Upload .env ---
echo "[2/5] Uploading .env for account $N..."
scp "$DIR/.env.server_${N}" "root@${IP}:/opt/polisyos/policy-engine/.env"

# --- 3. Upload topics shard ---
echo "[3/5] Uploading topics shard $N..."
ssh "root@${IP}" "mkdir -p /data/topics"
scp "$DIR/relevant_topics_shard_${N}.csv" "root@${IP}:/data/topics/relevant_topics_shard.csv"
TOPIC_COUNT=$(ssh "root@${IP}" "wc -l < /data/topics/relevant_topics_shard.csv" 2>/dev/null || echo "?")
echo "  Uploaded $TOPIC_COUNT topics"

# --- 4. Upload shared cache (optional) ---
CACHE_DIR="${CACHE_PATH:-}"
if [ -n "$CACHE_DIR" ] && [ -d "$CACHE_DIR" ]; then
    echo "[4/5] Uploading shared cache from $CACHE_DIR..."
    ssh "root@${IP}" "mkdir -p /data/cache"
    rsync -azP --timeout=120 "$CACHE_DIR/" "root@${IP}:/data/cache/"
else
    echo "[4/5] No cache (set CACHE_PATH to upload). Creating empty cache dir..."
    ssh "root@${IP}" "mkdir -p /data/cache"
fi

# --- 5. Install Python + dependencies ---
echo "[5/5] Setting up Python environment on server..."
ssh "root@${IP}" 'bash -s' << 'SETUP'
set -euo pipefail

cd /opt/polisyos/policy-engine

# Create venv if not exists
if [ ! -d .venv ]; then
    echo "  Creating Python venv..."
    python3.12 -m venv .venv
fi

source .venv/bin/activate

# jax-metal is macOS-only (Apple Silicon Metal GPU) — remove it on Linux
if [ "$(uname)" = "Linux" ]; then
    echo "  Removing macOS-only jax-metal from pyproject.toml..."
    sed -i '/"jax-metal/d' pyproject.toml
fi

echo "  Installing dependencies (2-3 min)..."
pip install --upgrade pip -q 2>&1 | tail -1
pip install -e ".[dev,test,academic-skg]" -q 2>&1 | tail -3

# Quick validation
python -c "import aiohttp, duckdb, pydantic, orjson; print('  Core packages: OK')"
python -c "from polisyos.academic.batch.cli import main; print('  Pipeline CLI: OK')"

echo ""
echo "  Python: $(python --version)"
echo "  Disk:   $(df -h / | tail -1 | awk '{print $4}') free"
echo "  RAM:    $(free -h | grep Mem | awk '{print $2}') total"
SETUP

echo ""
echo "=========================================="
echo "  Server $N ($IP) is READY!"
echo "=========================================="
echo ""
echo "To start the pipeline:"
echo "  ssh root@${IP}"
echo "  tmux new -s pipeline"
echo "  bash /opt/polisyos/policy-engine/tools/cloud/run_pipeline.sh"
echo ""
echo "Then detach: Ctrl+B, D"
echo "Reconnect later: ssh root@${IP} -t 'tmux attach -t pipeline'"
echo ""

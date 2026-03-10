#!/bin/bash
# =============================================================================
# PolicyOS Cloud Server Setup Script
# Run on each Hetzner VPS after first SSH connection.
# Usage: bash setup_server.sh
# =============================================================================
set -euo pipefail

echo "=== PolicyOS Server Setup ==="
echo "Detected OS: $(uname -s) $(uname -m)"

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3.12 python3.12-venv python3.12-dev \
  python3-pip git tmux htop curl wget \
  build-essential libffi-dev libssl-dev \
  > /dev/null 2>&1

# --- 2. Create working directories ---
echo "[2/6] Creating directories..."
mkdir -p /opt/polisyos /data/output /data/cache /data/topics

# --- 3. Clone repo (or copy) ---
echo "[3/6] Setting up project..."
if [ -d /opt/polisyos/policy-engine ]; then
    echo "  Project already exists, pulling latest..."
    cd /opt/polisyos && git pull || true
else
    echo "  Cloning repository..."
    echo "  NOTE: If repo is private, you'll need to set up SSH key or use token."
    echo "  Alternative: scp the project from your Mac (see guide)."
    echo ""
    echo "  For now, skipping git clone."
    echo "  Upload the project with: scp -r policy-engine/ root@SERVER_IP:/opt/polisyos/"
fi

# --- 4. Python virtual environment ---
echo "[4/6] Setting up Python environment..."
cd /opt/polisyos/policy-engine

python3.12 -m venv .venv
source .venv/bin/activate

echo "  Installing dependencies (this takes 2-3 minutes)..."
# On Linux: skip jax-metal (macOS only), install CPU jax
pip install --upgrade pip > /dev/null 2>&1
pip install -e ".[dev,test,academic-skg]" 2>&1 | tail -5

# Verify key packages
python -c "import aiohttp, openai, duckdb, pydantic, orjson; print('  Core packages OK')"
python -c "from polisyos.academic.batch.cli import main; print('  Pipeline CLI OK')"

# --- 5. Environment variables template ---
echo "[5/6] Checking .env file..."
if [ -f /opt/polisyos/policy-engine/.env ]; then
    echo "  .env already exists"
else
    echo "  No .env found. You need to create one (see guide)."
fi

# --- 6. tmux configuration (nice-to-have) ---
echo "[6/6] Configuring tmux..."
cat > /root/.tmux.conf << 'TMUX'
set -g history-limit 50000
set -g mouse on
set -g status-right '%H:%M %d-%b'
TMUX

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Upload .env file:  scp .env.server_N root@THIS_SERVER:/opt/polisyos/policy-engine/.env"
echo "  2. Upload topics:     scp topics_shard_N.csv root@THIS_SERVER:/data/topics/topics.csv"
echo "  3. Upload cache:      rsync -avz ext_shared_cache/ root@THIS_SERVER:/data/cache/"
echo "  4. Start pipeline:    bash /opt/polisyos/policy-engine/tools/cloud/run_pipeline.sh"
echo ""

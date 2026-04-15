#!/usr/bin/env bash
# =============================================================================
# Check pipeline progress on remote servers.
# Usage: bash check_progress.sh <ip1> [ip2 ...]
# =============================================================================

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash tools/cloud/check_progress.sh <ip1> [ip2 ...]
EOF
}

if [[ $# -eq 0 ]]; then
  usage >&2
  exit 2
fi

echo "=== Pipeline Progress Check ($(date)) ==="
echo ""

IPS=("$@")
for index in "${!IPS[@]}"; do
  ip="${IPS[$index]}"
  server_no=$((index + 1))

  echo "--- Server ${server_no} (${ip}) ---"

  if ! tmux_status="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "root@${ip}" "bash -lc 'if tmux has-session -t pipeline 2>/dev/null; then echo RUNNING; else echo STOPPED; fi'")"; then
    echo "  CONNECTION FAILED"
    echo ""
    continue
  fi
  echo "  Status: ${tmux_status}"

  if ! server_report="$(ssh -o BatchMode=yes -o ConnectTimeout=5 "root@${ip}" "bash -s" <<'REMOTE'
set -euo pipefail

log_path="$(find /data/output -name pipeline.log -type f 2>/dev/null | sort | tail -1 || true)"
if [[ -n "$log_path" && -f "$log_path" ]]; then
  echo "  Log tail:"
  tail -3 "$log_path" | sed 's/^/    /'
  if grep -q "Done in" "$log_path" 2>/dev/null; then
    echo "  FINISHED!"
    grep "Done in" "$log_path" | tail -1 | sed 's/^/    /'
  fi
else
  echo "  No log file yet"
fi

if [[ -d /data/output ]]; then
  echo "  Disk: $(du -sh /data/output 2>/dev/null | cut -f1 || echo unknown) used"
else
  echo "  Disk: output directory missing"
fi

if command -v free >/dev/null 2>&1; then
  echo "  RAM:  $(free -h 2>/dev/null | awk '/^Mem:/ {print $3\"/\"$2\" used\"}' || echo unavailable)"
else
  echo "  RAM:  unavailable"
fi

if command -v uptime >/dev/null 2>&1; then
  echo "  Load: $(uptime | sed 's/.*load average/load/')"
else
  echo "  Load: unavailable"
fi
REMOTE
)"; then
    echo "  DETAILS UNAVAILABLE"
    echo ""
    continue
  fi

  printf '%s\n' "$server_report"
  echo ""
done

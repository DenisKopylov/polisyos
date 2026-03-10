#!/bin/bash
# =============================================================================
# Check pipeline progress on all 3 servers from your Mac.
# Usage: bash check_progress.sh <ip1> <ip2> <ip3>
# =============================================================================

echo "=== Pipeline Progress Check ($(date)) ==="
echo ""

for i in 1 2 3; do
    IP="${!i:-}"
    if [ -z "$IP" ]; then
        continue
    fi

    echo "--- Server $i ($IP) ---"

    # Check if tmux session is running (pipeline active)
    TMUX_STATUS=$(ssh -o ConnectTimeout=5 "root@${IP}" "tmux has-session -t pipeline 2>/dev/null && echo RUNNING || echo STOPPED" 2>/dev/null)
    if [ $? -ne 0 ]; then
        echo "  CONNECTION FAILED"
        echo ""
        continue
    fi
    echo "  Status: $TMUX_STATUS"

    # Get last 5 lines of pipeline log
    ssh -o ConnectTimeout=5 "root@${IP}" '
        LOG=$(find /data/output -name "pipeline.log" -type f 2>/dev/null | head -1)
        if [ -n "$LOG" ]; then
            echo "  Log tail:"
            tail -3 "$LOG" | sed "s/^/    /"

            # Check for stage timing in log
            if grep -q "Done in" "$LOG" 2>/dev/null; then
                echo "  FINISHED!"
                grep "Done in" "$LOG" | tail -1 | sed "s/^/    /"
            fi
        else
            echo "  No log file yet"
        fi

        # Disk usage
        echo "  Disk: $(du -sh /data/output 2>/dev/null | cut -f1) used"

        # Memory
        echo "  RAM:  $(free -h 2>/dev/null | grep Mem | awk "{print \$3\"/\"\$2\" used\"}")"

        # Load
        echo "  Load: $(uptime | sed "s/.*load average/load/")"
    ' 2>/dev/null

    echo ""
done

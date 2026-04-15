#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BENCH_ROOT="${REPO_ROOT}/benchmarks"
PYTHON="${PYTHON:-python3}"
MODE="${BENCH_MODE:-smoke}"
JSON_ROOT="${BENCH_JSON_ROOT:-${BENCH_ROOT}/_reports/contours-$(date -u +%Y%m%dT%H%M%SZ)}"

mkdir -p "${JSON_ROOT}"

run_lane() {
    local lane_name="$1"
    shift
    local lane_dir="${JSON_ROOT}/${lane_name}"
    mkdir -p "${lane_dir}"
    echo "==> Running ${lane_name}"
    (
        cd "${REPO_ROOT}"
        uv run polisyos-tools benchmarks run-all \
            --mode "${MODE}" \
            --json-dir "${lane_dir}" \
            --quiet \
            "$@"
    )
    "${PYTHON}" "${BENCH_ROOT}/build_release_summary.py" \
        --json-dir "${lane_dir}" \
        --out "${lane_dir}/release_summary.json" >/dev/null
}

run_lane "legacy_floor" --profile air-m2
run_lane "production" --contour production --profile extended
run_lane "academic_public" --contour academic --visibility public --profile extended
run_lane "academic_hidden" --contour academic --visibility hidden_release --profile extended
run_lane "academic_shadow" --contour academic --visibility prod_shadow --profile extended
run_lane "prod_shadow" --contour production --visibility prod_shadow --profile extended

echo "==> Merging top-level release summary"
"${PYTHON}" "${BENCH_ROOT}/build_release_summary.py" \
    --json-dir "${JSON_ROOT}" \
    --out "${JSON_ROOT}/release_summary.json" >/dev/null

echo "Benchmark contour outputs written to ${JSON_ROOT}"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON="${PYTHON:-python3}"
export PYTHONPATH="${REPO_ROOT}/src:${REPO_ROOT}:${PYTHONPATH:-}"

PROFILE="air-m2"
MODE="smoke"
PREPARE=1
QUIET_FLAG="--quiet"
COOLDOWN_S="${BENCH_COOLDOWN_S:-1}"
DATA_ROOT="${REPO_ROOT}/data/raw/benchmarks/local_real"
JSON_DIR="${SCRIPT_DIR}/_reports/local_sota_${PROFILE}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="$2"
            JSON_DIR="${SCRIPT_DIR}/_reports/local_sota_${PROFILE}"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --json-dir)
            JSON_DIR="$2"
            shift 2
            ;;
        --data-root)
            DATA_ROOT="$2"
            shift 2
            ;;
        --skip-prepare)
            PREPARE=0
            shift
            ;;
        --verbose)
            QUIET_FLAG=""
            shift
            ;;
        --cooldown-s)
            COOLDOWN_S="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
RUN_ID="${BENCH_RUN_ID:-local-sota-${PROFILE}-$(date -u +%Y%m%dT%H%M%SZ)}"
ESTIMATOR_PROFILE="${BENCH_ESTIMATOR_PROFILE:-flagship_competitive}"
ESTIMATION_METHOD_PROFILE="${BENCH_ESTIMATION_METHOD_PROFILE:-}"
if [[ -z "${ESTIMATION_METHOD_PROFILE}" ]]; then
    if [[ "${MODE}" == "smoke" ]]; then
        ESTIMATION_METHOD_PROFILE="production_estimation"
    else
        ESTIMATION_METHOD_PROFILE="full_matrix_estimation"
    fi
fi
export BENCH_RUN_ID="${RUN_ID}"
export BENCH_ESTIMATOR_PROFILE="${ESTIMATOR_PROFILE}"
export BENCH_ESTIMATION_METHOD_PROFILE="${ESTIMATION_METHOD_PROFILE}"
export BENCH_PROFILE="${PROFILE}"

if [[ "${PREPARE}" == "1" ]]; then
    "${PYTHON}" "${SCRIPT_DIR}/prepare_real_benchmark_data.py" \
        --profile "${PROFILE}" \
        --data-root "${DATA_ROOT}"
fi

export ACIC_DATA_DIR="${DATA_ROOT}/acic"
export LBIDD_DATA_DIR="${DATA_ROOT}/lbidd"
export REALCAUSE_DATA_DIR="${DATA_ROOT}/realcause"

mkdir -p "${JSON_DIR}"

SUITES=()
while IFS= read -r line; do
    SUITES+=("${line}")
done < <(
    BENCH_PROFILE="${PROFILE}" "${PYTHON}" - <<'PY'
import os
from benchmarks.suite_registry import suites_for_profile

for spec in suites_for_profile(os.environ["BENCH_PROFILE"]):
    print(spec.suite_id)
PY
)

FAILURES=0
PASSED=0
STATUS_ROWS_FILE="$(mktemp)"
trap 'rm -f "${STATUS_ROWS_FILE}"' EXIT

for suite in "${SUITES[@]}"; do
    echo "==> ${suite}"
    if BENCH_RUN_ID="${RUN_ID}" BENCH_ESTIMATOR_PROFILE="${ESTIMATOR_PROFILE}" BENCH_PROFILE="${PROFILE}" \
        bash "${SCRIPT_DIR}/run_all_benchmarks.sh" --mode "${MODE}" --profile "${PROFILE}" --circuit "${suite}" --json-dir "${JSON_DIR}" ${QUIET_FLAG}; then
        PASSED=$((PASSED + 1))
    else
        FAILURES=$((FAILURES + 1))
    fi

    export BENCH_LOCAL_SUITE="${suite}"
    export BENCH_LOCAL_JSON_DIR="${JSON_DIR}"
    export BENCH_LOCAL_RUN_SUMMARY="${JSON_DIR}/run_summary.json"
    export BENCH_LOCAL_STATUS_ROWS_FILE="${STATUS_ROWS_FILE}"
    "${PYTHON}" - <<'PY'
import json
import os
from pathlib import Path

suite = os.environ["BENCH_LOCAL_SUITE"]
json_dir = Path(os.environ["BENCH_LOCAL_JSON_DIR"])
summary_path = Path(os.environ["BENCH_LOCAL_RUN_SUMMARY"])
default_report_path = json_dir / f"{suite}.json"
row = {
    "suite_id": suite,
    "status": "suite_crashed_before_report",
    "failure_reason": "suite_crashed_before_report",
    "report_path": str(default_report_path),
    "n_total": None,
    "n_passed": None,
    "pass_rate": None,
    "blockers": [],
    "preflight": {},
}
if summary_path.exists():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    suite_row = next(
        (item for item in summary.get("suite_results", []) if item.get("suite_id") == suite),
        None,
    )
    if suite_row is None:
        row["status"] = "suite_not_registered"
        row["failure_reason"] = "suite_not_registered"
    else:
        row["status"] = suite_row.get("status", row["status"])
        row["failure_reason"] = suite_row.get("failure_reason")
        row["exit_code"] = suite_row.get("exit_code")
        row["report_path"] = suite_row.get("report_path", row["report_path"])
        report_path = Path(row["report_path"])
        if report_path.exists():
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            row["n_total"] = payload.get("n_total")
            row["n_passed"] = payload.get("n_passed")
            row["pass_rate"] = payload.get("pass_rate")
            row["blockers"] = payload.get("blockers", [])
            row["preflight"] = payload.get("preflight", {})
            row["run_id"] = payload.get("run_id") or payload.get("preflight", {}).get("run_id")
            row["benchmark_tier"] = payload.get("benchmark_tier")
            row["estimator_profile"] = payload.get("estimator_profile")
with open(os.environ["BENCH_LOCAL_STATUS_ROWS_FILE"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(row) + "\n")
PY

    if [[ "${COOLDOWN_S}" != "0" ]]; then
        sleep "${COOLDOWN_S}"
    fi
done

export BENCH_LOCAL_JSON_DIR="${JSON_DIR}"
export BENCH_LOCAL_PROFILE="${PROFILE}"
export BENCH_LOCAL_MODE="${MODE}"
export BENCH_LOCAL_SUITES="$(IFS=,; echo "${SUITES[*]}")"
export BENCH_LOCAL_RUN_ID="${RUN_ID}"
export BENCH_LOCAL_ESTIMATOR_PROFILE="${ESTIMATOR_PROFILE}"
export BENCH_LOCAL_STATUS_ROWS_FILE="${STATUS_ROWS_FILE}"
"${PYTHON}" - <<'PY'
import json
import os
from pathlib import Path

json_dir = Path(os.environ["BENCH_LOCAL_JSON_DIR"])
rows_path = Path(os.environ["BENCH_LOCAL_STATUS_ROWS_FILE"])
rows = []
if rows_path.exists():
    for raw_line in rows_path.read_text(encoding="utf-8").splitlines():
        if raw_line.strip():
            rows.append(json.loads(raw_line))

summary = {
    "run_id": os.environ["BENCH_LOCAL_RUN_ID"],
    "profile": os.environ["BENCH_LOCAL_PROFILE"],
    "mode": os.environ["BENCH_LOCAL_MODE"],
    "benchmark_tier": "local_evidence" if os.environ["BENCH_LOCAL_MODE"] == "smoke" else "research_acceptance",
    "estimator_profile": os.environ["BENCH_LOCAL_ESTIMATOR_PROFILE"],
    "json_dir": str(json_dir),
    "suites": rows,
}
summary["n_suites"] = len(summary["suites"])
summary["n_passed_suites"] = sum(1 for suite in summary["suites"] if suite.get("status") == "passed")
summary["n_failed_suites"] = summary["n_suites"] - summary["n_passed_suites"]
summary["status_counts"] = {}
for suite in summary["suites"]:
    key = suite.get("status", "unknown")
    summary["status_counts"][key] = summary["status_counts"].get(key, 0) + 1

for filename in ("run_summary.json", "local_sota_summary.json"):
    path = json_dir / filename
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
PY

"${PYTHON}" "${REPO_ROOT}/benchmarks/claim_gate.py" \
    --json-dir "${JSON_DIR}" \
    --profile "${PROFILE}" \
    --output "${JSON_DIR}/claim_gate.json" >/dev/null || true

if [[ "${FAILURES}" -eq 0 ]]; then
    exit 0
fi
exit 2

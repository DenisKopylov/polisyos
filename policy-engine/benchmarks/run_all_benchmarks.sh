#!/usr/bin/env bash
# run_all_benchmarks.sh — Unified PolicyOS benchmark runner backed by suite_registry.py

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_DIR="${REPO_ROOT}/src"

PYTHON="${PYTHON:-python3}"
JSON_DIR="${BENCH_JSON_DIR:-${SCRIPT_DIR}/_reports}"
BENCH_MODE="${BENCH_MODE:-smoke}"
BENCH_TIER="${BENCH_TIER:-}"
BENCH_PROFILE="${BENCH_PROFILE:-}"
BENCH_VALIDATION_CONTOUR="${BENCH_VALIDATION_CONTOUR:-}"
BENCH_VISIBILITY="${BENCH_VISIBILITY:-}"
FILTER_CIRCUIT="${BENCH_CIRCUIT:-all}"
RUN_ID="${BENCH_RUN_ID:-bench-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ESTIMATOR_PROFILE="${BENCH_ESTIMATOR_PROFILE:-flagship_competitive}"
QUIET_FLAG=""
if [[ "${BENCH_QUIET:-0}" == "1" ]]; then
    QUIET_FLAG="--quiet"
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --circuit)
            FILTER_CIRCUIT="$2"
            shift 2
            ;;
        --json-dir)
            JSON_DIR="$2"
            shift 2
            ;;
        --quiet)
            QUIET_FLAG="--quiet"
            shift
            ;;
        --mode)
            BENCH_MODE="$2"
            shift 2
            ;;
        --tier)
            BENCH_TIER="$2"
            shift 2
            ;;
        --profile)
            BENCH_PROFILE="$2"
            shift 2
            ;;
        --contour)
            BENCH_VALIDATION_CONTOUR="$2"
            shift 2
            ;;
        --visibility)
            BENCH_VISIBILITY="$2"
            shift 2
            ;;
        --run-id)
            RUN_ID="$2"
            shift 2
            ;;
        --estimator-profile)
            ESTIMATOR_PROFILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

mkdir -p "${JSON_DIR}"
export PYTHONPATH="${SRC_DIR}:${REPO_ROOT}:${PYTHONPATH:-}"
export BENCH_MODE
export BENCH_RUN_ID="${RUN_ID}"
export BENCH_ESTIMATOR_PROFILE="${ESTIMATOR_PROFILE}"
export BENCH_VALIDATION_CONTOUR
export BENCH_VISIBILITY
if [[ -z "${BENCH_TIER}" ]]; then
    BENCH_TIER="$(
        BENCH_MODE="${BENCH_MODE}" "${PYTHON}" - <<'PY'
import os
from benchmarks.runtime import resolve_mode, resolve_tier

mode = resolve_mode(os.environ["BENCH_MODE"])
print(resolve_tier(mode=mode).value)
PY
    )"
fi
export BENCH_TIER
FILTER_CIRCUIT="$(
    FILTER_CIRCUIT="${FILTER_CIRCUIT}" "${PYTHON}" - <<'PY'
import os
from benchmarks.suite_registry import canonical_suite_id

print(canonical_suite_id(os.environ["FILTER_CIRCUIT"]))
PY
)"

_sep() { printf '=%.0s' {1..72}; echo; }
_banner() { _sep; echo "  $1"; _sep; }

FAILURES=0
TOTAL=0
PASSED=0
MATCHED=0
STATUS_ROWS_FILE="$(mktemp)"
trap 'rm -f "${STATUS_ROWS_FILE}"' EXIT

_log_failure_reason() {
    local log_file="$1"
    if [[ ! -f "${log_file}" ]]; then
        echo "suite_crashed_before_report"
        return
    fi
    if grep -Eiq "preflight failed|required comparator/dependency missing|real benchmark dataset is required in acceptance mode" "${log_file}"; then
        echo "suite_skipped_by_preflight"
        return
    fi
    echo "suite_crashed_before_report"
}

_record_status_row() {
    local suite_id="$1"
    local label="$2"
    local script="$3"
    local json_file="$4"
    local status="$5"
    local exit_code="$6"
    local failure_reason="$7"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "${suite_id}" \
        "${label}" \
        "${script}" \
        "${json_file}" \
        "${status}" \
        "${exit_code}" \
        "${failure_reason}" >> "${STATUS_ROWS_FILE}"
}

_run_benchmark() {
    local suite_id="$1"
    local label="$2"
    local script="$3"
    local aliases_csv="$4"
    local json_file="${JSON_DIR}/${suite_id}.json"
    local log_file="${JSON_DIR}/.${suite_id}.log"
    local status="passed"
    local failure_reason=""

    MATCHED=$((MATCHED + 1))
    TOTAL=$((TOTAL + 1))

    rm -f "${json_file}" "${log_file}"
    _banner "Circuit: ${label}"
    echo "  Suite  : ${suite_id}"
    echo "  Script : ${script}"
    echo "  Report : ${json_file}"
    echo "  Mode   : ${BENCH_MODE}"
    if [[ -n "${BENCH_TIER}" ]]; then
        echo "  Tier   : ${BENCH_TIER}"
    fi
    if [[ -n "${BENCH_PROFILE}" ]]; then
        echo "  Profile: ${BENCH_PROFILE}"
    fi
    echo "  Run ID : ${RUN_ID}"
    echo

    set +e
    "${PYTHON}" "${script}" ${QUIET_FLAG} --mode "${BENCH_MODE}" --json "${json_file}" > "${log_file}" 2>&1
    local exit_code=$?
    set -e

    if [[ -s "${log_file}" ]]; then
        cat "${log_file}"
    fi

    if [[ ${exit_code} -eq 0 ]]; then
        PASSED=$((PASSED + 1))
        status="passed"
        echo "  → PASSED"
    else
        FAILURES=$((FAILURES + 1))
        if [[ -f "${json_file}" ]]; then
            status="failed"
        else
            failure_reason="$(_log_failure_reason "${log_file}")"
            status="${failure_reason}"
        fi
        echo "  → FAILED (exit ${exit_code})"
    fi
    echo

    _record_status_row "${suite_id}" "${label}" "${script}" "${json_file}" "${status}" "${exit_code}" "${failure_reason}"
}

REGISTRY_LINES=()
while IFS= read -r line; do
    REGISTRY_LINES+=("${line}")
done < <(
    BENCH_PROFILE="${BENCH_PROFILE}" "${PYTHON}" - <<'PY'
import os
from benchmarks.suite_registry import emit_registry_tsv

profile = (os.environ.get("BENCH_PROFILE") or "").strip() or None
validation_contour = (os.environ.get("BENCH_VALIDATION_CONTOUR") or "").strip() or None
visibility = (os.environ.get("BENCH_VISIBILITY") or "").strip() or None
payload = emit_registry_tsv(
    profile=profile,
    validation_contour=validation_contour,
    visibility=visibility,
)
if payload:
    print(payload)
PY
)

for line in "${REGISTRY_LINES[@]}"; do
    [[ -z "${line}" ]] && continue
    IFS=$'\t' read -r suite_id label script_path aliases_csv profiles <<< "${line}"

    if [[ "${FILTER_CIRCUIT}" != "all" ]]; then
        if [[ "${FILTER_CIRCUIT}" != "${suite_id}" ]]; then
            matched_alias=0
            OLD_IFS="${IFS}"
            IFS=','
            for alias in ${aliases_csv}; do
                if [[ -n "${alias}" && "${FILTER_CIRCUIT}" == "${alias}" ]]; then
                    matched_alias=1
                    break
                fi
            done
            IFS="${OLD_IFS}"
            if [[ "${matched_alias}" -ne 1 ]]; then
                continue
            fi
        fi
    fi

    _run_benchmark "${suite_id}" "${label}" "${script_path}" "${aliases_csv}"
done

RUN_SUMMARY_FILE="${JSON_DIR}/run_summary.json"
LAST_SUITE_SUMMARY_FILE="${JSON_DIR}/last_suite_summary.json"
SUMMARY_FILE="${JSON_DIR}/summary.json"

export BENCH_SUMMARY_STATUS_ROWS="${STATUS_ROWS_FILE}"
export BENCH_SUMMARY_JSON_DIR="${JSON_DIR}"
export BENCH_SUMMARY_FILTER="${FILTER_CIRCUIT}"
export BENCH_SUMMARY_MODE="${BENCH_MODE}"
export BENCH_SUMMARY_TIER="${BENCH_TIER:-}"
export BENCH_SUMMARY_PROFILE="${BENCH_PROFILE:-}"
export BENCH_SUMMARY_VALIDATION_CONTOUR="${BENCH_VALIDATION_CONTOUR:-}"
export BENCH_SUMMARY_VISIBILITY="${BENCH_VISIBILITY:-}"
export BENCH_SUMMARY_RUN_ID="${RUN_ID}"
export BENCH_SUMMARY_ESTIMATOR_PROFILE="${ESTIMATOR_PROFILE}"
export BENCH_SUMMARY_MATCHED="${MATCHED}"
export BENCH_SUMMARY_TOTAL="${TOTAL}"
export BENCH_SUMMARY_PASSED="${PASSED}"
export BENCH_SUMMARY_FAILED="${FAILURES}"
export BENCH_SUMMARY_RUN_SUMMARY_FILE="${RUN_SUMMARY_FILE}"
export BENCH_SUMMARY_LAST_SUITE_FILE="${LAST_SUITE_SUMMARY_FILE}"
export BENCH_SUMMARY_FILE="${SUMMARY_FILE}"
"${PYTHON}" - <<'PY'
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _read_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        suite_id, label, script, report_path, status, exit_code, failure_reason = raw_line.split("\t")
        rows.append(
            {
                "suite_id": suite_id,
                "label": label,
                "script": script,
                "report_path": report_path,
                "report_exists": Path(report_path).exists(),
                "status": status,
                "exit_code": int(exit_code),
                "failure_reason": failure_reason or None,
            }
        )
    return rows


status_rows_path = Path(os.environ["BENCH_SUMMARY_STATUS_ROWS"])
json_dir = Path(os.environ["BENCH_SUMMARY_JSON_DIR"])
run_summary_path = Path(os.environ["BENCH_SUMMARY_RUN_SUMMARY_FILE"])
last_suite_path = Path(os.environ["BENCH_SUMMARY_LAST_SUITE_FILE"])
summary_path = Path(os.environ["BENCH_SUMMARY_FILE"])
rows = _read_rows(status_rows_path)
total = int(os.environ["BENCH_SUMMARY_TOTAL"])
passed = int(os.environ["BENCH_SUMMARY_PASSED"])
failed = int(os.environ["BENCH_SUMMARY_FAILED"])
matched = int(os.environ["BENCH_SUMMARY_MATCHED"])
summary = {
    "run_id": os.environ["BENCH_SUMMARY_RUN_ID"],
    "mode": os.environ["BENCH_SUMMARY_MODE"],
    "tier": os.environ["BENCH_SUMMARY_TIER"],
    "profile": os.environ["BENCH_SUMMARY_PROFILE"],
    "validation_contour": os.environ["BENCH_SUMMARY_VALIDATION_CONTOUR"],
    "visibility": os.environ["BENCH_SUMMARY_VISIBILITY"],
    "filter": os.environ["BENCH_SUMMARY_FILTER"],
    "matched": matched,
    "n_total": total,
    "n_passed": passed,
    "n_failed": failed,
    "pass_rate": round((passed / total), 4) if total else 0.0,
    "estimator_profile": os.environ["BENCH_SUMMARY_ESTIMATOR_PROFILE"],
    "json_dir": str(json_dir),
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "suite_results": rows,
}
payload = json.dumps(summary, indent=2) + "\n"
run_summary_path.write_text(payload, encoding="utf-8")
summary_path.write_text(payload, encoding="utf-8")

if rows:
    last = rows[-1]
    report_path = Path(str(last["report_path"]))
    if report_path.exists():
        last_payload = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        last_payload = {
            "suite_id": last["suite_id"],
            "status": last["status"],
            "failure_reason": last["failure_reason"],
            "exit_code": last["exit_code"],
            "report_path": last["report_path"],
            "run_id": summary["run_id"],
            "mode": summary["mode"],
            "benchmark_tier": summary["tier"],
            "estimator_profile": summary["estimator_profile"],
        }
    last_suite_path.write_text(json.dumps(last_payload, indent=2) + "\n", encoding="utf-8")
PY

if [[ "${FILTER_CIRCUIT}" != "all" && ${MATCHED} -eq 0 ]]; then
    echo "No benchmark suites matched filter: ${FILTER_CIRCUIT}" >&2
    exit 2
fi

_sep
echo
echo "  PolicyOS Benchmark Suite — Final Summary"
echo
echo "  Run ID         : ${RUN_ID}"
echo "  Mode           : ${BENCH_MODE}"
if [[ -n "${BENCH_TIER}" ]]; then
    echo "  Tier           : ${BENCH_TIER}"
fi
if [[ -n "${BENCH_PROFILE}" ]]; then
    echo "  Profile        : ${BENCH_PROFILE}"
fi
if [[ -n "${BENCH_VALIDATION_CONTOUR}" ]]; then
    echo "  Contour        : ${BENCH_VALIDATION_CONTOUR}"
fi
if [[ -n "${BENCH_VISIBILITY}" ]]; then
    echo "  Visibility     : ${BENCH_VISIBILITY}"
fi
echo "  Circuits run   : ${TOTAL}"
echo "  Circuits passed: ${PASSED}"
echo "  Circuits failed: ${FAILURES}"
echo
if [[ ${FAILURES} -eq 0 ]]; then
    echo "  ALL CIRCUITS PASSED"
else
    echo "  FAILURES DETECTED — see ${JSON_DIR}/ for per-circuit JSON reports"
fi
echo
echo "  Run summary    : ${RUN_SUMMARY_FILE}"
echo "  Last suite     : ${LAST_SUITE_SUMMARY_FILE}"
echo
_sep

if [[ ${FAILURES} -eq 0 ]]; then
    exit 0
fi
exit 1

#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
INSTANCE_NAME_PREFIX="${INSTANCE_NAME_PREFIX:?Set INSTANCE_NAME_PREFIX}"
OUTPUT_ROOT="${OUTPUT_ROOT:?Set OUTPUT_ROOT}"
SHARD_COUNT="${SHARD_COUNT:?Set SHARD_COUNT}"

CHECK_INTERVAL_SEC="${CHECK_INTERVAL_SEC:-300}"
ZONE="${ZONE:-europe-west2-b}"
SHARD_ZONE_MAP="${SHARD_ZONE_MAP:-}"
ON_SHARD_COMPLETE_CMD_TEMPLATE="${ON_SHARD_COMPLETE_CMD_TEMPLATE:-}"
ON_COMPLETE_CMD="${ON_COMPLETE_CMD:-}"
STATE_FILE="${STATE_FILE:-}"
STATE_DIR="${STATE_DIR:-}"

resolve_zone() {
  local shard_index="$1"
  local entry=""
  local shard=""
  local zone_override=""

  if [ -n "${SHARD_ZONE_MAP}" ]; then
    IFS=',' read -r -a zone_entries <<< "${SHARD_ZONE_MAP}"
    for entry in "${zone_entries[@]}"; do
      shard="${entry%%:*}"
      zone_override="${entry#*:}"
      if [ "${shard}" = "${shard_index}" ] && [ -n "${zone_override}" ]; then
        printf '%s\n' "${zone_override}"
        return 0
      fi
    done
  fi

  printf '%s\n' "${ZONE}"
}

gcloud config set project "${PROJECT_ID}" > /dev/null

while true; do
  completed=0

  for i in $(seq 0 $((SHARD_COUNT - 1))); do
    INSTANCE_NAME="${INSTANCE_NAME_PREFIX}-${i}"
    INSTANCE_ZONE="$(resolve_zone "${i}")"
    EXIT_CODE_URI="${OUTPUT_ROOT%/}/shard_${i}/manifests/pipeline_exit_code.txt"
    EXIT_CODE="$(gcloud storage cat "${EXIT_CODE_URI}" 2> /dev/null || true)"

    if [ "${EXIT_CODE}" = "0" ]; then
      completed=$((completed + 1))
      if [ -n "${ON_SHARD_COMPLETE_CMD_TEMPLATE}" ]; then
        shard_state_file=""
        if [ -n "${STATE_DIR}" ]; then
          mkdir -p "${STATE_DIR}"
          shard_state_file="${STATE_DIR}/shard_${i}.done"
        fi
        if [ -z "${shard_state_file}" ] || [ ! -f "${shard_state_file}" ]; then
          shard_cmd="${ON_SHARD_COMPLETE_CMD_TEMPLATE//__SHARD_INDEX__/${i}}"
          shard_cmd="${shard_cmd//__ZONE__/${INSTANCE_ZONE}}"
          echo "Promoting shard ${i} via: ${shard_cmd}"
          bash -lc "${shard_cmd}"
          if [ -n "${shard_state_file}" ]; then
            printf '%s\n' "completed" > "${shard_state_file}"
          fi
        fi
      fi
      continue
    fi

    if [ -n "${EXIT_CODE}" ] && [ "${EXIT_CODE}" != "0" ]; then
      echo "Detected non-zero exit code for ${INSTANCE_NAME}: ${EXIT_CODE}"
    fi

    STATUS="$(gcloud compute instances describe "${INSTANCE_NAME}" --zone="${INSTANCE_ZONE}" --format='get(status)' 2> /dev/null || true)"
    if [ "${STATUS}" = "TERMINATED" ]; then
      if [ -n "${EXIT_CODE}" ] && [ "${EXIT_CODE}" != "0" ]; then
        echo "Restarting ${INSTANCE_NAME} in ${INSTANCE_ZONE} because pipeline_exit_code=${EXIT_CODE}."
      else
        echo "Restarting ${INSTANCE_NAME} in ${INSTANCE_ZONE} because pipeline_exit_code.txt is missing."
      fi
      gcloud compute instances start "${INSTANCE_NAME}" --zone="${INSTANCE_ZONE}" > /dev/null || true
    fi
  done

  if [ "${completed}" -eq "${SHARD_COUNT}" ]; then
    echo "All ${SHARD_COUNT} shards for ${INSTANCE_NAME_PREFIX} completed."
    if [ -n "${ON_COMPLETE_CMD}" ]; then
      if [ -z "${STATE_FILE}" ] || [ ! -f "${STATE_FILE}" ]; then
        if [ -n "${STATE_FILE}" ]; then
          mkdir -p "$(dirname "${STATE_FILE}")"
        fi
        bash -lc "${ON_COMPLETE_CMD}"
        if [ -n "${STATE_FILE}" ]; then
          printf '%s\n' "completed" > "${STATE_FILE}"
        fi
      fi
    fi
    exit 0
  fi

  sleep "${CHECK_INTERVAL_SEC}"
done

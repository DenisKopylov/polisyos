#!/bin/bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
BUCKET_NAME="${BUCKET_NAME:?Set BUCKET_NAME}"
WORKER_SA_EMAIL="${WORKER_SA_EMAIL:-lex-workers@${PROJECT_ID}.iam.gserviceaccount.com}"
SNAPSHOT_LABEL="${SNAPSHOT_LABEL:-2026-04-05}"
STATUS_PASS="${STATUS_PASS:-current}"
MODE="${MODE:-phase1}"
SHARD_COUNT="${SHARD_COUNT:-6}"
INSTANCE_NAME_PREFIX="${INSTANCE_NAME_PREFIX:-lex-worker}"
MACHINE_TYPE="${MACHINE_TYPE:-t2d-standard-2}"
BOOT_DISK_SIZE_GB="${BOOT_DISK_SIZE_GB:-80}"
BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-ssd}"
SYNC_INTERVAL_SEC="${SYNC_INTERVAL_SEC:-120}"
AUTO_SHUTDOWN="${AUTO_SHUTDOWN:-1}"
GAP_FILL_MODE="${GAP_FILL_MODE:-narrow}"
GAP_FILL_SHARE="${GAP_FILL_SHARE:-0.10}"
RESUME_CACHE_ENABLED="${RESUME_CACHE_ENABLED:-1}"
ZONE="${ZONE:-europe-west1-b}"
SHARD_ZONE_MAP="${SHARD_ZONE_MAP:-0:europe-west1-b,1:europe-west1-b,2:europe-west1-b,3:europe-west4-b,4:europe-west4-b,5:europe-west4-b}"
SKIP_EXISTING="${SKIP_EXISTING:-1}"
RUN_LABEL="${RUN_LABEL:-${MODE}-$(date -u +%Y%m%d-%H%M%S)}"
REPO_BUNDLE_URI="${REPO_BUNDLE_URI:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESUME_CACHE_ROOT="${RESUME_CACHE_ROOT:-gs://${BUCKET_NAME}/cache/lex_resume/${SNAPSHOT_LABEL}/${STATUS_PASS}/shards_${SHARD_COUNT}}"

if [ -z "${REPO_BUNDLE_URI}" ]; then
  REPO_BUNDLE_URI="$(gcloud storage ls "gs://${BUCKET_NAME}/bootstrap/repo/" | tail -n 1)"
fi

if [ -z "${REPO_BUNDLE_URI}" ]; then
  echo "Unable to resolve REPO_BUNDLE_URI"
  exit 1
fi

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

# Shared defaults from the runbook.
D_WARMUP_SEC=30
D_WARMUP_SCALE=2.0
D_ADAPTIVE_RECOVERY=0.97
D_ADAPTIVE_PENALTY=1.35
D_ADAPTIVE_MAX_SCALE=4.0
D_GROUP_TIMEOUT=45
D_BATCH_SIZE=4
D_FOLLOWUP_SCALE=0.85
D_STRUCTURE_WORKERS=2
D_XML_PARSE_CHUNK=2000

case "${MODE}" in
  phase1)
    MAX_DOCS=(50 50 50 50 50 50)
    RPS=(5.0 5.0 8.0 5.0 5.0 9.0)
    PARALLEL_LLM=(16 16 20 30 16 25)
    PARALLEL_LLM_GLOBAL=(64 64 80 80 64 80)
    VERIFY_MODE=(llm llm llm llm code code)
    BATCH_CHARS=(3600 3600 3600 3600 3600 4800)
    HYPOTHESIS=(baseline_a baseline_b higher_rps higher_concurrency code_verify aggressive_capped)
    ;;
  phase1b)
    D_BATCH_SIZE=3
    D_XML_PARSE_CHUNK=128
    MAX_DOCS=(75 75 75 75 75 75)
    RPS=(5.0 5.0 5.0 6.0 5.0 5.0)
    PARALLEL_LLM=(16 16 24 20 16 20)
    PARALLEL_LLM_GLOBAL=(64 56 64 72 64 64)
    VERIFY_MODE=(llm llm llm llm code code)
    BATCH_CHARS=(3200 3200 3200 3200 3200 2800)
    HYPOTHESIS=(llm_control llm_lower_global llm_more_parallel llm_balanced_push code_control code_more_parallel)
    ;;
  phase1c)
    D_BATCH_SIZE=3
    D_XML_PARSE_CHUNK=128
    MAX_DOCS=(100 100 100 100 100 100)
    RPS=(5.0 5.0 4.0 5.0 6.0 5.0)
    PARALLEL_LLM=(16 16 16 16 16 16)
    PARALLEL_LLM_GLOBAL=(64 64 64 56 64 64)
    VERIFY_MODE=(code code code code code code)
    BATCH_CHARS=(3200 3200 3200 3200 3200 3600)
    HYPOTHESIS=(code_control_a code_control_b code_rps4 code_global56 code_rps6 code_batch3600)
    ;;
  phase1d)
    D_BATCH_SIZE=3
    D_XML_PARSE_CHUNK=128
    MAX_DOCS=(400 400 400 400 400 400)
    RPS=(5.0 5.0 5.0 5.0 5.0 5.0)
    PARALLEL_LLM=(16 16 16 16 16 16)
    PARALLEL_LLM_GLOBAL=(64 56 56 56 56 60)
    VERIFY_MODE=(code code code code code code)
    BATCH_CHARS=(3600 3200 3600 3600 3400 3600)
    HYPOTHESIS=(
      code_batch3600_g64
      code_batch3200_g56
      code_batch3600_g56_a
      code_batch3600_g56_b
      code_batch3400_g56
      code_batch3600_g60
    )
    ;;
  phase1e)
    D_BATCH_SIZE=3
    D_XML_PARSE_CHUNK=128
    MAX_DOCS=(1000 1000 1000 1000 1000 1000)
    RPS=(5.0 5.0 5.0 5.0 5.0 5.0)
    PARALLEL_LLM=(16 16 16 16 16 16)
    PARALLEL_LLM_GLOBAL=(56 56 56 56 56 56)
    VERIFY_MODE=(code code code code code code)
    BATCH_CHARS=(3600 3600 3600 3600 3600 3600)
    HYPOTHESIS=(code_batch3600_g56_best code_batch3600_g56_best code_batch3600_g56_best code_batch3600_g56_best code_batch3600_g56_best code_batch3600_g56_best)
    ;;
  phase2)
    MAX_DOCS=(200 200 200 200 200 200)
    RPS=(9.0 9.0 11.0 9.0 6.0 9.0)
    PARALLEL_LLM=(25 25 25 35 16 25)
    PARALLEL_LLM_GLOBAL=(80 80 80 96 64 64)
    VERIFY_MODE=(code code code code code code)
    BATCH_CHARS=(4800 4800 4800 4800 3600 4800)
    HYPOTHESIS=(winner_a winner_b rps_plus20 concur_plus40 control low_global_cap)
    ;;
  production)
    MAX_DOCS=(0 0 0 0 0 0)
    RPS=(9.0 9.0 9.0 9.0 9.0 9.0)
    PARALLEL_LLM=(25 25 25 25 25 25)
    PARALLEL_LLM_GLOBAL=(80 80 80 80 80 80)
    VERIFY_MODE=(code code code code code code)
    BATCH_CHARS=(4800 4800 4800 4800 4800 4800)
    HYPOTHESIS=(prod prod prod prod prod prod)
    ;;
  *)
    echo "Unknown MODE=${MODE}. Expected one of: phase1, phase1b, phase1c, phase1d, phase1e, phase2, production"
    exit 1
    ;;
esac

gcloud config set project "${PROJECT_ID}" >/dev/null

echo "=== Launch calibration workers ==="
echo "project=${PROJECT_ID} mode=${MODE} status=${STATUS_PASS} run_label=${RUN_LABEL}"
echo "bundle=${REPO_BUNDLE_URI}"
echo ""

for i in $(seq 0 $((SHARD_COUNT - 1))); do
  ACCOUNT_NUM=$((i + 1))
  INSTANCE_NAME="${INSTANCE_NAME_PREFIX}-${i}"
  INSTANCE_ZONE="$(resolve_zone "${i}")"
  OUTPUT_PREFIX="gs://${BUCKET_NAME}/output/${RUN_LABEL}/${STATUS_PASS}/shard_${i}"
  RESUME_CACHE_PREFIX="${RESUME_CACHE_ROOT}/shard_${i}"

  META="project-id=${PROJECT_ID}"
  META="${META},bucket-name=${BUCKET_NAME}"
  META="${META},repo-bundle-uri=${REPO_BUNDLE_URI}"
  META="${META},snapshot-label=${SNAPSHOT_LABEL}"
  META="${META},status-pass=${STATUS_PASS}"
  META="${META},worker-mode=run"
  META="${META},run-label=${RUN_LABEL}"
  META="${META},shard-index=${i}"
  META="${META},shard-count=${SHARD_COUNT}"
  META="${META},account-num=${ACCOUNT_NUM}"
  META="${META},output-prefix=${OUTPUT_PREFIX}"
  META="${META},max-docs=${MAX_DOCS[$i]}"
  META="${META},rps=${RPS[$i]}"
  META="${META},parallel-llm=${PARALLEL_LLM[$i]}"
  META="${META},parallel-llm-global=${PARALLEL_LLM_GLOBAL[$i]}"
  META="${META},batch-chars=${BATCH_CHARS[$i]}"
  META="${META},batch-size=${D_BATCH_SIZE}"
  META="${META},warmup-sec=${D_WARMUP_SEC}"
  META="${META},warmup-scale=${D_WARMUP_SCALE}"
  META="${META},adaptive-recovery=${D_ADAPTIVE_RECOVERY}"
  META="${META},adaptive-penalty=${D_ADAPTIVE_PENALTY}"
  META="${META},adaptive-max-scale=${D_ADAPTIVE_MAX_SCALE}"
  META="${META},group-timeout=${D_GROUP_TIMEOUT}"
  META="${META},followup-scale=${D_FOLLOWUP_SCALE}"
  META="${META},structure-workers=${D_STRUCTURE_WORKERS}"
  META="${META},xml-parse-chunk=${D_XML_PARSE_CHUNK}"
  META="${META},spo-verify-mode=${VERIFY_MODE[$i]}"
  META="${META},gap-fill-mode=${GAP_FILL_MODE}"
  META="${META},gap-fill-share=${GAP_FILL_SHARE}"
  META="${META},hypothesis=${HYPOTHESIS[$i]}"
  META="${META},sync-interval-sec=${SYNC_INTERVAL_SEC}"
  META="${META},auto-shutdown=${AUTO_SHUTDOWN}"
  META="${META},resume-cache-enabled=${RESUME_CACHE_ENABLED}"
  if [ "${RESUME_CACHE_ENABLED}" = "1" ]; then
    META="${META},resume-cache-prefix=${RESUME_CACHE_PREFIX}"
  fi

  if gcloud compute instances describe "${INSTANCE_NAME}" --zone="${INSTANCE_ZONE}" >/dev/null 2>&1; then
    if [ "${SKIP_EXISTING}" = "1" ]; then
      echo "Skipping existing instance ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
      continue
    fi
    echo "Instance already exists: ${INSTANCE_NAME} in ${INSTANCE_ZONE}"
    exit 1
  fi

  gcloud compute instances create "${INSTANCE_NAME}" \
    --zone="${INSTANCE_ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    --boot-disk-size="${BOOT_DISK_SIZE_GB}GB" \
    --boot-disk-type="${BOOT_DISK_TYPE}" \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --service-account="${WORKER_SA_EMAIL}" \
    --scopes=cloud-platform \
    --metadata="${META},serial-port-enable=TRUE" \
    --metadata-from-file=startup-script="${SCRIPT_DIR}/startup.sh" \
    --tags=lex-worker \
    --provisioning-model=SPOT \
    --maintenance-policy=TERMINATE \
    --instance-termination-action=STOP >/dev/null

  printf "  %-14s zone=%-15s hypothesis=%-18s rps=%-4s parallel=%-3s global=%-3s verify=%-4s max_docs=%s\n" \
    "${INSTANCE_NAME}" "${INSTANCE_ZONE}" "${HYPOTHESIS[$i]}" "${RPS[$i]}" "${PARALLEL_LLM[$i]}" "${PARALLEL_LLM_GLOBAL[$i]}" "${VERIFY_MODE[$i]}" "${MAX_DOCS[$i]}"
done

echo ""
echo "Run label: ${RUN_LABEL}"
echo "Output prefix: gs://${BUCKET_NAME}/output/${RUN_LABEL}/${STATUS_PASS}/"
echo ""
gcloud compute instances list --filter="name~^${INSTANCE_NAME_PREFIX}-" \
  --format="table(name,status,zone.basename(),machineType.basename(),networkInterfaces[0].accessConfigs[0].natIP)"

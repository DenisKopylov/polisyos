#!/bin/bash
set -euo pipefail

exec > >(tee -a /var/log/policyos-gcp-startup.log) 2>&1

md() {
  curl -fsS "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" \
    -H "Metadata-Flavor: Google"
}

meta_or_default() {
  local key="$1"
  local fallback="${2:-}"
  md "${key}" 2>/dev/null || printf '%s\n' "${fallback}"
}

PROJECT_ID="$(md project-id)"
BUCKET_NAME="$(md bucket-name)"
REPO_BUNDLE_URI="$(md repo-bundle-uri)"
SNAPSHOT_LABEL="$(md snapshot-label)"
STATUS_PASS="$(md status-pass)"
WORKER_MODE="$(md worker-mode)"
SHARD_INDEX="$(md shard-index)"
SHARD_COUNT="$(md shard-count)"
ACCOUNT_NUM="$(md account-num)"
OUTPUT_PREFIX="$(md output-prefix)"
QUEUE_NAME="$(meta_or_default queue-name "")"
LOAD_GONKA_SECRETS="$(meta_or_default load-gonka-secrets 1)"
MANIFEST_URI="$(meta_or_default manifest-uri "")"
RESUME_CACHE_ENABLED="$(meta_or_default resume-cache-enabled 0)"
RESUME_CACHE_PREFIX="$(meta_or_default resume-cache-prefix "")"
if [ -n "${MANIFEST_URI}" ]; then
  MANIFEST_NAME="$(basename "${MANIFEST_URI}")"
else
  MANIFEST_NAME="$(printf 'shard_%02d_of_%02d.jsonl.zst' "${SHARD_INDEX}" "${SHARD_COUNT}")"
fi
MAX_DOCS="$(meta_or_default max-docs 0)"
RPS="$(meta_or_default rps 5.0)"
PARALLEL_LLM="$(meta_or_default parallel-llm 16)"
PARALLEL_LLM_GLOBAL="$(meta_or_default parallel-llm-global 64)"
BATCH_CHARS="$(meta_or_default batch-chars 3600)"
BATCH_SIZE="$(meta_or_default batch-size 4)"
WARMUP_SEC="$(meta_or_default warmup-sec 30)"
WARMUP_SCALE="$(meta_or_default warmup-scale 2.0)"
ADAPTIVE_RECOVERY="$(meta_or_default adaptive-recovery 0.97)"
ADAPTIVE_PENALTY="$(meta_or_default adaptive-penalty 1.35)"
ADAPTIVE_MAX_SCALE="$(meta_or_default adaptive-max-scale 4.0)"
GROUP_TIMEOUT="$(meta_or_default group-timeout 45)"
VERIFY_MODE="$(meta_or_default spo-verify-mode llm)"
STRUCTURE_WORKERS="$(meta_or_default structure-workers 2)"
XML_PARSE_CHUNK="$(meta_or_default xml-parse-chunk 2000)"
GAP_FILL_MODE="$(meta_or_default gap-fill-mode narrow)"
GAP_FILL_SHARE="$(meta_or_default gap-fill-share 0.10)"
HYPOTHESIS="$(meta_or_default hypothesis unnamed)"
QUALITY_MAX_FULL_ONLY_DOCS_PCT="$(meta_or_default quality-max-full-only-docs-pct 25.0)"
FOLLOWUP_SCALE="$(meta_or_default followup-scale 0.85)"
SYNC_INTERVAL_SEC="$(meta_or_default sync-interval-sec 120)"
AUTO_SHUTDOWN="$(meta_or_default auto-shutdown 1)"
RUN_LABEL="$(meta_or_default run-label adhoc)"
SHARD_SLUG="$(printf 'shard_%02d_of_%02d' "${SHARD_INDEX}" "${SHARD_COUNT}")"

SYNCABLE_CACHE_DIRS=(
  provisions
  references
  domains
  spo_results
  spo_grounded
  resolved_references
)

echo "=== PolicyOS GCP worker bootstrap ==="
echo "project=${PROJECT_ID} bucket=${BUCKET_NAME} mode=${WORKER_MODE} shard=${SHARD_INDEX}/${SHARD_COUNT} account=${ACCOUNT_NUM} hypothesis=${HYPOTHESIS} queue=${QUEUE_NAME:-<default>}"
echo "resume_cache_enabled=${RESUME_CACHE_ENABLED} resume_cache_prefix=${RESUME_CACHE_PREFIX:-<disabled>}"
echo "[1/7] Installing base system packages"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  apt-transport-https ca-certificates curl gnupg git tar \
  build-essential libffi-dev libssl-dev pkg-config >/dev/null

if ! command -v gcloud >/dev/null 2>&1; then
  echo "[2/7] Installing gcloud CLI"
  install -d -m 0755 /usr/share/keyrings
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list
  apt-get update -qq
  apt-get install -y -qq google-cloud-cli >/dev/null
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[3/7] Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="/root/.local/bin:${PATH}"

mkdir -p /opt/polisyos /mnt/work/input /mnt/work/output /mnt/work/bootstrap

echo "[4/7] Downloading repo bundle"
gcloud storage cp "${REPO_BUNDLE_URI}" /mnt/work/bootstrap/repo.tgz >/dev/null
tar -xzf /mnt/work/bootstrap/repo.tgz -C /opt/polisyos

cd /opt/polisyos/policy-engine
echo "[5/7] Preparing Python runtime"
uv python install 3.14 >/dev/null
uv venv --python 3.14 /opt/venv >/dev/null
source /opt/venv/bin/activate
uv pip install --python /opt/venv/bin/python -e /opt/polisyos/policy-engine >/dev/null

echo "[6/7] Loading Gonka secrets and shard inputs"
if [ "${LOAD_GONKA_SECRETS}" = "1" ]; then
  for i in 1 2 3 4 5; do
    value="$(gcloud secrets versions access latest \
      --secret="gonka-acc${ACCOUNT_NUM}-key${i}" \
      --project="${PROJECT_ID}" 2>/dev/null || true)"
    if [ -n "${value}" ]; then
      export "GONKA_API_KEY_${i}=${value}"
    fi
  done
else
  echo "Skipping Gonka secret load for this worker group."
fi

gcloud storage cp \
  "gs://${BUCKET_NAME}/input/pre_sharded/${SNAPSHOT_LABEL}/summary.json" \
  /mnt/work/input/summary.json >/dev/null
if [ -n "${MANIFEST_URI}" ]; then
  gcloud storage cp "${MANIFEST_URI}" "/mnt/work/input/${MANIFEST_NAME}" >/dev/null
else
  gcloud storage cp \
    "gs://${BUCKET_NAME}/input/pre_sharded/${SNAPSHOT_LABEL}/${STATUS_PASS}/${MANIFEST_NAME}" \
    "/mnt/work/input/${MANIFEST_NAME}" >/dev/null
fi

sync_gcs_dir_to_local() {
  local remote_dir="$1"
  local local_dir="$2"
  mkdir -p "${local_dir}"
  gcloud storage rsync -r "${remote_dir}/" "${local_dir}/" >/dev/null 2>&1 || true
}

sync_local_dir_to_gcs() {
  local local_dir="$1"
  local remote_dir="$2"
  if [ ! -d "${local_dir}" ]; then
    return 0
  fi
  gcloud storage rsync -r "${local_dir}/" "${remote_dir}/" >/dev/null 2>&1 || true
}

sync_gcs_file_to_local() {
  local remote_file="$1"
  local local_file="$2"
  mkdir -p "$(dirname "${local_file}")"
  gcloud storage cp "${remote_file}" "${local_file}" >/dev/null 2>&1 || true
}

sync_local_file_to_gcs() {
  local local_file="$1"
  local remote_file="$2"
  if [ ! -f "${local_file}" ]; then
    return 0
  fi
  gcloud storage cp "${local_file}" "${remote_file}" >/dev/null 2>&1 || true
}

sync_resume_cache_to_local() {
  if [ "${RESUME_CACHE_ENABLED}" != "1" ] || [ -z "${RESUME_CACHE_PREFIX}" ]; then
    return 0
  fi

  sync_gcs_file_to_local \
    "${RESUME_CACHE_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl" \
    "/mnt/work/output/_shards/${SHARD_SLUG}/progress.jsonl"
  sync_gcs_file_to_local \
    "${RESUME_CACHE_PREFIX}/manifests/doc_metadata.json" \
    "/mnt/work/output/manifests/doc_metadata.json"
}

sync_local_resume_cache() {
  if [ "${RESUME_CACHE_ENABLED}" != "1" ] || [ -z "${RESUME_CACHE_PREFIX}" ]; then
    return 0
  fi

  sync_local_file_to_gcs \
    "/mnt/work/output/_shards/${SHARD_SLUG}/progress.jsonl" \
    "${RESUME_CACHE_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl"
  sync_local_file_to_gcs \
    "/mnt/work/output/manifests/doc_metadata.json" \
    "${RESUME_CACHE_PREFIX}/manifests/doc_metadata.json"

  for dir_name in "${SYNCABLE_CACHE_DIRS[@]}"; do
    sync_local_dir_to_gcs "/mnt/work/output/${dir_name}" "${RESUME_CACHE_PREFIX}/${dir_name}"
  done
}

sync_outputs() {
  mkdir -p /mnt/work/output/manifests
  printf '%s\n' "${RUN_LABEL}" > /mnt/work/output/manifests/run_label.txt
  cp /var/log/policyos-gcp-startup.log /mnt/work/output/manifests/startup.log 2>/dev/null || true
  # Keep a root-level telemetry.json for older tooling expectations.
  if [ -f /mnt/work/output/manifests/telemetry.json ]; then
    cp /mnt/work/output/manifests/telemetry.json /mnt/work/output/telemetry.json 2>/dev/null || true
  fi
  gcloud storage rsync -r /mnt/work/output/ "${OUTPUT_PREFIX}/" >/dev/null 2>&1 || true
  sync_local_resume_cache || true
}

SYNC_LOOP_PID=""
cleanup() {
  local exit_code=$?
  if [ -n "${SYNC_LOOP_PID}" ]; then
    kill "${SYNC_LOOP_PID}" >/dev/null 2>&1 || true
    wait "${SYNC_LOOP_PID}" 2>/dev/null || true
  fi
  sync_outputs || true
  echo "Worker exit code: ${exit_code}"
  if [ "${AUTO_SHUTDOWN}" = "1" ]; then
    shutdown -h now || true
  fi
}
trap cleanup EXIT TERM INT

if [ "${WORKER_MODE}" = "preflight" ]; then
  echo "[7/7] Running preflight validation"
  python /opt/polisyos/policy-engine/tools/cloud/gcp_preflight.py \
    --manifest "/mnt/work/input/${MANIFEST_NAME}" \
    --summary /mnt/work/input/summary.json \
    --output /mnt/work/output/preflight.json \
    --status-pass "${STATUS_PASS}" \
    --shard-index "${SHARD_INDEX}" \
    --account-num "${ACCOUNT_NUM}"

  sync_outputs
  echo "Preflight complete."
  exit 0
fi

if [ "${WORKER_MODE}" != "run" ]; then
  echo "Worker mode '${WORKER_MODE}' is reserved for explicit launch enablement."
  exit 2
fi

echo "[7/7] Restoring previous run state"
sync_resume_cache_to_local
gcloud storage rsync -r "${OUTPUT_PREFIX}/" /mnt/work/output/ >/dev/null 2>&1 || true
mkdir -p /mnt/work/output/manifests
rm -f /mnt/work/output/manifests/pipeline_exit_code.txt /mnt/work/output/pipeline_exit_code.txt

cat > /mnt/work/output/manifests/run_config.json <<EOF
{
  "run_label": "${RUN_LABEL}",
  "shard_index": ${SHARD_INDEX},
  "shard_count": ${SHARD_COUNT},
  "shard_slug": "${SHARD_SLUG}",
  "account_num": ${ACCOUNT_NUM},
  "status_pass": "${STATUS_PASS}",
  "queue_name": "${QUEUE_NAME}",
  "hypothesis": "${HYPOTHESIS}",
  "rps": ${RPS},
  "parallel_llm": ${PARALLEL_LLM},
  "parallel_llm_global": ${PARALLEL_LLM_GLOBAL},
  "spo_verify_mode": "${VERIFY_MODE}",
  "spo_request_batch_chars": ${BATCH_CHARS},
  "spo_request_batch_size": ${BATCH_SIZE},
  "structure_workers": ${STRUCTURE_WORKERS},
  "xml_parse_chunk": ${XML_PARSE_CHUNK},
  "quality_max_full_only_docs_pct": ${QUALITY_MAX_FULL_ONLY_DOCS_PCT},
  "manifest_name": "${MANIFEST_NAME}",
  "manifest_uri": "${MANIFEST_URI}",
  "output_prefix": "${OUTPUT_PREFIX}",
  "resume_cache_enabled": ${RESUME_CACHE_ENABLED},
  "resume_cache_prefix": "${RESUME_CACHE_PREFIX}"
}
EOF

if [ "${SYNC_INTERVAL_SEC}" != "0" ]; then
  (
    while true; do
      sleep "${SYNC_INTERVAL_SEC}"
      sync_outputs || true
    done
  ) &
  SYNC_LOOP_PID="$!"
fi

RUN_ARGS=(
  /opt/venv/bin/python
  /opt/polisyos/policy-engine/tools/cloud/run_lex_from_manifest.py
  --manifest "/mnt/work/input/${MANIFEST_NAME}"
  --output-dir /mnt/work/output
  --shard-count "${SHARD_COUNT}"
  --shard-index "${SHARD_INDEX}"
  --manifest-is-pre-sharded
  --resume
  --stages parse,structure,spo,ground_quotes,resolve_refs
  --parallel-llm "${PARALLEL_LLM}"
  --parallel-llm-global "${PARALLEL_LLM_GLOBAL}"
  --gonka-rate-limit-rps "${RPS}"
  --max-retries 7
  --structure-workers "${STRUCTURE_WORKERS}"
  --xml-parse-chunk "${XML_PARSE_CHUNK}"
  --spo-verify-mode "${VERIFY_MODE}"
  --spo-rate-warmup-seconds "${WARMUP_SEC}"
  --spo-rate-warmup-start-scale "${WARMUP_SCALE}"
  --spo-request-batch-size "${BATCH_SIZE}"
  --spo-request-batch-chars "${BATCH_CHARS}"
  --spo-group-timeout-seconds "${GROUP_TIMEOUT}"
  --spo-adaptive-batch-downshift-enabled
  --spo-adaptive-batch-soft-chars-share 0.85
  --spo-adaptive-rate-enabled
  --spo-adaptive-rate-recovery-factor "${ADAPTIVE_RECOVERY}"
  --spo-adaptive-rate-penalty-multiplier "${ADAPTIVE_PENALTY}"
  --spo-adaptive-rate-max-scale "${ADAPTIVE_MAX_SCALE}"
  --spo-retryable-followup-worker-scale "${FOLLOWUP_SCALE}"
  --spo-retryable-followup-dispatch-rps-scale "${FOLLOWUP_SCALE}"
  --spo-retryable-followup-client-rate-scale "${FOLLOWUP_SCALE}"
  --spo-retryable-followup-client-concurrency-scale "${FOLLOWUP_SCALE}"
  --quality-max-full-only-docs-pct "${QUALITY_MAX_FULL_ONLY_DOCS_PCT}"
  --spo-request-log-enabled
)

if [ "${MAX_DOCS}" != "0" ] && [ -n "${MAX_DOCS}" ]; then
  RUN_ARGS+=(--max-docs "${MAX_DOCS}")
fi

if [ "${STATUS_PASS}" = "current" ]; then
  RUN_ARGS+=(--status-filter "Чинний" "Не набрав чинності" --llm-gap-fill-mode "${GAP_FILL_MODE}" --llm-gap-fill-max-share "${GAP_FILL_SHARE}")
else
  RUN_ARGS+=(--status-filter "Втратив чинність" "Втратив чинність частково" "Дію призупинено" --llm-gap-fill-mode off)
fi

set +e
"${RUN_ARGS[@]}" 2>&1 | tee /mnt/work/output/pipeline.log
PIPE_EXIT=${PIPESTATUS[0]}
set -e

printf '%s\n' "${PIPE_EXIT}" > /mnt/work/output/manifests/pipeline_exit_code.txt
sync_outputs
exit "${PIPE_EXIT}"

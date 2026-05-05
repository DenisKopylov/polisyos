# Lex Production 140K Runbook — Google Cloud Edition

> Updated: April 8, 2026.
> Target deployment: `6` GCE Spot VMs (europe-west1), `6` Gonka accounts × `5` API keys each, full `ЄДРНПА` corpus.
> Data source: fresh ЄДРНПА dump from 2026-03-24.
> Budget: $300 GCP free credits.
> Execution posture: current code path (each worker streams the XML corpus itself) with safe per-pass shard outputs and an explicit local merge before finalize. Optional pre-shard acceleration is documented in Section 2.1 and is not assumed by the scripts below.

---

## 0. GCP Infrastructure

### 0.1 VM Spec: `t2d-standard-2` Spot

| Spec         | Value                                                              |
| ------------ | ------------------------------------------------------------------ |
| vCPUs        | 2 (shared-core Intel/AMD)                                          |
| RAM          | 8 GB                                                               |
| Boot disk    | 80 GB `pd-ssd`                                                     |
| External IP  | 1 per VM (auto-assigned, unique)                                   |
| Provisioning | **Spot** (60-91% discount; auto-stop on preemption)                |
| Image        | Ubuntu 24.04 LTS (`ubuntu-2404-lts-amd64`)                         |
| Zone         | `europe-west1-b` (Belgium — low latency to Gonka 138-node network) |

**Important quota note:** in the fresh `polisyos-lex` project, `europe-west1` exposes `E2_CPUS=8`, so `6 x e2-standard-2` will fail quota checks. `T2D_CPUS=16` in the same region, so `t2d-standard-2` is the safe default for six 2-vCPU workers unless Google raises the E2 quota later.

Spot pricing stays in the same rough band as the original plan and comfortably fits the $300 budget for setup, calibration, and the production run.

### 0.2 Why `t2d-standard-2` (not larger)

| Option               | vCPU  | RAM      | Spot $/hr           | Verdict                                                                     |
| -------------------- | ----: | -------: | ------------------: | --------------------------------------------------------------------------- |
| `e2-small`           | 2     | 2 GB     | $0.007              | **Too tight** — 2 GB marginal for async LLM dispatch + DuckDB               |
| `e2-standard-2`      | 2     | 8 GB     | $0.014              | Good shape, but blocked by the initial `E2_CPUS=8` quota in `europe-west1`  |
| **`t2d-standard-2`** | **2** | **8 GB** | **roughly similar** | **Quota-safe default** — same worker shape, enough regional quota for 6 VMs |
| `n2-standard-2`      | 2     | 8 GB     | $0.020              | Safe fallback if T2D capacity is unavailable in the chosen zone             |
| `e2-standard-4`      | 4     | 16 GB    | $0.027              | Overkill — extra CPU/RAM unused; doubles cost for no gain                   |

### 0.3 IP isolation

Each VM gets a unique external IP automatically. One account per IP — no overlap on key-level, account-level, or IP-level limits.

### 0.4 Cost budget breakdown

| Resource                           | Unit cost                                        | Total     |
| ---------------------------------- | ------------------------------------------------ | --------- |
| 6 × `t2d-standard-2` Spot, 30 days | same order of magnitude as the original estimate | ~$60-90   |
| 6 × 80 GB `pd-ssd`, 30 days        | $0.17/GB/mo × 80 × 6                             | ~$82      |
| GCS storage 50 GB, 30 days         | $0.02/GB/mo                                      | ~$1       |
| GCS egress (download results)      | $0.12/GB × 50 GB                                 | ~$6       |
| Secret Manager (30 secrets)        | free tier                                        | $0        |
| **Total (30 days)**                |                                                  | **~$149** |
| **Remaining from $300**            |                                                  | **~$151** |

Realistic pipeline completion: 5-10 days → actual spend **$25-60**.

---

## 1. Calibration Plan

### 1.1 Why calibrate on GCP specifically

The March 28 smoke test ran locally (Mac) with 5 keys and 1 IP. GCP changes three variables simultaneously:

1. **Network path** — GCE europe-west1 → Gonka latency will differ from local ISP (likely lower and more stable)
2. **6 unique IPs** — possible per-IP rate limit buckets change effective throughput ceiling
3. **30 keys across 6 accounts** — untested aggregate load; `transfer_agent_capacity_reached` threshold is unknown

Local smoke results (March 28) are useful as a **floor estimate**, not a ceiling. Calibration must find the actual GCP ceiling.

### 1.2 Calibration philosophy

**Every run produces useful artifacts.** All calibration runs process real corpus documents with `--resume` on shared GCS output. Subsequent runs skip already-completed docs via `progress.jsonl`. Nothing is thrown away — calibration and production form one continuous pipeline.

**Calibrate on the `current` pass first.** `Чинний` / `Не набрав чинності` is the slower and more LLM-heavy pass. Once its safe ceiling is known, apply the locked config to the `historical` pass with the same or lower pressure. A good default is: keep the same `rps` / `parallel-llm`, but start `historical` with `parallel-llm-global` lowered by `10-20%` for the first `~200` docs per shard, then raise it back if `429` stays low.

**All 6 VMs work from the start, but in roles.** Instead of ramping up 1 → 6, we launch 6 VMs in every phase. During calibration they should not all run the same hottest config: keep `2` control lanes, `2` main pressure probes, `1` orthogonal experiment (`verify` / `batch`), and `1` optimistic production candidate. This keeps all 6 servers productive without turning calibration into one large correlated stress blast.

**Phase 1 needs at least one duplicate control.** Shards are not perfectly homogeneous. A repeated baseline on a second shard is the cheapest way to tell whether a result comes from the config or from shard/doc mix.

**Reduce per-VM pressure before reducing VM count.** The provider sees aggregate pressure from `30` keys. If `429` / `transfer_agent_capacity_reached` rises across all shards, first lower `rps` or `parallel-llm-global` while keeping all 6 VMs active and producing docs.

**Test code-aware knobs, not only raw batch size.** The Lex pipeline already downshifts large/outlier documents internally, so Phase 1 should spend real budget on `--parallel-llm-global` and `--spo-verify-mode`, not just neighboring `batch-chars` values.

### 1.3 Phase 1 — Parallel hypothesis sweep (1-2 hours, ~$0.17)

**Goal:** Find the safe operating band on GCE, not the absolute single-shard peak. 6 VMs stay active, but one hypothesis is duplicated as a control so we can estimate shard variance while still probing higher pressure and verify mode.

**VM ← hypothesis mapping:**

| VM             | Hypothesis                  | RPS | parallel-llm | global cap | verify | batch-chars | Rationale                                                                      |
| -------------- | --------------------------- | --: | -----------: | ---------: | ------ | ----------: | ------------------------------------------------------------------------------ |
| `lex-worker-0` | **Baseline A** (local-like) | 5.0 | 16           | 64         | `llm`  | 3600        | Reference point — reproduce the conservative local shape on GCE                |
| `lex-worker-1` | **Baseline B** (replica)    | 5.0 | 16           | 64         | `llm`  | 3600        | Same config on another shard — measures shard/time-window variance             |
| `lex-worker-2` | **Higher RPS**              | 8.0 | 20           | 80         | `llm`  | 3600        | Test if GCE lower latency allows a moderate RPS lift per key                   |
| `lex-worker-3` | **Higher concurrency**      | 5.0 | 30           | 80         | `llm`  | 3600        | Same RPS but more parallel flights — tests if concurrency is the bottleneck    |
| `lex-worker-4` | **Code verify**             | 5.0 | 16           | 64         | `code` | 3600        | Is second-pass LLM verification the main cost/latency driver?                  |
| `lex-worker-5` | **Aggressive capped combo** | 9.0 | 25           | 80         | `code` | 4800        | Optimistic production candidate, but still capped below a full “blast” profile |

All other parameters are shared (`structure-workers=2`, `xml-parse-chunk=2000`, warmup, adaptive rate, retries, etc.).

**Launch:**

```bash
./create_workers.sh phase1
```

This runs `create_workers.sh` in `phase1` mode, which creates 6 VMs with per-VM metadata overrides (see Section 5.7).

**Measure after completion** (on your Mac, after all 6 VMs self-shutdown):

```bash
# Download all telemetry
./collect_telemetry.sh

# Compare hypotheses side-by-side
python3 tools/ops/calibration/compare_shards.py /tmp/calibration/
```

The comparison script (Section 5.9) outputs a table like:

```text
Shard  Hypothesis            Verify  GCap  Docs  RPS_eff  429%  cap_reached%  p50_ms  p90_ms  docs/hr
─────  ─────────────────────  ──────  ────  ────  ───────  ────  ────────────  ──────  ──────  ───────
0      baseline_a            llm     64    50    4.2      8%    1%            9200    22000   38
1      baseline_b            llm     64    50    4.0      7%    1%            9400    22500   37
2      higher_rps            llm     80    50    6.8      12%   2%            8500    19000   55
3      higher_concurrency    llm     80    50    4.8      6%    0%            8800    20000   44
4      code_verify           code    64    50    4.1      4%    0%            7100    15000   49
5      aggressive_capped     code    80    50    7.5      15%   3%            9500    24000   60
```

**Decision table:**

| Pattern                                                                       | Interpretation                                                             | Action for Phase 2                                                                             |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `baseline_a` and `baseline_b` are close (docs/hr within ~10%, 429 within ~3%) | Shard variance is acceptable; Phase 1 ranking is meaningful                | Trust the winners and move on                                                                  |
| `baseline_a` and `baseline_b` diverge strongly                                | Shard/doc mix is distorting raw docs/hr                                    | Use request metrics first, then repeat the top config and baseline at the same hour            |
| `higher_rps` beats both baselines with 429 < 15%                              | Safe operating band is above the local floor                               | Phase 2: test 9, 10, 11 RPS                                                                    |
| `higher_concurrency` best docs/hr, low 429                                    | Concurrency was the bottleneck, not RPS                                    | Phase 2: push concurrency further (35, 40)                                                     |
| `code_verify` matches or beats baseline with fewer 429 / lower latency        | Verify LLM pass is wasted pressure for this corpus slice                   | Phase 2: keep `--spo-verify-mode code` as default                                              |
| `higher_rps` / `higher_concurrency` add errors faster than throughput         | The provider is sensitive to burst pressure, not just nominal worker count | Phase 2: tune `--parallel-llm-global` around the winner before pushing harder                  |
| `aggressive_capped` best overall                                              | Best combined guess — validate stability with replicas plus controls       | Phase 2: promote it to the winner lanes                                                        |
| All shards show `capacity_reached` > 10%                                      | Gonka is saturated by aggregate pressure, not by one bad VM                | Keep all 6 VMs, but lower per-VM `rps` / `global cap` by `20-30%` and preserve 2 control lanes |
| All shards 429 < 5% and `aggressive_capped` wins                              | We're still below the ceiling                                              | Phase 2: test 10-11 RPS or a higher `parallel-llm-global`                                      |

### 1.4 Phase 2 — Validate winner + explore edges (2-3 hours, ~$0.25)

Based on Phase 1 results, keep all 6 VMs active but rebalance them into 4 roles: `2` winner replicas, `2` upper-edge probes, `1` conservative control, and `1` lower-pressure sentinel. This gives better diagnostics than running 6 identical copies too early.

**Example** (assuming Phase 1 winner was `aggressive_capped` at `rps=9`, `parallel=25`, `global=80`, `verify=code`, `batch=4800`):

| VM             | Config               | RPS  | parallel-llm | global cap | verify | batch-chars | Purpose                                             |
| -------------- | -------------------- | ---: | -----------: | ---------: | ------ | ----------: | --------------------------------------------------- |
| `lex-worker-0` | Winner               | 9.0  | 25           | 80         | `code` | 4800        | Stability check                                     |
| `lex-worker-1` | Winner               | 9.0  | 25           | 80         | `code` | 4800        | Stability check                                     |
| `lex-worker-2` | RPS +20%             | 11.0 | 25           | 80         | `code` | 4800        | Can we push RPS further?                            |
| `lex-worker-3` | Concurrency +40%     | 9.0  | 35           | 96         | `code` | 4800        | Concurrency headroom?                               |
| `lex-worker-4` | Conservative control | 6.0  | 16           | 64         | `code` | 3600        | Same time window, lower pressure baseline           |
| `lex-worker-5` | Lower global cap     | 9.0  | 25           | 64         | `code` | 4800        | Does a tighter in-flight cap improve docs/hr / 429? |

200 new docs per VM. Same `--resume` — builds on Phase 1's 50 docs per shard.

**Launch:**

```bash
./create_workers.sh phase2
```

**Decision:**

- If both "winner" VMs beat the conservative control and stay close to each other (429 variance < 3%) → config is stable, lock for production.
- If one of the edge VMs shows better docs/hr without a 429 spike → adopt it as the new winner.
- If the lower global cap matches winner throughput with cleaner errors → prefer the lower cap for production.
- If winner and control both deteriorate at the same hour → external provider load changed; rerun the same matrix later.

### 1.5 Phase 3 — Production (removes `--max-docs`)

All 6 VMs run the locked configuration. Remove `--max-docs` — each VM resumes from its existing ~250 checkpoint docs and processes the full shard.

```bash
./create_workers.sh production
```

**Artifacts from Phase 1-2 (~1500 docs total) are already committed** to `progress.jsonl` and GCS output. Phase 3 skips them automatically.

---

## 2. Corpus & Goal

Process the full `~140K`-document corpus with a mixed policy:

- `Чинний` + `Не набрав чинності`: `Current wide-like` (narrow gap-fill)
- `Втратив чинність` + rare statuses: `Primary only` (gap-fill off)

### Corpus split

| Status                      | Est. Docs     | Mode              |
| --------------------------- | ------------: | ----------------- |
| `Чинний`                    | ~99,000       | Current wide-like |
| `Не набрав чинності`        | ~330          | Current wide-like |
| `Втратив чинність`          | ~40,500       | Primary only      |
| `Втратив чинність частково` | ~490          | Primary only      |
| `Дію призупинено`           | ~35           | Primary only      |
| **Total**                   | **~140,000+** | mixed             |

### Fresh data — ЄДРНПА dump 2026-03-24

- Cards: `https://nais.gov.ua/files/general/2026/03/24/20260324092127-31.zip`
- Texts: `https://nais.gov.ua/files/general/2026/03/24/20260324092508-20.zip`

### 2.1 Optional fast path — pre-materialize per-pass shard inputs locally

The scripts in this runbook assume the **current code path**: each VM parses the XML dump itself and filters to its shard in-process. That is safe, but not optimal: with `6` workers we still pay for `6` full scans of the texts XML.

If you are willing to add a small helper before production, the best acceleration is:

1. Stream `cards.xml` + `texts.xml` **once** on your Mac or one staging VM.
2. Build `NPADocument` rows using the same `doc_id` logic as `polisyos.data_forge.domains.legal.batch.xml_parser._stable_doc_id(...)`.
3. Assign shard using the same hash rule as `BatchConfig.is_doc_in_shard(...)`.
4. Write separate per-pass shard manifests such as:

   - `gs://polisyos-lex-data/input/shards/current/shard_00.jsonl.zst`
   - `gs://polisyos-lex-data/input/shards/historical/shard_00.jsonl.zst`
5. Run each worker only against its own pre-materialized manifest.

Important:

- Do **not** split raw XML by file size or by `reestr_code` alone.
- The XML join logic is package-aware (`reestr_code` is not unique), so pre-sharding must happen **after** the card/text join and `doc_id` derivation.
- This is a recommended follow-up optimization, not a requirement for the commands below.

---

## 3. Local smoke baseline (March 28, for reference)

> These numbers are from a local Mac run, 5 keys, 1 IP. GCP results will differ.

| Metric                        | Value             |
| ----------------------------- | ----------------- |
| Wall time                     | 7.05 h (300 docs) |
| Docs/hour                     | 42.6              |
| Avg latency                   | 13.7 s            |
| p90 latency                   | 29.0 s            |
| HTTP 200                      | 77%               |
| HTTP 429                      | 11.9%             |
| HTTP 503                      | 11.0%             |
| Provisions/doc (heavy sample) | 360               |
| Gate LLM-saved                | 39.45%            |
| Gap-fill null yield           | 39.6%             |

---

## 4. Sharding Topology

6 shards — one per VM, one per Gonka account, one per IP.

| VM             | Shard | Gonka Account | Keys                 | External IP |
| -------------- | ----: | ------------- | -------------------- | ----------- |
| `lex-worker-0` | `0`   | Account 1     | `GONKA_API_KEY_1..5` | unique      |
| `lex-worker-1` | `1`   | Account 2     | `GONKA_API_KEY_1..5` | unique      |
| `lex-worker-2` | `2`   | Account 3     | `GONKA_API_KEY_1..5` | unique      |
| `lex-worker-3` | `3`   | Account 4     | `GONKA_API_KEY_1..5` | unique      |
| `lex-worker-4` | `4`   | Account 5     | `GONKA_API_KEY_1..5` | unique      |
| `lex-worker-5` | `5`   | Account 6     | `GONKA_API_KEY_1..5` | unique      |

Operational rules:

- In sharded mode run only `parse,structure,spo,ground_quotes,resolve_refs`.
- `graph`, `export_claims`, `benchmark`, `qc`, `publish_bundle` — single-process finalize pass after all shards complete.
- Use `--clean-output` only on shard 0, only on the very first fresh run.
- Keep **separate GCS prefixes per status pass**: `output/current/shard_N/...` and `output/historical/shard_N/...`.
- In code, shard-local state lives under `_shards/shard_XX_of_06/...`, not at the bucket root.
- Root-level files such as `manifests/doc_metadata.json`, `manifests/llm_gate.json`, `manifests/telemetry.json`, `manifests/llm_requests.jsonl`, and `llm_gate_audit.jsonl` are **per-run shard-local manifests**. Never merge shards by blindly overwriting them into one directory; aggregate them explicitly before finalize.

---

## 5. GCP Setup (from zero)

### 5.1 Install gcloud CLI (on your Mac)

```bash
brew install google-cloud-sdk
gcloud auth login
```

### 5.2 Create project & activate $300 credits

```bash
gcloud projects create polisyos-lex --name="PolicyOS Lex Pipeline"
gcloud config set project polisyos-lex

# Go to https://console.cloud.google.com/billing → Start Free Trial
# Then link billing:
gcloud billing projects link polisyos-lex \
  --billing-account=XXXXXX-XXXXXX-XXXXXX
```

### 5.3 Enable APIs

```bash
gcloud services enable \
  compute.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

### 5.4 Store Gonka keys in Secret Manager

```bash
# For each of 6 accounts × 5 keys:
# Format: gonka-acc{N}-key{M}
echo -n "gp-actual-key-here" | gcloud secrets create gonka-acc1-key1 --data-file=-
echo -n "gp-actual-key-here" | gcloud secrets create gonka-acc1-key2 --data-file=-
# ... repeat for all 30 keys

# Or use a script with keys.csv (acc_num,key_num,actual_key):
while IFS=, read -r acc key value; do
  echo -n "$value" | gcloud secrets create "gonka-acc${acc}-key${key}" --data-file=-
done < keys.csv
```

### 5.5 Create GCS bucket & upload data

```bash
gcloud storage buckets create gs://polisyos-lex-data \
  --location=europe-west1 \
  --default-storage-class=STANDARD

# Upload raw corpus once
gcloud storage cp edrnpa_cards_2026-03-24.xml gs://polisyos-lex-data/input/raw/
gcloud storage cp edrnpa_texts_2026-03-24.xml gs://polisyos-lex-data/input/raw/

# Optional future fast path (Section 2.1):
# gcloud storage cp shard manifests to:
#   gs://polisyos-lex-data/input/shards/current/
#   gs://polisyos-lex-data/input/shards/historical/

# Output layout used by this runbook:
#   gs://polisyos-lex-data/output/current/shard_0/
#   gs://polisyos-lex-data/output/current/shard_1/
#   ...
#   gs://polisyos-lex-data/output/historical/shard_0/
#   ...
```

### 5.6 Startup script

Save as `gcp/startup.sh`. The script reads **all tunable parameters from VM metadata**, so each VM can run a different configuration without changing the script.

```bash
#!/bin/bash
set -euo pipefail
exec > /var/log/lex-startup.log 2>&1

_meta() {
  curl -sf "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1" \
    -H "Metadata-Flavor: Google" || echo "$2"
}

# ---------- Read all parameters from VM metadata ----------
SHARD_INDEX=$(_meta shard-index 0)
SHARD_COUNT=$(_meta shard-count 6)
ACCOUNT_NUM=$(_meta account-num 1)
MAX_DOCS=$(_meta max-docs 0)
RPS=$(_meta rps 5.0)
PARALLEL_LLM=$(_meta parallel-llm 20)
PARALLEL_LLM_GLOBAL=$(_meta parallel-llm-global 64)
BATCH_CHARS=$(_meta batch-chars 3600)
BATCH_SIZE=$(_meta batch-size 4)
WARMUP_SEC=$(_meta warmup-sec 30)
WARMUP_SCALE=$(_meta warmup-scale 2.0)
ADAPTIVE_RECOVERY=$(_meta adaptive-recovery 0.97)
ADAPTIVE_PENALTY=$(_meta adaptive-penalty 1.35)
ADAPTIVE_MAX_SCALE=$(_meta adaptive-max-scale 4.0)
GROUP_TIMEOUT=$(_meta group-timeout 45)
VERIFY_MODE=$(_meta spo-verify-mode llm)
STRUCTURE_WORKERS=$(_meta structure-workers 2)
XML_PARSE_CHUNK=$(_meta xml-parse-chunk 2000)
GAP_FILL_MODE=$(_meta gap-fill-mode narrow)
GAP_FILL_SHARE=$(_meta gap-fill-share 0.10)
STATUS_PASS=$(_meta status-pass current)
HYPOTHESIS=$(_meta hypothesis unnamed)
FOLLOWUP_SCALE=$(_meta followup-scale 0.85)
SHARD_SLUG=$(printf "shard_%02d_of_%02d" "$SHARD_INDEX" "$SHARD_COUNT")
REMOTE_PREFIX="gs://polisyos-lex-data/output/${STATUS_PASS}/shard_${SHARD_INDEX}"

echo "=== Worker shard=${SHARD_INDEX}/${SHARD_COUNT} account=${ACCOUNT_NUM} hypothesis=${HYPOTHESIS} ==="
echo "    status=${STATUS_PASS} rps=${RPS} parallel=${PARALLEL_LLM} global=${PARALLEL_LLM_GLOBAL} verify=${VERIFY_MODE} batch_chars=${BATCH_CHARS} max_docs=${MAX_DOCS}"

# ---------- System packages ----------
apt-get update -qq
apt-get install -y -qq software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -qq
apt-get install -y -qq python3.14 python3.14-venv python3.14-dev git curl

# ---------- Work directory ----------
mkdir -p /mnt/work/{input,output}
mkdir -p /mnt/work/output/manifests

# ---------- Download corpus from GCS ----------
# Current executable plan still uses the raw XML input path.
# Optional pre-sharded manifests are documented in Section 2.1 but are not assumed here.
gcloud storage cp gs://polisyos-lex-data/input/raw/edrnpa_cards_2026-03-24.xml /mnt/work/input/
gcloud storage cp gs://polisyos-lex-data/input/raw/edrnpa_texts_2026-03-24.xml /mnt/work/input/

# ---------- Restore previous output from GCS (for --resume) ----------
gcloud storage rsync -r "${REMOTE_PREFIX}/" /mnt/work/output/ 2>/dev/null || true

# ---------- Clone repo & install ----------
cd /opt
git clone https://github.com/YOUR_USER/polisyos.git 2>/dev/null || (cd polisyos && git pull)
cd /opt/polisyos/policy-engine

python3.14 -m venv /opt/venv
source /opt/venv/bin/activate
pip install --quiet -e ".[batch]"

# ---------- Load Gonka keys from Secret Manager ----------
for i in 1 2 3 4 5; do
  KEY_VALUE=$(gcloud secrets versions access latest --secret="gonka-acc${ACCOUNT_NUM}-key${i}" 2>/dev/null || echo "")
  if [ -n "$KEY_VALUE" ]; then
    export "GONKA_API_KEY_${i}"="$KEY_VALUE"
    echo "  Loaded GONKA_API_KEY_${i}"
  fi
done

# ---------- Persist per-run config for later shard comparison/merge ----------
cat > /mnt/work/output/manifests/run_config.json <<EOF
{
  "shard_index": ${SHARD_INDEX},
  "shard_count": ${SHARD_COUNT},
  "shard_slug": "${SHARD_SLUG}",
  "account_num": ${ACCOUNT_NUM},
  "status_pass": "${STATUS_PASS}",
  "hypothesis": "${HYPOTHESIS}",
  "rps": ${RPS},
  "parallel_llm": ${PARALLEL_LLM},
  "parallel_llm_global": ${PARALLEL_LLM_GLOBAL},
  "spo_verify_mode": "${VERIFY_MODE}",
  "spo_request_batch_chars": ${BATCH_CHARS},
  "spo_request_batch_size": ${BATCH_SIZE},
  "structure_workers": ${STRUCTURE_WORKERS},
  "xml_parse_chunk": ${XML_PARSE_CHUNK}
}
EOF

# ---------- Build CLI args ----------
MAX_DOCS_FLAG=""
if [ "$MAX_DOCS" != "0" ] && [ -n "$MAX_DOCS" ]; then
  MAX_DOCS_FLAG="--max-docs $MAX_DOCS"
fi

if [ "$STATUS_PASS" = "current" ]; then
  STATUS_FLAGS="--status-filter Чинний \"Не набрав чинності\" --llm-gap-fill-mode ${GAP_FILL_MODE} --llm-gap-fill-max-share ${GAP_FILL_SHARE}"
else
  STATUS_FLAGS="--status-filter \"Втратив чинність\" \"Втратив чинність частково\" \"Дію призупинено\" --llm-gap-fill-mode off"
fi

# ---------- Run pipeline ----------
source /opt/venv/bin/activate
cd /opt/polisyos/policy-engine

eval python3 -m polisyos.data_forge.domains.legal.batch run \
  --cards /mnt/work/input/edrnpa_cards_2026-03-24.xml \
  --texts /mnt/work/input/edrnpa_texts_2026-03-24.xml \
  --output-dir /mnt/work/output \
  --shard-count "$SHARD_COUNT" \
  --shard-index "$SHARD_INDEX" \
  --resume \
  $MAX_DOCS_FLAG \
  --stages parse,structure,spo,ground_quotes,resolve_refs \
  --parallel-llm "$PARALLEL_LLM" \
  --parallel-llm-global "$PARALLEL_LLM_GLOBAL" \
  --gonka-rate-limit-rps "$RPS" \
  --max-retries 7 \
  --structure-workers "$STRUCTURE_WORKERS" \
  --xml-parse-chunk "$XML_PARSE_CHUNK" \
  --spo-verify-mode "$VERIFY_MODE" \
  --spo-rate-warmup-seconds "$WARMUP_SEC" \
  --spo-rate-warmup-start-scale "$WARMUP_SCALE" \
  --spo-request-batch-size "$BATCH_SIZE" \
  --spo-request-batch-chars "$BATCH_CHARS" \
  --spo-group-timeout-seconds "$GROUP_TIMEOUT" \
  --spo-adaptive-batch-downshift-enabled \
  --spo-adaptive-batch-soft-chars-share 0.85 \
  --spo-adaptive-rate-enabled \
  --spo-adaptive-rate-recovery-factor "$ADAPTIVE_RECOVERY" \
  --spo-adaptive-rate-penalty-multiplier "$ADAPTIVE_PENALTY" \
  --spo-adaptive-rate-max-scale "$ADAPTIVE_MAX_SCALE" \
  --spo-retryable-followup-worker-scale "$FOLLOWUP_SCALE" \
  --spo-retryable-followup-dispatch-rps-scale "$FOLLOWUP_SCALE" \
  --spo-retryable-followup-client-rate-scale "$FOLLOWUP_SCALE" \
  --spo-retryable-followup-client-concurrency-scale "$FOLLOWUP_SCALE" \
  --spo-request-log-enabled \
  $STATUS_FLAGS \
  --embedding-device cpu \
  2>&1 | tee /mnt/work/output/pipeline.log

# ---------- Upload results to GCS ----------
gcloud storage rsync -r /mnt/work/output/ \
  "${REMOTE_PREFIX}/"

echo "=== DONE at $(date -u). Shutting down. ==="
sudo shutdown -h now
```

### 5.7 Create VMs — `create_workers.sh`

The script supports named modes. Each mode defines per-VM parameter overrides.

Save as `gcp/create_workers.sh`:

```bash
#!/bin/bash
set -euo pipefail

MODE=${1:?Usage: ./create_workers.sh <phase1|phase2|production|custom> [status-pass]}
STATUS_PASS=${2:-current}
ZONE="europe-west1-b"
SHARD_COUNT=6

# ── Shared defaults ──
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

# ── Per-VM overrides: arrays indexed 0..5 ──
# Each array element corresponds to lex-worker-{i}.
# Only the parameters that vary per hypothesis need arrays.

case "$MODE" in

  phase1)
    #                         VM-0: baseline A  VM-1: baseline B  VM-2: higher_rps VM-3: hi_concur   VM-4: code_verify VM-5: aggressive
    MAX_DOCS=(                50                50                50               50                50                50              )
    RPS=(                     5.0               5.0               8.0              5.0               5.0               9.0             )
    PARALLEL_LLM=(            16                16                20               30                16                25              )
    PARALLEL_LLM_GLOBAL=(     64                64                80               80                64                80              )
    VERIFY_MODE=(             llm               llm               llm              llm               code              code            )
    BATCH_CHARS=(             3600              3600              3600             3600              3600              4800            )
    HYPOTHESIS=(              baseline_a        baseline_b        higher_rps       higher_concurrency code_verify       aggressive_capped)
    ;;

  phase2)
    # Fill after Phase 1 analysis. Example assuming "aggressive_capped" won:
    #                         VM-0: winner      VM-1: winner      VM-2: rps+20%    VM-3: concur+40%  VM-4: control     VM-5: low_global
    MAX_DOCS=(                200               200               200              200               200               200             )
    RPS=(                     9.0               9.0               11.0             9.0               6.0               9.0             )
    PARALLEL_LLM=(            25                25                25               35                16                25              )
    PARALLEL_LLM_GLOBAL=(     80                80                80               96                64                64              )
    VERIFY_MODE=(             code              code              code             code              code              code            )
    BATCH_CHARS=(             4800              4800              4800             4800              3600              4800            )
    HYPOTHESIS=(              winner_a          winner_b          rps_plus20       concur_plus40     control           low_global_cap  )
    ;;

  production)
    # All VMs use the locked config. Fill after Phase 2.
    #                         VM-0              VM-1              VM-2             VM-3              VM-4              VM-5
    MAX_DOCS=(                0                 0                 0                0                 0                 0               )
    RPS=(                     9.0               9.0               9.0              9.0               9.0               9.0             )
    PARALLEL_LLM=(            25                25                25               25                25                25              )
    PARALLEL_LLM_GLOBAL=(     80                80                80               80                80                80              )
    VERIFY_MODE=(             code              code              code             code              code              code            )
    BATCH_CHARS=(             4800              4800              4800             4800              4800              4800            )
    HYPOTHESIS=(              prod              prod              prod             prod              prod              prod            )
    ;;

  custom)
    echo "Edit the 'custom' case in this script with your per-VM values, then re-run."
    exit 1
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Usage: ./create_workers.sh <phase1|phase2|production|custom> [current|historical]"
    exit 1
    ;;
esac

echo "=== Creating 6 VMs: mode=$MODE status=$STATUS_PASS ==="
echo ""

for i in $(seq 0 5); do
  ACCOUNT_NUM=$((i + 1))

  META="shard-index=${i}"
  META="${META},shard-count=${SHARD_COUNT}"
  META="${META},account-num=${ACCOUNT_NUM}"
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
  META="${META},status-pass=${STATUS_PASS}"
  META="${META},hypothesis=${HYPOTHESIS[$i]}"

  gcloud compute instances create "lex-worker-${i}" \
    --zone="$ZONE" \
    --machine-type="${MACHINE_TYPE:-t2d-standard-2}" \
    --boot-disk-size=80GB \
    --boot-disk-type=pd-ssd \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --scopes=storage-full,cloud-platform \
    --metadata="$META" \
    --metadata-from-file=startup-script=gcp/startup.sh \
    --tags=lex-worker \
    --provisioning-model=SPOT \
    --instance-termination-action=STOP

  printf "  lex-worker-%-2d  acc=%d  hypothesis=%-18s  rps=%-5s  parallel=%-3s  global=%-3s  verify=%-4s  batch_chars=%-5s  max_docs=%s\n" \
    "$i" "$ACCOUNT_NUM" "${HYPOTHESIS[$i]}" "${RPS[$i]}" "${PARALLEL_LLM[$i]}" "${PARALLEL_LLM_GLOBAL[$i]}" "${VERIFY_MODE[$i]}" "${BATCH_CHARS[$i]}" "${MAX_DOCS[$i]}"
done

echo ""
echo "=== External IPs ==="
gcloud compute instances list --filter="tags.items=lex-worker" \
  --format="table(name, networkInterfaces[0].accessConfigs[0].natIP, status)"
```

### 5.8 Collect telemetry — `collect_telemetry.sh`

Save as `gcp/collect_telemetry.sh`:

```bash
#!/bin/bash
set -euo pipefail

OUT_DIR="${1:-/tmp/calibration}"
STATUS_PASS="${2:-current}"
mkdir -p "$OUT_DIR"

for i in $(seq 0 5); do
  SHARD_SLUG=$(printf "shard_%02d_of_06" "$i")
  REMOTE_PREFIX="gs://polisyos-lex-data/output/${STATUS_PASS}/shard_${i}"
  echo "Shard $i:"
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/llm_requests.jsonl" \
    "$OUT_DIR/shard_${i}_llm_requests.jsonl" 2>/dev/null || echo "  (no telemetry yet)"
  gcloud storage cp \
    "${REMOTE_PREFIX}/_shards/${SHARD_SLUG}/progress.jsonl" \
    "$OUT_DIR/shard_${i}_progress.jsonl" 2>/dev/null || echo "  (no progress yet)"
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/telemetry.json" \
    "$OUT_DIR/shard_${i}_telemetry.json" 2>/dev/null || true
  gcloud storage cp \
    "${REMOTE_PREFIX}/manifests/run_config.json" \
    "$OUT_DIR/shard_${i}_run_config.json" 2>/dev/null || true
done

echo ""
echo "Telemetry saved to $OUT_DIR (status-pass=${STATUS_PASS})"
echo "Run:  python3 tools/ops/calibration/compare_shards.py $OUT_DIR"
```

### 5.9 Compare hypotheses — `compare_shards.py`

Save as `tools/ops/calibration/compare_shards.py`:

```python
#!/usr/bin/env python3
"""Compare calibration results across shards/hypotheses."""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def analyze_shard(
    telemetry_path: Path,
    progress_path: Path,
    run_config_path: Path,
    stage_telemetry_path: Path,
    shard_idx: int,
) -> dict:
    rows = _load_jsonl(telemetry_path)
    progress = _load_jsonl(progress_path)
    run_cfg = _load_json(run_config_path)
    stage_telemetry = _load_json(stage_telemetry_path)
    if not rows:
        return {
            "shard": shard_idx,
            "hypothesis": run_cfg.get("hypothesis", "unknown"),
            "verify": run_cfg.get("spo_verify_mode", "?"),
            "global_cap": run_cfg.get("parallel_llm_global", 0),
            "status": "no_data",
        }

    ok = [r for r in rows if r.get("http_status") == 200]
    err_429 = [r for r in rows if r.get("http_status") == 429]
    lats = [r["total_latency_ms"] for r in ok if "total_latency_ms" in r]

    # Time span
    epochs = [r["completed_at_epoch_ms"] for r in rows if "completed_at_epoch_ms" in r]
    span_sec = (max(epochs) - min(epochs)) / 1000 if len(epochs) > 1 else 1

    # Error breakdown
    err_classes = Counter(
        r.get("error_class", "unknown") for r in rows if r.get("http_status") != 200
    )

    # Docs completed (exclude __global__ entries)
    doc_ids = {e["doc_id"] for e in progress if e.get("doc_id") != "__global__"}

    return {
        "shard": shard_idx,
        "hypothesis": run_cfg.get("hypothesis", "unknown"),
        "verify": run_cfg.get("spo_verify_mode", "?"),
        "global_cap": run_cfg.get("parallel_llm_global", 0),
        "docs": len(doc_ids),
        "total_requests": len(rows),
        "ok": len(ok),
        "pct_429": round(100 * len(err_429) / max(1, len(rows)), 1),
        "pct_capacity_reached": round(
            100 * err_classes.get("transfer_agent_capacity_reached", 0) / max(1, len(rows)), 1
        ),
        "rps_effective": round(len(ok) / max(1, span_sec), 2),
        "p50_ms": round(statistics.median(lats)) if lats else 0,
        "p90_ms": round(statistics.quantiles(lats, n=10)[8]) if len(lats) >= 10 else 0,
        "docs_per_hour": round(len(doc_ids) / max(0.001, span_sec / 3600), 1),
        "error_breakdown": dict(err_classes.most_common(5)),
        "stage_times": stage_telemetry.get("stage_times", {}),
    }


def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/calibration")

    results = []
    for i in range(6):
        results.append(
            analyze_shard(
                data_dir / f"shard_{i}_llm_requests.jsonl",
                data_dir / f"shard_{i}_progress.jsonl",
                data_dir / f"shard_{i}_run_config.json",
                data_dir / f"shard_{i}_telemetry.json",
                i,
            )
        )

    # Header
    fmt = "{:>5}  {:>20}  {:>6}  {:>5}  {:>6}  {:>8}  {:>6}  {:>13}  {:>8}  {:>8}  {:>9}"
    print(fmt.format(
        "Shard", "Hypothesis", "Verify", "GCap", "Docs", "RPS_eff",
        "429%", "cap_reached%", "p50_ms", "p90_ms", "docs/hr",
    ))
    print("─" * 120)

    for r in results:
        if r.get("status") == "no_data":
            print(
                fmt.format(
                    r["shard"],
                    r.get("hypothesis", "unknown")[:20],
                    r.get("verify", "?"),
                    r.get("global_cap", 0),
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                )
            )
            continue
        print(fmt.format(
            r["shard"],
            r["hypothesis"][:20],
            r["verify"],
            r["global_cap"],
            r["docs"],
            r["rps_effective"],
            r["pct_429"],
            r["pct_capacity_reached"],
            r["p50_ms"],
            r["p90_ms"],
            r["docs_per_hour"],
        ))

    print()
    for r in results:
        if r.get("error_breakdown"):
            print(f"  Shard {r['shard']} errors: {r['error_breakdown']}")
        if r.get("stage_times"):
            print(f"  Shard {r['shard']} stage_times: {r['stage_times']}")


if __name__ == "__main__":
    main()
```

### 5.10 Delete VMs — `delete_workers.sh`

Save as `gcp/delete_workers.sh`:

```bash
#!/bin/bash
ZONE="europe-west1-b"
for i in $(seq 0 5); do
  gcloud compute instances delete "lex-worker-${i}" --zone="$ZONE" --quiet 2>/dev/null && \
    echo "Deleted lex-worker-${i}" || echo "lex-worker-${i} not found"
done
```

---

## 6. Tuned LLM Parameters

### 6.1 Starting parameters (Phase 1 baseline — VM-0)

| Parameter                                | Value  | Rationale                                                                  |
| ---------------------------------------- | ------ | -------------------------------------------------------------------------- |
| `--parallel-llm`                         | `16`   | Per-key concurrency; conservative start                                    |
| `--parallel-llm-global`                  | `64`   | Keep global in-flight pressure below the theoretical `5 × 16 = 80` ceiling |
| `--gonka-rate-limit-rps`                 | `5.0`  | Per-key RPS; validated in local smoke                                      |
| `--max-retries`                          | `7`    | Longer retry budget for Spot VM resilience                                 |
| `--structure-workers`                    | `2`    | Matches the 2-vCPU worker shape; avoids Mac-tuned over-parallelism         |
| `--xml-parse-chunk`                      | `2000` | Lower memory pressure on 8 GB VMs                                          |
| `--spo-verify-mode`                      | `llm`  | Keep VM-0 as the local-like reference; VM-4 explicitly tests `code` verify |
| `--spo-rate-warmup-seconds`              | `30`   | Medium warmup — GCE network is stable                                      |
| `--spo-rate-warmup-start-scale`          | `2.0`  | Moderate initial slowdown                                                  |
| `--spo-request-batch-size`               | `4`    | Provisions per LLM request — validated locally                             |
| `--spo-request-batch-chars`              | `3600` | Smaller batches → fewer grouped timeouts                                   |
| `--spo-group-timeout-seconds`            | `45`   | Per-group wall time cap                                                    |
| `--spo-adaptive-rate-enabled`            | `true` | Auto-cooling on 429 bursts                                                 |
| `--spo-adaptive-rate-recovery-factor`    | `0.97` | Conservative recovery                                                      |
| `--spo-adaptive-rate-penalty-multiplier` | `1.35` | Default penalty                                                            |
| `--spo-adaptive-rate-max-scale`          | `4.0`  | Allow deeper throttle than Hetzner                                         |

### 6.2 Phase 1 hypothesis grid (what each VM tests differently)

| Parameter             | VM-0  | VM-1  | VM-2  | VM-3  | VM-4   | VM-5   |
| --------------------- | ----: | ----: | ----: | ----: | -----: | -----: |
| `rps`                 | 5.0   | 5.0   | 8.0   | 5.0   | 5.0    | 9.0    |
| `parallel-llm`        | 16    | 16    | 20    | 30    | 16     | 25     |
| `parallel-llm-global` | 64    | 64    | 80    | 80    | 64     | 80     |
| `spo-verify-mode`     | `llm` | `llm` | `llm` | `llm` | `code` | `code` |
| `batch-chars`         | 3600  | 3600  | 3600  | 3600  | 3600   | 4800   |

All other parameters remain at baseline defaults.

### 6.3 Gap-fill policy

| Pass                | Status filter                                                      | Gap-fill mode | Gap-fill max share |
| ------------------- | ------------------------------------------------------------------ | ------------- | ------------------ |
| Pass 1 (current)    | `Чинний`, `Не набрав чинності`                                     | `narrow`      | `0.10`             |
| Pass 2 (historical) | `Втратив чинність`, `Втратив чинність частково`, `Дію призупинено` | `off`         | —                  |

### 6.4 Expected time estimates (production, after calibration)

| Scenario                 | Docs/shard | Aggregate RPS (6 VMs) | Est. time per shard |
| ------------------------ | ---------: | --------------------: | ------------------- |
| Conservative (5 rps/key) | ~23,300    | ~150 effective        | ~5-8 days           |
| Tuned (7-9 rps/key)      | ~23,300    | ~210-270 effective    | ~3-6 days           |
| Aggressive (12 rps/key)  | ~23,300    | ~360 effective        | ~2-3 days           |

> Pass 2 (historical, gap-fill off) runs ~2-3× faster per doc than pass 1.

---

## 7. Monitoring

### 7.1 From your Mac

```bash
STATUS_PASS=current

# Status of all VMs
gcloud compute instances list --filter="tags.items=lex-worker"

# SSH into specific VM
gcloud compute ssh lex-worker-0 --zone=europe-west1-b

# Tail pipeline log
gcloud compute ssh lex-worker-0 --zone=europe-west1-b \
  --command="tail -f /mnt/work/output/pipeline.log"

# Serial port output (even if SSH is down)
gcloud compute instances get-serial-port-output lex-worker-0 \
  --zone=europe-west1-b

# Check progress across all shards (via GCS)
for i in $(seq 0 5); do
  SHARD_SLUG=$(printf "shard_%02d_of_06" "$i")
  echo -n "Shard $i: "
  gcloud storage cat "gs://polisyos-lex-data/output/${STATUS_PASS}/shard_${i}/_shards/${SHARD_SLUG}/progress.jsonl" 2>/dev/null | wc -l
done
```

### 7.2 On-VM diagnostics

```bash
# Document progress
find /mnt/work/output/_shards -maxdepth 2 -name progress.jsonl -print -exec wc -l {} \;

# 429 rate
grep -c '"http_status":429' /mnt/work/output/manifests/llm_requests.jsonl 2>/dev/null
grep -c '"http_status":200' /mnt/work/output/manifests/llm_requests.jsonl 2>/dev/null

# Run config / current pass metadata
cat /mnt/work/output/manifests/run_config.json

# Disk usage
df -h /
du -sh /mnt/work/output/

# Live RPS (last 60 seconds of telemetry)
python3 -c "
import json, time
rows = [json.loads(l) for l in open('/mnt/work/output/manifests/llm_requests.jsonl')]
recent = [r for r in rows if r.get('completed_at_epoch_ms', 0) > (time.time() - 60) * 1000]
ok = sum(1 for r in recent if r.get('http_status') == 200)
print(f'Last 60s: {ok} successful requests = {ok/60:.1f} RPS')
"
```

### 7.3 Common issues

| Symptom                                    | Cause                                                                                | Fix                                                                                                          |                  |
| ------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | ---------------- |
| VM in `TERMINATED` state                   | Spot preemption                                                                      | `gcloud compute instances start lex-worker-N` — resume picks up from checkpoint                              |                  |
| Mass 429 (>20%)                            | Aggregate load too high                                                              | Reduce `--gonka-rate-limit-rps`; or stop 1-2 VMs to reduce pressure                                          |                  |
| `transfer_agent_capacity_reached`          | Gonka node saturation (138 nodes)                                                    | Cannot fix with more keys; reduce aggregate RPS or wait for off-peak                                         |                  |
| OOM kill                                   | 8 GB RAM exhausted                                                                   | Reduce `--parallel-llm` to 12; `dmesg                                                                        | tail` to confirm |
| Disk full                                  | Output > 80 GB                                                                       | Sync to GCS and clear: `gcloud storage rsync -r ... && rm -rf /mnt/work/output/manifests/llm_requests.jsonl` |                  |
| Startup script failed                      | Package install error / network                                                      | Check `cat /var/log/lex-startup.log`; re-run startup or recreate VM                                          |                  |
| SSH timeout                                | VM has no external IP                                                                | Verify: `gcloud compute instances describe lex-worker-N --zone=europe-west1-b`                               |                  |
| Finalize sees only one pass / missing docs | Current and historical shard outputs were merged by overwrite instead of aggregation | Re-sync into `_imports/`, rebuild aggregated `doc_metadata.json` / `llm_gate.json`, then re-run finalize     |                  |

---

## 8. Collecting Results & Finalize Pass

### 8.1 Sync results from GCS after all shards complete

```bash
FINALIZE_DIR="$HOME/data/lex_prod_140k"
mkdir -p "$FINALIZE_DIR/_imports/current" "$FINALIZE_DIR/_imports/historical"

for STATUS_PASS in current historical; do
  for i in $(seq 0 5); do
    gcloud storage rsync -r \
      "gs://polisyos-lex-data/output/${STATUS_PASS}/shard_${i}/" \
      "$FINALIZE_DIR/_imports/${STATUS_PASS}/shard_${i}/" &
  done
  wait
done
echo "All shard imports synced."
```

Expected structure after sync:

- `_imports/current/shard_0/` .. `_imports/current/shard_5/`
- `_imports/historical/shard_0/` .. `_imports/historical/shard_5/`
- Each imported shard root contains:
  - document-level dirs such as `provisions/`, `spo_results/`, `spo_grounded/`, `references/`, `resolved_references/`, `domains/`
  - shard-local state under `_shards/shard_XX_of_06/`
  - shard-local manifests such as `manifests/doc_metadata.json`, `manifests/llm_gate.json`, `manifests/telemetry.json`, `manifests/run_config.json`

### 8.2 Build the merged finalize input locally

Do **not** `rsync` all shard roots directly into one directory. First merge only the document-level dirs and explicitly aggregate the per-shard manifests that the finalize path depends on.

```bash
export FINALIZE_DIR="$HOME/data/lex_prod_140k"

python3 - <<'PY'
import json
import os
import shutil
from collections import Counter
from pathlib import Path

finalize_dir = Path(os.environ["FINALIZE_DIR"]).expanduser()
imports_dir = finalize_dir / "_imports"
manifests_dir = finalize_dir / "manifests"
manifests_dir.mkdir(parents=True, exist_ok=True)

doc_level_dirs = (
    "provisions",
    "spo_results",
    "spo_grounded",
    "references",
    "resolved_references",
    "domains",
)
for rel in doc_level_dirs:
    (finalize_dir / rel).mkdir(parents=True, exist_ok=True)
(finalize_dir / "_shard_runs").mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for item in src.rglob("*"):
        if item.is_dir():
            continue
        target = dst / item.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((num * 100.0) / den, 3)


agg_counts = Counter()
deferred_reason_counts = Counter()
gap_fill_trigger_counts = Counter()
top_gap_fill_subtypes = Counter()
top_gap_fill_families = Counter()
top_timeout_gap_fill_families = Counter()
all_docs: dict[str, dict] = {}
run_configs: list[dict] = []
shard_telemetry: list[dict] = []

llm_gate_audit_out = finalize_dir / "llm_gate_audit.jsonl"
if llm_gate_audit_out.exists():
    llm_gate_audit_out.unlink()

count_fields = [
    "provisions_seen",
    "skipped_total",
    "auto_by_code_total",
    "auto_empty_skipped_total",
    "llm_candidate_total",
    "llm_sent_total",
    "llm_primary_sent_total",
    "llm_gap_fill_sent_total",
    "llm_gap_fill_added_statements_total",
    "baseline_vs_gap_fill_added_statements_total",
    "llm_gap_fill_timeout_fallback_total",
    "llm_gap_fill_empty_responses_total",
    "gap_fill_null_yield_total",
    "gap_fill_null_yield_persisted_empty_total",
    "gap_fill_null_yield_preserved_baseline_total",
    "deferred_total",
    "dedup_reused_total",
    "audit_sample_total",
    "audit_miss_total",
    "circuit_breaker_hits",
    "timeout_retry_groups_total",
    "timeout_retry_success_total",
    "timeout_retry_failure_total",
    "retry_followup_passes_run",
    "retry_followup_pending_items_total",
    "retry_followup_recovered_items_total",
    "retry_followup_items_exhausted_total",
]

for status_dir in sorted(path for path in imports_dir.iterdir() if path.is_dir()):
    for shard_dir in sorted(path for path in status_dir.iterdir() if path.is_dir()):
        for rel in doc_level_dirs:
            copy_tree(shard_dir / rel, finalize_dir / rel)
        for shard_state in sorted((shard_dir / "_shards").glob("shard_*")):
            copy_tree(shard_state, finalize_dir / "_shard_runs" / status_dir.name / shard_state.name)

        run_cfg = load_json(shard_dir / "manifests" / "run_config.json")
        if run_cfg:
            run_cfg["status_pass"] = status_dir.name
            run_configs.append(run_cfg)

        stage_tel = load_json(shard_dir / "manifests" / "telemetry.json")
        if stage_tel:
            shard_telemetry.append(
                {
                    "status_pass": status_dir.name,
                    "shard": shard_dir.name,
                    **stage_tel,
                }
            )

        doc_meta = load_json(shard_dir / "manifests" / "doc_metadata.json")
        doc_rows = doc_meta.get("documents", {}) if isinstance(doc_meta.get("documents"), dict) else {}
        for doc_id, meta in doc_rows.items():
            if isinstance(meta, dict):
                all_docs[str(doc_id)] = meta

        gate = load_json(shard_dir / "manifests" / "llm_gate.json")
        metrics = gate.get("metrics", {}) if isinstance(gate.get("metrics"), dict) else {}
        for field in count_fields:
            agg_counts[field] += int(metrics.get(field) or 0)
        for key, value in (metrics.get("deferred_reason_counts") or {}).items():
            deferred_reason_counts[str(key)] += int(value or 0)
        for key, value in (metrics.get("gap_fill_trigger_counts") or {}).items():
            gap_fill_trigger_counts[str(key)] += int(value or 0)
        for item in metrics.get("top_gap_fill_subtypes") or []:
            top_gap_fill_subtypes[str(item.get("legal_unit_subtype") or "unknown")] += int(item.get("count") or 0)
        for item in metrics.get("top_gap_fill_families") or []:
            top_gap_fill_families[str(item.get("family") or "unknown")] += int(item.get("count") or 0)
        for item in metrics.get("top_timeout_gap_fill_families") or []:
            top_timeout_gap_fill_families[str(item.get("family") or "unknown")] += int(item.get("count") or 0)

        audit_path = shard_dir / "llm_gate_audit.jsonl"
        if audit_path.exists():
            with open(llm_gate_audit_out, "a", encoding="utf-8") as out_fh, open(audit_path, "r", encoding="utf-8") as in_fh:
                for line in in_fh:
                    if line.strip():
                        out_fh.write(line.rstrip("\n") + "\n")

merged_metrics = {field: int(agg_counts[field]) for field in count_fields}
merged_metrics["deferred_reason_counts"] = dict(sorted(deferred_reason_counts.items()))
merged_metrics["gap_fill_trigger_counts"] = dict(sorted(gap_fill_trigger_counts.items()))
merged_metrics["top_gap_fill_subtypes"] = [
    {"legal_unit_subtype": key, "count": value}
    for key, value in top_gap_fill_subtypes.most_common(8)
]
merged_metrics["top_gap_fill_families"] = [
    {"family": key, "count": value}
    for key, value in top_gap_fill_families.most_common(5)
]
merged_metrics["top_timeout_gap_fill_families"] = [
    {"family": key, "count": value}
    for key, value in top_timeout_gap_fill_families.most_common(5)
]
merged_metrics["llm_saved_pct"] = pct(
    agg_counts["llm_candidate_total"] - agg_counts["llm_sent_total"],
    agg_counts["llm_candidate_total"],
)
merged_metrics["primary_llm_saved_pct"] = pct(
    agg_counts["llm_candidate_total"] - agg_counts["llm_primary_sent_total"],
    agg_counts["llm_candidate_total"],
)
merged_metrics["audit_miss_rate_pct"] = pct(
    agg_counts["audit_miss_total"],
    agg_counts["audit_sample_total"],
)
merged_metrics["audit_miss_rate_pct_before_gap_fill_baseline"] = merged_metrics["audit_miss_rate_pct"]
merged_metrics["audit_miss_rate_pct_after_gap_fill"] = merged_metrics["audit_miss_rate_pct"]
merged_metrics["llm_gap_fill_gain_rate_pct"] = pct(
    agg_counts["llm_gap_fill_added_statements_total"],
    agg_counts["llm_gap_fill_sent_total"],
)
merged_metrics["gap_fill_null_yield_pct"] = pct(
    agg_counts["gap_fill_null_yield_total"],
    agg_counts["llm_gap_fill_sent_total"],
)

with open(manifests_dir / "doc_metadata.json", "w", encoding="utf-8") as fh:
    json.dump(
        {
            "kind": "lex_doc_metadata",
            "documents_total": len(all_docs),
            "documents": all_docs,
        },
        fh,
        ensure_ascii=False,
        indent=2,
    )

with open(manifests_dir / "llm_gate.json", "w", encoding="utf-8") as fh:
    json.dump(
        {
            "kind": "stage",
            "stage": "llm_gate",
            "mode": "merged_finalize_input",
            "gate_enabled": True,
            "llm_gap_fill_mode": "mixed_passes",
            "llm_gap_fill_enabled": True,
            "metrics": merged_metrics,
        },
        fh,
        ensure_ascii=False,
        indent=2,
    )

with open(manifests_dir / "shard_run_configs.json", "w", encoding="utf-8") as fh:
    json.dump(run_configs, fh, ensure_ascii=False, indent=2)

with open(manifests_dir / "shard_telemetry.json", "w", encoding="utf-8") as fh:
    json.dump(shard_telemetry, fh, ensure_ascii=False, indent=2)

print(f"Merged documents: {len(all_docs)}")
print(f"Aggregated llm_gate metrics from {len(run_configs)} shard runs")
PY
```

After this step the finalize root should contain:

- merged doc-level dirs: `provisions/`, `spo_results/`, `spo_grounded/`, `references/`, `resolved_references/`, `domains/`
- preserved shard-local progress under `_shard_runs/current/shard_00_of_06` .. `_shard_runs/historical/shard_05_of_06`
- aggregated manifests:
  - `manifests/doc_metadata.json`
  - `manifests/llm_gate.json`
  - `llm_gate_audit.jsonl`
  - `manifests/shard_run_configs.json`
  - `manifests/shard_telemetry.json`

### 8.3 Finalize pass (single-process, local or one VM)

```bash
cd ~/polisyos/policy-engine && source .venv/bin/activate

python3 -m polisyos.data_forge.domains.legal.batch run \
  --cards "$CARDS_XML" \
  --texts "$TEXTS_XML" \
  --output-dir "$FINALIZE_DIR" \
  --resume \
  --stages graph,benchmark,qc,export_claims,publish_bundle \
  --no-publish-require-embeddings \
  --embedding-device cpu
```

---

## 9. Temporal Requirement

Production policy for this `140k` run:

- Deterministic temporal extraction must be preserved for all statuses
- Temporal metadata must remain available in the output graph for current and historical acts
- At minimum preserve and publish:
  - `temporal_text_uk`
  - `effective_from`
  - `effective_to`

---

## 10. Post-Run Validation Checklist

After finalize pass completes:

- [ ] `lex_knowledge_graph.duckdb` exists and is queryable
- [ ] `manifests/doc_metadata.json` exists and `documents_total` is in the expected range
- [ ] `manifests/shard_run_configs.json` contains both `current` and `historical` shard imports
- [ ] QC gates passed (check `qc` stage output)
- [ ] No critical hallucination rate breach (`quality_max_hallucination_rate_pct < 3.0`)
- [ ] Reference resolution coverage ≥ 80%
- [ ] Temporal fields present:
      `SELECT COUNT(*) FROM lex_doc_temporal WHERE effective_from IS NOT NULL OR effective_to IS NOT NULL;`
- [ ] Status coverage looks sane:
      `SELECT doc_status, COUNT(*) FROM lex_doc_versions GROUP BY 1 ORDER BY 2 DESC;`
- [ ] Graph node/edge counts are in expected range
- [ ] `publish_bundle` stage created the bundle manifest
- [ ] All 6 shards contributed documents (no shard stuck at 0)

---

## 11. Cleanup

```bash
# Delete all VMs
./gcp/delete_workers.sh

# Keep GCS output bucket (it's cheap: ~$1/month for 50 GB)
# Or delete if backed up locally:
# gcloud storage rm -r gs://polisyos-lex-data/

# Delete secrets (optional — free tier)
for acc in $(seq 1 6); do
  for key in $(seq 1 5); do
    gcloud secrets delete "gonka-acc${acc}-key${key}" --quiet
  done
done
```

---

## 12. Calibration Log

> Fill in after each phase. This section is the running record of actual measurements.

### Phase 1 — Parallel hypothesis sweep

| Metric               | VM-0 baseline_a | VM-1 baseline_b | VM-2 higher_rps | VM-3 higher_concurrency | VM-4 code_verify | VM-5 aggressive_capped |
| -------------------- | --------------- | --------------- | --------------- | ----------------------- | ---------------- | ---------------------- |
| Date                 |                 |                 |                 |                         |                  |                        |
| Docs processed       |                 |                 |                 |                         |                  |                        |
| Wall time            |                 |                 |                 |                         |                  |                        |
| Docs/hour            |                 |                 |                 |                         |                  |                        |
| Total LLM requests   |                 |                 |                 |                         |                  |                        |
| HTTP 200 %           |                 |                 |                 |                         |                  |                        |
| HTTP 429 %           |                 |                 |                 |                         |                  |                        |
| `capacity_reached` % |                 |                 |                 |                         |                  |                        |
| p50 latency (ms)     |                 |                 |                 |                         |                  |                        |
| p90 latency (ms)     |                 |                 |                 |                         |                  |                        |
| Effective RPS        |                 |                 |                 |                         |                  |                        |
| Verify mode          | `llm`           | `llm`           | `llm`           | `llm`                   | `code`           | `code`                 |
| Global cap           | `64`            | `80`            | `100`           | `80`                    | `64`             | `80`                   |
| **Winner?**          |                 |                 |                 |                         |                  |                        |

**Phase 1 decision:** `______________`

### Phase 2 — Validate winner + explore edges

| Metric               | VM-0 winner_a | VM-1 winner_b | VM-2 rps_plus20 | VM-3 concur_plus40 | VM-4 control | VM-5 low_global_cap |
| -------------------- | ------------- | ------------- | --------------- | ------------------ | ------------ | ------------------- |
| Date                 |               |               |                 |                    |              |                     |
| Docs processed       |               |               |                 |                    |              |                     |
| HTTP 200 %           |               |               |                 |                    |              |                     |
| HTTP 429 %           |               |               |                 |                    |              |                     |
| `capacity_reached` % |               |               |                 |                    |              |                     |
| Effective RPS        |               |               |                 |                    |              |                     |
| Docs/hour            |               |               |                 |                    |              |                     |
| Winner 3-VM variance |               |               |                 | n/a                | n/a          | n/a                 |

**Phase 2 decision:** `______________`

**Locked production config:**

| Parameter             | Value |
| --------------------- | ----- |
| `rps`                 |       |
| `parallel-llm`        |       |
| `parallel-llm-global` |       |
| `spo-verify-mode`     |       |
| `batch-chars`         |       |
| `adaptive-penalty`    |       |
| `adaptive-recovery`   |       |

### Phase 3 — Production

| Metric                         | Value |
| ------------------------------ | ----- |
| Start date                     |       |
| End date (pass 1 — current)    |       |
| End date (pass 2 — historical) |       |
| Total docs processed           |       |
| Total LLM requests             |       |
| Total GCP spend                |       |

---

## Notes

- The exact XML status string is `Не набрав чинності`, not `Не набув чинності`.
- Rare statuses are routed conservatively to `Primary only`.
- API keys are stored in GCP Secret Manager, never in git or VM metadata.
- Spot VMs may be preempted — `--resume` + GCS sync ensures no work is lost.
- Each VM auto-shuts-down after completion to stop billing.
- GCS output is the source of truth — VM local disk is ephemeral.
- If a Spot VM is preempted mid-run, just restart it: startup script restores output from GCS and resumes.
- Keep `current` and `historical` outputs in separate remote prefixes until the explicit local merge step.
- The safe finalize path depends on aggregated `doc_metadata.json`, `llm_gate.json`, and `llm_gate_audit.jsonl`; raw overwrite-based shard sync is not sufficient.
- Phase 1 and Phase 2 calibration docs are not wasted — they are real production artifacts counted toward the 140K total.
- This runbook replaces the Hetzner-based version (March 30). Previous Hetzner smoke results are kept as reference in Section 3.

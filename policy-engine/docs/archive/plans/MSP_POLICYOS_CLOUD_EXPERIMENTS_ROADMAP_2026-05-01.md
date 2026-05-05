# PolicyOS MSME Cloud Experiments Roadmap for 2026-05-01 Deadline

Дата составления: 2026-04-30
Крайний срок результата: 2026-05-01 08:00 Europe/Kyiv
Основная цель: провести экспериментальную апробацию PolicyOS для раздела 3.8
квалификационной работы и додатка Б, используя уже обработанный корпус НПА,
локальные production-данные и воспроизводимый облачный контур.

## 1. Executive Summary

Рекомендуемый путь на дедлайн:

1. Не перезапускать Lex extraction и не ждать full amendment enrichment.
2. Использовать уже опубликованный fast-finalize Lex-бандл в GCS как юридический
   слой для экспериментов.
3. Синхронизировать `policy-engine/production_data` в тот же GCS-префикс, чтобы
   все данные были доступны внутри облака.
4. Арендовать одну основную CPU-машину `t2d-standard-16` или `c2d-standard-16`
   с 64 GB RAM и 350-500 GB `pd-balanced` диском.
5. Если после удаления старой finalize-VM освободится `pd-ssd` квота, допустимо
   взять 240 GB `pd-ssd`; иначе не упираться в SSD quota и брать `pd-balanced`.
6. Запускать эксперименты в deadline-mode: benchmark, publish и quality gates
   работают как warning/reporting gates, но не блокируют финальные артефакты.
7. Минимальный результат должен покрыть все H1-H6 из раздела 3.8, даже если часть
   экспериментов будет работать на агрегированных, синтетических или proxy-данных.

Что считать успехом к 08:00 2026-05-01:

- есть единый `experiment_index.json` со статусом H1-H6;
- есть отдельные папки `H1_formalization`, `H2_causal_stack`,
  `H3_transportability`, `H4_mechanism_welfare`, `H5_fairness_recourse`,
  `H6_adaptivity_audit`;
- для каждого эксперимента есть входной manifest, machine-readable result,
  human-readable summary и список ограничений;
- создан `thesis_results_summary.md`, который можно переносить в раздел 3.8;
- создан `appendix_b_artifact_table.md`, который можно переносить в додаток Б;
- все артефакты выгружены в GCS и, по возможности, скачаны локально.

## 2. Thesis Experiment Scope

Квалификационная работа задает шесть гипотез экспериментальной апробации.
Этот roadmap переводит их в cloud-executable план.

### H1. Формализация и auto-identification

Проверяется:

- три программы поддержки МСП формализуются в Trinity;
- Lex/NormPack дают юридические условия;
- Datasets/Fabric дают variable alignment и lineage;
- `id_engine` выводит estimands и `RequiredDataSpec`;
- неидентифицируемые cases возвращают `HedgeCertificate`, а не фиктивную оценку.

Минимально допустимый deadline-результат:

- 3 Trinity-like bundles: `VlasnaSprava`, `5-7-9`, `TaxRelief/SMERegime`;
- `IdentificationResult` или `HedgeCertificate` для каждой программы;
- таблица coverage: какие поля `RequiredDataSpec` покрыты реальными источниками,
  какие только proxy/synthetic;
- governance note о качестве Lex fast-finalize слоя.

### H2. Полный causal stack

Проверяется:

- discovery;
- identification;
- pre-treatment diagnostics;
- DiD / synthetic control / adjustment estimators;
- DML/HTE/QTE where available;
- mediation/interference/bounds/sensitivity;
- counterfactual attribution;
- conformal or uncertainty surface;
- governance verdict.

Минимально допустимый deadline-результат:

- один governed causal run для программы `Власна справа`;
- consensus graph или список candidate DAG/PAG;
- bounds + sensitivity даже если point estimate не допускается;
- явный статус: `identified`, `bounds_only`, `proxy_only`, `synthetic_demo`,
  `blocked_missing_microdata`.

### H3. Transportability UK -> wartime Ukraine

Проверяется:

- переносимость доказательств по близким британским программам поддержки МСП;
- S-graph / transport formula;
- invariance and support-factor checks;
- Bayesian pooling or context-distance downweighting;
- transport bounds;
- admissibility verdict.

Минимально допустимый deadline-результат:

- `SGraph` или структурированный replacement artifact;
- `NormalizedTransportFormula` or `transport_formula_summary`;
- support-factor checklist;
- verdict: `admissible`, `partially_admissible`, `not_admissible`,
  `missing_support_factors`.

### H4. Runtime mechanisms, welfare optimization, robustness

Проверяется:

- policy parameter simulation для `5-7-9`;
- welfare stack;
- Pareto frontier;
- distributional and spatial incidence;
- robust MCDA / DRO-lite;
- runtime patch report.

Минимально допустимый deadline-результат:

- таблица сценариев: ставки, лимиты, eligibility, budget cap;
- Pareto-frontier или frontier-like shortlist;
- welfare ranking under at least 2-3 social welfare functions;
- distributional profile;
- runtime patch report.

### H5. Fairness, recourse, conflict sensitivity

Проверяется:

- fairness decomposition;
- disparate impact bounds;
- conflict-sensitive region tags;
- recourse atlas;
- human-review escalation.

Минимально допустимый deadline-результат:

- synthetic or proxy applicant panel;
- fairness audit report;
- recourse packet template;
- conflict-sensitive risk table for frontline/deoccupied regions;
- governance note that real application-level microdata is absent.

### H6. Adaptivity and chained audit

Проверяется:

- hypothetical norm change;
- NormPack diff;
- intervention recompile;
- Foundry/Scientist re-run;
- governance verdict diff;
- replay plan.

Минимально допустимый deadline-результат:

- synthetic norm-change scenario;
- `NormPack ref -> intervention ref -> ProgramGraph ref -> execution ref ->
  governance verdict ref -> decision packet ref`;
- replay plan for independent audit;
- decision packet diff.

## 3. Current Data Inventory

### 3.1 Cloud Lex Artifacts

Current project:

```text
project_id = lex-1-494208
bucket     = gs://lex-1-494208-data
prefix     = gs://lex-1-494208-data/finalize/lex-finalize-20260429/finalize/
```

Verified key files:

| Artifact | Size | Role |
| --- | ---: | --- |
| `lex_knowledge_graph.duckdb` | 17.98 GiB | Main legal knowledge graph for experiments |
| `claim_exports/normative_claims.jsonl` | 1.93 GiB | Normative claims export, direct input for NormPack/Trinity seeding |
| `publish/consumer_readiness.json` | 93 KiB | Publish/readiness status |
| `qc_report.json` | 51 KiB | QC status |
| `benchmark_report.json` | 11 KiB | Benchmark status, warning-only for deadline |
| `manifests/fast_finalize_deferred_layers.json` | 772 B | Explicit record of deferred amendment enrichment |

Core graph counts from the fast finalize:

| Table / layer | Count |
| --- | ---: |
| `lex_facts` | 1,980,256 |
| `lex_provisions` | 6,074,716 |
| `lex_references` | 84,271 |
| `lex_reference_edges` | 73,793 |
| `lex_doc_temporal` | 134,849 |
| `lex_doc_versions` | 134,849 |
| `lex_doc_domains` | 222,604 |
| `lex_entities` after fast backfill | 357,742 |
| `lex_normative_facts` | 1,604,211 |
| `lex_high_confidence_norms` | 1,443,585 |
| `lex_amendments` | 0, deferred |

Important caveat:

- full amendment extraction / target-resolution / enrichment was deferred;
- benchmark failed amendment/reference/current-temporal readiness checks;
- this must be disclosed in the experiment report;
- it does not block deadline experiments because H1-H6 need usable legal
  conditions, traceability and NormPack-like source refs more urgently than a
  fully enriched amendment graph.

### 3.2 Local `production_data`

Local path:

```text
policy-engine/production_data
```

Current size:

```text
7.4 GiB total
```

Important files:

| Path | Size | Role |
| --- | ---: | --- |
| `dataset_catalog.duckdb` | 1.2 GiB | Main Datasets catalog |
| `all_records.jsonl` | 725 MiB | Merged dataset records |
| `ds_dataset_embeddings.npz` | 539 MiB | Dataset embeddings |
| `ds_dataset_index.hnsw` | 555 MiB | Search index |
| `policyos_academic_runtime_slim_20260411T112032Z/` | 3.2 GiB | Academic/SKG runtime artifacts |
| `ukraine_agent_simulation_baseline_20260410/` | 1.3 GiB | Simulation baseline and graph addons |
| `consumer_readiness.json` | small | Datasets readiness |
| `benchmark_report.json`, `qc_report.json` | small | Dataset QC/benchmark |

Known readiness caveat:

- Datasets `consumer_ready` is false because some source preflight/QC checks are
  strict.
- For this deadline, use the datasets in `warn_only` mode and explicitly record
  source limitations rather than blocking H1-H6.

### 3.3 Derived Cloud Experiment Prefix

Recommended experiment prefix:

```text
gs://lex-1-494208-data/experiments/msme_deadline_20260430/
```

Recommended subdirectories:

```text
input/
  lex/
  production_data/
  thesis_protocol/
runs/
  H1_formalization/
  H2_causal_stack/
  H3_transportability/
  H4_mechanism_welfare/
  H5_fairness_recourse/
  H6_adaptivity_audit/
reports/
  thesis_results_summary.md
  appendix_b_artifact_table.md
  fresg_after_scorecard.json
  limitations.md
manifests/
  experiment_index.json
  environment_fingerprint.json
  source_hashes.json
logs/
```

## 4. Cloud Resource Plan

### 4.1 Current Quota Situation

Observed quota and resource constraints in `europe-west2`:

- regional CPU quota is sufficient for one 16-vCPU worker and likely for up to
  32 vCPU total;
- `T2D_CPUS` limit is sufficient for `t2d-standard-16`;
- `C2D_CPUS` appears sufficient for `c2d-standard-16`;
- `SSD_TOTAL_GB` limit is 250 GB;
- a stopped VM `lex1-finalize-20260429` still owns a 240 GB `pd-ssd` disk;
- while that disk exists, only about 10 GB of SSD quota remains.

Recommended before launching the experiment VM:

1. Verify that all final Lex artifacts are in GCS.
2. If no local disk recovery is needed, delete `lex1-finalize-20260429` with its
   boot disk.
3. If we want maximum safety, keep the finalizer disk for a few hours but use
   `pd-balanced` for the experiment VM instead of `pd-ssd`.

### 4.2 Recommended Machine

Primary recommendation:

```text
machine_type = t2d-standard-16
vCPU         = 16
RAM          = 64 GB
disk         = 350-500 GB pd-balanced
zone         = europe-west2-b
preemptible  = no
```

Why:

- enough RAM for DuckDB over the 18 GB Lex DB plus dataset catalog;
- enough CPU for JAX/NumPy/DuckDB workflows;
- avoids GPU setup risk;
- avoids `pd-ssd` quota pressure if the old finalizer disk is kept;
- non-SPOT prevents losing the final deadline run to preemption.

Alternative if SSD quota is freed:

```text
machine_type = t2d-standard-16
disk         = 240 GB pd-ssd
```

Alternative if single-thread CPU speed becomes more important:

```text
machine_type = c2d-standard-16
disk         = 350-500 GB pd-balanced
```

Fallback if T2D/C2D creation fails:

```text
machine_type = e2-standard-16
disk         = 350-500 GB pd-balanced
```

### 4.3 Parallelization Strategy

Default: one 16-vCPU VM, controlled internal parallelism.

Do not run all six experiments as uncontrolled background jobs. The expensive
parts compete for RAM, disk cache and JAX compilation resources. Use staged
parallelism:

| Window | Jobs | CPU allocation |
| --- | --- | ---: |
| Setup/preflight | staging + checksum | 4-8 threads |
| H1 + H3 | Lex/DuckDB + transport checks | 8 + 6 threads |
| H2 | causal stack | 12-16 threads |
| H4 | simulation/welfare | 12-16 threads |
| H5 + H6 | fairness + audit chain | 8 + 6 threads |
| Reporting | aggregation | 4-8 threads |

If two machines are used:

- VM A: H1, H3, H6, report packaging;
- VM B: H2, H4, H5;
- both read from GCS and write separate run prefixes;
- final aggregation runs on VM A.

Given the deadline, the safer option is one larger non-SPOT VM unless we already
have a tested two-VM orchestration script.

### 4.4 Quota-Constrained Maximum Profile

Current hard project-level constraint:

```text
CPUS_ALL_REGIONS = 12
```

Even though `europe-west2` has regional `CPUS=32`, `C2D_CPUS=32` and
`N2_CPUS=32`, the global all-regions CPU quota means a 16-vCPU or 32-vCPU VM can
still be rejected. Until `CPUS_ALL_REGIONS` is raised, use the strongest
single-machine profile that fits exactly into the global quota:

```text
machine_type = n2-custom-12-98304
vCPU         = 12
RAM          = 96 GB
zone         = europe-west2-b
disk         = 240 GB pd-ssd, or 100 GB pd-balanced boot + 375 GB local SSD scratch
preemptible  = no
```

Why this is the best current fit:

- uses the full 12-vCPU global quota;
- gives the maximum allowed N2 custom memory for 12 vCPU: 96 GB;
- keeps the run on one machine, avoiding cross-VM orchestration overhead;
- has enough RAM for the 18 GiB Lex DuckDB, the 1.2 GiB Datasets DuckDB, indexes,
  Python/JAX runtime and report aggregation;
- stays in `europe-west2`, the same region as `gs://lex-1-494208-data`.

Disk recommendation under the 12-vCPU plan:

| Option | When to use | Notes |
| --- | --- | --- |
| `240GB pd-ssd` boot disk | safest simple fast path | Uses almost all `SSD_TOTAL_GB=250`, but quota is now free |
| `100GB pd-balanced` boot + `375GB local SSD` scratch | fastest scratch I/O | Local SSD is ephemeral; sync outputs to GCS after every experiment |
| `500GB pd-balanced` boot disk | capacity-first fallback | Slower than SSD, but simplest if local SSD mounting is inconvenient |

Recommended current command profile:

```bash
gcloud compute instances create "msme-exp-main-20260430" \
  --project="${PROJECT_ID}" \
  --zone="europe-west2-b" \
  --machine-type="n2-custom-12-98304" \
  --boot-disk-size="240GB" \
  --boot-disk-type="pd-ssd" \
  --image-family="ubuntu-2404-lts-amd64" \
  --image-project="ubuntu-os-cloud" \
  --scopes="storage-full,cloud-platform" \
  --metadata="run-id=${RUN_ID},role=msme-experiments,threads=12" \
  --tags="msme-exp"
```

Threading profile for this constrained machine:

```bash
export POLISYOS_EXPERIMENT_THREADS=12
export OMP_NUM_THREADS=12
export MKL_NUM_THREADS=12
export OPENBLAS_NUM_THREADS=12
export NUMEXPR_MAX_THREADS=12
export JAX_PLATFORMS=cpu
export JAX_PLATFORM_NAME=cpu
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=12"
```

Execution strategy changes under 12 vCPU:

- do not run H2 and H4 at the same time;
- run H1/H3 light extraction tasks while H2/H4 are not JAX-compiling;
- run H5/H6/report generation in parallel only after heavy numerical stages end;
- sync after every H-run because deadline output safety is more important than
  squeezing the last few percent of throughput.

## 5. Deadline Schedule

Assumption: start around the morning of 2026-04-30 Kyiv time, with final
artifact deadline at 2026-05-01 08:00.

| Kyiv time | Work |
| --- | --- |
| 08:30-09:15 Apr 30 | Cleanup old disk if approved, upload `production_data`, create VM |
| 09:15-10:00 Apr 30 | Environment setup, data download, hash/inventory preflight |
| 10:00-12:00 Apr 30 | H1 formalization and auto-identification |
| 12:00-15:30 Apr 30 | H2 causal stack MVP |
| 15:30-17:30 Apr 30 | H3 transportability |
| 17:30-21:30 Apr 30 | H4 mechanism/welfare/robustness |
| 21:30-23:30 Apr 30 | H5 fairness/recourse/conflict sensitivity |
| 23:30-01:30 May 1 | H6 adaptivity/chained audit |
| 01:30-03:30 May 1 | Aggregate reports, thesis summary, appendix artifact table |
| 03:30-06:00 May 1 | Buffer for reruns and missing outputs |
| 06:00-07:30 May 1 | Download final reports locally, final sanity checks |
| 07:30-08:00 May 1 | Freeze results and stop/delete VM if all data is in GCS |

Minimum viable schedule if time collapses:

| Priority | Must finish |
| --- | --- |
| P0 | H1, H2, H6, final summary |
| P1 | H3, H4 |
| P2 | H5 enriched version |

Rationale:

- H1 proves legal/data formalization;
- H2 proves causal engine behavior;
- H6 proves reproducibility/adaptivity;
- H3-H5 make the result richer, but can be framed as bounded/proxy experiments
  if needed.

## 6. Gate Policy for Deadline Mode

The experiments must not fail just because strict gates detect known quality
compromises. Instead:

| Gate | Deadline behavior |
| --- | --- |
| Lex benchmark | warning only |
| Datasets consumer readiness | warning only |
| Academic/SKG readiness | warning only |
| Missing microdata | convert to `blocked_missing_microdata` or `synthetic_demo` |
| Failed causal identification | return `HedgeCertificate`, not failure |
| Failed transportability | return `not_admissible` or `partial_admissibility`, not failure |
| Failed fairness support | return `insufficient_protected_attribute_data`, not failure |
| Missing amendment enrichment | record in limitations and continue |

Only hard blockers:

- GCS input corruption;
- no Lex DB and no normative claims export;
- no output manifest;
- Python environment cannot import core `polisyos`;
- result directory cannot be synced to GCS.

## 7. Setup and Staging Commands

These commands are intended as the next operational runbook. They are included
here so the experiment can be launched without reconstructing the plan.

### 7.1 Variables

```bash
export PROJECT_ID="lex-1-494208"
export ZONE="europe-west2-b"
export BUCKET="gs://lex-1-494208-data"
export RUN_ID="msme_deadline_20260430"
export RUN_PREFIX="${BUCKET}/experiments/${RUN_ID}"
export LEX_PREFIX="${BUCKET}/finalize/lex-finalize-20260429/finalize"
export LOCAL_REPO="/Users/deniskopylov/polisyos"
```

### 7.2 Verify Lex Inputs

```bash
gcloud storage ls --project="${PROJECT_ID}" -l \
  "${LEX_PREFIX}/lex_knowledge_graph.duckdb" \
  "${LEX_PREFIX}/claim_exports/normative_claims.jsonl" \
  "${LEX_PREFIX}/publish/consumer_readiness.json" \
  "${LEX_PREFIX}/qc_report.json" \
  "${LEX_PREFIX}/benchmark_report.json" \
  "${LEX_PREFIX}/manifests/fast_finalize_deferred_layers.json"
```

### 7.3 Upload Local Production Data

Run from repository root:

```bash
cd "${LOCAL_REPO}"
gcloud storage rsync -r \
  "policy-engine/production_data" \
  "${RUN_PREFIX}/input/production_data"
```

Optional: upload the thesis protocol source as trace evidence:

```bash
gcloud storage cp \
  "/Users/deniskopylov/Downloads/Кваліфікаційна_робота_мета_завдання_узгоджено.docx" \
  "${RUN_PREFIX}/input/thesis_protocol/"
```

### 7.4 Optional Cleanup of Old Finalizer Disk

Only after confirming the Lex artifacts are in GCS:

```bash
gcloud compute instances delete "lex1-finalize-20260429" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --delete-disks=all \
  --quiet
```

If we do not delete it, create the experiment VM with `pd-balanced`, not
`pd-ssd`.

### 7.5 Create the Main Experiment VM

Recommended non-SPOT VM:

```bash
gcloud compute instances create "msme-exp-main-20260430" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --machine-type="t2d-standard-16" \
  --boot-disk-size="500GB" \
  --boot-disk-type="pd-balanced" \
  --image-family="ubuntu-2404-lts-amd64" \
  --image-project="ubuntu-os-cloud" \
  --scopes="storage-full,cloud-platform" \
  --metadata="run-id=${RUN_ID},role=msme-experiments,threads=16" \
  --tags="msme-exp"
```

If SSD quota is free and we prefer `pd-ssd`:

```bash
gcloud compute instances create "msme-exp-main-20260430" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --machine-type="t2d-standard-16" \
  --boot-disk-size="240GB" \
  --boot-disk-type="pd-ssd" \
  --image-family="ubuntu-2404-lts-amd64" \
  --image-project="ubuntu-os-cloud" \
  --scopes="storage-full,cloud-platform" \
  --metadata="run-id=${RUN_ID},role=msme-experiments,threads=16" \
  --tags="msme-exp"
```

### 7.6 VM Environment Setup

```bash
gcloud compute ssh "msme-exp-main-20260430" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}"
```

Inside the VM:

```bash
set -euo pipefail

sudo apt-get update -qq
sudo apt-get install -y -qq \
  git curl jq unzip build-essential pkg-config \
  python3.14 python3.14-venv python3.14-dev \
  htop tmux

sudo mkdir -p /mnt/experiments
sudo chown -R "$USER:$USER" /mnt/experiments

cd /mnt/experiments
git clone https://github.com/DenisKopylov/polisyos.git || true
cd /mnt/experiments/polisyos/policy-engine

python3.14 -m venv /mnt/experiments/venv
source /mnt/experiments/venv/bin/activate
python -m pip install -U pip wheel
python -m pip install -e ".[research,test,runtime,agent-sim]"
```

Threading environment:

```bash
export POLISYOS_EXPERIMENT_THREADS=16
export OMP_NUM_THREADS=16
export MKL_NUM_THREADS=16
export OPENBLAS_NUM_THREADS=16
export NUMEXPR_MAX_THREADS=16
export JAX_PLATFORMS=cpu
export JAX_PLATFORM_NAME=cpu
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=16"
```

Important Python 3.14 caveat:

- Some optional causal packages are gated in `pyproject.toml` for older Python
  versions (`dowhy`, some `econml` paths).
- Do not spend deadline time fighting those resolvers.
- If a method is unavailable, record `method_unavailable_python314` and fall
  back to native PolicyOS methods, bounds, sensitivity, synthetic benchmark or
  artifact-only report.

### 7.7 Download Inputs on VM

```bash
export PROJECT_ID="lex-1-494208"
export BUCKET="gs://lex-1-494208-data"
export RUN_ID="msme_deadline_20260430"
export RUN_PREFIX="${BUCKET}/experiments/${RUN_ID}"
export LEX_PREFIX="${BUCKET}/finalize/lex-finalize-20260429/finalize"
export WORKDIR="/mnt/experiments/${RUN_ID}"

mkdir -p "${WORKDIR}/input/lex" \
         "${WORKDIR}/input/production_data" \
         "${WORKDIR}/runs" \
         "${WORKDIR}/reports" \
         "${WORKDIR}/manifests" \
         "${WORKDIR}/logs" \
         "${WORKDIR}/cas"

gcloud storage cp "${LEX_PREFIX}/lex_knowledge_graph.duckdb" \
  "${WORKDIR}/input/lex/"
gcloud storage cp "${LEX_PREFIX}/claim_exports/normative_claims.jsonl" \
  "${WORKDIR}/input/lex/"
gcloud storage cp "${LEX_PREFIX}/publish/consumer_readiness.json" \
  "${WORKDIR}/input/lex/"
gcloud storage cp "${LEX_PREFIX}/qc_report.json" \
  "${WORKDIR}/input/lex/"
gcloud storage cp "${LEX_PREFIX}/benchmark_report.json" \
  "${WORKDIR}/input/lex/"
gcloud storage cp "${LEX_PREFIX}/manifests/fast_finalize_deferred_layers.json" \
  "${WORKDIR}/input/lex/"

gcloud storage rsync -r \
  "${RUN_PREFIX}/input/production_data" \
  "${WORKDIR}/input/production_data"
```

### 7.8 Input Preflight

```bash
cd /mnt/experiments/polisyos/policy-engine
source /mnt/experiments/venv/bin/activate

python - <<'PY'
from pathlib import Path
import duckdb, json, hashlib, os

work = Path(os.environ["WORKDIR"])
lex_db = work / "input/lex/lex_knowledge_graph.duckdb"
claims = work / "input/lex/normative_claims.jsonl"
prod = work / "input/production_data"

assert lex_db.exists(), lex_db
assert claims.exists(), claims
assert prod.exists(), prod

con = duckdb.connect(str(lex_db), read_only=True)
tables = [
    "lex_facts",
    "lex_provisions",
    "lex_doc_temporal",
    "lex_doc_domains",
    "lex_normative_facts",
]
counts = {}
for table in tables:
    counts[table] = con.execute(f"select count(*) from {table}").fetchone()[0]

payload = {
    "lex_db_bytes": lex_db.stat().st_size,
    "claims_bytes": claims.stat().st_size,
    "production_data_files": sum(1 for p in prod.rglob("*") if p.is_file()),
    "counts": counts,
}
out = work / "manifests/input_preflight.json"
out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
```

## 8. Experiment Design and Expected Outputs

### 8.1 H1 Formalization and Auto-Identification

Inputs:

- `lex_knowledge_graph.duckdb`;
- `normative_claims.jsonl`;
- `dataset_catalog.duckdb`;
- `all_records.jsonl`;
- Datasets embeddings/index if variable lookup is needed.

Program set:

1. `Власна справа`;
2. `Доступні кредити 5-7-9%`;
3. wartime SME tax/regulatory relief, including Tax Code references where found.

Lex query strategy:

- search by Ukrainian/Russian program names;
- search by known institutional entities: `Мінекономіки`, `Дія.Бізнес`,
  `Фонд розвитку підприємництва`, `Кабінет Міністрів`;
- search by policy terms: `мікрогрант`, `кредит`, `компенсація`, `ставка`,
  `малого та середнього підприємництва`, `ФОП`, `ветеран`, `воєнний стан`;
- export source provisions, facts, domains, references and temporal status.

Processing steps:

1. Extract candidate legal facts from Lex DB into
   `runs/H1_formalization/legal_source_pack.jsonl`.
2. Build program-specific `intervention_pack.json` for each program.
3. Build `TrinityBundle` or Trinity-like JSON for each program.
4. Run `id_engine` against the ProblemFrame.
5. Generate `RequiredDataSpec`.
6. Match `RequiredDataSpec` fields to Datasets variables.
7. Emit `IdentificationResult` or `HedgeCertificate`.

Expected output files:

```text
runs/H1_formalization/
  legal_source_pack.jsonl
  vlasna_sprava.trinity.json
  five_seven_nine.trinity.json
  tax_relief.trinity.json
  variable_manifest.json
  identification_results.json
  required_data_spec.json
  hedge_certificates.json
  h1_summary.md
```

Target runtime:

- 45-90 minutes for MVP;
- up to 2 hours if Lex SQL filtering is broadened.

Success criteria:

- at least 3 program bundles are generated;
- each bundle has a legal source trace;
- each bundle has an identification status;
- failure to identify is represented as a certificate, not a crash.

### 8.2 H2 Full Causal Stack

Inputs:

- H1 `TrinityBundle` for `Власна справа`;
- `production_data/ukraine_agent_simulation_baseline_20260410`;
- `production_data/dataset_catalog.duckdb`;
- synthetic or aggregate observation panel if real microdata is unavailable.

Method stack:

- discovery: PC/FCI/GES/DAGMA/PCMCI where available;
- identification: `id_engine`, `SymbolicIdentifyV2` where available;
- estimators: modern DiD, synthetic control, adjustment, DML-compatible native
  fallback, HTE/CATE-lite, QTE-lite;
- validity: bounds, sensitivity, specification curve;
- governance: method result status and limitations.

Deadline fallback:

- If real microdata is missing, run against a synthetic benchmark calibrated by
  production_data aggregates and mark `synthetic_demo`.
- If optional libraries are not importable on Python 3.14, record the unavailable
  method and use native fallback.
- If discovery disagrees, produce `candidate_graph_set` and `consensus_graph`
  with confidence notes, not a single overclaimed DAG.

Expected output files:

```text
runs/H2_causal_stack/
  causal_task.json
  discovery_candidates.json
  consensus_graph.json
  identification_result.json
  estimator_results.json
  bounds_summary.json
  sensitivity_report.json
  qte_profile.json
  cate_or_hte_summary.json
  specification_curve.json
  governance_verdict.json
  h2_summary.md
```

Target runtime:

- 2-4 hours MVP;
- 4-6 hours if multiple estimators and specification curve are expanded.

Success criteria:

- causal stack returns structured statuses for every requested block;
- principal result includes uncertainty or bounds;
- missing data is an explicit blocker/fallback, not hidden.

### 8.3 H3 Transportability UK -> Ukraine

Inputs:

- `production_data/policyos_academic_runtime_slim_20260411T112032Z`;
- `academic/transport_scores.jsonl`;
- `academic/graph/scholar_knowledge.duckdb`;
- Lex facts for Ukrainian wartime legal context;
- H1 variable manifest.

Processing steps:

1. Query Academic/SKG for Start Up Loans and similar SME grant/credit evidence.
2. Align UK variables to Ukrainian variables.
3. Build S-graph / context difference graph.
4. Run invariance/support-factor checks.
5. Produce transport formula or reason for non-transportability.
6. Produce bounds and admissibility verdict.

Expected output files:

```text
runs/H3_transportability/
  uk_evidence_pack.jsonl
  ua_context_pack.json
  variable_alignment_uk_ua.json
  s_graph.json
  transport_formula.json
  invariance_certificate.json
  support_factors_checklist.json
  transport_bounds.json
  admissibility_verdict.json
  h3_summary.md
```

Target runtime:

- 1-2 hours MVP;
- 2-3 hours with broader Academic/SKG query and sensitivity.

Success criteria:

- verdict is explicit;
- missing support factors are named;
- no direct transfer is claimed without support.

### 8.4 H4 Mechanism, Welfare and Robustness

Inputs:

- H1 `5-7-9` intervention pack;
- `ukraine_agent_simulation_baseline_20260410`;
- heavy graph addons:
  - `budget_graph_sparse.npz`;
  - `trade_graph_sparse.npz`;
  - `procurement_graph_sparse.npz`;
  - `distress_graph_sparse.npz`;
  - `public_service_graph_sparse.npz`;
- Lex eligibility/constraint facts.

Processing steps:

1. Define scenario grid:
   - interest rate subsidy levels;
   - loan caps;
   - eligibility thresholds;
   - budget caps;
   - conflict exposure weighting;
   - region/sector targeting.
2. Run simulation or mechanism demo.
3. Compute welfare under multiple social welfare functions.
4. Compute cost-effectiveness and budget impact.
5. Compute Pareto frontier.
6. Run DRO-lite / MCDA robustness over uncertain parameters.
7. Emit runtime patch report.

Expected output files:

```text
runs/H4_mechanism_welfare/
  scenario_grid.json
  simulation_results.jsonl
  welfare_table.json
  budget_impact.json
  distributional_profile.json
  spatial_incidence.json
  pareto_frontier.json
  robust_rank.json
  runtime_patch_report.json
  h4_summary.md
```

Target runtime:

- 3-5 hours for useful scenario grid;
- can be cut to 1-2 hours by reducing grid size and MC samples.

Success criteria:

- at least 10-30 scenarios evaluated;
- ranking is not based on one metric only;
- result includes robustness caveat.

### 8.5 H5 Fairness, Recourse and Conflict Sensitivity

Inputs:

- synthetic/proxy applicant panel;
- Lex eligibility facts;
- region conflict exposure tags;
- H4 scenario outputs.

Processing steps:

1. Construct applicant feature panel:
   - sex/gender proxy if available or synthetic;
   - region;
   - veteran status;
   - sector;
   - firm size;
   - conflict exposure;
   - application outcome.
2. Run fairness decomposition.
3. Compute disparate impact bounds.
4. Build recourse atlas for rejected applicants.
5. Build contestability packet template.
6. Mark cases requiring human review.

Expected output files:

```text
runs/H5_fairness_recourse/
  applicant_panel_manifest.json
  fairness_audit_report.json
  disparate_impact_bounds.json
  conflict_sensitivity_regions.json
  recourse_atlas.json
  contestability_packet_template.md
  human_review_escalation.json
  h5_summary.md
```

Target runtime:

- 1-2 hours MVP;
- 2-3 hours with richer synthetic data and extra fairness slices.

Success criteria:

- protected-attribute limitations are disclosed;
- recourse suggestions reference legal eligibility facts;
- human review is not optional for risky cases.

### 8.6 H6 Adaptivity and Chained Audit

Inputs:

- H1 `Власна справа` NormPack-like pack;
- hypothetical legal amendment scenario:
  - expanded veteran-FOP support;
  - modified caps;
  - additional conflict exposure eligibility;
- H2/H4 reusable outputs.

Processing steps:

1. Create synthetic norm diff.
2. Rebuild intervention pack.
3. Recompile ProgramGraph/ExecPlan.
4. Re-run compact causal validity and transportability checks.
5. Build decision packet diff.
6. Build replay plan.
7. Write chained artifact manifest.

Expected output files:

```text
runs/H6_adaptivity_audit/
  norm_diff.json
  old_intervention_pack.json
  new_intervention_pack.json
  program_graph_diff.json
  execution_ref.json
  governance_verdict_diff.json
  decision_packet_diff.md
  replay_plan.json
  audit_chain_manifest.json
  h6_summary.md
```

Target runtime:

- 1-2 hours MVP.

Success criteria:

- the old and new policy states are both traceable;
- replay plan identifies exact inputs and hashes;
- governance verdict changes are explicit.

## 9. Experiment Harness Recommendation

For speed, create one thin deadline harness rather than wiring a full production
workflow. Recommended file for the next implementation step:

```text
policy-engine/tools/ops/experiments/run_msme_deadline_suite.py
```

Recommended CLI:

```bash
uv run python tools/ops/experiments/run_msme_deadline_suite.py \
  --workdir "${WORKDIR}" \
  --lex-db "${WORKDIR}/input/lex/lex_knowledge_graph.duckdb" \
  --claims-jsonl "${WORKDIR}/input/lex/normative_claims.jsonl" \
  --production-data "${WORKDIR}/input/production_data" \
  --cas-root "${WORKDIR}/cas" \
  --output-dir "${WORKDIR}/runs" \
  --reports-dir "${WORKDIR}/reports" \
  --threads 16 \
  --deadline-mode \
  --warn-only-gates \
  --experiments H1,H2,H3,H4,H5,H6
```

Harness responsibilities:

- never mutate input data;
- write one subdirectory per experiment;
- catch expected method/data failures and convert them into structured statuses;
- produce per-experiment `summary.md`;
- produce `experiment_index.json`;
- produce `thesis_results_summary.md`;
- produce `appendix_b_artifact_table.md`;
- sync outputs to GCS at the end and after each experiment.

Minimal result schema:

```json
{
  "experiment_id": "H2_causal_stack",
  "status": "completed_with_limitations",
  "started_at": "...",
  "finished_at": "...",
  "inputs": [],
  "outputs": [],
  "method_statuses": [],
  "limitations": [],
  "thesis_claims_supported": [],
  "hard_failures": []
}
```

## 10. Monitoring

### 10.1 VM Status

```bash
gcloud compute instances list \
  --project="${PROJECT_ID}" \
  --filter="tags.items=msme-exp" \
  --format="table(name,zone.basename(),machineType.basename(),status,networkInterfaces[0].accessConfigs[0].natIP)"
```

### 10.2 SSH Tail

```bash
gcloud compute ssh "msme-exp-main-20260430" \
  --project="${PROJECT_ID}" \
  --zone="${ZONE}" \
  --command="tail -f /mnt/experiments/${RUN_ID}/logs/experiment_suite.log"
```

### 10.3 CPU and Memory

Inside VM:

```bash
htop
df -h
free -h
du -sh /mnt/experiments/${RUN_ID}/*
```

Expected CPU behavior:

- DuckDB scans: high CPU bursts plus high disk read;
- JAX compile: temporary high CPU then lower steady-state;
- GCS sync: lower CPU and network-bound;
- report generation: low CPU.

### 10.4 Continuous Sync

After each experiment:

```bash
gcloud storage rsync -r \
  "${WORKDIR}/runs" \
  "${RUN_PREFIX}/runs"

gcloud storage rsync -r \
  "${WORKDIR}/reports" \
  "${RUN_PREFIX}/reports"

gcloud storage rsync -r \
  "${WORKDIR}/manifests" \
  "${RUN_PREFIX}/manifests"
```

## 11. Final Packaging

Required final files:

```text
reports/thesis_results_summary.md
reports/appendix_b_artifact_table.md
reports/fresg_after_scorecard.json
reports/limitations.md
manifests/experiment_index.json
manifests/environment_fingerprint.json
manifests/source_hashes.json
```

Recommended `thesis_results_summary.md` structure:

```text
# Experimental Approbation Results

## Data and Runtime
## H1 Formalization and Auto-Identification
## H2 Causal Stack
## H3 Transportability
## H4 Mechanism and Welfare
## H5 Fairness and Recourse
## H6 Adaptivity and Chained Audit
## FRESG Reassessment
## Limitations
## What This Proves and What It Does Not Prove
```

Recommended `appendix_b_artifact_table.md` columns:

| Experiment | Protocol artifact | Actual artifact | Status | GCS path | Limitation |
| --- | --- | --- | --- | --- | --- |

Recommended final sync:

```bash
gcloud storage rsync -r \
  "${WORKDIR}" \
  "${RUN_PREFIX}/workspace_final"
```

Recommended local download:

```bash
mkdir -p "/Users/deniskopylov/Downloads/${RUN_ID}_results"
gcloud storage rsync -r \
  "${RUN_PREFIX}/reports" \
  "/Users/deniskopylov/Downloads/${RUN_ID}_results/reports"
gcloud storage rsync -r \
  "${RUN_PREFIX}/manifests" \
  "/Users/deniskopylov/Downloads/${RUN_ID}_results/manifests"
```

## 12. Interpretation Rules for Thesis

Use cautious claims:

- "The experiment validates the executable protocol and artifact discipline."
- "The system returns bounded, qualified or negative certificates when evidence
  is insufficient."
- "The result is an architectural and methodological validation, not a final
  causal estimate of real-world effectiveness."
- "Because application-level microdata is absent, some runs use synthetic or
  aggregate proxy data."
- "Because amendment enrichment was deferred, amendment-level legal dynamics are
  not part of the deadline result."

Avoid overclaims:

- do not claim the real effect of `Власна справа` unless real microdata is used;
- do not claim UK evidence transfers directly to Ukraine without support-factor
  caveats;
- do not claim fairness compliance without real applicant-level protected
  attributes;
- do not claim full legal temporal safety while amendment enrichment is deferred.

Good phrasing:

```text
The experiments show that PolicyOS can formalize policy problems, bind legal and
data evidence, execute causal and simulation methods under governance, and return
auditable artifacts. Where data or identification assumptions are insufficient,
the system produces explicit limitations, certificates or fallback statuses rather
than unsupported point estimates.
```

## 13. Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Old finalizer disk consumes SSD quota | Cannot create new pd-ssd VM | Use pd-balanced or delete old VM after GCS verification |
| Optional causal packages unavailable on Python 3.14 | Some methods unavailable | Record method status and use native fallback/bounds |
| No real microdata for applications | H2/H5 cannot be real effect estimates | Use synthetic/aggregate/proxy data and state limitation |
| Amendment enrichment deferred | Legal change dynamics incomplete | Use core legal facts and disclose deferred layer |
| GCS staging slow | Late start | Stage production_data first; copy only needed Lex files locally |
| JAX oversubscription | Lower throughput | Set thread env and avoid running H2/H4 concurrently |
| Strict gates fail | Blocks artifacts | Warn-only gates in deadline mode |
| Discovery returns conflicting graphs | Ambiguous causal structure | Emit candidate graph set and consensus caveat |
| Transportability weak | No direct transferred effect | Return partial/not admissible verdict with missing support factors |
| VM cost continues after run | Billing risk | Auto-shutdown or manual delete after GCS sync |

## 14. Recommended Next Actions

Order of operations:

1. Confirm whether to delete `lex1-finalize-20260429` and its 240 GB disk.
2. Upload `policy-engine/production_data` to
   `gs://lex-1-494208-data/experiments/msme_deadline_20260430/input/production_data`.
3. Create `msme-exp-main-20260430` as non-SPOT `t2d-standard-16`.
4. Download only the required Lex files and production data onto the VM.
5. Run input preflight and write `input_preflight.json`.
6. Implement or run the thin deadline harness.
7. Execute H1-H6 in the schedule above.
8. Sync after every H-run.
9. Generate thesis-ready summaries.
10. Download final reports locally.
11. Stop/delete VM only after GCS and local report download are verified.

## 15. One-Page Run Decision

Recommended concrete decision:

```text
Use one non-SPOT t2d-standard-16 VM in europe-west2-b.
Use 500 GB pd-balanced unless the old finalizer disk is deleted.
Run all experiments in deadline-mode with warn-only gates.
Do not rerun Lex.
Do not attempt full amendment enrichment.
Use Lex fast-finalize + production_data as the evidence base.
Produce thesis-ready H1-H6 artifacts and limitations by 2026-05-01 08:00 Kyiv.
```

This is the best tradeoff between speed, reproducibility and intellectual
honesty for the current deadline.

## 16. Phase 2: End-to-End PolicyOS Showcase Experiments

### 16.1 Why This Phase Is Needed

The completed H1-H6 deadline suite is useful for the thesis because it produced
machine-readable artifacts over the real Lex bundle and `production_data`.
However, H1-H6 deliberately used a thin deadline harness for speed. It should
not be described as a full end-to-end PolicyOS run with all system layers
activated.

Phase 2 adds that missing end-to-end layer:

- a natural-language policy intent is converted into a structured design task;
- legal and dataset evidence is retrieved from the processed corpus;
- candidate wartime SME policy designs are generated and compared;
- Runtime-style `QuantityValue` rows are projected through Fabric trust
  envelopes and product evidence paths;
- Foundry performs real CAS-backed compile/execute smoke runs;
- a CPU-heavy optimization arena evaluates policy portfolios under uncertainty;
- an optional LLM governance review critiques the top policies when Gonka/OpenAI
  compatible credentials are available.

The purpose is not to replace H1-H6. The purpose is to add a thesis-friendly
showcase proving that the layers can be composed in one auditable workflow.

### 16.2 Experiment Set

#### S1. Policy Intent and Agentic Design Loop

Question:

```text
What wartime Ukrainian SME support policy should be recommended for 2026 if the
goal is to maximize business survival, employment preservation, regional
resilience and fiscal responsibility under incomplete microdata?
```

Inputs:

- Lex legal source pack from H1;
- normative claims export and Lex DuckDB samples;
- dataset catalog summaries from `production_data`;
- H1-H6 outputs as prior evidence;
- optional LLM key from VM environment or cloud secret-staged env files.

Outputs:

- `policy_intent.json`;
- `retrieval_evidence.jsonl`;
- `agent_plan.json`;
- `agent_transcript.jsonl`;
- `candidate_policy_designs.json`;
- `s1_policy_design_summary.md`.

Deadline interpretation:

- if LLM credentials are available, use a small multi-role LLM loop
  (`planner`, `data_scout`, `governance_reviewer`);
- if credentials are absent or rate-limited, run the deterministic agent
  fallback and mark the result as `llm_unavailable_or_fallback`;
- never present deterministic fallback text as an LLM result.

#### S2. Fabric Runtime Trust Flow

Question:

```text
Can decision-bearing metrics from the MSME experiments be moved through the
Runtime/Fabric trust contract instead of remaining as naked numbers?
```

Inputs:

- top H4 scenario metrics;
- H1 coverage and legal-source metrics;
- H2/H5 limitation metrics;
- `QuantityValue`, `LineageRef`, `TemporalScope` runtime contracts;
- Fabric `from_runtime_quantities`, `coverage_from_decision_data` and product
  evidence-path adapters.

Outputs:

- `runtime_quantities.json`;
- `fabric_decision_data.json`;
- `fabric_coverage.json`;
- `fabric_evidence_paths.json`;
- `fabric_to_foundry_context.json`;
- `s2_fabric_trust_flow_summary.md`.

Success criterion:

- all decision-bearing metrics are wrapped in Fabric trust envelopes;
- coverage explicitly distinguishes traced, pending and untraced values;
- uncertainty inflation and calibration weights are derived from Fabric trust
  posture and can be consumed by downstream Foundry/Scientist stages.

#### S3. Foundry Compile/Execute Smoke Path

Question:

```text
Can the current repository compile and execute a policy bundle through Foundry's
real CAS-backed compile/execute path inside the same cloud environment?
```

Inputs:

- `polisyos.foundry.quickstart.run_trivial_compile_execute`;
- `run_feedback_compile_execute`;
- `run_feedback_multiplicity_demo`;
- a dedicated CAS directory under the experiment output path.

Outputs:

- `foundry_quickstart_results.json`;
- `foundry_cas_manifest.json`;
- `foundry_artifact_refs.json`;
- `s3_foundry_compile_execute_summary.md`.

Success criterion:

- compile and execute return `ok=true` for at least the trivial path;
- feedback and multiplicity runs either succeed or fail with typed diagnostics;
- artifact IDs are recorded and the CAS directory is synced to GCS.

#### S4. Policy Optimization Arena

Question:

```text
Which mix of grants, subsidized credit, tax relief and conflict-sensitive
targeting performs best under fiscal, fairness and robustness constraints?
```

Inputs:

- H1-H6 outputs;
- Lex-derived policy constraints;
- production-data priors where available;
- synthetic/proxy applicant and firm panels generated from disclosed assumptions.

CPU plan:

- use all available vCPUs on the current `n2-custom-12-98304`;
- set BLAS/JAX/NumExpr thread variables to 12;
- use multiprocessing for candidate batches;
- sync intermediate results after each major chunk.

Outputs:

- `optimization_input_manifest.json`;
- `candidate_grid.jsonl`;
- `optimization_results.jsonl`;
- `pareto_frontier.json`;
- `robustness_sensitivity.json`;
- `top_policy_recommendations.json`;
- `s4_policy_optimization_summary.md`.

Success criterion:

- at least thousands of candidate policy portfolios are evaluated;
- final recommendation includes a Pareto rank, fiscal cost, expected survival
  lift, employment preservation proxy, fairness penalty, conflict-sensitivity
  score and robustness score;
- results are explicitly labelled as proxy/simulation outputs, not real causal
  effects.

#### S5. Governance Review and Thesis Decision Packet

Question:

```text
Can PolicyOS produce a readable, auditable policy recommendation packet that
names assumptions, limitations, and what would be needed for a stronger claim?
```

Inputs:

- S1-S4 outputs;
- H1-H6 limitations;
- optional LLM governance critique.

Outputs:

- `governance_review.md`;
- `decision_packet.md`;
- `showcase_thesis_summary.md`;
- `showcase_artifact_table.md`;
- `showcase_index.json`.

Success criterion:

- the packet separates actionable recommendation from evidence limitations;
- missing microdata and deferred amendment enrichment are not hidden;
- the result can be moved into the thesis as an experimental appendix without
  overclaiming.

### 16.3 Launch Profile

Current active VM:

```text
project_id   = lex-1-494208
zone         = europe-west1-b
instance     = msme-exp-main-20260430
machine      = n2-custom-12-98304
vCPU/RAM     = 12 vCPU / 96 GB
disk         = 240 GB pd-ssd
workdir      = /mnt/experiments/msme_deadline_20260430
gcs_prefix   = gs://lex-1-494208-data/experiments/msme_deadline_20260430/e2e_showcase
```

Threading profile:

```bash
export POLISYOS_EXPERIMENT_THREADS=12
export OMP_NUM_THREADS=12
export MKL_NUM_THREADS=12
export OPENBLAS_NUM_THREADS=12
export NUMEXPR_MAX_THREADS=12
export JAX_PLATFORMS=cpu
export JAX_PLATFORM_NAME=cpu
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=12"
```

Run mode:

- `--mode preflight` first;
- if preflight passes, `--mode run`;
- sync each S-experiment folder to GCS immediately after completion;
- keep a local log under `logs/e2e_showcase.log`;
- do not delete any H1-H6 artifacts.

### 16.4 Expected Time Budget

| Stage | Expected time on 12 vCPU | Notes |
| --- | ---: | --- |
| Preflight | 2-5 min | checks data, imports, GCS write, optional LLM env |
| S1 policy design loop | 5-25 min | depends on LLM availability/rate limits |
| S2 Fabric trust flow | 3-10 min | mostly model conversion and JSON writing |
| S3 Foundry compile/execute | 5-20 min | may include JAX/registry startup overhead |
| S4 optimization arena | 30-120 min | tunable; target high CPU utilization |
| S5 governance packet | 5-20 min | LLM optional, deterministic fallback fast |
| Final aggregation/sync | 5-15 min | depends on CAS/output size |

Total expected wall time: 1-3 hours for the default showcase profile, with a
safe upper buffer of 4-5 hours if LLM calls retry or Foundry compiles slowly.

### 16.5 Claims Allowed After Phase 2

Allowed:

- PolicyOS can compose legal evidence, dataset evidence, Fabric trust envelopes,
  Foundry execution and policy optimization into one reproducible cloud workflow.
- The system can produce a policy recommendation packet with explicit
  limitations and audit artifacts.
- Foundry compile/execute is verified in the same environment as the thesis
  experiments, at least on the quickstart policy bundle.

Not allowed:

- claim that every production route was exercised through the HTTP runtime;
- claim that real treatment effects were estimated without applicant-level
  microdata;
- claim that amendment-aware legal temporal reasoning is complete;
- claim that LLM agents were used if the run fell back to deterministic agents.

## 17. Phase 3: MSME PolicyOS Grand Tournament v2

Дата фиксации дизайна: 2026-04-30
Рабочее имя запуска: `msme_grand_tournament_v2`
Целевой runtime: 2-4 часа на текущем cloud-стеке, с возможностью ранней
остановки после получения thesis-grade артефактов.
GCS prefix:

```text
gs://lex-1-494208-data/experiments/msme_deadline_20260430/msme_grand_tournament_v2/
```

### 17.1 Why Phase 3 Exists

Phase 2 доказал композиционный путь, но он был осторожным: несколько policy
designs, Fabric trust flow, Foundry quickstart и 120k proxy-кандидатов. Для
дипломного дедлайна этого достаточно, но не показывает весь потенциал системы.

Phase 3 должен показать более сильный, но честный результат:

- LLM/agentic policy design не на 3, а на десятки политик;
- Fabric/Datasets не на несколько источников, а на сотни релевантных dataset
  candidates и тысячи observation/metric links;
- Foundry causal block не как “название блока”, а как исполняемый gauntlet с
  реальными `pure_step`-вызовами там, где текущие сигнатуры позволяют;
- `ukraine_agent_simulation_baseline_20260410` используется как источник
  графовой структуры и wartime-agent priors;
- policy ranking проходит через MCDA/welfare/governance layer;
- итоговый пакет явно разделяет: verified evidence, proxy evidence,
  synthetic/semi-synthetic simulation, and blocked claims.

Главное правило Phase 3: амбициозность не должна превращаться в overclaiming.
Если нет applicant-level microdata, результат может быть сильной системной
апробацией PolicyOS и scenario-ranking experiment, но не “доказанным
каузальным эффектом” реальной программы.

### 17.2 Capability Inventory Used For Design

Этот раздел зафиксирован после повторного осмотра текущего репозитория и
подготовленной VM, а не только на основании архитектурного описания.

#### Scientist / Policy Design

Реальный DAG `scientist_policy_design` включает:

- planning: `plan_policy_request`, `build_execution_plan`, `run_preflight`;
- data: `build_data_snapshot`, `bind_foundry_inputs`, `run_data_plane_gate`;
- evidence: `build_literature_prior`, `reconcile_causal_graph`,
  `compile_cross_graph_evidence`;
- legal/source path: `assemble_legal_candidate_pack`,
  `expand_legal_source_pack`, `run_source_verification`,
  `run_source_gap_review`;
- policy generation/search: `draft_policy_options`,
  `formalize_verified_policy`, `run_hierarchical_policy_search`;
- execution: `compile_foundry`, `resolve_parameters`,
  `counterfactual_identification_gate`, `run_simulation`;
- evaluation: `run_metric_validation`, `legal_check`,
  `run_distributional_analysis`, `propagate_welfare`,
  `propagate_uncertainty`, `run_causal_evaluation`,
  `run_normative_arbitration`, `run_governance`;
- final packaging: `build_verified_policy_report`,
  `run_policy_blueprint_runtime`, `run_policy_translation`,
  `run_translator_compliance`, `build_policy_output_bundle`.

Deadline decision:

- do not depend on a fully successful end-to-end Scientist DAG for the entire
  run, because it requires very carefully pinned registry/input artifacts;
- use a controlled harness that exercises the same components and records which
  steps are direct system calls, which are compatibility projections, and which
  are deadline adapters;
- reserve a small `scientist_policy_design` smoke/preflight lane if the required
  state can be built quickly, but do not block the whole experiment on it.

#### Foundry Method Catalog

The registered method catalog on the prepared environment contains hundreds of
methods; the relevant inventory observed for this experiment is:

| Family | Approx. count | Phase 3 use |
| --- | ---: | --- |
| causal | 151 | AIPW, TMLE, IPW, matching, diagnostics, bounds, sensitivity, DiD/proxy lanes |
| econometrics | 46 | panel and reduced-form support where signatures fit |
| policy | 23 | budget impact, scorecard, TOPSIS/AHP/ELECTRE-style MCDA, welfare proxies |
| simulation | 15 | agent population / coupled policy / Monte Carlo lanes |
| distributional | 17 | subgroup and incidence summaries |
| optimization | 18 | search/frontier scoring support |
| survey / spatial / network / forecasting | 53+ combined | support diagnostics and extensions |

Directly inspectable `pure_step` methods available for Phase 3 include:

- `AIPWEstimator`, `TMLEEstimator`, `IPWEstimator`,
  `PropensityScoreMatchingEstimator`, `EntropyBalancingEstimator`,
  `CBPSEstimator`;
- `ManskiBoundsEstimator`, `LeeBoundsEstimator`,
  `BalkePearlBoundsEstimator`, `ImbensManskiBoundsEstimator`,
  `OptimizationBasedBoundsEstimator`;
- `TOPSISEstimator`, `AHPEstimator`, `RankStabilityEstimator`,
  `RobustTOPSISEstimator`, `RobustAHPEstimator`, `RobustELECTREEstimator`;
- `BudgetImpactEstimator`, `PolicyScorecardEstimator`,
  `ExAnteSimulationEstimator`;
- `AgentPopulationSimulationEstimator`,
  `CoupledPolicySimulationEstimator`, `CoupledPairedMonteCarloEstimator`;
- system dynamics, queue simulation, Monte Carlo, bootstrap and permutation
  inference methods.

Deadline decision:

- call the simple, stable `pure_step` methods directly for treatment-effect,
  MCDA, budget and simulation stages;
- for methods whose state models are heavier (`PanelObservationalData`,
  graph-specific SCM objects, PAG/transport objects), record them as catalog
  capabilities and run a deadline adapter only if building their typed state is
  feasible inside the timebox;
- every result row must include `execution_mode`:
  `foundry_pure_step`, `foundry_quickstart`, `deadline_adapter`,
  `proxy_simulation`, or `not_run_capability_inventory_only`.

#### Fabric / Datasets

Available production data:

| Artifact | Observed role |
| --- | --- |
| `dataset_catalog.duckdb` | 137,176 datasets, 605,408 distributions, 56,846 metric bindings, 3,708,006 observations |
| `ds_dataset_embeddings.npz` + `ds_dataset_index.hnsw` | dataset retrieval / semantic search support |
| `all_records.jsonl` | raw merged catalog records |
| `consumer_readiness.json`, `qc_report.json`, `benchmark_report.json` | readiness and quality posture |

Phase 3 Fabric task:

- retrieve and score hundreds of MSME-relevant datasets instead of hand-picking a
  few sources;
- build a `fabric_evidence_matrix` with relevance, quality, variable alignment,
  metric binding, distribution format and observation coverage;
- wrap decision-bearing metrics as Runtime `QuantityValue` and project them into
  Fabric decision-data envelopes using `from_runtime_quantities`;
- mark source limitations as part of the output, not as a hidden failure.

#### Ukraine Agent Simulation Baseline

Available bundle:

```text
policy-engine/production_data/ukraine_agent_simulation_baseline_20260410/
```

Important graph add-ons:

| Graph | Role in Phase 3 |
| --- | --- |
| `budget_graph_sparse.npz` | fiscal exposure / spending-network proxy |
| `procurement_graph_sparse.npz` | procurement channel and SME demand proxy |
| `distress_graph_sparse.npz` | regional/business distress propagation proxy |
| `trade_graph_sparse.npz` | trade shock and network-spillover proxy |
| `public_service_graph_sparse.npz` | service-access / local capacity proxy |

Phase 3 will use these graphs conservatively:

- load graph metadata and sparse row/degree summaries;
- derive policy-specific spillover priors for conflict targeting, procurement
  preference, credit depth and public-service capacity;
- avoid claiming that the graph alone identifies causal effects;
- use graph features as scenario priors for agent-simulation and robustness.

#### Academic / Transport Evidence

Available bundle:

```text
policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/
```

Key artifacts:

- `academic/graph/scholar_knowledge.duckdb`;
- `academic/transport_scores.jsonl`;
- `academic/ac_work_embeddings.npz`;
- `academic/ac_work_index.hnsw`;
- runtime evidence manifests and benchmark/QC reports.

Phase 3 use:

- sample transport scores relevant to entrepreneurship, credit, grants,
  employment and wartime/public-sector support;
- produce a `transport_prior_summary`;
- do not block the run if full SKG traversal is too heavy for the deadline.

### 17.3 Experimental Questions

Phase 3 answers five higher-level questions:

1. Can PolicyOS generate a broad portfolio of wartime SME policy designs from
   legal, dataset and academic evidence?
2. Can Fabric evidence retrieval scale from a handful of sources to hundreds of
   candidate datasets while preserving traceability?
3. Do multiple Foundry causal estimators, bounds and diagnostics give a coherent
   caution profile under semi-synthetic MSME panels?
4. Which policy levers remain robust under agent-simulation shocks, regional
   conflict priors, budget constraints and fairness penalties?
5. Can the system produce a thesis-ready decision dossier that is ambitious but
   explicit about limitations?

### 17.4 Stage Design

#### T1. Capability Snapshot

Inputs:

- Foundry method registry;
- Scientist workflow spec;
- production-data manifests;
- Lex finalize manifests;
- GCP machine/runtime metadata.

Outputs:

- `T1_capability_snapshot/method_catalog_summary.json`;
- `T1_capability_snapshot/scientist_workflow_inventory.json`;
- `T1_capability_snapshot/fabric_catalog_counts.json`;
- `T1_capability_snapshot/agent_baseline_graph_inventory.json`;
- `T1_capability_snapshot/runtime_environment.json`;
- `T1_capability_snapshot/capability_snapshot_summary.md`.

Success criterion:

- the final report can prove which system capabilities were actually visible in
  the run environment.

#### T2. Policy Design Factory

Inputs:

- policy intent about wartime Ukrainian SME support;
- Lex/H1 legal evidence snippets;
- Fabric dataset candidate summaries;
- optional Gonka/LLM keys from the prepared environment.

Planned work:

- ask the LLM for 4-6 batches of policy designs, each with different roles:
  fiscal conservative, resilience planner, fairness/recourse reviewer,
  procurement/regional-development designer, anti-fraud/governance reviewer;
- target 72-120 normalized policy designs;
- fill missing designs with deterministic combinatorial variants if LLM is
  rate-limited;
- validate normalized fields against a schema-lite compatible with
  `PolicyCandidateSchema` concepts: rollout, target population, parameters,
  budget envelope, monitoring metrics, assumptions, harm envelope, fallback.

Outputs:

- `T2_policy_design_factory/policy_design_requests.jsonl`;
- `T2_policy_design_factory/llm_policy_batches.jsonl`;
- `T2_policy_design_factory/normalized_policy_designs.jsonl`;
- `T2_policy_design_factory/policy_schema_compatibility_report.json`;
- `T2_policy_design_factory/policy_design_factory_summary.md`.

Success criterion:

- at least 72 valid policy designs, ideally 96-120;
- every design has bounded budget, target group, levers, monitoring signals,
  legal/evidence references and known limitations.

#### T3. Fabric Evidence Matrix

Inputs:

- `dataset_catalog.duckdb`;
- normalized policy designs;
- MSME/war/economic keywords in Ukrainian and English;
- selected `ds_metric_bindings`, `ds_variable_alignments`,
  `ds_distributions`, `ds_observations`.

Planned work:

- retrieve 500-1,500 relevant dataset candidates;
- compute relevance, source quality, parser support, metric-binding confidence,
  variable-alignment confidence and observation coverage;
- construct policy-by-evidence matrix for all normalized designs;
- create Runtime `QuantityValue` envelopes for core evidence scores;
- project core quantities into Fabric decision-data envelopes.

Outputs:

- `T3_fabric_evidence_matrix/relevant_datasets.jsonl`;
- `T3_fabric_evidence_matrix/evidence_matrix.parquet` or `.jsonl`;
- `T3_fabric_evidence_matrix/runtime_quantities.json`;
- `T3_fabric_evidence_matrix/fabric_decision_data.json`;
- `T3_fabric_evidence_matrix/fabric_coverage.json`;
- `T3_fabric_evidence_matrix/fabric_evidence_matrix_summary.md`.

Success criterion:

- hundreds of datasets are considered;
- the shortlist is traceable and not just hand-selected;
- low-quality/proxy sources are labelled rather than silently excluded.

#### T4. Foundry Causal Gauntlet

Inputs:

- semi-synthetic applicant/firm panel generated from disclosed priors;
- policy assignments derived from design levers;
- Fabric evidence weights and region/conflict priors;
- Foundry causal methods that can be called directly.

Planned direct Foundry calls:

- AIPW;
- TMLE;
- IPW;
- propensity-score matching;
- entropy balancing / CBPS if stable under generated panel;
- Manski/Lee/Imbens-Manski/Balke-Pearl-style bounds where signature fits.

Planned deadline adapters:

- DiD / synthetic control / transport checks if typed state construction would
  take too long;
- placebo and overlap diagnostics with explicit `execution_mode` labels.

Outputs:

- `T4_causal_gauntlet/causal_panel_manifest.json`;
- `T4_causal_gauntlet/causal_method_runs.jsonl`;
- `T4_causal_gauntlet/causal_consensus_table.json`;
- `T4_causal_gauntlet/identification_and_bounds_report.md`;
- `T4_causal_gauntlet/causal_gauntlet_summary.md`.

Success criterion:

- multiple real Foundry estimators run successfully;
- estimates, bounds and diagnostics are reported as a caution profile, not as
  final causal proof;
- any adapter/proxy result is visibly labelled.

#### T5. Ukraine Graph-Aware Agent Simulation Arena

Inputs:

- normalized policy designs;
- `ukraine_agent_simulation_baseline_20260410` graph summaries;
- Fabric evidence priors;
- budget, procurement, distress, trade and public-service graph features;
- 12-vCPU CPU/JAX environment.

Planned work:

- evaluate 72-120 designs across multiple seeds, regions and shock scenarios;
- simulate firm survival, employment preservation, credit uptake, grant uptake,
  default risk, admin burden, fraud/abuse risk, conflict resilience and budget
  pressure;
- use graph-derived priors for spillover and resilience penalties;
- run in multiprocessing/JAX/NumPy chunks to keep CPU near saturation;
- sync intermediate chunks to GCS after each major batch.

Outputs:

- `T5_agent_sim_arena/simulation_input_manifest.json`;
- `T5_agent_sim_arena/agent_sim_chunks/*.jsonl`;
- `T5_agent_sim_arena/policy_simulation_scores.jsonl`;
- `T5_agent_sim_arena/spillover_prior_summary.json`;
- `T5_agent_sim_arena/agent_sim_arena_summary.md`.

Success criterion:

- each policy is evaluated under many scenario draws;
- the run produces enough work to materially exercise CPU;
- simulation results expose uncertainty, not only a single rank.

#### T6. Welfare, MCDA, Robustness and Governance Tournament

Inputs:

- T2 policy designs;
- T3 Fabric evidence matrix;
- T4 causal caution profile;
- T5 simulation scores;
- Foundry policy methods: budget impact, scorecard, TOPSIS/AHP/ELECTRE and
  robust variants where stable.

Planned work:

- build a decision matrix with criteria:
  survival lift proxy, employment preservation, budget cost, fairness,
  conflict sensitivity, fraud risk, admin feasibility, legal/evidence support,
  causal caution and robustness;
- rank with several weight profiles:
  balanced, fiscal-conservative, resilience-first, fairness-first,
  implementation-risk-first;
- run rank stability under weight perturbations;
- optionally ask LLM governance reviewers to critique top 10 policies.

Outputs:

- `T6_tournament/tournament_decision_matrix.json`;
- `T6_tournament/mcda_results.json`;
- `T6_tournament/rank_stability.json`;
- `T6_tournament/top_policy_dossiers.json`;
- `T6_tournament/governance_jury.jsonl`;
- `T6_tournament/tournament_summary.md`.

Success criterion:

- final top policies are not just best on expected score; they survive at least
  one robustness/stability check;
- governance warnings are attached to the shortlist.

#### T7. Foundry/Scientist Shortlist Compatibility

Inputs:

- top 5-10 policies from T6;
- Foundry quickstart compile/execute path;
- policy schema compatibility report.

Planned work:

- run Foundry quickstart compile/execute as an execution-path proof;
- map top policies into a compact Scientist/PolicyCandidate compatibility
  projection;
- if full `scientist_policy_design` smoke state can be assembled safely, run it
  as an optional non-blocking lane.

Outputs:

- `T7_shortlist_compatibility/foundry_quickstart_results.json`;
- `T7_shortlist_compatibility/shortlist_policy_candidate_projection.json`;
- `T7_shortlist_compatibility/scientist_smoke_result.json` if attempted;
- `T7_shortlist_compatibility/shortlist_compatibility_summary.md`.

Success criterion:

- the report distinguishes “compatible with PolicyOS contracts” from “fully
  executed through the production DAG”.

#### T8. Thesis Dossier

Outputs:

- `T8_thesis_dossier/grand_tournament_index.json`;
- `T8_thesis_dossier/grand_tournament_results_summary.md`;
- `T8_thesis_dossier/thesis_tables.md`;
- `T8_thesis_dossier/appendix_artifact_inventory.md`;
- `T8_thesis_dossier/limitations_and_claims_boundary.md`.

Success criterion:

- a human-readable packet can be moved into the thesis within 1-2 hours after
  the run finishes;
- every figure/table has a source artifact.

### 17.5 Runtime Profile

Current machine:

```text
instance = msme-exp-main-20260430
zone     = europe-west1-b
machine  = n2-custom-12-98304
vCPU/RAM = 12 vCPU / 96 GB
disk     = 240 GB pd-ssd
```

Recommended command profile:

```bash
export POLISYOS_EXPERIMENT_THREADS=12
export OMP_NUM_THREADS=12
export MKL_NUM_THREADS=12
export OPENBLAS_NUM_THREADS=12
export NUMEXPR_MAX_THREADS=12
export JAX_PLATFORMS=cpu
export JAX_PLATFORM_NAME=cpu
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=12"
```

Default experiment sizing:

| Knob | Default | Purpose |
| --- | ---: | --- |
| `policy_count` | 96 | enough designs for a serious policy tournament |
| `fabric_dataset_limit` | 1,200 | broad evidence retrieval without exhausting time |
| `causal_panel_rows` | 120,000 | causal gauntlet large enough for stable diagnostics |
| `agent_count` | 180,000 | CPU-heavy agent simulation per chunk |
| `simulation_months` | 24 | wartime policy horizon |
| `simulation_seeds` | 48 | uncertainty/robustness draws |
| `threads` | 12 | saturate current VM without overcommitting |

Expected wall time:

| Stage | Expected time |
| --- | ---: |
| T1 capability snapshot | 3-8 min |
| T2 policy design factory | 10-40 min depending on LLM rate limits |
| T3 Fabric evidence matrix | 5-20 min |
| T4 causal gauntlet | 15-45 min |
| T5 agent simulation arena | 45-150 min, tunable |
| T6 tournament | 5-25 min |
| T7 compatibility | 5-25 min |
| T8 dossier | 5-15 min |

Total target: 2-4 hours. If the LLM provider is slow, the run should continue
with deterministic policy variants and mark `llm_status` accordingly.

### 17.6 Safety and Resume Rules

- Do not delete H1-H6 or Phase 2 outputs.
- Every stage writes `experiment_result.json` or a stage summary before syncing.
- Sync each stage folder to GCS immediately after completion.
- If a stage fails, write a typed failure artifact and continue when downstream
  stages can use partial results.
- Do not print API keys into logs; artifacts may record key variable names and
  availability only.
- If the run is interrupted, resume from existing stage artifacts where possible
  instead of overwriting completed outputs.

### 17.7 Claims Boundary

Allowed after a successful Phase 3:

- PolicyOS can run a broad, auditable policy-design and simulation tournament
  over wartime Ukrainian SME support scenarios.
- The system can combine Lex-derived legal evidence, Fabric dataset evidence,
  Foundry causal estimators, graph-aware simulation and policy MCDA into one
  reproducible cloud workflow.
- The system can generate thesis-grade artifacts with clear limitation labels.

Not allowed:

- claiming real causal effects for Ukrainian MSME programs without
  applicant-level treatment/outcome microdata;
- claiming all 389 Foundry methods were executed;
- claiming full amendment-aware legal temporal reasoning, because amendment
  enrichment was deferred in the fast finalize;
- claiming LLM-agent policy generation if the run used deterministic fallback.

### 17.8 Go / No-Go Criteria Before Launch

Go if all are true:

- VM is running and has the repository, venv and production data mounted/staged;
- Lex finalize artifacts are reachable from GCS or local workdir;
- `dataset_catalog.duckdb` is readable;
- Foundry imports and at least one direct `pure_step` method works;
- GCS write test succeeds under the Phase 3 prefix;
- the Phase 3 design is committed to this roadmap before launching.

No-go or downgrade if:

- GCS write fails;
- production data is missing;
- core imports fail in the cloud venv;
- available disk drops below a safe buffer for outputs and temporary arrays.

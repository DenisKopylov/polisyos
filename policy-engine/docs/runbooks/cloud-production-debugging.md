# Cloud Production Debugging Runbook

Owner: `@platform-owners` with `@runtime-owners`
Created: `2026-05-20`
Scope: Google Cloud production-debug setup for real PolicyOS production-quality validation.
Evidence path: `_build/.tmp/production-quality/`, `.polisyos/canary_evidence/`, `.polisyos/canary_matrix_runs/`, `gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/`.
Rollback path: stop the VM, stop or remove the PostgreSQL container, and remove the staging bucket prefix only after evidence has been copied.

Use this runbook when local MacBook validation is not enough and we need a production-like cloud host with durable PostgreSQL control-plane state, real provider credentials, production data, and IAP-only operator access. This is still a debug deployment, not a promoted production service.

## Active Debug Host

```text
account: repairkyiv4@gmail.com
project: lex-1-494208
zone: europe-west1-b
instance: policyos-prod-debug-20260520
machine: e2-standard-8
disk: 250 GB pd-balanced
image: Ubuntu 24.04 LTS
service account: policyos-prod-debug-vm@lex-1-494208.iam.gserviceaccount.com
network: default VPC, no external IP
ssh: IAP tunnel only
tags: policyos-prod-debug
```

Security posture for the debug host:

- OS Login is enabled.
- Project SSH keys are blocked on the instance.
- Shielded VM secure boot, vTPM, and integrity monitoring are enabled.
- SSH ingress is limited to IAP source range `35.235.240.0/20` and target tag `policyos-prod-debug`.
- PostgreSQL is bound to `127.0.0.1:5432` inside the VM only.
- Provider credentials are stored in Secret Manager and written only to a VM-local env file with mode `0600`.

Connect:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap
```

Check the host without opening a shell:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='uname -a && df -h /workspace && sudo docker ps'
```

## Cloud Backing Services

The debug PostgreSQL container is:

```text
container: policyos-control-pg
image: postgres:16-alpine
bind: 127.0.0.1:5432 -> 5432
volume: policyos-control-pg-data
limits: 2 CPU, 2 GB RAM
database: polisyos_control
user: polisyos
```

Check health:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='sudo docker ps --filter name=policyos-control-pg --format "{{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

Restart only the backing database:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='sudo docker restart policyos-control-pg'
```

## Code And Data Layout

Workspace on the VM:

```text
/workspace/polisyos/policy-engine
/workspace/policyos_real_runs
/workspace/policyos_prod_debug_artifacts
```

Code is uploaded as a tarball without `.git`, `.venv`, `_build`, `production_data`, cache directories, or local env files. Production data is staged separately so large data transfer can be retried and reused.

Current staging prefix:

```text
gs://lex-1-494208-data/bootstrap/policyos-prod-debug-20260520/production_data/
```

The staged data was first bootstrapped with the manifest-required runtime subset
and then expanded to the full local `production_data` tree after the first live
pass showed that a minimal subset leaves too much uncertainty for a production
debug run. The current VM copy is expected to match local `production_data` at
`6562` files and about `34G`.

The manifest-required subset includes:

- `production_data/manifest.json`
- curated Fabric contracts and source bindings
- `dataset_catalog.duckdb`
- `lex_knowledge_graph.duckdb`
- `scholar_knowledge.duckdb`
- required benchmark, QC, manifest, and Ukraine simulation bundle metadata

The full staged tree additionally includes canonical legal provision shards,
publish manifests, academic publish/QC metadata, Ukraine simulation heavy graph
add-ons, calibration/intervention/runtime bundles, cell registries, embedding
bundles, and related release manifests.

Sync staged data to the VM:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && gcloud storage rsync -r gs://lex-1-494208-data/bootstrap/policyos-prod-debug-20260520/production_data production_data'
```

Verify the required files exist:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && test -f production_data/manifest.json && du -sh production_data'
```

## Cloud Env

The VM-local env file is:

```text
/workspace/polisyos/policy-engine/.env.prod-cloud
```

It must stay untracked and mode `0600`. It contains:

```text
POLISYOS_EXECUTION_PROFILE=research
POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=1
POLISYOS_CONTROL_WORKER_BACKEND=embedded
POLISYOS_CONTROL_STATE_STORE_BACKEND=postgres
POLISYOS_CONTROL_POSTGRES_DSN=postgresql://polisyos:...@127.0.0.1:5432/polisyos_control
POLISYOS_LLM_GATEWAY_BASE_URL=https://proxy.gonka.gg/v1
POLISYOS_LLM_GATEWAY_PROVIDER=gonka_proxy
POLISYOS_LLM_GATEWAY_API_KEY=...
POLISYOS_PRODUCTION_DATA_ROOT=/workspace/polisyos/policy-engine/production_data
```

Load it before probes:

```bash
set -a
source .env.prod-cloud
set +a
```

## Validation Order

Run the lightweight cloud quick probe first:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && set -a && source .env.prod-cloud && set +a && uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks quick --output _build/.tmp/production-quality/cloud_prod_debug_quick.json'
```

Run provider preflight before spending time on a live lane:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && set -a && source .env.prod-cloud && set +a && uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks provider-preflight --allow-live-provider --output _build/.tmp/production-quality/cloud_prod_debug_provider.json'
```

Run exactly one live research lane after quick and provider checks have useful output:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && set -a && source .env.prod-cloud && set +a && uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py --repo-root . --checks live-research-lane,evidence-inspection --allow-live-provider --live-timeout-s 900 --output _build/.tmp/production-quality/cloud_prod_debug_live.json'
```

Expected cloud blockers are valid findings, not reasons to delete evidence:

- provider gateway health, model availability, or response format degradation;
- missing production-data paths if the staged subset is incomplete for a workflow;
- strict `production` bootstrap failing until the real security chain and external worker topology are available;
- evidence/readiness mismatches where a failed live lane is not reflected in readiness.

## 2026-05-20 Cloud Setup Log

- Created VM `policyos-prod-debug-20260520` in project `lex-1-494208`, zone
  `europe-west1-b`, under account `repairkyiv4@gmail.com`.
- Used `e2-standard-8`, `250 GB` balanced persistent disk, Ubuntu 24.04 LTS,
  no external IP, OS Login, blocked project SSH keys, Shielded VM, and IAP-only
  SSH.
- Created VM service account `policyos-prod-debug-vm@lex-1-494208.iam.gserviceaccount.com`
  with Secret Manager read and GCS object access for the debug prefixes.
- Added Cloud Router/NAT for outbound package install while keeping the VM
  private.
- Installed Docker, Docker Compose, PostgreSQL client, `uv`, Node 22, `pnpm`,
  and build headers needed by Python package wheels/source builds.
- Started `policyos-control-pg` from `postgres:16-alpine`, bound to
  `127.0.0.1:5432`, with Docker limits of `2` CPU and `2 GB` RAM.
- Uploaded code to `/workspace/polisyos/policy-engine` without `.git`, local
  env files, caches, `_build`, or `production_data`; initialized a local git
  metadata directory only so docs reproducibility checks can evaluate
  `.gitignore`.
- Stored the live-provider key in Secret Manager as
  `policyos-llm-gateway-api-key`; wrote `.env.prod-cloud` on the VM with mode
  `0600`.
- Staged full `production_data` to
  `gs://lex-1-494208-data/bootstrap/policyos-prod-debug-20260520/production_data/`
  and synced it to the VM.

## 2026-05-20 Validation Notes

Observed evidence paths:

```text
gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality/
gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_evidence/live-research/
gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/canary_matrix_runs/live-research/
```

Validation sequence:

```text
cloud_prod_debug_provider.json: pass
cloud_prod_debug_quick.json: warn, 6 passed / 1 warned / 0 failed, minimal production_data
cloud_prod_debug_live.json: fail, early LLM gateway model-variant failure, minimal production_data
cloud_prod_debug_quick_full_data.json: warn, 6 passed / 1 warned / 0 failed, full production_data
cloud_prod_debug_live_full_data.json: fail, completed run with scorecard fail, full production_data
```

Important interpretation:

- Full `production_data` changed the live behavior from early model-call failure
  to a completed run with no missing required evidence in the canary matrix
  envelope.
- The full-data live run still failed the production-quality scorecard with
  `overall_score=0.34375`, `quality_status=fail`, and
  `approval_state=quality_failed`.
- The scorecard failure is a real product/system diagnostic, not an
  infrastructure bootstrap failure.

Primary full-data scorecard blockers:

- provider/model quality ledger demotes the default Qwen model because the live
  observation had `grounding_failure_rate=1.0`;
- prompt/tool/parser authority ledger is not passing serious closeout;
- several authority-bearing record families fail `hds_unknown_provenance`;
- production data quality remains failing on missing data dictionaries,
  construct-validity metrics, recency timestamps, missingness, and outliers;
- Lex normative applicability cannot find a relevant norm and recommendation
  normative anchors are missing;
- Fabric source selection picked a source family that is not admissible for the
  serious lane and lacks rights, dictionary, schema, and field refs;
- Foundry method evidence used an unexpected method family and lacks required
  assumptions, uncertainty, and missingness diagnostics;
- policy grounding has major claims without sufficient grounding and freshness
  is unknown;
- serious Policy Design Case records still miss concept/jurisdiction closure,
  scholar academic evidence, substrate residual verification, self-FMEA,
  partial-state consistency, maturity profile, dormant capability inventory,
  skip-causality ledger, freshness/policy-time semantics, Pass 1B hardening, and
  legacy migration redaction closure.

## Preserve Evidence

After each run, copy evidence to the project bucket:

```bash
gcloud compute ssh policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap \
  --command='cd /workspace/polisyos/policy-engine && gcloud storage rsync -r _build/.tmp/production-quality gs://lex-1-494208-data/real_runs/policyos-prod-debug-20260520/production-quality'
```

Optional local pull:

```bash
gcloud compute scp --recurse \
  policyos-prod-debug-20260520:/workspace/polisyos/policy-engine/_build/.tmp/production-quality \
  _build/cloud-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b \
  --tunnel-through-iap
```

## Pause Or Cleanup

Stop the VM when not actively debugging:

```bash
gcloud compute instances stop policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b
```

Restart it:

```bash
gcloud compute instances start policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b
```

Delete only after evidence has been copied and the staging data is no longer needed:

```bash
gcloud compute instances delete policyos-prod-debug-20260520 \
  --project=lex-1-494208 \
  --zone=europe-west1-b
```

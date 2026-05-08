# Repository Best-In-Class Remediation - Phase 0.6 Inventory

Date: 2026-05-05

Scope: ops, runtime state, control-plane topology, release gates, and supply-chain controls.

This is a read-only inventory report for Wave 1 planning. It records current repository state and local ignored runtime-state shape, but does not change ops paths, rulesets, workflows, or secrets.

## Summary

Phase 0.6 has enough data for Wave 1 to decide:

- Ops taxonomy: keep `ops/**` as the declarative/control-plane artifact tree and `tools/ops/**` as executable runner/helper surface, with explicit exceptions called out below.
- Runtime-state contract: split `.polisyos/**` into ephemeral execution state, CAS/materialized blobs, retained audit/evidence, external production snapshots, and promotion candidates.
- Operability bundle shape: SLO source files, Prometheus rules, dashboards, runbooks, and component-to-runbook mapping exist, but alert-level `runbook_url` annotations are sparse.
- Supply-chain controls: active release workflow already has SBOM, vulnerability policy, keyless signing, provenance attestations, canary gate, and GitHub release publication. Branch/ruleset and CODEOWNERS are present as repository artifacts, but some docs describing governance are stale.

## 1. Runtime State Inventory

### `.polisyos` first-level entries

All observed `.polisyos/**` entries are ignored by git and have no tracked files.

| Path | Files | Dirs | Size | Classification | Notes |
| --- | ---: | ---: | ---: | --- | --- |
| `.polisyos/artifacts` | 6858 | 3604 | 95M | CAS/materialized blobs | Hash-shaped `sha256/**` content. Do not commit raw blobs. |
| `.polisyos/audits` | 19 | 2 | 228K | retained evidence candidate | Contains repository SOTA audit output. Promote curated reports/manifests after review. |
| `.polisyos/cas` | 0 | 3 | 0B | CAS root | Empty local CAS root, documented in code examples. |
| `.polisyos/cas-readme-check` | 54 | 55 | 228K | CAS check fixture/state | Local CAS validation output. Usually ephemeral. |
| `.polisyos/cas_cache` | 0 | 3 | 0B | CAS cache | Empty local cache root. |
| `.polisyos/decision_validity` | 0 | 5 | 0B | runtime state | Empty namespaces for dedupes, dependencies, packets, and lineages. |
| `.polisyos/evicted` | 1439 | 207 | 184M | evicted runtime/CAS state | Large ignored eviction area. Needs retention/backup decision, not commit promotion. |
| `.polisyos/live_gonka_smoke.json` | 1 | 0 | 4K | smoke evidence candidate | Promote only after redaction and schema decision. |
| `.polisyos/production_data` | 80 | 23 | 27G | external production snapshots | Explicitly outside git. Requires external backup/object-store contract. |
| `.polisyos/provider_verification` | 1 | 1 | 4K | provider evidence candidate | Promote only if stable and non-sensitive. |
| `.polisyos/reports` | 6 | 2 | 24K | retained evidence candidate | Small report outputs are likely promotion candidates. |
| `.polisyos/runs` | 1131 | 578 | 5.5M | runtime execution state | Legacy/current run state. Use runtime inventory/archive helpers before changing contract. |
| `.polisyos/runtime` | 0 | 3 | 0B | runtime audit/idempotency root | Empty `audit` and `idempotency` namespaces. |
| `.polisyos/search_registry` | 4 | 8 | 16K | registry state | Calibration, lessons, judge thresholds, claim adjudication. Promote only curated summaries. |
| `.polisyos/security` | 1 | 2 | 20K | security evidence candidate | Contains SLSA-related local evidence. Promote curated attestation summaries only. |

### Nested runtime-state shape

Observed nested namespaces:

- `artifacts/sha256`
- `audits/repository-sota-phase-minus-1-5`
- `cas/artifacts`
- `cas_cache/artifacts`
- `cas-readme-check/artifacts`
- `decision_validity/dedupes`, `decision_validity/dependencies`, `decision_validity/packets`, `decision_validity/lineages`
- `evicted/phase-1a`
- `production_data/datasets_full_phase3full_20260327_183054`
- `production_data/lex_current_20260501`
- `production_data/policyos_academic_runtime_slim_20260411T112032Z`
- `production_data/ukraine_agent_simulation_baseline_20260410`
- `reports/repository-sota-phase-minus-1-5`
- `runs/<run-id>`
- `runtime/audit`, `runtime/idempotency`
- `search_registry/judge_thresholds`, `search_registry/claim_adjudication`, `search_registry/lessons`, `search_registry/calibration_meta`
- `security/slsa`

### CAS-related paths and assumptions

Documented or observed CAS/state roots:

- `.polisyos/cas` - README example root for `FileSystemCAS`.
- `.polisyos/artifacts/sha256` - observed materialized hash-addressed artifacts.
- `.polisyos/cas_cache/artifacts` and `.polisyos/cas-readme-check/artifacts` - observed cache/check roots.
- `.polisyos/runtime/audit` and `.polisyos/runtime/audit/archive` - runtime audit retention paths documented in security compliance material.
- `.polisyos/production_data` - production snapshots moved out of git by ADR.
- Tenant-scoped CAS roots are documented as `<root>/tenants/<tenant_id>` for fabric CAS usage.

Retention and backup signals:

- Runtime audit retention is documented with a 365-day command example.
- Core CAS artifacts are treated as immutable content-addressed state.
- `.polisyos/production_data` is large local production fixture/state and is not backed by git. Wave 1 should define whether this is disposable, reproducible, or backed by object storage.
- No repository-enforced backup policy was found for `.polisyos/**`; backup expectations are currently implied by docs and external storage conventions.

Promotion candidates for committed evidence:

- Curated small reports under `.polisyos/reports/**`.
- Curated audit manifests/summaries under `.polisyos/audits/**`.
- SLSA/security summaries under `.polisyos/security/slsa/**`.
- `provider_verification` output if it is schema-stable and non-sensitive.
- Smoke-run summaries such as `live_gonka_smoke.json` after redaction review.

Do not promote raw blobs, full run directories, evicted artifacts, production data snapshots, ignored local deployment assets, or secret-bearing material.

## 2. Ops Taxonomy Inventory

### Top-level subtree counts

| Path | Files | Dirs | Classification |
| --- | ---: | ---: | --- |
| `ops/README.md` | 1 | 0 | declarative perimeter description |
| `ops/ci` | 16 | 4 | declarative CI templates/placeholders |
| `ops/cloud` | 66 | 16 | mixed declarative infra plus local cloud runners/assets |
| `ops/deploy` | 1 | 1 | placeholder/reserved deploy contract |
| `ops/docker` | 3 | 1 | declarative local compose artifacts |
| `ops/migrations` | 7 | 1 | DB migration contract and SQL |
| `ops/observability` | 30 | 8 | observability artifacts |
| `ops/policy` | 15 | 2 | policy artifacts |
| `ops/release` | 3 | 1 | release governance policy |
| `ops/runtime` | 2 | 1 | runtime-state contract |
| `ops/security` | 6 | 1 | security policy/config |
| `tools/ops/__init__.py` | 1 | 0 | package marker |
| `tools/ops/__pycache__` | 1 | 1 | generated local residue |
| `tools/ops/calibration` | 5 | 2 | runner/script |
| `tools/ops/cloud` | 43 | 7 | runner/script |
| `tools/ops/data` | 11 | 2 | runner/script |
| `tools/ops/deploy` | 2 | 1 | placeholder/reserved deploy runner |
| `tools/ops/experiments` | 17 | 2 | runner/script |
| `tools/ops/migrations` | 7 | 2 | migration helpers |
| `tools/ops/release` | 15 | 2 | release gate helpers |
| `tools/ops/runtime` | 15 | 2 | runtime-state helpers |
| `tools/ops/ukraine_data` | 23 | 2 | data ingestion runners |

Duplicate subtree names between `ops/**` and `tools/ops/**`:

- `cloud`
- `deploy`
- `migrations`
- `release`
- `runtime`

Non-duplicate `ops/**` subtrees:

- `ci`
- `docker`
- `observability`
- `policy`
- `security`

Non-duplicate `tools/ops/**` subtrees:

- `calibration`
- `data`
- `experiments`
- `ukraine_data`

### Classification by duplicate name

| Name | `ops/**` role | `tools/ops/**` role | Wave 1 taxonomy decision |
| --- | --- | --- | --- |
| `cloud` | Helm, Terraform, GCP deploy assets, cloud docs | command implementations and cloud operation helpers | Keep declarative/provider assets in `ops/cloud`; keep executable helpers in `tools/ops/cloud`. Local ignored assets need explicit secret/runtime classification. |
| `deploy` | reserved deploy artifact contract | reserved provider-neutral deploy orchestration helpers | Decide whether to remove placeholder duplication or write an explicit reserved namespace contract. |
| `migrations` | DB SQL and migration contract | Python migration helper CLIs | Keep SQL/source-of-truth in `ops/migrations`; helpers stay in `tools/ops/migrations`. |
| `release` | commit/release-fragment policy | release validation/build helper scripts | Keep policy in `ops/release`; executable gate logic stays in `tools/ops/release`. |
| `runtime` | runtime-state contract docs | runtime API schema export/check and legacy run archive helpers | Keep contract docs in `ops/runtime`; keep inspectors/migrators in `tools/ops/runtime`. |

Additional inventory notes:

- `ops/policy/policies/*.rego` and Helm chart copies under `ops/cloud/helm/polisyos-cell/policies/*.rego` are documented as needing sync.
- `ops/ci/**` contains workflow templates, not active `.github/workflows/**` control-plane entries.
- Generated/local residue exists under ops-adjacent paths, including `__pycache__` and `.DS_Store` files. This phase only records them.

## 3. Operability Inventory

### `ops/observability` organization

Current shape:

- `ops/observability/otel/baseline.yaml`
- `ops/observability/prometheus/**`
- `ops/observability/grafana/**`
- `ops/observability/slo/**`

Prometheus files include:

- `alerts.yml`
- `recording_rules.yml`
- `slo_alerts.yml`
- `slo_recording_rules.yml`
- `rules/audit_chain_alerts.yml`
- `rules/mtls-rules.yaml`
- `rules/runtime_operability_alerts.yml`
- `rules/scientist-alerts.yml`

Grafana dashboards:

- `executive-overview.json`
- `foundry-hpc.json`
- `knowledge-freshness.json`
- `runtime-operability.json`
- `scientist-agents.json`
- `scientist-llm-cost.json`
- `security-phase4.json`
- `slo-overview.json`

### SLO source files

| File | Owner | Objectives | Runbook coverage |
| --- | --- | ---: | --- |
| `data_forge.yaml` | `team-data-forge` | 4 | yes |
| `docs_freshness.yaml` | `team-docs` | 1 | yes |
| `fabric.yaml` | `team-fabric` | 2 | yes |
| `runtime.yaml` | `team-runtime` | 2 | yes |
| `schema_drift.yaml` | `team-architecture` | 1 | yes |
| `scientist.yaml` | `team-scientist` | 2 | yes |

Total SLO objective count: 12.

### Runbook coverage

Runbook files exist for:

- artifact corruption recovery
- artifact signing / SBOM / SLSA failure
- benchmark regression triage
- broken contract generation
- cache rebuild storm
- canary rollback or promotion failure
- CAS/OPA outage
- dependency upgrade regression
- docs publication failure
- fabric quarantine, DLQ, and data-plane recovery
- idempotency incident
- key rotation
- Lex production 140k
- mutation audit investigation
- replay or restore
- retained artifact recovery
- runtime API outage
- runtime graceful shutdown and stuck worker

Coverage signal:

- SLO YAML objectives reference runbooks.
- `docs/reference/operations/observability-topology.md` maps alert families/components to runbooks and dashboards.
- Prometheus alert files contain 46 alert definitions but only 3 explicit `runbook_url` annotations. Wave 1 should decide whether alert-level `runbook_url` annotations are required for every production alert.

### Dashboard and docs drift

The observability topology reference documents 6 dashboards, while the tree currently contains 8 dashboards. The missing entries in the docs inventory are:

- `runtime-operability.json`
- `scientist-llm-cost.json`

### Public-stable package inventory

`architecture/public_surface/contract.toml` declares these `public_stable` modules:

- `polisyos.common`
- `core`
- `ir`
- `fabric`
- `foundry`
- `scientist`
- `runtime`
- `lex`

`architecture/public_surface/inventory.json` has inventory entries for all of them. Export counts currently recorded there are:

| Package | Export count |
| --- | ---: |
| `polisyos.common` | 7 |
| `core` | 15 |
| `ir` | 273 |
| `fabric` | 28 |
| `foundry` | 3 |
| `scientist` | 4 |
| `runtime` | 10 |
| `lex` | 50 |

Potential missing public-stable package artifact:

- If Wave 1 expects one committed per-package snapshot under `architecture/public_surface/`, only `data_forge.json` is present today. No per-package snapshots were found for the eight declared public-stable packages.

## 4. Migration Inventory

### DB SQL migrations

`ops/migrations/**` contains:

- `001_tenant_columns.sql` - add nullable `tenant_id` columns to tenant-scoped tables.
- `002_tenant_backfill.sql` - backfill template/gate before RLS enablement.
- `003_rls_enable.sql` - fail-safe tenant setting, indexes, NOT NULL, RLS enable/force, policies.
- `003_rls_disable_rollback.sql` - emergency rollback only.
- `004_roles_grants.sql` - app role/grant/default privilege baseline, with no `BYPASSRLS` or superuser grants.
- `migration-contracts.toml` - source-of-truth contract for migration ordering and rollback policy.

The migration contract names PostgreSQL as the database target and points to both `ops/migrations/*.sql` and `src/polisyos/core/security/db_backend.py`.

### Python migration helpers

Repository migration helper surfaces:

- `src/polisyos/common/migrations/**` - common-owned artifact migration registry/executor, including dataset manifest `0.9 -> 1.0`.
- `src/polisyos/ir/migrations/**` - policy IR/schema compatibility migration helpers and registry rules.
- `tools/ops/migrations/migrate.py` - CLI for `policy_ir`, `dataset_manifest`, and `run_manifest` JSON/YAML migrations.
- `tools/ops/migrations/migrate_duckdb_to_pg.py` - DuckDB to PostgreSQL tenant migration helper with dry-run mode.

### Runtime-state formats

Runtime-state format surfaces:

- `.polisyos/runs/<run-id>` - observed local run-state tree.
- `tools/ops/runtime/inventory_legacy_runs.py` - legacy run manifest inventory helper.
- `tools/ops/runtime/archive_legacy_runs.py` - deterministic archive helper for legacy run directories.
- `.polisyos/runtime/idempotency` - reserved idempotency namespace.
- `.polisyos/runtime/audit` - reserved runtime audit namespace.
- `ops/runtime/README.md` and `ops/runtime/runtime-state-contract.toml` - declarative runtime-state contract.

### API schemas

Runtime API schema surfaces:

- `schemas/runtime_api_v1.openapi.json`
- `tools/ops/runtime/export_runtime_openapi.py`
- `tools/ops/runtime/generate_api_client.py`
- `tools/ops/runtime/check_api_client_drift.py`
- `packages/runtime-api-client/**`
- `apps/runtime-dashboard/**`
- `apps/runtime-reference-shell/**`

### IR and artifact schemas

Schema inventory surfaces:

- `schemas/snapshots/ir/**` - IR schema snapshots and manifest.
- `schemas/snapshots/fabric/**` - fabric/source contract schema snapshots.
- `schemas/artifacts/**`
- `schemas/manifests/**`
- `schemas/ops/slo.schema.json`
- `schemas/topology/**`

Wave 1 should decide which schema families are governed as API contracts, runtime-state contracts, internal generated snapshots, or migration-only compatibility aids.

## 5. Release Topology And Promotion Gates

### Active release topology

Active release workflow: `.github/workflows/release.yml`.

Main jobs:

- `prepare-release`
- `build-artifacts`
- `release-notes`
- `supply-chain-gate`
- `release-canary`
- `sign-artifacts`
- `attest-artifacts`
- `publish-release`

Deployment/publication target:

- GitHub Releases for Python wheel, sdist, runtime dashboard bundle, checksums, signatures, certificates, release notes, SBOM, vulnerability report, vulnerability policy evidence, and build provenance.

Release artifacts:

- Python wheel
- Python sdist
- runtime dashboard tarball
- `SHA256SUMS`
- CycloneDX SBOM
- Grype vulnerability report
- vulnerability policy evidence
- Sigstore/cosign signatures and certificates
- GitHub build provenance attestations

### Control-plane / data-plane / frontend split

Control-plane surfaces:

- Runtime HTTP app and routes under `src/polisyos/runtime/http/**`.
- Runtime services under `src/polisyos/runtime/services/**`, including control-plane store/worker/task runner surfaces.
- Runtime deploy docs in `docs/how-to/deploy-runtime.md`.
- Runtime API OpenAPI schema and generated frontend client.

Data-plane surfaces:

- Fabric data-plane code under `src/polisyos/fabric/data_plane/**`.
- Foundry data-plane binding under `src/polisyos/foundry/data_plane/bindings.py`.
- Fabric/tenant CAS contracts in docs and source.

Frontend surfaces:

- `apps/runtime-dashboard`
- `packages/runtime-api-client`
- `apps/runtime-reference-shell`
- Workspace packages currently marked private in package metadata.

### Infrastructure/deployment targets

Observed deployment/infrastructure baselines:

- Helm chart `ops/cloud/helm/polisyos-cell` for cell/tenant isolation baseline.
- Helm chart `ops/cloud/helm/spire` for local SPIRE baseline.
- Helm chart `ops/cloud/helm/keycloak` for local Keycloak baseline.
- Terraform module `ops/cloud/terraform/modules/confidential_nodepool` for AKS confidential node pool.
- Local observability docker compose under `ops/docker/**`.
- GCP/Gonka helper scripts and ignored local assets under cloud ops paths.

Production-readiness caveats recorded by existing docs:

- Keycloak chart is local `start-dev` baseline and not HA/TLS/persistent production deployment.
- SPIRE chart is single-replica/local datastore baseline.
- Confidential node pool module is a module, not a full wired root/provider/backend deployment.
- Split LLM/compute infrastructure docs describe target state and P0/P1 gaps, not a plug-and-play release topology.

### Staging-to-production gates

Current gates:

- Release tag/version validation.
- Release fragment validation.
- Artifact size policy check.
- Supply-chain gate with SBOM, vulnerability scan, and policy evaluation.
- Canary environment job named `release-canary`.
- Production publication job with `release-production` environment.
- Runtime canary from installed release artifact.
- Runtime/dashboard smoke checks.
- Release notes build and curated notes sections.
- Signing and provenance before publish.

Current gap:

- No separate persistent staging deployment target/config manifest was found. The staged path is represented by release canary environment checks, dashboard environment labels, and the canary rollback/promotion runbook.

### Release evidence templates

Evidence templates and policies:

- `release/platform-acceptance.evidence.template.toml`
- `release/core-runtime-closeout.evidence.template.toml`
- `release/artifact-size-policy.toml`
- `release/cve-exceptions.toml`
- `release-fragments/template.toml`
- `ops/release/commit-policy.toml`
- `ops/release/release-fragment-policy.toml`

Evidence directories already include platform release canary/dry-run style artifacts, but this phase did not modify or promote them.

## 6. Control-Plane And Supply-Chain Inventory

### CODEOWNERS coverage

`.github/CODEOWNERS` exists and maps all current paths to `@DenisKopylov`.

Covered path families include:

- `.github/**`
- root governance metadata
- Renovate config
- `policy-engine/*`
- architecture, schemas, source packages, frontend packages, tests, data, benchmarks, examples, packs, baseline, docs, ops, tools, release, and release fragments.

Inventory caveat:

- `docs/reference/ownership.md` has a richer logical owner model.
- Actual CODEOWNERS is a personal-repo reviewer mapping.

### Branch/ruleset protection

`.github/repository-rulesets/main.yml` exists and defines:

- target branch include `refs/heads/main`
- pull request requirement
- one approval
- code owner review
- stale approval dismissal
- most recent push approval requirement
- conversation resolution
- strict required status checks:
  - `Fast PR / Gate`
  - `Standard PR / Gate`
- protected control-plane path list
- signed release tags required
- merge queue disabled with personal-repo rationale

Inventory caveat:

- This file is repository evidence of the intended ruleset. It does not prove the ruleset is applied in GitHub.
- `docs/reference/merge-governance.md` still states that repository-tracked CODEOWNERS/ruleset files are absent, which is now stale.

### Workflow permissions and OIDC usage

Active workflow permission posture:

- Most active workflows use `contents: read`.
- `docs-pages.yml` grants `pages: write` and `id-token: write` only for the deploy job.
- `release.yml` uses:
  - top-level `contents: read`
  - `id-token: write` for signing
  - `attestations: write` and `id-token: write` for build provenance
  - `contents: write` only for release publication
- `frontend-nightly.yml` grants `security-events: write` for Scorecard/SARIF upload.

OIDC usage:

- GitHub Pages deployment.
- Release signing with keyless cosign/Sigstore.
- GitHub artifact provenance attestations.
- Inactive `ops/ci` templates also model id-token usage for build/push flows.

### Long-lived secrets and ignored local assets

Repository controls:

- `ops/security/secrets-baseline.toml` defines blocked secret locations and scanner commands.
- Active workflows reference Sentry secrets only in conditional main/push CI paths.
- Release workflow uses GitHub token and OIDC rather than static signing keys.

Ignored local assets observed:

- `ops/cloud/deploy/assets/.env.server_*` are ignored and contain deployment/runtime environment variable names. Values were not recorded in this report.
- GCP/Gonka secret manifest JSON files under `ops/cloud/gcp/**` are ignored.
- `.polisyos/**` is ignored and can contain runtime/security evidence.

Long-lived secret policy signals:

- Docs discourage long-lived cloud access keys and prefer workload identity / managed identity.
- Runtime deploy docs list sensitive variables such as control-plane DSNs, delegation secrets, and LLM gateway API keys.
- Security docs reference signing key paths for local/offline flows, while the release workflow uses keyless signing.

### Dependency update policy

`renovate.json` exists and enables:

- best-practices preset
- dependency dashboard
- scheduled dependency updates
- lockfile maintenance
- vulnerability alerts
- grouped Python tooling updates
- grouped security-sensitive Python runtime dependencies
- grouped frontend tooling updates
- grouped Playwright/Storybook updates
- grouped GitHub Actions updates

### SBOM, provenance, attestations, and signed artifacts

Supply-chain controls:

- `ops/security/sbom.toml` defines CycloneDX JSON SBOM output policy and inputs.
- `frontend-nightly.yml` generates a repository SBOM with Syft and scans with Grype.
- `release.yml` generates release SBOM, scans release assets with Grype, evaluates vulnerability policy, signs release assets with cosign keyless signing, and emits GitHub build provenance attestations.
- `ops/policy/policies/vulnerability.rego` provides deploy/release vulnerability policy.
- Helm policy copies include vulnerability policy material.
- `docs/runbooks/artifact-signing-sbom-failure.md` covers signing, SBOM, and SLSA/provenance incident handling.

Signed artifact expectations:

- Release assets are expected to have `.sig` and `.pem` outputs.
- Release publication includes signed artifacts and provenance evidence.
- Signed release tags are required by the ruleset artifact.

Release security gates:

- Release immutability check.
- Artifact size policy.
- SBOM generation.
- Vulnerability scan.
- Vulnerability policy evaluation.
- Canary validation.
- Keyless signing.
- Build provenance attestation.
- Production release publication after prior gates.

## 7. Wave 1 Decision Inputs

Ops taxonomy:

- Recommended default: `ops/**` is declarative artifact/control-plane state; `tools/ops/**` is executable runner/helper state.
- Explicitly classify `ops/cloud/gcp/**` and `ops/cloud/helm/**/install-*.sh` because they are runner/scripts inside the declarative ops tree.
- Decide whether placeholder duplicates under `ops/deploy` and `tools/ops/deploy` should remain reserved namespaces or be consolidated.

Runtime-state contract:

- Define allowed `.polisyos/**` classes: ephemeral, retained evidence, CAS/blob, local external dataset, secret-bearing local asset, and promotable curated evidence.
- Define retention and backup for `.polisyos/production_data`, `.polisyos/evicted`, `.polisyos/artifacts`, and `.polisyos/runs`.
- Define promotion/redaction rules for `.polisyos/reports`, `.polisyos/audits`, `.polisyos/security`, and smoke/provider verification outputs.

Operability bundle:

- Bundle should include SLO YAML, Prometheus alert/rule files, Grafana dashboards, runbooks, topology mapping, and release evidence templates.
- Decide whether every production alert must carry a direct `runbook_url`.
- Update observability topology inventory to include all dashboards or intentionally exclude non-production dashboards.

Migration contract:

- Keep DB SQL, runtime-state format, API schema, IR schema, and helper CLI migrations as separate contract families.
- Decide which schema snapshots are public compatibility contracts versus generated implementation evidence.
- Decide whether legacy run migration/archive helpers become part of the runtime-state contract.

Release/control-plane:

- Release topology is strongest around GitHub Releases and canary/publish gates.
- Persistent staging topology is not explicit; Wave 1 should decide whether `release-canary` is enough or whether a staged environment manifest is required.
- Control-plane/data-plane/frontend boundaries are identifiable in source, docs, and frontend package layout.

Supply-chain:

- Current controls support SBOM, scan, policy, signing, provenance, and release gates.
- Verify GitHub-side application of `.github/repository-rulesets/main.yml`; repository file alone is not proof.
- Align stale governance docs with actual CODEOWNERS/ruleset artifacts.
- Decide whether ignored local cloud/deploy secret assets should be replaced by documented secret-manager flows.

## Acceptance Check

- Wave 1 has enough inventory data to decide ops taxonomy, runtime-state contract, operability bundle shape, and supply-chain controls.
- No ops paths, rulesets, workflows, or secrets were changed for this phase.
- Only this archived inventory report was added.

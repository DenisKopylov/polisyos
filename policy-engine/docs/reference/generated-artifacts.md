# Generated Artifacts

> Generated from `architecture/generated_artifacts.toml`.
> Regenerate this page with `uv run polisyos-tools architecture guardrails sync`.
> Validate drift with `uv run polisyos-tools architecture guardrails check`.

Every committed generated artifact family must have a source of truth, a regeneration command, a freshness rule, and an approval owner.

| Family | Commit policy | Drift gate | Owner | Outputs |
| --- | --- | --- | --- | --- |
| `ABI schema snapshots` | `committed` | `automated` | `team-polisyos` | `schemas/snapshots/ir`<br/>`schemas/snapshots/fabric/edge_kind.schema.json`<br/>`schemas/snapshots/fabric/node_kind.schema.json`<br/>`schemas/snapshots/fabric/_manifest.json` |
| `Fabric connector contract registry` | `committed` | `automated` | `team-polisyos` | `schemas/snapshots/fabric/connector_contract_registry.json`<br/>`schemas/snapshots/fabric/source_contracts_v2.json`<br/>`schemas/snapshots/fabric/source_scorecards.json` |
| `Runtime OpenAPI snapshot` | `committed` | `automated` | `team-polisyos` | `schemas/runtime_api_v1.openapi.json` |
| `Generated runtime API client` | `committed` | `automated` | `team-polisyos` | `frontend/runtime-api-client/runtimeApiClient.ts`<br/>`frontend/runtime-api-client/runtimeApiClient.js` |
| `Runtime dashboard generated API types` | `committed` | `automated` | `team-polisyos` | `frontend/runtime-dashboard/src/api/types.ts` |
| `Recorded connector fixtures` | `committed` | `manual_review` | `team-polisyos` | `tests/unit/fabric/connectors/sources/fixtures` |
| `Catalog relevant topics domain fixtures` | `committed` | `manual_review` | `team-data-forge` | `src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files` |
| `Runtime dashboard contract fixtures` | `committed` | `manual_review` | `team-polisyos` | `frontend/runtime-dashboard/src/test/contracts/fixtures` |
| `Benchmark reports and bundle stats` | `mixed` | `manual_review` | `team-polisyos` | `benchmarks/_reports`<br/>`_build/frontend/runtime-dashboard/dist/bundle-stats.json` |
| `Audit and evidence artifacts` | `mixed` | `manual_review` | `team-polisyos` | `docs/archive/reports`<br/>`_build/frontend/runtime-dashboard/audit/pnpm-audit-report.json`<br/>`_build/frontend/runtime-dashboard/audit/pnpm-audit-summary.md` |
| `Public surface inventory` | `committed` | `automated` | `team-architecture` | `architecture/public_surface_inventory.json`<br/>`architecture/public_surface` |
| `Release SBOM` | `local_ignored` | `ignored_by_policy` | `team-security` | `_build/release/sbom` |
| `Data Forge migration fixture baselines` | `committed` | `manual_review` | `team-data-forge` | `tests/unit/data_forge/fixtures/non_lex_split`<br/>`tests/unit/data_forge/fixtures/legal_shadow`<br/>`tests/unit/data_forge/fixtures/ukraine_shadow` |
| `Data Forge artifact and manifest contract schemas` | `committed` | `manual_review` | `team-data-forge` | `schemas/artifacts/data_forge_artifact_ref_v1.schema.json`<br/>`schemas/artifacts/data_forge_artifact_trace_metadata_v1.schema.json`<br/>`schemas/artifacts/data_forge_domain_artifact_v1.schema.json`<br/>`schemas/manifests/data_forge_publish_manifest_v1.schema.json`<br/>`schemas/manifests/data_forge_raw_manifest_v1.schema.json`<br/>`schemas/manifests/data_forge_stage_manifest_v1.schema.json` |
| `Frontend workspace lockfile` | `committed` | `manual_review` | `team-frontend` | `pnpm-lock.yaml` |
| `Frontend local generated outputs` | `local_ignored` | `ignored_by_policy` | `team-frontend` | `node_modules`<br/>`frontend/runtime-api-client/node_modules`<br/>`_build/frontend/runtime-api-client/coverage`<br/>`_build/frontend/runtime-api-client/dist`<br/>`_build/frontend/runtime-api-client/.tmp`<br/>`_cache/frontend/runtime-api-client/eslint/.eslintcache`<br/>`frontend/runtime-dashboard/node_modules`<br/>`_build/frontend/runtime-dashboard/coverage`<br/>`_build/frontend/runtime-dashboard/dist`<br/>`_build/frontend/runtime-dashboard/output`<br/>`_build/frontend/runtime-dashboard/playwright-report`<br/>`_build/frontend/runtime-dashboard/storybook-static`<br/>`_build/frontend/runtime-dashboard/test-results`<br/>`_build/frontend/runtime-dashboard/.tmp`<br/>`_cache/frontend/runtime-dashboard/eslint/.eslintcache`<br/>`frontend/runtime-reference-shell/node_modules`<br/>`_build/frontend/runtime-reference-shell/coverage`<br/>`_build/frontend/runtime-reference-shell/dist`<br/>`_build/frontend/runtime-reference-shell/.tmp`<br/>`_cache/frontend/runtime-reference-shell/eslint/.eslintcache`<br/>`packages/cli/node_modules`<br/>`_cache/frontend/cli/eslint/.eslintcache` |
| `Committed data fixtures and catalogs` | `committed` | `manual_review` | `team-data-forge` | `data/academic_gold`<br/>`data/dataset_catalog` |
| `Local medallion data lake` | `local_ignored` | `ignored_by_policy` | `team-data-forge` | `data/bronze`<br/>`data/silver`<br/>`data/gold`<br/>`data/manifests`<br/>`data/quarantine` |
| `Local PolisyOS runtime state` | `local_ignored` | `ignored_by_policy` | `team-platform` | `.polisyos` |
| `Ops observability baselines` | `committed` | `manual_review` | `team-observability` | `ops/observability/otel/baseline.yaml`<br/>`ops/observability/slo`<br/>`ops/observability/prometheus`<br/>`ops/observability/grafana/dashboards` |
| `Ops security and release baselines` | `committed` | `manual_review` | `team-security` | `ops/security/gitleaks.toml`<br/>`ops/security/trufflehog.yaml`<br/>`ops/security/osv-scanner.toml`<br/>`ops/security/sbom.toml`<br/>`ops/security/secrets-baseline.toml`<br/>`ops/release/release-fragment-policy.toml`<br/>`ops/release/commit-policy.toml` |
| `Ops runtime and migration baselines` | `committed` | `manual_review` | `team-platform` | `ops/runtime/runtime-contracts.toml`<br/>`ops/migrations/README.md`<br/>`ops/migrations/migration-contracts.toml`<br/>`ops/migrations/001_tenant_columns.sql`<br/>`ops/migrations/002_tenant_backfill.sql`<br/>`ops/migrations/003_rls_enable.sql`<br/>`ops/migrations/003_rls_disable_rollback.sql`<br/>`ops/migrations/004_roles_grants.sql` |

## `ABI schema snapshots`

- Family id: `abi-schema-snapshots`
- Source of truth: schemas/abi_models.py + src/polisyos/** Pydantic/Enum contracts
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever ABI-visible IR or Fabric contracts change.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `../.github/workflows/abi.yml`
- Outputs:
  - `schemas/snapshots/ir`
  - `schemas/snapshots/fabric/edge_kind.schema.json`
  - `schemas/snapshots/fabric/node_kind.schema.json`
  - `schemas/snapshots/fabric/_manifest.json`

Canonical regeneration commands:

```bash
PYTHONPATH=src:. uv run --extra ml python tools/quality/diagnostics/gen_schema.py
```

## `Fabric connector contract registry`

- Family id: `fabric-connector-contract-registry`
- Source of truth: polisyos.fabric.connectors.sources._contracts.ALL_SOURCE_CONTRACTS and tools/quality/validation/fabric_schema_governance.py
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever source connector contracts or their governance metadata change.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `tools/ci/check_fabric_schema_registry.py`
- Outputs:
  - `schemas/snapshots/fabric/connector_contract_registry.json`
  - `schemas/snapshots/fabric/source_contracts_v2.json`
  - `schemas/snapshots/fabric/source_scorecards.json`

Canonical regeneration commands:

```bash
uv run python tools/ci/check_fabric_schema_registry.py --update
```

## `Runtime OpenAPI snapshot`

- Family id: `runtime-openapi-snapshot`
- Source of truth: src/polisyos/runtime/http/** FastAPI app factory and DTO contracts
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime routes, request/response DTOs, or OpenAPI examples change.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `schemas/runtime_api_v1.openapi.json`

Canonical regeneration commands:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

## `Generated runtime API client`

- Family id: `runtime-api-client`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever the runtime OpenAPI snapshot changes.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `frontend/runtime-api-client/runtimeApiClient.ts`
  - `frontend/runtime-api-client/runtimeApiClient.js`

Canonical regeneration commands:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts frontend/runtime-api-client/runtimeApiClient.ts --out-js frontend/runtime-api-client/runtimeApiClient.js
```

## `Runtime dashboard generated API types`

- Family id: `runtime-dashboard-api-types`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime OpenAPI changes affect dashboard-facing types.
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `frontend/runtime-dashboard/src/api/types.ts`

Canonical regeneration commands:

```bash
pnpm --filter @polisyos/runtime-dashboard run generate:api
```

## `Recorded connector fixtures`

- Family id: `connector-recorded-fixtures`
- Source of truth: Live upstream connector responses captured through polisyos-tools data record-fixtures.
- Commit policy: `committed`
- Freshness rule: Refresh intentionally when connector contracts, source profiles, or upstream response shapes change.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `tools/ops/data/record_fixtures.py`
- Outputs:
  - `tests/unit/fabric/connectors/sources/fixtures`

Canonical regeneration commands:

```bash
uv run polisyos-tools data record-fixtures --wave 1
uv run polisyos-tools data record-fixtures --wave 2
uv run polisyos-tools data record-fixtures --wave 3
```

## `Catalog relevant topics domain fixtures`

- Family id: `catalog-relevant-topics-domain-fixtures`
- Source of truth: OpenAlex topic CSV curation via tools/research/experiments/filter_topics.py and tools/research/experiments/organize_relevant_topics.py
- Commit policy: `committed`
- Freshness rule: Refresh only when topic taxonomy fixtures are intentionally regenerated and reviewed.
- Drift gate: `manual_review`
- Owner: `team-data-forge`
- Approval owner: `team-data-forge`
- Outputs:
  - `src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files`

Canonical regeneration commands:

```bash
uv run python tools/research/experiments/filter_topics.py --input <approved-openalex-topics.csv> --output <workdir>/relevant_topics.csv
uv run python tools/research/experiments/organize_relevant_topics.py --input <workdir>/relevant_topics.csv --labeled-output <workdir>/relevant_topics_thematic.csv --summary-output src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files/relevant_topics_thematic_summary.csv
```

## `Runtime dashboard contract fixtures`

- Family id: `runtime-dashboard-contract-fixtures`
- Source of truth: Live Runtime API responses captured via frontend/runtime-dashboard/scripts/record-runtime-contracts.mjs
- Commit policy: `committed`
- Freshness rule: Refresh when dashboard contract fixtures are intentionally updated to match runtime API behavior.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `frontend/runtime-dashboard/scripts/record-runtime-contracts.mjs`
- Outputs:
  - `frontend/runtime-dashboard/src/test/contracts/fixtures`

Canonical regeneration commands:

```bash
pnpm --filter @polisyos/runtime-dashboard run contracts:record
```

## `Benchmark reports and bundle stats`

- Family id: `benchmark-reports-and-bundle-stats`
- Source of truth: benchmarks/** runners, frontend/runtime-dashboard/scripts/emit-bundle-stats.mjs, and benchmark publication helpers
- Commit policy: `mixed`
- Freshness rule: Commit benchmark reports only when they serve as intentional baselines, evidence packs, or review artifacts. `_build/frontend/runtime-dashboard/dist/bundle-stats.json` is local by default and is committed only when reviewers explicitly want a checked-in bundle baseline.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/perf.yml`
- Outputs:
  - `benchmarks/_reports`
  - `_build/frontend/runtime-dashboard/dist/bundle-stats.json`

Canonical regeneration commands:

```bash
uv run polisyos-tools benchmarks run-all
pnpm --filter @polisyos/runtime-dashboard run bundle:stats
```

## `Audit and evidence artifacts`

- Family id: `audit-and-evidence-artifacts`
- Source of truth: Dedicated audit/report generators such as frontend/runtime-dashboard/scripts/run-audit.mjs and curated evidence/report pipelines
- Commit policy: `mixed`
- Freshness rule: Only intentionally reviewed evidence packs stay committed; frontend audit outputs stay local under `_build/frontend/runtime-dashboard/audit/` unless promoted to a reviewed baseline.
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `frontend/runtime-dashboard/scripts/run-audit.mjs`
- Outputs:
  - `docs/archive/reports`
  - `_build/frontend/runtime-dashboard/audit/pnpm-audit-report.json`
  - `_build/frontend/runtime-dashboard/audit/pnpm-audit-summary.md`

Canonical regeneration commands:

```bash
pnpm --filter @polisyos/runtime-dashboard run audit:ci
```

## `Public surface inventory`

- Family id: `public-surface-inventory`
- Source of truth: architecture/public_surface.toml and src/polisyos/**/__init__.py public exports
- Commit policy: `committed`
- Freshness rule: Regenerate whenever supported public entrypoints, __all__, or public signatures change.
- Drift gate: `automated`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `architecture/public_surface_inventory.json`
  - `architecture/public_surface`

Canonical regeneration commands:

```bash
uv run polisyos-tools quality public-surface snapshot --all
```

## `Release SBOM`

- Family id: `release-sbom`
- Source of truth: uv.lock, pnpm-lock.yaml, Dockerfile.reproducible, and release manifest inputs
- Commit policy: `local_ignored`
- Freshness rule: Regenerate for every release candidate or dependency-lock change; publish through CI/release artifacts rather than committing local SBOM output.
- Drift gate: `ignored_by_policy`
- Owner: `team-security`
- Approval owner: `team-security`
- Related workflow/config: `ops/ci/templates/workflows/build-and-push.yml`
- Outputs:
  - `_build/release/sbom`

Canonical regeneration commands:

```bash
uv run polisyos-tools security sbom --output _build/release/sbom/
```

## `Data Forge migration fixture baselines`

- Family id: `data-forge-migration-fixture-baselines`
- Source of truth: tests/unit/data_forge/** golden, shadow, replay, and differential fixture contracts
- Commit policy: `committed`
- Freshness rule: Refresh when Data Forge behavior-changing migrations intentionally update golden, replay, shadow, or differential baselines.
- Drift gate: `manual_review`
- Owner: `team-data-forge`
- Approval owner: `team-architecture`
- Related workflow/config: `tests/unit/data_forge`
- Outputs:
  - `tests/unit/data_forge/fixtures/non_lex_split`
  - `tests/unit/data_forge/fixtures/legal_shadow`
  - `tests/unit/data_forge/fixtures/ukraine_shadow`

Canonical regeneration commands:

```bash
manual review: refresh paired baseline/candidate fixtures and run uv run pytest tests/unit/data_forge/test_phase1_shared_kernel_cutover.py tests/unit/data_forge/test_phase7_schema_quality_observability.py tests/unit/data_forge/test_repository_sota_phase1_foundation.py -q
```

## `Data Forge artifact and manifest contract schemas`

- Family id: `data-forge-contract-schemas`
- Source of truth: src/polisyos/data_forge/kernel/** ArtifactRef, trace metadata, domain artifact, and manifest contracts
- Commit policy: `committed`
- Freshness rule: Review whenever Data Forge ArtifactRef, trace metadata, domain artifact, raw/stage/publish manifest, or publish-manifest contracts change.
- Drift gate: `manual_review`
- Owner: `team-data-forge`
- Approval owner: `team-architecture`
- Related workflow/config: `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`
- Outputs:
  - `schemas/artifacts/data_forge_artifact_ref_v1.schema.json`
  - `schemas/artifacts/data_forge_artifact_trace_metadata_v1.schema.json`
  - `schemas/artifacts/data_forge_domain_artifact_v1.schema.json`
  - `schemas/manifests/data_forge_publish_manifest_v1.schema.json`
  - `schemas/manifests/data_forge_raw_manifest_v1.schema.json`
  - `schemas/manifests/data_forge_stage_manifest_v1.schema.json`

Canonical regeneration commands:

```bash
manual review: update JSON Schema alongside Data Forge kernel manifest/model changes
```

## `Frontend workspace lockfile`

- Family id: `frontend-workspace-lockfiles`
- Source of truth: pnpm-workspace.yaml, package.json, frontend/*/package.json, packages/*/package.json, and the Node 22 contributor baseline
- Commit policy: `committed`
- Freshness rule: Regenerate and commit the root pnpm lockfile whenever any workspace package dependency graph changes.
- Drift gate: `manual_review`
- Owner: `team-frontend`
- Approval owner: `team-frontend`
- Related workflow/config: `../.github/workflows/frontend-quality.yml`
- Outputs:
  - `pnpm-lock.yaml`

Canonical regeneration commands:

```bash
pnpm install --lockfile-only
```

## `Frontend local generated outputs`

- Family id: `frontend-local-generated-outputs`
- Source of truth: frontend workspace build, coverage, audit, Playwright, Storybook, cache, and package manager commands
- Commit policy: `local_ignored`
- Freshness rule: Keep local generated outputs ignored. Commit only explicit reviewed baselines registered in a committed artifact family.
- Drift gate: `ignored_by_policy`
- Owner: `team-frontend`
- Approval owner: `team-frontend`
- Related workflow/config: `docs/reference/frontend/workspace-contract.md`
- Outputs:
  - `node_modules`
  - `frontend/runtime-api-client/node_modules`
  - `_build/frontend/runtime-api-client/coverage`
  - `_build/frontend/runtime-api-client/dist`
  - `_build/frontend/runtime-api-client/.tmp`
  - `_cache/frontend/runtime-api-client/eslint/.eslintcache`
  - `frontend/runtime-dashboard/node_modules`
  - `_build/frontend/runtime-dashboard/coverage`
  - `_build/frontend/runtime-dashboard/dist`
  - `_build/frontend/runtime-dashboard/output`
  - `_build/frontend/runtime-dashboard/playwright-report`
  - `_build/frontend/runtime-dashboard/storybook-static`
  - `_build/frontend/runtime-dashboard/test-results`
  - `_build/frontend/runtime-dashboard/.tmp`
  - `_cache/frontend/runtime-dashboard/eslint/.eslintcache`
  - `frontend/runtime-reference-shell/node_modules`
  - `_build/frontend/runtime-reference-shell/coverage`
  - `_build/frontend/runtime-reference-shell/dist`
  - `_build/frontend/runtime-reference-shell/.tmp`
  - `_cache/frontend/runtime-reference-shell/eslint/.eslintcache`
  - `packages/cli/node_modules`
  - `_cache/frontend/cli/eslint/.eslintcache`

Canonical regeneration commands:

```bash
pnpm --filter @polisyos/runtime-dashboard run build
pnpm --filter @polisyos/runtime-dashboard run test:coverage
pnpm --filter @polisyos/runtime-dashboard run build-storybook
```

## `Committed data fixtures and catalogs`

- Family id: `committed-data-fixtures-and-catalogs`
- Source of truth: data/README.md, data/academic_gold/** tiny examples, and data/dataset_catalog/*.yaml registry entries
- Commit policy: `committed`
- Freshness rule: Commit only small fixtures, contracts, manifests, registry entries, or tiny gold examples. Bulk raw/curated/database outputs remain ignored local data.
- Drift gate: `manual_review`
- Owner: `team-data-forge`
- Approval owner: `team-data-forge`
- Related workflow/config: `docs/reference/data-lake-policy.md`
- Outputs:
  - `data/academic_gold`
  - `data/dataset_catalog`

Canonical regeneration commands:

```bash
manual review: refresh tiny gold fixtures or catalog YAML alongside the source schema/contract change
```

## `Local medallion data lake`

- Family id: `local-medallion-data-lake`
- Source of truth: architecture/data_policy.toml
- Commit policy: `local_ignored`
- Freshness rule: Local data lake content is local runtime or corpus state and must stay ignored unless promoted to a registered tiny fixture.
- Drift gate: `ignored_by_policy`
- Owner: `team-data-forge`
- Approval owner: `team-data-forge`
- Related workflow/config: `docs/reference/data-lake-policy.md`
- Outputs:
  - `data/bronze`
  - `data/silver`
  - `data/gold`
  - `data/manifests`
  - `data/quarantine`

Canonical regeneration commands:

```bash
manual/local: create medallion directories under the ignored product-root data/ lake as needed
```

## `Local PolisyOS runtime state`

- Family id: `local-runtime-state`
- Source of truth: architecture/local_runtime_state.toml
- Commit policy: `local_ignored`
- Freshness rule: Keep runtime state ignored, retention-classed, and cleanable through the documented cleanup commands.
- Drift gate: `ignored_by_policy`
- Owner: `team-platform`
- Approval owner: `team-platform`
- Related workflow/config: `docs/reference/local-runtime-state.md`
- Outputs:
  - `.polisyos`

Canonical regeneration commands:

```bash
manual/local: runtime runs, reports, artifact-cache, and provider-verification commands create .polisyos state
```

## `Ops observability baselines`

- Family id: `ops-observability-baselines`
- Source of truth: ops/observability, ops/observability/prometheus, ops/observability/grafana, and runtime telemetry conventions
- Commit policy: `committed`
- Freshness rule: Review whenever runtime metrics, trace attributes, SLO objectives, or dashboard panels change.
- Drift gate: `manual_review`
- Owner: `team-observability`
- Approval owner: `team-platform`
- Related workflow/config: `../.github/workflows/core-runtime-release-gate.yml`
- Outputs:
  - `ops/observability/otel/baseline.yaml`
  - `ops/observability/slo`
  - `ops/observability/prometheus`
  - `ops/observability/grafana/dashboards`

Canonical regeneration commands:

```bash
docker compose -f ops/docker/observability.compose.yml config
manual review: update OTel, SLO, Prometheus, and Grafana baselines together with emitted telemetry changes
```

## `Ops security and release baselines`

- Family id: `ops-security-release-baselines`
- Source of truth: ops/security, ops/release, release-fragments, dependency locks, and Dockerfile.reproducible
- Commit policy: `committed`
- Freshness rule: Review whenever secret scanning policy, dependency lock inputs, SBOM format, release-fragment rules, or commit policy changes.
- Drift gate: `manual_review`
- Owner: `team-security`
- Approval owner: `team-platform`
- Related workflow/config: `../.github/workflows/release.yml`
- Outputs:
  - `ops/security/gitleaks.toml`
  - `ops/security/trufflehog.yaml`
  - `ops/security/osv-scanner.toml`
  - `ops/security/sbom.toml`
  - `ops/security/secrets-baseline.toml`
  - `ops/release/release-fragment-policy.toml`
  - `ops/release/commit-policy.toml`

Canonical regeneration commands:

```bash
manual review: run gitleaks, trufflehog, OSV, SBOM, release-fragment, and commit-policy checks for release candidates
```

## `Ops runtime and migration baselines`

- Family id: `ops-runtime-and-migration-baselines`
- Source of truth: ops/runtime, ops/migrations, runtime deployment contracts, and tenant/RLS SQL chain
- Commit policy: `committed`
- Freshness rule: Review whenever runtime deployment contracts, tenant isolation, RLS, rollback, or migration sequencing changes.
- Drift gate: `manual_review`
- Owner: `team-platform`
- Approval owner: `team-platform`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `ops/runtime/runtime-contracts.toml`
  - `ops/migrations/README.md`
  - `ops/migrations/migration-contracts.toml`
  - `ops/migrations/001_tenant_columns.sql`
  - `ops/migrations/002_tenant_backfill.sql`
  - `ops/migrations/003_rls_enable.sql`
  - `ops/migrations/003_rls_disable_rollback.sql`
  - `ops/migrations/004_roles_grants.sql`

Canonical regeneration commands:

```bash
manual review: update runtime and SQL migration baselines alongside deployment/runtime security contract changes
```

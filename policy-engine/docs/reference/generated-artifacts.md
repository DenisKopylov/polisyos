# Generated Artifacts

> Generated from `architecture/generated_artifacts.toml`.
> Regenerate this page with `uv run polisyos-tools architecture guardrails sync`.
> Validate drift with `uv run polisyos-tools architecture guardrails check`.

Every committed generated artifact family must have a source of truth, a regeneration command, a freshness rule, and an approval owner.

| Family | Lifecycle | Commit policy | Drift gate | Owner | Outputs |
| --- | --- | --- | --- | --- | --- |
| `ABI schema snapshots` | `generated_committed` | `committed` | `automated` | `team-polisyos` | `schemas/snapshots/ir`<br/>`schemas/snapshots/fabric/edge_kind.schema.json`<br/>`schemas/snapshots/fabric/node_kind.schema.json`<br/>`schemas/snapshots/fabric/_manifest.json` |
| `Fabric connector contract registry` | `generated_committed` | `committed` | `automated` | `team-polisyos` | `schemas/snapshots/fabric/connector_contract_registry.json`<br/>`schemas/snapshots/fabric/source_contracts_v2.json`<br/>`schemas/snapshots/fabric/source_scorecards.json` |
| `Runtime OpenAPI snapshot` | `generated_committed` | `committed` | `automated` | `team-polisyos` | `schemas/runtime_api_v1.openapi.json` |
| `Generated runtime API client` | `generated_committed` | `committed` | `automated` | `team-polisyos` | `packages/runtime-api-client/runtimeApiClient.ts`<br/>`packages/runtime-api-client/runtimeApiClient.js` |
| `Runtime dashboard generated API types` | `generated_committed` | `committed` | `automated` | `team-polisyos` | `apps/runtime-dashboard/src/api/types.ts` |
| `Recorded connector fixtures` | `generated_committed` | `committed` | `manual_review` | `team-polisyos` | `tests/_data/fabric/connectors/sources` |
| `Catalog relevant topics domain fixtures` | `generated_committed` | `committed` | `manual_review` | `team-data-forge` | `src/polisyos/data_forge/domains/catalog/fixtures/relevant_topics_domain_files` |
| `Runtime dashboard contract fixtures` | `generated_committed` | `committed` | `manual_review` | `team-polisyos` | `apps/runtime-dashboard/src/test/contracts/fixtures` |
| `Benchmark reports and bundle stats` | `generated_ignored` | `mixed` | `manual_review` | `team-polisyos` | `benchmarks/_reports`<br/>`_build/apps/runtime-dashboard/dist/bundle-stats.json` |
| `Audit and evidence artifacts` | `generated_ignored` | `mixed` | `manual_review` | `team-polisyos` | `docs/archive/reports`<br/>`_build/apps/runtime-dashboard/audit/pnpm-audit-report.json`<br/>`_build/apps/runtime-dashboard/audit/pnpm-audit-summary.md` |
| `Public surface inventory` | `generated_committed` | `committed` | `automated` | `team-architecture` | `architecture/public_surface/inventory.json`<br/>`architecture/public_surface` |
| `Architecture package contract aggregate mirrors` | `generated_committed` | `committed` | `automated_report_only` | `team-architecture` | `architecture/packages/boundaries.toml`<br/>`architecture/packages/layout.toml`<br/>`architecture/public_surface/contract.toml`<br/>`architecture/tests/topology.toml` |
| `Architecture report-only contract reports` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-architecture` | `_build/reports/architecture` |
| `Architecture import-boundary and dependency-graph reports` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-architecture` | `_build/reports/architecture/import-boundary-report.json`<br/>`_build/reports/architecture/dependency-graph-report.json`<br/>`_build/reports/architecture/dynamic-import-registry-report.json`<br/>`_build/reports/architecture/phase6-1-package-import-gates.json` |
| `Architecture mypy and Ruff override report` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-architecture` | `_build/reports/architecture/static-analysis-overrides.json` |
| `Generated mypy, Ruff, and MkDocs configs` | `generated_committed` | `committed_generated` | `uv run polisyos-tools workspace tool-configs --check` | `team-devx` | `architecture/tooling/mypy/generated.ini`<br/>`architecture/tooling/ruff/generated.toml`<br/>`architecture/tooling/mkdocs/generated.yml`<br/>`mypy.ini`<br/>`ruff.toml`<br/>`mkdocs.yml` |
| `Release inputs and unreleased fragments` | `source_committed` | `committed` | `automated` | `team-release` | `release`<br/>`release-fragments/README.md`<br/>`release-fragments/template.toml`<br/>`release-fragments/unreleased` |
| `Release build output staging` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-release` | `_build/release`<br/>`_build/release-fragments` |
| `Local build cache and scratch` | `scratch_ignored` | `local_ignored` | `ignored_by_policy` | `team-devx` | `_build/scratch`<br/>`_build/.tmp`<br/>`_cache` |
| `Wrong-root cache and tmp residue` | `scratch_ignored` | `local_ignored` | `ignored_by_policy` | `team-devx` | `../_build`<br/>`../_cache`<br/>`../tmp`<br/>`../.tmp_*` |
| `Release SBOM` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-security` | `_build/release/sbom` |
| `Supply-chain control crosswalk` | `generated_committed` | `committed` | `automated` | `team-security` | `docs/archive/reports/supply-chain-control-crosswalk.json` |
| `Release build/cache cleanup command` | `scratch_ignored` | `local_ignored` | `automated` | `team-devx` | `_build/scratch`<br/>`_cache`<br/>`../_cache`<br/>`../tmp` |
| `Data Forge migration fixture baselines` | `generated_committed` | `committed` | `manual_review` | `team-data-forge` | `tests/_data/data_forge/non_lex_split`<br/>`tests/_data/data_forge/legal_shadow`<br/>`tests/_data/data_forge/ukraine_shadow` |
| `Data Forge artifact and manifest contract schemas` | `generated_committed` | `committed` | `manual_review` | `team-data-forge` | `schemas/artifacts/data_forge_artifact_ref_v1.schema.json`<br/>`schemas/artifacts/data_forge_artifact_trace_metadata_v1.schema.json`<br/>`schemas/artifacts/data_forge_domain_artifact_v1.schema.json`<br/>`schemas/manifests/data_forge_publish_manifest_v1.schema.json`<br/>`schemas/manifests/data_forge_raw_manifest_v1.schema.json`<br/>`schemas/manifests/data_forge_stage_manifest_v1.schema.json` |
| `Frontend workspace lockfile` | `generated_committed` | `committed` | `manual_review` | `team-frontend` | `pnpm-lock.yaml` |
| `Frontend local generated outputs` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-frontend` | `node_modules`<br/>`packages/runtime-api-client/node_modules`<br/>`_build/packages/runtime-api-client/coverage`<br/>`_build/packages/runtime-api-client/dist`<br/>`_build/packages/runtime-api-client/.tmp`<br/>`_cache/packages/runtime-api-client/eslint/.eslintcache`<br/>`apps/runtime-dashboard/node_modules`<br/>`_build/apps/runtime-dashboard/coverage`<br/>`_build/apps/runtime-dashboard/dist`<br/>`_build/apps/runtime-dashboard/output`<br/>`_build/apps/runtime-dashboard/playwright-report`<br/>`_build/apps/runtime-dashboard/storybook-static`<br/>`_build/apps/runtime-dashboard/test-results`<br/>`_build/apps/runtime-dashboard/.tmp`<br/>`_cache/apps/runtime-dashboard/eslint/.eslintcache`<br/>`apps/runtime-reference-shell/node_modules`<br/>`_build/apps/runtime-reference-shell/coverage`<br/>`_build/apps/runtime-reference-shell/dist`<br/>`_build/apps/runtime-reference-shell/.tmp`<br/>`_cache/apps/runtime-reference-shell/eslint/.eslintcache`<br/>`packages/cli/node_modules`<br/>`_cache/packages/cli/eslint/.eslintcache` |
| `Committed data fixtures and catalogs` | `source_committed` | `committed` | `manual_review` | `team-data-forge` | `data/academic_gold`<br/>`data/dataset_catalog` |
| `Local medallion data lake` | `generated_ignored` | `local_ignored` | `ignored_by_policy` | `team-data-forge` | `data/bronze`<br/>`data/silver`<br/>`data/gold`<br/>`data/manifests`<br/>`data/quarantine` |
| `Local PolisyOS runtime state` | `runtime_ignored` | `local_ignored` | `ignored_by_policy` | `team-platform` | `.polisyos` |
| `Ops observability baselines` | `source_committed` | `committed` | `manual_review` | `team-observability` | `ops/observability/otel/baseline.yaml`<br/>`ops/observability/slo`<br/>`ops/observability/prometheus`<br/>`ops/observability/grafana/dashboards` |
| `Ops security and release baselines` | `source_committed` | `committed` | `manual_review` | `team-security` | `ops/security/gitleaks.toml`<br/>`ops/security/trufflehog.yaml`<br/>`ops/security/osv-scanner.toml`<br/>`ops/security/sbom.toml`<br/>`ops/security/secrets-baseline.toml`<br/>`ops/release/release-fragment-policy.toml`<br/>`ops/release/commit-policy.toml`<br/>`ops/release/deployment-topology.toml`<br/>`ops/release/promotion-gates.toml` |
| `Ops runtime and migration baselines` | `source_committed` | `committed` | `manual_review` | `team-platform` | `ops/runtime/runtime-contracts.toml`<br/>`ops/migrations/README.md`<br/>`ops/migrations/migration-contracts.toml`<br/>`ops/migrations/db/README.md`<br/>`ops/migrations/db/001_tenant_columns.sql`<br/>`ops/migrations/db/002_tenant_backfill.sql`<br/>`ops/migrations/db/003_rls_enable.sql`<br/>`ops/migrations/db/003_rls_disable_rollback.sql`<br/>`ops/migrations/db/004_roles_grants.sql`<br/>`ops/migrations/runtime_state/README.md`<br/>`ops/migrations/api_schemas/README.md`<br/>`ops/migrations/ir/README.md` |

## `ABI schema snapshots`

- Family id: `abi-schema-snapshots`
- Lifecycle: `generated_committed`
- Source of truth: src/polisyos/schemas/abi_models.py + src/polisyos/** Pydantic/Enum contracts
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever ABI-visible IR or Fabric contracts change.
- Stale output behavior: `fail`
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
uv run --extra ml polisyos-tools diagnostics gen-schema
```

## `Fabric connector contract registry`

- Family id: `fabric-connector-contract-registry`
- Lifecycle: `generated_committed`
- Source of truth: polisyos.fabric.connectors.sources._contracts.ALL_SOURCE_CONTRACTS and tools/quality/validation/fabric_schema_governance.py
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever source connector contracts or their governance metadata change.
- Stale output behavior: `fail`
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
- Lifecycle: `generated_committed`
- Source of truth: src/polisyos/runtime/http/** FastAPI app factory and DTO contracts
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime routes, request/response DTOs, or OpenAPI examples change.
- Stale output behavior: `fail`
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `schemas/runtime_api_v1.openapi.json`

Canonical regeneration commands:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
```

## `Generated runtime API client`

- Family id: `runtime-api-client`
- Lifecycle: `generated_committed`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever the runtime OpenAPI snapshot changes.
- Stale output behavior: `fail`
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `packages/runtime-api-client/runtimeApiClient.ts`
  - `packages/runtime-api-client/runtimeApiClient.js`

Canonical regeneration commands:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/generate_runtime_client.py --openapi schemas/runtime_api_v1.openapi.json --out-ts packages/runtime-api-client/runtimeApiClient.ts --out-js packages/runtime-api-client/runtimeApiClient.js
```

## `Runtime dashboard generated API types`

- Family id: `runtime-dashboard-api-types`
- Lifecycle: `generated_committed`
- Source of truth: schemas/runtime_api_v1.openapi.json
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever runtime OpenAPI changes affect dashboard-facing types.
- Stale output behavior: `fail`
- Drift gate: `automated`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `apps/runtime-dashboard/src/api/types.ts`

Canonical regeneration commands:

```bash
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api
```

## `Recorded connector fixtures`

- Family id: `connector-recorded-fixtures`
- Lifecycle: `generated_committed`
- Source of truth: Live upstream connector responses captured through polisyos-tools data record-fixtures.
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Refresh intentionally when connector contracts, source profiles, or upstream response shapes change.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `tools/ops_runners/data/record_fixtures.py`
- Outputs:
  - `tests/_data/fabric/connectors/sources`

Canonical regeneration commands:

```bash
uv run polisyos-tools data record-fixtures --wave 1
uv run polisyos-tools data record-fixtures --wave 2
uv run polisyos-tools data record-fixtures --wave 3
```

## `Catalog relevant topics domain fixtures`

- Family id: `catalog-relevant-topics-domain-fixtures`
- Lifecycle: `generated_committed`
- Source of truth: OpenAlex topic CSV curation via tools/research/experiments/filter_topics.py and tools/research/experiments/organize_relevant_topics.py
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Refresh only when topic taxonomy fixtures are intentionally regenerated and reviewed.
- Stale output behavior: `warn`
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
- Lifecycle: `generated_committed`
- Source of truth: Live Runtime API responses captured via apps/runtime-dashboard/scripts/record-runtime-contracts.mjs
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Refresh when dashboard contract fixtures are intentionally updated to match runtime API behavior.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `apps/runtime-dashboard/scripts/record-runtime-contracts.mjs`
- Outputs:
  - `apps/runtime-dashboard/src/test/contracts/fixtures`

Canonical regeneration commands:

```bash
corepack pnpm --filter @polisyos/runtime-dashboard run contracts:record
```

## `Benchmark reports and bundle stats`

- Family id: `benchmark-reports-and-bundle-stats`
- Lifecycle: `generated_ignored`
- Source of truth: benchmarks/** runners, apps/runtime-dashboard/scripts/emit-bundle-stats.mjs, and benchmark publication helpers
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/benchmarks/ or architecture/generated_artifacts.toml when promoted as reviewed evidence
- Commit policy: `mixed`
- Freshness rule: Commit benchmark reports only when they serve as intentional baselines, evidence packs, or review artifacts. `_build/apps/runtime-dashboard/dist/bundle-stats.json` is local by default and is committed only when reviewers explicitly want a checked-in bundle baseline.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `ops/ci/templates/workflows/perf.yml`
- Outputs:
  - `benchmarks/_reports`
  - `_build/apps/runtime-dashboard/dist/bundle-stats.json`

Canonical regeneration commands:

```bash
uv run polisyos-tools benchmarks run-all
corepack pnpm --filter @polisyos/runtime-dashboard run bundle:stats
```

## `Audit and evidence artifacts`

- Family id: `audit-and-evidence-artifacts`
- Lifecycle: `generated_ignored`
- Source of truth: Dedicated audit/report generators such as apps/runtime-dashboard/scripts/run-audit.mjs and curated evidence/report pipelines
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/ after review and redaction
- Commit policy: `mixed`
- Freshness rule: Only intentionally reviewed evidence packs stay committed; frontend audit outputs stay local under `_build/apps/runtime-dashboard/audit/` unless promoted to a reviewed baseline.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-polisyos`
- Approval owner: `team-polisyos`
- Related workflow/config: `apps/runtime-dashboard/scripts/run-audit.mjs`
- Outputs:
  - `docs/archive/reports`
  - `_build/apps/runtime-dashboard/audit/pnpm-audit-report.json`
  - `_build/apps/runtime-dashboard/audit/pnpm-audit-summary.md`

Canonical regeneration commands:

```bash
corepack pnpm --filter @polisyos/runtime-dashboard run audit:ci
```

## `Public surface inventory`

- Family id: `public-surface-inventory`
- Lifecycle: `generated_committed`
- Source of truth: architecture/public_surface/contract.toml and src/polisyos/**/__init__.py public exports
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate whenever supported public entrypoints, __all__, or public signatures change.
- Stale output behavior: `fail`
- Drift gate: `automated`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `architecture/public_surface/inventory.json`
  - `architecture/public_surface`

Canonical regeneration commands:

```bash
uv run polisyos-tools quality public-surface snapshot --all
```

## `Architecture package contract aggregate mirrors`

- Family id: `architecture-package-contract-aggregates`
- Lifecycle: `generated_committed`
- Source of truth: architecture/packages/*.toml
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Update or generate aggregate mirrors whenever a package contract changes package boundaries, layout, public surface, or test expectations.
- Stale output behavior: `warn`
- Drift gate: `automated_report_only`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `tools/quality/validation/architecture_report_only_contracts.py`
- Outputs:
  - `architecture/packages/boundaries.toml`
  - `architecture/packages/layout.toml`
  - `architecture/public_surface/contract.toml`
  - `architecture/tests/topology.toml`

Canonical regeneration commands:

```bash
mirror package-contract changes into legacy aggregate TOML until the aggregate generator replaces hand-edits
uv run python tools/quality/validation/architecture_report_only_contracts.py --report package-mirrors --fail-on-contract-errors
```

## `Architecture report-only contract reports`

- Family id: `architecture-report-only-contract-reports`
- Lifecycle: `generated_ignored`
- Source of truth: architecture/gates/report_only.toml and architecture/*_*.toml report-only contracts
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/architecture/ when reviewed as durable evidence
- Commit policy: `local_ignored`
- Freshness rule: Generate report-only evidence locally or in CI before promoting any Phase 1.3 gate to fail-closed.
- Stale output behavior: `ignored_by_policy`
- Drift gate: `ignored_by_policy`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `tools/quality/validation/architecture_report_only_contracts.py`
- Outputs:
  - `_build/reports/architecture`

Canonical regeneration commands:

```bash
uv run python tools/quality/validation/architecture_report_only_contracts.py --json-output _build/reports/architecture/phase1_3_report_only_contracts.json
```

## `Architecture import-boundary and dependency-graph reports`

- Family id: `architecture-import-dependency-reports`
- Lifecycle: `generated_ignored`
- Source of truth: architecture/imports/reports.toml, architecture/imports/contracts.toml, architecture/imports/policy.toml, architecture/imports/exceptions.toml, architecture/baselines/imports/deep_import.json, architecture/imports/dynamic.toml, architecture/imports/lazy.toml, architecture/packages/boundaries.toml, architecture/packages/layout.toml, architecture/public_surface/contract.toml, architecture/public_surface/inventory.json, architecture/name_registry.toml, and architecture/shims.toml
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/architecture/ when reviewed as durable evidence
- Commit policy: `local_ignored`
- Freshness rule: Regenerate when import policies, package boundaries, dynamic imports, or deep-import baselines change.
- Stale output behavior: `ignored_by_policy`
- Drift gate: `ignored_by_policy`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `tools/quality/validation/architecture_report_only_contracts.py`
- Outputs:
  - `_build/reports/architecture/import-boundary-report.json`
  - `_build/reports/architecture/dependency-graph-report.json`
  - `_build/reports/architecture/dynamic-import-registry-report.json`
  - `_build/reports/architecture/phase6-1-package-import-gates.json`

Canonical regeneration commands:

```bash
uv run python tools/quality/validation/architecture_report_only_contracts.py --report dependency-graph --json-output _build/reports/architecture/import-boundary-report.json
uv run python tools/quality/validation/architecture_report_only_contracts.py --report dependency-graph --json-output _build/reports/architecture/dependency-graph-report.json
uv run python tools/quality/validation/architecture_report_only_contracts.py --report dynamic-imports --json-output _build/reports/architecture/dynamic-import-registry-report.json
uv run python tools/quality/validation/architecture_report_only_contracts.py --report phase6-1 --json-output _build/reports/architecture/phase6-1-package-import-gates.json
```

## `Architecture mypy and Ruff override report`

- Family id: `architecture-static-analysis-override-report`
- Lifecycle: `generated_ignored`
- Source of truth: architecture/tooling/static_analysis_overrides.toml, architecture/tooling/tool_config_split.toml, architecture/tooling/mypy/generated.ini, architecture/tooling/ruff/generated.toml, and inline noqa/type-ignore comments
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/architecture/ when reviewed as durable evidence
- Commit policy: `local_ignored`
- Freshness rule: Run `uv run polisyos-tools workspace tool-configs --check` before shrinking or promoting mypy/Ruff override ratchets.
- Stale output behavior: `ignored_by_policy`
- Drift gate: `ignored_by_policy`
- Owner: `team-architecture`
- Approval owner: `team-architecture`
- Related workflow/config: `tools/quality/validation/architecture_report_only_contracts.py`
- Outputs:
  - `_build/reports/architecture/static-analysis-overrides.json`

Canonical regeneration commands:

```bash
uv run python tools/quality/validation/architecture_report_only_contracts.py --report static-analysis-overrides --json-output _build/reports/architecture/static-analysis-overrides.json
```

## `Generated mypy, Ruff, and MkDocs configs`

- Family id: `tool-config-split-generated-configs`
- Lifecycle: `generated_committed`
- Source of truth: architecture/tooling/tool_config_split.toml and architecture/tooling/{mypy,ruff,mkdocs}/** source fragments
- Generator: uv run polisyos-tools workspace tool-configs
- Verifier: uv run polisyos-tools workspace tool-configs --check
- Promotion target: committed generated operational tool configs
- Commit policy: `committed_generated`
- Freshness rule: Regenerate whenever any tool-config fragment, root policy stub, or static-analysis override registry changes.
- Stale output behavior: `fail`
- Drift gate: `uv run polisyos-tools workspace tool-configs --check`
- Owner: `team-devx`
- Approval owner: `team-architecture`
- Related workflow/config: `tools/devx/workspace/tool_configs.py`
- Outputs:
  - `architecture/tooling/mypy/generated.ini`
  - `architecture/tooling/ruff/generated.toml`
  - `architecture/tooling/mkdocs/generated.yml`
  - `mypy.ini`
  - `ruff.toml`
  - `mkdocs.yml`

Canonical regeneration commands:

```bash
uv run polisyos-tools workspace tool-configs
```

## `Release inputs and unreleased fragments`

- Family id: `release-inputs-and-fragments`
- Lifecycle: `source_committed`
- Source of truth: release/**, release-fragments/unreleased/**, release-fragments/template.toml, ops/release/**, and docs/how-to/release-policy.md
- Generator: manual release-owner edits using release-fragments/template.toml and ops/release policy
- Verifier: uv run polisyos-tools workspace release-build-cache-lifecycle check
- Promotion target: release/** and release-fragments/unreleased/** committed through release-owner review
- Commit policy: `committed`
- Freshness rule: Update committed release inputs whenever release policy, release evidence templates, CVE exceptions, artifact-size policy, or unreleased release-note inputs change.
- Stale output behavior: `warn`
- Drift gate: `automated`
- Owner: `team-release`
- Approval owner: `team-release`
- Related workflow/config: `../.github/workflows/release.yml`
- Outputs:
  - `release`
  - `release-fragments/README.md`
  - `release-fragments/template.toml`
  - `release-fragments/unreleased`

Canonical regeneration commands:

```bash
manual review: add release ledgers, evidence templates, and unreleased fragments under release/** or release-fragments/unreleased/**
```

## `Release build output staging`

- Family id: `release-build-output-staging`
- Lifecycle: `generated_ignored`
- Source of truth: release/**, release-fragments/unreleased/**, pyproject.toml, dependency locks, and release workflow inputs
- Generator: uv run polisyos-tools release stage-release-snapshot and release workflow artifact builders
- Verifier: uv run polisyos-tools workspace release-build-cache-lifecycle check
- Promotion target: release/ or docs/archive/reports/release/ after release-owner review
- Commit policy: `local_ignored`
- Freshness rule: Regenerate release build output for each release candidate. Keep it ignored unless a reviewed release evidence record is promoted.
- Stale output behavior: `warn`
- Drift gate: `ignored_by_policy`
- Owner: `team-release`
- Approval owner: `team-release`
- Retention: `90` days
- Related workflow/config: `../.github/workflows/release.yml`
- Outputs:
  - `_build/release`
  - `_build/release-fragments`

Canonical regeneration commands:

```bash
uv run polisyos-tools release stage-release-snapshot --version <version> --source-dir release-fragments/unreleased --release-root _build/release-fragments
uv run polisyos-tools release build-release-notes --version <version> --fragments-dir _build/release-fragments/<version> --output _build/release/notes/<version>.md
```

## `Local build cache and scratch`

- Family id: `local-build-cache-and-scratch`
- Lifecycle: `scratch_ignored`
- Source of truth: recomputable local command outputs and caches
- Generator: local build, test, docs, release, and quality commands
- Verifier: uv run polisyos-tools workspace release-build-cache-lifecycle check
- Promotion target: none; promote reviewed evidence through a dedicated generated-artifact family before commit
- Commit policy: `local_ignored`
- Freshness rule: Keep local scratch/cache ignored and delete when stale, corrupted, or no longer needed.
- Stale output behavior: `cleanup_eligible`
- Drift gate: `ignored_by_policy`
- Owner: `team-devx`
- Approval owner: `team-devx`
- Retention: `30` days
- Related workflow/config: `tools/devx/workspace/release_build_cache_lifecycle.py`
- Outputs:
  - `_build/scratch`
  - `_build/.tmp`
  - `_cache`

Canonical regeneration commands:

```bash
local commands recreate these scratch and cache paths on demand
```

## `Wrong-root cache and tmp residue`

- Family id: `wrong-root-cache-tmp-residue`
- Lifecycle: `scratch_ignored`
- Source of truth: repository root topology decision; product work belongs under policy-engine/
- Generator: mis-scoped local commands run from the outer Git root
- Verifier: uv run polisyos-tools workspace release-build-cache-lifecycle check
- Promotion target: none; recreate under policy-engine/_build, policy-engine/_cache, or the registered runtime-state root
- Commit policy: `local_ignored`
- Freshness rule: Remove wrong-root cache/tmp residue during lifecycle cleanup. Do not migrate it into source roots.
- Stale output behavior: `cleanup_eligible`
- Drift gate: `ignored_by_policy`
- Owner: `team-devx`
- Approval owner: `team-devx`
- Retention: `7` days
- Related workflow/config: `tools/devx/workspace/release_build_cache_lifecycle.py`
- Outputs:
  - `../_build`
  - `../_cache`
  - `../tmp`
  - `../.tmp_*`

Canonical regeneration commands:

```bash
do not regenerate intentionally; rerun the owning command from policy-engine/ so output lands under the product root
```

## `Release SBOM`

- Family id: `release-sbom`
- Lifecycle: `generated_ignored`
- Source of truth: uv.lock, pnpm-lock.yaml, Dockerfile.reproducible, and release manifest inputs
- Generator: release workflow CycloneDX SBOM generation job
- Verifier: uv run polisyos-tools workspace release-build-cache-lifecycle check plus release workflow SBOM policy checks
- Promotion target: release candidate artifact channel; committed evidence only after release-owner promotion
- Commit policy: `local_ignored`
- Freshness rule: Regenerate for every release candidate or dependency-lock change; publish through CI/release artifacts rather than committing local SBOM output.
- Stale output behavior: `block_release`
- Drift gate: `ignored_by_policy`
- Owner: `team-security`
- Approval owner: `team-security`
- Retention: `90` days
- Related workflow/config: `ops/ci/templates/workflows/build-and-push.yml`
- Outputs:
  - `_build/release/sbom`

Canonical regeneration commands:

```bash
manual/CI: run the release workflow SBOM generation job with output under _build/release/sbom/
```

## `Supply-chain control crosswalk`

- Family id: `supply-chain-control-crosswalk`
- Lifecycle: `generated_committed`
- Source of truth: architecture/control_plane_supply_chain.toml and external OpenSSF Scorecard/SLSA/CycloneDX/Sigstore control baselines
- Generator: tools/quality/validation/control_plane_supply_chain_contracts.py --crosswalk-json
- Verifier: uv run python tools/quality/validation/control_plane_supply_chain_contracts.py
- Promotion target: docs/archive/reports/supply-chain-control-crosswalk.json
- Commit policy: `committed`
- Freshness rule: Regenerate and commit whenever release phase gates, artifact signing/provenance expectations, workflow identity permissions, or external supply-chain control mappings change.
- Stale output behavior: `fail`
- Drift gate: `automated`
- Owner: `team-security`
- Approval owner: `team-security`
- Related workflow/config: `tools/quality/validation/control_plane_supply_chain_contracts.py`
- Outputs:
  - `docs/archive/reports/supply-chain-control-crosswalk.json`

Canonical regeneration commands:

```bash
uv run python tools/quality/validation/control_plane_supply_chain_contracts.py --crosswalk-json docs/archive/reports/supply-chain-control-crosswalk.json
```

## `Release build/cache cleanup command`

- Family id: `release-local-cleanup`
- Lifecycle: `scratch_ignored`
- Source of truth: architecture/generated_artifacts.toml, .gitignore, and release/build/cache lifecycle decision
- Generator: uv run polisyos-tools workspace release-build-cache-lifecycle cleanup
- Verifier: uv run pytest tests/repo_quality/tools/test_release_build_cache_lifecycle.py -q
- Promotion target: none; command removes local ignored output only
- Commit policy: `local_ignored`
- Freshness rule: Run dry-run cleanup before applying. Cleanup must preserve release/** and release-fragments/unreleased/**.
- Stale output behavior: `cleanup_eligible`
- Drift gate: `automated`
- Owner: `team-devx`
- Approval owner: `team-release`
- Retention: `30` days
- Related workflow/config: `tools/devx/workspace/release_build_cache_lifecycle.py`
- Outputs:
  - `_build/scratch`
  - `_cache`
  - `../_cache`
  - `../tmp`

Canonical regeneration commands:

```bash
uv run polisyos-tools workspace release-build-cache-lifecycle cleanup
uv run polisyos-tools workspace release-build-cache-lifecycle cleanup --apply
```

## `Data Forge migration fixture baselines`

- Family id: `data-forge-migration-fixture-baselines`
- Lifecycle: `generated_committed`
- Source of truth: tests/_data/data_forge/** golden, shadow, replay, and differential fixture contracts
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Refresh when Data Forge behavior-changing migrations intentionally update golden, replay, shadow, or differential baselines.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-data-forge`
- Approval owner: `team-architecture`
- Related workflow/config: `tests/unit/data_forge`
- Outputs:
  - `tests/_data/data_forge/non_lex_split`
  - `tests/_data/data_forge/legal_shadow`
  - `tests/_data/data_forge/ukraine_shadow`

Canonical regeneration commands:

```bash
manual review: refresh paired baseline/candidate fixtures and run uv run pytest tests/unit/data_forge/test_phase1_shared_kernel_cutover.py tests/unit/data_forge/test_phase7_schema_quality_observability.py tests/unit/data_forge/test_repository_sota_phase1_foundation.py -q
```

## `Data Forge artifact and manifest contract schemas`

- Family id: `data-forge-contract-schemas`
- Lifecycle: `generated_committed`
- Source of truth: src/polisyos/data_forge/kernel/** ArtifactRef, trace metadata, domain artifact, and manifest contracts
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Review whenever Data Forge ArtifactRef, trace metadata, domain artifact, raw/stage/publish manifest, or publish-manifest contracts change.
- Stale output behavior: `warn`
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
- Lifecycle: `generated_committed`
- Source of truth: pnpm-workspace.yaml, package.json, apps/*/package.json, packages/*/package.json, and the Node 22 contributor baseline
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: registered committed outputs listed in outputs
- Commit policy: `committed`
- Freshness rule: Regenerate and commit the root pnpm lockfile whenever any workspace package dependency graph changes.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-frontend`
- Approval owner: `team-frontend`
- Related workflow/config: `../.github/workflows/frontend-quality.yml`
- Outputs:
  - `pnpm-lock.yaml`

Canonical regeneration commands:

```bash
corepack pnpm install --lockfile-only
```

## `Frontend local generated outputs`

- Family id: `frontend-local-generated-outputs`
- Lifecycle: `generated_ignored`
- Source of truth: apps and packages workspace build, coverage, audit, Playwright, Storybook, cache, and package manager commands
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: none unless a reviewed baseline family is added
- Commit policy: `local_ignored`
- Freshness rule: Keep local generated outputs ignored. Commit only explicit reviewed baselines registered in a committed artifact family.
- Stale output behavior: `ignored_by_policy`
- Drift gate: `ignored_by_policy`
- Owner: `team-frontend`
- Approval owner: `team-frontend`
- Related workflow/config: `docs/reference/frontend/workspace-contract.md`
- Outputs:
  - `node_modules`
  - `packages/runtime-api-client/node_modules`
  - `_build/packages/runtime-api-client/coverage`
  - `_build/packages/runtime-api-client/dist`
  - `_build/packages/runtime-api-client/.tmp`
  - `_cache/packages/runtime-api-client/eslint/.eslintcache`
  - `apps/runtime-dashboard/node_modules`
  - `_build/apps/runtime-dashboard/coverage`
  - `_build/apps/runtime-dashboard/dist`
  - `_build/apps/runtime-dashboard/output`
  - `_build/apps/runtime-dashboard/playwright-report`
  - `_build/apps/runtime-dashboard/storybook-static`
  - `_build/apps/runtime-dashboard/test-results`
  - `_build/apps/runtime-dashboard/.tmp`
  - `_cache/apps/runtime-dashboard/eslint/.eslintcache`
  - `apps/runtime-reference-shell/node_modules`
  - `_build/apps/runtime-reference-shell/coverage`
  - `_build/apps/runtime-reference-shell/dist`
  - `_build/apps/runtime-reference-shell/.tmp`
  - `_cache/apps/runtime-reference-shell/eslint/.eslintcache`
  - `packages/cli/node_modules`
  - `_cache/packages/cli/eslint/.eslintcache`

Canonical regeneration commands:

```bash
corepack pnpm --filter @polisyos/runtime-dashboard run build
corepack pnpm --filter @polisyos/runtime-dashboard run test:coverage
corepack pnpm --filter @polisyos/runtime-dashboard run build-storybook
```

## `Committed data fixtures and catalogs`

- Family id: `committed-data-fixtures-and-catalogs`
- Lifecycle: `source_committed`
- Source of truth: data/README.md, data/academic_gold/** tiny examples, and data/dataset_catalog/*.yaml registry entries
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: data/academic_gold/ or data/dataset_catalog/ through data policy review
- Commit policy: `committed`
- Freshness rule: Commit only small fixtures, contracts, manifests, registry entries, or tiny gold examples. Bulk raw/curated/database outputs remain ignored local data.
- Stale output behavior: `warn`
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
- Lifecycle: `generated_ignored`
- Source of truth: architecture/policies/data.toml
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: none; promote only curated tiny fixtures through data policy
- Commit policy: `local_ignored`
- Freshness rule: Local data lake content is local runtime or corpus state and must stay ignored unless promoted to a registered tiny fixture.
- Stale output behavior: `ignored_by_policy`
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
- Lifecycle: `runtime_ignored`
- Source of truth: architecture/local_runtime_state.toml and architecture/runtime_state_layout.toml
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: docs/archive/reports/ after redaction or release evidence after approval
- Commit policy: `local_ignored`
- Freshness rule: Keep runtime state ignored, retention-classed, and cleanable through the documented cleanup commands.
- Stale output behavior: `ignored_by_policy`
- Drift gate: `ignored_by_policy`
- Owner: `team-platform`
- Approval owner: `team-platform`
- Related workflow/config: `docs/reference/local-runtime-state.md`
- Outputs:
  - `.polisyos`

Canonical regeneration commands:

```bash
manual/local: runtime runs, reports, CAS, artifact-cache, and provider-verification commands create .polisyos state
```

## `Ops observability baselines`

- Family id: `ops-observability-baselines`
- Lifecycle: `source_committed`
- Source of truth: architecture/component_observability.toml, architecture/runbook_coverage.toml, ops/observability, ops/observability/prometheus, ops/observability/grafana, and runtime telemetry conventions
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: ops/observability/** through observability-owner review
- Commit policy: `committed`
- Freshness rule: Review whenever runtime metrics, trace attributes, SLO objectives, or dashboard panels change.
- Stale output behavior: `warn`
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
- Lifecycle: `source_committed`
- Source of truth: ops/security, ops/release, release-fragments, dependency locks, and Dockerfile.reproducible
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: ops/security/** or ops/release/** through security/release-owner review
- Commit policy: `committed`
- Freshness rule: Review whenever secret scanning policy, dependency lock inputs, SBOM format, release-fragment rules, or commit policy changes.
- Stale output behavior: `warn`
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
  - `ops/release/deployment-topology.toml`
  - `ops/release/promotion-gates.toml`

Canonical regeneration commands:

```bash
manual review: run gitleaks, trufflehog, OSV, SBOM, release-fragment, and commit-policy checks for release candidates
```

## `Ops runtime and migration baselines`

- Family id: `ops-runtime-and-migration-baselines`
- Lifecycle: `source_committed`
- Source of truth: ops/runtime, ops/migrations, runtime deployment contracts, and tenant/RLS SQL chain
- Generator: canonical generator declared in regenerate_commands
- Verifier: verifier declared by check_command, drift_gate, workflow, or manual review policy
- Promotion target: ops/runtime/** or ops/migrations/** through platform-owner review
- Commit policy: `committed`
- Freshness rule: Review whenever runtime deployment contracts, tenant isolation, RLS, rollback, helper bindings, release gates, or migration sequencing changes.
- Stale output behavior: `warn`
- Drift gate: `manual_review`
- Owner: `team-platform`
- Approval owner: `team-platform`
- Related workflow/config: `ops/ci/templates/workflows/arch.yml`
- Outputs:
  - `ops/runtime/runtime-contracts.toml`
  - `ops/migrations/README.md`
  - `ops/migrations/migration-contracts.toml`
  - `ops/migrations/db/README.md`
  - `ops/migrations/db/001_tenant_columns.sql`
  - `ops/migrations/db/002_tenant_backfill.sql`
  - `ops/migrations/db/003_rls_enable.sql`
  - `ops/migrations/db/003_rls_disable_rollback.sql`
  - `ops/migrations/db/004_roles_grants.sql`
  - `ops/migrations/runtime_state/README.md`
  - `ops/migrations/api_schemas/README.md`
  - `ops/migrations/ir/README.md`

Canonical regeneration commands:

```bash
manual review: update runtime and DB/runtime-state/API/IR migration baselines alongside deployment/runtime security contract changes
```

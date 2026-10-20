# Native phase 6.5: tracked-ready owner and engineering handoff

**Source frame:** `d3008898be4f075dd6be66265b8fd933193ff9d1` / tree `c65d6054d57f130197ed227b3bb9e69aeb84a5ec`, parent `2775b1091299aa675ae3bca79ce880566ebc0c67`. Draft only; no tracked files, exceptions, baselines, source, or authority records were changed. Independent G adjudication is false and closure IDs are empty.

This handoff preserves the original decision packet byte-for-byte and appends the missing A94 evidence as a separate corrigendum. It carries the full ordered 28 exception occurrences and all 13 registered gate commands/owners. The native 13-gate wave at this source frame remains **UNRUN**.

## Evidence correction

The prior packet described the reported 237-test cap outcome as an unlocated consumer assertion. Independent review located and reconciled the exact A94 v2 receipt. It is a focused-cohort `ERROR_resource_limit_abort` on ancestor `be09be99df14d93dd4d22a140696ea06e26c5c8d` / tree `3c3d5104aa910accc37e38253e7735714a03a95e`, not a semantic test failure, not OOM, not a pass, and not a d300 full native result. The R3 collector and selected test file hashes match d300, but the whole scanned source inventory was not reconciled to d300.

- Receipt: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-dynamic-import-r3-a94-20261020/resource-limit-error-v2.json` SHA-256 `706ec6a3f2e531d4edafaacfa3a17f36e588216994e9d41cb025a9ec24d69ec1`.
- Actual argv addendum: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-dynamic-import-r3-a94-20261020/resource-limit-error-v2-addendum.json` SHA-256 `393b02874796f15b49e89d390d701bdbee0ff178c54c85cdbadca98e4c423518`. It binds the command-start event; the original receipt’s `argv: null` does not mean the argv was unavailable.
- Output index: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-dynamic-import-r3-a94-20261020/execution-outputs-v2.json` SHA-256 `f5d225fa60971a4230e6d14c7d35733c666e5d34f102d84e52e94fbda7a979d3`.
- The run collected 335 tests: 237 selected, 98 deselected. The first selected node started but did not complete. Sampled RSS reached 1,114,357,760 bytes against a 1,073,741,824-byte cap; the process exited `-15` after about 5.07 seconds. No JUnit or R8 finish/origin receipt exists.
- Required follow-up: after a new explicit slot/grant and source freeze, rerun the complete selected cohort with sufficient measured resource cap and retain JUnit plus R8 finish/origin provenance. Then run the complete native 13-gate closeout separately. Do not reuse this error as a behavior result.

Independent review also corrected Ruff invocation: call Ruff through `uv run python -m ruff check ...`; do not use `uv run ruff check`.

## Owner decisions, not engineering blockers

The only semantic questions routed to external accountable owners are five underlying SLO/service decisions and two namespace boundaries. The 19 SLO rows are mirrors of five decisions. A team label, expired date, or `objectives: []` does not establish an issuer, coverage, or service performance. No renewal date is proposed. Request a named issuer and expiry only if an accountable owner actually elects to renew a real exception.

| Decision | Rows | Exact owner evidence needed |
|---|---:|---|
| `slo-berl` | 2, 13, 18, 25 | Joint package/service owners identify BERL service boundary and either actual standalone SLI/target/window/source, alert/runbook/release ownership, or named Scientist delegated SLO/runbook with failure coverage. Team labels do not appoint an issuer. |
| `slo-calibration` | 3, 15, 20, 24 | Foundry and Scientist resolve service ownership and provide either measured standalone SLO inputs or named delegated coverage and escalation/runbook owner. |
| `slo-common` | 4, 12, 17, 22 | team-core chooses measured standalone Common SLO or names monitored dependent components and shows those SLOs cover Common failure modes. |
| `slo-ddm` | 5, 14, 19, 26 | Architecture/Scientist resolve DDM public-stable status after shim/version policy and identify actual SLO issuer or exact delegated coverage plus runbook response. |
| `slo-security` | 16, 21, 23 | team-security chooses an actual Security SLO or names existing release/security operational coverage and proves the covered failure modes and escalation path. |
| `name-discovery` | 27 | team-architecture decides whether core/discovery is canonical or transitional after caller/import review; missing sibling directories do not decide this. |
| `name-runtime` | 28 | team-foundry/team-scientist choose whether live Foundry runtime remains canonical, moves to _runtime_glue, or joins a facade/API; then approve one atomic caller/test/docs/registry migration. |

The two namespace choices are discovery (whether `core/discovery` is canonical or transitional) and runtime (whether live Foundry runtime remains canonical, moves to `_runtime_glue`, or joins a facade/API). Existing tracked paths and callers decide the migration work after owners choose the boundary; absent siblings or zero collision findings do not close it.

## Executable engineering work

| Family | Rows | Work that remains executable | First falsifier |
|---|---:|---|---|
| dynamic-import | 1 | Use adopted R3 collector, existing validator and registered architecture gate; no parallel checker. Commands: `uv run --locked --no-sync --offline python tools/quality/validation/architecture_report_only_contracts.py --report dynamic-imports`<br>`uv run polisyos-tools architecture guardrails check --all-generated-checks` | Ordinary Path.write_bytes remains a non-importer while a genuine importer-source alias still fails closed. Recompute the complete current source denominator; selected A94 attempt is an ERROR only. |
| static-analysis | 6, 8, 9, 10, 11 | Use source override fragments, real configured tools, and registered tool-config generator; never edit generated outputs. Commands: `uv run --locked --no-sync --offline python tools/quality/validation/architecture_report_only_contracts.py --report static-analysis-overrides`<br>`uv run python -m ruff check src/polisyos/fabric tests/unit/fabric`<br>`uv run mypy --config-file architecture/tooling/mypy/generated.ini src/polisyos/fabric`<br>`uv run python -m ruff check src/polisyos/ir tests/unit/ir`<br>`uv run mypy --config-file architecture/tooling/mypy/generated.ini src/polisyos/ir`<br>`uv run python -m ruff check tests`<br>`uv run polisyos-tools workspace tool-configs --check`<br>`uv run python tools/ops_runners/reports/dead_overrides.py` | Removing a selector changes real Ruff/mypy diagnostics or leaves generated config drift. Metadata-only override reports do not decide this. |
| runtime-ratchet | 7 | Use report_test_ratchets.py and its contract test; keep floor and baseline fixed. Commands: `uv run python tools/quality/testing/report_test_ratchets.py --format json --fail-on-regression`<br>`uv run pytest tests/repo_quality/architecture/test_test_ratchets_contract.py -q` | A below-floor/no-exception control must fail; above-floor evidence must come from complete current source/test denominator, not 227/317. |
| names | 27, 28 | Use name_registry.toml, current tracked tree/caller inventory and existing name tests; do not create a new namespace mechanism. Commands: `uv run --locked --no-sync --offline python tools/quality/validation/architecture_report_only_contracts.py --report name-collisions`<br>`uv run pytest tests/repo_quality/architecture/test_repository_structure_phase1c.py tests/repo_quality/architecture/test_last_mile_name_and_concern_inventory.py -q` | A live path or caller remains after proposed retirement, irrespective of a zero collision report. |
| slo-projection | 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26 | Use existing ops/components/index.toml plus component_observability and runbook_coverage routes; decide 5 components once and project consistently. Commands: `uv run --locked --no-sync --offline python tools/quality/validation/architecture_report_only_contracts.py --report component-observability`<br>`uv run --locked --no-sync --offline python tools/quality/validation/architecture_report_only_contracts.py --report runbook-coverage`<br>`uv run polisyos-tools workspace repository-sota-closeout --contract-only` | An endpoint, alert, or failure mode lacks accountable owner/coverage in the chosen path, or objectives=[] is treated as an active SLO. |

For static analysis, run actual diagnostics before pruning any selector; regenerate generated configs only through `tool-configs` and verify with `tool-configs --check`. The old runtime ratio 227/317 (0.7161 vs 0.7152) is historical, not current evidence. The below-floor/no-exception control must continue to fail; do not change the floor or baseline.

## Complete 28-row ledger (occurrence order)

Each occurrence below remains open; mirror rows route to their shared component decision. Full source statements, historic state, source refs, and required evidence are in the machine-readable handoff JSON.

| # | Finding | Route | Required next action |
|---:|---|---|---|
| 1 | `dynamic_imports.review` | engineering | team-architecture owns the existing registry; recompute the complete current source denominator and run the real importer guard. The A94 receipt is an ERROR, not a behavior result. |
| 2 | `berl-standalone-slo-deferred` | external_service_boundary | Resolve BERL standalone service versus named, verified Scientist delegated coverage; only issue an SLO if the accountable owner supplies the operational facts. |
| 3 | `calibration-standalone-slo-deferred` | external_service_boundary | Resolve Foundry/Scientist service ownership and standalone versus delegated coverage for Calibration. |
| 4 | `common-dependent-slo` | external_service_boundary | team-core chooses standalone Common SLO or supplies named dependent SLOs and evidence of Common failure coverage. |
| 5 | `ddm-standalone-slo-deferred` | external_service_boundary | Resolve DDM public-stable/shim version status, accountable SLO issuer, or exact delegated coverage. |
| 6 | `fabric-ruff-ratchet` | engineering_then_owner_acceptance | Run package-scoped Ruff/mypy against current generated configs first; team-fabric acceptance is only needed for any remaining bounded package debt. |
| 7 | `runtime.mirror_regression_exception` | engineering | Recompute the complete current test/source denominator and preserve the below-floor/no-exception falsifier; do not change floor or baseline. |
| 8 | `fabric-ruff-package-ratchet` | engineering | Run real Fabric Ruff diagnostics on registered scope, then edit source fragment and regenerate/check only if the selector is unused. |
| 9 | `fabric-mypy-module-ratchet` | engineering | Run real Fabric mypy diagnostics with generated config; never hand-edit generated.ini. |
| 10 | `ir-ruff-package-ratchet` | engineering | Run real IR Ruff diagnostics and global tests scope because selector includes tests/**; do not infer from metadata report. |
| 11 | `ir-mypy-module-ratchet` | engineering | Run real IR mypy diagnostics with generated config; never hand-edit generated.ini. |
| 12 | `architecture/component_observability.toml:common` | mirror_of_external_service_boundary | One Common owner decision shared with rows 4/17/22, then project consistently to this mirror. |
| 13 | `architecture/component_observability.toml:berl` | mirror_of_external_service_boundary | One BERL owner decision shared with row 2, then project consistently to this mirror. |
| 14 | `architecture/component_observability.toml:ddm` | mirror_of_external_service_boundary | One DDM owner decision shared with row 5, then project consistently to this mirror. |
| 15 | `architecture/component_observability.toml:calibration` | mirror_of_external_service_boundary | One Calibration owner decision shared with row 3, then project consistently to this mirror. |
| 16 | `architecture/component_observability.toml:security` | external_service_boundary | team-security chooses a real Security SLO or names release/security coverage and proves failure coverage. |
| 17 | `ops/components/index.toml:common` | mirror_of_external_service_boundary | One Common owner decision shared with rows 4/12/22, then project consistently to this mirror. |
| 18 | `ops/components/index.toml:berl` | mirror_of_external_service_boundary | One BERL owner decision shared with row 2, then project consistently to this mirror. |
| 19 | `ops/components/index.toml:ddm` | mirror_of_external_service_boundary | One DDM owner decision shared with row 5, then project consistently to this mirror. |
| 20 | `ops/components/index.toml:calibration` | mirror_of_external_service_boundary | One Calibration owner decision shared with row 3, then project consistently to this mirror. |
| 21 | `ops/components/index.toml:security` | external_service_boundary | One Security owner decision shared with row 16, then project consistently to this mirror. |
| 22 | `architecture/runbook_coverage.toml:common` | mirror_of_external_service_boundary | One Common owner decision shared with rows 4/12/17, then project consistently to this mirror. |
| 23 | `architecture/runbook_coverage.toml:security` | external_service_boundary | One Security owner decision shared with row 16, then project consistently to this mirror. |
| 24 | `architecture/runbook_coverage.toml:calibration` | mirror_of_external_service_boundary | One Calibration owner decision shared with row 3, then project consistently to this mirror. |
| 25 | `architecture/runbook_coverage.toml:berl` | mirror_of_external_service_boundary | One BERL owner decision shared with row 2, then project consistently to this mirror. |
| 26 | `architecture/runbook_coverage.toml:ddm` | mirror_of_external_service_boundary | One DDM owner decision shared with row 5, then project consistently to this mirror. |
| 27 | `name_registry:discovery` | external_namespace_boundary | team-architecture decides whether core/discovery is canonical or transitional after caller review; then run current path/import tests. |
| 28 | `name_registry:runtime` | external_namespace_boundary | team-foundry/team-scientist decide Foundry runtime ownership and migration target; then update callers/tests/registry/docs as one change. |

## All 13 registered native gates

The following are the exact current registry commands and owners. The 637 status column is historical only; it is not a current result. Six were `not_run`; seven were `preflight_only_not_full_gate`.

| # | Gate | Owner | Registered command | At 637 | d300 |
|---:|---|---|---|---|---|
| 1 | `topology-loose-files` | team-architecture | `uv run pytest tests/repo_quality/architecture/test_repository_sota_phase3_topology_cleanup.py -q` | `not_run` | UNRUN |
| 2 | `import-linter` | team-architecture | `uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml` | `not_run` | UNRUN |
| 3 | `public-surface` | team-architecture | `uv run polisyos-tools architecture guardrails check` | `not_run` | UNRUN |
| 4 | `generated-drift` | team-architecture | `uv run polisyos-tools architecture guardrails check --all-generated-checks` | `not_run` | UNRUN |
| 5 | `docs-freshness` | team-docs | `uv run polisyos-tools validation check-docs-accuracy --repo-root .` | `preflight_only_not_full_gate` | UNRUN |
| 6 | `public-polish` | team-docs | `uv run pytest tests/repo_quality/architecture/test_repository_public_polish.py -q` | `not_run` | UNRUN |
| 7 | `shim-audit` | team-architecture | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 8 | `complexity-exceptions` | team-architecture | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 9 | `security-baselines` | team-security | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 10 | `dependency-baselines` | team-security | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 11 | `sbom-baseline` | team-security | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 12 | `commit-policy` | team-release | `uv run polisyos-tools workspace repository-sota-closeout --contract-only` | `preflight_only_not_full_gate` | UNRUN |
| 13 | `command-registry` | team-devx | `uv run polisyos-tools docs --output docs/reference/tools.md --check` | `not_run` | UNRUN |

After owner decisions that affect inputs and an explicitly frozen source frame, use the canonical one-shot runner `uv run polisyos-tools workspace repository-sota-closeout`. Retain the complete output. Contract-only output is preflight, not registered subprocess completion.

## Tracked adoption proposal

Proposed tracked outputs (not written in this task):

- `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/native-phase6-5-exception-gdecision-2026-10-20.md`
- `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/native-phase6-5-exception-gdecision-2026-10-20.json`

Keep this concise summary and machine-readable ordered rows/gates in the repository; cite detailed RAW evidence by immutable path and SHA-256. Do not edit a lease/index here; root can append its automatic journal/index binding after adoption.

## Input references

The JSON packet contains the complete immutable input reference list, including prior packet/review bindings, historical ledger/map, A94 receipt/addendum/output index, run driver/request/sandbox, captured outputs/source snapshots, and R3 focused receipt. No mutable lease/index prehash is included. The prior decision-v1 packet and all exception/baseline files remain unchanged.

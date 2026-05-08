---
title: Repository Best-In-Class Last-Mile Closeout
status: accepted
owner: team-polisyos
created: 2026-05-07
last_verified: 2026-05-08
stability: final
supersedes:
  - ../active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md
  - 2026-05-07-repository-best-in-class-final-acceptance.md
---

# Repository Best-In-Class Last-Mile Closeout

This archive report closes Wave 7 of the Repository Best-In-Class last-mile
program. It records the committed-state evidence required by
`docs/plans/active/REPOSITORY_BEST_IN_CLASS_LAST_MILE_REMEDIATION_PLAN.md` and
keeps the executable proof in `_build/.tmp/last-mile/*`.

## Closure Summary

| Area | Final evidence | Result |
| --- | --- | --- |
| Last-mile inventory | `_build/.tmp/last-mile/inventory.json` | 26 finding families inventoried; active enforcement is owned by the fail-closed gates below. |
| Package import gates | `_build/.tmp/last-mile/package-import-gates.json` | `status=passed`, `mode=fail_closed`, `finding_count=0`. |
| Directory health | `_build/.tmp/last-mile/directory-health.json` | `status=passed`, `finding_count=0`, `contract_error_count=0`, `regression_count=0`. |
| Test ratchets | `_build/.tmp/last-mile/test-ratchets.json` | 13 packages checked; 0 floor, strict, property, or helper-topology regressions. |
| Module size contracts | `_build/.tmp/last-mile/module-size.json` | `contract_error_count=0`, 35 module-size budgets tracked. |
| Operability release gates | `_build/.tmp/last-mile/operability-release-gates.json` | `status=passed`, `mode=fail_closed`, `finding_count=0`. |
| Compatibility release gates | `_build/.tmp/last-mile/compatibility-release-gates.json` | `contract_error_count=0`; report-only compatibility promotion remains contract-clean. |
| Platform acceptance | `_build/.tmp/last-mile/platform-acceptance.md` | 22 checks passed; 0 automated blockers, 0 manual blockers, 0 pending manual checks. |

## Scientist Root Facade Final Inventory

| Metric | Final value | Evidence |
| --- | ---: | --- |
| Canonical first-level roots | 18 | `architecture/packages/scientist.toml`, package-import gate summary |
| Canonical root cap | 18 | `architecture/packages/scientist.toml` |
| Registered root `.py` shims | 11 | `summary.scientist_root_facade.registered_root_py_shim_files` |
| Unregistered root `.py` files | 0 | `summary.scientist_root_facade.unregistered_root_py_count` |
| Wave 2 root-file debt | 0 | `summary.scientist_root_facade.wave2_root_file_debt_count` |
| Duplicate package/file pairs | 5 registered | `architecture/packages/scientist.toml` |
| Root facade gate findings | 0 | `_build/.tmp/last-mile/package-import-gates.json` |

Registered Scientist root shims are:
`decision_validity.py`, `error_semantics.py`, `evidence_sources.py`,
`feedback_utils.py`, `frontier_runtime.py`, `latent_separation.py`,
`llm_cycle.py`, `publisher.py`, `reliability_scorecard.py`,
`remediation_status.py`, and `replay_backend.py`.

## Fabric And IR Semantic Group Inventory

| Package | Canonical implementation roots | Compatibility posture | Evidence |
| --- | ---: | --- | --- |
| Fabric | 24 | Active root facade; implementation lives under semantic groups such as `_adapters`, `connectors`, `data_plane`, `evidence`, `identity`, `numerics`, `quality`, and `world`. | `architecture/packages/fabric.toml` |
| IR | 18 | Resolved root facade; implementation lives under `analytics`, `loading`, `model_layer`, `registry`, `schemas`, `_internal`, and `_lazy_facade`. | `architecture/packages/ir.toml` |
| Shell package gate | 0 findings | `mode=fail_closed`; 5 dated IR shell exceptions remain explicitly registered. | `_build/.tmp/last-mile/package-import-gates.json` |

## Cross-Package Names And Cross-Cutting Concerns

| Decision type | Examples | Owner | Final gate |
| --- | --- | --- | --- |
| `scoped_ok` | `_internal`, `contracts`, `connectors`, `governance`, `methods` | team-architecture | Name-collision gate: 0 findings |
| `canonical_home_with_adapters` | `_adapters`, `calibration`, observability adapter policy | team-architecture | Cross-cutting concern gate: 0 findings |
| `sunset_shim` | Scientist `discovery`, `orchestrator` | team-scientist/team-architecture | Shim debt tracked in `architecture/shims.toml`; no expired shims |
| Bounded-context repeat | Fabric/Scientist `evidence`, Fabric/IR `connectors`, Foundry/Scientist `feedback` | package owners | `architecture/name_registry.toml` |

The read-only inventory still records 45 repeated cross-package names and 25
cross-cutting concern paths so future drift remains visible, but the fail-closed
decision gates have 0 findings.

## Scientist Parallel Implementation Audit Closeout

| Family | Resolution | Compatibility path |
| --- | --- | --- |
| `publishing` / `publisher.py` | Canonical implementation under `scientist/publishing`. | Root `publisher.py` re-export shim. |
| `evidence` / `evidence_sources.py` | Canonical implementation under `scientist/evidence`. | Root `evidence_sources.py` re-export shim. |
| `feedback` / `feedback_utils.py` | Canonical implementation under `scientist/feedback`. | Root `feedback_utils.py` re-export shim. |
| `replay` / `replay_backend.py` | Canonical implementation under `scientist/replay`. | Root `replay_backend.py` re-export shim. |
| `llm` / `llm_cycle.py` | Canonical implementation under orchestration LLM paths. | Root `llm_cycle.py` re-export shim. |
| `orchestration` / `orchestrator` | `orchestration` is canonical. | `orchestrator` is compatibility root only. |
| Engine/governance/causal file pairs | Canonical homes are orchestration engine, governance, and methods/causal. | Root re-export shims are registered and sunset-dated. |

## Collision Resolution Table

| Collision | Final decision | Evidence |
| --- | --- | --- |
| `ir/refs` versus `ir/references` | No active collision remains; package-import gate `ir_refs_references_collision` has 0 findings. | `_build/.tmp/last-mile/package-import-gates.json` |
| Scientist `orchestrator` versus `orchestration` | `orchestration` is active; `orchestrator` is a compatibility shim root. | `architecture/packages/scientist.toml`, `architecture/shims.toml` |
| Root architecture TOML versus `architecture/gates/**` | Gate contracts are organized under `architecture/gates/**` with registered aggregate mirrors. | `architecture/gates/index.toml`, package-import `phase6_1` summary |
| Frontend legacy path names | Active JS workspaces are `apps/**` and `packages/**`; legacy `frontend/` remains a redirect stub with sunset metadata. | `frontend/README.md`, directory lifecycle gates |

## Shim Caller Report And Sunset Table

| Metric | Value | Evidence |
| --- | ---: | --- |
| Caller report shims scanned | 60 | `_build/.tmp/last-mile/shim_callers.json` |
| Total caller edges | 2,892 | `_build/.tmp/last-mile/shim_callers.json` |
| Shims with first-party source callers | 37 | `_build/.tmp/last-mile/shim_callers.json` |
| Zero-caller shims | 0 | `_build/.tmp/last-mile/shim_callers.json` |
| Registered shim debt entries | 81 | `_build/.tmp/last-mile/package-import-gates.json` |
| Expired shims | 0 | `_build/.tmp/last-mile/package-import-gates.json` |
| Due within 30 days | 0 | `_build/.tmp/last-mile/package-import-gates.json` |

Removal rule: a shim can be removed only after caller count reaches zero or all
remaining callers are examples/tests intentionally exercising compatibility.

## God-Module Line-Count Before/After

| Module | Before | After | Delta | Owner |
| --- | ---: | ---: | ---: | --- |
| `foundry/.../causal_engine.py` | 10,231 | 10 | -10,221 | team-foundry |
| `data_forge/.../core_sources_ingest.py` | 8,236 | 116 | -8,120 | team-data-forge |
| `foundry/.../interference.py` | 5,769 | 9 | -5,760 | team-foundry |
| `foundry/.../id_engine.py` | 5,045 | 9 | -5,036 | team-foundry |
| `scientist/.../build_decision_packet.py` | 4,684 | 6 | -4,678 | team-scientist |
| `data_forge/.../resolve_extract.py` | 4,622 | 98 | -4,524 | team-data-forge |
| `runtime/http/services/control.py` | 4,114 | 10 | -4,104 | team-runtime |
| `scientist/.../decision_packet/builder.py` | 4,653 | 885 | -3,768 | team-scientist |
| `runtime/.../control/run_lifecycle.py` | 3,953 | 2,050 | -1,903 | team-runtime |

Module-size budget status: 35 budgets tracked, 9 shrunk, 23 no-growth, 3
budgeted growth entries, and 0 contract errors in report-only mode.

## Mirror-Ratio Before/After

| Package | Loose before | Loose after | Strict before | Strict after | Property files | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `berl` | 0.0385 | 0.3846 | 0.0385 | 0.0385 | 0 -> 0 | explicit exception |
| `calibration` | 0.7143 | 0.7143 | 0.7143 | 0.7143 | 0 -> 0 | explicit exception |
| `common` | 0.3333 | 0.7778 | 0.3333 | 0.3333 | 1 -> 1 | no regression |
| `core` | 0.2327 | 0.5031 | 0.1447 | 0.1447 | 0 -> 0 | below-first-target tracking |
| `data_forge` | 0.3803 | 0.6009 | 0.1831 | 0.2197 | 1 -> 1 | no regression |
| `ddm` | 0.0000 | 0.6667 | 0.0000 | 0.0000 | 0 -> 0 | explicit exception |
| `fabric` | 0.1342 | 0.4980 | 0.0736 | 0.0683 | 1 -> 1 | registered exceptions |
| `foundry` | 0.4581 | 0.7205 | 0.3587 | 0.3498 | 28 -> 28 | registered strict exception |
| `ir` | 0.1911 | 0.6012 | 0.1401 | 0.1272 | 1 -> 1 | registered strict exception |
| `lex` | 0.2333 | 0.4667 | 0.2333 | 0.2333 | 1 -> 1 | explicit exception |
| `runtime` | 0.0351 | 0.7619 | 0.0175 | 0.0159 | 1 -> 1 | registered strict exception |
| `scholar` | 0.1429 | 0.4762 | 0.1429 | 0.1429 | 0 -> 0 | explicit exception |
| `scientist` | 0.6155 | 0.7524 | 0.3247 | 0.3217 | 5 -> 5 | registered strict exception |

Ratchet summary: 0 floor regressions, 0 strict regressions, 0 property
regressions, and 0 helper-topology count regressions.

## Integration-Test Bridge Inventory

| Bridge | Test |
| --- | --- |
| Core/runtime config and startup | `tests/integration/core_runtime/test_config_security_startup_bridge.py` |
| Data Forge to runtime | `tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py` |
| Fabric to IR observation | `tests/integration/fabric_ir/test_connector_observation_bridge.py` |
| Foundry to calibration | `tests/integration/foundry_calibration/test_method_calibration_bridge.py` |
| Foundry to Scientist | `tests/integration/foundry_scientist/test_method_node_bridge.py` |
| Lex to IR to Foundry | `tests/integration/lex_ir_foundry/test_normpack_factlog_method_bridge.py` |
| Runtime to frontend client | `tests/integration/runtime_frontend/test_runtime_client_contract_bridge.py` |
| Scholar to Scientist | `tests/integration/scholar_scientist/test_search_orchestration_bridge.py` |
| Scientist to BERL | `tests/integration/scientist_berl/test_explanation_reliability_bridge.py` |

`uv run pytest tests/integration -q` passed with 4 environment-gated skips.

## Test Helper And Conftest Contract Evidence

| Contract item | Value | Evidence |
| --- | ---: | --- |
| Shared helper files | 8 | `test_helper_topology.summary.shared_helper_files` |
| Layer-local `conftest.py` files | 27 | `test_helper_topology.summary.layer_local_conftest_files` |
| Unused helpers | 0 | `test_helper_topology.summary.unused_helpers` |
| Forbidden reverse imports | 0 | `test_helper_topology.summary.forbidden_reverse_imports` |
| Registered duplicate fixture factories | 1 | `scientist-cas-store-local-fixture` |
| Unregistered duplicate fixture factories | 0 | `_build/.tmp/last-mile/test-ratchets.json` |

## Schemas Pure-Data Evidence

| Check | Result |
| --- | --- |
| `find schemas \( -name '*.py' -o -name '__pycache__' \)` | Empty output |
| `test ! -s _build/.tmp/last-mile/schemas-python-residue.txt` | Pass |
| Package import schema-only gate | 0 findings |

Python schema helpers live under `src/polisyos/schemas`; top-level `schemas/**`
remains committed schema/data artifacts only.

## Entry-Point Example Coverage

| Entry point group | Example package | Gate result |
| --- | --- | --- |
| `polisyos.fabric_connectors` | `examples/extensions/fabric_connector` | install, discovery, smoke pass |
| `polisyos.foundry_methods` | `examples/extensions/foundry_method` | install, discovery, smoke pass |
| `polisyos.scientist_governance_passes` | `examples/extensions/scientist_governance_pass` | install, discovery, smoke pass |
| `polisyos.scientist_nodes` | `examples/extensions/scientist_node` | install, discovery, smoke pass |
| `polisyos.data_forge_domains` | `examples/extensions/data_forge_domain` | install, discovery, smoke pass |
| `polisyos.lex_normpacks` | `examples/extensions/lex_normpack` | install, discovery, smoke pass |
| `polisyos.runtime_middlewares` | `examples/extensions/runtime_middleware` | install, discovery, smoke pass |

`uv run python tools/quality/validation/check_extension_examples.py` discovered
7 extension examples and passed.

## ADR Thematic Index Freshness

| Artifact | Evidence |
| --- | --- |
| `docs/adr/index.toml` | Generated source of truth |
| `docs/adr/index.md` | Fresh |
| `docs/adr/by-topic.md` | Fresh |
| Gate | `uv run python tools/quality/validation/generate_adr_index.py --check` passed |

## Operability Bundle Completeness

| Metric | Value |
| --- | ---: |
| Components | 14 |
| Public-stable components | 8 |
| Observability contracts | 14 |
| Component alerts | 46 |
| Central alert mappings | 46 |
| Prometheus alerts | 46 |
| Required bundle files | `README.md`, `alerts.yml`, `dashboard.json`, `retention-policy.toml`, `runbooks.md`, `runtime-contract.toml`, `slo.yaml` |

## Architecture Taxonomy And Gate Organization

| Item | Final state |
| --- | --- |
| Gate contract root | `architecture/gates/index.toml` plus gate-specific TOMLs |
| Converted gate families | root facade/package layout, package boundary, public surface, deep import, dynamic import, import cycle, name collision, shim expiry |
| Architecture taxonomy | `architecture/conceptual_groups.toml` and `architecture/policies/cross_cutting_concerns.toml` |
| Package contracts | 16 packages tracked |
| Report-only gate count | 14, all contract-clean |

## Local Hygiene Evidence

| Check | Result |
| --- | --- |
| Directory health | 0 findings, 0 regressions, 123/123 high-volume subtrees documented |
| Local ignored residue in committed baseline | 0 paths in `LM-009` |
| Dead overrides | 1,045 overrides tracked; 0 stale mypy, 0 stale Ruff, 0 missing metadata |
| Outer root policy | Final root checks run from `/Users/deniskopylov/polisyos` after commit |
| Generated build residue | `_build/**`, `node_modules/**`, caches, `.venv/**`, and `.polisyos/**` remain excluded from committed paths unless explicitly policy-owned |

## Verification Commands

All commands below were run from `/Users/deniskopylov/polisyos/policy-engine`
on 2026-05-08 unless a different working directory is noted.

```bash
uv run python tools/quality/validation/repository_structure_phase0.py gate --gate all --mode fail-closed --json
uv run python tools/quality/validation/repository_last_mile_inventory.py --json-output _build/.tmp/last-mile/inventory.json
uv run python tools/quality/validation/check_package_import_gates.py --fail-closed --json-output _build/.tmp/last-mile/package-import-gates.json
uv run python tools/quality/validation/directory_health.py --repo-root . --json-output _build/.tmp/last-mile/directory-health.json --markdown-output _build/.tmp/last-mile/directory-health.md --fail-on-regression
uv run python tools/quality/testing/report_test_ratchets.py --format json --output _build/.tmp/last-mile/test-ratchets.json --fail-on-regression
uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/last-mile/dead-overrides.json
uv run python tools/quality/validation/check_extension_examples.py
uv run python tools/quality/validation/generate_adr_index.py --check
uv run python tools/quality/validation/architecture_report_only_contracts.py --report module-size --json-output _build/.tmp/last-mile/module-size.json --fail-on-contract-errors
uv run python tools/ops_runners/release/check_operability_release_gates.py --json-output _build/.tmp/last-mile/operability-release-gates.json --fail-closed
uv run python tools/ops_runners/release/check_compatibility_release_gates.py --json-output _build/.tmp/last-mile/compatibility-release-gates.json --fail-on-contract-errors
uv run polisyos-tools workspace acceptance-audit --json-output _build/.tmp/last-mile/platform-acceptance.json --summary _build/.tmp/last-mile/platform-acceptance.md
uv run python -m tools.devx.workspace.doctor
uv run pytest tests/contract -q
uv run pytest tests/repo_quality -q
uv run pytest tests/integration -q
corepack pnpm install --frozen-lockfile
corepack pnpm -r --workspace-concurrency=1 --if-present run build
corepack pnpm -r --workspace-concurrency=1 --if-present run test
```

Schema purity was run from `/Users/deniskopylov/polisyos/policy-engine`:

```bash
find schemas \( -name '*.py' -o -name '__pycache__' \) -print | tee _build/.tmp/last-mile/schemas-python-residue.txt
test ! -s _build/.tmp/last-mile/schemas-python-residue.txt
```

Final root checks are run from `/Users/deniskopylov/polisyos` after the closeout
commit so `git status --porcelain=v1` proves the committed state.

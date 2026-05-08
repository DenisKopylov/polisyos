---
title: Decomposition Blueprint
status: accepted
adr: ADR-0143
owner: team-scientist/team-foundry
created: 2026-05-03
last_verified: 2026-05-03
stability: phase-3a-baseline
---

# Decomposition Blueprint

This is the accepted Phase 3A plan-first artifact for scientist/foundry decomposition.
It authorizes no physical `.py` moves in `src/polisyos/scientist/` or
`src/polisyos/foundry/`; it only freezes contracts for Phase 5/6.

## ADR-0143 Decision

- Phase 5/6 may start only after all Phase 3A gates are green.
- Current audited counts are 12 Scientist non-facade root modules and 28 Foundry
  non-facade root modules. These counts supersede older draft text that mentioned
  17/22 modules.
- Every old source FQN gets a targeted Python re-export shim; star imports in shims
  are forbidden by ADR-0144.
- Shim sunset arithmetic: max(60 days, 2 x max workflow lifetime) = 604 days.
  Draft sunset date for Phase 5/6 shims: created + 604 days.

## Move Map

| Source FQN | Target FQN | Type | Reasoning |
| --- | --- | --- | --- |
| `polisyos.scientist.decision_validity` | `polisyos.scientist.validation.decision_validity` | public | Decision-validity checks belong with the Scientist validation package. |
| `polisyos.scientist.error_semantics` | `polisyos.scientist.orchestration.engine.error_semantics` | public | Engine error normalization is used by checkpoint/resume flows. |
| `polisyos.scientist.evidence_sources` | `polisyos.scientist.evidence.sources` | public | Evidence source configuration belongs with the evidence package. |
| `polisyos.scientist.feedback_utils` | `polisyos.scientist.feedback.utils` | public | Feedback helpers should move next to the feedback implementation. |
| `polisyos.scientist.frontier_runtime` | `polisyos.scientist.orchestration.engine.frontier_runtime` | public | Runtime capability glue is engine-owned and should not shadow top-level runtime. |
| `polisyos.scientist.latent_separation` | `polisyos.scientist.methods.causal.latent_separation` | public | Latent-separation diagnostics are causal-readiness concerns. |
| `polisyos.scientist.llm_cycle` | `polisyos.scientist.orchestration.llm.cycle` | public | LLM orchestration belongs under the Scientist LLM package. |
| `polisyos.scientist.publisher` | `polisyos.scientist.publishing.publisher` | public | Decision-grade publishing should live under the Scientist publishing package. |
| `polisyos.scientist.reliability_scorecard` | `polisyos.scientist.validation.reliability_scorecard` | public | Reliability scoring is validation/reporting surface. |
| `polisyos.scientist.remediation_status` | `polisyos.scientist.governance.remediation_status` | public | Remediation status is governance evidence, not a package-root module. |
| `polisyos.scientist.replay_backend` | `polisyos.scientist.replay.backend` | public | Replay backend belongs with replay comparators and verification. |
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | internal | Default internal bucket. |
| `polisyos.foundry._registry` | `polisyos.foundry._internal.registry` | internal | Default internal bucket. |

## External Importers

### `polisyos.scientist.decision_validity`
- `src/polisyos/scientist/validation/README.md:20` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:12` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:288` (literal_fqn)

### `polisyos.scientist.error_semantics`
- `tests/repo_quality/architecture/test_last_mile_import_map.py:13` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:292` (literal_fqn)

### `polisyos.scientist.evidence_sources`
- `src/polisyos/scientist/evidence/README.md:15` (literal_fqn)
- `src/polisyos/scientist/evidence/compatibility.py:47` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:14` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:17` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:40` (literal_fqn)
- `tests/unit/scientist/facade/test_phase52_api_extensions.py:19` (import_module)
- `tests/unit/scientist/facade/test_phase52_api_extensions.py:19` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:296` (literal_fqn)

### `polisyos.scientist.feedback_utils`
- `src/polisyos/scientist/evidence/compatibility.py:29` (literal_fqn)
- `src/polisyos/scientist/feedback/AUTHORING.md:9` (literal_fqn)
- `src/polisyos/scientist/feedback/README.md:12` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:15` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:18` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:30` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:300` (literal_fqn)

### `polisyos.scientist.frontier_runtime`
- `tests/repo_quality/architecture/test_last_mile_import_map.py:16` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:304` (literal_fqn)

### `polisyos.scientist.latent_separation`
- `tests/repo_quality/architecture/test_last_mile_import_map.py:17` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:308` (literal_fqn)

### `polisyos.scientist.llm_cycle`
- `tests/repo_quality/architecture/test_last_mile_import_map.py:18` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:312` (literal_fqn)

### `polisyos.scientist.publisher`
- `src/polisyos/scientist/publishing/README.md:8` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:19` (literal_fqn)
- `tests/unit/scientist/facade/test_phase52_api_extensions.py:20` (import_module)
- `tests/unit/scientist/facade/test_phase52_api_extensions.py:20` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:275` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:316` (literal_fqn)

### `polisyos.scientist.reliability_scorecard`
- `src/polisyos/scientist/validation/README.md:22` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:20` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:320` (literal_fqn)

### `polisyos.scientist.remediation_status`
- `tests/repo_quality/architecture/test_last_mile_import_map.py:21` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:324` (literal_fqn)

### `polisyos.scientist.replay_backend`
- `src/polisyos/scientist/evidence/compatibility.py:38` (literal_fqn)
- `src/polisyos/scientist/replay/AUTHORING.md:8` (literal_fqn)
- `src/polisyos/scientist/replay/README.md:12` (literal_fqn)
- `tests/repo_quality/architecture/test_last_mile_import_map.py:22` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:20` (literal_fqn)
- `tests/unit/scientist/evidence/test_phase44_taxonomy.py:35` (literal_fqn)
- `tests/unit/scientist/methods/test_import_shims.py:328` (literal_fqn)

### `polisyos.foundry._quickstart`
- `src/polisyos/foundry/quickstart/__init__.py:23` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:24` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:26` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:30` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:34` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:38` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:41` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:42` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:44` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:48` (literal_fqn)
- `src/polisyos/foundry/quickstart/__init__.py:51` (literal_fqn)
- `tests/unit/foundry/facade/test_quickstart.py:8` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:25` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:774` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py:1625` (literal_fqn)

### `polisyos.foundry._registry`
- `src/polisyos/foundry/calibration/pure_executor.py:23` (literal_fqn)
- `src/polisyos/foundry/compile/_lowering.py:17` (literal_fqn)
- `src/polisyos/foundry/execute/_internal/graph/__init__.py:35` (literal_fqn)
- `src/polisyos/foundry/execute/api.py:50` (literal_fqn)
- `src/polisyos/foundry/extensions/registry.py:147` (literal_fqn)
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:104` (literal_fqn)
- `tests/unit/foundry/methods/test_foundry_v2_unified_runtime.py:4` (literal_fqn)
- `tools/research/demos/run_mechanism_design.py:34` (literal_fqn)

## Planned Re-export Shims

| Shim FQN | Target FQN | Shape | Draft sunset |
| --- | --- | --- | --- |
| `polisyos.scientist.decision_validity` | `polisyos.scientist.validation.decision_validity` | targeted names only | created + 604 days |
| `polisyos.scientist.error_semantics` | `polisyos.scientist.orchestration.engine.error_semantics` | targeted names only | created + 604 days |
| `polisyos.scientist.evidence_sources` | `polisyos.scientist.evidence.sources` | targeted names only | created + 604 days |
| `polisyos.scientist.feedback_utils` | `polisyos.scientist.feedback.utils` | targeted names only | created + 604 days |
| `polisyos.scientist.frontier_runtime` | `polisyos.scientist.orchestration.engine.frontier_runtime` | targeted names only | created + 604 days |
| `polisyos.scientist.latent_separation` | `polisyos.scientist.methods.causal.latent_separation` | targeted names only | created + 604 days |
| `polisyos.scientist.llm_cycle` | `polisyos.scientist.orchestration.llm.cycle` | targeted names only | created + 604 days |
| `polisyos.scientist.publisher` | `polisyos.scientist.publishing.publisher` | targeted names only | created + 604 days |
| `polisyos.scientist.reliability_scorecard` | `polisyos.scientist.validation.reliability_scorecard` | targeted names only | created + 604 days |
| `polisyos.scientist.remediation_status` | `polisyos.scientist.governance.remediation_status` | targeted names only | created + 604 days |
| `polisyos.scientist.replay_backend` | `polisyos.scientist.replay.backend` | targeted names only | created + 604 days |
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | targeted names only | created + 604 days |
| `polisyos.foundry._registry` | `polisyos.foundry._internal.registry` | targeted names only | created + 604 days |

## Pydantic Models And Runtime API Schema Usage

No Pydantic models were found in planned move files.

## JAX/Pydantic Top-level Registrations

- No JAX/Pydantic top-level registrations were found in planned move files.

## Pickle And Checkpoint Inventory

- Call sites: 21
- Live artifacts: 2
- Canonical fixtures: `tests/_data/checkpoint_compat`

## Dynamic Imports

- Registered dynamic import patterns: 199
- Registry: `architecture/imports/dynamic.toml`

## Import Cycles

- Modules in scientist/foundry graph: 1446
- Edges in graph: 3616
- Pre-existing lazy SCCs: 15
- Allowed lazy cycles are frozen in `architecture/imports/lazy.toml`.
- The baseline graph records the collector mode; this workspace uses the internal
  deterministic AST graph because `pydeps`/`import-linter` are not required dev
  dependencies here.

## Baselines

- `architecture/baselines/structure_remediation/import_graph_pre_decomp.json`
- `architecture/baselines/structure_remediation/import_time_pre_decomp.json`
- `architecture/baselines/structure_remediation/pickle_checkpoint_inventory.json`
- `architecture/baselines/structure_remediation/public_surface_pre_decomp.json`
- `architecture/baselines/structure_remediation/schema_diff_pre_decomp.json`
- `architecture/baselines/structure_remediation/tests_baseline.txt`

`tests_baseline.txt` intentionally records a deferred full-suite baseline:
the local `pytest tests/unit tests/integration tests/property tests/contract tests/repo_quality -q`
run was not completed because of thermal load on the laptop. The full baseline
must be run in cloud infrastructure during the final Phase 7 closeout; it is
not a local Phase 3A prerequisite.

## Phase 5/6 Entry Criteria

- `dynamic_imports_gate` green.
- `pickle_compat_gate` green.
- `public_surface_snapshot_gate` green.
- `import_cycles_gate` green.
- `import_time_regression_gate` green in live CI mode.
- `reexport_shim_shape_gate` green.
- Full-suite baseline remains explicitly deferred to the Phase 7 cloud closeout.
- No `.py` files in `src/polisyos/scientist/` or `src/polisyos/foundry/` moved during Phase 3A.

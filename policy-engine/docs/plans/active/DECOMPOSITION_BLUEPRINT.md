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
- Old source FQNs retained as compatibility shims use targeted Python re-exports;
  star imports in shims are forbidden by ADR-0144. The supported-surface contract
  and explicit compatibility map determine whether a prior FQN is retained.
- Shim sunset arithmetic: max(60 days, 2 x max workflow lifetime) = 1170 days.
  Draft sunset date for Phase 5/6 shims: created + 1170 days.

## E02 Candidate Route Update (2026-10-17)

`polisyos.foundry._registry` is not a supported public entrypoint under the
current `architecture/public_surface/contract.toml` internal-by-default rule
and is absent from the Foundry supported-entrypoint list and
`architecture/shims.toml`. This route places runtime mechanism descriptors in
the existing `methods.catalog.mechanism.runtime_registry` owner, migrates the
14 census-bound in-repository references, and removes the old private module
instead of retaining an unregistered re-export. The supported Foundry facade
exports, `methods.selection.registry.__all__` (including
`get_registry_audit_log`), and the extension-registry binding remain unchanged.
The focused test imports the retired FQN in a clean module-cache state and
requires `ModuleNotFoundError` for that exact name.

The source-bound census does not observe external imports or persisted external
pickle stores. Their populations remain `not_established`; this route makes no
claim that external uses do not exist. It creates no shim registration or
compatibility sunset date for this private path.

The _quickstart route treats the old module as an unlisted internal helper, not a
supported facade entrypoint. The routine candidate moves the complete existing
implementation verbatim into the already-owned
polisyos.foundry._internal.quickstart, migrates every current repository
importer, and deletes the old module without a compatibility shim or new
facade export. Compile/execute behavior, CAS artifact contracts, CPU-first JAX
defaults, and result field names stay the same; the dataclass __module__
identity naturally follows the new owner. External imports and persisted
pickles remain not_established, so this route makes no compatibility claim.
Pattern pass: P06/P28/P31/P40; target is one existing owner with complete caller
migration, and acceptance requires actual CAS-path tests plus old-import removal.

## Move Map

| Source identity | Target FQN | Type | Reasoning |
| --- | --- | --- | --- |
| Pre-move `polisyos.foundry._quickstart` at the pinned baseline below | `polisyos.foundry._internal.quickstart` | internal | Existing owner; migrate the measured repository callers and remove the old module without a shim. The source FQN is retained here as a dated migration input, not a current import route. |
| `polisyos.foundry._registry` | `polisyos.foundry.methods.catalog.mechanism.runtime_registry` | internal | The unlisted private FQN is retired after repository references migrate to the existing mechanism-catalog owner; external use remains unestablished. |

## Repository Import References

The candidate distinguishes active target references from historical source references. The target references below are expected in the R3 postimages after root adoption; they do not establish that the runtime or generated inventories have already been adopted.

### Candidate target imports after the move (R3 postimages)

Direct importing modules routed to `polisyos.foundry._internal.quickstart`:
- `apps/runtime-dashboard/scripts/fixture_support/catalog_profile_source_fixture.py:254`
- `tests/integration/runtime_quality/test_workflow_post_data_view_profile_binding.py:32`
- `tests/unit/foundry/calibration/test_identifiability_response_basis.py:156`
- `tests/unit/foundry/compile/test_trinity_compiler.py:124`
- `tests/unit/foundry/facade/test_quickstart.py:26, 89, 241`
- `tests/unit/foundry/runtime/test_execute_feedback.py:23`
- `tests/unit/foundry/validation/test_release_gate.py:17`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py:51`
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:773, 1380`
- `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py:1626`

Other active target references in the candidate postimages:
- `src/polisyos/foundry/README.md:200`
- `tests/repo_quality/tools/test_docs_gate.py:348`
- `docs/tutorials/getting-started.md:100`

### Historical pre-move references (Git baseline only)

The old module identity and the following locations are a snapshot of the pre-move repository state, not a list of current imports. The Git anchor is commit `3d07f60e617e20814e7d5ba049a0b66d6db78974` (tree `02d8efdf9682035544a12492c99074c1c2bef529`, committed `2026-10-17T17:53:12+03:00`). At that revision `src/polisyos/foundry/_quickstart.py` existed with content SHA-256 `9b7215b46cc926df088fddd451fd8c3444a13d1ef3b9450e0a4c0f0aeb41d8b4`. The baseline Git path, not the spelling of the old FQN alone, anchors this record.

Direct importing modules in the corrected pre-move census were:
- `apps/runtime-dashboard/scripts/fixture_support/catalog_profile_source_fixture.py:254`
- `tests/integration/runtime_quality/test_workflow_post_data_view_profile_binding.py:32`
- `tests/unit/foundry/calibration/test_identifiability_response_basis.py:156`
- `tests/unit/foundry/compile/test_trinity_compiler.py:124`
- `tests/unit/foundry/facade/test_quickstart.py:25, 88, 240`
- `tests/unit/foundry/runtime/test_execute_feedback.py:23`
- `tests/unit/foundry/validation/test_release_gate.py:17`
- `tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py:51`
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:773, 1380`
- `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py:1626`

The corrected baseline census covers 12,963 eligible current files and 50 hit files; it is the authority for the historical/current role partition. The R3 manifest's `historical_records_preserved` list is not exhaustive: the corrected census additionally classifies `docs/archive/reports/MSME_POLICYOS_FINAL_EXPERIMENT_SUITE_2026-05-01.md` and `docs/archive/reports/REPOSITORY_BEST_IN_CLASS_PHASE_0_5_SOURCE_COMPLEXITY_INVENTORY.md` as historical records, and both remain unchanged. Do not infer a complete archive-history list from the R3 manifest or treat a matching string by itself as an active import.

### `polisyos.foundry._registry` (retired private path)

The source-bound census records 14 in-repository references across 14 Python
paths; its denominators are 25,391 tracked product paths (7,643 tracked Python
paths) and 6,288 maintained application Python files in `apps/`, `src/`,
`tests/`, and `tools/`. The candidate migrates these call sites to the canonical
mechanism catalog owner:
- `src/polisyos/foundry/calibration/pure_executor.py:26`
- `src/polisyos/foundry/compile/_lowering.py:21`
- `src/polisyos/foundry/execute/_internal/graph/__init__.py:65`
- `src/polisyos/foundry/execute/api.py:106`
- `src/polisyos/foundry/extensions/registry.py:238`
- `src/polisyos/foundry/methods/catalog/mechanism/runtime.py:131`
- `tests/unit/foundry/execute/mechanisms/test_fiscal_labor_replay.py:11`
- `tests/unit/foundry/execute/mechanisms/test_fiscal_precision.py:11`
- `tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py:11`
- `tests/unit/foundry/methods/test_foundry_v2_unified_runtime.py:6`
- `tests/unit/foundry/plugins/test_economic_profile_consumers.py:9`
- `tests/unit/foundry/plugins/test_economic_profiles.py:12`
- `tests/unit/remediation/test_fry_03.py:86`
- `tools/research/demos/run_mechanism_design.py:35`

This is a repository-scoped inventory, not evidence about external adoption.

## Planned Re-export Shims

| Shim FQN | Target FQN | Shape | Draft sunset |
| --- | --- | --- | --- |

The `_quickstart` and `_registry` FQNs are intentionally absent from this
compatibility table: both are internal under the current public-surface contract
and are removed after their enumerated repository references migrate. No
external non-use claim is made.

## Pydantic Models And Runtime API Schema Usage

No Pydantic models were found in planned move files.

## JAX/Pydantic Top-level Registrations

- No JAX/Pydantic top-level registrations were found in planned move files.

## Pickle And Checkpoint Inventory

- Call sites: 21
- Live artifacts: 2
- Canonical fixtures: `tests/_data/checkpoint_compat`

## Dynamic Imports

- Registered dynamic import patterns: 201
- Registry: `architecture/imports/dynamic.toml`

## Import Cycles

- Modules in scientist/foundry graph: 1173
- Edges in graph: 3424
- Deferred SCCs remain in the full AST baseline and the historical inventory in `architecture/imports/lazy.toml`.
- The blocking gate checks source-resolved module-initialization calls supported by the deterministic AST binding collector, including direct construction, tracked instances, and joined class-member values.
- Source-known calls whose factory return, custom-`__new__` allocation, rebound receiver, or possible binding target remains unresolved produce machine-readable `not_established` rows and fail the gate. Direct source-base method targets are followed; unresolved base-constructor dispatch remains fail-closed.
- One `_BindingKnowledge` value carries every known value variant and the possible-unknown bit through function, module, and class-member exports; joins union targets and OR uncertainty, so one known candidate cannot erase another path.
- Source-value origins remain attached through aliases, attributes, subscriptions, containers, branch joins, and module/class exports, and through the collector’s shared binding sink for augmented assignments, loops, context managers, exception captures, match captures, and comprehensions. Attribute/subscript member state is keyed by source class identity or allocation-site instance identity rather than a variable spelling, so alias chains, rebinding, and branch joins share the same owner/member relation. A store through several possible owners retains uncertainty for each owner instead of asserting that every candidate received the write. Unsupported owner identities and cross-module mutable-owner snapshots remain `not_established`; the two-pass export does not claim module mutation order. Direct attribute/subscript stores, deletes, and builtin `setattr`/`delattr` updates share one owner-member effect transfer. A strong update requires one guaranteed mutator, owner, and key on every joined path; possible writes weakly join prior and new source origins, while dynamic keys use a wildcard member state that reads retain. Branches with no write and multi-owner effects preserve alternatives. Untrackable owners or keys are reported as `not_established` rather than disappearing. Iteration, context-manager, exception, and nested-pattern captures retain unknown value shape; the collector does not invent element or return types. Comprehension target bindings are restored at the expression boundary. For an indexed source free-function call with an indexed signature, source-owned arguments are mapped across positional-only, positional-or-keyword, keyword-only, `*args`, and `**kwargs` formals using Python signature binding. Positional and keyword-only defaults retain the source-value knowledge captured when the function is defined, even if the name used in the default expression is later rebound; an explicit actual overrides that captured default. Literal tuple/list and string-key dictionary expansions are mapped when their shape is known; unresolved expansions and source-derived arguments whose formal is referenced by the callee body remain machine-reported as `not_established`. Indexed source callees outside the free-function signature shape retain source-origin actuals and referenced captured defaults as `not_established`. The collector does not invent callback edges. Unrecognized indirect and reflective calls remain outside this bounded scope; the collector does not claim whole-language module-eager completeness. `TYPE_CHECKING` and uncalled function bodies are deferred.
- A deferred-cycle entry never suppresses a source-resolved module-eager cycle.
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

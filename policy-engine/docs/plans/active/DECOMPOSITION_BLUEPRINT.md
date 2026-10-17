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
compatibility sunset date for this private path. Existing unrelated shim and
exception rows remain unchanged.

## Move Map

| Source FQN | Target FQN | Type | Reasoning |
| --- | --- | --- | --- |
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | internal | Default internal bucket. |
| `polisyos.foundry._registry` | `polisyos.foundry.methods.catalog.mechanism.runtime_registry` | internal | The unlisted private FQN is retired after repository references migrate to the existing mechanism-catalog owner; external use remains unestablished. |

## Repository Import References

### `polisyos.foundry._quickstart`
- `src/polisyos/foundry/README.md:97` (literal_fqn)
- `tests/repo_quality/tools/test_docs_gate.py:279` (literal_fqn)
- `tests/unit/foundry/facade/test_quickstart.py:8` (literal_fqn)
- `tests/unit/foundry/runtime/test_execute_feedback.py:25` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:774` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_e2e_showcase.py:1380` (literal_fqn)
- `tools/ops_runners/experiments/run_msme_grand_tournament_v2.py:1627` (literal_fqn)

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
| `polisyos.foundry._quickstart` | `polisyos.foundry._internal.quickstart` | targeted names only | created + 1170 days |

The `_registry` FQN is intentionally absent from this compatibility table: it is
unlisted/internal under the current public-surface contract and is removed after
the enumerated repository references migrate. No external non-use claim is made.

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

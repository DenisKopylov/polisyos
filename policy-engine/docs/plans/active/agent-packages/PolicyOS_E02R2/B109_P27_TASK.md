# B109 / P27 — use the existing Pareto owner on the served search path

**Status:** partial. The accelerated mathematical comparator has current four-base passing evidence, but the default hierarchical-search path bypasses the typed owner. The class-wide served behavior, write-set replay, removal probe, and control are `UNRUN`; this task does not close B109 or imply production registration of ParetoRegistry.

## Property and owner chain

For a registered hierarchical-policy-search run, the persisted `PolicyFrontierReport.global_frontier` and the downstream output bundle must reflect the existing `ParetoRegistry` snapshot for that run and its typed vector directions. A node-local `evaluation.feasible` flag cannot label every feasible candidate `global_feasible`.

Reuse the existing `ParetoRegistry.update` / `global_feasible` / `ParetoPromoter.compute_front` owner. Current served chain: registered workflow → `RunHierarchicalPolicySearchNode` → adapter/coordinator → node report artifact → `BuildPolicyOutputBundleNode` and translation consumers. The default adapter does not inject a registry; the node marks all feasible records as global frontier. The output path reads `pareto_registry_snapshot`, but the source census found zero production writes to that state field. The repository census also found zero production `ParetoRegistry(...)` constructions. Thus the current default path has a producer/consumer wiring gap; do not construct a global `.polisyos/search_registry` in the node or infer tenant/loop scope.

The existing 2D/3D equality-secondary comparator tests and independent oracle pass in all four bases (test_pareto.py: 8/25/8/25). That is the comparator only, not served frontier closure.

## Required served witness, removal probe, control

- **Positive:** execute the registered node and production adapter/coordinator with feasible vectors A=(2,1), B=(1,1), both maximizing. Preserve the registry snapshot through the ordinary state/artifact path and output builder. Persist/reload both reports; only A's hash may be `global_feasible`.
- **Removal probe:** with DTOs and markers intact, restore the old node rule “every feasible evaluation is global_feasible” / bypass registry membership. The same served witness must turn red because B appears.
- **Preserving control:** two distinct candidates with identical vectors (2,1) remain both on the frontier under strict dominance.
- **Scope control:** candidate search must still proceed when tenant/loop registry scope is unknown, while cross-run transfer/frontier claims stay limited; bind any registry/snapshot to the runtime tenant/cell and run owner.

No current runtime registry provider or snapshot writer is established. Wire the existing owner at the composition boundary and pass the same typed snapshot to the node artifact and downstream consumer; preserve evaluated-but-not-frontier records for audit. Do not duplicate the comparator or make candidate frontier output an authority/promotion signal.

## P41 before any source/test edits

The complete targeted denominator is six whole files, present at all four pinned refs. Only `tests/unit/scientist/methods/autotune/test_pareto.py` is already in the current matrix and measured; the other five need broker admission before edits:

1. `tests/unit/scientist/methods/autotune/test_pareto.py` — retain recorded 8/25/8/25 outcomes.
2. `tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py`.
3. `tests/unit/scientist/search/test_phase_b_policy_runtime.py`.
4. `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`.
5. `tests/unit/scientist/nodes/test_build_policy_output_bundle.py`.
6. `tests/unit/scientist/orchestration/workflows/test_workflow_specs.py` if DAG registration/binding changes.

Run each entire admitted file at all four bases before source changes. If the patch enters the legacy frontier adapter or strategy helper, add its whole-file P41 path under B111/R11 rather than silently expanding this denominator.

## Evidence and scope

Source/design: `/Users/deniskopylov/.codex/scratch/e02-r2-b109-p27-design-20260925.md@sha256:9eb1de15e2a42bd4c6182aad76efb6b75026461f034d3a4e5d9ea02514c8ab0b`.

The source report assigns the owner-bypass instance to the same P27 class as B109's frontier-correctness boundary. GY-PR1 and Atlas DS12 remain blocked; candidate search/frontier wiring advances neither to closure. No exact B109-to-live-register or Atlas row edge is established in the current CROSSWALK, so this task proposes no debt-register edit or closure.

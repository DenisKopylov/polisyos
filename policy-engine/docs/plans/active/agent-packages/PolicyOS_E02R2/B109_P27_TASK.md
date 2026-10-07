Current criterion-scope correction: [B109/B111/B100 errata](../../../../research/e02-cloud-test-plan/integration/reviews/original-criteria-errata-2026-10-06.md). B109 is fast/direct comparator acceptance; the served provider is additional capability. B111 keeps invalid-state/partial-denominator/finite-or-unavailable semantics; schema-v3 migration and finite-positive underflow are separately scoped. Historical outcomes and status counts below are retained.

# B109 / P27 — use the existing Pareto owner on the served search path

**Status:** partial. The local comparator has a bounded 31/31 whole-file witness at `0cf4afa19`, but the exact current six-file four-base cohort and registered served behavior remain `UNRUN`. Earlier 8/25/8/25 whole-file counts use different case sets; they are not four-base outcomes for the later 31-case file. This task does not close B109 or imply production registration of `ParetoRegistry`.

## Property and owner chain

For a registered hierarchical-policy-search run, the persisted `PolicyFrontierReport.global_frontier` and the downstream output bundle must reflect the existing `ParetoRegistry` snapshot for that run and its typed vector directions. A node-local `evaluation.feasible` flag cannot label every feasible candidate `global_feasible`.

Reuse the existing `ParetoRegistry.update` / `global_feasible` / `ParetoPromoter.compute_front` owner. Current served chain: registered workflow → `RunHierarchicalPolicySearchNode` → adapter/coordinator → node report artifact → `BuildPolicyOutputBundleNode` and translation consumers. The default adapter does not inject a registry. When the search result has no projection, the node builds an unranked, basis-limited projection; denominator reconciliation preserves the candidate/unknown records in `candidate_frontier`, sets `denominator_limited`, and persists an empty `global_frontier`. The current no-registry fallback does not mark every feasible record as globally ranked. The output bundle and translation paths read `pareto_registry_snapshot`, but the 612a source census found no production writer or literal `ParetoRegistry(...)` construction. Thus the remaining gap is the registered owner/provider and persisted-consumer bridge; do not construct a global `.polisyos/search_registry` in the node or infer tenant/loop scope.

The retained local comparator receipt is 31/31 at `0cf4afa19`, with a marker-retaining comparator-removal probe. The historical whole-file counts 8/25/8/25 use different selector sets and are not a four-base replay of the later 31-case file; the exact 2D/3D selectors are absent at execution and main. This bounded evidence does not close served frontier behavior.

## Required served witness, removal probe, control

- **Positive:** execute the registered node and production adapter/coordinator with feasible vectors A=(2,1), B=(1,1), both maximizing. Preserve the registry snapshot through the ordinary state/artifact path and output builder. Persist/reload both reports; only A's hash may be `global_feasible`.
- **Removal probe (after the registered provider path exists):** keep DTOs and markers intact, then remove or bypass the registered report path’s binding to admitted registry membership. The same served witness must turn red because dominated candidate B enters `global_frontier`. This probe is currently `UNRUN`: the positive registered provider path is not wired, and the old “mark every feasible evaluation global” rule is already absent from the current no-registry fallback.
- **Preserving control:** two distinct candidates with identical vectors (2,1) remain both on the frontier under strict dominance.
- **Scope control:** candidate search must still proceed when tenant/loop registry scope is unknown, while cross-run transfer/frontier claims stay limited; bind any registry/snapshot to the runtime tenant/cell and run owner.

No current runtime registry provider or snapshot writer is established. Wire the existing owner at the composition boundary and pass the same typed snapshot to the node artifact and downstream consumer; preserve evaluated-but-not-frontier records for audit. Do not duplicate the comparator or make candidate frontier output an authority/promotion signal.

## P41 before any source/test edits

The complete targeted denominator is six whole files, present at all four pinned refs. `test_pareto.py` has recorded whole-file counts 8/25/8/25 at different selector sets and a separate 31/31 witness at `0cf4afa19`; these do not constitute one consistent current four-base result. The other five files need broker admission before edits:

1. `tests/unit/scientist/methods/autotune/test_pareto.py` — reconcile selector identities and run the complete file at all four bases; historical 8/25/8/25 totals and the later 31/31 run are different case sets.
2. `tests/unit/scientist/policy_design/test_phase_b_hierarchical_search.py`.
3. `tests/unit/scientist/search/test_phase_b_policy_runtime.py`.
4. `tests/unit/scientist/nodes/builtins/planning/test_run_hierarchical_policy_search.py`.
5. `tests/unit/scientist/nodes/test_build_policy_output_bundle.py`.
6. `tests/unit/scientist/orchestration/workflows/test_workflow_specs.py` if DAG registration/binding changes.

Run each entire admitted file at all four bases before source changes. If the patch enters the legacy frontier adapter or strategy helper, add its whole-file P41 path under B111/R11 rather than silently expanding this denominator.

## Evidence and scope

Source/design: `/Users/deniskopylov/.codex/scratch/e02-r2-b109-p27-design-20260925.md@sha256:9eb1de15e2a42bd4c6182aad76efb6b75026461f034d3a4e5d9ea02514c8ab0b`. The current fallback/provider census and full documentation claim review are pinned at `/Users/deniskopylov/.codex/scratch/E02R2_OPT01_INDEPENDENT_REVIEW_612a78f_20261002.md@sha256:3daa3e5933700579bf360b637afdc209970240ddcba423412bb4807985d9a60c`; no tests were run by that review.

The source report assigns the owner-bypass instance to the same P27 class as B109's frontier-correctness boundary. GY-PR1 and Atlas DS12 remain blocked; candidate search/frontier wiring advances neither to closure. No exact B109-to-live-register or Atlas row edge is established in the current CROSSWALK, so this task proposes no debt-register edit or closure.

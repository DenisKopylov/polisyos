# CYC-05 — retire removed HTTP context-builder caller

## Discrepancies first

Before migration the whole test file was UNRUN at collection: it imported the
retired `_build_cycle_substrate_context_from_owner`. A rootless early-return
proxy test is retired with that removed mechanism; the existing served unknown
world-scope witness exercises ordinary candidate work and no implicit context.
This test migration does not restore a checkout-manufactured owner context.

The candidate AST census is 18 test functions / 20 expanded cases after
retirement. Three source-currentness checks retain older R2 expectations and
are diagnostics; current semantics and actual outcomes must be measured below.
The controlled-profile helper can still stop on the known five-slot R1 mismatch.
Neither those reds nor the retired helper are automatically classified inherited.

## Change and behavioral controls

Only `tests/unit/remediation/test_cyc_05.py` changes: remove the retired import
and proxy test; bind the mismatch negative to its exact compiled problem via
existing `_cyc01_owner_bound_n5_case(problem_seed=...)`, select simulate-only,
remove the stale monkeypatch, preserve the no-controller-run sentinel and exact
error assertion. All other assertions remain. No runtime source changes.

- `/Users/deniskopylov/.codex/scratch/e02-r2-bounded-census-integration-20260930/B26_CYC05_MIGRATION_CANDIDATE_20261001/B26_CYC05_MIGRATION.patch@sha256:5d98246daffa28da23e24026cfc91ee1e5254437e5595a0475c9abad63d72445`
- `/Users/deniskopylov/.codex/scratch/e02-r2-bounded-census-integration-20260930/B26_CYC05_MIGRATION_REVIEW_R1.md@sha256:8bbfa3b9ab4c5c81d94fcb204f946bb209afaabcd957a2a144762025c0bc3dd6`

## Whole-file result

Actual V2 whole-file command exits **1**: **20 cases = 13 PASS, 7 FAIL**, zero ERROR/SKIP. Collection now succeeds. Wall time 37.22 seconds, peak RSS 1,069,449,216 bytes, zero swaps. The origin audit passes over all 1,723 loaded product modules, one test module, 12 test/support modules and 31 frozen inputs; zero foreign origins and zero input drift. The test bytes are unchanged after that run. Canonical Ruff passes the migrated file as part of the 20-file B61/CYC-05 denominator.

The seven remaining failures are recorded rather than waived:

- `test_http_job_progress_exposes_requested_and_effective_recursive_limits`: absent `recursive_budget_resolution` after the request stays on the N4 candidate proposal path. R1 candidate/recursive semantics must distinguish this from a completed N6 run.
- `test_generation_cycle_consumer_rejects_stale_source_receipt`: expected `strangled`, actual `not_established`; the synthetic old receipt lacks current deployment evidence. R2 historical validity/currentness must be tested separately.
- `test_workspace_fixture_children_flow_through_recursive_graph_and_n5`, the three `test_recursive_parent_blocks_without_n5_or_composition_for_missing_inputs` variants, and `test_recursive_parent_blocks_for_wrong_parent_workspace_identity`: the fixture's substituted N9 owner is refused by `recursive_contract_testing_candidate_n9_owner_not_established` before their intended parent/N5 assertions. These checks need a candidate-only execution path with honest owner wiring; their assertions are not relaxed here.

The red ownership is **not established** by this current-only run; none is called inherited or a base-to-head regression without the exact four-base replay. The narrow retired-caller repair is delivered; R1/R2 substantive follow-up and the full four-base CYC-05 cohort remain open.

- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/FROZEN_INPUTS.v2.json@sha256:399ea523afbb27764db9b3fb780b9937dd6bfb58cb646c26d079e24f20c04707`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/cyc05-v2.junit.xml@sha256:e827781fba5e836ef844c13a9b3ca0869761a19868e7fccdf2124ed5a94e88be`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/cyc05-v2.log@sha256:3b28f5ba0526bd31145026b0751ee555d542d3002b6dfe5eab115da01f488abe`
- `/Users/deniskopylov/.codex/scratch/e02-b61-cyc05-integrated-1366-20261001/cyc05-v2.origins.json@sha256:1f64c93fb843b4c1291d7dfad720b870c49c11919a31522bf73cca9d7f60d5ab`

The post-run receipt update changes documentation only. The complete outputs remain outside the worktree.

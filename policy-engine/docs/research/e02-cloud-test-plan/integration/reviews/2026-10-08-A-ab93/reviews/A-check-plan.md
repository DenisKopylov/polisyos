# A bounded checks and merge-intake plan

Planning-only: no tests, exports, environment setup, refs, or tracked source were changed.

## Merge range and review boundary

The exact A candidate is ab93e222381372c54056b9f05e6c8cd7aedf2f2c, tree ee92f0719be5b02e212947dcd35f90a1276e875f. Its prior candidate is 332ba0b91e9a85774d48d101d4af86e3a3baf911; the exact candidate delta is 270 paths, with 17 implementation/test paths. The full commit list and path denominator are in the companion JSON.

An ordinary merge into G is much broader: common base 198076863e143dea9f89f02734b13d50dae3eed5; 324 G-only and 197 A-only commits. git cherry reports all 197 A commits patch-unique and none equivalent in G. A changes 1,192 paths from that base: 1,112 E02 research/evidence files, 51 test files, 23 production src/polisyos files, 2 runtime-client files, dashboard API types, the OpenAPI snapshot, and 2 public-surface outputs. These include cross-layer source under Core contracts, Foundry selection, runtime HTTP/quality, and Scientist LLM/policy-design search. A successful merge-tree does not accept this code.

The read-only merge-tree preview reports three conflicts:

- architecture/public_surface/inventory.json and docs/reference/public-surface.md: both are generated from source and need regeneration on the final composition.
- implementation-handoffs/A/compiler-full/census_tracked_python.py: add/add. G has its earlier installed-compiler slice; A’s later commit 1a520b209ce4bac86204137d15e765de05c08a73 adds lexical-scope alias handling. This is a new delta, not accepted by G’s earlier version.

Do not merge the full A ancestry as accepted. Accept bounded reviewed commits sequentially, and rerun affected checks on the composed source.

## Exact-candidate test plan

At the latest read-only snapshot, no matching pytest, uv, ruff, API-contract, or pnpm process was visible; G disk reported 41 GiB free. Existing G .venv has Python 3.14.3, pytest 9.0.2, pytest-asyncio 1.3.0, FastAPI 0.128.6, httpx 0.28.1, Pydantic 2.12.5, NumPy 2.3.5, JAX 0.8.2, DuckDB 1.4.3. This supports a Python-only bounded wave without setup. Node/pnpm was not inspected or run.

From a disposable checkout of exact A, use the existing G interpreter and candidate src; never use the mutable G worktree as the candidate. Select these exact functions:

- tests/unit/remediation/test_emp_01.py::test_default_cycle_preserves_simulation_only_result_and_history — reruns the old G332 failure, which this candidate changes.
- tests/unit/runtime/quality/test_e02_interaction_history_epoch.py::test_actual_default_n5_n8_interaction_history_is_versioned_and_replayable and tests/unit/runtime/quality/test_generation_cycle_history.py::test_v5_history_preserves_typed_conditional_interaction_evidence — real synthetic N5→N8 history and typed v5 wire mapping.
- tests/unit/runtime/quality/test_generation_cycle.py::test_prepared_n5_ignores_unconsumed_candidate_input_for_ksim and ::test_joint_port_two_refusals_persist_no_run_and_n8_refuses — actual-use blocker and persisted no-run refusal.
- tests/integration/core_runtime/test_e02_manual_n5_interaction_readback.py::test_manual_n5_interaction_evidence_is_recomputed_by_fresh_run_details_get — fresh GET for conditional result and static-engine refusal.
- tests/integration/core_runtime/test_e02_served_cycle_custody.py::test_served_candidate_value_fresh_get_with_candidate_only_substrate — served GET under synthetic candidate-only inputs.
- tests/integration/core_runtime/test_e02_recursive_partial_readback.py::test_partial_checkpoint_survives_owned_core_cas_and_fresh_run_details_get — partial-v2 schema through owned CAS and GET.
- tests/integration/core_runtime/test_e02_terminal_status_readback.py::test_n6_terminal_decision_and_iteration_survive_history_readback — all three parameterized terminal outcomes.
- tests/integration/runtime_quality/test_e02_required_numeric_container_intake.py::test_registered_ncm_output_damage_is_refused_with_distinct_reasons, ::test_registered_ncm_direct_zero_remains_a_numeric_zero, ::test_registered_coupled_queue_output_damage_is_refused, ::test_registered_coupled_direct_zero_queue_remains_numeric_zero, and ::test_malformed_owner_ncm_reason_survives_n6_cas_history — distinct missing/malformed/non-finite refusals, true zero, and persisted reason.
- tests/integration/runtime_quality/test_e02_registered_engine_applicability.py::test_registered_stock_flow_valid_slots_reach_the_real_producer and ::test_expected_applicability_rejects_a_changed_request_before_producer — supported real producer path and changed-request negative.

Command template, from the disposable exact-A policy-engine root:

    env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 JAX_PLATFORMS=cpu OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 <GROOT>/policy-engine/.venv/bin/python -m pytest -o addopts= --import-mode=importlib --strict-markers -q -p no:cacheprovider --basetemp=<unique-run-dir>/pytest-tmp --junitxml=<unique-run-dir>/junit.xml <exact selectors above>

Use the complete real src/polisyos tree (no empty stubs), complete tools tree for N4/N5 validators, selected tests and recursive helper closure, real package __init__.py files, tests/conftest.py, tests/unit/runtime/conftest.py, and candidate pytest/project config. Previously measured sizes: src/polisyos 54,990,236 bytes; tools 12,516,371 bytes; entire tests 32,455,454 bytes, but only exact selected tests and their imported closure are needed. Include the exact synthetic N4/N5 architecture assets pinned in JSON, including the 1,825-byte claim-dependency registry. Hash all selected inputs/modes before and after and capture every loaded polisyos/tools module origin and SHA. Retain raw stdout/stderr, JUnit, wall/RSS, and temp outputs under a unique ignored run directory. No production data or N9-positive test is required.

After the positive manual fresh-GET test, run its two in-memory removal controls separately: set POLISYOS_E02_CANDIDATE_LIMITER_REMOVAL=1 and select the conditional-result case, then POLISYOS_E02_N5_REFUSAL_BRANCH_REMOVAL=1 and select static-engine-refusal. Expect a semantic assertion red after removing the real property; setup/import errors are not a valid falsifier.

The exact default-cycle history test previously failed on G332 with generation_cycle_historical_projection_mismatch in 23.879 seconds. It changed in the current candidate and must be rerun; failure provenance stays not_established because the slice base was not replayed. Do not repeat four unchanged G332 PASS selectors only due to SHA movement. The combined wave has no measured runtime; use one 240-second outer harness cap, capture wall/RSS, and avoid aggressive per-test caps. This remains bounded code verification, not acceptance of A’s other 197 commits or finding closure.

## Runtime API and public-surface freshness

A adds a RunDetails DTO/field in earlier A commits. Its OpenAPI/client outputs need fresh verification: prior 5MATCH b3de is stale after runtime source/digest changes. Verify exact A output now, then rerun these owner checks on the eventual G+A composition; do not confuse that with resolving generated merge conflicts.

- Runtime OpenAPI snapshot: source is src/polisyos/runtime/http/**. Export to scratch with PYTHONPATH=src:. <GROOT>/policy-engine/.venv/bin/python tools/ops_runners/runtime/export_runtime_openapi.py --output <probe>/schemas/runtime_api_v1.openapi.json and compare bytes. Targeted check: PYTHONPATH=src:. <GROOT>/policy-engine/.venv/bin/python tools/ops_runners/runtime/check_runtime_api_contract.py --skip-client-drift. Inputs include runtime HTTP source, both tools/ops_runners/runtime scripts, tools/lib/imports.py, pyproject.toml, existing runtime/ml dependencies, and schemas/runtime_api_v1.openapi.json.
- Runtime client: corepack pnpm --filter @polisyos/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json --output-root <probe-root>; compare types.ts, canonicalRuntimeApiClient.ts and .js. The full check_runtime_api_contract.py (without --skip-client-drift) also performs a temporary generated-client comparison.
- Dashboard API types: corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json --output-root <probe-root>; compare apps/runtime-dashboard/src/api/types.ts.
- Public-surface outputs: owner is tools/devx/architecture/guardrails.py. Canonical sync is uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline; run only in a disposable derived candidate or direct --public-json, --public-md, and --generated-md to scratch, then compare candidate bytes. It uses architecture/public_surface/contract.toml and real source facades. The final G+A composition must regenerate both conflicted outputs.

Client/dashboard checks were not run and pnpm dependencies were not checked. A fresh checkout must follow AGENTS.md and run corepack pnpm install --frozen-lockfile before trusting any TypeScript scanner. Missing pnpm inputs are UNRUN/setup, not product failure. Python freshness and selected runtime tests remain independently runnable.

Pattern pass: P29/P32/P37/P38/P41. Use actual producer/readback behavior, typed history, removal/negative controls, and canonical generators. Passing this plan establishes only the selected exact-A runtime properties; it does not prove production grounding, N9, dashboard rendering, whole finding closure, or the 197-commit ancestry.

# DX0 JAX bootstrap and data-family fallback assessment

Date: 2026-10-10  
Candidate: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`

## JAX bootstrap repair

Three research entrypoints now call the existing `polisyos.common.jax_env.apply_jax_env_defaults()` after establishing the source import path and before importing Equinox/JAX:

- `tools/research/benchmarks/jax/bench_simulation.py` @ `7b887ac6dca0a2c0616a06ebfa5044c5b99ccf5f2077c786a86a34dbd0e578f9`
- `tools/research/demos/run_laffer_demo.py` @ `f98f45075177d96a22f40a26663921edd3244b4998a1fde7ab3fbb70bd1455b7`
- `tools/research/demos/run_mechanism_design.py` @ `517a6090b5d6bd7517e90c81fa3ee8eded4bd6f728b619e39b047fb968597061`

The third path had two direct CPU `setdefault` calls. With `JAX_PLATFORMS=metal` and `POLICY_ENGINE_ALLOW_JAX_METAL=1`, it still injected `JAX_PLATFORM_NAME=cpu`, diverging from the canonical helper. The test-first reproduction is retained at `LOCAL/decisions/raw/dx0-jax-order-third-entrypoint-red.log` @ `8897ef45e27f7db2c70bc153143774f2658a17803b33e50d6d060e4fc3a799ac`: the two prior direct callers passed and all three `run_mechanism_design.py` profiles failed; the platform-only Metal case observed `("metal", "cpu")` where the shared helper requires `("metal", None)`.

The HYG-04 source-bound subprocess guard now covers all three entrypoints under four environments: no operator setting, both explicit Metal variables, only `JAX_PLATFORMS=metal`, and only `JAX_PLATFORM_NAME=metal`; Metal cases set the existing opt-in. It simulates Darwin, instruments the real shared helper, stops at the first Equinox/JAX import, and asserts that no JAX module loaded. The final command passed all 12 cases:

```text
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA tests/unit/remediation/test_hyg_04.py -k jax_research_entrypoints_apply_defaults_before_jax_stack
12 passed, 14 deselected in 0.77s
```

Full output: `LOCAL/decisions/raw/dx0-jax-order-three-entrypoints-final.log` @ `d88da435cd9acb3083fff550f2c416b1491a2c72436b7e6c3bbcb3ba6b0f735d`.

The complete current `tools/research/**/*.py` census found 30 Python files, parsed all 30 with zero syntax failures, and found four files with JAX/bootstrap events. The three direct JAX importers above each call the helper before Equinox/JAX; `tools/research/benchmarks/jax/bench_domain.py` remains the existing `jax_bootstrap` compatibility-shim route, imported before downstream libraries. The benchmark wrapper files do not add JAX imports. The source-bound census is `LOCAL/decisions/raw/dx0-jax-post-repair-census-20261010.json` @ `a48823bd143e81484800098bbad841f7a90adb4acc3c16b1fa85c9266897d561`. Its pre-repair input/census counterpart is `LOCAL/decisions/raw/dx0-jax-data-requirements-20261010.json` @ `0c90c7493dcc3d851e9655b0edaa2c05d655ad74c2162e9989ea596ff79be9ca`.

The current test file `tests/unit/remediation/test_hyg_04.py` @ `4c8504a43cc9d1f8e401dc2719b62d5a17e704aab653a32ccaf2c19145939c3e` retains the legacy bootstrap/shim tests. The docs changed are `tools/research/demos/README.md` @ `4c06524484c09b91420633e12c2b9dcfd90a8b45e7b57084a4f26bc0c2e37a8d` and `tools/research/benchmarks/README.md` @ `4080cac5b06d027a44eb3c6520a302a8e3bfb7d80c5b7a6bb18b4ad8f6e660f1`. `jax_bootstrap.py` @ `a310ba39e82c2e338cde1b454f053b62b8bfc6fb741e8c4e748b36ee6071b5ce`, `src/polisyos/common/jax_env.py` @ `c47cae7faa16a86b0353ba95149a3a9d3ba1c26f2e0f39bbdae78277d89214e1`, `architecture/shims.toml` @ `18a908ce01dd560478ba31dc96fb91f0918b22d4dc6b6501f4f162d11388ad43`, and `bench_domain.py` remain unchanged. No backend/scientific behavior was added, and no actual JAX import or numerical fit was run.

## Data-requirement heuristic fallback

`src/polisyos/data_requirement/compiler.py` @ `68e673a7d190dcfde52af21dbe1ca3ab8ce85190c3690cbf63ec13f56728cd98` still contains `_required_data_families_from_heuristic`, gated by `POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED`. The default is `false`; the helper treats only `1`, `true`, `yes`, or `on` as enabled. When `compile_for_claim_ledger` has no resolver-derived family rules and the flag is enabled, it invokes the heuristic and stamps `family_derivation="legacy_heuristic_fallback"`.

The static source census is bounded to `src`, `tools`, and `tests`: 6,092 Python files parsed, zero parse failures, and 66 raw name/import/call occurrences in the saved JSON. That 66 is not a runtime caller count. The actual in-tree producer/API paths are:

- `runtime/quality/generation_cycle.py::_n7_data_requirement_specs` supplies `_n7_capability_resolver(problem)`, which may be absent; after typed request/spec/runtime-hint precedence, an unresolved grammar-backed compilation can reach the feature-flagged heuristic.
- `runtime/quality/scenario_evidence_contract.py::normalize_scenario_evidence_contract` constructs a compiler without a resolver. No in-tree caller of this exported normalizer was found, so external use remains possible but is not established here.
- Exported `compile_data_requirements_for_scenario` also constructs a compiler without a resolver; the in-tree reference found is a unit test.
- `tools/quality/validation/run_universal_outcome_corpus.py` has a separate validation-tool call. `runtime/quality/workspace/foundry_consumption.py` calls `compile_obligation_basis`, a distinct typed path that does not invoke this claim-family heuristic.

The feature flag is therefore default-off but not strangled: an operator can still enable it, and no-resolver public APIs remain. In-tree rollout config contains the literal string `"runtime"`; that is symbolic configuration data, not a value this boolean parser accepts as enabled. A separate `compile_for_scenario` branch, `_compile_from_legacy_scenario_fallback`, is controlled by missing grammar facets and projects `expected_evidence_contract` (or defaults to `production_data`); it is not governed by this environment flag.

The existing compiler tests demonstrate all three relevant behaviors: no fallback when disabled and no resolver, heuristic execution when enabled, and no hardcoded claim-text fallback when disabled. They passed:

```text
PYTHONPATH=src:. .venv/bin/python -m pytest --tb=short -rA \
  tests/unit/data_requirement/test_compiler.py::test_missing_resolver_does_not_load_runtime_fixture_when_fallback_is_disabled \
  tests/unit/data_requirement/test_compiler.py::test_legacy_family_heuristic_only_runs_when_phase4_flag_is_enabled \
  tests/unit/data_requirement/test_compiler.py::test_hardcoded_claim_text_fallback_is_not_used_when_phase4_flag_is_disabled
3 passed, 2 warnings in 5.12s
```

Output: `LOCAL/decisions/raw/dx0-data-requirement-fallback-tests.log` @ `1645e5c1a2d93528ce8125cd5dd42385a160c52ec625f40a7131a8ea146dd6eb`. The active `architecture/shims.toml` row defaults the flag to false and requires Phase 7 frozen legacy replay, W12.A missing-contract zero, and W11.E no-regression evidence before removal. Those gates were not run here, so retirement is not migration-ready. The retirement test remains that exact declared replay and W12.A/W11.E trigger; these compiler unit tests do not substitute for it. No fallback semantics or shim lifecycle record was changed.

## Verification and limitations

- `.venv/bin/python -m ruff check --select E402,I001,PT007` on the three entrypoints and HYG-04 test: passed (`LOCAL/decisions/raw/dx0-jax-focused-ruff-final3.log`, SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`).
- `.venv/bin/python -m ruff format --check` on the same four Python files: passed (`LOCAL/decisions/raw/dx0-jax-format-final3.log`, SHA-256 `177f260a5645724013185e4b140c7045cc39e56c0c97b120f5cb23599f85f0de`).
- Full HYG-04 file: 24 passed, 2 failed. The remaining failures are `test_benchmark_wrapper_caller_census_is_complete_and_bounded` (its tracked-doc reference set includes additional recovery/closure evidence paths) and `test_frontend_workspace_build_paths_and_python_package_boundaries` (`pyproject.toml` lacks the expected `[tool.hatch]`). Neither failure concerns the JAX helper or the changed entrypoint; no unrelated fix was made. Full output is retained at `LOCAL/decisions/raw/dx0-hyg04-full-final.log` @ `0e49bb7897b00ec7a57e70463825a07dadea4f2a5160c603bc022537d191b54d`.
- Candidate import preflight confirms `.venv` Python and `polisyos.common.jax_env` resolve inside this candidate checkout: `LOCAL/decisions/raw/dx0-jax-import-preflight.log` @ `c70e2350d922d2bdea0e06a1f5b1fa031de77e658b34b9b1c58a08ec213e9839`.

Pattern check: JAX repair reuses the canonical helper rather than maintaining three entrypoint policies (P31/P40); the trap tests exercise ordering and effective environment, not markers (P29). The heuristic assessment is an unresolved live compatibility path, not a retirement claim (P28/P35). No Git operation, generator, heavy runtime check, or source change to the data-requirement fallback was made.

# V3 route-schema and fixture-CAS patch proposal

Status: patch-only, un-applied, and unverified. This proposal follows the captured 22-test run at candidate HEAD `9194a65fb59355ceac35270c869f429efc7482d8`. It does not revise or replace patch 829.

## Current deciding run

The complete command, stdout, stderr, and JUnit are retained under `LOCAL/raw/v3-shared-root-owned-guarded-verification-20261010/`. The command ran the served authority route test, all `tests/unit/runtime/quality/test_acquisition_world_growth.py` tests, and the complete `tests/integration/core_runtime/test_acquisition_world_growth_chain.py` module. Exit was 1: 20 passed, 2 failed, 0 skipped; JUnit duration 87.844 s and measured wall 92.662 s.

- `command.json` SHA256 `48b15db5a4dfb7915deba4a191274a4d5bf5547b89cef73d68161a4f74932793`
- `stdout.txt` SHA256 `a41bfe396f92e9060adc5a8e4855623871247a7c05f46f0f8ee0fbc03fdcc206`
- `stderr.txt` SHA256 `e9373518718ea94a98c5fbd3d0aa4872888920d30b52aa276aef9c2dcf1ad365`
- `junit.xml` SHA256 `04936988a2ed6d238c1eae09d5fcc4a7709adbaa02714e081dd3cfb4021b12e8`

## Failure 1: served API emits a supported compiled-run version the route consumer rejects

The failing test is `tests/integration/core_runtime/test_acquisition_authority_served.py::test_served_acquisition_selects_committed_human_authority_and_reopens_worker`. The actual public NL POST completed, persisted its compiled recursive run, and reached `AcquisitionRouteLoop.resolve_current_route`; failure is `compiled_run_schema_mismatch` at `acquisition_route_loop.py:410`.

This is an actual producer/consumer divergence. The selected compiled artifact is `sha256:529c0d1273faadaa1ae1e6638acfe5c36ea12092fdbc5d3c1682ad4ade9330db`, whose bytes declare `policyos.runtime.http.compiled_recursive_generation_cycle.v4`. The run model at `src/polisyos/runtime/http/services/control/generation_cycle.py` explicitly accepts v1–v4 and recomputes the required version from the recursive-run shape and present source/cost fields in `_verify_bindings`. `AcquisitionRouteLoop` first successfully validates that strict model and then adds a stale v1-only equality check. The adjacent hand-seeded fixture in `tests/_helpers/acquisition_production.py` constructs a v1 run, which is why the stale check survived its earlier path.

The proposed production delta removes the duplicate v1-only check and leaves support authority with `CompiledRecursiveGenerationCycleRun.model_validate`: unsupported versions still fail the strict `Literal`, and inconsistent supported versions fail `_verify_bindings`. The existing v1 route-loop test remains a positive. The real served POST route is the v4 positive. The patch adds a v5 model rejection control so broadening acceptance cannot silently become an open string.

## Failure 2: guarded reader checks an artifact produced by the wrong fixture store

The failing test is `tests/integration/core_runtime/test_acquisition_world_growth_chain.py::test_active_dataforge_row_builds_limited_candidate_world_with_source_time_unknown`. It stops at the real `load_verified_epoch_statement` read of passport `sha256:bc843fa37f1d3e4583a5be0bfa09992600af5a7b645a3eff0ffbdc372f5f25e0`, which correctly refuses because the current owner index reports it as unowned for tenant `7cf3b2a8-0d6b-4d25-a01c-f248e933e1f0` / cell `cell-a`.

The exact passport manifest is retained in the run fixture. It has `inputs: []` and no `tenant_context`; the current ownership-index pointer selects generation `842d1e75e5247bd40f951283c3bf574da2e2e159036cf21f7fc0adcb8fd24655`, whose current artifact map does not include that passport. I traced fixture setup to `_run_actual_wdi_admits_delta_and_reenters_same_case_impl`: it monkeypatches `FileSystemCAS` in `tests.unit.runtime.http.test_control_service_di`, but the imported `_build_control_service` is defined in `tests/_helpers/runtime_http.py` and resolves that module's own `FileSystemCAS`. The monkeypatch therefore does not install the guarded store in the actual fixture control service. The consumer later creates `guard_runtime_cas(served.control._artifact_store.for_tenant(...))`; that read boundary is behaving correctly, and must stay strict.

The patch instead creates one explicit tenant-scoped `FileSystemCAS` view at the fixture control-store boundary, wraps it with `guard_runtime_cas`, and passes it as `artifact_store=` to the actual `_build_control_service`. This same store instance then serves the fixture's real producer, `production_admission_inputs`, bridge, and port, so ownership is established at write time and the guard remains in the path. It avoids ambient ownership, metadata rewriting, and per-operation bypasses. The existing active Data Forge test already exercises the real producer → passport artifact → guarded reader → world consumer path; the patch adds a foreign-tenant read denial against that exact persisted passport.

## P40 classification

Both findings are `SAME_CLASS_DEEPER` within the actual producer → persisted artifact → typed consumer boundary. The first exposed an additional supported producer schema after the consumer had only been exercised through v1. The second exposed that the downstream guarded consumer had not been paired with the same correctly owner-scoped fixture producer. The mechanism is widened once to the typed model's complete supported schema set and to one fixture-wide scoped-and-guarded store; the proposal does not add a v4 special case or per-artifact owner claims.

## Proposed patch footprint

The ignored patch is `LOCAL/raw/v3-route-tenant-cas-patch-20261010/v3-route-tenant-cas.patch`, SHA256 `290c78dd44cf874962e32843621464e444cd0f6fd0340c041eed5f861ef2eef1`. It proposes changes only to:

- `src/polisyos/runtime/quality/acquisition_route_loop.py` — remove the stale schema equality after typed validation.
- `tests/unit/runtime/quality/test_acquisition_route_loop.py` — reject a v5 schema through the strict typed model.
- `tests/integration/core_runtime/test_acquisition_world_growth_chain.py` — construct the actual fixture service with a tenant-scoped guarded store and prove tenant isolation for the produced passport.

The unchanged schema authority is `src/polisyos/runtime/http/services/control/generation_cycle.py` SHA256 `c4492d44e17df4c18364bf1e23aee3dd9c346d3a12f3b689e341e86c288f35c9`. Preimage hashes: route loop `d7beab61333e15f5688dbf49d29f06499c593fec441be4568457a7b64c2b683c`; route-loop test `06a91d9603cfacc9ca216fa7229676e0a34f2806b84efbb581d49dfe5f189c5b`; world-growth integration test `20c5dff891702e7ca1365a41ccf8ddeece9e157f97e29620706f9cc028f4a77b`. The earlier existing helper artifacts read for diagnosis remain `acquisition_chain.py@d63629772af08962f887d2d9fd69fede8261bbb6345948a7eb5ae57beeb8a92f` and `acquisition_production.py@895bd55772c481e88c9ed86daee91e799c4acb61b822ef34a4d20575bf1fc267`.

No product source or test was edited and no test was run for this proposal. Recommended first verification after root applies/reviews it: the unit route-loop selector, the actual served NL route selector above, `test_active_dataforge_row_builds_limited_candidate_world_with_source_time_unknown`, and then the already captured 22-test denominator. Do not claim closure until those exact outputs are read back.

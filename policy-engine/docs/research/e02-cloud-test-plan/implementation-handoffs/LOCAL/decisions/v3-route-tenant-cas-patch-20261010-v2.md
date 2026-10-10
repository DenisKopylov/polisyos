# V3 route schema and tenant-owned CAS patch proposal (v2)

This is a patch-only proposal. No product/test source was edited, and no test or Git command was run. The malformed v1 artifact remains untouched at LOCAL/raw/v3-route-tenant-cas-patch-20261010/v3-route-tenant-cas.patch (SHA-256 290c78dd44cf874962e32843621464e444cd0f6fd0340c041eed5f861ef2eef1). The new v2 patch was generated from current source preimages with Python difflib.unified_diff, rather than hand-maintained hunk counts:

- Patch: LOCAL/raw/v3-route-tenant-cas-patch-20261010/v3-route-tenant-cas-v2.patch
- Patch SHA-256: eb8f850353d3f442c417a87129889092e079e2f389731d56af115267ecb3577c
- Patch size: 6,002 bytes

## Exact patch footprint and preimages

The patch changes exactly these three files:

- src/polisyos/runtime/quality/acquisition_route_loop.py — preimage SHA-256 d7beab61333e15f5688dbf49d29f06499c593fec441be4568457a7b64c2b683c
- tests/unit/runtime/quality/test_acquisition_route_loop.py — preimage SHA-256 06a91d9603cfacc9ca216fa7229676e0a34f2806b84efbb581d49dfe5f189c5b
- tests/integration/core_runtime/test_acquisition_world_growth_chain.py — preimage SHA-256 20c5dff891702e7ca1365a41ccf8ddeece9e157f97e29620706f9cc028f4a77b

Unchanged helper inputs inspected for the fixture route:

- tests/_helpers/acquisition_chain.py — SHA-256 d63629772af08962f887d2d9fd69fede8261bbb6345948a7eb5ae57beeb8a92f
- tests/_helpers/acquisition_production.py — SHA-256 895bd55772c481e88c9ed86daee91e799c4acb61b822ef34a4d20575bf1fc267

## Patch behavior

The route resolver first validates persisted bytes with strict CompiledRecursiveGenerationCycleRun.model_validate. Its extra equality against the current default-version constant rejects supported persisted versions emitted by the actual compiler. The proposed source delta removes that redundant equality; the typed DTO remains the authority for the supported version set.

The route unit test now carries both the supported v1 positive and a persisted v5 negative through the existing real CAS/job/core-run/terminal-event route. The v5 payload recomputes its content_hash after changing only schema_version, so the consumer rejection is attributable to the unsupported version rather than a stale-hash shortcut. The expected resolver code is compiled_run_invalid.

The guarded integration fixture previously patched FileSystemCAS in a different test module than the helper that constructs the actual control service. That left the served producer on an unscoped store. The proposal constructs the tenant/cell-scoped filesystem CAS at the fixture owner, wraps it with guard_runtime_cas, and passes that exact store into _build_control_service; production admission, route persistence, and world-growth processing then share it. The actual passport is read successfully by its owner and a tenant-scoped foreign store must receive ArtifactOwnershipError for the same persisted ArtifactRef.

## Evidence boundary

The composed source-bound run that motivated this proposal is retained at LOCAL/raw/v3-shared-root-owned-guarded-verification-20261010/:

- Command metadata SHA-256 48b15db5a4dfb7915deba4a191274a4d5bf5547b89cef73d68161a4f74932793
- stdout SHA-256 a41bfe396f92e9060adc5a8e4855623871247a7c05f46f0f8ee0fbc03fdcc206
- stderr SHA-256 e9373518718ea94a98c5fbd3d0aa4872888920d30b52aa276aef9c2dcf1ad365
- JUnit SHA-256 04936988a2ed6d238c1eae09d5fcc4a7709adbaa02714e081dd3cfb4021b12e8
- Result: 20 passed, 2 failed; this is the prior run, not verification of v2.

The two failure boundaries were: (1) actual served compiler output used the supported compiled_recursive_generation_cycle.v4 schema but route resolution returned compiled_run_schema_mismatch; and (2) the persisted passport artifact had no owner input binding and was correctly denied on the scoped consumer path. The v2 patch proposes addressing those exact boundaries. It has not been apply-checked or executed.

## P40 classification

Both are SAME_CLASS_DEEPER within producer → persisted artifact → consumer continuity. The schema issue is one stale consumer equality across the whole strict DTO-supported version set, not a per-version exception. The CAS issue is one fixture-wide ownership boundary, not an artifact-by-artifact repair. The v5 persisted negative and foreign-tenant denial are falsifiers for those invariants.

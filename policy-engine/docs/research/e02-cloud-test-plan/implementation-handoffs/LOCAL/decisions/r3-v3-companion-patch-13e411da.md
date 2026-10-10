# R3/V3 companion patch preparation

Prepared patch only against the parent-designated frozen base `13e411da`. No target source or test file was edited and no tests or servers were run.

Patch: `LOCAL/raw/r3-v3-companion-patch-13e411da.patch` (sha256 `d27ff7c6e717f92ffd25579610cf1acbcdc9de6c4a06f78528d3bf90d7650a7c`). It contains exactly two test-file paths:

- `tests/unit/runtime/http/test_nl_pipeline_cost_projection.py` (base sha256 `50d578cd48e1a527642cce52d69f122a0ca4a47a969de18578677c4a901d1754`)
- `tests/integration/core_runtime/test_acquisition_authority_served.py` (base sha256 `5df4c678ae7b5ee54216d6e9e5d6785581a386ddd83b6025635043d8d088cd08`)

R3 companion: the fake retrieval service receives the real typed keyword-only `run_profile: CatalogRunProfile | None`, records the request profile and keyword profile, and the four-origin producer-cost test selects `prod_full` and asserts both values match. All existing reported-zero, estimated, unknown-null, reuse-zero/origin, aggregate-null, and settlement assertions are unchanged. The fake method is shared with the ordinary NL POST test, so the same signature also covers that caller. No production retrieval behavior is patched. The existing `test_control_service_di.py` profile-conflict test remains a separate negative control.

V3 companion: the test retains an explicit no-bearer `401/missing_bearer_token` assertion, then performs both the positive history GET and post-corruption history GET with the already-issued `acquisition-operator` bearer and matching `X-Tenant-ID`. This principal has `runs.view`; middleware and route policy remain unchanged. Existing selected human-authority, acquisition-history/ref, candidate-only, currentness-limited, and corruption-limitation assertions remain unchanged.

P40 buckets are distinct: R3 is the same stale test-double/API-signature class; V3 is a new omitted read-auth-context class, with the correct product behavior being 401 absent credentials. Acceptance after root applies the patch: R3 selector reaches the unchanged four-origin assertions and verifies `prod_full` forwarding; V3 selector preserves the unauthenticated denial, serves the exact history with the issued credential, then returns the typed integrity limitation under the same credential after corruption.

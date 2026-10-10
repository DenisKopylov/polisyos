# R3/V3 test companion patch v2

Prepared as an unapplied patch against frozen base 13e411da; no source or test file was edited and no test was run.

Patch: LOCAL/raw/r3-v3-companion-patch-13e411da-v2.patch
SHA-256: 55a291a9be60f5040671aecdb9498b2e76dd9195797a63e28052e0c189777f39

It contains exactly these two test paths:
- tests/unit/runtime/http/test_nl_pipeline_cost_projection.py
- tests/integration/core_runtime/test_acquisition_authority_served.py

The original unapplied patch remains preserved at LOCAL/raw/r3-v3-companion-patch-13e411da.patch with SHA-256 d27ff7c6e717f92ffd25579610cf1acbcdc9de6c4a06f78528d3bf90d7650a7c.

## R3 actual receiver binding

Source inspection confirms the production call path in src/polisyos/runtime/http/services/control/nl_pipeline.py: _agent_pipeline locally imports RetrievalService, creates its local receiver at line 5370, and invokes retrieval.resolve(...) at line 5667 with both the DataResolveRequest and run_profile=self._catalog_run_profile. Separately, run_lifecycle.py creates ControlPlaneService._retrieval at line 1627; that instance is not the NL local receiver and is unused by this NL call.

The v2 test fake records every constructed instance. It clears the registry after ControlPlaneService construction, before _execute_nl_pipeline, so only receiver(s) constructed during the actual NL invocation can satisfy the assertion. It selects instances that recorded resolve calls, requires a nonempty receiver set, and checks every observed request profile and keyword profile equals prod_full. The cost assertions for reported zero, estimate, unknown-null, reuse-zero/origin, aggregation, and durable settlement remain unchanged.

P40: same stale test-double/API class, widened to the actual receiver quantity. The v1 patch asserted against a nonreceiver service field, which was a P38 proxy and would observe no call.

## V3 served history auth

The V3 hunk is unchanged from v1: it retains explicit unauthenticated 401/missing_bearer_token, then passes the fixture-issued acquisition-operator bearer and matching tenant header on both successful and corruption history GETs. No production auth policy is weakened. This is a separate omitted read-auth-context companion, not a product route defect.

Patch-only disposition: ready for independent review/application and the designated selectors. No test pass is claimed.

# Independent review: R3/V3 companion patch

## Scope and evidence

Read-only review of the unapplied patch `LOCAL/raw/r3-v3-companion-patch-13e411da.patch`, SHA-256 `d27ff7c6e717f92ffd25579610cf1acbcdc9de6c4a06f78528d3bf90d7650a7c`. The patch contains exactly the two designated test paths. I did not apply it or run tests. The target files still match the diagnosis base hashes: R3 test `50d578cd48e1a527642cce52d69f122a0ca4a47a969de18578677c4a901d1754`; V3 test `5df4c678ae7b5ee54216d6e9e5d6785581a386ddd83b6025635043d8d088cd08`.

I read `LOCAL/decisions/r3-cost-profile-companion-diagnosis.md`, `LOCAL/decisions/v3-history-auth-companion-diagnosis.md`, and the patch-preparation record. Current source fingerprints relevant to the R3 boundary are `nl_pipeline.py@aa5dcbbfaef0c17905b85d9dca6696fb6d7ac6b4f5501075d53d2e5aa1965142`, `run_lifecycle.py@4f941cd8b069020cc3d70bd4ac61f129d881c68d77e673278cea7d00265b5fd3`, `fabric/retrieval/service.py@db94b6159844b4adbf844c0e798a0e423c283ae10a5a3f510eff06ef7e3cf543`, and `control_registry_providers.py@cd7cb561b727fa91bfd96499aca13b122e36dbee49ecd4930425a63512a8a2a0`.

## R3: patch has a false observer and will fail its new assertion

The signature update is correct: `RetrievalService.resolve(request, *, run_profile=...)` accepts the typed keyword; the request profile is a `CatalogRunProfile` literal, and the configured `prod_full` value flows from `ControlRegistryProviders.catalog_run_profile` to `ControlPlaneService._catalog_run_profile`. The four-origin settlement assertions remain untouched.

However, the new witness captures `retrieval_service = service._retrieval` immediately after `ControlPlaneService` construction, then checks that object's `resolve_profile_calls`. It is not the receiver used by this NL pipeline. `run_lifecycle.py` initializes `self._retrieval` in its constructor (around line 1627), while `nl_pipeline.py` constructs a second local `retrieval = RetrievalService(...)` inside `_execute_nl_pipeline` (around line 5370) and invokes that local object's `resolve` (around line 5667). The NL module has no use of `self._retrieval` on this path. Thus the new call log is attached to an unused fake instance; the assertion `retrieval_service.resolve_profile_calls` will be empty even if the actual local fake receives both `prod_full` values. This is a P38 proxy-gate divergence: the asserted observer is not the producer receiver whose forwarding is under test.

Minimal correction: observe the fake instance(s) constructed by the monkeypatched `RetrievalService` constructor, then assert that the instance used by the NL local call recorded the matching request and keyword profiles. A class-level/closure instance registry in this test fake is sufficient; alternatively capture the actual construction at the NL seam. Do not weaken the non-empty observation or remove the profile equality assertion. Keep the four-origin cost assertions unchanged. P40 classification remains the same stale test-double/API class; this defect is in the chosen witness receiver, not a new production behavior class.

## V3: hunk is aligned with the served authorization contract

The patch preserves the explicit anonymous read denial (`401`, `missing_bearer_token`) and then uses the fixture-issued `acquisition-operator` bearer plus the same `X-Tenant-ID` for the positive history read and the post-corruption read. The fixture's actual configured permissions include `runs.view`; the token binds the same tenant and cell. The app has real security middleware enabled. No route, middleware, permission, or production authentication behavior is weakened. The existing selected-human-authority and corruption-integrity assertions remain in place, so the authenticated fresh read still distinguishes valid history from the typed integrity limitation.

This correctly addresses the V3 diagnosis's new read-auth-context omission class. It is a test-source review only; no execution result is inferred from the patch.

## Disposition

Do not accept the R3 companion as written: change the observer to the actual NL-created retrieval receiver, then rerun the designated R3 selector. The V3 hunk is acceptable as a companion and should be exercised by its designated selector. This review does not certify either selector green, nor does it claim production retrieval behavior was changed.

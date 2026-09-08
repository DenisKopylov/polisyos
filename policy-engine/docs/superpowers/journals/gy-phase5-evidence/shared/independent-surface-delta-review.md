# Independent surface delta review — 2026-09-08

No findings in this bounded review. **Approve the PA1 D3e callable-client bridge and the D4 Core-contract facade correction for final integration.** This consolidates the earlier D3e approval by message. Active Foundry facade and D3f example changes are outside this review and are not implicitly approved.

## D3e: specification and transport correctness

The only generator-policy change adds the exact live operation ID `submit_run_normative_evidence` to the existing curated POST-operation owner in `tools/ops_runners/runtime/generate_runtime_client.py`. It uses the unchanged OpenAPI operation/body resolver and request renderer; no generated method is hand-authored and no general operation-selection policy is changed.

Read back the raw and canonical generated TypeScript and JavaScript methods. `submitRunNormativeEvidence` requires the run identifier and typed `NormativeEvidenceSubmissionRequest`, encodes the run path, sends `POST` and the unchanged request body, and reuses the existing response/error/auth transport. The strict backend intake and authority decisions remain unchanged. The added test in `packages/runtime-api-client/runtimeApiClient.test.mjs` invokes both actual generated JavaScript classes, with a run ID requiring URL encoding, nullable prior-head reference, and nested evidence refs. It asserts fetch method, URL, exact serialized body and response. Its payload is a transport fixture, not a constructed governance receipt or backend admission witness.

Read complete recorded results:

- `runtime-client-operation-red.json`: actual callable missing, RC 1, 0.891 seconds.
- `runtime-client-final-tests.json`: canonical package test command RC 0, 4.669 seconds, including both-client transport behavior and existing canonicalization/recursive-type tests.
- `runtime-client-final-typecheck.json`: canonical package typecheck RC 0, 4.152 seconds.
- `runtime-client-operation-removal.json`: process-local removal of the operation from the actual generator, canonical raw-client regeneration into scratch, and byte-identical transport test; RC 1, 0.668 seconds, failing on the missing callable while DTO markers remain. This removal directly falsifies the raw producer seam. The ordinary positive separately executes both raw and canonical clients; the removal record does not pretend that its unchanged copied canonical client was independently removed.

The decisive property is an actual generated callable reaching the existing transport, not presence of OpenAPI DTO names. The red/removal both observe that property. No new receipt epoch or backend capability claim follows from the client surface.

## D4 Core facade: specification and owner identity

`src/polisyos/core/contracts/__init__.py` adds `ControlJobResponse` to its existing `.control` lazy-symbol map, type-checking import and public `__all__`. Its unchanged lazy resolver imports the existing owner and returns that exact class object; no DTO wrapper, subclass, duplicate contract or eager cross-subsystem owner is introduced. `runtime/http/services/control/generation_cycle.py` imports the response through that supported facade, and `NormativeEvidenceSubmissionResponse.job` retains the same existing Pydantic model type. This review covers this import correction only, not a fresh review of already approved PA1 head semantics.

`tests/repo_quality/architecture/test_public_api_facades.py::test_normative_job_surface_uses_the_core_contract_facade` imports the actual facade, asserts object identity with the `.control` owner, imports the actual consumer, and checks its resolved Pydantic field annotation is that same object. `core-contract-facade-red.json` records RC 1, 5.595 seconds, on the originally absent facade attribute. `core-contract-facade-green.json` records the same command RC 0, 90.318 seconds. Source inspection confirms that the consumer uses the facade; the common architecture guard remains responsible for import-policy enforcement.

## Review boundary and P40 disposition

These are the already named surface/owner-boundary corrections: D3e is the callable-client bridge under P01/P02/P03, and D4 Core is the same-object public-owner import correction under P27. This delta review establishes no new class or deeper escape and requests no repair round or recursive verifier. No tests, generator, production source edits or receipt writes were performed by the reviewer. Root owns final integrated checks and generated-artifact freshness after all source inputs are frozen.

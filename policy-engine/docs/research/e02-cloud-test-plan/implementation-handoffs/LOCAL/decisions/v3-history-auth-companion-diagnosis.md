# V3 served history GET authentication companion diagnosis

## Scope and replay evidence

Read-only diagnosis of the parent-supplied frozen replay for source revision `13e411da`. I did not edit source/test files or rerun the integration selector. The captured selector is `tests/integration/core_runtime/test_acquisition_authority_served.py::test_served_acquisition_selects_committed_human_authority_and_reopens_worker`.

Evidence is under `LOCAL/raw/composed-mac-current-source-20261010/v3_active_acquisition_served_history/`:

- `metadata.json` (sha256 `f7719ab26ea86cec7e152f027e1afe2d446640b0baad02e527ed40e3c9f70e56`) records the single-selector invocation and complete output inventory.
- `junit.xml` (sha256 `25b3268ca75c0925e4d5673f22172271f4c7010096ce48f64ce9a2218b20a5f2`) records 1 failure, 0 passes. The selected test ran for 82.276 seconds; suite time was 95.579 seconds.
- `stdout.bin` sha256 `fcdf7865e423d35af06ad15379b345f70ae78db90bff10b45fd5d88855ea452b`; `stderr.bin` is empty (sha256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

The failure is at `test_acquisition_authority_served.py:1296`: `client.get(f"/api/v1/runs/{core_run_id}")` returns 401 with `code="missing_bearer_token"` and detail `Authorization header must contain a Bearer token`. The response body is preserved in JUnit. The route never returned a history projection, so the replay does not establish a history-reader or acquisition-receipt defect.

## Property and classification

This is a **NEW test-auth-context omission class**, separate from the prior R3 stale retrieval-fake `run_profile` signature. It is not a runtime authorization regression and not a stale test double. The product correctly rejects a request with no bearer token; the test omitted credentials on a protected read after successfully exercising authenticated, step-up-protected mutations.

The test's `app()` configures the real `DeploymentSecurity` and sets `enable_security_middlewares=True` at lines 612–623. `_ExternalTrust` issues locally signed JWTs against a live fixture JWKS server; its `acquisition-operator` principal carries `evidence.acquire`, `runs.review`, and `runs.view`, and its JWT binds the same tenant/cell and analyst role (lines 360–390). The `trust.post` helper supplies `Authorization: Bearer <trust.tokens[subject]>` and `X-Tenant-ID: TENANT` (lines 402–411), then adds a signed step-up token for mutations. Those authenticated POSTs and worker transitions succeeded before the history read, so the existing fixture already has the appropriate credential.

`GET /api/v1/runs/{run_id}` is the normal `get_run_details` handler (`src/polisyos/runtime/http/routes/runs.py:2217–2256`), which enforces tenant access and records a `runtime.run` read. The 401 is produced before the handler because the GET at line 1295 has no `headers`. The later corruption-control GET at line 1714 also omits headers and will hit the same expected 401 once execution reaches it. Both GET calls occur inside the same final fresh `TestClient(app())` session opened at line 1087; both can reuse the still-valid, already-issued acquisition-operator bearer plus tenant header.

## Minimal test companion and controls

Use the existing fixture credential, not a relaxed middleware or an invented identity:

```python
history_headers = {
    "Authorization": f"Bearer {trust.tokens['acquisition-operator']}",
    "X-Tenant-ID": TENANT,
}
```

Before the authorized history read, keep an explicit unauthenticated request with only the tenant header and assert 401 plus `missing_bearer_token`. Then use `history_headers` for the positive history GET and for the later corrupt-reentry GET. No step-up header is needed for this read; `runs.view` is the configured permission, and the same issued identity has it. Do not disable middleware, forge a new token, alter tenant scope, or change the route's authorization policy.

Preserve the existing successful-chain checks after the authorized read: one acquisition history row; exact route/reentry refs and old/new candidate IDs; exact selected N4 source ref; `origin_source_ref is None`; `currentness_status="not_established"`; `authority_purpose="candidate_observation_only"`; and `publication_authority is False`. Preserve the negative content-integrity check too: after corrupting the reentry blob, authenticated GET should still return 200 with an empty acquisition history and `acquisition_action_history_integrity_not_established`. The unauthenticated 401 is a separate access-control negative and should remain intact.

Pattern pass: P31 says reuse the existing fixture issuer and its normal auth headers rather than patching the endpoint or adding a special unauthenticated history path. P32 is not implicated because no receipt/reference was admitted by shape here—the request stopped at authentication. P40 bucket is NEW relative to the retrieval fake/API drift finding: this GET omitted the caller credential, a distinct read-auth plane. The smallest acceptance probe is unauthenticated GET → 401, then the same run GET with the fixture's already-issued `runs.view` operator credential and tenant → history assertions, followed by same authenticated GET after content corruption → typed limitation.

Relevant source hashes at diagnosis: `test_acquisition_authority_served.py` `5df4c678ae7b5ee54216d6e9e5d6785581a386ddd83b6025635043d8d088cd08`; `runs.py` `2d0bec815342d2cd32a2c59e8e1e9a3c28149238c0934210776a3413f0786bd1`; `jwt_auth_middleware.py` `88e60822c34b371e8703f532627540e899231ca1aeefa8cc56dfa1485cff8f2a`; `permissions.py` `a198692f8f40c1fe1375960f62a15c38f852631f0ee8611c32c745934a14fa1e`.

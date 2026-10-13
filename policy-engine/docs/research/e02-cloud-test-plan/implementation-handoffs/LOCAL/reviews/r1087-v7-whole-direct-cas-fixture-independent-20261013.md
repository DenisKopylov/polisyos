# R1078 whole direct-CAS fixture scope — independent review (R1087)

Date: 2026-10-13. Verdict: **GO for root apply and focused native replay only**. This review makes no product behavior claim and grants no formal closure (`closure_ids: []`).

## Identity and readback

- Frozen candidate patch: `LOCAL/raw/r1078-v7-whole-fixture-direct-cas-owner-context-20261013/candidate.patch` @ SHA-256 `92194e8392ea76437174c1526b55f90c138e3403503621cf4f37ff3c86fae900`.
- Binding manifest: adjacent `manifest.json` @ `1d08dfaa61f132f3196894d8cb88e49fcfef5f178fc8aa367c463fbe30e5faae`.
- Base frame: `LOCAL/root-author-source-frame-r1076-20261013.json` @ `018b1e5998e45ca73fcfb4cac4fbcee11c0851610d283d2e9c2dff2f7ba39e12`; HEAD/tree `9511169e1a7f6dbd4137de824905dfbff8992a3f` / `d6d48c83b5a60afdead8066253bc30cd216f5913`.
- The only patch target is `policy-engine/tests/unit/runtime/http/test_control_service_di.py`. Its physical bytes matched the bound preimage `80cf995c501b7932864b36bcad4ba2438759acc9aa4971dc46f5687d306d5c00`; strict in-memory replay of both hunks (39 removed/context lines, 43 added/context lines) yielded manifest postimage `958a166e00c66fb1fdbabdd509944e53ef0d98b0b9b149e152583ef50a8f665d` (238,759 bytes). No product source, index, or history was written.

## Property and complete test-function census

R1077 is the relevant actual failure: `LOCAL/raw/v7-ordinary-post-fresh-get-same-intent-owner-context-actual-r1077-20261013/junit.xml` @ `2f5d77dea2663f1baf970d621e96b2f8d4ae2110225d3bed4468967e7e5f5a52`, stdout @ `98418f494b7cf39b409e5197c2de56b91e4ba3fdbe6108a0ddacda687ff6a2f7`. The test reached the successful POST/event, fresh GET, same-intent replay, conflict and tampered-event assertions before failing while it directly seeded a legacy association/event. The failure was `ArtifactOwnershipError` on `write input:run_manifest`, because that test-side CAS fixture materialization had no active owner context. R1078 does not change the production route; it supplies the same declared fixture tenant/cell to the fixture writes and leaves the later HTTP retry outside those added scopes.

I walked the entire affected test function AST, then the exact virtual postimage. The direct CAS paths fall into these groups:

1. The job-input callback writes/reads sources, model/policy specs and the rule. It is invoked from the actual `RunContext.start` callback while the admitted control job is inside `ControlPlaneService._install_execution_scope(admission.scope)`. That existing execution scope installs the persisted tenant/cell, so adding a second manual scope here would be redundant and is not in this patch.
2. The report/evidence direct reads already use the narrow R1071 fixture scope. The alternate-profile candidate `get_bytes`/`put_bytes` pair also already uses a narrow fixture scope.
3. The previously unscoped unrooted-model `_spec` fixture write is now inside a small tenant/cell scope. Its HTTP POST remains after the scope exits and still asserts the model is absent from the run root.
4. The legacy fixture’s `_persist_association` and `_append_association_event` are now inside one narrow tenant/cell scope. The legacy retry POST remains after scope exit; its expected 409/unverifiable-intent result, unknown intent record, and unchanged ForecastOwner count are untouched.

All TestClient GET/POST expressions remain outside the two newly added `tenant_scope` blocks. There is no whole-test or autouse scope. The current fixture identity declares `tenant-fixture` / `cell-fixture`; `tenant_scope` installs and resets those values, and `FileSystemCAS` continues resolving the active owner and enforcing manifest/blob ownership. The patch therefore creates owned test data under the fixture’s already-declared owner without bypassing CAS ownership checks or changing HTTP authorization.

P40 classification: **SAME_CLASS_DEEPER** than R1072. The earlier direct-read helper lacked owner context; R1077 exposed the same fixture-owner class at the next direct CAS setup operation. This patch widens across the remaining direct fixture writes that need an owner while preserving the already-correct worker scope and the existing narrow scopes. P37: candidate path/pre/post binding is independently reconciled; the R1077 failure is independently reconciled from JUnit; static job-scope and fixture identity bindings are recomputed from source. Post-delta runtime behavior remains **not established** until the requested root replay.

## Independent checks and limits

- Normalized only the two new fixture `with tenant_scope(...)` wrappers by replacing each with its original body. AST for the entire affected async test then matched the preimage exactly. No request, branch, payload, expected result, or assertion changed.
- Strict in-memory patch replay verified each hunk’s context and exact manifest postimage.
- On the exact postimage from `policy-engine/`:
  - `.venv/bin/python -B -m ruff check --no-cache --output-format json --stdin-filename tests/unit/runtime/http/test_control_service_di.py -` — exit 0, stdout `[]`, SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; stderr empty.
  - `.venv/bin/python -B -m ruff format --check --no-cache --stdin-filename tests/unit/runtime/http/test_control_service_di.py -` — exit 0, stdout/stderr empty, SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- No pytest, runtime imports, or native replay was run here. The root replay must confirm the legacy HTTP refusal still holds after the fixture is materialized under its legitimate owner. This is not whole-capability acceptance.

## Source origins

- Test preimage: `policy-engine/tests/unit/runtime/http/test_control_service_di.py` @ `80cf995c501b7932864b36bcad4ba2438759acc9aa4971dc46f5687d306d5c00` (fixture and affected test, lines 4178–5025).
- Fixture owner contract: `policy-engine/src/polisyos/core/security/tenant_context.py` @ `f9051375fa189e5bc3e020356eccc4d14f6c1e6402080cd4261396ef3b56c9e0` (`tenant_scope`, line 99).
- CAS owner enforcement: `policy-engine/src/polisyos/core/artifacts/store.py` @ `220175d9166865b45257ed8643ac3c18c06914a1d822a82d4794a7a4bcc4bddb` (`_resolve_owner`, `_require_manifest_view_owner`, refusal on missing owner).
- Job callback scope: `policy-engine/src/polisyos/runtime/http/services/control/job_scope_admission.py` @ `116c3778c82a072a778374555d3247d5bb08ebb1af9ddd8138579a900a195cb2` (`_install_execution_scope`, line 395).
- Worker invocation inside that scope: `policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py` @ `7a8044cb1141b665d25a9cb453e649444fc8e9b306cd02efe36e15e4960850c4` (admitted job scope around `_process_control_job_admitted`, line 3842).

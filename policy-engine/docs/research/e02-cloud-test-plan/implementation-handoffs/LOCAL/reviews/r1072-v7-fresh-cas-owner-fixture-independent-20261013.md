# R1071 fresh-CAS owner fixture companion — independent review (R1072)

Date: 2026-10-13. Verdict: **GO for the focused root native replay only**. This review does not establish a production change, a successful post-delta runtime run, or any formal closure (`closure_ids: []`).

## Bound packet and source

- Frozen patch: `raw/r1071-v7-fresh-cas-owner-read-test-companion-20261013/candidate.patch` @ SHA-256 `3de346c9b49ce64bf8248a564973e9c7e4990f50211f31efb7499a415ab7f625`.
- Binding manifest: adjacent `manifest.json` @ `7fad3e3508861f9dcc7c83cb68d555ab1e8bb7215e59733cbdba007130304557`.
- Manifest target is only `policy-engine/tests/unit/runtime/http/test_control_service_di.py`: preimage `2d3b45e1d4ed498b0fbae4ef94259e4065626432432d13d350ad0ab73a0becff`, postimage `80cf995c501b7932864b36bcad4ba2438759acc9aa4971dc46f5687d306d5c00`. The current physical target bytes matched the declared preimage; the R1059 frame records the same path/hash (`root-author-source-frame-r1059-20261013.json` @ `110476638a39394b71eef6ab6701d0ef751a53c4509f8a96fe3d221ca24930f2`). Frame HEAD/tree: `9511169e1a7f6dbd4137de824905dfbff8992a3f` / `d6d48c83b5a60afdead8066253bc30cd216f5913`.
- I replayed the single unified-diff hunk in memory against that exact preimage. Context/removal counts were 13 and additions 14; produced SHA-256 exactly matched the manifest postimage. No product file, index, or Git history was written.

## Finding and property

R1066 is the relevant failure receipt: `LOCAL/v7-whole-record-ref-fresh-get-deciding-r1066-20261013.json` @ `c3516cd9d23df5e20aa057f687b8b01a11e60db7fd6f126ca1de48d2c3a5a027`. It binds 17 passed / 1 failed across 18 tests. The failing end-to-end case had already completed POST 201/event and exact intent, refused the foreign-run GET with 409, then returned fresh GET 200 with the exact association and reference. It failed only afterward, when the test helper directly reopened the persisted report reference: `ArtifactOwnershipError` said an active owner was required for `read_manifest`. JUnit is `raw/v7-whole-record-ref-post-event-fresh-get-exact-intent-actual-r1066-20261013/junit.xml` @ `7ad60383056cc2f6b41ea4e60fff84fb3d6030e2cd6d513b02af660848d2e3e8`; the recorded command is adjacent `command.json` @ `0d63245a1398dfb69414024dee37ea7ab40b0109026144ec8c368227bd736956`.

The R1071 delta wraps just the helper's two direct CAS loaders—`load_backtest_report` and `load_empirical_calibration_evidence`—in the fixture's existing `tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture")`. Both values are still checked after the scope exits, including the exact selected profile, report/evidence identity, run binding, intent binding, and reason codes. No production endpoint, authorization guard, ownership index, stored artifact, expected result, or semantic assertion changes.

This fixture scope is source-bound to the same test identity: `_fixture_claims` declares the same tenant and cell, `_install_fixture_tenant_lifespan` uses the same values, and `tenant_scope` installs/resets those context values. `FileSystemCAS._resolve_owner` reads the active tenant/cell; the manifest/blob ownership checks remain active and still require the selected artifact to belong to that owner. Thus the changed code exercises owned reads under the already-declared fixture owner; it does not suppress ownership checks or grant a new scope. The test imports `tenant_scope` already, and the later fresh GET and other route assertions remain untouched.

P40 classification: **NEW test-consumer context regression**, distinct from the previous Core/IR reference-shape compatibility issue. The delta widens the owner context over the complete current direct-read quantity in this helper (both report and evidence), instead of patching only the first failure. P37 binding is independently reconciled for packet pre/postimages, R1066 failure location, and fixture tenant/cell equality from source. Whether the focused test passes after this delta remains **not established** pending root native replay.

## Independent checks and limits

- Normalized the one new `with tenant_scope(...)` by replacing its two contained assignments with their original statements; AST for the full test function then matched the preimage exactly. All reads and assertions outside the owner context were retained.
- On the exact in-memory postimage, from `policy-engine/`:
  - `.venv/bin/python -B -m ruff check --no-cache --output-format json --stdin-filename tests/unit/runtime/http/test_control_service_di.py -` — exit 0, stdout `[]` (SHA-256 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`), stderr empty.
  - `.venv/bin/python -B -m ruff format --check --no-cache --stdin-filename tests/unit/runtime/http/test_control_service_di.py -` — exit 0, stdout/stderr empty (empty SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
- An initial independent replay/Ruff wrapper stopped on an internal Python assertion before Ruff ran. A diagnostic strict replay then confirmed the 13→14 hunk and exact postimage hash; the successful Ruff commands above ran on that verified postimage. No result was inferred from the aborted invocation.
- Pytest/native tests were not run in this review. R1066's exact-intent replay after the direct read did not execute because the helper failed; that assertion remains for the requested focused native replay. This is a bounded reviewer GO, not whole-capability or formal acceptance.

## Source origins

- Test preimage: `policy-engine/tests/unit/runtime/http/test_control_service_di.py` @ `2d3b45e1d4ed498b0fbae4ef94259e4065626432432d13d350ad0ab73a0becff` (fixture identity around lines 109–144; helper and GET flow around lines 4207–4791).
- Owner context: `policy-engine/src/polisyos/core/security/tenant_context.py` @ `f9051375fa189e5bc3e020356eccc4d14f6c1e6402080cd4261396ef3b56c9e0` (`tenant_scope`, line 99).
- CAS ownership enforcement: `policy-engine/src/polisyos/core/artifacts/store.py` @ `220175d9166865b45257ed8643ac3c18c06914a1d822a82d4794a7a4bcc4bddb` (`_resolve_owner`, lines 1050–1078; manifest-view ownership begins line 1158; missing-owner refusal at line 1212).
- Direct consumers: `policy-engine/src/polisyos/ir/analytics/backtest.py` @ `2f0571c95a576ce0932417e06a4a0cfcffa1e29d1e9afc37c9324926eaf05cbd` (`load_backtest_report`, line 789) and `policy-engine/src/polisyos/calibration/forecast_bridge.py` @ `99c11c8e2e706ed66c0e084cbc38af666d18a9a9c31c9769985cf64e2c55dc91` (`load_empirical_calibration_evidence`, line 579).

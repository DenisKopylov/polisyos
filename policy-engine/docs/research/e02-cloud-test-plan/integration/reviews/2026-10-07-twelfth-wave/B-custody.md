G qualification: old B-authored `B120 bridge_missing` labels below describe that packet’s scope. They are superseded for the bounded D factory path by G’s [exact-680 correction](../2026-10-07-eleventh-wave/B120-correction.md): 10 native PASS, while integrated acceptance/formal closure remain pending.

# B current-head metadata and custody review — 2026-10-07 13:11 intake

Read-only audit of the four pinned B topic heads. I did not execute tests or inspect the already-reviewed getter/no-effect source. The pin file records the four exact remote heads and trees below; each head/tree matched Git, and each prior comparison base is an ancestor.

| Slice | Pinned head / tree | Prior head | Delta footprint |
|---|---|---|---|
| Adapters | `2d0f65266a9b42f56bcc73264c43e0f296e10ac5` / `dd10d17bc2caf9ed5beb3ca25a32db5ec92e558e` | `4d523e51ccdc9d1a16d5ff81316f44898827ee78` | 1,073 paths; 8 product paths |
| CAS generation | `d81e7c68a83850834bbe48c492c87975010e79ba` / `f5be50a6768fc7f878784d98f715074175def60c` | `8c292c4904462a1ecd57d250f06fdfd7ff293c95` | 22 evidence/handoff paths; no source or test paths |
| Durability | `3dd221a83dbfa4a9f900b4a2d9338f14ce0a1f29` / `526435eb211b83c6c6f0ff35ef145b199d621008` | `0bf268e7860831241e3fd193b3da46086d5893cc` | 17 evidence/handoff paths; no source or test paths |
| Runtime | `2c773afbcd2b84c96f482ff3d757e0ed4b18de63` / `9f0b2cc027562c60377d93a997971841d801f373` | `9b57328d57cce174da8a2953e6db0e77c1ad1fee` | 10 metadata/handoff paths; no source or test paths |

## Numeric gateway consumer custody

The committed `tenth-wave-gateway-numeric-custody.json` at `91651c5e2b8b2f35a7e0cf3294550ad0487504cb` (tree `47026c744cc1a02aa3a3ee50fc6d38bc3076f897`, base `590e5d18e7f56c7c4d2e42070dcc687c79acc58c`) has no source/test delta and no formal closure IDs. Its fresh `guarded-http-ledger-fresh-reader15` check ran the whole `test_gateway_exact_money_consumer.py` file at source `590e5d18e7f56c7c4d2e42070dcc687c79acc58c`, tree `e6ec2e4bb34f84f946341004f1e5c8374fb29010`: 15 passed, 0 failed/error/skipped, all 45 setup/call/teardown phases passed, exit 0. It used Python 3.14.2, pytest 9.0.2, aiohttp 3.13.3, pydantic 2.12.5, orjson 3.11.5 and tiktoken 0.12.0; the fixture was real loopback HTTP, an fsynced request, initialized `FileBudgetLedger`, a fresh B process, then the three-module external D reader at `8f58d7349edefebbac7e7f21e6859f8daa075c1d`. No live provider or production dataset was used.

The receipt’s 876-row file-backed source census was independently compared with the pinned adapters head `2d0f652…`: all 876 path hashes match. Separately, the declared test blob `f15c776…` at source commit `595a259…` is the same blob at the current adapters head. This transfers only the recorded loaded-file profile and test input; it does not assert full-tree identity or a whole-branch test. The committed evidence index lists 85 payloads totaling 7,797,566 bytes; all listed Git blobs matched their recorded lengths and SHA-256. The actual partition has 15 cases and 75 physical-input files, with each outcome PASS. The package record says all 15 response and ledger byte sets are bound.

Keep the new 15-case execution separate from retained older checks: the 30-case decoder candidate/removal receipts target `e7c5182…`, and the independent money baseline/candidate/removal records were marked not re-executed in this slice. They are not additional current-source passes. The handoff keeps B65 at “retained/no new audit adjudication”, B66 `limited`, and D’s B120 controller bridge `bridge_missing`; it closes nothing.

## Process recovery and imported checkpoint

The process-recovery receipt at `e246c3028d0ae19086db975c8a937cd411fe20ca` records a test-only execution at `f4e8422232ce3b61ef28c5c1928a65df5038a3fe`, tree `d2eef1f673e9a1422999f5dc64a9dd4a89d54704`, using `pytest -c /dev/null --noconftest -o addopts= -vv -s tests/unit/scientist/orchestration/engine/test_budget_llm_process_recovery.py`. Python 3.14.2 ran on Linux 6.18.44; plugin autoload and numeric thread caps were disabled. The native result is 3/3 passed. Its material-removal run selects `-p remove_admission -k kill` and yields one expected property-failure case (exit 1), so it must not be counted as an ordinary test failure or as another native pass. Both raw stdout/XML pairs and wrappers are indexed; all 16 payload hashes and lengths reconcile to 208,231 bytes. The receipt declares no production edits and no closure IDs.

That process receipt is not byte-identical to the current adapters source across its declared input closure: the test and 6/7 guarded production files match `2d0f652…`, but `policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py` differs (`df2db47…` at the tested source; `4161bc6…` at the current adapters head). Keep the 3-pass receipt pinned to `f4e842…`. To carry the process result to `2d0f652…`, rerun this focused test at that source or provide a source-bound exclusion for the changed declared input; none is present in this packet. This is an input-identity qualification, not a source-mechanism review.

The separate imported-checkpoint receipt at `3dd221…` records four native PASS cases (12 passed phases) on target `590e5d18…`/tree `e6ec2e4…`; its member-identity removal control fails as intended. The test is `test_imported_module_checkpoint_identity.py` (11,096 bytes, SHA-256 `1c22fd…`); its projection input is a 712-byte fixture. The recorded runtime is Python 3.14.2/Linux with pytest 9.0.2, NumPy 2.3.5, JAX 0.8.2 and pydantic 2.12.5. This is a bounded imported-member/builtin/dynamic-namespace profile, not universal module-identity closure. Its output is separate from the gateway and process receipts.

## CAS and runtime evidence-only deltas

The CAS-generation head adds only custody metadata. Its final Git-only audit at `590e5d18…` reports PASS with no audit errors and reconciles the exact durability checkpoint receipt and adapters numeric receipt. The eight indexed audit payloads (147,323 bytes) hash and size-match. Two earlier audit attempts are retained as ERROR (initial peer-path construction, then snapshot comparison); they are superseded by the final corrected metadata audit, not product-runtime outcomes. Candidate runtime remains `UNRUN`; B74 remains `limited`, D’s B120 bridge remains missing, and closure IDs are empty.

The runtime head is likewise source-only metadata: it records static consumer-source reconciliation against `590e5d18…`, including a failed whole-loaded-source-transfer premise (two changed paths), while a new native/served/provider check is explicitly `UNRUN`. Its navigation/import PASS must not be read as a current runtime test.

**Disposition:** the physical custody is complete enough to preserve and use each output only at its named source cut. The gateway 15-case result has a matching bounded input census at current adapters; process recovery has one changed declared production input and stays pinned to `f4e842…`; CAS/runtime heads add no fresh runtime execution. None of these four handoffs formally closes a B finding or accepts code by metadata alone.

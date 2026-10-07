# Independent B+C composition and NETING test-delta review

Reviewer: `/root/c2_dependencies` (independent read-only review). This note records two completed reviews; it is not a B-source acceptance or G-admission artifact.

## B+C composition

The composed source candidate is `c694daaf888657ec261988fa2066df792fd77110`, tree `bf1e231b53c1f68f7fce176792ea0011636a83f8`, with immutable parents C `07bbb61ffa6d53709942bcda87c37daef1a04651` and B `121fcf450757086ffcc506dabca33fbe28dcd661`. The independently reviewed path census was 4,488 distinct paths: B contributes 4,302 (156 source/test paths), C contributes 186 (8 source/test paths). Their path sets are disjoint; the merge tree is their exact union and changed blobs match the respective owner parent. All 36 reviewed B supplier dependency blobs match B's parent bytes. This verifies composition integrity only; it does not accept B's supplier behavior or establish B87 closure/G admission.

Composition evidence retained beside this note:

- Full path inventory: `../staged-full-paths.txt`, SHA-256 `05530730c9151be7539dc043628b19768bf74ad6c8305831bad8cd5f13c21714`.
- Full source/test comparison: `../staged-source-test-diff.txt`, SHA-256 `e80bd9bf63f05003c2addf32fd6261c73de6fc30d82c74999c122a07a2e3be1b`.
- Hook status is a nonreceipt: `../hook-nonreceipt.json`, SHA-256 `f5d767fbeefd692db2e415fa3da7d1794ac44dc0a7f1d7672472c47755fde2cb`. Hooks were UNRUN; the merge command used `core.hooksPath=/dev/null`. This is not a frontend or hook pass.

## Test-only delta

The reviewed commit is `0979fae4edaea61f3ae602241423d5cd96b091de`, tree `0ae7f83ad99321e0b83343a3eb3e02f7454d8bc4`, parent `c694daaf888657ec261988fa2066df792fd77110`. It adds only `policy-engine/tests/unit/fabric/data_plane/test_net_ing_current_frontier.py` (440 lines); blob `3b3dea7cbb99b28cece5ba01e9da52bad6c6ded1`, SHA-256 `b99737efb81cc5c332f125ae0b04261940cb8a3768fa213c1d7e828e3af9b894`. The streaming source blob remains `80af60d90e2eb6aeed0d335c4dbe5d80c8c24c7c` from the composition commit to the test commit. The result is a bounded GO for this test delta.

The 3-to-1 restored-cap test observes actual poll, flush, frontier commit, pool acquire/release, and public CAS `put_json`/`put_bytes` calls. It asserts refusal before poll/flush/commit/CAS write, balanced leases, unchanged checkpoint/cursor models, byte-identical stream and cursor indexes, unchanged complete CAS artifact-ID set, and unchanged pending chunk bytes/manifest model. The recovery test independently parses source JSON lines, checks complete chunk rows and exactly-once event IDs, ordered windows and contributor refs against the actual chunk artifacts, then reopens the store and checks a repeated call emits no rows/refs or new chunk/window IDs. Persisted dedupe keys are checked by `json.loads` into field/value tuples, not a production key helper.

The removal control replaces `_admit_restored_operator_state` with a no-op while leaving the test markers intact. The test then observes two real polls and fails at `poll_events == []`; this is a behavioral removal probe. One bounded assertion detail: checkpoint/cursor and pending-manifest comparisons use model dumps, while index snapshots are raw bytes; the same test observes no CAS write calls and unchanged artifact IDs/payload bytes.

Deciding outputs (already run; no rerun performed for this note):

- Native test run: `.tmp/e02-net-ing-20261007/raw/verification/oracle-final-20261007T092259Z-3ca6d2ee/native.txt` SHA-256 `6f011a1ee84e0d0b34a25072eb03c2a0484600d2fc29ab0aa7bf32507c5ee656`; stderr empty (SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`); XML SHA-256 `d8b586016d363531ce6c52ae58b72adc64d04d0e3fc4762b6ac49a05e61d73fa`; 2 passed.
- Admission-removal control: `.tmp/e02-net-ing-20261007/raw/verification/removal-final-20261007T092326Z-742cc0dd/native.txt` SHA-256 `56ca37baf8a749db32f9b8f7feaf14ec802ed48130004663314f0b6cfd59ffc6`; expected one-test failure; XML SHA-256 `23125f42c5453becc6969af68bab70ef10f25d39858c6e6efa3cb7e18070b0fd`; plugin SHA-256 `e30fdfc09cfa295a457b33ef35272aed1e9bfaf7fd54c4fad04d7f45f015226e`.
- The composed parent run had 2 B budget-oracle setup failures before cap/recovery assertions: the shared B helper expects `_message_id:event-N`, whereas C stores canonical JSON pair strings such as `[["_message_id","event-1"]]`. This is oracle representation drift, not a C product failure and not a P41 inherited-red disposition. Captured composed stdout SHA-256 `507ed15c57b0aac8b357aceefca06cf765467a22675442fdbd70cead00a1d693`; XML SHA-256 `41885910d734f9e77fd009dba4bf9371271ed2bd00e872825fbb66af7b0da61c`.
- Separate historical B receipt `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-completed-crossunit-final-evidence/native.xml` SHA-256 `b4b60fd6c986cbd3a2d454cbdfd5ac5d0a2294941b27583f4faec17cb0fc7958` is source `1862c021df74a5c5815bc5cd21a20e61b30132b6` evidence (8 passed, 2 failed), not a result of this test-only delta.

The author's review map is retained as a separate source artifact at `.tmp/e02-net-ing-20261007/raw/verification/net-ing-final-review-map.json`, SHA-256 `486a24818a438920ca547a15f090775f78149e6f45c7ea890b11f29c2f3a8b66`. Its conclusions are not presented here as independent reviewer evidence; the source/test and output artifacts above were read independently.

# Independent review: V9 R2 fixes v2

## Verdict

**GO for this scoped proposal**, based on read-only source inspection and a successful git apply --check. This is not a runtime pass, a full closeout receipt, or an admission/closure decision. I did not run tests.

Review target: LOCAL/raw/nonproperty-error-truth-v9-r2-fixes-v2.patch SHA-256 5cffe72517500504decb0138af772f1a25ec4d201f0425db5857d329602bb2b7, against these exact source/test preimages (path @ SHA-256):

- policy-engine/src/polisyos/data_forge/domains/academic/batch/edge_synthesize.py @ ac94e1af16fcec930a8c1dba7e451ed24f60f6db8e4745eab08c70fed9c6e122
- policy-engine/tests/unit/data_forge/domains/academic/batch/test_qc.py @ fe3d79c8c8bda5b8dbf8a51a86c8b137bbc94cb5c5a86ae1796805bbc53cd1cb
- policy-engine/tests/unit/data_forge/domains/academic/batch/test_run2_pipeline_upgrades.py @ e44d994cfaf5276afa25c69d1a72961c1c7d268c90e4a846a8dd439a71e98a63

Its companion proposal note is SHA-256 94d8181d939bd3d0dbd39dbf70d70554359bb206e2f2cb64b55d630044918db0. At review readback, the candidate checkout was HEAD 214e56201613f1098e9791aac4d7b4ec0f57c30e, tree d45a620d26202126cff8ef63626794c816b63e74; the source/test preimages were unchanged.

## Property review

The relevant property is that provenance carried from an exact source edge stays unknown when its value is absent or null, and malformed present provenance is refused before producing output. V2 closes the whole row-value intake and projection path: it represents SQL NULL and JSON text null as unknown, runs every other present value through the strict object decoder, and safely projects an absent sibling using .get. Unknown values are not coerced to false. The output aggregator retains its existing rule: only known true emits a true synthetic marker; known false is emitted only when all contributions are known false.

This matches the owner semantics in _graph_staging.py SHA-256 87f2effe1c4fb797170a622191a2f0e80992ce29d13ba79d12281595850ac037: absent fields/null cells remain unknown and malformed present containers refuse. It also matches the actual edge writer in graph_builder.py SHA-256 0d1b79b2dc45d3d97dbb7f2414be69ecae534a1212dfdaa917b21b9a272b996d, which validates quality_signals_json as a dict. The shared decode_json_object in common/serialization.py SHA-256 73967455cce4a0a54ae3be927067ddc208f9fbcb0b288e341b1d7e67e884c1f5 rejects non-objects, duplicate decoded keys, non-standard non-finite constants, and overflowing JSON floats.

The proposed consumer fixture exercises persisted JSON null plus an absent sibling edge through run_edge_synthesize; it asserts the exact edge IDs survive and that the aggregate does not claim synthetic. The negative fixture supplies a present array, expects ValueError, and checks that source bytes and report/manifest absence are preserved. These are behavioral controls at the consumer seam, rather than constructor-only assertions.

## P40 bucket and limits

This is SAME_CLASS_DEEPER: v1 addressed a missing exact-edge row, while V2 handles a null value inside a present row. V2 widens the full per-row value decoder and projection behavior, rather than adding another case-specific fallback.

The SQL-NULL branch is explicit in the proposed code but is not directly exercised by the new fixture; the fixture covers JSON text null and a missing sibling. This is a small coverage caveat, not a blocker to the source-level conclusion. The patch also carries the prior six test expectation/input corrections; I did not independently rerun those cases.

## Checks and scope

- git apply --check policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/nonproperty-error-truth-v9-r2-fixes-v2.patch — exit 0 against the current composed checkout.
- No tests or heavy checks were run; no source/test files were edited and the patch remains unapplied.
- The referenced R2 run (440 passed, 7 failed) is historical evidence from the proposal packet, not evidence for this V2 delta.
- No authority or formal finding closure follows from this review.

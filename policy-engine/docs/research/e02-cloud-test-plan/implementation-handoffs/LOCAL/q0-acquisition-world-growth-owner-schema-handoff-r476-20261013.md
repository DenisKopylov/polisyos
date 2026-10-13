# Q0 owner receipt schema handshake — R476

**State: virtual candidate, not applied, not independently reviewed, runtime acceptance unrun, `closure_ids=[]`.** This packet closes the exact producer/consumer schema-name disagreement found in the R444 world-growth action-head path. It leaves currentness, ActionHead/event verification, G adjudication, and the wider Q0 claim unchanged.

## Source boundary and diagnosis

The candidate binds to the current R480 source frame `LOCAL/root-author-source-frame-r480-20261013.json@a2b0b98730e4effd3b7425b3152fdc6ad10919d8a3e273f797552138e8b2447b` on branch `codex/e02-unified-local-20261009`, HEAD `929dafec0f26ea95c3e3405ab8fc701d305ba115`, tree `7993709ed9994623d67e23e833cf7f2076880b30`; the shared index is preserved at SHA-256 `fc7e4cdfa0398d6ccd264c6e4d9b36d52f6664b9adf9be041e5b93027b8a60c9` (72 staged paths). The two owner/sink preimages and Q0 integration test remain the R464-qualified bytes in this frame.

The R444 diagnosis is retained at `LOCAL/reviews/q0-acquisition-world-growth-owner-receipt-schema-diagnosis-r444-20261013.md@933986c9b91295bd85d289a30f9147c3679d01b2ed6f0b74a68da454a0b76d55`. The canonical owner writes `SchemaInfo.name == "AcquisitionWorldGrowthReceipt"`; its own reader expects the same value. The action-head consumer instead required `polisyos.runtime.AcquisitionWorldGrowthReceipt`, so it rejected otherwise-valid current owner evidence at the exact schema predicate before the existing durable event join.

## Candidate change

`AcquisitionWorldGrowthReceipt.ARTIFACT_SCHEMA_NAME` becomes the single code-owned schema identity. The owner writer, owner readback map, and action-head consumer all use it. The no-growth receipt schema and all current ActionHead predecessor/event/source/phase/hash/tenant/route checks remain as they are. The consumer accepts no alias list.

The added marker-preserving negative builds the existing actual WDI owner/action chain, verifies the complete current positive head, then changes only the readback schema name to the former qualified spelling. The consumer must refuse with `acquisition_action_owner_receipt_binding_mismatch`; restoring the original manifest view must verify again. Thus the guard exercises schema identity with producer, CAS bytes, action selection, authority event, tenant, route, phase, and head markers held intact.

## Pattern pass and limits

- `P12`: one canonical producer-owned schema identity closes a producer/consumer handshake mismatch.
- `P32`: a schema label alone is not evidence; the existing code still resolves the owner bytes and verifies hash, action scope, and durable authority event.
- `P37`: expected schema identity is `recomputed` from the canonical owner class; an unknown or mismatched label fails closed.
- `P38`: the property is exact source-defined owner-schema agreement; the previous consumer predicate compared against a namespace alias, rejecting the actual producer output.
- Capability remains `implemented_but_not_orchestrated` pending the full current Q0 source-bound acceptance wave. No production currentness or G closure is claimed. The DS15 projection still distinguishes `not_established`, `no_growth`, and `grew`; source time remains unknown where previously limited; `G` remains unadjudicated.

## Acceptance boundary

The entire current `test_acquisition_world_growth_chain.py` and all root-declared source-bound Q0 controls are for the root-owned native run. They are **UNRUN** in this packet. Also unrun: R3 no-call, typed-state/migration, provider truthfulness, monetary truthfulness, cleanup, native API/browser, and all original-source recovery controls. No product imports, tests, database/provider access, or physical source/index/Git writes were performed by this author.

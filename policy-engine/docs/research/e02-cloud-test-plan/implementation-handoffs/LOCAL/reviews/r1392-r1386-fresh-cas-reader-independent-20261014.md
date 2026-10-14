# R1392 independent review — R1386 fresh CAS reader fixture

Date: 2026-10-14  
Decision: **GO for focused composed replay of the candidate source property, with an unresolved packet-manifest identity mismatch.** This is not a runtime pass or closure.

## Bound inputs

- Worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- Branch/HEAD/tree/parent: `codex/e02-unified-local-20261009` / `f0ebb3c7a4f042bd00eebfbc3166573e0d8289d8` / `e0e1d31e7f7d76e0b9af487261566105fbd57c3f` / `1387e46f4a2f9e4f95cdc17ca5d7e31f8e506974`
- Source frame: `LOCAL/root-author-source-frame-r1383-20261014.json` SHA-256 `a8042763d5fc41bd1db8490c46cb7899dc2765f391a09f1e576ff4a42e60cd38`
- Candidate: `LOCAL/raw/r1386-cost-projection-fresh-cas-read-20261014/candidate.patch` SHA-256 `dcf3d7e7a3fa16b168a80be9b65842d4d428f9b8dd89af315d705d02539a63be` (matches the assigned patch identity).
- The assignment named adjacent `manifest.json` SHA-256 `dbfcc65f704c68c133a24ded192f592d80f2efa9271f46ca71e22d470113e405`. The only adjacent `manifest.json` present during review hashes to `7537b0c4ebba33afaf0854e8ed922a1ac9efcc2072fd9b3beef46f1702585819`. Its body binds the candidate SHA and the exact observed base, preimage, and postimage below, but these are different byte identities. I therefore do not attest that the announced manifest bytes were reviewed. Parent should rebind the packet to the actual manifest or supply the exact announced bytes.
- Target path: `policy-engine/tests/unit/runtime/http/test_nl_pipeline_cost_projection.py`; working file and `HEAD:path` both SHA-256 `5092c6a52fa96ba5e89e610cef5936b08c2cd92fbec8e86b94fcacd2e887699f`.
- Candidate postimage declared by the observed manifest and independently reconstructed in memory: SHA-256 `7e3d206a7c244866daa3250580e1c89b7aa99ccffdfb41d3d307a7320fc1cac3`.
- Read-only `git apply --check --verbose <candidate.patch>` exited 0 and reported `Checking patch policy-engine/tests/unit/runtime/http/test_nl_pipeline_cost_projection.py...`; no patch was applied.

## Source-property finding

The R1384 retained failure receipt `LOCAL/raw/source39-owner-ruff-scope-and-expiry-controls-actual-r1384-20261014/full-nonpass.json` SHA-256 `64c7a0b0fd5d8091d664c094795a0e47154a339b2f0497b4805003ed3208300d` records the target test failing with `RuntimeDependencyUnavailableError: content_addressed_storage dependency guard is closed`. In the source, `service.close()` runs in the `finally` block before the final selected-reference loop. That loop had reused the service-bound `original_get_manifest` at its post-close lines 666 and 668. Other reads using that service handle in the function occur before close; the later test's environment close is its final action. The whole-file post-close census and source readback are consistent.

The candidate replaces the entire post-close selected-reference loop. For every captured authority write result it checks the payload, authority-envelope, and diagnostic-event references. It creates a distinct `FileSystemCAS(cas_root)` rooted at the exact namespace used by the producer; it does not reopen the service, call the closed proxy, or remove the guard. It passes each full selected `ArtifactRef` through `get_manifest`, `get_bytes`, and `read_core_json_artifact`, then checks kind, media type, schema, tenant/cell context, selected profile digest, byte size, SHA-256 identity, strict Core JSON conformance, decoded object shape, and the payload's exact envelope/event ID and profile links.

The existing profileless-default and same-artifact/different-profile negative controls are retained and still execute before service close. The new checks widen the read from the failing leaf to every selected ref and every captured result, so this is `P40 SAME_CLASS_DEEPER`, handled at the shared fixture read boundary rather than by reopening one call site.

`FileSystemCAS(cas_root)` is unscoped: source inspection shows that with no tenant ID the constructor does not enable ownership enforcement. The test checks stored tenant/cell context against the fixed controlled producer input, which is evidence that the simulated producer persisted that context; it is not an ownership claim, issuer proof, production access guarantee, billing proof, or currentness claim. The candidate correctly avoids `for_tenant(...)` and does not fabricate an `ArtifactOwnershipIndex` owner record. Those stronger predicates remain `not_established` and outside this fixture's claim.

P38 property: selected post-close artifacts remain readable from the persisted test namespace under their exact typed/profiled identity. The candidate measures the actual raw CAS read and strict profile decoder, rather than a marker or declared status. No divergence from that bounded property was found. Ownership and external-provider claims are outside the measured property.

## Verification and disposition

The observed manifest records successful in-memory reconstruction, AST parsing, Ruff check, and Ruff format check. I independently verified the base preimage hash and read-only patch applicability. Its retained receipts are `patch-materialization-check.json` SHA-256 `69eb07ad18658f8708b68653d85dfaa1eca04f3e0bd85e0e5d7da354a77ba348`, `ruff-full-output.json` SHA-256 `3aead036252f99205b5f860bd236e9e97d88f367647f0263db3ad2ebebe52350`, and `ruff-format-output.json` SHA-256 `5160b4a4a71b528763dc770e602f5392f87c910411e54b1408889bcdc758dbba`.

Runtime imports and pytest are **UNRUN**. Root should replay the correctly rebound patch in its composed source and run the targeted node before treating this fixture repair as behaviorally verified. The source-property review is GO for that bounded replay; exact announced-manifest binding is unresolved as stated above. `closure_ids: []`.

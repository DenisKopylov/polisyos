# R1329 independent delta review: N4 comparator and basis binding

## Disposition

Qualified go to the root-owned focused instrumented replay. R1322-r4 structurally addresses the two R1314 evidence gaps: the scope digest test rebuilds the full basis and tests a source-identity mutation, and the declared-lever negative now calls the real derivation function with a typed, fully rebound result that must raise the exact comparator refusal. The two long served tests now emit phase probes.

This remains a virtual test-only candidate. Pytest/native behavior is unrun; no N4-V2, G, production, or closure claim follows.

## Exact composition and source binding

Current source is unchanged at branch codex/e02-unified-local-20261009, HEAD a02f4f8920c60e02e745ba91bbed9ab9524fcbe7, tree/index da829953b1c170f3bc69420059dc7d1af4fb06f7. The bound frame is root-author-source-frame-r1306-r2-20261014.json, SHA-256 cf7bbc6d742ace36a33cb1077dbbeb2effc377da7ef723e3d7bf8d2864dc9d92, with 590 listed physical paths.

R1322-r4 candidate.patch SHA-256 is 5dc255724c503b74bd829cafd2776c520b52801cda88feda28b92e3bff0ba814; delta.patch SHA-256 is 9f0f3777fa70152f6931fb5daba2425189ff88ba268e5c604bee31a57c8f2cd7; manifest.json SHA-256 is 02eca171d9bba0f5f0407128d2aca18bfe4fd112bf534e66d0f6c423083cdcb8; static-property-readback.json SHA-256 is 127ad96da8663463db27ec67f31ad88d6021802a657ea59b6057c21ca4175138; decision.md SHA-256 is 878de79f48f5b9c4cccd1847343806db67fc20d14100ff9acb9d427ade2af3d7.

I rehashed all three current preimages; each matches the R1322 manifest. The patch passes git apply --check. I also applied the unified patches in memory: applying the full R1272 patch yields each of its three declared postimage hashes; applying the R1322 delta to those images yields byte-identical files to the cumulative R1322 candidate; and all three cumulative images match the R1322 manifest postimage bytes and hashes. The virtual postimages all parse with Python’s stdlib AST. No file was patched during these checks.

The R1272 fixture boundary and two unchanged helper semantics are preserved. R1322’s semantic delta is in the served integration test; the helper’s formatting adjustment is formatting-only. The mechanism remains three Python test/helper paths and zero product-source paths. The R1314 full test-tree census still applies: it walked 2,995 Python files under policy-engine/tests and counted 16 calls to the shared helper. R1322 adds no helper call sites; its census and full callsite list are retained in R1314 JSON SHA-256 f185fa1e5ee9aee76eee2cb4004702ec27f363cde8e9a0bc125bee855e4d0036.

One prior attribution qualification remains: the tracked controlled_candidate_profile.py path is absent from the current frame’s 590-entry postimage map, but its bytes match the R1322 preimage exactly. The other two changed paths are in the map and match. This is not unexplained byte drift.

## Review of the corrected controls

The basis assertion independently assembles the same named basis fields from the reconstructed problem, source recording ID and whole-recording hash, allowed operators, resolved levers, and resolution rows, then compares gy_content_hash of that structure with the emitted scope ref. Its slot mutation changes the computed digest and derived fixture ID. A separate in-memory copy changes only the synthetic recording ID, recomputes the whole-row hash, runs the recording validator, and verifies the controlled scope and parent identity change. It preserves the original recorded response bytes and supported domain/request inputs; historical scope remains not established. This addresses R1314-F2.

The new negative begins with the actual two admitted candidates and first confirms that the original parent yields two children. It then makes a distinct probe parent with the complete matching lever set for the first candidate removed, preserving allowed operators and the other parent premises. It rebinds the typed candidate atoms to the new exact parent ref, recomputes atom hashes/IDs and candidate provenance hashes, updates the matching disposition bindings, and validates a GenerationUnderAResult with the same two candidate IDs and count. The real derive_n4_candidate_child_problems call is expected to raise DesignGenerationError with code n4_recursive_child_declared_lever_semantics_missing. The unchanged recording’s credit-guarantee unknown_blocked status remains a separate upstream control. A pytest.raises assertion on this real function call is comparator-dependent: if the comparator is removed and no other refusal occurs, this test fails rather than passing on the upstream disposition marker. This addresses R1314-F1 structurally.

The negative is an adversarial, typed re-bound copy derived from actual generated candidates; it is not an N4 producer emission for the reduced-parent probe. It proves the derivation guard’s response to a validly re-bound typed input and makes no claim about the producer emitting unmatched candidates. Its probe-only scope hint retains original source context and uses a distinct guard_probe_kind; do not interpret that hint or the direct call as persisted authority or a real historical parent.

Both previously uninstrumented long cases now accept served_worker_phase_probe and pass phase_callback through preparation and worker/GET. The original-capture case marks fixture preparation, app creation, client lifespan, POST, worker dispatch, and fresh GET. The N5-writer-removal case marks preparation/app/lifespan and passes the probe into the existing worker/GET helper. This addresses R1314-F3’s missing phase visibility. The historical R1268/R1274 failure and incomplete run remain historical facts and are not converted to passes.

## Limits and classification

R1322-r4’s own readback reports Ruff check and format check passing for all three Python paths and AST parsing passing. My review independently verified hashes, patch composition, apply-check, and AST syntax; I did not run Ruff, pytest, imports, runtime/native code, or a product test wave. Runtime/native status is still NOT RUN.

P40 bucket: same N4 source-to-child declared-lever class; the previous upstream-proxy example is now supplemented with a direct comparator control, and the digest self-consistency gap has an independent basis recomputation. The bounded residual is that this direct negative is a typed adversarial rebind, not an actual producer output for the reduced parent; that is the correct scope of this guard test and does not warrant another instance-level repair. The ordinary served positive, N6 persisted history, and fresh consumer path still require the root-owned instrumented run. N4-V2 remains not established and closure_ids is empty.

# B state/runtime/adapters — checkpoint 11 delta

Read-only delta review at G `127dc7ab8365d29eb656fe32c0c894f6cc971286` (tree `759daf4ccbd6e72230de8bda36e1522ffa8fe3e4`). Input inventory: `R/1740-new-head-triage.json` SHA-256 `5bf0728f2e84fd4263a1ec118960f82ea3b50a09ce06624bee6b807a850ed7b2`; `after-checkpoint11-ref-delta.json` SHA-256 `e1bcd91f5c213d71e4d3165d0ea48b4efdf10cde4b73e7eeb8bba308f0388c3a`. No refs, source, tests, environment, or checkout were changed; no tests were run.

## Execution state — no remedy to the 3eb counterexample

The new execution tip `f70331f5c007ec8a9886a50bc6c8da4fbb35a24d` / tree `97698e556a8fd7175c2f0e2e6c9eaa7a88fa3df2` is an evidence-only descendant of `5ba2411581d164d1c5051907799a3b80337ba3ca`: 13 changed paths, no product source/test. New directory/lineage selector reviews are about choosing the cohort, not typed state write isolation; they carry empty `closure_ids`. The selector review preserves an actual C1 observer FAIL (18 absent names, 4 unmapped/UNRUN); later finite `ff54` controls PASS do not turn the source census or final cohort green.

The prior G probe remains **FAIL on its exact B candidate** `3eb2e887e07452a316aab95b7dbe3b4f2874951d` / tree `1fa3889f9fa5d216ab54357de6a680d03c4621d4`: mutation of the actual `ArtifactRef` at `inputs.ref` under an unrelated declared write path leaked into the base with an empty journal; dict controls passed. The `f703` evidence-only delta changes none of those bytes and gives no remedy. Keep the B candidate’s typed-leaf scope/isolation result on HOLD until the canonical owner closes mutable-model leaves such as `ArtifactRef` and reruns the actual branch/cache consumer with the same controls.

Do not call this an exact-current-G replay. At G `127dc`, `state_branching.py` is blob `08760b26aae2…`, whereas candidate 3eb is `6f5bd398af2b…`; the current-G discriminator is UNRUN here. Neither a source-lineage difference nor a selector audit waives the immutable 3eb FAIL.

Receipts: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-all15-execution-state.json@5ba2411581d164d1c5051907799a3b80337ba3ca`; `.../final-selector-directory-independent-review.json@f70331f5c007ec8a9886a50bc6c8da4fbb35a24d`; `.../final-selector-lineage-independent-review.json@f70331f5c007ec8a9886a50bc6c8da4fbb35a24d`; exact probe details `R/1548-B-state-runtime.md`.

## Runtime — previous Mac FAILs unchanged

The new runtime tip `eec8523d7d901cdaf9f93ef50d06569096dfe1bc` / tree `dbfa1fa1621f151065c09552a09ef6abca88c98d` is a receipt/review-only descendant of `dae863be52dc612e7ccef8b52a542159ca69e330`: 23 evidence paths, no product source or tests, and no changed primary handoff. It does not modify the previously tested `e1871506fcebc47d6572891b323ddf1f2083a3c9` runtime bytes. Preserve the **six Mac control FAILs** (sync/async × `SystemExit`, `KeyboardInterrupt`, unsupported `SystemExit` → `NodeTimeoutError` after one attempt) and keep that B runtime candidate on HOLD. New runtime audit reports do not replay those cases: the terminal-run consumer report is a saved-data reconciliation whose metadata check passes while the underlying native root run remains exit 1 (85 FAIL, 1,314 ERROR); it retains B14/B24/B39 LIMITED and has `closure_ids=[]`.

The Mac result is specific to e187; G `127dc` has different `retry.py`/`async_executor.py` blobs. The exact current-G Mac check is UNRUN, not PASS or inherited waiver. The needed B repair remains the non-Linux supervisor’s typed control-exception completion (or an explicitly enforced narrower platform contract), followed by those six Mac cases plus the Linux control selector on the repaired exact source.

Receipts: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-runtime-process.json@dae863be52dc612e7ccef8b52a542159ca69e330`; `.../current-terminal-run-consumer-independent-review/review.json@eec8523d7d901cdaf9f93ef50d06569096dfe1bc`; Mac matrix/source identity retained in `R/1548-B-state-runtime.md`.

## Adapters — bounded B50 witness; finding remains limited

The adapter tip `84566f836be6efaa42b26ccd9163c937ce4ef118` / tree `b6df513a4f9667f7e8efd71d298ff978aa8c48bf` adds one test and evidence only (9 paths total); it has no production-source delta. The test commit is `a8af9d0fcdc55436f008f065941ed1cfa5069502` / tree `47a5a80e55439479e10de3e25666aaea3dd74814`. Its committed handoff pins actual runtime source separately to B coordination candidate `456f34938731b1ef11555d8333d011d3552574ec` / tree `d3bae9a9502b701e2ed73d9ffab07ba6a0883502`; this distinction matters because the new adapter branch itself is test-only.

**Bounded test/code-path GO for B50’s three terminal ports on source 456f.** The test invokes real `MethodCompiler.compile`, observes an actual joined `_wait_for_flight` follower, and injects `CancelledError` and `SystemExit` from the leader build plus `RuntimeError` from real cache publication. For each case the leader/follower terminate with the expected error identity or `CompilationError` cause/reason; the flight is retired without a cached result. A fresh native JAX retry then reads back 20, warm dynamic factor 3 reads 30 on the same kernel, and the old factor-2 handle still reads 20. Actual Linux/Python 3.14.2, pytest 9.0.2, JAX/JAXlib 0.8.2 output is 3 PASS / 0 FAIL / 0 ERROR / 0 SKIP. This tests the real compile→flight→follower→cache→kernel path; it is not marker-only or mock-only evidence.

Boundaries: this is a test-only adapter commit against imported source 456f (no overlay), not a G-target run. G’s `compiler/__init__.py` blob is `31c85543a0ce…`, versus `cfa6273688e4…` at 456f, so do not transfer the native PASS to current G. The witness covers these three synchronous terminal ports and a JAX recovery/readback; it does not establish arbitrary interruption points, XLA hard cancellation, every backend, or the full JIT-01 contract. The handoff itself says `closure_ids=[]` and leaves B50 **LIMITED** pending independent criterion admission plus prior generation/invalidation evidence. No B50 finding closure follows from this review.

Receipts: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-jit-leader-terminal.json@84566f836be6efaa42b26ccd9163c937ce4ef118`; `.../current-jit-leader-terminal-evidence/native.json@84566f836be6efaa42b26ccd9163c937ce4ef118`; `.../current-jit-leader-terminal-evidence/native.txt@84566f836be6efaa42b26ccd9163c937ce4ef118`; criterion `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/JIT-01.md@69780761ae091d8fcc6ab8778c7f5f7227eeef0b` (B50).

## Disposition

- B typed-reference probe: **FAIL on 3eb; HOLD**. New execution receipts do not change its source or witness. Current-G exact check: **UNRUN**.
- B non-Linux runtime: **six FAILs on e187; HOLD**. New runtime receipts do not change its tested bytes. Current-G exact Mac check: **UNRUN**.
- B50 adapter test: **bounded GO on source 456f**; current-G transfer: **UNRUN/HOLD** because source differs. B50 finding: **LIMITED**, not closed.

After canonical source changes, review only changed code/dependencies, then run the affected exact-source discriminators on a frozen G candidate. Do not start a broad replay for these evidence-only tips.

## Location and branch qualification

The previous reply's markdown link incorrectly named the primary checkout. The report is present only at this ignored path in GROOT; readback confirms branch `codex/e02-integration` at G `127dc7ab8365d29eb656fe32c0c894f6cc971286` (tree `759daf4ccbd6e72230de8bda36e1522ffa8fe3e4`). The primary checkout at `/Users/deniskopylov/polisyos` was on `docs/raw-evidence-ignore` at `355f5e861be96ebf03ee97888a856da2c26f767f` and did not contain the report at its corresponding path; it is not treated as G state. The three incoming immutable commit objects resolve in GROOT. Candidate-specific results above remain pinned to those incoming commits; this qualification adds no current-G runtime/state replay.

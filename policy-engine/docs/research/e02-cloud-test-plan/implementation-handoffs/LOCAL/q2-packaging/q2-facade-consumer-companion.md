# Q2 public-facade consumer companion (virtual delta)

Status: **UNAPPLIED proposal**. This packet changes no product or test source, manifest, runner, environment, build, install, collection, or test execution. The final source SHA/tree remain **NULL / UNFROZEN** and Q2 remains **UNRUN**. Patch SHA-256: `bb2d4dd716cf02b5b135e82f8c96188b7bb695a040aa003ed1106bb18a485ead`; bytes: 2,594. The only proposed source/test delta is retained in `raw/q2-facade-consumer-companion.patch` (`raw/q2-facade-consumer-companion.patch`; unavailable in this checkout).

This is a successor to `current-contracts-delta-readiness.md` (preserved unchanged at SHA-256 `0b7f9152db4746d3c4bd9a1fff5790d9c66baed7968de1c1ea3aa4cb2c59173b`). Its three exact target preimages, read from the shared worktree for this patch, are:

| Path | Preimage SHA-256 | Proposed postimage SHA-256 |
|---|---|---|
| `policy-engine/tests/unit/fabric/test_semantic_group_imports.py` | `59013de3042b61b14fffb19769864d8ccc686963a478fab5fe7170abce42d968` | `0f3162454ff5b57a451119b62249044108c445a41f28ad07a3dc4e8fd780e611` |
| `policy-engine/tests/unit/foundry/methods/test_artifacts.py` | `8cd23b1a481ece841ef1dd9f202ad41b68c8b09eb3ff59d9730116c3741e357f` | `6c58683b86f279a45be7e0f011d29baa4425bb178a92dde38aa193a4a140bf07` |
| `policy-engine/tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py` | `ae65b7181b58c20c6a7be193b4388b18d3efce8caac8ae8b9bc92b6dd71d98c8` | `383d64bf0491c6e0aec96aa1f44ec573444dc1eb9c902db630e03307707b392f` |

## Proposed behavior and selectors

- Add `tests/unit/fabric/test_semantic_group_imports.py::test_identity_facade_exports_bind_all_manifest_owners`. It derives the complete legacy public `manifest` set from `manifest.__all__` when present, otherwise `vars(manifest)` excluding underscore names; it requires each facade attribute to be the exact owner object. It also derives every declared `identity.__all__` item, locates its unique owner among `manifest` and `segment_manifest`, and checks object identity. This includes the public `BaseModel`, `ConfigDict`, `Field`, and `utc_now` names that are not in the identity facade’s `__all__`, as well as `segment_manifest.write_segment_manifest`.
- Add `tests/unit/foundry/methods/test_artifacts.py::test_artifacts_facade_exports_bind_all_parts_owners`. It takes its full denominator from `parts.__all__`, checks the facade export list matches, then checks exact object identity for every class, record, helper, and factory function.
- Keep the already-selected `tests/integration/foundry/uncertainty/test_posterior_summary_persistence.py::test_native_bayesian_method_evidence_persists_candidate_summary` selector. Change its `MonteCarloPropagator` import to the curated `polisyos.foundry.uncertainty` facade. Its existing body still exercises the native method job, persisted evidence and posterior summary, fresh CAS reader, and the selected-role propagation consumer with the draw rows and candidate-only semantics asserted. This binds the actual consumer call to the public facade; it is not an import-only check.

The two tests add two planned IDs to the existing 193-ID candidate, making **195 planned IDs** once this patch is adopted. The integration test remains one existing selector whose source bytes need rebinding. This arithmetic is not a collection receipt: both new node IDs, the full collected set, and JUnit agreement remain **UNRUN** and must be recomputed after source freeze. No new scientific capability closure is claimed.

## Existing source-runtime evidence, bounded correctly

The older readiness note’s sentence “Do not treat the reported 243-owner inventory as runtime proof” is too broad. The preserved raw receipt `LOCAL/raw/batched-blocking-focused-20261010/current-full-export-identities-plus-implicit-manifest-20261011/` contains the actual `.venv/bin/python -B -c` invocation, its full stdout and command record. I parsed the retained JSON stdout: it reports `status=PASS` for 243 exact owner-identity bindings (217 Foundry API, 13 Foundry artifacts, 5 Fabric identity declared exports, and 8 implicit public manifest exports). Stdout SHA-256 is `afd74c35ce2d7bc846a8766770b18ff6c6ff2973d803a08edcc81d666a8ac4e2`; stderr is empty with SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. This is genuine **source-runtime** evidence from the recorded source checkout. It is not an installed-wheel, rebuilt-sdist, or GCP-archive consumer receipt, and it does not replace the new behavioral tests or the later installed-origin guard.

## Pattern and acceptance boundary

P29/P32/P38: assert owner identity and preserve a real persisted-consumer path, rather than names or imports. P35: derive the export sets from their owner modules and reconcile actual pytest collection after freeze. P39: keep this patch, manifest/runner rebinding, collection receipt, and installed run as mandatory companions outside the test-ID count. P40: same known facade-binding/consumer-reachability gap, widened with two generic owner-derived identity tests and the existing persisted consumer routed through the facade; no new closure category. P41: every result stays explicitly UNRUN until replayed against the frozen source and exact installed profile.

After review and source freeze, apply this patch only if its three preimages still match, rebind the three file hashes in the composed Q2 inputs, collect and reconcile the exact selector set, and then include the public-facade consumer in the serialized installed profiles. Until those receipts exist, facade installed verification remains `verification_missing`.

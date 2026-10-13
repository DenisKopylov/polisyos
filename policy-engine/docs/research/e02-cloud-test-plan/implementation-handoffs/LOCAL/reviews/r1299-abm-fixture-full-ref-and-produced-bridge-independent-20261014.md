# R1299 — ABM fixture full-reference and producer-bridge independent review

**Disposition: BLOCK for root composition.** This is a read-only independent static review of R1282r2. The proposed test-only fix has the right target and the real producer bridge is source-grounded, but the newly added fixture guard leaves two invalid helper calls in module-level parametrization data. Those calls raise during test-module import. No test was run and no source file or Git state was changed.

## Bound candidate and current source

- OWN: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, branch `codex/e02-unified-local-20261009`, HEAD `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`, tree `1355896e91789026d21396d2b087c63827ab251b`.
- Frame: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1267-20261014.json` @ `a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`, 590 physical source paths.
- Candidate patch: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1282-abm-source-basis-fixture-full-ref-denominator-successor-r2-20261014/proposal.patch` @ `1602fabd4c4c96558f97f63c120a2277396d4bdcdb80b9096e4bdc6fcf09c6a6`.
- Candidate manifest: adjacent `manifest.json` @ `cabc1f3ec3d29a6ef7013e2a7a18b338bd64d8fb30f9c43bb20feee65630e4e8`. Its two test preimages match current bytes, and an in-memory hunk reconstruction matches both manifest postimage hashes. Both proposed files parse with stdlib AST. The existing static readback records `git apply --check` exit 0, but that patch applicability does not establish module importability after the helper change.
- Author decision: adjacent `decision.md` @ `3faa9e776a0218d709885335e9248f4a141dc25dae3163b15006d11d9cde8f1e`.

## Blocking full-quantity issue

In `policy-engine/tests/unit/foundry/methods/catalog/simulation/test_abm_receipt_strangle.py`, r2 changes `_artifact_id(char)` to raise unless `char` is one lowercase hexadecimal character. Its four replacements resolve four affected failure/positive cases, but the proposed postimage still has two `_ref("g", ...)` calls:

- `_ref("g", "foundry.exec_plan")` in the `test_abm_source_basis_rejects_malformed_status_and_ref_scope` parameter list (current preimage line 204; proposed postimage line 206), whose intended discriminator is a wrong `kind`.
- `_ref("g", "foundry.execution_input_basis", media_type="application/jsonl")` in the same parameter list (current preimage line 214; proposed postimage line 216), whose intended discriminator is a wrong `media_type`.

These calls are evaluated while Python constructs the module-level `pytest.mark.parametrize` arguments, before either test executes. With r2's helper they raise `ValueError("fixture artifact id fill must be one lowercase hexadecimal character")` during import/collection. This is a deterministic static consequence, not an observed pytest result. It blocks the changed test module even though those two old rows did not appear among R1276's four recorded failing cases.

For a successor, replace the remaining two helper characters with a valid hex fill such as `"a"`; keep their wrong-kind and wrong-media dimensions intact. If a malformed-hex negative is desired, express it directly as an invalid raw payload rather than through the valid-reference factory. The relevant class is the same fixture-reference validity class, and the repair must cover all six `g` uses; do not treat the four R1276 red rows as the entire helper-call denominator.

The R1276 failure input `.../raw/composed-source35-independent-consumers-actual-r1276-20261014/full-nonpass-case-outputs.json` @ `d5a599acb36363fb6b1bcea5b4f30eda4533e3dd5e9648323bee8d2dcd334e29` contains 17 nonpass records and four ABM records. The four are the malformed-status case, the schema-1.3 case, the swapped typed-ref kind case, and the schema-1.4 positive wire-equivalence case. Their failure payloads show the invalid `sha256:gg…` digest triggering the lower-hex validator before each intended status/kind/persistence assertion. The separate wrong-kind and wrong-media parametrizations remain additional helper consumers even though they were not among those four reds.

## Producer-to-IR/CAS bridge review

The added test in `policy-engine/tests/unit/scientist/methods/search/funnel/test_source_bound_risk_candidate.py` uses the existing `foundry_source` fixture, which calls `_build_foundry_source`. That builder creates a `FileSystemCAS`, obtains a selected default registry bundle, compiles with `compile_foundry`, and executes through `execute_foundry` with `return_selected_profile=True`. It reads the produced `SimulationResult` through `_get_json_artifact`, projects its execution-basis ref using `_producer_output_ref`, reads the actual `FoundryExecutionInputBasis`, and checks its selected profile and `single_step` mode.

The new test then traces the four ref coordinates (`artifact_id`, `kind`, `media_type`, `manifest_profile_sha256`) through the source ref, the serialized simulation result, `build_abm_result_from_simulation`, and the fresh `load_abm_result` call. `persist_abm_result` writes through the existing IR artifact-store API with an `execution_input_basis` input edge; the test checks the emitted manifest edge retains the artifact ID and selected manifest profile. This is a real controlled Foundry producer-to-CAS-to-IR-reader path, not a test-supplied ref or marker. Its data is still a synthetic controlled fixture and does not establish live production evidence or external authority.

The relevant product APIs are unchanged by the candidate: `src/polisyos/foundry/methods/catalog/simulation/dynamics.py::build_abm_result_from_simulation`, `src/polisyos/ir/analytics/phase4_dynamics.py::persist_abm_result` and `load_abm_result`, and the Core-to-IR adapter. The bridge test is an appropriate semantic companion after the module-level fixture error is corrected; it remains UNRUN here.

## Scope, decision boundary, and next check

R1237 remains an author proposal for independent G: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/r1237-abm-version-namespace-and-reader-migration-proposal-20261013.md` @ `f7be74a4941f82dfbfb0e8115c2d62014b07c2ee482c211a56bcd2c0b3c85e70` explicitly leaves the persisted-version coordinate and migration ruling unresolved. R1282r2 must not be reported as resolving that namespace/publication choice. It proposes no product change or new scientific authority.

P40 classification: **same fixture-reference validity class; widen over every helper call affected by the new invariant**. Capability status remains `verification_missing / not_adjudicated` for this review, `closure_ids=[]`. A successor should regenerate the immutable patch/manifest against the same current preimages, then run the exact two-test module target plus the existing producer bridge only after independent review and root scheduling. No tests, imports, package/runtime commands, or source writes were run here.

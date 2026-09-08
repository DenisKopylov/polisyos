# Independent D1d frozen-delta review

Disposition: **approved for the final targeted verification and canonical writer/check wave; no blocking code finding**. This is bounded read-only review of the committed D1d decision and the frozen validator/test delta, not a claim that pending commands have passed. No generator, shared replay, pytest, or source edit was performed by this reviewer.

## Reviewed boundary

- `tools/quality/validation/check_layer3_gy_promotion_contract.py:931` adds the explicit reissue branch before the unchanged ordinary admitted-block preservation. Existing production N9 and generic comparison owners are unchanged by this delta.
- `_is_authorized_credal_input_epoch_reissue:982` requires both full manifests equal the actual fresh plan and all comparison identity fields except the naturally changed content hash equal. It recomputes the frozen comparison hash; the prior same-manifest admission shortcut cannot supply that warrant alone.
- The helper walks every actual plan entry and invokes its existing strict owner projector. Missing entries fail in `plan.project`; duplicate paths are refused by the existing plan constructor. No exceptional receipt-key allowlist narrows the denominator.
- A non-null reference must undergo exactly `policyos.runtime.grounding_credal_reference.v1` to `.v2`. Null-reference receipts remain part of the comparison and must otherwise be equal. Receipt projections must agree after only this field changes, and the entire projected envelope must also agree. Extra governing changes inside or outside a receipt therefore do not authorize reissue.
- Projection calls produce independent typed/model-dumped values; only those temporary projections are normalized. The branch returns the actual newly produced live envelope, not edited historical receipts. Old bytes are preserved as the historical fixture.

## Verification reviewed

`tests/repo_quality/tools/test_layer3_gy_promotion_contract.py:32` uses the actual writer then normal validator against an isolated output file initially containing the historical capture; it does not synthesize a positive promotion or swap the canonical input denominator. It checks all actual admissions, current receipt epochs, refusal/non-promotability, and unchanged historical fixture bytes.

The added refusal tests cover an unsupported input epoch, a governing change within a receipt, a governing change outside admitted receipts, changed comparison epoch, invalid outer content hash, invalid inner comparison hash with a valid recomputed outer hash, and absent/null/empty/duplicate/novel/scalar admission manifests. The removal test disables only the new transition predicate and requires the actual writer to return the old owner semantic mismatch without changing the historical output.

Read `pr1/d1d-reissue-red.json`: actual writer rejected the old capture with `current_governing_projection_drift` / `promotion_legacy_comparison_semantic_mismatch` before repair. Read the initial `pr1/d1d-reissue-green.json` and `pr1/d1d-final-ruff-v2.json`, both RC0. The initial green predates the expanded negative matrix; its coverage must not be reported as that final matrix. Root/PR1 owns the final frozen command result and full test-identity reconciliation.

Independently read the verbatim historical fixture and `git show 3d572c146:policy-engine/architecture/policy_design_case/layer3_gy_promotion_contract.json`; exact byte equality holds, SHA256 `4825fd7adac74ef35a351d023dbd0069952b602b26b1c124c7795ef696f1a59a`. This is a retained owner-produced capture, not a newly constructed receipt.

## Pattern disposition

P27: extend the existing governed capture-reissue owner; no parallel semantic comparator or production evaluator.
P29: actual writer/check red-first and removal; final canonical regeneration/check and drift remain required.
P37: authority to reissue comes from fresh owner admission plus recomputed complete comparison, not the persisted manifest or schema string alone.
P38: the predicate measures exact allowed semantic transition, not merely two matching schema labels or a receipt count.
P40: no new escape found in this bounded delta. Previously declared law-correspondence and scientific-source limitations remain worked examples of their existing scope, not new review rounds or repaired capabilities. §§3.5.5–6 remain unchanged.

## Frozen files

- `tools/quality/validation/check_layer3_gy_promotion_contract.py` — SHA256 `c22dfbdacaea081511a082d5ac4becaf203f1926b0b99fd1dcc0c700e3d72384`.
- `tests/repo_quality/tools/test_layer3_gy_promotion_contract.py` — SHA256 `2b602b3697f9018613e27a8b822e532e1318b2375b01a9a7239a785df64a3a98`.
- `tests/repo_quality/tools/fixtures/layer3_gy_promotion_contract_credal_v1.json` — SHA256 `4825fd7adac74ef35a351d023dbd0069952b602b26b1c124c7795ef696f1a59a`.

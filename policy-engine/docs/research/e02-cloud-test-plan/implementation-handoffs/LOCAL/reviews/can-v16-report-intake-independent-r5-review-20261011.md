# CAN V16 report intake r5 independent review

Disposition: **GO to apply as candidate-only source, with the bounded residual below.** This is not runtime verification, G acceptance, integration publication, or formal finding adjudication. `closure_ids` remains empty.

## Exact candidate and admission

- Entry source base: `0390c44e7f9871122c21afa78af844cbafaa1d0e`, tree `33e1305efb43bb01960faf65808449cc4bd7a891`.
- Checkout at review: HEAD `2ace03593a28a6bb5cc4688602fc731444f7408f` (the doc-only packet commit); product postimage inputs remain the exact dirty-worktree preimages captured in the r5 manifest.
- Patch: `implementation-handoffs/LOCAL/raw/can-v16-report-intake-overlay-20261011-r5/can-v16-report-intake-v16.patch` @ SHA-256 `bf848a17ca8d1c71c76d2efd853ac8bb0b67307310bed83b340c06eb98bd7030`.
- Manifest: same r5 directory, `manifest.json` @ SHA-256 `3feb9d20d923b0bb42fbfa90b88102aa97198868c54d3f5543edf53a2cbf4ef5`.
- Validation receipt: `validation.json` @ SHA-256 `da737fade0cd7351cf34f55dcf7d2d4f96b6184ec6634c296d45fec4a2359fa1`.
- All six preimages matched independently, including the pre-existing untracked `report_registry.py` and the dirty `canary_evidence.py` at `a739a244116e0fac1c1c4aae38357f2160c18ba1cf787e964eaa4c164714fd54`. `git apply --check` passed. Product source remains unapplied by this reviewer.

## Reviewed behavior and evidence

The r5 classifier widens registered report-body handling across the complete 61-alias registry. Markerless mappings for every registered body alias remain bodies, bodies do not synthesize ref roles when no producer-owned runtime role exists, and `quality_evidence` candidate refs do not seed the runtime-owned admission surfaces. The prior r2 escape is closed: for the same registered PGM body key, malformed `artifact_id` text with an extra unknown field produces a typed `control_character` refusal and no selected role. The marker-preserving removal probe demonstrates that removing the classifier makes that refusal disappear while the same input and markers remain.

The CAS-bound Canary controls compare a selected report's self-declared role identity to the selected runtime ref and refuse a mismatch; a serious bundle uses the loaded selected CAS body over a contradictory inline candidate, including status and issue content. The missing-runtime-ref consumer control continues to assert that the five serious roles are absent from both scorecard evidence refs and the artifact intake map. Typed refusal rows survive ref stripping. The removed `policy_design_case → claim_registry → runtime_authority` extraction was a local pure-read chain whose `runtime_authority` result had no consumer; `_first_dict` and `_nested_get` remain because other paths use them.

The immutable validation receipt reports compileall, canonical Ruff, patch admission, five focused semantic tests, and the marker-preserving removal probe as passing. These checks are source-bound to the overlay; the full Canary/runtime suite and the composed root replay remain **UNRUN**.

## Bounded residual and next check

An independent falsifier against the frozen r5 overlay used a registered PGM mapping with a syntactically valid `artifact_id` plus an unknown extension. The exact result at `implementation-handoffs/LOCAL/raw/can-v16-valid-wrapper-extension-falsifier-20261011-r2/result.json` @ SHA-256 `c27778e2ee014a604f815a9e6dcfd2a819613f153f26a96ab81fe7b59cdb5084` is: no role selected, no unrejected ref, and no typed rejection. This is fail-closed for authority selection; it does not establish diagnostic refusal for every valid-looking generic ref plus unknown extension.

The intake accepts open `Mapping` report bodies and does not bind a closed PGM DTO/full field set at this boundary. Without that discriminator, the code cannot tell whether the extra key is a legitimate report-body extension or an invalid wrapper extension. The smallest closure choice is to bind an existing complete versioned strict schema at intake, if one exists, or to adopt a global generic-wrapper-plus-unknown rule with an explicit extension migration. This needs G's semantic decision if reuse cannot supply the complete field set. Until then, hold any proposal claiming that every malformed wrapper yields a typed refusal; retain the narrower tested claim that malformed generic-ref values produce a typed refusal and no selected authority role.

P40 classification: the mixed malformed-value wrapper escape was the same class one level deeper; r5 widens the shared mechanism and tests it across the registry. The valid-value-plus-extension ambiguity is recorded as the bounded residual after that widening. No G finding occurrence is formally closed by this review.

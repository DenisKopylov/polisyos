# R1089 independent review: selected-manifest edge test

**Disposition: GO for root-owned materialization and the focused native test.** The R1085 test delta fixes R1081’s invalid `InputRef.kind`/`media_type` access and now exercises the full six-role selected-reference binding property. This is not source acceptance or G acceptance; the runtime test remains unrun here.

## Frozen stack and source binding

- Checkout: branch `codex/e02-unified-local-20261009`, HEAD `9511169e1a7f6dbd4137de824905dfbff8992a3f`, tree `d6d48c83b5a60afdead8066253bc30cd216f5913`.
- Root frame: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/root-author-source-frame-r1076-20261013.json` @ `018b1e5998e45ca73fcfb4cac4fbcee11c0851610d283d2e9c2dff2f7ba39e12`, with 553 source entries.
- Three tracked dirty source paths at review time were `runtime/quality/design_axes/outcome_prediction.py`, `tests/unit/runtime/http/test_control_service_di.py`, and `tests/unit/runtime/quality/design_axes/test_outcome_prediction.py`; their set is disjoint from the frozen R1009 19-file set.
- R1009 frozen producer source: patch `.../LOCAL/raw/r1009-adjudication-whole-selected-input-edge-emission-20261013/r1035-rebound-r2c/candidate-r1009-rebound-r2c.patch` @ `3d46ebf6b9dddb4625f220706b40ddca68b993ae4a2392cc22cc46334cdc238a`; source pre/post @ `9b13ca1495574314e1b5e974f24161a09fd4627333ef31a24c96df8448a5c0ca`. Its 19-path denominator is 17 `.py`, one `.md`, one `.toml`; current physical preimages match 19/19, with the new release fragment correctly absent at its null preimage.
- R1054 predecessor patch @ `d9e0ed39e2b401b77bffb7cb1feb7783be45627de1e1ccdbe9a120ec8c326a62`, manifest @ `a00bcb7a2490595586a4daf6a7468ccb0664024558f74d64132a18c298c94fa4`, and target postimage @ `a2f8444914058ac1cb81ec4947bc03f7de0f8435318a2af3326cb000ae854486`.
- R1085 candidate patch: `.../LOCAL/raw/r1085-adjudication-selected-manifest-edge-semantic-test-companion-20261013/candidate-r1085-test-delta.patch` @ `7f30764d2c1c9c6b069483da9bf562b621e92f84e4a8c621b7210145843b2fee`; manifest @ `2cd40e2fe5c82453b6a0928cf489a70c2d290080f75da925aea6229c3138e573`; target postimage @ `3a07df70f4d02dfc17520f6e5b90f085971e0d2590c4b83c275cab5c926140a9`. R1085 source-pre/post @ `6173c999dcb34bc94284f6387f373dbeca1327d5ff4502b5b9283a02b6432668` proves the candidate is one `.py` test file, based on the exact R1054 postimage. The physical test file remains the recorded checkout preimage, so this is an unapplied virtual candidate.

## Property review

R1085 no longer treats a lineage `InputRef` as an `ArtifactRef`. It reads the result manifest once, maps its edges by role, checks role uniqueness (`len(inputs) == len(result_manifest.inputs)`), and requires an exact match to all six expected roles. For each edge it checks the role, artifact ID, and non-null selected profile against the corresponding producer-returned `ArtifactRef`; it resolves that exact `(artifact_id, profile)` with `store.get_manifest_by_profile`, converts the persisted manifest using the public `artifact_ref_for_manifest` helper, then compares artifact ID, kind, media type, and profile to the actual expected reference.

This is sufficient for the test’s stated property: the result’s persisted role edges select the same typed manifest views as the fixture producers returned. The exact role-set check catches missing/extra edges; the count check catches duplicate roles otherwise collapsed by the dict; selected-profile equality and lookup refuse missing or substituted views; the converted-ref comparisons bind the persisted manifest descriptor to the producer identity. `InputRef.role == role` is redundant because the dictionary key comes from that same field, but its removal would not remove the tested property; the independent set, duplicate, identity, profile, and resolved-descriptor assertions carry it.

The resolution verifies the selected manifest view, not a separate payload-byte read. This test makes no new claim about CAS blob-integrity verification; that remains the store’s responsibility and existing CAS read path. R1085’s production-source delta is empty, so the previous R1048 review of the frozen R1009 producer mechanism remains the relevant source bound.

## P40 and verification boundary

P40 classification: **SAME_CLASS_DEEPER, widened to the complete current edge set.** R1048 found the omitted sixth `benchmark_suite` role; R1081 then found invalid field access while trying to bind that role. R1085 closes both at the whole current six-role edge contract rather than adding a one-role exception. I found no remaining escape in this test’s current role/ref quantity.

The author receipt reports AST, one-file roundtrip, Ruff check, and Ruff format passes. Pytest/runtime/native remain `UNRUN`; run the focused test after root-owned materialization. External evaluator issuance remains `producer_missing`; B117 process/crash/race remains `UNRUN`; `closure_ids=[]`. No product/source files were written by this review.

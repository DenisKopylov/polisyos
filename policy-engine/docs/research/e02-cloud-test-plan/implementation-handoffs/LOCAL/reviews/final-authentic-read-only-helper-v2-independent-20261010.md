# Independent delta review: bounded authentic read-only helper v2

**Static delta verdict: GO to the coordinating task’s planned focused controls and bounded named-source attempt.** The three blockers in the prior review are repaired in this version. This is not a runtime or closeout pass: I did not execute the helper, call HTTP, open a database, run tests, or inspect production payloads.

## Reviewed inputs

- Helper: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/final_authentic_read_only_check.py` — SHA-256 `d8f44b0f2ff8983839f72345865e77d82479a84eb5dc7c46e03161f32d4082ec`.
- Readiness note: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/decisions/final-authentic-read-only-command-readiness-20261010.md` — SHA-256 `3be45e00598439209a92f664a7723586983eebcecc5f09d7d88e61449135d91a`.
- Prior review: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/reviews/final-authentic-read-only-helper-independent-20261010.md`.

## Delta findings

The typed-ref comparison now uses the canonical strict `ArtifactRef` model. `_canonical_ref` requires the three non-optional fields, rejects extras, and validates both actual and expected values with `strict=True`; malformed-present mappings therefore refuse instead of matching through missing `.get()` values. The canonical model allows a missing profile field as its real legacy default. `_ref_matches` treats either side without a profile hash as `unverified_profileless_legacy`, with `protected_binding_match=False`; it cannot make the overall check exit `3`. The output also explicitly says reference identity does not verify artifact-body custody. This addresses the previous malformed-ref/body-custody concern without claiming more than the identity check establishes.

JSON Pointer decoding now validates each `~` escape and accepts only canonical nonnegative list indices. Invalid escapes and indices such as `01` or `+1` refuse rather than selecting a descriptor. Filesystem and other input failures emit stable error codes or exception type names, not exception messages; the direct root resolution, member hashing, and outer failure path no longer print the private path value. Static resolved-path containment remains intact: absolute member paths are rejected, in-root targets are resolved, and resolved escapes are refused.

No additional source blocker was found in the inspected delta. The helper remains bounded to one named manifest and two distinct declared members, with no database access, directory walk, service startup, or payload output. Its stdin is still caller-supplied JSON: the helper does not authenticate the HTTP origin or prove request freshness. The readiness note and output correctly leave serving profile, source currentness, and closeout incomplete. Likewise, the two descriptor hashes are reported for the owner-selected manifest pointers; the helper does not claim those bytes independently establish custody of the snapshot/trace artifact bodies.

## P40 and remaining evidence boundary

**P40: same selector-integrity class, now fixed at the generic intake boundary.** The v1 empty-dictionary ref match and permissive pointer parsing are addressed structurally by strict model validation and standards-conformant pointer decoding; no per-member patch or further hypothetical expansion is indicated. The earlier redaction finding is also fixed at the shared error-output boundary. The remaining required evidence is the coordinating task’s actual malformed/present/refusal and valid profiled/profileless controls, followed by the bounded named-source attempt. Until those run, this review supports only a static delta GO; it does not establish runtime behavior, authentic HTTP provenance, profile/currentness binding, or B13 closure.

# B148 import report disposition choice

Date: 2026-10-11
Status: local additive candidate for independent G review; no formal closure
Basis: committed source `cd5651c3a6897f12d32212e3521e73bb570f137b`; B148 original criterion in `B_r19_original.md` §51.

## Choice

Keep the legacy `imported_artifacts` count and `imported_refs` selector tuple unchanged. Add separate fields for received unique IDs, canonical manifest-profile views published or reused, and exact refs actually returned by an integrity verifier. Canonical profile identity uses the content profile digest, so a selector-free default and its explicit profile alias count once while distinct profiles remain separate. CLI JSON and text surfaces project one shared typed report.

The disposition source is the owner transaction boundary: `published_refs` are views with a manifest stage in the completed durable transaction intent; `reused_refs` are exact admitted views or transaction views with no manifest stage. A stage carried by a recovered pending intent is reported as transaction-published, not as bytes written by this invocation. Sorting and projection are completed after the owner outcome has been assembled and cannot cause a post-publication comparison of `None` with a profile string.

When `verify_integrity=True`, staged candidates and exact reused views are sent through the real verifier before successful return. Only verifier-positive canonical refs enter `integrity_verified_refs`. When false, that list is empty. A failed verification blocks new publication and remains visible in `verification_failed`; previously admitted exact views remain separately identified as reused.

## Alternatives considered

A: redefine `imported_artifacts` as newly published views. Rejected because it breaks the established count contract and conflates IDs with profiles.

B: infer reuse/publication from `Path.exists()` after the callback. Rejected because it races publication, mislabels partial transactions, and can claim this invocation wrote recovered bytes.

C: preserve the count and report selection intent only. Rejected because it hides actual admitted/published view outcomes from callers.

The additive report is the narrow compatibility extension. Existing callers can continue using the old fields; new consumers can distinguish bytes received, exact views reused, stage-intent publication, and integrity checks. No migration changes stored manifests or CAS ownership.

## Limits and acceptance

This report establishes local bytes/profile verification and durable owner-intent disposition only. It does not establish an external signer, signature trust, owner authorization beyond existing CAS admission, provenance truth, custody outside the local store, or production currentness. G must independently review the code and tests, re-run the source-bound consumer routes, and adjudicate the original B148 whole-property criterion. `closure_ids` is empty.

Pattern pass: P04/P05 (status and authority), P12 (producer/consumer handshake), P29/P32/P33 (behavioral verification), P38 (count proxy divergence), P40 (full profile-identity quantity). Target pattern: additive typed report derived from owner admission and durable transaction intent; negative tests for corrupt bytes, failed publication, profile alias and exact reuse. Capability still limited until the complete composed candidate and all required G verification pass.

## Reuse-first selection, migration, and status meaning

The implementation reuses the existing archive intake, staged integrity verifier, immutable CAS owner transaction, and public `ImportReport`. It extends the report with defaulted fields so existing Python construction and the legacy `imported_artifacts`/`imported_refs` meanings remain available. A small internal `ImportPublication` value carries the owner transaction's actual refs and stage-intent basis across the existing bridge; it does not replace or bypass the CAS owner. The four JSON and four text replay branches reuse one report projection. No new CAS, manifest format, or storage migration is introduced.

The four outcomes have distinct bases: `received_artifact_ids` are unique recognized IDs in incoming members; `published_refs` are canonical profile views whose manifest stage was present in the completed owner intent; `reused_refs` are exact admitted or unstaged owner views; `integrity_verified_refs` contain only canonical refs returned as successful by the configured verifier. Recovery of a pending transaction is described as completion of its durable stage intent, never as bytes newly written by this invocation. `verify_integrity=False` produces no verified refs. These are local transaction and verifier observations, not claims about external custody, signer authority, owner identity beyond the existing admission contract, provenance truth, or production currentness.

Migration is additive at the report and CLI boundaries. Stored manifests and existing CAS bytes are unchanged. Existing consumers may continue reading legacy fields; consumers adopting the new fields must treat `disposition_basis` as required context, not infer publication from `imported_artifacts`, `Path.exists()`, or an artifact ID alone. CLI text adds a compact outcome line; JSON adds a `bundle_import` object while retaining all prior keys.

## Candidate lineage

This candidate is derived from the exact committed B148 preimages named in its manifest using the versioned local composer and verified virtual overlays. A separately captured older composer/candidate was not applied or used as source; its authorship and provenance remain `not_established`. This statement does not attribute, repair, or accept those bytes.

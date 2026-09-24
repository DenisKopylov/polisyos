# R10 Signature Boundary Map

Status: read-only implementation plan, prepared 2026-09-24 while the four-base
baseline was pending. No tests or native jobs were run for this note.

## Property and boundary

`FileSystemCAS.verify_signature` must treat a canonical valid string
`ArtifactID` exactly like the typed `ArtifactID`, and return a typed `ERROR`
without CAS reads for malformed strings. Existing integrity, signature,
trust, revocation, identity, and result behavior for typed IDs stays the same.

The public boundary is
`policy-engine/src/polisyos/core/artifacts/store.py:569-586`. It currently
passes its `artifact_id` argument straight to
`core/artifacts/_signature_ops.py:180-201`, where the first operation is
`load_snapshot(artifact_id)`. The concrete
`FileSystemCAS._load_verified_snapshot` expects an `ArtifactID` and routes it
through ownership and path resolution at `store.py:1166-1175`; path resolution
needs `.hex`. A valid string therefore becomes `ERROR` before signature lookup.
The neighboring `FileSystemCAS.verify` already accepts `ArtifactID | str` and
normalizes before storage access (`store.py:803-807`).

Smallest implementation: widen `verify_signature`'s annotation to
`ArtifactID | str`, preserve the original string, and normalize it before
calling `_verify_signature`:

1. If input is an `ArtifactID`, keep it unchanged.
2. If input is a string, call `ArtifactID.model_validate` once.
3. On ID-validation failure, return
   `SignatureVerificationResult(status=ERROR, artifact_id=original_string,
   message=...)` immediately. Do not call snapshot, signature, blob, manifest,
   or ownership operations.
4. Delegate valid typed IDs through the current `_verify_signature` path.

`ArtifactID` is a `RootModel[str]` (`core/artifacts/ids.py:13`). Its validator
requires the `sha256:` prefix, lowercases the digest, and checks for 64 hex
digits (`ids.py:22-39`). Uppercase hex is accepted and canonicalized. Missing
prefix, unsupported prefix, wrong length, non-hex input, and empty strings
fail validation. Catch validation exceptions narrowly (Pydantic validation,
`TypeError`, and `ValueError` as applicable); do not turn later storage or
cryptographic errors into malformed-ID errors. A syntactically valid but
absent artifact continues through the existing integrity `ERROR` path.

The malformed branch can safely preserve the requested string because
`SignatureVerificationResult.artifact_id` is already typed `str`
(`core/artifacts/signing.py:104-115`). No result-model or signature-record
schema change is needed.

## Complete caller census

The census walked every `*.py` under `policy-engine/src/polisyos` and
`policy-engine/tests`: **5,415 `.py` paths**. A literal
`.verify_signature(` scan found **28 call expressions in 19 files**: 16 source
and 12 test calls. A second all-occurrences review found one additional
indirect invocation through a retrieved callable in
`runtime/quality/promotion_safety.py:231-242`. Total invocation denominator:
**29**.

| Source call sites | Lines |
| --- | --- |
| `src/polisyos/core/artifacts/store.py` (bulk verification delegation) | 633 |
| `src/polisyos/core/components/_cli_crypto.py` | 264 |
| `src/polisyos/foundry/methods/equivalence/store.py` | 156 |
| `src/polisyos/lex/knowledge/multilingual_assurance.py` | 343 |
| `src/polisyos/runtime/http/access_audit.py` | 822, 905 |
| `src/polisyos/runtime/http/services/acquisition_admission_bundle.py` | 216 |
| `src/polisyos/runtime/http/services/control/run_lifecycle.py` | 1295 |
| `src/polisyos/runtime/quality/agent_action_authority.py` | 1216, 1367 |
| `src/polisyos/runtime/quality/capability_authority.py` | 402 |
| `src/polisyos/runtime/quality/design_axes/value_choice_provenance.py` | 666 |
| `src/polisyos/runtime/quality/obligation_coverage.py` | 532, 589 |
| `src/polisyos/scientist/evidence/claims/owner_events.py` | 315, 318 |
| `src/polisyos/runtime/quality/promotion_safety.py` (dynamic callable) | 231-242 |

| Test call sites | Lines |
| --- | --- |
| `tests/unit/core/phase0/test_store_signing.py` | 52, 66, 79, 113, 114, 197 |
| `tests/unit/remediation/test_cas_02.py` | 324 |
| `tests/unit/remediation/test_cas_03.py` | 84 |
| `tests/unit/runtime/http/test_human_decision_service.py` | 2840 |
| `tests/unit/runtime/http/test_runtime_authorization_access_audit.py` | 965 |
| `tests/unit/runtime/http/test_runtime_deployment_security.py` | 336 |
| `tests/unit/runtime/quality/test_agent_action_authority.py` | 817 |

The raw-string consumers are `obligation_coverage.py:499-514,532,589` (its
accepted references are `tuple[str, ...]`), `value_choice_provenance.py:662-667`
(`ref: str`), and the dynamic PromotionSafety call at `promotion_safety.py:231-242`.
Other current callers either normalize first or pass an `ArtifactID`.

Related local verifier Protocols are declarations, not extra invocations:
`runtime/http/access_audit.py:71-77`,
`runtime/http/services/control/run_lifecycle.py:426-432`,
`runtime/http/services/acquisition_admission_bundle.py:73-79`,
`runtime/quality/agent_action_authority.py:79-85`, and
`runtime/quality/capability_authority.py:185-191`. Their present callers
normalize before calling. The general `core/artifacts/protocol.py` does not
declare a signing method. No caller-specific type patch is required for R10.

## Behavioral witnesses

The two representative main witnesses are:

- `tests/unit/runtime/http/test_human_decision_guarded_custody.py::test_guarded_store_custodies_record_and_recovers_signed_orphan[True]`.
  Its recovery case runs
  `test_human_decision_service::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2`,
  which calls `verify_signature` with the string record reference at
  `test_human_decision_service.py:2840`.
- `tests/unit/runtime/quality/test_promotion_safety.py::test_canonical_port_and_independent_reader_share_fixed_source_trust`.
  Its source reference is a string and reaches the indirect verifier at
  `promotion_safety.py:242`.

Also replay the Appendix-B siblings:
`test_human_decision_service::test_human_decision_hard_crash_reconciles_null_ref_signed_orphan_before_v2`
and
`test_promotion_safety::test_signed_source_custody_never_establishes_promotion_policy[None]`.
These exercise the same raw-string routes under their standalone service and
source-custody flows.

### Removal probe

In `tests/unit/core/phase0/test_store_signing.py`, sign a real fixture and call
the public API with `str(ref.artifact_id)`. Spy on `_load_verified_snapshot`
and assert it receives an `ArtifactID`; delegate to the original loader and
assert the result is `VALID` with the expected key and signer. Removing the
boundary conversion while leaving the `ArtifactID | str` annotation and result
markers makes this behavioral assertion fail: the raw string reaches the
typed loader and verification returns `ERROR`.

### Malformed-input cases

Add a malformed-string matrix for missing `sha256:` prefix, unsupported
prefix, wrong digest length, non-hex digest, and empty string. Each case must
return `ERROR`, preserve the exact input in `result.artifact_id`, and perform
zero CAS reads. Instrument `_load_verified_snapshot`, `get_signature`,
`get_bytes`, and `get_manifest_bytes` to raise if reached; no such spy may fire.

### Property-preserving control

Keep the existing typed-`ArtifactID` valid, unsigned, malformed-sidecar, and
signature-transfer controls in `test_store_signing.py:45-115,191-198` green
with unchanged statuses. Also verify an uppercase-hex valid string
canonicalizes and returns the same verification result as the typed ID.
R10 changes only an input boundary; persisted manifest, signature, and
historical evidence bytes do not change.

## P37 / P38 classification

- **Property:** a syntactically valid string representation of an artifact ID
  reaches the same signature verifier as the equivalent typed ID; malformed
  IDs fail closed before I/O.
- **P37 predicate:** ID syntax/canonicalization is `recomputed` by the
  `ArtifactID` validator. The signed bytes and signature validity remain
  recomputed by the existing snapshot and cryptographic verifier path. A
  caller-supplied string is not evidence that an artifact exists or is signed.
- **P38 divergence:** current code effectively tests the Python input type at
  the snapshot boundary. A valid `sha256:<64hex>` string and an
  `ArtifactID` denote the same ID, but only the typed instance reaches the
  loader correctly. The implementation therefore reports `ERROR` precisely
  for a valid public representation. The valid-string removal probe above
  distinguishes the property from the current type proxy.

Applicable design references: the identity boundary requires typed,
fail-closed evidence when another signature affects our claim
(`policyos-identity-and-custody-boundary.md:100-112`); signature verification
is not signing and a verifier Protocol only describes shape
(`policyos-identity-and-custody-boundary.md:201-207`). The failure-pattern
register requires rule-versioned replay (P07), an owner-level class repair and
content-bound verification (P31/P32), malformed/sibling probes (P33/P34),
predicate classification (P37), and a named divergent case (P38)
(`policy-design-case-failure-patterns.md:52,82-83,341-350`).

## Write set and R9 sequencing

R10's prospective mechanism write set is one file:
`policy-engine/src/polisyos/core/artifacts/store.py:569-586`. Its focused test
write set is `policy-engine/tests/unit/core/phase0/test_store_signing.py`.
Do not edit `signing.py`, `_signature_ops.py`, `core/artifacts/protocol.py`, or
the already-normalizing callers for this class.

R9 also owns `core/artifacts/store.py` for typed views and view-signature
storage. Therefore land R10 as its own commit first, after verifying branch
attachment and before R9 edits begin. R9 then extends the same owner in a later
commit; it must rerun the valid-string, malformed-string, and typed-ID
signature tests. Keep R9 view-specific test additions in a separate test file
so the two classes do not race on `test_store_signing.py`.

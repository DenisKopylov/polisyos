# English reader translation of ADR-0010: CAS artifact signing (Ed25519)

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0010-cas-artifact-signing-ed25519.md`

This page translates the decision text in the [source ADR](../../adr/0010-cas-artifact-signing-ed25519.md), whose SHA-256 is
`51d3ce5640fc81d5799bfb548b06f9b412d062e70f42ff1a710276c80db82790`.
The generated ADR index reports the source status as `accepted` at the source
pin. This derivative does not ratify or revise the decision and does not
establish that the decision was implemented.

- **Date:** 2026-02-07
- **Status in source:** Accepted
- **Roadmap label:** ADR-006

## Context

CAS already guarantees integrity (`sha256(blob)`) in Policy OS, but it does
not guarantee authenticity or non-repudiation. That is insufficient for
government / audit scenarios: artifacts need a cryptographically verifiable
origin.

## Decision

1. Add detached signatures in sidecar files `<artifact>.sig` beside
   `<artifact>.blob` and `<artifact>.manifest.json`.
2. Use **Ed25519** (through `cryptography`) as the signing algorithm.
3. Sign a canonical statement with these fields:
   - `artifact_id`
   - `blob_sha256`
   - `manifest_sha256`
   - `key_id`
4. The signature source of truth is the `.sig` file (do not rewrite the
   manifest).
5. Add a trust store:
   - `.polisyos/keys/trusted/*.pub`
   - `.polisyos/keys/revoked/*.pub`
   - `.polisyos/keys/identities.json` (optional `key_id` ->
     identity binding)
6. Verification returns a status model:
   `valid | unsigned | invalid | untrusted | revoked | error`.
7. Use `ThreadPoolExecutor` for bulk operations.
8. When `sign_on_put=true`, sign inside `put_bytes` before it returns
   (the default `fail` policy applies).

## Consequences

### Advantages

- Supports chain of custody for CAS artifacts.
- Prepares for Phase 7 (external audit export) with standalone verification.
- Provides a scalable batch verification / signing model for CI.

### Disadvantages

- Adds one sidecar file per artifact.
- Adds operational overhead (trust store, rotation, revocation).

### Risks and mitigations

- **Private-key compromise:** key rotation + revoked list.
- **Identity spoofing in `signer_identity`:** binding by `key_id`, strict
  identity mode.
- **Unsigned drift when `sign_on_put` is enabled:** fail-hard policy inside
  `put_bytes`.

## Alternatives

- Inline signature in the manifest: rejected (mutability / circularity risk).
- Signature as a separate CAS artifact: rejected (complex lookup and
  association).
- RSA / ECDSA: rejected because of size / complexity / operational tradeoffs
  for this use case.

## Related Decisions

- Extended by: ADR-0122 (lakehouse snapshot semantics), ADR-0123
  (ArtifactRef governance metadata), ADR-0128 (hermetic reproducibility).
- Related: ADR-0118 (release train and SemVer contracts).

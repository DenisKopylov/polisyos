# Artifact Signing or SBOM Failure

Related explanation: [Security Model](../explanation/security-model.md). Related
reference: [Ownership](../reference/ownership.md). Related how-to:
[Installation](../how-to/install.md).

> Use this runbook when artifact signing, audit-package verification,
> SBOM generation or verification, or SLSA payload validation fails.

Owner: `@platform-owners`
Historical validation receipt (as recorded by this page): `2026-04-17` — signing/SBOM regression and release-evidence material available at that time; this is not a fresh validation.
Evidence path: `docs/reference/security-compliance.md`; `docs/archive/reports/platform-acceptance.md`; `tests/unit/core/security/test_sbom.py`
Rollback path: return to the last trusted signer and trust-store state, block promotion, and only time-box any temporary allowlist or grace-window exception.

## Symptom

- The `runtime-signing` surface fails in `polisyos-tools workspace doctor`;
- CI or the release gate reports unsigned artifacts, an invalid signature, an untrusted
  key, or a revoked signer;

- Sigstore/cosign verification of release assets or `SHA256SUMS` fails;
- The SBOM gate returns `deny`, `critical` CVEs appear, or
  `polisyos_sbom_deployment_gate_total{decision="deny"}`;

- The audit verifier reports a missing `slsa/attestation.json`,
  `slsa/signature.json`, or `provenance/prov.json`.

## Likely Causes

- `POLISYOS_SIGNING_KEY` or `POLISYOS_SIGNING_KEY_FILE` is missing or invalid;
  `POLISYOS_SIGNING_KEY_FILE`;

- The GitHub OIDC-based Sigstore signing step did not receive an identity token or ran
  outside the canonical release workflow;

- The trust store and `identities.json` are out of sync after rotation;
- The artifact was built outside the canonical signing path;
- `cyclonedx-py`, `syft`, or `grype` is unavailable or produced malformed output;
- The vulnerability threshold or allowlist changed and now correctly returns `deny`.

## Timeline Capture Expectations

Record:

- The UTC timestamp of the first failed verification;
- commit/release candidate/build ID;
- The exact failing step: signing, provenance, SLSA, SBOM generation, or the SBOM gate;
- The affected artifact family: CAS blobs, audit package, release bundle,
  or runtime image;

- The key ID, signer identity, trust-directory revision, and vulnerability threshold;
- If the denial involves a CVE, record the package, version, CVE ID, and CVSS score.

## First Triage Steps

1. Confirm that the optional surface is ready:

   ```bash
   cd policy-engine
   uv run polisyos-tools workspace doctor --surface runtime-signing
   ```

2. Check the signing inputs:

   - Confirm that the current process can read the private key;
   - Confirm that the trusted and revoked key sets are current;
   - Confirm that rotation did not leave the old key active after revocation.
   - Confirm that Sigstore signing saved the `.sig` and `.pem` sidecars beside the release
     assets.

3. Run the focused security tests:

   ```bash
   cd policy-engine
   uv run pytest \
     tests/unit/core/phase0/test_cli_signing.py \
     tests/unit/core/phase0/test_store_signing.py \
     tests/unit/core/security/test_sbom.py
   ```

4. If the audit package is affected, check for:

   - `provenance/prov.json`
   - `slsa/attestation.json`
   - `slsa/signature.json`
   - signature sidecars under `signatures/sha256/`

5. If the SBOM gate denies promotion, distinguish a tooling failure from a legitimate vulnerability:
   first check whether the generator or scanner is broken, then decide whether an
   allowlist entry or dependency patch is appropriate.

## Rollback / Mitigation

- If tooling or configuration drift broke the signing path, restore the last
  known-good signer configuration and trust store;

- If key rotation caused the issue, keep the previous public key trusted temporarily
  until the grace period ends;

- If the SBOM denial is valid, do not promote; fix or pin the dependency
  instead of bypassing the gate;

- Allowlist a CVE temporarily only after security review and with an expiry date;
- Never silence missing provenance or signatures with an ad hoc “green button”.

## Escalation Owner

- primary: `@platform-owners`;
- security review and policy approval: security/compliance owner path;
- Supporting: the subsystem owner, if unsigned artifacts are produced only in that subsystem.

## Follow-up Checklist

- It is established whether the failure was tooling-related or policy-correct;
- Rotation artifacts and the trust store are synchronized;
- Any allowlist entry has an owner and expiry date;
- The [Key Rotation](../key-rotation.md) page is updated after the incident if it was
  the source of drift;

- Security alert routing and dashboard ownership are current.

## Blameless Postmortem

### What Went Well

- Which verifier or metric provided the first accurate signal;
- Which safeguards stopped the bad artifact before promotion;
- Where the trust model was clear and verifiable.

### What Went Poorly

- Where the signing or SBOM path depended on tacit knowledge;
- Which environment variables, keys, or trust files were too implicit;
- Where policy was bypassed manually instead of following a clear runbook path.

### Action Items

| Action item                                                             | Owner              | Due date   | Status |
| ----------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Fix the broken signing, verification, or SBOM generation path           | `@platform-owners` | YYYY-MM-DD | open   |
| Remove or time-box any temporary exception introduced during mitigation | security owner     | YYYY-MM-DD | open   |
| Improve visibility of trust store, provenance, or vulnerability gating  | `@platform-owners` | YYYY-MM-DD | open   |

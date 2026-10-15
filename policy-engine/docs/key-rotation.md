# Key Rotation for CAS Artifact Signing

Related ADR: [ADR-0102](adr/0102-key-rotation-lifecycle-and-trust-store-policy.md).
Related runbook: [Key Rotation](runbooks/key-rotation.md).

Owner: `@platform-owners`
Source of truth: `policy-engine/src/polisyos/core/security/rotation.py`, `policy-engine/src/polisyos/core/components/_cli_security.py`, `policy-engine/src/polisyos/core/artifacts/signing.py`, and [Security and Compliance Operations](reference/security-compliance.md).

## Scope

This document describes Ed25519 key rotation for signing CAS artifacts (Phase 6).

## Trust Store Layout

```text
.polisyos/keys/
  trusted/
    signer-2026q1.pub
    signer-2026q2.pub
  revoked/
    signer-2025q4.pub
  identities.json
```

`identities.json`:

```json
{
  "sha256:<full_key_fingerprint>": "ci-prod"
}
```

## Rotation Procedure

1. Check the deployment-specific trust store, signing secret, and CAS scope; this document does not report the current key state of any deployment.
2. Generate a key and add its public part to the trust store with the supported CLI:

   ```bash
   polisyos security rotate-ed25519 \
     --output ~/.polisyos/keys/new-signer \
     --identity ci-prod
   ```

   At the source pin below, this command creates a key pair, writes the private key with mode `0600`, copies the public key to `trusted/`, and updates `identities.json`. By default, these directories are relative to the current working directory under `.polisyos/keys/`; use absolute paths for another deployment (the CLI does not expand `~` in `--trust-dir`, `--revoked-dir`, or `--identities`). The command does not switch the CI/runtime secret or prove that the selected deployment accepted the new key.
3. Transfer the new private key to a managed secret store and switch the signer in a separate controlled operation. Do not commit the key.
4. Sign only the assigned scope. `polisyos sign --all` affects every unsigned artifact in the selected CAS, not only new artifacts; specify and verify the correct CAS scope.
5. For a planned rotation, keep the old public key in `trusted/` for the agreed release/grace period.
6. After the grace period, move the old public key to `revoked/` and preserve a record of its validity period. The verifier checks revoked keys before trusted keys. The `--revoke-public-key` option on `polisyos security rotate-ed25519` copies the specified key to `revoked/` but does not remove its copy from `trusted/`; each invocation also creates and trusts a new key, so do not rerun it only to revoke a key unless a new rotation is intended.
7. Verify the required artifacts with `--strict-identity`. A full `polisyos verify --all --fail-unsigned --strict-identity` covers the entire selected CAS and fails if it contains unsigned, revoked, untrusted, or invalid records, or verification errors. After revocation, historical signatures from the old key may be revoked; define the expected scope in advance and do not treat a nonzero result from a full scan as proof that the new signer was rejected.

## Operational Notes

- Do not commit private keys to the repository.
- For local development, the private key must have mode `0600`.
- `signer_identity` in `.sig` is used as a hint; trust is determined by `key_id` in the trust store.
- In strict mode (`--strict-identity`), a mismatch between `signer_identity` and `identities.json` is an error.

Source inspection: `policy-engine/src/polisyos/core/security/rotation.py`, `policy-engine/src/polisyos/core/components/_cli_security.py`, `policy-engine/src/polisyos/core/components/_cli_crypto.py`, `policy-engine/src/polisyos/core/artifacts/signing.py`, and `policy-engine/tools/ops_runners/runtime_cli.py` at `8dd933600dd7a5a8a5b48432c6089d63b81ca641` (2026-10-14). Code inspected; CLI operations and tests were not run. These instructions describe a procedure, not evidence of a completed deployment rotation.

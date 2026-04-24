# ADR-0102: Key Rotation Lifecycle and Trust Store Policy

## Status

Accepted

## Date

2026-04-12

## Context

Artifact signing is already required for authenticity and auditability, but
signing without an explicit rotation lifecycle creates a new long-lived risk:
stale keys, ambiguous trust transitions, and unclear incident response during
compromise or signer replacement.

The project already documents trust-store layout and manual rotation steps. This
ADR promotes that guidance into a formal platform policy.

## Decision

1. CAS signing keys are managed through a trust store with explicit states:

   - trusted;
   - revoked;
   - optional identity binding metadata.
2. Key rotation is a planned lifecycle, not an emergency-only action:

   - introduce a new trusted key;
   - switch signers for new artifacts;
   - keep the previous public key trusted through the compatibility window;
   - revoke only after the grace period or incident decision.
3. Verification trust is derived from key material and trust-store state, not
   from a human-readable signer string alone.
4. Compromise or suspected compromise triggers an emergency rotation path with:

   - immediate signer replacement;
   - explicit revocation of the old public key;
   - incident documentation and artifact-scope assessment.
5. Rotation procedure, operator checks, and emergency response are documented in
   a dedicated runbook and public reference page.

## Consequences

### Positive

- Signing trust becomes explainable to operators and auditors.
- Routine rotation and emergency compromise response share one vocabulary.
- Signature verification can distinguish `valid`, `untrusted`, and `revoked`
  states consistently.

### Negative

- Rotation adds operational ceremony around CI secrets and trust-store updates.
- Historical artifact verification now depends on retaining the correct trust
  history, not only the current key.

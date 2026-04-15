# Key Rotation

Related explanation: [Key Rotation for CAS Artifact Signing](../key-rotation.md).
Related reference: [Security and Compliance Operations](../reference/security-compliance.md).

> Use this runbook for planned signer rotation, emergency signer compromise, or
> any trust-store transition affecting CAS artifact verification.

## Symptom

- a scheduled quarterly or release-bound signer/JWT rotation is due;
- signature verification starts returning `untrusted` or `revoked`;
- CI or runtime can no longer sign newly created artifacts;
- runtime starts rejecting JWTs with `jwt_untrusted_kid` or `jwt_revoked_kid`;
- suspected key compromise requires emergency replacement.

## Likely Causes

- normal planned signer or identity-provider lifecycle;
- trust-store drift between environments;
- signer private key compromise or accidental disclosure;
- stale `identities.json` binding after key replacement.
- stale JWT `kid` allowlist/revocation config during identity-provider rollout.

## Timeline Capture Expectations

- current active signer `key_id`;
- current JWT active/next/retired/revoked `kid` values;
- when the new signer was introduced;
- affected environments and CI secrets;
- whether the event is planned rotation or emergency revocation;
- any affected artifact families or time window.

## First Triage Steps

1. Confirm current trust-store state:
   - `trusted/`
   - `revoked/`
   - `identities.json`
2. Confirm current JWT rotation state:
   - identity-provider active signing `kid`;
   - `POLISYOS_JWT_ALLOWED_KIDS`;
   - `POLISYOS_JWT_REVOKED_KIDS`;
   - `.polisyos/security/jwt-trust-anchors.json` if used.
3. For planned Ed25519 rotation, verify the new public key is already trusted before
   switching the private key in CI/runtime.
4. For planned JWT rotation, allow the next `kid` before the identity provider
   signs with it, then retire the previous `kid` after the compatibility window.
5. For emergency rotation, determine the exposure window and immediately stop
   new signing with the compromised key.
6. Verify one freshly signed artifact and one historical artifact after the
   trust-store change.

## Rollback / Mitigation

- planned rotation:
  - keep the previous public key trusted through the grace window;
  - keep the previous JWT `kid` allowed through the grace window;
  - do not revoke the old key until verification coverage is confirmed.
- emergency rotation:
  - replace the active signer immediately;
  - revoke the old public key;
  - add compromised JWT `kid` values to `POLISYOS_JWT_REVOKED_KIDS`;
  - record the affected artifact time window;
  - notify security/compliance owners.

## Escalation Owner

- primary: `@platform-owners`
- supporting: security owner for emergency rotations

## Follow-up Checklist

- confirm all environments have the same trust-store update;
- capture the exact rotation or revocation timeline in UTC;
- update the key-rotation reference page if the runbook exposed missing detail.

## Blameless Postmortem

### What Went Well

- whether trust-store state made the transition self-explanatory;
- whether historical artifact verification continued working through the grace
  window.

### What Went Poorly

- whether environments drifted in trust-store contents;
- whether operator steps depended on unwritten CI knowledge.

### Action Items

| Action item | Owner | Due date | Status |
|---|---|---|---|
| Improve trust-store distribution or validation automation | `@platform-owners` | YYYY-MM-DD | open |
| Add compromise drill or documentation if emergency handling was slow | security owner | YYYY-MM-DD | open |

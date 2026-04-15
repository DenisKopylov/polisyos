# Onboarding: Security / Compliance Reviewer

Related explanation: [Security Model](../../explanation/security-model.md).
Related reference: [Ownership](../../reference/ownership.md),
[Operations Reference](../../reference/operations/index.md).

## Understand First

- artifact signing, provenance, SBOM, authz, tenancy, and TEE are operational
  control surfaces, not side topics;
- ownership and escalation still route through logical owner groups even when
  the current GitHub reviewer is a single account;
- security exceptions must be scoped, named, and time-boxed.

## Safely Ignore at First

- most feature-level UX details unrelated to security or audit evidence;
- benchmark families that do not affect release, provenance, or policy controls;
- optional LLM/data surfaces outside your current review scope.

## Commands and Docs to Use

Recommended setup:

```bash
cd policy-engine
python3 -m tools.cli workspace bootstrap --skip-playwright
python3 -m tools.cli workspace doctor --surface runtime-signing --surface runtime-oidc
uv run pytest \
  tests/core/phase0/test_cli_signing.py \
  tests/core/phase0/test_store_signing.py \
  tests/core/security/test_sbom.py
```

Primary docs:

- [Security Model](../../explanation/security-model.md)
- [Key Rotation](../../key-rotation.md)
- [Artifact Signing or SBOM Failure](../../runbooks/artifact-signing-sbom-failure.md)
- [Retention and Recovery Policy](../../reference/operations/retention-and-recovery.md)

## First Productive Task

Review one operational security path from evidence to enforcement:

- confirm how keys, trust store, and signer identity are expected to work;
- verify how SBOM gate decisions are made and surfaced;
- identify one missing owner, alert, restore step, or exception-expiry rule and
  propose the fix in docs or policy.

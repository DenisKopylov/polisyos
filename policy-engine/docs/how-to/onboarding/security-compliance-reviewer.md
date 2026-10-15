# Onboarding: Security / Compliance Reviewer

Related explanation: [Security Model](../../explanation/security-model.md).
Related reference: [Security and Compliance Operations](../../reference/security-compliance.md),
[Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md).

## Goal

Learn to assemble a review packet from current documentation, tests, workflows,
and retained evidence rather than verbal explanations.

## Inputs

- access to the code and documentation;
- an understanding of the current review scope: authz, signing, SBOM, tenancy,
  replay, release evidence, or acceptance;

- readiness to rely on validation anchors from tests/workflows.

## Output

After this onboarding, you should be able to:

- assemble a verifiable evidence map for one review topic;
- connect a control claim to code, documentation, and a validation anchor;
- quickly identify a missing owner, evidence, or rollback story.

## Canonical Commands

```bash
cd policy-engine
uv run polisyos-tools workspace doctor --skip-playwright --skip-lockfile-checks --skip-contract-checks \
  --surface runtime-signing --surface runtime-oidc
uv run pytest -q \
  tests/unit/core/phase0/test_cli_signing.py \
  tests/unit/core/phase0/test_store_signing.py \
  tests/unit/core/security/test_sbom.py \
  tests/unit/core/security/test_tenant_context.py \
  tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/property/runtime/http/test_access_invariants_properties.py
```

The `doctor` flags here skip Playwright, lockfile, and generated-contract checks,
but not the baseline checks for Python `3.14.x`, Node `22.x`, and `uv 0.9.21`.
`runtime-signing` and `runtime-oidc` in this command check only that environment
values are non-empty; they do not verify signing, keys, or actual OIDC
authentication. See [Installation](../install.md) for the exact boundaries of
`doctor`.

## Start Here By Task

| Task                                            | Primary doc                                                                                                                                                          |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Operational security contract                   | [Security and Compliance Operations](../../reference/security-compliance.md)                                                                                         |
| Where to find proof/evidence for a control area | [Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md) and `docs/fedramp/gap-analysis.md`                                              |
| Rotation / incident response                    | [Key Rotation](../../runbooks/key-rotation.md), [Artifact Signing or SBOM Failure](../../runbooks/artifact-signing-sbom-failure.md)                                  |
| Retention, replay, acceptance evidence          | [Retention and Recovery](../../reference/operations/retention-and-recovery.md), [Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md) |

## First Productive Slice

Choose one control area:

- JWT/OIDC and tenant enforcement;
- artifact signing and trust anchors;
- SBOM and supply-chain evidence;
- replay/retention and audit export.

For that area, collect four anchors:

1. reference doc;
2. code surface;
3. validation test/workflow;
4. runbook or retained evidence.

## Rollback / Handoff

- if a test does not support the control claim, do not replace the evidence with
  a prose-only assertion; record the gap;

- if the review moves into deployment plumbing, hand the operational part to
  the
  [Platform / Ops Engineer](platform-ops-engineer.md);

- if the issue is purely API/DTO-level, coordinate with the backend owner.

## Troubleshooting

- security documentation seems too broad: start with the evidence map rather
  than reading the entire reference page at once;

- a local review does not require the full browser stack, so the `skip-playwright`
  path is often appropriate;

- if workflow evidence is absent from the repository, record a missing control
  anchor instead of assuming it exists somewhere.

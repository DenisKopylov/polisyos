# Onboarding: Security / Compliance Reviewer

Related explanation: [Security Model](../../explanation/security-model.md).
Related reference: [Security and Compliance Operations](../../reference/security-compliance.md),
[Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md).

## Goal

Научиться собирать review packet из текущих docs, tests, workflows и retained
evidence, а не из устных объяснений.

## Inputs

- доступ к коду и docs;
- понимание текущего review scope: authz, signing, SBOM, tenancy, replay,
  release evidence или acceptance;

- готовность опираться на validation anchors из tests/workflows.

## Output

После этого onboarding вы должны уметь:

- собрать проверяемый evidence map для одной review темы;
- связать control claim с кодом, docs и validation anchor;
- быстро понять, где не хватает owner, evidence или rollback story.

## Canonical Commands

```bash
cd policy-engine
python3 -m tools.cli workspace doctor --surface runtime-signing --surface runtime-oidc
uv run pytest -q \
  tests/core/phase0/test_cli_signing.py \
  tests/core/phase0/test_store_signing.py \
  tests/core/security/test_sbom.py \
  tests/core/security/test_tenant_context.py \
  tests/runtime/http/test_runtime_api_authz.py \
  tests/runtime/http/test_access_invariants_properties.py
```

## Start Here By Task

| Task                                      | Primary doc                                                                                                                                                          |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Операционный security contract            | [Security and Compliance Operations](../../reference/security-compliance.md)                                                                                         |
| Где искать proof/evidence по control area | [Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md) and `docs/fedramp/gap-analysis.md`                                              |
| Rotation / incident response              | [Key Rotation](../../runbooks/key-rotation.md), [Artifact Signing or SBOM Failure](../../runbooks/artifact-signing-sbom-failure.md)                                  |
| Retention, replay, acceptance evidence    | [Retention and Recovery](../../reference/operations/retention-and-recovery.md), [Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md) |

## First Productive Slice

Выберите один control area:

- JWT/OIDC and tenant enforcement;
- artifact signing and trust anchors;
- SBOM and supply-chain evidence;
- replay/retention and audit export.

Для него соберите четыре anchors:

1. reference doc;
2. code surface;
3. validation test/workflow;
4. runbook or retained evidence.

## Rollback / Handoff

- если control claim не подтверждается тестом, не заменяйте это prose-only
  утверждением: зафиксируйте gap;

- если review уходит в deployment plumbing, передайте operational часть в
  [Platform / Ops Engineer](platform-ops-engineer.md);

- если проблема purely API/DTO-level, синхронизируйтесь с backend owner.

## Troubleshooting

- security docs кажутся слишком широкими: начните с evidence map, а не со всего
  reference page сразу;

- локальный review не требует полного browser stack, поэтому `skip-playwright`
  path часто нормален;

- если workflow evidence отсутствует в repo, фиксируйте это как missing control
  anchor, а не как "наверное где-то есть".

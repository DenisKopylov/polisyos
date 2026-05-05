# Onboarding: Platform / Ops Engineer

Related reference: [Operations](../../reference/operations/index.md),
[Security and Compliance](../../reference/security-compliance.md),
[Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md).

## Goal

Быстро войти в operator surface: runtime deployment, control plane,
observability, release gates и replay/restore workflows.

## Inputs

- установлен runtime profile;
- доступ к Docker/devcontainer или эквивалентной локальной машине;
- понимание, какие optional surfaces реально нужны: signing, OIDC, Postgres,
  browser checks.

## Output

После этого onboarding вы должны уметь:

- проверить host и optional env surfaces через `doctor`;
- понимать, где искать deploy/release/recovery instructions;
- провести маленький operational drill end to end.

## Canonical Commands

```bash
cd policy-engine
python3 -m tools.cli workspace doctor --list-surfaces
python3 -m tools.cli workspace doctor --surface runtime-research-postgres --surface runtime-signing
python3 -m tools.cli workspace verify
python3 -m tools.cli workspace ci-parity --skip-browser
```

Локальный observability stack:

```bash
cd ops
docker compose -f ops/docker/observability.compose.yml up
```

## Start Here By Task

| Task                                | Primary doc                                                       |
| ----------------------------------- | ----------------------------------------------------------------- |
| Runtime deploy and env surface      | [Deploy Runtime](../deploy-runtime.md)                            |
| Control-plane launch/poll/ops flow  | [Use Control Plane](../use-control-plane.md)                      |
| CI/CD and required local parity     | [Operate the CI/CD Platform](../operate-ci-cd-platform.md)        |
| Versioning and rollout expectations | [Release Policy](../release-policy.md)                            |
| Replay, restore, rollback drills    | [Replay or Restore Workflow](../../runbooks/replay-or-restore.md) |

## First Productive Slice

Сделайте один реальный drill:

1. поднимите observability stack;
2. проверьте одну optional surface через `doctor --surface ...`;
3. пройдите один recovery path из `Replay or Restore Workflow`;
4. зафиксируйте missing owner, missing signal или missing doc step.

## Rollback / Handoff

- если проблема ушла в code-level route/DTO drift, верните change владельцу
  backend/frontend lane;

- не выполняйте destructive cleanup поверх retained artifacts без опоры на
  runbook;

- если release/control issue стал security/compliance issue, переведите review в
  [Security / Compliance Reviewer](security-compliance-reviewer.md).

## Troubleshooting

- `doctor` падает только на optional surface: фиксируйте это как environment gap,
  а не как общий bootstrap failure;

- `ci-parity` слишком тяжелый для локального цикла: используйте `verify`, а
  parity оставьте на pre-PR closeout;

- recovery instructions кажутся неполными: обновляйте runbook сразу, пока
  реальный контекст еще свежий.

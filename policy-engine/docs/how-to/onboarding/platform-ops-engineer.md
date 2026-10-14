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
uv run polisyos-tools workspace doctor --list-surfaces
uv run polisyos-tools workspace doctor --surface runtime-research-postgres --surface runtime-signing
uv run polisyos-tools workspace verify
uv run polisyos-tools workspace ci-parity --skip-browser
```

`doctor --surface runtime-research-postgres` and `runtime-signing` only check that
their required environment values are non-empty. They do not connect to Postgres,
check a signing-key file or parse a key, or perform signing and verification; a
pass confirms presence only. Verify connectivity and signing behavior with the
task-specific check before relying on either surface.

Локальный observability stack:

```bash
cd policy-engine
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

Проведите небольшой operator rehearsal по документированным шагам и фиксируйте границы между
ними. Сам по себе такой drill не подтверждает интегрированный E2E policy flow:

1. поднимите observability stack;
2. проверьте наличие env values для одной optional surface через `doctor --surface ...`;
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

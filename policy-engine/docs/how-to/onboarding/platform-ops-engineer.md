# Onboarding: Platform / Ops Engineer

Related reference: [Operations](../../reference/operations/index.md),
[Security and Compliance](../../reference/security-compliance.md),
[Platform Acceptance Audit](../../reference/operations/platform-acceptance-audit.md).

## Goal

Quickly become productive with the operator surface: runtime deployment, the
control plane, observability, release gates, and replay/restore workflows.

## Inputs

- an installed runtime profile;
- access to Docker/devcontainer or an equivalent local machine;
- an understanding of which optional surfaces are actually needed: signing,
  OIDC, Postgres, or browser checks.

## Output

After this onboarding, you should be able to:

- check the host and optional environment surfaces with `doctor`;
- find deployment, release, and recovery instructions;
- run a small operational drill from start to finish.

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

Local observability stack:

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

Run a small operator rehearsal using the documented steps and record the
boundaries between them. The drill alone does not establish an integrated
end-to-end policy flow:

1. Start the observability stack.
2. Check that environment values exist for one optional surface with
   `doctor --surface ...`.
3. Follow one recovery path from `Replay or Restore Workflow`.
4. Record a missing owner, signal, or documentation step.

## Rollback / Handoff

- if the problem is a code-level route/DTO drift, hand the change back to the
  backend/frontend lane;

- do not perform destructive cleanup of retained artifacts without following a
  runbook;

- if a release/control issue becomes a security/compliance issue, move the review
  to the
  [Security / Compliance Reviewer](security-compliance-reviewer.md).

## Troubleshooting

- `doctor` fails only on an optional surface: record an environment gap rather
  than a general bootstrap failure;

- `ci-parity` is too heavy for the local cycle: use `verify` and reserve parity
  for pre-PR closeout;

- recovery instructions seem incomplete: update the runbook while the actual
  context is still fresh.

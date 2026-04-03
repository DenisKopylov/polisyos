# Onboarding Tracks

Related guides: [Installation](../install.md), [Deploy Runtime](../deploy-runtime.md),
[Use Control Plane](../use-control-plane.md), [Manage Schemas](../manage-schemas.md).

> Role-based onboarding reduces the amount of system a newcomer must understand
> before becoming useful.

## Tracks

| Track | First focus | Primary command surface |
|---|---|---|
| [Domain / Policy Reader](domain-policy-reader.md) | Trinity, evidence, governance, decision artifacts | `./scripts/bootstrap --skip-frontend --skip-playwright` |
| [Backend Engineer](backend-engineer.md) | Python runtime, contracts, Scientist/Fabric/Foundry service paths | `./scripts/bootstrap`, `./scripts/verify --backend-only` |
| [Frontend Engineer](frontend-engineer.md) | runtime dashboard, route structure, contracts, UX telemetry | `./scripts/bootstrap`, `./scripts/verify --frontend-only` |
| [Platform / Ops Engineer](platform-ops-engineer.md) | bootstrap/doctor/verify, runtime deploy, observability, release surfaces | `./scripts/bootstrap`, `./scripts/doctor`, `./scripts/verify` |
| [Security / Compliance Reviewer](security-compliance-reviewer.md) | signing, SBOM, authz, TEE, ownership, audit evidence | `./scripts/bootstrap --skip-playwright`, focused security surfaces |

## Shared Principles

- Start from [Contributor Start Here](../../reference/contributor-start-here.md)
  when you are unsure whether the task is role-local or cross-platform.
- Start with one role-shaped slice of the system, not with the whole tree.
- Use the canonical command surface before inventing ad hoc scripts.
- Prefer docs and runbooks over chat archaeology.
- If a first task needs permissions, data, or keys you do not have, record the
  missing surface explicitly instead of working around it silently.

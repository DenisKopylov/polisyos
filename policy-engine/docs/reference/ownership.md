# Ownership

Owner: `@platform-owners`
Source of truth: `docs/DOCUMENTATION_SOTA_PLAN.md`, `architecture/*.toml`,
`src/polisyos/**`, `frontend/**`, `tools/**`, `ops/**`, `docs/**`, and the
logical owner-group policy documented on this page

This page defines human ownership for the PolicyOS canonical product root under
`policy-engine/`.

Per [ADR-0096](../adr/0096-canonical-product-root-and-workspace-boundary.md),
`policy-engine/` is the product root and the repository root is repo control
plane. The active GitHub enforcement file is the repository-root
`.github/CODEOWNERS`; this page remains the logical owner-group reference for
reviews and escalation.

## Ownership Model

- Logical owner groups are the stable architecture vocabulary for review,
  escalation, and future GitHub team provisioning.
- The current GitHub-enforced reviewer is `@DenisKopylov` for every owned path,
  because the repository is currently hosted as a personal repository rather
  than an organization with provisioned team slugs.
- `@platform-owners` is the fallback owner and escalation path for unowned,
  ambiguous, or time-sensitive changes. Today that fallback resolves to
  `@DenisKopylov`.

## Subsystem Owners

| Area | Canonical paths | Logical owner group | Current GitHub reviewer | Fallback owner |
|---|---|---|---|---|
| Core | `src/polisyos/core/**` | `@core-owners` | `@DenisKopylov` | `@platform-owners` |
| IR | `src/polisyos/ir/**` | `@ir-owners` | `@DenisKopylov` | `@platform-owners` |
| Fabric | `src/polisyos/fabric/**` | `@fabric-owners` | `@DenisKopylov` | `@platform-owners` |
| Foundry | `src/polisyos/foundry/**` | `@foundry-owners` | `@DenisKopylov` | `@platform-owners` |
| Scientist | `src/polisyos/scientist/**` | `@scientist-owners` | `@DenisKopylov` | `@platform-owners` |
| Lex | `src/polisyos/lex/**` | `@lex-owners` | `@DenisKopylov` | `@platform-owners` |
| Runtime | `src/polisyos/runtime/**` | `@runtime-owners` | `@DenisKopylov` | `@platform-owners` |
| Common | `src/polisyos/common/**` | `@core-owners` | `@DenisKopylov` | `@platform-owners` |
| Data Forge | `src/polisyos/data_forge/**`, `schemas/artifacts/**`, `schemas/manifests/**` | `@data-forge-owners` | `@DenisKopylov` | `@platform-owners` |
| Architecture contracts | `architecture/**`, `schemas/topology/**` | `@architecture-owners` | `@DenisKopylov` | `@platform-owners` |
| Schemas | `schemas/**` | `@architecture-owners` | `@DenisKopylov` | `@platform-owners` |
| Frontend | `frontend/**` | `@frontend-owners` | `@DenisKopylov` | `@platform-owners` |
| Tools | `tools/**` | `@tools-owners` | `@DenisKopylov` | `@platform-owners` |
| Docs | `docs/**` | `@docs-owners` | `@DenisKopylov` | `@platform-owners` |
| ADRs and active plans | `docs/adr/**`, `docs/plans/**` | `@architecture-owners` | `@DenisKopylov` | `@platform-owners` |
| Ops | `ops/**` | `@platform-owners` | `@DenisKopylov` | `@platform-owners` |
| Observability and security ops | `ops/observability/**`, `ops/security/**` | `@platform-owners` | `@DenisKopylov` | `@runtime-owners` |

## Documentation SOTA Lane Owners

This matrix is the Phase D0 owner map for the documentation refresh described
by `docs/DOCUMENTATION_SOTA_PLAN.md`. The logical owner is responsible for
technical correctness; the backup owner is responsible for unblocking review,
conflict resolution, and escalation when the primary owner is unavailable.

| Lane | Documentation surfaces | Primary owner | Backup owner |
|---|---|---|---|
| L0 Program / IA | `docs/reference/documentation-inventory.md`, `mkdocs.yml`, `docs/index.md`, `docs/reference/index.md`, archive policy | `@docs-owners` | `@platform-owners` |
| L1 Core/Common/Runtime | `README.md`, `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `docs/reference/api/**`, `docs/reference/operations/**`, runtime runbooks | `@runtime-owners` | `@core-owners` |
| L2 Fabric | `src/polisyos/fabric/README.md`, `docs/reference/fabric/**`, `docs/connectors/CONTRIBUTING.md`, Fabric how-to and runbook surfaces | `@fabric-owners` | `@platform-owners` |
| L3 Foundry | `src/polisyos/foundry/README.md`, `docs/reference/foundry/**`, causal-engine explanation, benchmark and reproducibility docs | `@foundry-owners` | `@platform-owners` |
| L4 IR | `src/polisyos/ir/README.md`, `docs/reference/ir/**`, `docs/reference/schemas.md`, `docs/contracts/**`, IR ADR surfaces | `@ir-owners` | `@platform-owners` |
| L5 Tools | `tools/README.md`, `docs/reference/tools.md`, CI/CD how-to, validation and contributor command maps | `@tools-owners` | `@platform-owners` |
| L6 Scientist | `src/polisyos/scientist/README.md`, `docs/reference/scientist/**`, Scientist tutorials and how-to surfaces | `@scientist-owners` | `@platform-owners` |
| L7 Frontend/API consumers | `frontend/**` docs, runtime API client docs, dashboard/API-consumer reference surfaces | `@frontend-owners` | `@runtime-owners` |
| L8 Ops/Security/Compliance | `docs/runbooks/**`, `docs/reference/security-compliance.md`, SLO, audit, FedRAMP, release-gate evidence | `@platform-owners` | `@runtime-owners` |
| L9 Automation/Gates | `docs/reference/quality-gates.md`, generated reference pages, docs QA commands, CI gate docs | `@platform-owners` | `@tools-owners` |
| L10 Data Forge | `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`, Data Forge ADRs, `schemas/artifacts/**`, Data Forge runbooks | `@data-forge-owners` | `@platform-owners` |

## Boundary-Crossing Approval

- A change contained within one owned area should be approved by that area's
  owner group.
- A change that touches two or more owned code areas should be approved by each
  affected area owner group.
- A change that modifies shared contracts, import-policy boundaries, runtime API
  behavior, or generated frontend runtime-client surfaces should also receive
  `@platform-owners` approval acting as the architecture owner role.
- When the relevant owner is unavailable or the correct owner is unclear,
  `@platform-owners` becomes the approving fallback and escalation path.

## Cross-Cutting Ownership

| Responsibility | Primary owner | Supporting owner(s) | Notes |
|---|---|---|---|
| Release engineering | `@platform-owners` | affected subsystem owners | Owns release orchestration, cut readiness, and go/no-go decisions. |
| Docs platform | `@platform-owners` | `@docs-owners` | Owns MkDocs config, docs CI, publishing, and broken-site recovery. |
| Docs content accuracy | `@docs-owners` | relevant subsystem owners | Content changes still require the subsystem owner when docs describe a contract or behavior change. |
| Incident response | `@platform-owners` | `@runtime-owners`, affected subsystem owners | `@platform-owners` leads coordination; runtime owners lead live service triage; impacted subsystem owners own remediation in their area. |

## Notes

- The logical owner groups above are intentionally stable even if GitHub team
  handles change later.
- When the repository moves under an organization with provisioned teams, the
  manual owner mapping here can be projected into a repo-tracked `CODEOWNERS`
  file without changing the ownership model itself.

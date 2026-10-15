# Ownership

Owner: `@platform-owners`
Source of truth: `architecture/control_plane_supply_chain.toml` and its
`owner_source_order`, the package and public-surface architecture manifests,
repository-root `.github/CODEOWNERS`, and the logical owner-group policy on
this page

This page defines human ownership for the PolicyOS canonical product root under
`policy-engine/`.

Per [ADR-0096](../adr/0096-canonical-product-root-and-workspace-boundary.md),
`policy-engine/` is the product root and the repository root is repo control
plane. The checked-in `.github/CODEOWNERS` records reviewer routing, while
`architecture/control_plane_supply_chain.toml` records the owner projection.
These files do not establish that GitHub has applied the routing. This page
remains the logical owner-group reference for reviews and escalation.

## Ownership Model

- Logical owner groups are the stable architecture vocabulary for review,
  escalation, and future GitHub team provisioning.

- The checked-in `.github/CODEOWNERS` routes the owned product paths to
  `@DenisKopylov`; the control-plane contract records a personal-repository
  exception for missing organization team slugs. This is tracked configuration,
  not verification of live GitHub behavior.

- `@platform-owners` is the fallback owner and escalation path for unowned,
  ambiguous, or time-sensitive changes. The control-plane owner mapping records
  `@DenisKopylov` as the current reviewer under its personal-repository
  exception.

The `Logical owner group` and `Reviewer in tracked CODEOWNERS` columns below
describe human review routing; they are distinct from an artifact or public
surface contract's `owner` field. For `polisyos.fabric`, the public-surface
contract says `team-polisyos`, while this table lists `@fabric-owners` and the
tracked CODEOWNERS path routes to `@DenisKopylov`. The control-plane mapping
records `team-polisyos` with `@platform-owners` and `team-fabric` with
`@fabric-owners`, both covering `polisyos.fabric`. These records do not establish
that the artifact owner label and the human review group are equivalent or
which group is accountable for that artifact. Preserve the labels as declared;
neither one proves team provisioning, an accepted appointment, or approval of a
change.

## Change-Triggered Documentation Review

When a canonical implementation, contract, schema, public surface, generated
reference, or owner mapping changes, review the documentation claims that depend
on that source. The relevant subsystem owner checks technical accuracy; the
docs owner checks audience, scope, and navigation. Review only affected claims
and qualify any part that the inspected source does not establish.

Keep the roles distinct: a logical owner group is the repository's
responsibility label; a checked-in `CODEOWNERS` entry is tracked reviewer
routing; an approval is evidenced by the review record for the change. Neither
the group label nor a tracked route proves that a team is provisioned, a person
accepted a current appointment, or a review occurred. The approval matrix below
states the expected route, not evidence that approval was obtained. If the
available source does not establish an owner, live routing, or approval, say so
explicitly rather than inferring one.

Keep ratified decisions and historical ownership records in their original
role and time context. Record a changed assignment in its current canonical
source and update this projection; do not silently rewrite a historical lane
as a present appointment.

## Subsystem Owners

<!-- markdownlint-disable MD060 -->

| Area                           | Canonical paths                                                              | Logical owner group    | Reviewer in tracked CODEOWNERS | Fallback owner     |
| ------------------------------ | ---------------------------------------------------------------------------- | ---------------------- | ----------------------- | ------------------ |
| Core                           | `src/polisyos/core/**`                                                       | `@core-owners`         | `@DenisKopylov`         | `@platform-owners` |
| IR                             | `src/polisyos/ir/**`                                                         | `@ir-owners`           | `@DenisKopylov`         | `@platform-owners` |
| Fabric                         | `src/polisyos/fabric/**`                                                     | `@fabric-owners`       | `@DenisKopylov`         | `@platform-owners` |
| Foundry                        | `src/polisyos/foundry/**`                                                    | `@foundry-owners`      | `@DenisKopylov`         | `@platform-owners` |
| Scientist                      | `src/polisyos/scientist/**`                                                  | `@scientist-owners`    | `@DenisKopylov`         | `@platform-owners` |
| Lex                            | `src/polisyos/lex/**`                                                        | `@lex-owners`          | `@DenisKopylov`         | `@platform-owners` |
| Runtime                        | `src/polisyos/runtime/**`                                                    | `@runtime-owners`      | `@DenisKopylov`         | `@platform-owners` |
| Common                         | `src/polisyos/common/**`                                                     | `@core-owners`         | `@DenisKopylov`         | `@platform-owners` |
| Data Forge                     | `src/polisyos/data_forge/**`, `schemas/artifacts/**`, `schemas/manifests/**` | `@data-forge-owners`   | `@DenisKopylov`         | `@platform-owners` |
| Scholar                        | `src/polisyos/scholar/**`                                                    | `@scholar-owners`      | `@DenisKopylov`         | `@platform-owners` |
| Scientist support packages     | `src/polisyos/berl/**`, `src/polisyos/calibration/**`, `src/polisyos/ddm/**` | `@scientist-owners` | `@DenisKopylov` | `@architecture-owners` |
| Foundry support packages       | `src/polisyos/foundry/agent_sim/world/**`                                  | `@foundry-owners`      | `@DenisKopylov`         | `@architecture-owners` |
| Architecture contracts         | `architecture/**`, `schemas/topology/**`                                     | `@architecture-owners` | `@DenisKopylov`         | `@platform-owners` |
| Schemas                        | `schemas/**`                                                                 | `@architecture-owners` | `@DenisKopylov`         | `@platform-owners` |
| Frontend                       | `apps/**`, `packages/**`                                                      | `@frontend-owners`     | `@DenisKopylov`         | `@platform-owners` |
| Tools                          | `tools/**`                                                                   | `@tools-owners`        | `@DenisKopylov`         | `@platform-owners` |
| Docs                           | `docs/**`                                                                    | `@docs-owners`         | `@DenisKopylov`         | `@platform-owners` |
| ADRs and active plans          | `docs/adr/**`, `docs/plans/**`                                               | `@architecture-owners` | `@DenisKopylov`         | `@platform-owners` |
| Ops                            | `ops/**`                                                                     | `@platform-owners`     | `@DenisKopylov`         | `@platform-owners` |
| Observability and security ops | `ops/observability/**`, `ops/security/**`                                    | `@platform-owners`     | `@DenisKopylov`         | `@runtime-owners`  |

<!-- markdownlint-enable MD060 -->

## Historical Documentation SOTA Lane Owners

This matrix preserves the Phase D0 assignment from the superseded
`docs/plans/active/DOCUMENTATION_SOTA_PLAN.md`; it is historical and does not
assign current documentation work. The task-specific lane commission is
recorded in `docs/plans/active/DOCUMENTATION_MAINTENANCE_20261014.md`.
Within the historical matrix, the logical owner was responsible for technical
correctness and the backup owner for unblocking review, conflict resolution,
and escalation when the primary owner was unavailable.

| Lane                       | Documentation surfaces                                                                                                                                                                   | Primary owner        | Backup owner       |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- | ------------------ |
| L0 Program / IA            | `docs/reference/documentation-inventory.md`, `mkdocs.yml`, `docs/index.md`, `docs/reference/index.md`, archive policy                                                                    | `@docs-owners`       | `@platform-owners` |
| L1 Core/Common/Runtime     | `README.md`, `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `docs/reference/api/**`, `docs/reference/operations/**`, runtime runbooks | `@runtime-owners`    | `@core-owners`     |
| L2 Fabric                  | `src/polisyos/fabric/README.md`, `docs/reference/fabric/**`, `docs/connectors/CONTRIBUTING.md`, Fabric how-to and runbook surfaces                                                       | `@fabric-owners`     | `@platform-owners` |
| L3 Foundry                 | `src/polisyos/foundry/README.md`, `docs/reference/foundry/**`, causal-engine explanation, benchmark and reproducibility docs                                                             | `@foundry-owners`    | `@platform-owners` |
| L4 IR                      | `src/polisyos/ir/README.md`, `docs/reference/ir/**`, `docs/reference/schemas.md`, `docs/contracts/**`, IR ADR surfaces                                                                   | `@ir-owners`         | `@platform-owners` |
| L5 Tools                   | `tools/README.md`, `docs/reference/tools.md`, CI/CD how-to, validation and contributor command maps                                                                                      | `@tools-owners`      | `@platform-owners` |
| L6 Scientist               | `src/polisyos/scientist/README.md`, `docs/reference/scientist/**`, Scientist tutorials and how-to surfaces                                                                               | `@scientist-owners`  | `@platform-owners` |
| L7 Frontend/API consumers  | `apps/**` docs, `packages/runtime-api-client/**` docs, dashboard/API-consumer reference surfaces                                                                                         | `@frontend-owners`   | `@runtime-owners`  |
| L8 Ops/Security/Compliance | `docs/runbooks/**`, `docs/reference/security-compliance.md`, SLO, audit, FedRAMP, release-gate evidence                                                                                  | `@platform-owners`   | `@runtime-owners`  |
| L9 Automation/Gates        | `docs/reference/quality-gates.md`, generated reference pages, docs QA commands, CI gate docs                                                                                             | `@platform-owners`   | `@tools-owners`    |
| L10 Data Forge             | `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`, Data Forge ADRs, `schemas/artifacts/**`, Data Forge runbooks                                                                       | `@data-forge-owners` | `@platform-owners` |

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

| Responsibility        | Primary owner      | Supporting owner(s)                          | Notes                                                                                                                                    |
| --------------------- | ------------------ | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Release engineering   | `@platform-owners` | affected subsystem owners                    | Owns release orchestration, cut readiness, and go/no-go decisions.                                                                       |
| Docs platform         | `@platform-owners` | `@docs-owners`                               | Owns MkDocs config, docs CI, publishing, and broken-site recovery.                                                                       |
| Docs content accuracy | `@docs-owners`     | relevant subsystem owners                    | Content changes still require the subsystem owner when docs describe a contract or behavior change.                                      |
| Incident response     | `@platform-owners` | `@runtime-owners`, affected subsystem owners | `@platform-owners` leads coordination; runtime owners lead live service triage; impacted subsystem owners own remediation in their area. |

## Notes

- The logical owner groups above are intentionally stable even if GitHub team
  handles change later.

- When the repository moves under an organization with provisioned teams, the
  manual owner mapping here can be projected into a repo-tracked `CODEOWNERS`
  file without changing the ownership model itself.

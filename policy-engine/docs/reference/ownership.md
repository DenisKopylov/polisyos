# Ownership

This page defines human ownership for the PolicyOS canonical product root under
`policy-engine/`.

Per [ADR-0096](../adr/0096-canonical-product-root-and-workspace-boundary.md),
`policy-engine/` is the product root and the repository root is repo control
plane. GitHub evaluates `CODEOWNERS` from the repository root, so the matching
rules live in `.github/CODEOWNERS` and use `/policy-engine/...` prefixes.

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
| Frontend | `frontend/**` | `@frontend-owners` | `@DenisKopylov` | `@platform-owners` |
| Docs | `docs/**` | `@docs-owners` | `@DenisKopylov` | `@platform-owners` |
| Ops | `ops/**` | `@platform-owners` | `@DenisKopylov` | `@platform-owners` |

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
- When the repository moves under an organization with provisioned teams,
  `.github/CODEOWNERS` should switch from `@DenisKopylov` to the logical team
  handles documented here without changing the ownership model itself.

# ADR-0096: Canonical Product Root and Workspace Boundary

## Status

Accepted

## Date

2026-04-03

## Context

Repository root and `policy-engine/` both accumulated product-facing signals:

- root `README.md` presented itself as product documentation;
- packaging reality lived under `policy-engine/`, while a stray root-level `uv.lock`
  suggested an alternative root;

- contributor setup knowledge was implicit and split between CI, docs, and local habits;
- newcomers could not tell quickly whether root-level files were there by platform
  constraint or by architectural drift.

Phase 0 requires one unambiguous source of truth before any deeper infrastructure
work continues.

## Decision

1. `policy-engine/` is the canonical product root for PolisyOS.
2. Repository root is a workspace gateway plus repo control plane. It is not the
   canonical source of product metadata, packaging, or release logic.
3. The following may live at repository root:

   - research materials;
   - local datasets excluded from product automation;
   - design artifacts;
   - workspace-only helper files;
   - repo-native GitHub governance files.
4. The following must live under `policy-engine/`:

   - product code;
   - product docs;
   - packaging and lockfiles;
   - release logic.
5. Root-level files that exist only because GitHub or platform tooling requires
   them are treated as repo control plane, not as product topology.
6. Contributor bootstrap commands (`bootstrap`, `doctor`, `verify`) are defined
   inside `policy-engine/` so the supported local path starts at the canonical
   product root.
7. Contradictory root-level packaging signals are removed; specifically, the
   empty root `uv.lock` is deleted.

## Consequences

### Positive

- A newcomer can determine in under 30 seconds that the product starts in
  `policy-engine/`.

- Root-level files can be explained as either repo control plane or allowed
  workspace material, instead of ambiguous product drift.

- Packaging, docs, release logic, and contributor setup now point to the same
  place.

### Negative

- Some existing habits that treated repository root as a product root must change.
- Workspace-only scripts and datasets remain in the same repository, so the root
  still needs policy discipline to avoid gradual drift.

- Tooling and docs must stay synchronized with this boundary, or ambiguity will
  reappear.

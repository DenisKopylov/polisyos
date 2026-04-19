# ADR-0111: Workspace Root Boundary as a SOTA Contract

## Status
Proposed

## Date
2026-04-18

## Context

ADR-0096 made `policy-engine/` the canonical product root and repository root a
workspace gateway. The current cleanup work needs that decision to become a
machine-checkable contract with a root allowlist, loose-file policy, topology
registry, and CI gate.

## Decision

Keep the fortified split-root model:

1. Repository root is a gateway/control plane.
2. `policy-engine/` is the product root.
3. Root loose files are restricted to explicit sentinels in
   `architecture/topology.toml`.
4. Product source, docs, release logic, tooling, schemas, and tests live under
   `policy-engine/`.
5. Local datasets and scratch state live under ignored roots such as root
   `data/`, `.polisyos/`, and `.tmp/`.

## Consequences

- Root drift becomes visible in CI instead of code review memory.
- Existing root scripts and local reports must move or become wrappers.
- ADR-0096 remains the foundation; this ADR adds enforcement and SOTA scope.

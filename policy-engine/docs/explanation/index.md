# Explanation

These pages explain why the current architecture is shaped the way it is and
which contracts, ADRs, tests, and runbooks back the published claims.

## Reading Order

| Page                                              | Use it for                                                              | Primary anchors                                                     |
| ------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------- |
| [Architecture](architecture.md)                   | Whole-system boundaries, containers, and artifact lifecycles            | operations diagrams, generated artifacts, platform acceptance audit |
| [Trinity](trinity.md)                             | ProblemFrame / PolicySpec / ModelSpec split and bundle lifecycle        | `TRINITY.md`, merge semantics, Foundry compile/execute              |
| [IR Design](ir-design.md)                         | Why IR is the compatibility layer and how schema evolution works        | ADR-0104..0109, IR schema catalog, transport contracts              |
| [Security Model](security-model.md)               | Runtime trust boundaries, authn/authz, tenant isolation, signing, audit | auth/tenant reference, security compliance, runtime runbooks        |
| [Data Fabric](data-fabric.md)                     | Connector ingestion, lineage, schema governance, world/data plane       | Fabric reference set, Fabric runbooks                               |
| [Causal Engine](causal-engine.md)                 | Foundry compile/execute and Scientist causal orchestration              | Foundry and Scientist references, method tests, benchmarks          |
| [Lex Pipeline](lex-pipeline.md)                   | Legal corpus to NormPack and intervention flows                         | Lex reference and Lex contracts                                     |
| [Governance Model](governance-model.md)           | Workflow gating, governance artifacts, human review, accountability     | Scientist workflows, governance passes, accountability artifacts    |
| [Observation Contracts](observation-contracts.md) | Data-to-method contracts, trust tiers, readiness bundles                | IR observation reference, Fabric quality, Scientist causal validity |
| [Freeze Policy](freeze-policy.md)                 | Import gates, ratchets, and CI/docs quality-gate flow                   | ADR-0004, ADR-0053, quality gates, ratchet policy                   |

## Shared Evidence Policy

- Pages in this section link back to the ADRs, contracts, and reference pages
  that define the default behavior.

- Strong claims about default behavior should also point at tests, benchmarks,
  generated artifacts, acceptance audits, or runbook evidence.

- Capability flags and non-default rollout paths stay linked to the relevant
  roadmap or acceptance page instead of being described as current default
  behavior.

See also:

- [ADR index](../adr/index.md)
- [Reference index](../reference/index.md)
- [TRINITY contract](../contracts/TRINITY.md)

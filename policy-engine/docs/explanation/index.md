# Explanation

> **Owner:** `team-architecture`
>
> **Source of truth:** the linked decision records, contracts, and references for each page.
>
> **Evidence caveat:** source and test references identify evidence locations, not fresh execution
> receipts. The architecture page states its inspected source snapshot and verification scope.

These pages explain why the current architecture is shaped the way it is and
which contracts, ADRs, tests, and runbooks back the published claims.

## Reading Order

| Page                                              | Use it for                                                         | Primary anchors                          |
| ------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------- |
| [Architecture](architecture.md)                   | Ratified boundary, target, package contracts, and selected bridges | operations, artifacts, acceptance audit  |
| [End-to-End Data Flow](end-to-end-data-flow.md)   | One run-bound predictive diagnostic from input to readback         | producer, CAS, SQL association, S10, API |
| [Trinity](trinity.md)                             | Trinity bundle and merge lifecycle                                 | TRINITY, Foundry compile/execute         |
| [IR Design](ir-design.md)                         | IR compatibility and schema evolution                              | IR catalog, transport contracts          |
| [Security Model](security-model.md)               | Runtime auth, tenants, signing, and audit                          | security references and runbooks         |
| [Data Fabric](data-fabric.md)                     | Connectors, lineage, schemas, and data/world plane                 | Fabric references and runbooks           |
| [Causal Engine](causal-engine.md)                 | Foundry compile/execute and Scientist orchestration                | method tests, benchmarks                 |
| [Lex Pipeline](lex-pipeline.md)                   | Legal corpus to NormPack and intervention flows                    | Lex reference and contracts              |
| [Governance Model](governance-model.md)           | Workflow gates, artifacts, review, and accountability              | Scientist governance references          |
| [Observation Contracts](observation-contracts.md) | Data-to-method contracts, trust tiers, and readiness               | IR, Fabric, Scientist references         |
| [Freeze Policy](freeze-policy.md)                 | Import gates, ratchets, and docs quality gates                     | ADRs 0004/0053 and quality gates         |

## Shared Evidence Policy

- Pages in this section link back to the ADRs, contracts, and reference pages
  that define the default behavior.

- Strong claims about default behavior should also point at tests, benchmarks,
  generated artifacts, acceptance audits, or runbook evidence.

- Capability flags and non-default rollout paths stay linked to the relevant
  roadmap or acceptance page instead of being described as current default
  behavior.

- A source path or test name is not a test-run receipt. Current-code claims
  state the inspected snapshot and whether verification was run for that page.

See also:

- [ADR index](../adr/index.md)
- [Reference index](../reference/index.md)
- [TRINITY contract](../contracts/TRINITY.md)

# Governance IR
Related explanation: [Governance Model](../../explanation/governance-model.md).

> Policy authoring contracts, governance alias registries, and gate payloads used before execution.

Governance in the IR layer splits into two concerns:

- policy authoring, where `PolicySpec` declares interventions, parameters, and schedules;
- validation metadata, where observation-family governance mappings and gate payloads tell Scientist what must be checked before execution can proceed.

## Source Modules

| Module | Focus | Key exports |
|--------|-------|-------------|
| `polisyos.ir.governance.policy_spec` | Policy authoring and temporal interventions | `PolicySpec`, `PolicyInterventionSpec`, `MechanismBinding`, `ParameterSpec`, `TemporalInterventionSequence` |
| `polisyos.ir.observation.governance` | Observation-family governance aliases and pass routing | `GovernancePassAlias`, `GovernancePassAliasRegistry`, `GovernancePassAliasStatus`, `ObservationFamilyPolicy`, `GovernancePassMappingRegistry` |
| `polisyos.ir.governance.gate` | Human or automated approval payloads | `GateContext`, `GateRequest`, `GateDecision`, `GateEvent`, `GateVerdict` |

## Policy Specification

::: polisyos.ir.governance.policy_spec

## Observation Governance

The observation layer introduces a second governance surface that is orthogonal
to policy authoring: it resolves which governance passes apply to each evidence
family and how those canonical pass ids map to runtime pass implementations.

::: polisyos.ir.observation.governance

## Gate Event Contracts

::: polisyos.ir.governance.gate

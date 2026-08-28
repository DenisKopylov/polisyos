# Lex Interventions

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Owner: `@lex-owners`
Source of truth: `src/polisyos/lex/interventions.py`, `src/polisyos/lex/intervention_artifacts.py`, and `src/polisyos/ir/governance/policy_spec.py`

Lex interventions translate legal provisions into executable intervention
contracts, parameter knobs, and temporal intervention sequences. The neutral
`CompiledLexIntervention` contract lives in IR; Scientist nodes adapt policy
bundles into search and materialize temporal sequences for Foundry causal methods.

## Core Concepts

| Concept                                | Role                                                             |
| -------------------------------------- | ---------------------------------------------------------------- |
| `LexProvisionDirective`                | One provision-level intervention request                         |
| `LexInterventionCompiler`              | Compiles directives into `InterventionSpec` plus `ParameterSpec` |
| `LexProvisionMappingRegistry`          | Resolves provision mappings, knobs, and program crosswalks       |
| `TemporalInterventionSequencer`        | Builds ordered intervention sequences for DTR workflows          |
| `HierarchicalPolicySearchPlan`         | Search-plan handoff into Scientist hierarchical policy search    |

Scientist owns `HierarchicalPolicySearchAdapter` in
`scientist.nodes.builtins.planning.run_hierarchical_policy_search` and
`TemporalInterventionSequenceCompiler` in
`scientist.nodes.builtins.causal.run_causal_contract_execution`. These are node
implementation details, not module `__all__` or Lex package exports. Dynamic
treatment materialization formerly exposed as
`TemporalInterventionSequencer.to_dynamic_treatment` is part of that Scientist
causal execution path as well.

## Reference

::: polisyos.lex.intervention_artifacts

::: polisyos.lex.interventions

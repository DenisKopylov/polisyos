# Lex Interventions
Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Lex interventions translate legal provisions into executable intervention
contracts, parameter knobs, and temporal intervention sequences that can be
handed to Scientist policy search and Foundry causal/runtime execution.

## Core Concepts

| Concept | Role |
|---------|------|
| `LexProvisionDirective` | One provision-level intervention request |
| `LexInterventionCompiler` | Compiles directives into `InterventionSpec` plus `ParameterSpec` |
| `LexProvisionMappingRegistry` | Resolves provision mappings, knobs, and program crosswalks |
| `TemporalInterventionSequencer` | Builds ordered intervention sequences for DTR workflows |
| `TemporalInterventionSequenceCompiler` | Runs DTR compilation and persistence for sequence tasks |
| `HierarchicalPolicySearchPlan` | Search-plan handoff into Scientist hierarchical policy search |

## Reference

::: polisyos.lex.intervention_artifacts

::: polisyos.lex.interventions

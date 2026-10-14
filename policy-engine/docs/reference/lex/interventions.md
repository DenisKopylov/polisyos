# Lex Interventions

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Freshness: 2026-10-14
Owner: `@lex-owners` for provision-to-policy mapping and typed runtime inputs; Scientist and Foundry own the downstream planning and causal-method execution bridges.
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Source of truth: `src/polisyos/lex/interventions.py`, `src/polisyos/lex/intervention_artifacts.py`, `src/polisyos/ir/governance/policy_spec.py`, and the named test below.
Evidence level: source and named test behavior were inspected at the source pin; tests were inspected, not run for this documentation refresh. The fixture covers mapping and validation behavior, not legal-source verification or a live policy/causal end-to-end run.

Lex maps a supplied provision reference and mapping artifact into typed policy-action
contracts, parameter knobs, and temporal sequence inputs. These are caller-supplied
policy-design inputs: compiling them does not verify that a provision is official,
currently effective, or applicable to a policy claim. The neutral
`CompiledLexIntervention` contract lives in IR. Scientist owns the search and causal
execution bridges that consume these contracts.

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
causal execution path as well. In IR, `InterventionSpec` declares a policy action,
not a causal-query `do()` intervention. The temporal input checks date-string shape
and sequence ordering; they do not validate an issuer's legal date or establish
legal authority. Provision and source references are carried as typed strings and
are not resolved here to source bytes or issuer credentials.

## Code-inspected evidence

- Compiler, registry, and IR boundary: `src/polisyos/lex/interventions.py`, `src/polisyos/lex/intervention_artifacts.py`, and `src/polisyos/ir/governance/policy_spec.py::InterventionSpec`.
- Scientist consumers: `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py` and `src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py::TemporalInterventionSequenceCompiler`.
- Mapping and validation fixtures: `tests/unit/lex/test_interventions.py::test_lex_intervention_compiler_maps_provision_ref_to_knob_and_parameter`, `tests/unit/lex/test_interventions.py::test_temporal_intervention_sequencer_rejects_unknown_override_param`, and `tests/unit/lex/test_interventions.py::test_lex_provision_directive_requires_channels_when_strategic_response_expected`.

## Reference

::: polisyos.lex.intervention_artifacts

::: polisyos.lex.interventions

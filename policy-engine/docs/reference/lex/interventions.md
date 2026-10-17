# Lex Interventions

Related explanation: [Lex Pipeline](../../explanation/lex-pipeline.md).

Freshness: 2026-10-17
Owner: `@lex-owners` for provision-to-policy mapping and typed runtime inputs; Scientist and Foundry own the downstream planning and causal-method execution bridges.
Historical source pin: `b700c1b434f2a64e51f09a74a5605d7c896fd1f3` for existing IR, Scientist consumers, and pre-candidate test bytes; it predates the candidate Lex owner files and the separately bound test postimage below.
Source of truth: `src/polisyos/lex/interventions/compiler.py`, `src/polisyos/lex/interventions/artifacts.py`, `src/polisyos/ir/governance/policy_spec.py`, and the named test below.
Evidence level: existing IR/Scientist sources and prior test files were inspected at the historical source pin; candidate Lex owner files are bound by postimage hashes below. Tests were inspected, not run for this documentation refresh. The fixture covers mapping and validation behavior, not legal-source verification or a live policy/causal end-to-end run.

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

Candidate owner source inspected in the R4 overlay (file hashes, not a Git revision):

- `src/polisyos/lex/interventions/artifacts.py` — `sha256:565135daaaddbf4d3cad03c6eb1af92481cbd656df21f081a39dcb7dcb68ae86`
- `src/polisyos/lex/interventions/compiler.py` — `sha256:8afbe3f6e55575e0efb98584560d8a95fa51a5b609245fd90ff439f3c048aa47`

Candidate-only test source: `tests/unit/lex/interventions/test_compiler.py` — R4 added postimage `sha256:f96ddb9b33825863c1b233be25e03480172f9cd4ac495b5cefaae9d66d1cea9e` (no b700 preimage). The three selectors below were included in R4 run `candidate-lex-tests-r3` (30 passed); result `validation/r4/validation-results-r4.json` has SHA-256 `37ae1d635acb1b747d58a5c1d26e276e30ede95726a2090fff766c1191f4bc88`. This documentation successor did not rerun tests.

- Compiler, registry, and IR boundary: `src/polisyos/lex/interventions/compiler.py`, `src/polisyos/lex/interventions/artifacts.py`, and `src/polisyos/ir/governance/policy_spec.py::InterventionSpec`.
- Scientist consumers: `src/polisyos/scientist/nodes/builtins/planning/run_hierarchical_policy_search.py` and `src/polisyos/scientist/nodes/builtins/causal/run_causal_contract_execution.py::TemporalInterventionSequenceCompiler`.
- Mapping and validation fixtures: `tests/unit/lex/interventions/test_compiler.py::test_lex_intervention_compiler_maps_provision_ref_to_knob_and_parameter`, `tests/unit/lex/interventions/test_compiler.py::test_temporal_intervention_sequencer_rejects_unknown_override_param`, and `tests/unit/lex/interventions/test_compiler.py::test_lex_provision_directive_requires_channels_when_strategic_response_expected`.

## Reference

::: polisyos.lex.interventions.artifacts

::: polisyos.lex.interventions

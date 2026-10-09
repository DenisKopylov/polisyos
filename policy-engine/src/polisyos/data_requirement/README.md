# Data Requirement (`polisyos.data_requirement`)

`data_requirement` compiles W6 policy grammar facets, obligation graph frontiers,
and claim ledgers into claim-bound `DataRequirementSpec` artifacts for Fabric.

## Role in System

- **Consumes:** `policy_grammar`, `obligation_graph`, `obligation_rules`, and
  `scientist.policy_design.claim_decomposition`.
- **Produces:** typed `DataRequirementSpec` rows plus the
  `policyos.data_requirement_compilation.v1` bridge report.
- **Used by:** Fabric source-contract binding, runtime-quality scenario contracts,
  and production-data static checks.

## Contract

Each requirement carries the required data family, claim id, population/geography/time
scope, recency horizon, lineage strictness, quality minima, missingness tolerance,
transformation tolerance, admissibility predicates, mandatory facets, concept refs,
and authority-profile refs.

The legacy `scenario_evidence_contract.admissible_data_source_families` surface is a
compatibility projection from compiled specs. New consumers should read
`data_requirement_specs`; closeout compatibility may continue to read the projected
family list until its shim sunset.


## Runtime Constraint Compilation

DataRequirementCompiler.compile_obligation_basis is the existing compiler's
runtime-facing W6.A→W6.B→W6.C stage. It accepts the existing typed grammar intent,
authority profile, and concept-spine refs, then returns the grammar case, facet
snapshots, governed seed catalog, and obligation graph from their owner compilers.
Blocked or candidate-unverified grammar status is retained without compiling a
downstream graph. This stage establishes compilation only; runtime source
verification and constraint admission remain separate gates.

Before emitting a Phase-2 constraint snapshot, runtime reads the record limit from
the existing `ConstraintStoreSnapshot` schema. If the complete owner-recomputed
population exceeds that limit, runtime persists the full basis and returns a typed
`constraint_population_budget_exceeded` refusal with its count, schema limit, CAS
ref, and content digest. It does not admit a truncated snapshot, and source
authority remains a separate missing basis.

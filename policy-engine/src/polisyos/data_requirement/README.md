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

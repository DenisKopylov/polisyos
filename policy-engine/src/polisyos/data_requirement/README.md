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

Scenario construct aliases may be omitted, supplied as a non-empty string, or supplied as a
sequence of strings; an empty sequence contributes no constructs. A present `null`, wrong type,
blank string, or invalid sequence item is malformed and returns a typed input refusal instead of
falling through to a default. Synonymous aliases in one profile must agree. Candidate construct
aliases remain proposals and are not promoted to required inputs. The legacy scenario-family
fallback keeps missing, explicit-empty, and declared frontiers distinct. Missing or explicit-empty
frontiers produce no fabricated source family; malformed declarations return a typed refusal.


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


## N7 Capability-Resolution Handoff

The compiler report carries a versioned `capability_requirement_resolutions` tuple for
all required constructs. Direct `required_constructs` and `construct_refs` inputs join
declarations from every compatible top-level or context scope-profile alias as one
ordered, deduplicated required set. Incompatible profile identity or scope, and any
malformed supplied construct value, produce a typed refusal instead of dropping the
input. Each resolution row retains the typed resolver query and either the resolver's
binding status, reasons, selected reference, index reference, and authority posture or
an explicit `not_established` reason. Candidate construct proposals remain separate;
they never enter the required set or its query tuple, and proposal-only input does not
suppress ordinary semantic requirement derivation. A missing tuple on a historical
report means that the resolution basis is not established; an empty tuple means the
current compiler produced no required-construct queries. Explicit profile time role and
granularity are retained as supplied; the compiler does not infer either from interval labels.

N7 copies each result into the matching compiled data-family gap. A required construct
without a data-family projection becomes a typed routing gap carrying the original
resolution. The planner action and acquisition receipt preserve that result. This route
records missing requirements only; it does not treat a selected capability as acquired
data, external authority, or requirement satisfaction. A blocked or unavailable
resolver therefore remains visible and cannot become a successful requirement resolution
or empty-spec success.

The Fabric Catalog projection consumes only fields represented by its existing DataNeed
contract. It carries typed source scope and unrepresented requirement fields in the owner
receipt as not-established limitations. DataNeed quality_min receives the requirement's
minimum quality score, not its completeness threshold. Catalog candidates remain candidate-only;
the projection does not create source binding, acquired content, or requirement satisfaction.
N7 copies the existing typed TimeFrequency token into the profile granularity field, but it
does not infer a time role from the interval. Missing profile scope or granularity and a
bounded interval without an explicit role cause a typed refusal before Catalog access. An
unbounded query may remain candidate-only with its absent time role marked not_established.
Every control declared only by `DataDiscoverRequest` is compared with the actual N7
`DataResolveRequest` surface and refused before Catalog access when present, including
malformed and zero-valued inputs. The adapter also refuses explicit legacy budget or
availability controls that `DataNeed` cannot express.

Pattern pass: this bridge addresses `P01`/`P02` by connecting the existing compiler
producer to the existing N7 consumer, and `P04`/`P05` by preserving blocked and
not-established outcomes without minting authority. Acceptance is a real N7 receipt
whose action record contains the exact profile-required query and binding result, plus a
candidate-proposal exclusion control.

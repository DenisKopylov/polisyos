# Data Requirement (`polisyos.data_requirement`)

`data_requirement` compiles W6 policy grammar facets, obligation graph frontiers,
and claim ledgers into claim-bound `DataRequirementSpec` artifacts for Fabric.

## Role in System

- **Consumes:** `policy_grammar`, `obligation_graph`, `obligation_rules`, and
  `scientist.policy_design.claim_decomposition`.
- **Produces:** typed `DataRequirementSpec` rows plus the
  `policyos.data_requirement_compilation.v2` bridge report.
- **Used by:** Fabric source-contract binding, runtime-quality scenario contracts,
  and production-data static checks.

## Contract

Each requirement carries the required data family, claim id, population/geography/time
scope, recency horizon, lineage strictness, quality minima, missingness tolerance,
transformation tolerance, admissibility predicates, mandatory facets, concept refs,
and authority-profile refs.

The legacy `scenario_evidence_contract.admissible_data_source_families` surface remains a
candidate compatibility projection. New consumers should read `data_requirement_specs` and the
producer-owned `requirement_basis`. Compilation reports bind the basis to an event reference,
subject refs, rule-version refs, and a SHA-256 input digest. A consumer-declared family is
`consumer_asserted`, never an authority-grade resolver result. Missing or explicit-empty
frontiers produce a typed `not_established` basis, not a fabricated family or a no-data success.
The public `data_requirement_compilation_event_ref(run_id)` helper constructs the v2 event
reference by reversible UTF-8 URI-component encoding, preserving case and underscores while
keeping distinct run IDs distinct.

The current producer emits the strict `policyos.data_requirement_compilation.v2`
schema. The explicit `parse_data_requirement_compilation_report` reader also
accepts the strict historical v1 report shape as
`DataRequirementCompilationReportV1`. Its typed `requirement_basis` property is
`not_established` with reason `legacy_report_basis_not_carried`; it is not part
of the v1 payload and is never serialized back into that report. The audit
projection exposes that typed unknown separately, while a byte-input report
writer preserves the original v1 bytes. V1 reports carrying any extra field,
including a forged basis, are refused. V2 report filenames use the SHA-256 of
their exact serialized bytes, avoiding run-ID slug collisions; repeated exact
bytes are idempotent, while a mismatched existing destination refuses. The v1
legacy filename remains unchanged and conflicting bytes at that name refuse
instead of replacing the prior record. Use the versioned reader for persisted
reports; direct `DataRequirementCompilationReport.model_validate` remains the
strict v2 producer contract.

The normalized scenario evidence contract is v2. Its public scenario loader
consumer must match that schema while retaining v1 `contract_id` values as
scenario identity, not as the contract schema version.

Scenario construct aliases may be omitted, supplied as a non-empty string, or supplied as a
sequence of strings; an empty sequence contributes no constructs. A present `null`, wrong type,
blank string, or invalid sequence item is malformed and returns a typed input refusal instead of
falling through to a default. Synonymous aliases in one profile must agree. Candidate construct
aliases remain proposals and are not promoted to required inputs.


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

## Declared Domain and Claim Input Contracts

The scenario adapter interprets `domain` and `domain_hint` as declared routing
vocabulary. Canonical `ProblemDomain` names/values, case/separator spelling and a
terminal `policy` suffix select the same enum. The finite vocabulary also includes
`health`, `health care` and `образование`. It never selects a hard domain from a
scenario ID or lexical topic. A supplied unknown label routes as `CUSTOM` with
`unresolved` status; an absent label routes as `CUSTOM` with `not_supplied` status.
Both retain candidate work and explicit constructs, without claiming that every
custom domain has methodological support.

Empty/non-string fields and incompatible simultaneous `domain`/`domain_hint`
declarations raise `ScenarioDomainInputError` before grammar execution. Its code
is `scenario_domain_input_invalid`, with `reason_code` (`domain_wrong_type`,
`domain_empty`, or `domain_alias_conflict`) and an exact `field_path`. Equivalent
aliases may be supplied together; two different unknown labels are not silently
treated as the same declaration.

New scenario reports retain raw domain fields, canonical value, resolution status
and purpose under `metadata.scenario_domain_resolution`. The interpretation rule
`policyos.data_requirement.scenario_domain.v1` joins the report rule references and
input-content binding. The report schema remains V2; no reader retroactively adds
this interpretation to an old report. Domain normalization is routing vocabulary,
not source authority or proof of semantic support.

Per-claim Mapping input follows the strict `ClaimRecord` contract: construct
requirements belong in `metadata.required_constructs` or its supported metadata
aliases. Top-level claim `required_constructs`, `required_evidence_constructs`,
`explicit_constructs`, `construct_refs` and `construct_ref` are unsupported and
raise `ClaimConstructDeclarationInputError` with an exact claim/field path rather
than disappearing. This bounded contract differs from scenario-level and
scope-profile construct declarations, which remain supported. The finite
first-party caller census found no maintained public compiler producer requiring
a top-level per-claim declaration; a private-helper test does not extend that API.

Strict readers retain the exact source bytes of unchanged V1 and V2 reports.
The immutable writer preserves those bytes and their content address; if a model
was intentionally changed, it compares the semantic projection and writes new
bytes instead of returning stale retained input. Historical reports keep their
old basis and do not gain the new domain-rule metadata. Actual acquisition and
N7 source admission remain separate consumers of the compiled denominator.

### Candidate Source Discovery

An injected resolver may implement the optional neutral
`CapabilityCandidateDiscoveryPort.discover_sources(query)` alongside its
existing authority `resolve(query)`. The compiler keeps the original
`claim_evidence_closeout` query and complete binding unchanged. A typed
`candidate_discovery` sibling records the finite loaded-index lookup, complete
owner descriptors, their content digests, and exact query identity. It never
satisfies claim evidence and always requires independent native source
admission. Descriptor identity is not external source provenance, permission,
release currency, execution approval, or model adequacy.

Known population, entity, geography, and time mismatches exclude a source.
Generic or missing query scope and missing source coverage remain named
candidate limitations; they are not silently replaced by the source scope.
The existing scope profile also accepts explicit `population` and
`entity_scope` declarations. They survive the compiled query and requirement
scope without adding domain-specific branches or claiming source authority.

An absent discovery port is represented by an omitted sibling, never a
successful no-match. A declared `CapabilitySourceDiscoveryUnavailableError`
preserves the existing claim binding with exact unavailability reason codes.
Malformed or mismatched discovery output refuses at the compiler boundary;
unrelated failures are not relabeled as an outage. Historical reports with no
sibling retain their original wire shape and exact source bytes. Consumers
must resolve the persisted compiler report and independently admit a source;
they cannot turn a descriptor or its hash into an admitted observation.

When grammar facets are not established, explicitly declared requirements reuse
the same canonical claim-ledger compiler. This preserves useful candidate
needs without asserting grounded policy semantics. Canonical specs replace a
same-family legacy projection; additional caller-only legacy families remain
in the denominator with an aggregate `consumer_asserted` basis. A recomputed
canonical subset cannot upgrade that tail. The report retains the grammar
limitation and complete blocked or admitted claim binding independently.

### World-Slot Requirement Joins

`compiled_requirements_for_world_slot` recomputes a routing-only join from the
existing typed specs and capability resolutions. It checks the complete spec
binding, original query and scope profile, index, descriptor digest, declared
source asset, target slot, and supported fetch/metric relationship. It returns
all matching spec occurrences: zero is unresolved and more than one is
ambiguous. Multiple source descriptors inside one spec remain available for
later independent selected-digest admission; the helper never chooses one.

A uniquely established slot declaration can reuse its canonical construct
spec rather than create a second legacy need. The original declaration and
source reference remain recorded. Unmapped or ambiguous declarations retain
their legacy rows and consumer-asserted aggregate basis. Optional fetch
`profile_id=None` remains valid. Semantic metric aliases require an actual
owner-bound mapping; this helper does not invent equivalence for differing
construct and metric identifiers.

Candidate discovery rule v1.2 and this join share the neutral
`candidate_source_time_coverage` predicate. It follows the kernel's ISO
calendar-date law, compares actual dates, refuses malformed or inverted
intervals, and requires complete coverage for known bounds. Absent bounds
remain explicit unknowns. A source's explicit foreign jurisdiction also
refuses. Existing claim-evidence resolution and historical report bytes retain
their original interpretation; these candidate checks confer no authority.

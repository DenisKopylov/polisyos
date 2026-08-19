---
title: OPS-R15 — Recommended Audited Revision
status: draft_audit
kind: research-audit
research_task: OPS-R15
source_report_status: delivered
source_report_result_type: accepted_narrow_scope
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
audit_date: 2026-07-27
audit_branch: research/ops-r15-independent-audit
authoritative_for:
  - repository audit findings at recorded commits
  - benchmark-validity and executability findings
  - recommended corrections to OPS-R15
may_not_use_for:
  - production capability claim
  - legal compliance certification
  - final runtime contract
  - production RPO or RTO commitment
  - authority grant
  - implementation authorization
  - proof that an external institution performed an act
  - proof of disaster-recovery capability
research_only: true
---

# OPS-R15 — Recommended Revision

## Research standing

```yaml
result_type: blocked_pending_oracle_independence
benchmark_kernel: accepted_as_research_guidance
extension_packs: deferred
contract_standing:
  - research_only
  - candidate_for_consolidation
repository_historical_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
repository_current_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
pao_r0_audit_commit: 258aa740efcfb9e6771bfe52d4fdabc6b74f93a7
pao_r1_audit_commit: 566840c330e867a15313923c87c20b6863cb053f
```

This revision does not overwrite the delivered OPS-R15 report. It retains the report's custody proposition and strongest falsifiers while removing claims that the prose calendar is already an executable, independent Stage-0 benchmark.

## Revised executive finding

PolicyOS custody is benchmarkable as a bounded set of observable semantic predicates: durable suspension, exact wake binding, fresh action-specific authority admission, payload-versus-authority invalidation, append-only correction, transaction-time historical replay, independent current-state reconstruction, scoped affected-set recall, tenant/jurisdiction isolation, external-act separation, public stale/current accuracy, idempotence and recoverable custody state.

The delivered 24-month calendar is a valuable scenario catalogue but not yet a valid capstone benchmark. Its expected results and oracle labels are co-located with visible inputs; no machine-readable oracle or independent evaluator is supplied; repository capability chains are incomplete; institutional/legal facts are synthetic; and many calendar rows prescribe unresolved H2, OPS-R1–R14, PAO, INT, Atlas, Fabric, Lex or DDM designs.

The safe Stage-0 anchor is therefore the 16-predicate kernel in the companion kernel specification. Legal, KPI, institutional, public-correction, cryptographic, world-release, matter-lineage, fleet and production-resilience material becomes optional conformance packs.

## Claim and validity boundary

A benchmark pass supports only the following bounded claim:

> The named implementation, repository revision and test environment satisfied the committed semantic predicates for the frozen fixture populations and declared scenario assumptions.

It does not prove production readiness, legal validity, institutional competence, causally safe policy adaptation, universal dependency completeness, disaster-recovery SLOs, or authority to perform external acts.

## Ratified and audited inputs

### Stable repository-derived constraints

- PolicyOS authority is purpose-scoped: permitted use narrows and prohibited use accumulates under `AuthorityBoundary`.
- verifier-owned authority fields and projection-only surfaces must not be bypassed;
- custody facts, corrections and supersession are append-only;
- external execution is not established by receipt, authentication or display of evidence;
- historical replay and current rebuild answer different questions;
- tenant and jurisdiction scope are security and authority inputs, not labels;
- candidate evidence and workflow state do not self-promote to authority.

### PAO-R0 assumptions

No production `PolicyMatter` contract exists. Matter identifiers, split/successor semantics and matter-scoped inheritance are optional fixture assumptions pending consolidation. Kernel fixtures use opaque fixture-local subject references and require tenant-qualified binding; they do not prescribe PDC ownership, status enums or a final schema.

### PAO-R1 assumptions

The benchmark preserves the five-layer distinction:

1. external institutional act;
2. external evidence emission;
3. PolicyOS receipt/admission;
4. PolicyOS claim reaction;
5. public projection.

An external act is externally owned or out of PolicyOS execution scope; only its evidence interface and PolicyOS reaction can be integrated/owned. The rejected 213-row register, universal institutional envelope, owner-state lattice and exact clock bundle are not benchmark inputs.

## Correct benchmark composition

OPS-R15 is a suite, not one monolithic proof:

- a mandatory semantic custody kernel;
- identity/boundary, temporal/replay, dependency, public-record and resilience conformance profiles;
- optional task-owned extension packs;
- a separate production-like exercise programme for deployment RPO/RTO.

Each profile declares its claim, fixture population, observable outputs, independent oracle, environment, exclusions and uncertainty. Results are never averaged across critical lanes.

## Fixture architecture

### Public material

Publish schemas, invariant definitions, scoring rules, admissible output equivalence, fixture-family descriptions and external-validity limitations.

### Implementation-visible input

Supply only input actors, external events/evidence, infrastructure faults and invocation context. Do not include `expected_wake`, expected impact sets, expected PolicyOS actions, expected public posture, prohibited outcome, oracle reference, hidden dependency truth or scoring label.

### Sealed oracle material

Store expected predicates, allowed alternative outcomes, negative controls, dependency truth and ambiguity labels in a separately access-controlled repository or artifact store. Publish a cryptographic commitment before execution. Keep oracle authorship and custody separate from implementation.

### Run material

Record the implementation revision, dependency lock, environment/topology, wall-clock source, virtual-time seed, fixture/oracle/evaluator hashes, access events, output artifacts, public observations, failures and adjudication.

## Event model

The benchmark may use a test-only wrapper:

```yaml
fixture_event:
  fixture_event_id: opaque, permutable
  family: fixture-local discriminator
  producer_ref: fixture actor
  subject_ref: opaque fixture subject
  tenant_ref: required
  jurisdiction_ref: required or explicitly unknown
  event_time: family-defined or null
  observation_time: family-defined or null
  delivery_time: evaluator-controlled
  payload_ref: content-addressed family-native payload
  provenance_ref: fixture provenance
```

The wrapper is not a production `ExternalEvent`. Producer-supplied events do not carry admission time, transaction time, downstream action permission, expected wake, expected impact, expected action or oracle reference. Receipt, verification, admission, reaction and projection are separately observed outputs.

## Temporal model

Require only clocks with a declared owner and meaning:

- source event/effective/valid time where meaningful to the family;
- PolicyOS receipt and admission event references;
- storage-assigned transaction sequence/time;
- evaluator delivery time and wall-clock measurement;
- publication/correction/revocation event references where tested.

Historical replay is evaluated at a transaction-time cutoff with the exact rule/schema/validator/authority versions visible then. “Current rebuild” evaluates all admitted current facts. Byte equality is required only for canonical signed artifacts whose serialization is frozen; otherwise the oracle specifies semantic equivalence and permitted nondeterminism.

## Suspension, wake and gate model

Suspension is durable and reconstructable without a live worker. A wake is a typed candidate for reevaluation, not permission to resume or publish. Exact subject, tenant, jurisdiction, generation and dedupe binding are mandatory.

The evaluator checks phased protections:

- core state integrity and security binding before evaluation;
- action-specific authentication, authorization, authority, evidence, freshness and compatibility before protected actions;
- conditional budget, certified-envelope and human gates only when the scenario/action requires them;
- public implications, correction and authority posture before signing or current publication;
- dependency fan-out may be asynchronous, but affected authority-bearing actions remain frozen until complete.

Equivalent implementations may organize these protections differently. “All twenty gates on every resume” is removed.

## Dependency and rebuild model

Payload dependencies and authority dependencies are distinct semantic relations, but the benchmark does not require two physical graphs. Impact categories may overlap.

Affected-set recall is critical only against an independently authored closed truth set. Precision, reuse and minimal recomputation are diagnostic until OPS-R2 establishes safe equivalence and complete denominators. A same-code full rebuild is a consistency check, not an independent semantic oracle. The reference evaluator must not import the implementation's reducers, admission service, dependency traversal or status projector.

## State model

Replace required state names with predicates:

- suspended state is durable and non-executing;
- evidence has no authority effect before admitted for a declared purpose;
- current authority is distinguishable from stale, contested, corrected, superseded and historical-only posture;
- public currentness follows admitted lifecycle facts;
- release compatibility and selection are atomic when the optional profile applies.

Internal enum names, number of states and transition layout remain implementation choices. `benchmark_passed` must never be a runtime authority or world-release state.

## Oracle governance

### Semantic oracle

Use a declarative, versioned predicate set and a separately implemented evaluator. Represent one correct result, a set/range of acceptable results, `contested`, or `unresolved`. Preserve every scored oracle version and run. Corrections supersede; they do not rescore history silently.

### Authority oracle

Treat competence, finality, proof of service, matter identity, succession and remedy status as fixture-local scenario axioms reviewed by relevant experts. Record jurisdiction, authority source, reviewer conflicts and uncertainty. Do not call synthetic labels legal ground truth.

### Human oracle

Pre-register reviewer eligibility, training, blinded assignment, conflicts, abstention, agreement statistic, adjudication and drift checks. Retain raw labels and rationale. Three reviewers may be a minimum fixture design, not universal sufficiency; majority vote cannot create authority.

### Public oracle

Test predicates—external attribution, evidence/admission qualification, as-of information, stale/current/corrected posture and no authority minting—against a frozen inventory of controlled surfaces. Defer exact vocabulary to PAO-R36/Atlas owners.

### Recovery oracle

Separate semantic conformance, synthetic integration and production-like exercises. Report environment and wall-clock results. Virtual time cannot prove infrastructure recovery.

## Metrics and verdicts

Every metric declares numerator, frozen denominator, unit, data source, oracle, exclusions and ambiguity policy. Critical predicates fail their applicable profile; no weighted score overrides them. Diagnostic metrics cannot grant authority.

Preserve as critical after correction:

- lost durable custody object;
- unauthorized authority upgrade;
- stale public shown as current on a controlled surface;
- silent historical rewrite;
- duplicate irreversible PolicyOS effect;
- wrong-tenant/jurisdiction admission;
- external-execution overclaim;
- observation/candidate-to-authority upgrade;
- independent rebuild disagreement;
- affected-set recall miss against sealed truth.

Redefine:

- “out-of-boundary action attempted” as an implementation-originated invocation, excluding evaluator probes while requiring probe denial;
- public consistency over a frozen controlled-surface inventory and reconciliation window;
- recomputation measures against sealed affected truth;
- late-event correctness as per-event predicate groups, not a prose assertion.

Demote reuse share, minimal-recompute share, recompute precision, human false-escalation rate, aggregate DR success and all latency/RPO/RTO thresholds to diagnostics until their task/environment owners justify them.

## Anti-overfitting protocol

At least one sealed adjacent case and one metamorphic family per critical property are required. Use opaque randomized IDs, delivery-order permutations, wrong-scope look-alikes, wrong tenant/jurisdiction variants, and deliberately missing dependency edges. Run the implementation in a sandbox that cannot read oracle artifacts. Scan outputs/builds for fixture IDs only as a supplementary check; behavioral permutation is the primary detection method.

Limit run access, record every query, rotate hidden variants after a declared exposure budget, and retire compromised fixtures. Never commit sealed answers or decryption material to the implementation repository or its Git history.

## Corrected scenario disposition

The original 117 rows are retained as a research catalogue:

- 24 rows seed the mandatory kernel after input/oracle separation;
- 16 rows require explicit external-act/evidence/admission/reaction splitting;
- compound and institution-dependent rows become extension-pack material;
- all 117 need machine-readable inputs, independent expected predicates and declared acceptable alternatives before execution.

No row is independently executable merely because its expected action is detailed.

## Resilience posture

Zero-RPO and 1/4/8/24/48/72-hour targets are illustrative scenario numbers only. A semantic fixture may require “no acknowledged custody event is silently lost” and “never expose unverifiable restored state as current.” Deployment RPO/RTO requires topology, durability boundary, acknowledgement semantics, fault scope, recovery resources, wall-clock measurement and accountable SLO owner.

The 10,000-case event is a future fleet-load exercise, not evidence from Stage 0.

## Promotion and kill rules

`research_only` continues until machine-readable packages and an independent evaluator exist.

`prototype_allowed` permits only isolated fixture/evaluator work with synthetic data and no external act.

`governed_evaluation_allowed` additionally requires sealed governance, closed denominators, audit reviewers, PAO cross-anchor assumptions, independent evaluator and preserved failures.

No benchmark status authorizes production.

A run is invalid—not merely failed—if fixture answers leak, the oracle changes after outputs are viewed, populations are selectively excluded, the evaluator shares semantic reducers, the environment/revision is unrecorded, or access controls cannot be demonstrated.

## Stage-0 anchor packet

Safe to freeze as research guidance:

1. custody is a bounded-composition claim, not universal proof;
2. wake never equals authority-bearing resume;
3. external act, evidence, admission, reaction and projection are separate;
4. payload validity and authority validity are distinct;
5. current rebuild and historical replay are distinct;
6. corrections append and preserve historical views;
7. wrong tenant/jurisdiction/subject fail closed;
8. critical lanes cannot be averaged away;
9. benchmark inputs cannot disclose expected outputs;
10. same-code rebuild is not an independent oracle;
11. benchmark passage grants no production or legal authority;
12. failed runs, oracle versions and challenges remain auditable.

Not safe to freeze: exact production contracts, state names, gate count, graph layout, common clock bundle, `WorldRelease`, `PolicyMatter`, institutional legal answers, performance targets or full calendar.

## Required work before first scored run

1. Consolidate PAO-R0/R1 assumptions or localize them explicitly.
2. Publish machine-readable public/input schemas.
3. Establish oracle-author/custodian/evaluator separation and access controls.
4. Build an independent declarative evaluator.
5. Convert the 24 kernel rows into sealed predicate fixtures and define acceptable alternatives.
6. Freeze controlled surfaces and observable effect ledgers.
7. Exercise ID/order/adjacent-case transformations.
8. Pre-register all populations, denominators, environment and invalid-run conditions.
9. Conduct a dry run whose outputs cannot be used to alter thresholds.
10. Review by architecture, PDC, runtime quality, control plane, Fabric, Lex, DDM, audit/security, publication and PAO audit owners.

## Final posture

OPS-R15 should constrain later research only at the semantic-invariant level. The report's broad calendar remains useful as a scenario bank and cross-task requirements elicitation tool. It must not certify the self-authored future architecture, and it must not be described as an executable capstone until independent oracle, sealing, observability and conformance-profile prerequisites are met.

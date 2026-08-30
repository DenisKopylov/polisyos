---
task_id: INT-R3
stage: 1
title: Authority UI comprehension benchmark
status: research_complete
date: 2026-08-28
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
branch: research/int-r3-research
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
evidence_standing: not_established
authoritative_for:
  - benchmark_specification_candidate
  - pre_build_surface_constraints
  - research_findings
may_not_use_for:
  - claim_that_operator_comprehension_is_established
  - human_subject_result
  - publication_authority
  - governance_threshold
  - implementation_closure
---

# INT-R3 — Authority UI comprehension benchmark

## 1. Task And Project Fit

### Source task and exact question

Can a real operator, under time pressure, act correctly when shown a weakest link, a set-valued value,
`unknown`, `incomparable`, a δ-budget, a stale epoch, a quarantine and an acquisition route?

The deliverable is an `AuthorityUIComprehensionBenchmark` measuring behavior rather than preference:
the operator finds the true blocker; preserves `unknown ≠ zero ≠ missing`; treats `incomparable` as
absence of an admissible ranking; refuses stale and quarantined evidence; does not read a small
δ-budget as high value; and chooses acquisition, escalation or abstention correctly under
keyboard-only, screen-reader, low-numeracy and time-pressure conditions.

This is a mandatory design input. It must constrain a slice before surface completion and may not be
recast as a post-hoc usability survey.

### Why research first

The programme already relies on typed refusals remaining sharply visible and demonstrable in the
absence of institutional authority. That architecture is honest only if a person can use the refusal
to avoid an unauthorized act and take the correct next transition. Structural conformance, field
presence and good design practice do not answer that question.

The false production claim prevented by this work is:

> Because the interface faithfully renders a typed refusal and meets structural accessibility checks,
> a real operator will understand it and act safely.

No human-subject study was run in stage 1. The current PolicyOS claim is therefore:

```yaml
operator_comprehension: not_established
operator_actionability: not_established
```

### Four-way boundary verdict

**Primary verdict: OWN.** PolicyOS owns the requirement to establish that its own signed authority
projections support correct action. If this premise is false, a technically truthful projection can
still mislead in operation and weaken the effective justification claim.

The execution boundary is split:

- **OWN:** benchmark contract, frozen surface/packet binding, semantic conformance, action event,
  metric derivation and fail-closed use of the result;
- **INTEGRATE:** operator recruitment, research ethics where required, competence records, local
  action policy, escalation authority and governance thresholds;
- **OBSERVE:** organizational training, adoption and workarounds in later field validation;
- **OUT_OF_SCOPE:** preference or satisfaction as correctness, and owning an employer, ethics board,
  court or operational command system.

No contradiction with the identity decision or the demonstrability ruling is established at stage 1.
The external record shows a material untested premise and credible failure mechanisms, not that the
canonical PolicyOS refusal pattern is already non-actionable. A real run demonstrating systematic
non-actionability would trigger the requested architect stop.

## 2. Current Repo Baseline

The coordinate-level inventory is committed at
[`int-r3/repo-baseline.md`](int-r3/repo-baseline.md).

### Existing operator targets

The repository already exposes or plans every construct required by the task:

- Trust Posture renders source-bound claim posture and the institutional appointment refusal through
  `TrustPosturePage`, `ClaimPostureRegister`, the strict schemas in `trust/domain/posture.ts`, and the
  generated `trust-claim-posture.v1.json` packet.
- `TimeSemanticsLabel` separates created, as-of, updated, valid-from, valid-until and freshness labels.
- Cycle Board places weakest links, missing link, acquisition route/economics, source freshness,
  owner route and public-safe explanation on the glass.
- Case Workspace exposes artifact absence, authority abstention, blockers, limitations, objections,
  abstentions, stage trace and the human-decision gate.
- Human Decision Gate carries role, decision class, information/channel/representation/time rights,
  mandate validity, evidence exposure and server-offered actions/modes.
- DS16’s red-first plan forbids point collapse, `unknown → zero/gap` and
  `incomparable → ranking`.
- DS17 requires the conditional δ chip on every rendered δ value with declared basis, obligation
  language, cutoff, unknown remainder and TTL.
- DS18 requires visible as-of/epoch/validity and distinct incident, appeal, correction, retraction,
  legal-change and bias perturbations.
- DS15/GY-N13b defines the planned passport/quarantine/re-entry path.

### The developed typed refusal

The trust-posture and case surfaces can jointly present:

- the absent role or accountable owner;
- a blocker/refusal code;
- the affected authority purpose and scope;
- denied uses;
- supporting material that remains inspectable;
- an owner route;
- an executable closure or appointment condition.

That is substantially stronger than a generic unavailable message. It is nevertheless only a
projection. `INT-R3` must test whether the operator locates the binding relation and selects a safe
transition rather than merely noticing the panel.

### Existing evidence and current gap

The repository has schema checks, AST/semantic negatives, component tests, page-accessibility
receipts, packet/DOM/MACHINE parity and action validation. It has **no admitted evidence that a target
operator understands the output or chooses a safe action**.

Three registered debts state the boundary directly:

- `DS11-CURRENT-PAGE-A11Y`: the recorded page suite was not fully green;
- `DS11-EXTERNAL-A11Y-COUNTERSIGN`: no current content-bound external countersign is admitted;
- `DS11-GENERAL-COPY-SEMANTICS`: the structural checker does not own arbitrary public copy.

Current capability standing for a behavioral comprehension benchmark is `absent/unallocated`: no
admitted contract, appointed owner, producer, study run, persisted event, scorer, result consumer and
promotion gate exist as one chain. This Markdown package is a research input, not `contract_only`.

### Smallest reuse-first path

Freeze the actual producer packet and dashboard build; use the existing trust, cycle, case and
decision routes; capture exact interaction events; derive a research-only result; and feed that result
into Atlas/GY distillation. Do not create a second status lattice, a parallel case system or a
simulated authority.

## 3. External Research Baseline

The full classification and transfer argument are committed at
[`int-r3/external-evidence-ledger.md`](int-r3/external-evidence-ledger.md).

### What the literature independently establishes

- Presentation can change objective comprehension and some decisions; professional status does not
  eliminate format effects.
- Hidden missing-as-zero can produce severe semantic error, while explicit missingness still does not
  guarantee epistemic restraint.
- Time pressure tends to compress search and can increase miss errors; expert recognition is useful
  under some environmental conditions and unsafe under others.
- Overrides are heterogeneous: the same observable override can be rational or dangerous;
  mandatory clicks and reasons can become ceremony.
- Compliance cost, alert history and workflow topology affect refusal behavior.
- Weak-link identification and correct chain aggregation are distinct tasks.
- FDA-style methods separate comprehension, application/self-selection and actual use.
- RAND-style adjudication preserves disagreement and supports set-valued action truth.
- Proper calibration scores must be supplemented by an explicit confident-and-wrong safety cell.
- Accessibility research shows that access to atoms does not ensure access to relations.

### What is not established

Direct evidence is thin for explicit epistemic `unknown`, pure set-valued uncertainty, UI-declared
strict incomparability, remaining policy δ-budget, quarantine behavior and uncertainty reasoning under
assistive technology. No surveyed study validates this exact eight-construct composition or the
PolicyOS surfaces.

### Transfer rule

A source-domain result transfers only as a failure mechanism or measurement precedent when the
structural relation is shared. Its prevalence, effect size and operational threshold do not transfer.
Every number remains attached to its original population, instrument, task and denominator in the
commissioned survey packet.

### Preserved disagreement

Naturalistic decision making and heuristics-and-biases are not reconciled by assertion. The benchmark
supports fast recognition inside a declared envelope and tests whether explicit exits are taken when
the envelope is violated. It neither forces full deliberation on every trial nor treats confidence in
recognition as authority.

## 4. Result

### Controlling result

The stage-1 result is a defensible, implementable **benchmark specification**, not evidence that the
surface works. The complete protocol is committed at
[`int-r3/benchmark-specification.md`](int-r3/benchmark-specification.md).

Until a sealed benchmark is run with real target operators against a frozen version of the actual
surfaces:

```yaml
comprehensibility: not_established
actionability_under_time_pressure: not_established
accessible_path_equivalence: not_established
low_numeracy_robustness: not_established
confidence_calibration: not_established
```

Literature synthesis cannot change those values.

### Ground-truth result

Correctness is defined by three sealed layers:

1. registered semantic truth;
2. frozen scenario facts;
3. a possibly set-valued admissible-action set `A_i*`.

Ground-truth disagreement creates `contestable`, exclusion from the primary score or an honestly
set-valued key. It is never resolved by majority after participant data are seen. If governing policy
permits both acquisition and escalation, the benchmark does not mark one wrong because a researcher
prefers the other.

### Metric result

The six mandatory metrics are defined with explicit eligible denominators:

- `false_action`;
- `false_pass`;
- `missed_blocker`;
- `unsafe_override`;
- time-to-correct with censoring and competing terminal outcomes;
- confidence-versus-correctness calibration, including direct high-confidence-wrong cells.

A blocked unsafe attempt is recorded separately from a committed unsafe action. A timeout is not
converted into an arbitrary slow success. A good average cannot compensate for a failed critical
safety cell.

### Pre-build result

Twelve red-first predicates bind the surfaces before completion. They require preservation of the
weakest-link relation, outer-set semantics, typed non-values, unrankability, δ riders, time/epoch
semantics, quarantine admission state, safe next routes, accessible relation order, attempt/commit
separation, pre-feedback confidence and sealed scoring keys.

### Standing under `W4-K05`

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

- Research is accepted for the protocol and bounded transfer arguments.
- Capability is absent/unallocated because no admitted implementation chain or owner exists.
- Gate is `NO_GO` for any claim that operator comprehension has been established or can close a
  surface/publication condition.

No axis is inferable from another. `evidence_standing: not_established` is an additional annotation,
not a replacement standing field.

## 5. Counterexamples And Failure Modes

1. **Honest and useless refusal.** The appointment panel accurately names the absent role and closure
   signal. Under a deadline, the operator presses the familiar commit path without using the refusal.
   Structural honesty passes; actionability fails.
2. **Weak-link averaging.** Components are `supported, supported, blocked`. The operator finds the
   blocked link, reports “two of three are fine” and passes. Detection passes; chain semantics fail.
3. **Outer-set point invention.** `[2,8]` is presented with a center marker; the operator treats `5`
   as the estimate and spends δ against it. Every source value remains technically present.
4. **`unknown` collapse.** A display labels a value unknown but leaves numeric zero in the same chart
   scale or export cell. The operator treats it as zero and clears the case.
5. **False ranking.** Two options are `incomparable`; equal local scores and vertical placement induce
   a tie or top-first choice, and the operator commits without a new admissible criterion.
6. **Budget inversion.** “2 units remaining” is read as “risk/value = 2” or positive permission rather
   than near-exhausted allowance.
7. **Stale-but-understood override.** The operator correctly understands that evidence is old, decides
   the age is irrelevant and uses it. A comprehension quiz passes while the policy action fails.
8. **Quarantine/provisional confusion.** Legitimate experience with provisional statistics makes
   `quarantined` look usable-with-caution rather than inadmissible.
9. **Accessible atoms, missing relation.** A screen reader exposes every value and reason, but the
   binding rider occurs after action controls and is never associated with the number.
10. **Hard-stop false success.** Every operator attempts the prohibited commit; a disabled control
    prevents it, and the system reports zero unsafe commits as comprehension.
11. **Ground truth by researcher taste.** Policy permits acquire or escalate, but the key marks only
    acquire correct and calls safe escalation an error.
12. **Confident-and-wrong hidden by average.** Hundreds of easy calibrated cases hide one
    high-confidence critical false pass.
13. **Learning the benchmark.** Repeated literal templates and immediate feedback teach operators to
    pattern-match the scored bank rather than understand unseen cases.
14. **After-hours phantom route.** Escalation appears available but the accountable role is absent;
    the benchmark key silently assumes a responder and rewards an impossible transition.
15. **Late evidence mutation.** Evidence becomes fresh after a trial, and the result is rewritten
    instead of preserving the original decision state and replay.

The general falsifier for an unsafe implementation is a counterfactual twin where the formal decision
state changes but the rendered/action state and event-derived score do not.

## 6. Benchmark Or Fixture Proposal

### Instrument layers

1. semantic micro-cases for exact type distinctions;
2. full synthetic operational cases with distractors;
3. high-fidelity interaction against actual Trust, Cycle, Case and Human Decision surfaces;
4. later shadow/field validation.

A stage-1 slice author can implement the first three without claiming the fourth.

### Factorial fixtures

The item grammar crosses weakest-link location, value type, ordering relation, δ state, time/epoch,
provenance/admission, route availability, authority, consequence, deadline, distractors and modality.
Counterfactual twins change one decision-relevant fact while preserving the rest.

Required twins include:

- `unknown ↔ 0` and `unknown ↔ missing`;
- outer set ↔ probability interval;
- incomparable ↔ tie;
- fresh ↔ stale;
- admitted ↔ quarantined;
- remaining allowance ↔ positive value signal;
- authority appointed ↔ absent;
- acquisition possible ↔ structurally impossible.

### Sealed evaluation

Before recruitment, seal:

- build and packet digests;
- scenario facts and registered vocabulary versions;
- true blocker set;
- evidence-admissibility matrix;
- admissible-action set;
- critical and eligible flags for every metric denominator;
- action/event schema;
- analysis and exclusion rules.

No correctness feedback occurs during a scored block. Participant and scenario are both sampled
factors. Actual thresholds require a later appointed governance owner.

### Human-review packet

Each item packet contains visual and accessibility-tree captures, raw MACHINE packet, expected
propositional relation, action key, adjudicator ratings and dissent, counterfactual twin, leak audit
and replay instructions.

### Accessible-path requirement

Every modality must preserve one inspectable semantic chain:

`overall state → binding link → reason → decision consequence → safe transition → underlying detail`.

Keyboard-only, screen-reader and low-numeracy conditions are crossed into the core instrument. They
are not appended as a conformance annex.

## 7. Artifact Contract Sketch

The following are research candidates for consolidation, not canonical owners.

```yaml
AuthorityUIComprehensionBenchmarkSpec:
  benchmark_id: string
  version: string
  build_ref: digest
  target_population: declared_scope
  constructs:
    - weakest_link
    - outer_set
    - unknown
    - incomparable
    - delta_budget
    - epoch_staleness
    - quarantine
    - acquisition_route
  conditions:
    - visual_pointer
    - keyboard_only
    - screen_reader
    - low_numeracy
    - time_pressure
  metric_version: string
  authority_boundary:
    authoritative_for: [research_protocol]
    may_not_use_for: [operator_authority, publication_authority, comprehension_claim]

AuthorityUIScenarioManifest:
  item_id: string
  semantic_rule_refs: [versioned_ref]
  packet_ref: digest
  latent_facts: object
  true_blockers: [blocker_ref]
  evidence_admissibility: [item_ref, state, reason]
  admissible_actions: [action]
  metric_eligibility: object
  item_state: sealed | contestable | invalid
  adjudication_ref: digest
  valid_from: timestamp
  expires_at: timestamp

AuthorityUITrialEvent:
  run_id: string
  participant_pseudonym: string
  item_id: string
  condition: string
  event_id: string
  monotonic_time: number
  wall_time: timestamp
  event_kind: focus | inspect | action_attempt | action_commit | timeout | confidence
  action: string?
  object_ref: string?
  interlock_result: string?
  source_digest: digest

AuthorityUIBenchmarkResult:
  run_id: string
  spec_ref: digest
  build_ref: digest
  population_scope: object
  item_population: object
  raw_event_manifest_ref: digest
  metric_report_ref: digest
  standing:
    research_standing: registered_value
    capability_standing: registered_value
    gate_standing: registered_value
  evidence_standing: not_established | recomputed | independently_reconciled
  limitations: [string]
```

Time, provenance, audience, rule/schema version, scope, uncertainty and all five lifecycles remain
load-bearing. Benchmark events belong to the research/epistemic lifecycle; they do not collapse
administrative, institutional or implementation states into one status.

### Canonical-owner map

- extend existing Atlas/GY surface and status owners; create no new display lattice;
- candidate benchmark specification/result owner: **missing**, to be routed through research
  distillation;
- raw action-event storage should extend the honest diagnostics/event/CAS substrate if distillation
  approves;
- semantic vocabularies remain owned by DS0/DS4/DS16/DS17/DS18 and their canonical contracts;
- operator authority semantics remain with INT-R5/GY-PA2/DS9, not INT-R3;
- research adjudication and governance thresholds require external accountable appointments.

## 8. Later Integration Handoff

| Chain role | Handoff |
| --- | --- |
| producer | benchmark runner bound to frozen packets/build and real target operators |
| persisted artifact/event | sealed scenario/adjudication records, raw trial events and metric report in CAS |
| bridge | existing runtime-dashboard routes and diagnostics/event capture; generated API only if required |
| consumer | Atlas slice acceptance gates, GY/DS distillation and later reviewer surface |
| verification | schema replay, event idempotency, counterfactual twins, independent metric recomputation and accessibility-equivalence audit |
| surface | research/reviewer report; never a public authority score without later routing |

Implementation home is Atlas/GY because the benchmark constrains existing gated surfaces. It is not a
new H2 custody-runtime subsystem and not a case-management product.

The integration must preserve:

- attempt versus commit;
- exact eligible denominators;
- packet/build/item identity;
- action-key policy version;
- item expiry and contestability;
- complete modality/environment context;
- historical replay;
- inability of a dashboard to mint `GO`.

## 9. Promotion And Kill Rules

### `research_only`

Current state. Required while no real run, no appointed owner or no sealed action key exists.

### `prototype_allowed`

All pre-build predicates have non-vacuous red witnesses; scenario/event schemas validate;
accessible-path parity is inspectable; only synthetic/internal pilot data are used; output remains
non-authoritative.

### `governed_allowed`

Requires appointed study and policy/risk owners, ethics/consent determination, sealed
preregistration, target-operator recruitment, independently adjudicated item bank, raw-event custody,
metric recomputation and declared thresholds.

### `production_candidate`

Requires independent replication and evidence that benchmark performance transports to shadow/field
behavior for the declared population and workflow. Every co-primary safety cell passes its approved
criterion; no aggregate score compensates.

### `blocked`

Block any comprehension claim when:

- no target-operator run exists;
- accessible and visual propositional structures differ;
- an item key moves after responses;
- a mandatory metric lacks its eligible denominator;
- critical confident-and-wrong is hidden;
- the build, packet or item cannot replay;
- a missing institutional owner is impersonated;
- the benchmark teaches its scored bank;
- the action route depends on an unavailable owner not encoded in the scenario;
- a real run materially contradicts the demonstrability ruling pending architect decision.

### `kill / redesign`

Kill or redesign a display or item family when counterfactual twins do not change action as the formal
semantics require, or when a modality systematically cannot reach the binding relation. Do not repair
this by lowering the safety threshold, merging statuses or removing the refusal.

## 10. Open Questions For Consolidation

1. **INT-R5 seam:** who supplies the action-admissibility policy, role competence and escalation
   authority without INT-R3 creating a duplicate authority model?
2. **INT-R6 seam:** which semantic identifiers must survive locale/translation so the same item key
   remains valid?
3. **DS9:** how does the benchmark bind to server-offered decision modes and distinguish an attempted
   override from a committed one?
4. **DS16/DS17/DS18:** which successor plans consume the red-first predicates before their surface
   contracts freeze?
5. **DS15/GY-N13b:** is quarantine technically enforced, advisory or both; what event proves use?
6. **Ground-truth institution:** who appoints item adjudicators and the governance loss/acceptance
   owner? No signer exists.
7. **Thresholds:** what maximum upper confidence bounds are acceptable for each safety cell and
   population? Stage 1 does not invent them.
8. **Field transport:** which operational audit or outcome can validate simulation without converting
   PolicyOS into the administrator or employer?
9. **AT × uncertainty:** direct evidence is thin; which item families require formative co-design
   before a powered comparison?
10. **Canonical contract owner:** distillation must decide whether to extend honest diagnostics,
    Atlas verification artifacts or another existing owner. This package creates no canonical family.
11. **OPS-R15 capstone:** which capstone event supplies a realistic operator decision point and
    after-hours escalation failure without making INT-R3 depend on unresolved future work?
12. **Demonstrability ruling:** predefine the result pattern that triggers architect stop rather than
    allowing a failed run to be cosmetically reframed.
13. **Training boundary:** which examples belong in operator training and which remain sealed to
    preserve benchmark validity?
14. **Population boundary:** what roles, authority levels, tenure bands and operating environments
    define the first target population?

## Operational closure addendum

### A1. Boundary census

The primary benchmark obligation is OWN; recruitment, ethics, operator competence, authority and
governance thresholds are INTEGRATE; adoption and workarounds are OBSERVE; preference-as-correctness
is OUT_OF_SCOPE. Owners are mapped in the baseline. The canonical benchmark owner and institutional
signers are currently missing.

### A2. Real operator workflow

1. A policy analyst or reviewer opens a run, Trust Posture, Cycle Board or Case Workspace in the
   normal dashboard.
2. The system presents current packet state and, where applicable, a decision request.
3. The operator must locate the binding reason, inspect evidence as needed and take one terminal or
   transitional action.
4. On a missing concrete input, acquisition routes to the named producer/owner.
5. On authority or independent-judgment need, escalation carries the case state and trigger.
6. On unresolved uncertainty or absence of a safe route, abstention/defer records reason, next owner
   and revisit trigger.
7. On UI, API or assistive-technology failure, the trial enters degraded/aborted state; no missing
   event is imputed as a safe action.
8. After hours, owner unavailability is a scenario fact and changes `A_i*`; the researcher may not
   silently substitute an imaginary responder.

### A3. State machine

```text
DRAFT
  -> SEMANTICALLY_VERIFIED
  -> ACTION_ADJUDICATED
  -> SEALED
  -> SCHEDULED
  -> RUNNING
  -> SCORED
  -> INDEPENDENTLY_RECONCILED
  -> CLOSED
```

Side states and transitions:

- any pre-seal defect -> `INVALID`;
- unresolved policy disagreement -> `CONTESTED`;
- environment/AT/event failure in run -> `ABORTED`;
- version or policy expiry after close -> `SUPERSEDED`;
- governed new evidence -> `REOPENED` through a new version, never silent edit.

Clocks: manifest validity, policy/adjudication version, participant session, monotonic event clock,
deadline and result review due. Owners: item author, semantic verifier, adjudication panel, study
operator, metric recomputer and governance consumer; institutional roles are not currently appointed.
Terminal states are `CLOSED`, `INVALID`, `ABORTED` and `SUPERSEDED`. Public meaning remains
research-only unless a later gate promotes a bounded claim.

### A4. Typed artifacts

Candidate shapes are specified in §7. The minimum artifact set is:

- `AuthorityUIComprehensionBenchmarkSpec`;
- `AuthorityUIScenarioManifest`;
- `AuthorityUIReferenceStandard`;
- `AuthorityUITrialEvent`;
- `AuthorityUIBenchmarkRun`;
- `AuthorityUIMetricReport`;
- `AuthorityUIFindingRecord`.

Each carries an authority boundary, build/packet/source versions, time, audience, scope and
`may_not_use_for`. None establishes a new canonical owner.

### A5. Edge-case fixtures

| Fixture | Expected handling |
| --- | --- |
| happy path | correct terminal action and calibrated confidence |
| missing evidence | pass/commit prohibited; acquire/escalate/defer per sealed key |
| late evidence event | does not alter sealed trial retroactively; later version/replay |
| duplicate event | identical id and content are idempotent |
| conflicting duplicate | trial quarantined pending reconciliation |
| conflicting authority | item contestable or action set narrowed fail-closed |
| owner unavailable | after-hours route changes admissible actions explicitly |
| malicious actor | tampered packet/event digest invalidates trial |
| degraded mode | accessible or API failure produces aborted/non-receipt, never safe pass |
| partial success | blocker found but unsafe action taken: detection success, action failure |
| rollback | new result supersedes; old raw record remains provable |
| historical replay | original build, packet, policy and metric version reproduce |
| hard-stop attempt | attempt logged; commit absent; comprehension not inferred |
| stale badge present/use continues | `P38` marker/property divergence |
| screen-reader atoms/no relation | accessible-equivalence failure |
| multiple safe exits | set-valued key accepts each permitted action |
| confident critical error | direct high-confidence-wrong cell fires regardless of aggregate score |
| acquired wrong gap type | additional rows do not close a structural/authority gap |
| ranking with all zero scores | no order is inferred from position or identical scalar display |

### A6. Tabletop and fault injection

- kill the packet provider after the UI loads;
- remove the benchmark worker during event ingestion;
- send duplicate and conflicting terminal events;
- cross an epoch boundary mid-session;
- replace fresh evidence with stale bytes while retaining the badge marker;
- expose quarantined evidence through an alternate route;
- remove the escalation owner after the decision request;
- inject conflicting policy/action rules;
- make the accessibility tree ready after visual action controls;
- trigger a mass result invalidation after policy revision;
- recover from CAS/event outage and reconcile idempotently;
- attempt rollback and historical replay.

Success means no false positive is minted: affected trials are blocked, aborted, contested or
superseded with visible cause and recoverable history.

### A7. Capstone linkage

The benchmark plugs into the OPS-R15 custody-cycle capstone as the human-action leg:

```text
capstone event
  -> PolicyOS evidence/authority projection
  -> operator receives decision surface
  -> acquire / escalate / abstain / pass / commit event
  -> benchmark scoring and confidence
  -> later revalidation after epoch/perturbation
```

The capstone supplies realistic lifecycle and after-hours context; INT-R3 supplies the human-behavior
measurement contract. Neither may claim the other’s unresolved producer or authority.

## Pattern Pass and finding classification

The complete Pattern Pass is committed at
[`int-r3/pattern-pass.md`](int-r3/pattern-pass.md). It records `P01`–`P38`, including the `P35`
denominator/executor rule, `P36` finding IDs, `P37` predicate classification and `P38`
implementation/property divergent cases.

Every material finding is classified at
[`int-r3/finding-register.md`](int-r3/finding-register.md).

Contract-to-file coverage is committed at
[`int-r3/contract-coverage.md`](int-r3/contract-coverage.md).

## Final stage-1 statement

This package makes the premise testable and makes pre-build constraints available. It does not make
the premise true.

> Until `AuthorityUIComprehensionBenchmark` is run with real target operators against frozen actual
> surfaces, PolicyOS comprehension and actionability are `not_established`.

---
title: INT-R9 — First-Promotion State Machine and Artifact Contract Sketches
status: delivered
kind: deep-research-support
research_task: INT-R9
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r9-first-promotion-protocol
historical_repository_commit: 4813b49f6ce14e8debf3aaea096f0967d38d9768
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-02
authoritative_for:
  - research-level first-promotion workflow semantics
  - research sketches of typed custody artifacts for later consolidation
  - mapping of first-promotion workflow facts to the adopted Custody Time Model
  - prevention of a parallel status lattice or duplicate canonical owner
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical schema or package placement
  - canonical owner assignment
  - authority grant
  - capability claim
  - promise that a positive promotion is achievable
  - benchmark passage
  - legal compliance conclusion
research_only: true
---

# INT-R9 — First-Promotion State Machine and Artifact Contract Sketches

## 1. Standing and non-duplication rule

This file gives **research shapes**, not production types. A later consolidation and
implementation pass may reject, split, merge, or rename any shape. No symbol in this file
becomes canonical by being written here.

The repository already requires one truthful status surface rather than parallel status
truths (Organizing Rule 8), while `SearchTerminalKind`,
`PromotionObligationStatus`, and the N9 promotion receipt already carry canonical owner
semantics
([`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:145-230`](../../../system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md);
[`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:120-310`](../../../../src/polisyos/pdc/_impl/gy_waist.py);
[`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1-270`](../../../../src/polisyos/runtime/quality/promotion_sequence.py)).
Accordingly:

- the phases below are **custody-workflow facts**;
- they do not replace runtime terminal states, obligation statuses, confidence-ledger
  outcomes, or canonical publication/currentness states;
- a `promoted` workflow phase is admissible only when an existing canonical promotion
  owner has emitted a valid promotion receipt and all INT-R9 procedural predicates pass;
- an INT-R9 dispute can block or qualify a public claim, but it cannot turn a canonical
  refusal into promotion;
- Atlas may later project these facts through its one status surface; INT-R9 does not
  define that projection contract.

S0-GAP-02 owns the generic oracle/evaluator independence machinery—commitment, sealing,
access control, rotation, challenge, and inter-reviewer adjudication. These sketches refer
to that machinery instead of creating another one
([`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:75-210`](../consolidation/stage0/stage0-additional-research-register.md)).

## 2. State machine

### 2.1 State table

| Workflow state | Entry owner / evidence | Load-bearing clocks | Permitted exits | Expiry / escalation | Terminal meaning | Public meaning |
| --- | --- | --- | --- | --- | --- | --- |
| `pre_registration_drafted` | Protocol-author group; editable draft; no candidate access may occur. | Draft transaction time; authoring intervals. | `sealed`; `terminal_no_attempt`. | No automatic authority. A stale draft can be abandoned. | No. | Proposal only. It provides no anti-selection protection. |
| `sealed` | Independent custodian accepts signed commitments for protocol, finite attempt order, primary and adjacent case packages, expectation/evaluator packages, panel, conflicts, stopping, and publication rule. | `received_at`, `sealed_at`, independent transaction visibility, verified-at, purpose-scoped admission; latest permitted start/expiry. | `candidate_inspected`; `retired_before_inspection`; `disputed`; `terminal_no_attempt`. | Expiry is predeclared. A breach or unresolvable custody challenge enters `disputed`. | No. | The protocol is prospectively fixed, not passed. |
| `candidate_inspected` | Next committed primary input is revealed only after code, model/prompt, dependency, environment, configuration, registry, evaluator executable, and source-cutoff freeze. | First inspection time; input reveal; run start/end; source observation/validity/effective times; candidate-output freeze. | `adjudicated`; `void`; `disputed`. | No rollback to `sealed`. Incident containment may stop execution but cannot rescue the score. | No. | The slot is irrevocably in the attempt history and useful-design-rate denominator. |
| `adjudicated` | Named human panel signs raw votes after authorized expectation reveal; all owner receipts, falsifiers, adjacent result, deviations, and conflicts are in view. | Adjudicator receipt times; evaluator verification time; adjudication action time; public-record transaction time. | `promoted`; `refused`; `disputed`. | Missing quorum, material ambiguity, unresolved dissent, or challenge enters `disputed`. | No. | A completed evaluation exists; no positive public claim until final disposition. |
| `promoted` | Existing canonical promotion receipt plus all INT-R9 predicates; panel quorum; no material dissent; bounded public wording. | Promotion action time; publication transaction time; currentness/review-due time. | Append-only correction, suspension, withdrawal, supersession, or challenge; never in-place mutation. | Revalidation and challenge rules come from existing owners and later consolidation. | Yes for this slot and for the “first” sequence. | One bounded first governed promotion occurred under the named revision, environment, cases, assumptions, evaluator, and protocol. Nothing broader. |
| `refused` | Canonical owner refusal/unknown/blocker or any predeclared NO-GO; signed panel record. | Refusal action and publication times. | Next precommitted slot, if one remains; otherwise `exhausted_without_promotion`. | Challenge may append a dispute, but no silent re-score. | Yes for the slot. | No promotion from this slot. It does not prove promotion impossible. |
| `void` | Integrity/custody failure: leakage, wrong slot, post-reveal change, unverifiable freeze, or equivalent. | Incident observation, verification, and void action times. | Next precommitted slot, if one remains; otherwise `exhausted_without_promotion`. | Challenge is append-only. The chronological risk position and denominator entry remain. | Yes for the slot. | No substantive conclusion; the governed attempt failed its custody conditions. |
| `disputed` | Material challenge, unresolved dissent, criterion ambiguity, adjudicator conflict/unavailability without clean alternate, custody breach, or post-promotion challenge. | Challenge receipt, verification, escalation, and resolution times; response deadline. | Append-only resolution to `promoted`, `refused`, or continuing `disputed`, under the S0-GAP-02 challenge path. | While material dispute remains, current positive representation is prohibited. | Terminal-until-resolved. | No unqualified current promotion claim is permitted. |
| `retired_before_inspection` | Custodian proves no candidate input, answer, output, or outcome-relevant information was inspected; old version preserved with public diff. | Retirement receipt; proof interval ending before any reveal. | A new protocol version may be drafted and sealed. | Any contrary access evidence changes this to `disputed` or `void`. | Yes for the version. | The version was corrected prospectively; no scored attempt occurred. |
| `terminal_no_attempt` | Draft abandoned or sealed protocol expires without any candidate inspection. | Abandonment/expiry time. | None for the version. | A new version is a new record. | Yes. | No candidate was inspected and no result exists. |
| `exhausted_without_promotion` | Every precommitted slot is terminal without promotion. | Last-slot terminal and publication times. | None for the version. A later version requires fresh cases and prospective ratification. | No retrospective expansion or substitution. | Yes. | The finite program produced no promotion. This is a publishable primary outcome. |

### 2.2 Transition invariants

1. **Prospective-order invariant.** The seal's independently visible transaction time must
   precede the earliest candidate input disclosure, output-bearing execution, evaluator
   answer access, or human inspection. A self-authored timestamp is not sufficient.
2. **No erasure invariant.** Every attempted, void, refused, disputed, or promoted slot
   remains addressable. Later correction references the old record; it never overwrites it.
3. **No substitution invariant.** The evaluated case is the earliest unresolved slot in the
   committed order. A successful unregistered case is development evidence only.
4. **No best-run invariant.** The first result-bearing run under the frozen slot is the scored
   run. Retries caused by non-outcome-bearing infrastructure failure are admissible only if a
   predeclared deterministic retry rule and complete logs establish that no output or answer
   was exposed; otherwise the slot is void/disputed.
5. **One-status invariant.** Workflow phase, canonical runtime status, obligation outcomes,
   confidence-ledger state, and public currentness are linked but not collapsed.
6. **Dispute-blocking invariant.** A material unresolved dispute prevents an unqualified
   current positive representation.
7. **Earliest-qualified invariant.** If two candidates appear to qualify, “first” is determined
   by the precommitted slot order and canonical transaction order, never by comparative
   attractiveness.
8. **No retroactive amendment invariant.** A changed criterion, threshold, fixture
   interpretation, materiality rule, evaluator rule, or stopping rule cannot alter the scored
   disposition of a run already inspected.
9. **Cumulative-accounting invariant.** A void or failed attempt does not refund chronological
   execution ordinal or open a fresh confidence budget. The existing confidence-ledger owner
   remains authoritative for that accounting
   ([`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-230`](../../../../src/polisyos/runtime/quality/confidence_ledger.py)).
10. **Bounded-public-meaning invariant.** The public record names the implementation revision,
    environment, cases, evaluator, protocol, assumptions, limitations, and unresolved seams;
    it cannot imply legal compliance, institutional competence, production readiness, or
    population performance. This implements the bounded-passage direction of S0-K16
    ([`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:90-109`](../../../system-design-decisions/stage0-custody-kernel-ratification.md)).

### 2.3 Reopening after a positive result

“First” is historically irreversible, but the **justification is not immune to correction**.
If later evidence shows that the promotion was unjustified:

- retain the original promotion and its exact public wording;
- append the challenge, new evidence, verification, and owner decisions;
- use the existing canonical owner to suspend, withdraw, correct, or supersede the current
  claim;
- project the current truth without deleting the historical fact that a promotion was once
  issued;
- do not claim that the original event never occurred;
- do not reuse the corrected case as a fresh first-promotion holdout.

This follows the adopted custody model's separation of source, receipt, transaction,
verification, admission, and lifecycle-action time rather than pretending one timestamp can
carry every meaning
([`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:35-240`](../../../system-design-decisions/policy-design-custody-time-model.md)).

## 3. Custody Time Model mapping

The adopted Custody Time Model defines reusable roles, including source assertion/validity,
receipt, transaction visibility, verification, purpose-scoped admission, and
lifecycle/decision action. INT-R9 uses those roles; it does not create a competing time model
([`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:58-151`](../../../system-design-decisions/policy-design-custody-time-model.md)).

| First-promotion fact | CTM role | Required interpretation |
| --- | --- | --- |
| External case source says a legal instrument or observation applied during an interval. | R1/R2/R3/R4 as applicable | Source-native time remains distinct from PolicyOS receipt or inspection. |
| Custodian receives preregistration or sealed package. | R5 receipt | Proves receipt, not independent public existence or validity. |
| Commitment/record becomes independently visible in append-only custody. | R6 transaction visibility | The ordering fact needed to show sealing preceded inspection. |
| Custodian or verifier checks digest, signature, access log, build equality, or source snapshot. | R7 verification | A later verification does not backdate transaction visibility. |
| Protocol/case/evidence is admitted for the narrow first-promotion purpose. | R8 purpose-scoped admission | Admission for evaluation is not claim authority or legal admission. |
| Governance seals, run owner freezes, panel adjudicates, owner promotes/refuses, or public owner corrects. | R9 lifecycle/decision action | Each action has its own actor, rule version, and transaction time. |

### 3.1 Temporal proof required for prospective registration

At minimum, the following partial order must be machine-checkable and independently
verifiable:

```text
protocol_and_queue_received_at
  <= protocol_and_queue_transaction_visible_at
  <= protocol_and_queue_verified_at
  <= protocol_admitted_for_first_promotion_at
  < implementation_freeze_completed_at
  < primary_input_revealed_at
  <= candidate_first_inspected_at
  <= candidate_output_frozen_at
  < expectation_package_revealed_at
  <= adjudication_action_at
```

Where accuracy or clock uncertainty prevents strict ordering, the protocol cannot infer
prospectivity. RFC 3161 is one possible proof-of-existence building block, not a required
implementation: it supports evidence that a datum existed before a time and distinguishes
policy, accuracy, nonce, and ordering properties. Choice of timestamping and commitment
mechanism belongs to S0-GAP-02, not INT-R9.

## 4. Common artifact envelope

Every sketched artifact below carries the following research-level fields. They are repeated
conceptually rather than proposed as a universal production envelope.

```yaml
artifact_identity:
  artifact_id: opaque durable identifier
  artifact_kind: one of the research shapes below
  schema_version: exact research/implemented schema ref
  created_by: accountable actor or service identity
  created_at: lifecycle/decision action time
custody:
  received_at: optional R5
  transaction_visible_at: required R6 for scored records
  verified_at: optional/repeatable R7 receipts
  admitted_at: optional R8 plus purpose and authority owner
  commitment_receipts: []
  signatures: []
  access_log_ref: optional
versioning:
  protocol_version: exact
  rule_refs: []
  evaluator_version: optional
  repository_commit: exact
  implementation_tree_hash: optional
provenance:
  producer_refs: []
  input_artifact_refs: []
  source_snapshot_refs: []
  transformation_refs: []
scope:
  purpose: exact
  jurisdiction: optional
  population_or_case_scope: exact
  maintained_assumptions: []
  uncertainty_and_unknowns: []
audience:
  intended_audiences: [governance, expert, machine, public]
  redaction_or_disclosure_refs: []
authority_boundary:
  authoritative_for: []
  may_not_use_for: []
correction:
  corrects: []
  supersedes: []
  withdrawn_by: []
  challenge_refs: []
```

A later implementation should reuse existing provenance, time, status, signature, and
publication primitives where they fit. Repetition here is descriptive; it is not a proposal
for one universal event envelope.

## 5. Typed artifact sketches

### 5.1 `FirstPromotionPreRegistration`

```yaml
FirstPromotionPreRegistration:
  identity:
    preregistration_id: string
    protocol_id: string
    protocol_version: string
  freeze_basis:
    repository_commit: sha
    implementation_tree_hash: digest
    build_and_dependency_refs: [digest]
    environment_ref: digest
    model_prompt_configuration_refs: [digest]
    evaluator_executable_commitment: CommitmentRef
  selection:
    eligible_population_definition: text
    excluded_population:
      - case_or_class_ref: string
        reason_code: string
        evidence_refs: [ArtifactRef]
    contamination_census_ref: ArtifactRef
    attempt_queue:
      - slot_number: positive_integer
        opaque_primary_commitment: CommitmentRef
        opaque_adjacent_commitment: CommitmentRef
        declared_stratum: string
    stopping_rule: exact rule/version
    substitution_rule: forbidden
  criteria:
    existing_owner_predicate_refs: [RuleRef]
    procedural_predicates: [RuleRef]
    threshold_refs: [RuleRef]
    materiality_rule_ref: RuleRef
    ambiguity_rule_ref: RuleRef
    deviation_rule_ref: RuleRef
    no_go_reason_refs: [RuleRef]
  people:
    criteria_authors: [AccountableIdentity]
    case_authors: [AccountableIdentity]
    implementation_authors: [AccountableIdentity]
    panel: [AccountableIdentity]
    alternates: [AccountableIdentity]
    custodian: AccountableIdentity
    conflicts_and_independence_assessments: [SignedAssessment]
  publication:
    public_regression_plan_ref: ArtifactRef
    result_independent_publication_commitment: SignedCommitment
    raw_vote_and_dissent_rule_ref: RuleRef
  time_and_custody:
    drafted_at: instant
    received_at: instant
    transaction_visible_at: instant
    verified_at: instant
    admitted_at: instant
    first_inspection_not_before: instant
    expiry_or_review_due_at: instant
    commitment_receipts: [ReceiptRef]
  authority_boundary:
    authoritative_for:
      - exact prospective protocol, queue, criteria, and publication commitment
    may_not_use_for:
      - proof that any case will qualify
      - benchmark passage
      - production readiness
      - legal compliance
      - authority grant
```

**Admission rule:** the record is admissible for a scored attempt only when the custodian can
prove the temporal ordering in §3.1 and all required people/conflict/custody fields are
complete. A draft in git after a candidate was seen is not a preregistration.

### 5.2 `FirstPromotionAttemptRecord`

```yaml
FirstPromotionAttemptRecord:
  attempt_id: string
  preregistration_ref: ArtifactRef
  slot_number: positive_integer
  chronology:
    primary_input_revealed_at: instant
    candidate_first_inspected_at: instant
    run_started_at: instant
    run_completed_at: instant_or_null
    candidate_output_frozen_at: instant_or_null
    expectation_revealed_at: instant_or_null
  identity_and_freeze:
    primary_case_reveal_receipt: ReceiptRef
    adjacent_case_reveal_receipt: ReceiptRef_or_null
    implementation_freeze_receipt: ReceiptRef
    source_snapshot_refs: [ArtifactRef]
    evaluator_executable_ref: ArtifactRef
    risk_scope_and_execution_ordinal_ref: ArtifactRef
  owner_results:
    canonical_promotion_receipt_ref: ArtifactRef_or_null
    obligation_outcome_refs: [ArtifactRef]
    confidence_ledger_refs: [ArtifactRef]
    firewall_ref: ArtifactRef
  integrity:
    public_regression_ref: ArtifactRef
    no_case_specific_code_evidence_refs: [ArtifactRef]
    deviations: [DeviationRef]
    incidents: [IncidentRef]
  terminal_kind:
    workflow_phase: candidate_inspected|void|ready_for_adjudication
    canonical_status_refs: [ArtifactRef]
  authority_boundary:
    authoritative_for:
      - chronological fact that this committed slot was or was not executed under the named freeze
    may_not_use_for:
      - promotion without adjudication
      - deletion or refund of a failed or void slot
```

### 5.3 `FirstPromotionAdjudicationRecord`

```yaml
FirstPromotionAdjudicationRecord:
  adjudication_id: string
  attempt_ref: ArtifactRef
  evaluator:
    evaluator_version: string
    expectation_commitment_and_reveal_receipts: [ReceiptRef]
    raw_evaluator_output_ref: ArtifactRef
    admissible_alternative_outcomes_ref: ArtifactRef
  falsifiers:
    source_flip_result_ref: ArtifactRef
    obligation_removal_result_ref: ArtifactRef
    opaque_identity_result_ref: ArtifactRef
    wrong_scope_result_ref: ArtifactRef
    adjacent_case_result_ref: ArtifactRef
  panel:
    member_assessments:
      - identity: AccountableIdentity
        signed_vote: approve|refuse|dispute|abstain
        criterion_findings: [Finding]
        conflicts_reconfirmed_at: instant
        reasons: text
    calibration_ref: ArtifactRef
    unresolved_material_dissent: boolean
  deviations_and_no_go:
    deviation_refs: [DeviationRef]
    no_go_findings: [Finding]
  disposition:
    procedural_disposition: promoted|refused|disputed|void
    canonical_promotion_receipt_ref: ArtifactRef_or_null
    bounded_external_validity_statement: text
    current_public_claim_permitted: boolean
  authority_boundary:
    authoritative_for:
      - signed procedural adjudication under the named protocol and evaluator
    may_not_use_for:
      - population-level generalization
      - correctness of the external oracle beyond declared assumptions
      - legal or institutional authority
```

A panel majority is not enough when a material dispute remains. The structured protocol
requires at least two approvals, no dispute vote, no unresolved material dissent, and a reason
for every abstention. Agreement coefficients may be reported, but they do not establish
oracle correctness.

### 5.4 `FirstPromotionDeviationRecord`

```yaml
FirstPromotionDeviationRecord:
  deviation_id: string
  preregistration_ref: ArtifactRef
  attempt_ref: ArtifactRef_or_null
  observed_at: instant
  verified_at: instant
  actor_or_detector: AccountableIdentity
  affected_rule_refs: [RuleRef]
  category: administrative|substantive|custody|integrity|oracle|environment|unknown
  description: text
  outcome_relevant_information_seen_before_deviation: boolean|unknown
  materiality_assessment:
    assessor: AccountableIdentity
    result: immaterial|material|unknown|disputed
    reasons: text
  treatment:
    - retain_original_scoring
    - void_attempt
    - dispute_attempt
    - retire_before_inspection
    - amend_only_future_protocol_version
  public_disclosure_ref: ArtifactRef
  authority_boundary:
    authoritative_for:
      - existence and treatment of a deviation
    may_not_use_for:
      - post hoc rescue of a favorable result
      - erasure of the original rule or run
```

### 5.5 `FirstPromotionChallengeResolution`

```yaml
FirstPromotionChallengeResolution:
  challenge_id: string
  challenged_artifact_refs: [ArtifactRef]
  received_at: instant
  transaction_visible_at: instant
  challenger_scope_and_disclosure: text
  allegations_or_questions: [Finding]
  evidence_refs: [ArtifactRef]
  independent_resolver_refs: [AccountableIdentity]
  response_deadline: instant
  interim_public_posture: disputed|suspended|unchanged_with_reason
  resolution:
    decided_at: instant_or_null
    result: upheld|refused|corrected|superseded|withdrawn|unresolved
    reasons: text
    canonical_owner_action_refs: [ArtifactRef]
  authority_boundary:
    authoritative_for:
      - challenge custody and its resolution under the named process
    may_not_use_for:
      - minting a new runtime status
      - bypassing canonical correction or withdrawal owners
```

### 5.6 `FirstPromotionPublicRecord`

```yaml
FirstPromotionPublicRecord:
  public_record_id: string
  protocol_and_attempt_refs: [ArtifactRef]
  terminal_disposition: promoted|refused|void|disputed|exhausted_without_promotion|terminal_no_attempt
  canonical_status_and_owner_receipt_refs: [ArtifactRef]
  plain_language_summary: text
  bounded_claim:
    implementation_revision: string
    environment: string
    primary_and_adjacent_case_scope: [string]
    evaluator_and_protocol_versions: [string]
    maintained_assumptions: [string]
    known_unknowns: [string]
    external_validity_boundary: text
  negative_result_fields:
    no_go_reasons: [string]
    blockers_or_unknowns: [string]
    next_precommitted_slot_ref: ArtifactRef_or_null
  dissent_and_deviation_refs: [ArtifactRef]
  useful_design_rate_reporting:
    numerator: integer
    denominator: integer
    denominator_definition_ref: RuleRef
    never_targeted_attestation: SignedAssessment
  currentness:
    published_at: instant
    current_as_of_transaction_time: instant
    review_due_at: instant_or_null
    challenge_refs: [ArtifactRef]
    corrected_or_superseded_by: [ArtifactRef]
  authority_boundary:
    authoritative_for:
      - bounded public account of the named first-promotion protocol outcome
    may_not_use_for:
      - legal compliance
      - production readiness
      - domain or population performance
      - proof that a positive promotion exists outside this record
```

## 6. Canonical-owner map

This map identifies **reuse candidates and consumers**, never new canonical ownership.

| Concern | Existing or commissioned owner to reuse | INT-R9 relationship | Evidence |
| --- | --- | --- | --- |
| Runtime promotion sequence and obligation ordering | GY N9 / `promotion_sequence.py` and waist contracts | Consume exact receipt and owner statuses; do not redefine checks, obligations, denominators, or thresholds. | [`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:1-270`](../../../../src/polisyos/runtime/quality/promotion_sequence.py); [`policy-engine/src/polisyos/pdc/_impl/gy_waist.py:120-310`](../../../../src/polisyos/pdc/_impl/gy_waist.py) |
| False-promotion risk scope, predictable allocation, e-process receipts | Confidence-ledger / GY N11 | Consume chronological ordinal and maintained assumptions; never create a parallel alpha budget. | [`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-230`](../../../../src/polisyos/runtime/quality/confidence_ledger.py); [`policy-engine/architecture/production_quality/confidence_ledger.toml:1-232`](../../../../architecture/production_quality/confidence_ledger.toml) |
| Candidate-shadow firewall | `candidate_firewall.py` and canonical protected owners | Require a valid firewall result; no B-output backfill of protected authority. | [`policy-engine/src/polisyos/runtime/quality/candidate_firewall.py:1-260`](../../../../src/polisyos/runtime/quality/candidate_firewall.py) |
| Sealed oracle/evaluator custody, access, rotation, challenge | S0-GAP-02 | Reuse wholesale unless consolidation identifies a first-event-specific delta. | [`policy-engine/docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md:75-210`](../consolidation/stage0/stage0-additional-research-register.md) |
| Bounded completeness of obligation set | INT-R1 | Consume a versioned declaration; weak output narrows or blocks. | Parallel task seam; no INT-R9 substitute. |
| Institutional competence/delegation evidence | INT-R5 and ratified identity boundary | Consume for panel/evidence-producer eligibility; do not certify competence here. | [`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:35-220`](../../../system-design-decisions/policyos-identity-and-custody-boundary.md) |
| Public projection/currentness/challenge | Atlas DS12 and INT-R8 consolidation | Project every positive and negative outcome without inventing new status truth. | [`policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1000-1280`](../../../plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md) |
| Custody-time roles and correction ordering | Adopted Custody Time Model | Reuse R1–R9 and relation semantics. | [`policy-engine/docs/system-design-decisions/policy-design-custody-time-model.md:35-240`](../../../system-design-decisions/policy-design-custody-time-model.md) |

## 7. State-machine edge cases

### 7.1 Registered case fails; unregistered case succeeds

The registered slot is `refused`. The unregistered success is retained as exploratory or
development evidence but cannot become the first governed promotion. Substitution would make
case selection depend on outcome.

### 7.2 Adjudicator unavailable mid-adjudication

Use only the predeclared alternate whose custody record shows no prohibited access and whose
conflicts remain acceptable. Otherwise enter `disputed`. Selecting a new favorable reviewer
after seeing votes is forbidden.

### 7.3 Criterion ambiguous after sealing

The panel records the ambiguity and enters `disputed` if material. It cannot silently select
the interpretation that yields promotion. A clarified criterion applies only to a new
prospective protocol version and fresh cases.

### 7.4 Holdout leak

The slot becomes `void` or `disputed` according to the predeclared incident rule. It remains in
chronology, denominator, and risk accounting. A replacement is never inserted into the same
slot.

### 7.5 Promotion later found unjustified

Append a challenge and canonical suspension/correction/withdrawal/supersession. Preserve the
original record. The current public surface must show the new posture and the historical
sequence.

### 7.6 Two candidates qualify simultaneously

The earlier committed slot and canonical transaction order determine firstness. Comparative
quality does not permit selection.

### 7.7 Preregistration mis-specified before any result is seen

The custodian may mark the version `retired_before_inspection` only with affirmative evidence
that no input, answer, output, or outcome-relevant information was accessed. Publish the old
version and diff, then seal a new version. Uncertainty about access is a dispute, not proof of
clean correction.

### 7.8 Hand-coded binding from three slices ago

Contributor departure does not cleanse the binding. Its provenance makes the case
implementation-conditioned and triggers the no-case-specific-code NO-GO. Literal case-ID
absence is irrelevant if source fingerprints, aliases, or semantic bindings perform the same
function.

## 8. Verification checklist for a later implementation

A later implementation review should be able to answer, with artifact references rather than
prose assertions:

1. Which exact protocol and queue were independently visible before first inspection?
2. Which clocks and accuracy bounds establish that order?
3. Which source, code, build, dependency, model, prompt, configuration, adapter, registry,
   evaluator, and query cutoffs were frozen?
4. Which slot was next, and were all earlier slots retained?
5. Which existing canonical owner receipts were consumed without redefinition?
6. Which confidence-ledger scope, head, ordinal, allocation, and maintained assumptions apply?
7. Who authored the case, criteria, implementation, and answer key; who had access; and when?
8. Which named humans adjudicated; what were their conflicts, raw votes, abstentions, and
   dissent?
9. Did source-flip and obligation-removal change the authority outcome as predeclared?
10. Was the adjacent case run with the same frozen implementation and configuration?
11. What evidence rules out case-specific code or old hand-written bindings?
12. Were deviations retained and scored under the original protocol?
13. Is refusal/no-promotion published with the same durability and career visibility as
    promotion?
14. Does the public record stay within the bounded external-validity statement?
15. If corrected later, can an auditor reconstruct both the historical promotion and current
    posture?

An inability to answer any promotion-critical item is not an invitation to infer a convenient
value. It is a typed unknown, refusal, void, or dispute under the applicable existing owner.

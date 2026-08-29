---
title: INT-R2 — Gap Acquisition Cases For Non-Data Objects
status: stage_1_research_delivered
kind: deep-research
research_task: INT-R2
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r2-research
repository_base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
authoritative_for:
  - research-level candidate semantics for classifying and acquiring eight non-data gap objects
  - research-level authority-ceiling, re-entry and deeper-terminal tests
  - later consolidation and ratification input for the missing knowledge/grounding acquisition plane
may_not_use_for:
  - capability claim
  - canonical owner appointment
  - institutional signer appointment
  - production admission
  - authority grant
  - public-signature release
  - final runtime or wire contract
research_only: true
---

# INT-R2 — Gap Acquisition Cases For Non-Data Objects

## 1. Task And Project Fit

### 1.1 Exact question and research boundary

INT-R2 asks how PolicyOS should model acquisition of eight things that are not interchangeable with
additional data rows: a grounding relation, an estimand binding, owner writability, a legal mandate,
a normative authorization, implementation-capacity evidence, a competent human decision and an
independent audit.

The result is a research-level candidate `GapAcquisitionCase` discriminated union. Every branch
answers six questions independently:

1. who may produce the object;
2. what counts as sufficient acquisition;
3. what admission proof is required;
4. what checkable authority ceiling results;
5. how the original demanding gate re-enters; and
6. what `deeper_terminal` means for that branch.

This is research-first because every answer defines a predicate a later authority gate might turn on.
Writing a convenient schema before producer standing, sufficiency, proof and ceiling are understood
would convert an unresolved premise into a positive-eligible gate. Stage 1 therefore specifies
candidate semantics and falsifiers. It does not create the runtime capability, appoint a canonical
owner or appoint any institutional signer.

The adversarial invariant is exact:

```text
for case_type in {grounding_relation, estimand_binding, legal_mandate}:
    add any number of rows to the current data stream
    while the required non-data acquisition object remains absent
    => the case remains unclosed
```

A new experiment or measurement regime can contribute to relation acquisition, and a mandate can
contain factual conditions. The invariant does not make evidence irrelevant. It requires the system
to name the new evidence regime or authority artifact and prove that it changes the blocked predicate;
`row_count increased` is never a universal closure operator.

### 1.2 False production claims prevented

The union prevents five recurrent false claims:

- **row-count closure:** more observations establish a relation, choose an estimand or create a
  mandate;
- **document-by-presence closure:** a signed letter, approval, checklist or report is accepted without
  resolving issuer competence, scope, work performed and current validity;
- **authority-ceiling theatre:** “limited authority” is recorded but no consumer can test the action,
  object, population, jurisdiction, purpose, time or maximum claim strength permitted;
- **terminal-as-progress:** a better characterised negative result is rendered as “almost approved”;
- **borrowed institution:** external practice is copied while silently assuming an adjudicator,
  register owner, competent decision-maker or independent provider that PolicyOS does not have.

### 1.3 Four-way identity-boundary verdict

The ratified identity makes PolicyOS the custodian of claims it signs, not the institution that
performs legislation, ethical adjudication, professional licensing, register adjudication, audit or
service delivery (`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:55-112`).

| Plane | Verdict | Consequence |
| --- | --- | --- |
| Typed demand, classification, evidence intake, ceiling enforcement, re-entry and claim reaction | **OWN** | Their absence can make PolicyOS’s own published claim silently false. |
| Mandates, consent/ethics decisions, canonical write grants, professional decisions, assurance and capacity assessment | **INTEGRATE** | PolicyOS owns the fail-closed contract and verification; the external institution owns the act. |
| Issuer succession, revocation, professional standing, assurance relationships and institutional changes | **OBSERVE** | These events can stale or reopen PolicyOS claims; PolicyOS does not administer the institution. |
| Performing the external institutional function | **OUT_OF_SCOPE** | Scarcity does not transfer the function to PolicyOS. Missing partners remain typed blockers. |

The commission says the package turns a route to a missing plane into an owner. Stage-1 authority
narrows that phrase: this report makes the candidate ownership boundary and integration contract
specifiable. Only later consolidation/ratification can appoint a canonical owner.

### 1.4 Project fit and standing

INT-R2 is the stand-alone “+1” in Wave 8. It consumes N13a/N13b residual evidence and may later inform
GY Phase 6 / O1/O3, but it is not part of the declared `INT-R4` ‖ `OPS-R5` pair.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The research result is suitable for independent audit and consolidation. The capability remains
absent because no admitted producer→artifact→bridge→consumer→verification→surface chain and no
appointed institutional producer exist. The public/production gate remains closed.

## 2. Current Repo Baseline

The detailed coordinate and measurement ledger is
`docs/research/policy-operations/int-r2/repo-baseline-and-source-ledger.md`.

> **Headline:** the repository has a strong, content-bound data-acquisition path and several
> purpose-scoped authority fragments, but no generic `GapAcquisitionCase` owner, residual-shape
> classifier, eight-type producer/admission chain or complete authority-ceiling evaluator.

### 2.1 Mandatory inspection set

The pinned study at `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` inspected:

- `AGENTS.md` and `policy-engine/CONTRIBUTING.md`;
- the identity ruling and required architecture documents:
  `policyos-identity-and-custody-boundary.md`,
  `universal-policy-design-system-vision-and-organizing-rules.md`,
  `universal-policy-design-target-architecture-and-gap.md`,
  `policy-design-best-in-class-operating-model.md`, `honest-diagnostics-substrate.md` and
  `policy-design-causal-operating-system-north-star.md`;
- the failure-pattern register, active GY and Atlas plans, and
  `deep-research-value-distillation.md`;
- N13a census and N13b planner, acquisition authority, passport/overlay and re-entry owners;
- CG3/CG5 grounding hooks, typed refusal service and human-decision seed.

The architecture converges on four controlling rules: generators produce candidates; external power
enters through the narrow waist; projections cannot mint authority; and a prose contract remains
`absent/unallocated` until the complete capability chain exists.

### 2.2 Refusal vocabulary and path-forward coverage

| Owner | What exists | INT-R2 limit |
| --- | --- | --- |
| PDC waist, `src/polisyos/pdc/_impl/gy_waist.py:218-255` | Coarse obligation/refusal outcomes such as `single_obligation_fail`, `proof_timeout`, `scope_insufficient`, `unknown`. | Gate posture is typed; missing acquisition object is not. |
| Authority-value service, `runtime/http/services/authority_values.py:1-150` | Real `refused | supplied` union and codes including `no_runtime_producer` and `owned_by_another_surface`. | Only some codes name a route; a first-class refusal may still be bare. |
| Acquisition planner, `runtime/quality/acquisition_planner.py:1-360` | Typed gaps, eligible strategies, authority levels, mandatory-gate state and dispositions. | Planner output routes work and explicitly does not satisfy the domain slot. |
| N13b re-entry, `tools/quality/validation/layer3_gy_n13b_reentry.py:1-210` | Closure versus two data-specific `deeper_terminal_*` outcomes. | Closure is dataset/binding/observation growth. |
| CG3/CG5, `grounding_admission.py:1-360`; `grounding_active_controller.py:1-300` | Typed blockers, acquisition need and bounded next actions. | CG5 is a router and explicitly cannot close obligations or mark resolution. |

A typed refusal is therefore not automatically a complete refusal-with-a-path. It may identify what
failed without establishing producer, proof, ceiling or re-entry.

### 2.3 The worked data-acquisition path

The existing exemplar is:

```text
typed requirement gap
→ eligible acquisition strategy
→ source/journal/CAS result
→ owner, rights, licence and trust re-resolution
→ content-bound admission passport
→ admitted/degraded/quarantined observation
→ separate overlay epoch
→ demanding-stage before/after availability recheck
→ closure only on real owner-visible growth, else stronger refusal
```

Its discipline is reusable: typed demand, eligible producer, content-bound proof, purpose-scoped
admission, bounded authority, owner-gated re-entry and replayable terminal.

Its storage/closure assumptions are not reusable:

```text
acquired object = observation row
admission = data passport
persistence = data overlay epoch
closure = dataset/binding/observation count increased
```

A relation, estimand, mandate, competent decision or audit cannot truthfully close by being forced
into those four shapes. The current grounding bridge still carries `data_requirement`/`routing_only`
semantics, demonstrating the exact data-gap gravity this task must prevent.

### 2.4 Authority fragments and the missing aggregate ceiling

The repository already has `authoritative_for`, `may_not_use_for`, authority levels, mandatory-gate
posture, content-bound passports, quarantine/non-admission, P37’s `not_established`, the
`absent/unallocated` capability label and specialised scope/time/provenance fields.

It does not have one owner-computed, cross-type predicate equivalent to:

```text
requested_use ∈ admitted_artifact.authority_ceiling
```

where the ceiling binds action/claim, subject/object, population, jurisdiction, purpose/audience,
effective/review windows, assumptions/evidence class, maximum claim strength or commitment stage,
permitted operations and prohibited downstream uses.

**Nothing in the pinned repository can express and enforce a complete generic ceiling for all eight
case types today.** Existing fragments are reusable; the aggregate evaluator and its registered
cross-type vocabulary are `absent/unallocated`.

### 2.5 CG5, the routed residual and the 15-row census

`GY-engine-subordination.md:2410-2495` records that N13b converted none of the 15 residuals into world
growth and that three capstone `not_a_data_gap` routes were sent to a future knowledge/grounding
acquisition plane — “CG5-class relation/lever acquisition + estimand evidence” — outside N13b.

The committed N13a census contains a complete 15-row ranked `growth_backlog`; every row says
`gap_kind: binding_gap`. It also contains three capstone route-evidence rows. The later measurement
supplied by the commission says one row was established data-shaped and 14 remained
`shape: not_established`. Holder standing is explicit:

- the pinned 15-row and three-route collections were read from their owner artifact and are
  `recomputed` here;
- the later `1 / 14` partition is `institutionally_supplied` because its executing slice is not in the
  pinned tree;
- the supplied zero structural classifications is not a settled zero for this holder under W4-K01/P35.
  The safe result is `structural classification not established here`.

`binding_gap` is not a discriminator. For each of the 14, classification requires the exact demanding
gate, minimal missing object, same-stream row-invariance test, competent producer, ruled-out
neighbouring types and `split_required` where several objects are independently missing. Unknown shape
must never default to data.

The three capstones narrow as follows:

| Route | Candidate disposition |
| --- | --- |
| `education`: `method_estimand_binding_mismatch` | `estimand_binding`; identification/data gaps may coexist but do not replace target binding. |
| `first_vertical`: `grounding_relation_or_owner_lever:gy_n4.emergency_tax_relief` | `grounding_relation`, `owner_writability`, or an ordered two-case sequence if both are absent. |
| `unseen`: `grounding_relation_or_owner_lever:candidate_fallback_1950390310ca54cb` | Same disjunction and split rule. |

The disjunction is not a ninth hybrid type. It proves that classification must precede case creation.

### 2.6 Reuse-first path and current capability labels

A later implementation should extend the canonical acquisition planner’s demand/routing boundary,
add a pre-union classifier, reuse CAS/provenance/quarantine/epoch/re-entry disciplines, extend existing
domain owners rather than duplicate them, and have every demanding gate re-resolve and enforce the
admitted ceiling. Atlas should render the one existing status lattice, not a parallel one.

| Slice | Current label |
| --- | --- |
| Generic union, residual classifier, generic ceiling evaluator, institutional producer set and multi-type re-entry bridges | `absent/unallocated` |
| Adversarial semantic fixture pack | `semantic_test_missing` |

Research blockers, engineering blockers and institutional blockers are separate. None is repaired by
adding rows to the observation overlay.

## 3. External Research Baseline

Five commissioned surveys were read as external practice, never as repository authority. Their full
source/limitation ledger is in the `int-r2/` support file.

### 3.1 Kinds of not-knowing and closure operators

The first survey rejects a scalar “uncertainty is high” test. It distinguishes:

- sampling/imprecision, where more relevant observations may help;
- target/estimand definition, where data cannot choose the question;
- non-identifiability, where distinct admissible worlds yield the same observables but different
  targets;
- directness/support/design mismatch, where more of the same stream does not repair the channel;
- authority, where facts do not create permission.

Its strongest operational result is conditional: no amount of observations **from the stated evidence
regime, for the stated target/model/assumptions** closes a non-identifiability certificate. Structural
is not metaphysical. A new intervention, measurement, assumption or authority change may reopen the
case.

The survey’s closest analogues for a deepened refusal are a non-identifiability certificate, an
identified set, `UNSAT` with an unsat core and a reasoned adverse determination. They disagree about
what “terminal” means; causal impossibility and administrative exhaustion must not be collapsed.

### 3.2 Causal relation versus estimand binding

The second survey establishes a non-substitution:

```text
relation acquisition = authority to state something about causal structure
estimand binding = authority to state which quantity is the target
```

Neither entails the other. Relation practice ranges from structured elicitation through mechanistic,
observational, experimental and institution-specific integrated adjudication. There is no universally
calibrated threshold that turns an arbitrary evidence portfolio into `causal relation established`.
Domain procedures such as IARC supply local categories and procedures, not a universal policy rule.

Estimand practice is more formal. A sufficient semantic target specifies treatment/regime, population,
outcome and horizon, handling of intercurrent events and population-level contrast. That still does not
prove identification or estimator alignment:

```text
BOUND != IDENTIFIED != ESTIMABLE != ESTIMATED
```

A target-trial or protocol-like artifact is useful because it binds the question before the estimator,
but observational emulation does not become randomisation and transportability must be rechecked.

### 3.3 Legal mandate, normative authorization and owner writability

The third survey rejects a single `authorized=true`. It identifies three different chains:

- **legal mandate:** the governing order gave this actor competence for this action;
- **normative authorization:** the required ethical/personal/institutional sanction exists;
- **owner writability:** the canonical truth/change owner authorised this mutation and the technical
  identity can execute it.

Their shared abstract form is:

```text
source of competence
→ issuer competence
→ grant/determination
→ recipient identity
→ scope
→ current validity
→ evidence of this use
```

But the source of power, issuer, proof, ceiling and terminal differ. A data-sharing agreement does not
create underlying legal power. IRB approval does not necessarily equal institutional permission. An
API role proves technical capability, not substantive write authority. A verifiable credential proves
issuer assertion and integrity, not issuer competence or truth.

The survey also preserves a material disagreement: social licence often lacks one issuer, threshold,
credential or expiry. It should not be fabricated into an ordinary authorization token. Where no
governing regime defines a competent producer and proof, the predicate stays `not_established`.

### 3.4 Competent decision versus independent audit

The fourth survey supplies a common reconstructability discipline but different objects.

A competent decision requires an identified person with standing at the decision time, role authority,
domain competence, case-specific task scope, access to the material, actual exercise of judgment,
handling of contrary evidence/uncertainty and a reconstructable attributable record. A signature alone
is binding proof of authorship/version, not proof of the intellectual work.

Independent assurance adds a relational requirement. Independence is not a permanent person flag; it
must be evaluated over reviewer, subject, funding, fees, appointment/removal, prior work, employment,
network and pressure. A competent external person can still be non-independent; an independent person
can still perform insufficient work. Assurance level, subject, criteria, period, scope and exclusions
bound the resulting authority. Agreed-upon procedures are not automatically limited assurance.

No competent person/provider is `unavailable`, not an adverse conclusion about the subject. Internal
review does not become independent because an independent provider is scarce.

### 3.5 Implementation-capacity evidence

The fifth survey treats capacity as evidence about a **specific delivery system**: people, suppliers,
technology, process, budget, dependencies, load, timeframe, reach, fidelity and quality. It is not legal
authority, causal effectiveness or a general state-capacity score.

The strongest practical regimes are stage-gated. First-line owners supply evidence; material or
irreversible commitments need independent challenge. Sufficiency is weakest-link: every critical
prerequisite must pass a stage-specific threshold. A composite maturity score cannot average away a
missing supplier, absent staff or untested throughput.

The ceiling is the next bounded commitment demonstrated by the evidence — feasibility work, pilot,
limited tranche, next load band — not a guarantee of success or automatic national rollout. Readiness
frameworks and delivery-confidence ratings are useful but not mature calibrated probability models.
A genuine terminal is horizon-relative: no credible build/maturation path, no narrower valuable stage
and no feasible alternative delivery channel within the decision horizon.

### 3.6 Preserved disagreements and adopted confidence

| Issue | Survey variation retained | INT-R2 treatment |
| --- | --- | --- |
| Universal uncertainty taxonomy | None exists. | Use closure-object classification, not an “uncertainty type” enum. |
| Causal sufficiency | Domain procedures differ and no universal threshold is calibrated. | Preserve acquisition mode/evidence class; cap language; mark universal threshold `deferred_open_problem`. |
| Social licence | Important legitimacy condition, usually no issuer/token. | Do not invent issuer; use normative case only where a governing regime supplies producer/proof. |
| Professional standing | Raises process warrant but does not prove truth. | Require work record and scope; do not let credential alone close. |
| Independence safeguards | Check known channels but do not scientifically prove independence of mind. | Require relationship evidence and bounded claim; never infer from `external=true`. |
| Capacity ratings | Stage-gating is mature; probability calibration is weak. | Authorise only next demonstrated commitment; never emit pseudo-probability. |

All adopted external findings are `surveyed_external_practice`. They establish possible mechanisms and
limits, not capability or authority in this repository.

## 4. Result

### 4.1 Scope of the union and non-exhaustiveness

The candidate union is exhaustive over the **eight acquisition objects commissioned by INT-R2**. It
is not claimed exhaustive over all possible non-data gaps. Unknown unknowns, value-choice formation,
political settlement, new kinds of institutional act and compound gaps may fall outside it. A residual
that cannot be classified therefore remains `not_established`; the union does not coerce it into the
nearest branch.

Research sketch:

```text
GapAcquisitionCase = discriminated_union(case_type):
    grounding_relation
    estimand_binding
    owner_writability
    legal_mandate
    normative_authorization
    implementation_capacity_evidence
    competent_human_decision
    independent_audit
```

The discriminator denotes the **object whose acquisition the demanding gate requires**, not the
profession involved, the document format, the acquisition action or the current refusal code.

### 4.2 Classification before case construction

A separate `GapShapeAssessment` is required before the union. It is not a ninth branch and does not
replace the Atlas status lattice.

```yaml
GapShapeAssessment:
  residual_ref: string
  demanding_gate_ref: string
  blocked_predicate: string
  minimal_missing_object: string | null
  current_evidence_regime_ref: string
  same_stream_data_effect: can_change | cannot_change | not_established
  candidate_case_types: [GapAcquisitionCaseType]
  ruled_out_case_types:
    - case_type: GapAcquisitionCaseType
      evidence_refs: [string]
  predicate_provenance:
    label: recomputed | independently_reconciled | consumer_asserted |
           institutionally_supplied | not_established
    source_refs: [string]
  classification_outcome: data_gap | one_case | split_required | not_established
  ordered_case_types: [GapAcquisitionCaseType]
  rule_version_ref: string
```

Rules:

1. `binding_gap` alone yields `not_established`.
2. `same_stream_data_effect=can_change` does not by itself prove an ordinary data gap; the exact
   missing object and demanding predicate still bind the decision.
3. `same_stream_data_effect=cannot_change` rules out row-only closure but does not select among the
   eight non-data branches.
4. A positive branch selection requires `recomputed` or `independently_reconciled` producer/shape
   predicates. `consumer_asserted`, `institutionally_supplied` or `not_established` fail closed.
5. Multiple independently required objects produce ordered cases, not a hybrid type.

This classifier is the required treatment of the fourteen `shape:not_established` residuals. The
later `1 data-shaped / 14 not_established` measurement cannot be converted into 14 guessed union
members. Each needs the evidence listed in §2.5.

### 4.3 Common case envelope

All branches share identity, provenance and gate-binding fields, but not sufficiency or ceiling
semantics:

```yaml
GapAcquisitionCaseCommon:
  schema_version: string
  case_id: string
  case_type: discriminator
  residual_ref: string
  shape_assessment_ref: string
  demanding_gate_ref: string
  blocked_claim_refs: [string]
  blocked_action_refs: [string]
  source_refusal_refs: [string]
  required_object_identity: object
  eligible_producer_requirement: object
  sufficiency_predicate_ref: string
  admission_proof_requirement: object
  admitted_artifact_refs: [string]
  authority_ceiling: AuthorityCeiling
  reentry_contract: ReentryContract
  terminal_record: TerminalRecord | null
  provenance_refs: [string]
  rule_version_ref: string
  valid_time: object
  transaction_time: object
  status_lattice_input_ref: string
  authoritative_for: [string]
  may_not_use_for: [string]
```

The shared envelope is not evidence that the branches are semantically identical. It is the narrow
waist through which different owner artifacts can be resolved, content-bound, admitted and consumed.

### 4.4 Checkable authority ceiling

```yaml
AuthorityCeiling:
  claim_kinds: [registered_claim_kind]
  action_refs: [string]
  subject_refs: [string]
  object_refs: [string]
  population_scope_ref: string | null
  jurisdiction_scope_ref: string | null
  purpose_refs: [string]
  audience_refs: [string]
  source_context_ref: string | null
  target_context_ref: string | null
  valid_from: timestamp | null
  valid_until: timestamp | null
  review_at: timestamp | null
  evidence_class_refs: [string]
  maintained_assumption_refs: [string]
  max_claim_strength_ref: string | null
  max_commitment_stage_ref: string | null
  permitted_operation_refs: [string]
  prohibited_use_refs: [string]
  required_downstream_gate_refs: [string]
  source_rule_version_refs: [string]
  reference_epoch_refs: [string]
```

A consumer may rely on an admitted artifact only when it resolves the artifact, verifies its content
identity and non-producer provenance, re-resolves producer standing/currentness, classifies every
load-bearing predicate under P37, and proves that the requested use is a subset of the ceiling. Missing
or unknown ceiling dimensions fail closed; a broad request is never truncated silently to fit.

The fields are checkable in principle. They are **not all checkable today** because several referenced
vocabularies and owner resolvers do not exist. External survey terms such as `reasonable assurance`,
`social licence`, `TRL` or IARC groups are not registered PolicyOS vocabularies merely because they
appear here. A later consolidation must map an adopted term to an existing registered vocabulary or
register a gap before a gate can turn on it.

### 4.5 Re-entry contract

Re-entry is reason-triggered, not “resume the old job”. A closing event invalidates the old refusal’s
currentness and permits a new owner-gate evaluation; it never converts the old refusal into approval.

```yaml
ReentryContract:
  accepted_trigger_kinds: [registered_event_kind]
  trigger_target_predicate_ref: string
  required_artifact_kinds: [string]
  invalidate_case_fields: [string]
  preserve_for_history: [string]
  rebind_scope_fields: [string]
  rerun_gate_refs: [string]
  automatic_closure_permitted: false
  duplicate_event_policy: idempotent
  stale_event_policy: reject_or_historical_only
```

A correct re-entry verifies that the event targets the blocker, resolves the new artifact, rebinds
scope/time/authority, reruns the demanding gate and records either closure, a new provisional refusal
or a deeper terminal. Old artifacts remain replayable under the rules that produced them.

### 4.6 The `deeper_terminal` test

`deeper_terminal` is true only if all five conditions hold:

1. an eligible acquisition route or competent owner procedure was actually attempted and produced new
   admitted evidence;
2. that evidence excludes or narrows a previously plausible closure route, proves a scoped
   impossibility/prohibition/unavailability, or establishes a stronger negative result;
3. the resulting refusal is more specific, scoped, replayable and checkable than the previous one;
4. no authority, approval or “almost success” credit is inferred from the added work; and
5. re-entry now requires a named change in evidence regime, target, governing rule, competent owner,
   provider relationship, delivery horizon or other explicit external condition — not merely more
   effort on the same route.

Not deeper: a timeout, empty search result, queue exhaustion, more rows with the same blocker, missing
signature without resolving who could sign, or a score just below a threshold.

A deepened refusal is progress in **knowledge of the boundary**, not progress toward permission.

### 4.7 Variant: `grounding_relation`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | A canonical causal/grounding evidence owner or a domain adjudicator whose standing and procedure are independently resolved. A subject-matter expert may produce structured background knowledge; expertise alone does not make the edge empirically established. PolicyOS has no appointed universal causal adjudicator. |
| **Sufficient acquisition** | Exact cause/intervention and effect variables, direction, scope, context, lag/versions, evidence streams, identification assumptions, alternative explanations, mechanism, dissent and transport conditions are bound; the acquisition mode’s governed sufficiency rule is satisfied. No universal cross-domain threshold is asserted. |
| **Admission proof** | A content-bound causal dossier or relation certificate identifying producer/adjudicator, search/inclusion rules, provenance by evidence stream, quality/bias assessment, assumptions, integration procedure, counterevidence, rationale, dissent, reference epoch and target scope. Pure expert elicitation also preserves individual judgments and aggregation/calibration method. |
| **Authority ceiling** | At most the relation, population/context, time, intervention/version, evidence class and maintained assumptions actually established. Expert-elicited output caps at `structured_background_assumption`; observational causal output is conditional on identification assumptions; domain adjudication licenses only its registered category. It does not authorise policy action, magnitude, transport or estimand. |
| **Re-entry** | New material evidence, changed relation definition, mechanism, population/context, intervention version, confounding structure, reference epoch or target-transport demand invalidates currentness and reruns source validity plus source→target transport. |
| **`deeper_terminal`** | A scoped negative relation is established, the formulated relation is semantically impossible, or a sound/complete procedure proves the query non-identifiable under the current information regime. `No study found` and “not classifiable” are provisional, not negative relation findings. |

**Data-path break:** observation growth can change evidential inputs but cannot itself decide the
integration assumptions or create the relation object. The demanding grounding owner, not the data
overlay, closes the case.

### 4.8 Variant: `estimand_binding`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | The accountable owner of the scientific/policy question together with a competent causal/statistical method owner; a regulator or other competent adjudicator where the intended claim is regime-governed. A dataset owner or estimator cannot infer the target from available columns. |
| **Sufficient acquisition** | Treatment/intervention regimes, target population, outcome and horizon, every relevant intercurrent-event strategy and population-level summary/contrast are unambiguous. A stronger “this analysis targets it” claim separately binds identification assumptions, observed-data functional, estimator and sensitivity plan. |
| **Admission proof** | Versioned protocol/SAP-like record or target-trial specification mapping every target attribute to the question and, when claimed, to identification and estimator semantics; amendments, rationale, scope, data compatibility, transport conditions and responsible producers are content-bound. `estimand_present=true` is insufficient. |
| **Authority ceiling** | Semantic binding alone authorises only “this is the defined target”. Identification/estimator proof may authorise “this analysis targets this estimand under these assumptions”. It never establishes the causal relation, unbiasedness, precision, transportability, mandate or action authority. |
| **Re-entry** | Any change in population, treatment versions, standard of care, outcome/horizon, intercurrent-event environment, contrast, decision purpose, protocol amendment or transport context rebinds all target attributes and then reruns identification. |
| **`deeper_terminal`** | The target is ill-defined or internally impossible, or it is well-defined but proven non-identifiable under the permitted information regime. `Identifiable but imprecise` is a data/estimation state, not this terminal. |

**Data-path break:** rows cannot choose between equally legitimate target questions. They become useful
only after the target is bound and the demanded analysis shows how they map to it.

### 4.9 Variant: `owner_writability`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | The canonical truth/change authority for the system of record, or a steward acting under a verified delegation, plus the technical security owner for the execution grant. A database administrator, requester or API account cannot self-create substantive change authority. |
| **Sufficient acquisition** | The substantive right to make the exact operation on the exact object/field for the stated purpose is established; the operation exists in the register ontology; preconditions/evidence are met; and the identified executor has a current least-privilege technical grant. Submission authority, adjudication authority and execution capability remain distinct. |
| **Admission proof** | Owner/delegation instrument, governance or statutory basis, operation/record/field semantics, decision/order and supporting evidence, executor credential, current status, audit/provenance event and system-of-record/version binding. An ACL or data-sharing agreement alone is insufficient. |
| **Authority ceiling** | Exact system of record, object/record/field, operation type, purpose, parties, evidence condition, actor/delegation depth and valid interval. It does not authorise a different operation, rewrite history, establish truth or supply legal/normative authority not present in the chain. |
| **Re-entry** | Owner policy, delegation, credential, purpose/party, operation ontology, underlying law, system of record, evidence condition or revocation changes trigger fresh owner and technical resolution. |
| **`deeper_terminal`** | The requested mutation is not a valid operation in the authoritative ontology, no competent change authority exists, or the substantive right is barred. A DBA grant cannot cure the terminal. A different legal operation yields `terminal_for_this_route`, not global impossibility. |

**Data-path break:** an observation passport admits a value to an overlay; it does not establish the
right to mutate another owner’s canonical state.

### 4.10 Variant: `legal_mandate`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | A competent constitutional/statutory authority or a competent delegator acting within the governing hierarchy and any permitted redelegation rule. PolicyOS and an LLM legal summary cannot issue the mandate. |
| **Sufficient acquisition** | A valid enabling norm covers the action; jurisdiction/institution competence is established; every delegation link is valid and current; the recipient occupies the covered role/identity; the proposed act lies within subject, function, territory, object, conditions and time. |
| **Admission proof** | Resolved norm and version, hierarchy/competence record, delegation and redelegation instruments, role-occupancy/identity proof, effective windows, conflicts/supersession, exact action mapping and attributable decision/use record. A signed memo is existence evidence, not proof of vires. |
| **Authority ceiling** | Action/function, actor, object, population, jurisdiction, instrument, amount/fiscal facet where relevant, conditions, effective interval and delegation depth. One authority facet does not imply another; enabling does not automatically supply funding or implementation authority. |
| **Re-entry** | Amendment, repeal, supersession, delegation issue/revocation/expiry, competence transfer, office-holder change, jurisdiction/fallback change or requested action/window change causes fresh hierarchy and scope resolution. |
| **`deeper_terminal`** | A higher-order rule prohibits the act, or no competent grantor exists under the current governing order. `This officer lacks authority but a superior can grant it` is recoverable, not terminal. |

**Data-path break:** facts may satisfy a mandate’s conditions but cannot create the enabling power or a
competent delegation chain.

### 4.11 Variant: `normative_authorization`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | The producer defined by the governing normative regime: affected person or authorised representative for consent, a properly constituted ethics/review body for approval/waiver, an institutional authority, or another formally competent process. Where social legitimacy has no canonical issuer, no issuer is invented. |
| **Sufficient acquisition** | Every regime-required approval, consent, waiver, participation or institutional determination applies to the exact protocol/action, purpose, population, site, procedures, risk profile and version; issuer standing and any reliance allocation are established. |
| **Admission proof** | Determination/approval/disapproval record, approved protocol/version, consent or documented waiver findings, minutes/reasons, reliance/responsibility allocation, participant/representative identity where applicable, current status, withdrawals/suspensions and exact scope binding. Popular support or mere consultation is not automatically authorization. |
| **Authority ceiling** | The approved purpose, protocol/version, procedures, population, sites, consent scope, risk conditions and review/validity triggers. It does not create legal competence, institutional execution permission, write authority or empirical effectiveness. |
| **Re-entry** | Material protocol, purpose, population, procedure, site or risk change; withdrawal, suspension, complaint, new review point or changed reliance allocation causes fresh determination. |
| **`deeper_terminal`** | A competent regime-specific disapproval or non-waivable refusal closes the current route, or the governing regime establishes that no authorised path exists. Absence of an issuer for an informal social-licence claim is `not_established` unless a competent regime itself makes it terminal. |

**Data-path break:** more facts may inform ethical review, but only the competent regime’s determination
creates the authorization object.

### 4.12 Variant: `implementation_capacity_evidence`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | The accountable delivery owner produces first-line evidence. For material/irreversible commitment, a competent assessor with sufficient independence from the achievement target adjudicates critical claims. Vendors/sponsors cannot be the sole admissibility source. |
| **Sufficient acquisition** | The delivery system, scale, environment, timeframe, causal core, reach/dose/fidelity/quality and every critical prerequisite are predeclared; each critical prerequisite passes a stage-specific threshold. An unresolved critical zero cannot be averaged away and yields no-go or a smaller tranche. |
| **Admission proof** | Prospective versioned assessment; delivery entity/owner; evidence register for workforce, contracts, suppliers, facilities, technology, interfaces, training, throughput and dependencies; assumptions, outside/reference class, conflicts, rating/threshold, baseline, outcome criterion, review triggers and permitted next commitment. A completed framework/checklist is not underlying evidence. |
| **Authority ceiling** | Only the next stage, tranche, load band, environment and period directly supported. Concept evidence permits feasibility work; representative demonstration permits limited rollout; operational load evidence permits the next bounded expansion. It is not a probability guarantee or automatic full-scale authority. |
| **Re-entry** | Stage, scope, scale, deadline, funding, supplier, workforce, technology/interface, regulation, dependency, adverse signal, elapsed validity, material pilot underperformance or baseline reset triggers reassessment. Old forecasts remain for calibration. |
| **`deeper_terminal`** | Capacity is absent and no credible build/maturation path, narrower valuable stage or alternative delivery channel reaches the required state within the decision horizon/envelope. A Red/not-ready rating with a recovery route is provisional. |

**Data-path break:** capacity evidence may contain many observations, but the acquired object is the
bounded deliverability warrant over critical prerequisites. Rows do not substitute for missing staff,
contracts, authority, integration or demonstrated load.

### 4.13 Variant: `competent_human_decision`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | An identified human whose professional/institutional standing, role authorization, domain competence, task-specific scope and validity at decision time are resolved. A credential supplies only one factor. No generic appointed signer exists today. |
| **Sufficient acquisition** | The decision question and exact subject/version are fixed; required inputs were actually available and reviewed; the person performed the required judgment, handled contrary evidence and material uncertainty, referred matters outside scope, and accepts attributable responsibility for the conclusion/qualifications. |
| **Admission proof** | Reconstructable decision record: person/credential/issuer and validity, role/mandate, competence scope, subject/version, question, inputs reviewed, criteria/method, contrary evidence, uncertainty, consultations/referrals, reasoning, conclusion/qualifications, timestamp/authentication, supersession and re-entry triggers. A click/signature alone is insufficient. |
| **Authority ceiling** | Exact decision/action, subject, version, conditions and competence/role scope. Another expert’s input does not automatically expand the signer’s scope. The decision does not become truth beyond the judgment actually made. |
| **Re-entry** | Subject version, evidence, material fact, governing rule/standard, credential/role/competence, conditions or stated trigger changes; human standing and decision validity are rechecked separately. |
| **`deeper_terminal`** | No competent authorised decision-maker exists and no governed referral or alternative route is available. This is `decision_source_unavailable`, not a negative decision about the subject. A competent decision against the proposal is a different adverse terminal. |

**Data-path break:** providing more material to nobody does not acquire a human judgment. Presence of a
person or signature without reconstructable work is ceremony, not decision acquisition.

### 4.14 Variant: `independent_audit`

| Required answer | Candidate semantics |
| --- | --- |
| **Who may produce it** | A competent assurance practitioner/body whose relational eligibility is established for this subject and engagement. Independence is resolved across individual, team, firm/network, funding/fees, appointment/removal, prior/future relationships and threats. No generic provider is appointed today. |
| **Sufficient acquisition** | Exact subject/version/period, responsible party, suitable criteria, engagement scope and assurance level are defined; independence threats are eliminated or reduced under the governing rule; sufficient appropriate procedures/evidence are performed; limitations, contrary evidence and quality review are recorded. |
| **Admission proof** | Engagement terms; practitioner/body/partner identity and standing; independence-threat register and safeguards; subject/criteria/scope/period/assurance level; procedures, evidence, contradictory findings/resolution, reviewer/quality review, limitations, conclusion, report identity/version/date and current relationship state. `external=true` is insufficient. |
| **Authority ceiling** | Only the stated subject, criteria, period/version, assurance level, scope and disclosed limitations. Limited and reasonable assurance differ; agreed-upon procedures report findings and do not silently become assurance. Audit does not create the management decision or establish claims outside the engagement. |
| **Re-entry** | Subject/control/data/criteria/scope/period change; new financial interest, non-assurance service, employment/familiarity/self-review/intimidation channel, rotation event, provider-status change or material contrary evidence triggers new independence and engagement evaluation. |
| **`deeper_terminal`** | No competent independent provider exists or independence threats cannot be remediated, so the required engagement is unavailable; alternatively, a valid audit produces an adverse conclusion or scope limitation. Unavailability and adverse audit are distinct terminals and must never be merged. |

**Data-path break:** additional auditee records do not create practitioner independence, engagement
scope or adequate work. An internal review remains internal when independent assurance is required.

### 4.15 Why the branches remain separate, and where they share machinery

| Candidate merge | Shared semantics | Why full merge is rejected |
| --- | --- | --- |
| Relation + estimand | Same-stream data invariance; both can precede estimation. | Relation is a world-structure claim; estimand is target meaning. Their producers, proof and ceilings differ and neither entails the other. |
| Legal + normative + writability | Issuer-chain, scope, validity and grant-style ceilings. | Legal power, normative sanction and canonical mutation right come from different regimes and can vary independently. They may share a `ScopedAuthorityGrant` base, not one discriminator. |
| Decision + audit | Standing, work record, reconstructability, version/time binding. | Audit additionally requires relational independence, criteria and assurance level; a decision owns the act while assurance evaluates a defined subject. |
| Capacity + audit | Material capacity claims may require independent challenge. | Audit is an input/admissibility condition; capacity requires direct evidence of the delivery system and authorises a bounded commitment. |

No pair can be collapsed without losing a downstream distinction a gate must check. Shared base
objects are desirable; false union collapse is not.

### 4.16 Authority-ceiling checkability today

| Case type | Reusable current primitives | Complete ceiling checkable today? | Missing item |
| --- | --- | --- | --- |
| grounding relation | CG1–CG3 certificates, reference epochs, mechanism/estimand obligations | **No — partial** | Adopted acquisition-mode/claim-strength vocabulary, competent producer and cross-context ceiling evaluator. |
| estimand binding | method/estimand hooks and protocol-like evidence patterns | **No — partial** | Canonical target-binding artifact/producer and demanding-gate bridge. |
| owner writability | data-overlay rights/passport owners | **No — only data-specific** | Generic truth/change owner and operation-ontology resolver. |
| legal mandate | Lex competence/hierarchy fragments | **No — partial** | Appointed institutional producer, complete mandate artifact and consumer enforcement for the exact action. |
| normative authorization | participation/legal fragments | **No** | Regime-specific producer registry, proof vocabulary and generic intake. |
| implementation capacity | planning/implementation obligation fragments | **No** | Canonical capacity evidence owner, thresholds, direct-evidence registry, assessor standing and re-entry bridge. |
| competent human decision | `HumanDecisionRecord` and delegation seeds | **No — partial** | Deployed competent decision producer pool, reconstructability enforcement and all demanding consumers. |
| independent audit | core audit packaging and assurance-case fragments | **No — partial** | Appointed independent provider, relationship/threat evidence and engagement-level consumer gate. |

The correct aggregate label remains `absent/unallocated`, not `contract_only`: this research text does
not establish an admitted canonical contract or owner.

### 4.17 Findings from the result, classified

| Finding | Classification |
| --- | --- |
| `INT-R2-F25` — classification must precede the union; `binding_gap` cannot discriminate. | `confirmed` |
| `INT-R2-F26` — the union is exhaustive only over the eight commissioned objects, not all non-data gaps. | `accepted_narrow_scope` |
| `INT-R2-F27` — arbitrary same-stream row growth cannot close relation, estimand or mandate cases. | `confirmed` within the stated object/evidence-regime scope |
| `INT-R2-F28` — one common checkable ceiling shape is feasible, but complete vocabularies/evaluators are absent. | `accepted_narrow_scope` |
| `INT-R2-F29` — re-entry opens a new owner evaluation and never auto-approves. | `confirmed` design rule supported by repo and surveyed practice |
| `INT-R2-F30` — `deeper_terminal` requires new admitted boundary knowledge, not more effort or near-pass. | `accepted_narrow_scope` |
| `INT-R2-F31` — no commissioned pair can be safely collapsed into one discriminator. | `confirmed` by producer/proof/ceiling derivation in §§4.7–4.15 |
| `INT-R2-F32` — current end-to-end checkability is absent for all eight; partial primitives do not compose into capability. | `confirmed` |

## 5. Counterexamples And Failure Modes

## 6. Benchmark Or Fixture Proposal

## 7. Artifact Contract Sketch

## 8. Later Integration Handoff

## 9. Promotion And Kill Rules

## 10. Open Questions For Consolidation

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

### 1.1 Question and research boundary

INT-R2 asks how PolicyOS should model acquisition of eight things that are not interchangeable with
additional data rows: a grounding relation, an estimand binding, owner writability, a legal mandate,
a normative authorization, implementation-capacity evidence, a competent human decision and an
independent audit.

The result is a research-level candidate `GapAcquisitionCase` discriminated union. Every branch
answers six questions independently:

1. who may produce it;
2. what counts as sufficient acquisition;
3. what admission proof is required;
4. what checkable authority ceiling follows;
5. how the demanding gate re-enters; and
6. what `deeper_terminal` means.

This is research-first because each answer defines a predicate a future authority gate might turn on.
Stage 1 specifies candidate semantics and falsifiers. It does not create the capability, appoint the
canonical owner or appoint any institutional signer.

The adversarial invariant is:

```text
for case_type in {grounding_relation, estimand_binding, legal_mandate}:
    add any number of rows to the current data stream
    while the required non-data acquisition object remains absent
    => the case remains unclosed
```

A new experiment or measurement regime can contribute to relation acquisition, and factual
conditions may matter to a mandate. The system must nevertheless name the changed evidence regime or
authority artifact and prove that it changes the blocked predicate. `row_count increased` is never a
universal closure operator.

### 1.2 False claims prevented

The union prevents:

- row-count closure of relation, target or authority;
- document-by-presence closure without issuer, scope, work and currentness;
- an authority ceiling that no consumer can check;
- rendering a stronger negative result as “almost approved”;
- borrowing an institutional signer or adjudicator merely because another field uses one.

### 1.3 Four-way identity-boundary verdict

The ratified identity makes PolicyOS the custodian of claims it signs, not a legislature, ethics body,
register, licensing body, auditor or delivery organisation
(`policy-engine/docs/system-design-decisions/policyos-identity-and-custody-boundary.md:55-112`).

| Plane | Verdict | Consequence |
| --- | --- | --- |
| Typed demand, classification, evidence intake, ceiling enforcement, re-entry and claim reaction | **OWN** | Their absence can make PolicyOS’s own signed claim silently false. |
| Mandates, normative determinations, canonical write grants, professional decisions, assurance and capacity assessments | **INTEGRATE** | PolicyOS owns the fail-closed evidence contract and verification; the external institution owns the act. |
| Succession, revocation, standing, assurance relationships and institutional changes | **OBSERVE** | They stale or reopen PolicyOS claims; PolicyOS does not administer them. |
| Performing the external institutional function | **OUT_OF_SCOPE** | Scarcity does not transfer the function to PolicyOS. |

The commission describes the package as turning a route to a missing plane into an owner. Stage-1
authority narrows this: the report makes the candidate ownership boundary and integration contract
specifiable. Consolidation/ratification must appoint the canonical owner.

### 1.4 Project fit and standing

INT-R2 is the stand-alone “+1” in Wave 8, not part of `INT-R4` ‖ `OPS-R5`.

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

The result is suitable for independent audit and consolidation. No admitted producer→artifact→bridge
→consumer→verification→surface chain and no appointed institutional producer exist. The production
and first-public-signature gates remain closed.

## 2. Current Repo Baseline

Detailed evidence is in
`docs/research/policy-operations/int-r2/repo-baseline-and-source-ledger.md`.

> **Headline:** the repository has a strong, content-bound data-acquisition path and purpose-scoped
> authority fragments, but no generic `GapAcquisitionCase` owner, residual-shape classifier,
> eight-type producer/admission chain or complete authority-ceiling evaluator.

### 2.1 Mandatory inspection and governing coordinates

The pinned study at `dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f` inspected:

- `AGENTS.md`, `policy-engine/CONTRIBUTING.md`;
- the identity ruling and required architecture documents;
- the failure-pattern register, active GY and Atlas plans, and distillation ledger;
- `policy-operations-research-pipeline.md:18-92,176-218`;
- the backlog’s Mandatory Baseline, Quality Bar, Unified Form, Operational Addendum and Pattern Pass;
- W4-K05/W4-K06;
- N13a census and N13b planner, acquisition authority, passport/overlay and re-entry owners;
- CG3/CG5 grounding hooks, typed refusal service and human-decision seed.

Architecture constraints are consistent: generators produce candidates; external power enters through
the narrow waist; projections cannot mint authority; research prose remains `absent/unallocated` until
the whole capability chain exists.

### 2.2 What refusal and acquisition do today

| Owner | Existing primitive | INT-R2 limit |
| --- | --- | --- |
| PDC waist, `src/polisyos/pdc/_impl/gy_waist.py:218-255` | Coarse obligation/refusal outcomes. | Gate posture is typed; missing acquisition object is not. |
| Authority-value service, `runtime/http/services/authority_values.py:1-150` | Real `refused | supplied` union and refusal codes. | A first-class refusal is not necessarily path-bearing. |
| Acquisition planner, `runtime/quality/acquisition_planner.py:1-360` | Typed gaps, strategies, authority levels, gate state and dispositions. | Routes work; explicitly does not satisfy the domain slot. |
| Data acquisition authority/passport/overlay | Rights/trust re-resolution, content-bound passport, quarantine and separate epochs. | Ends in admitted observation rows and data availability. |
| N13b re-entry, `tools/quality/validation/layer3_gy_n13b_reentry.py:1-210` | Real closure versus data-carrier/catalog deeper terminals. | Closure is dataset/binding/observation growth. |
| CG3/CG5 | Typed grounding blockers and next actions. | CG5 explicitly cannot close obligations or mark resolution. |

The reusable data-path discipline is:

```text
typed demand
→ eligible producer/action
→ content-bound proof
→ purpose-scoped admission
→ bounded authority
→ demanding-owner re-entry
→ replayable closure or stronger refusal
```

The non-reusable assumptions are:

```text
acquired object = observation row
admission = data passport
persistence = data overlay epoch
closure = dataset/binding/observation count increased
```

Forcing a relation, estimand, mandate, decision or audit into those shapes is the named data-gap
gravity failure.

### 2.3 Authority and ceiling baseline

PolicyOS already carries `authoritative_for`, `may_not_use_for`, authority levels, quarantine,
content identity, P37’s `not_established`, capability labels and specialised scope/time/provenance
fields. It does not have a generic owner-computed predicate:

```text
requested_use ∈ admitted_artifact.authority_ceiling
```

covering all eight case types across action/claim, subject/object, population, jurisdiction,
purpose/audience, time, evidence class, assumptions, claim strength/commitment stage, operations and
prohibited uses.

**A complete generic authority ceiling is not checkable today.** Existing fragments are reusable;
the aggregate evaluator and registered cross-type vocabulary are `absent/unallocated`.

### 2.4 CG5, 15 residuals and three capstones

`GY-engine-subordination.md:2410-2495` records that N13b converted none of the 15 residuals into world
growth and routes three `not_a_data_gap` capstones to a future knowledge/grounding plane outside N13b.
CG5 is correctly a router, not that producer.

The N13a census has a complete 15-row ranked backlog; every row says `binding_gap`. The later
measurement supplied by the commission says one was established data-shaped and 14 remained
`shape:not_established`. Holder standing:

- pinned 15-row and three-route collections: `recomputed`;
- later `1 / 14` partition: `institutionally_supplied` because its executing slice is absent at the
  pin;
- supplied zero structural classifications: not a settled zero for this holder under W4-K01/P35.

`binding_gap` is not a discriminator. Each of the 14 requires the exact demanding predicate, minimal
missing object, same-stream row-invariance result, competent producer, ruled-out neighbouring types
and `split_required` where several objects are independently missing. Unknown never defaults to data.

| Route | Candidate disposition |
| --- | --- |
| `education`: `method_estimand_binding_mismatch` | `estimand_binding`. |
| `first_vertical`: `grounding_relation_or_owner_lever:gy_n4.emergency_tax_relief` | `grounding_relation`, `owner_writability`, or ordered two-case sequence. |
| `unseen`: `grounding_relation_or_owner_lever:candidate_fallback_1950390310ca54cb` | Same disjunction/split rule. |

The disjunction proves classification must precede case creation; it does not justify a ninth hybrid.

### 2.5 Current labels

The generic union, classifier, aggregate ceiling evaluator, institutional producer set and multi-type
re-entry bridges are `absent/unallocated`. The adversarial semantic battery is
`semantic_test_missing`. Research, engineering and institutional blockers are separate; none is
repaired by observation growth.

## 3. External Research Baseline

Five commissioned surveys were treated as `surveyed_external_practice`, not repository capability or
authority. Their full scope/limitation ledger is in the `int-r2/` directory.

### 3.1 What more data can and cannot close

The first survey distinguishes imprecision from target definition, non-identifiability,
directness/support mismatch and authority. Its strongest claim is scoped: no number of observations
from the stated regime closes a target that is not a function of that regime under the stated model
and assumptions. Structural is therefore relative, not metaphysical. Deepened-refusal analogues
include non-identifiability certificates, identified sets, `UNSAT` cores and reasoned adverse
determinations; these mean different things and are not collapsed.

### 3.2 Relation and estimand

The second survey establishes:

```text
relation acquisition = warrant about causal structure
estimand binding = warrant about which quantity is the target
```

Neither entails the other. No universal calibrated causal-edge threshold exists; domain adjudication
can supply local categories. Estimand practice is more formal: intervention, population, outcome/time,
intercurrent-event treatment and contrast must be bound, while identification and estimator alignment
remain separate:

```text
BOUND != IDENTIFIED != ESTIMABLE != ESTIMATED
```

### 3.3 Mandate, normative authorization and writability

The third survey rejects `authorized=true` as a single object. Legal power, normative sanction and
canonical mutation right can vary independently. They share an issuer-chain discipline but differ in
source of power, producer, proof, ceiling and terminal. A verifiable credential proves issuer
assertion/integrity, not issuer competence or truth. Social licence often has no canonical issuer or
threshold; no token is invented where the regime supplies none.

### 3.4 Competent decision and independent audit

The fourth survey supplies reconstructability: identity/standing, scope, actual work, contrary
evidence, attribution, ceiling and revalidation. Audit adds relational independence, suitable criteria,
engagement scope and assurance level. A signature is not proof of work. `external=true` is not proof of
independence. No provider is `unavailable`, not an adverse conclusion about the subject.

### 3.5 Capacity evidence

The fifth survey treats capacity as evidence about a specific delivery system, scale, environment,
dependencies and timeframe. Sufficiency is stage-specific and weakest-link; a composite score cannot
average away a critical zero. The ceiling is the next demonstrated commitment, not a calibrated
probability of success or automatic full rollout. A genuine terminal requires no credible build path,
narrower valuable stage or alternative channel within the decision horizon.

### 3.6 Disagreements retained

- no universal uncertainty taxonomy;
- no universal calibrated relation threshold;
- social licence often has no issuer/token;
- professional standing and independence safeguards do not prove the conclusion true;
- capacity stage-gating is mature, but universal probability calibration is not.

External terms are not registered PolicyOS vocabularies merely because a survey uses them.

## 4. Result

### 4.1 Union scope and classifier

The union is exhaustive over the **eight commissioned acquisition objects**, not all possible non-data
gaps. Unknown or compound gaps remain `not_established`/`split_required`.

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

The discriminator denotes the object required by the demanding gate, not the profession, document
format, acquisition action or refusal code.

Before the union, `GapShapeAssessment` binds residual, demanding gate/predicate, minimal missing
object, evidence regime, same-stream-data effect, candidate/ruled-out types, P37 predicate provenance
and one outcome: `data_gap | one_case | split_required | not_established`.

Rules:

1. `binding_gap` alone yields `not_established`.
2. `cannot_change` rules out row-only closure but does not select a branch.
3. positive classification requires `recomputed` or `independently_reconciled` predicates;
4. `consumer_asserted`, `institutionally_supplied` and `not_established` fail closed;
5. several required objects become ordered cases, not a hybrid.

This is the exact disposition of the 14 unclassified residuals.

### 4.2 Common ceiling, re-entry and terminal rules

Every admitted artifact carries a ceiling over registered claim/action, subject/object, population,
jurisdiction, purpose/audience, source/target context, valid/review time, evidence class, assumptions,
maximum claim strength/commitment stage, permitted operations, prohibited uses, downstream gates,
rule versions and reference epochs.

A consumer resolves and content-binds the artifact, verifies non-producer provenance, re-resolves
producer standing/currentness, classifies gate predicates under P37 and proves requested use is a
subset. Unknown dimensions fail closed.

Re-entry is reason-triggered and never resumes blindly. A valid trigger invalidates currentness,
rebinds scope/time/authority and permits the demanding owner to recompute. It never converts a refusal
or admitted artifact directly into approval.

`deeper_terminal` requires all five:

1. an eligible route/competent procedure produced new admitted evidence;
2. the evidence excludes/narrows a plausible closure route or proves a scoped negative boundary;
3. the refusal is more specific, scoped, replayable and checkable;
4. no authority or near-success credit follows from extra work; and
5. re-entry now requires a named change in regime, target, rule, owner, relationship or horizon — not
   more effort on the same route.

Timeout, empty search, queue exhaustion, missing signature without owner resolution and near-threshold
scores are not deeper terminals.

### 4.3 `grounding_relation`

| Answer | Semantics |
| --- | --- |
| Producer | Canonical causal/grounding evidence owner or appointed domain adjudicator with resolved standing/procedure. Expert input alone is structured background knowledge. |
| Sufficient | Exact relation, scope/context/time, evidence streams, assumptions, alternatives, mechanism, dissent and transport conditions satisfy the governed acquisition-mode rule. No universal threshold is claimed. |
| Admission proof | Content-bound causal dossier/relation certificate with producer/adjudicator, search/inclusion, evidence provenance/quality, assumptions, counterevidence, integration rationale, dissent and epoch. |
| Ceiling | Exact relation/context/population/time/intervention/evidence class/assumptions. Expert edge caps at structured assumption; observational inference is conditional. No action, magnitude, transport or estimand authority follows. |
| Re-entry | New material evidence, definition/mechanism/context/intervention/confounding/reference/transport change; rerun source validity and target transport. |
| Deeper terminal | Scoped negative relation, semantic impossibility, or non-identifiability under the current information regime. “No study found” is provisional. |

Data can contribute evidence but observation growth cannot itself integrate assumptions or create the
relation object.

### 4.4 `estimand_binding`

| Answer | Semantics |
| --- | --- |
| Producer | Accountable question owner plus competent causal/statistical method owner; regulator where regime-governed. Dataset/estimator cannot infer the target from columns. |
| Sufficient | Intervention regimes, population, outcome/horizon, intercurrent-event strategies and contrast are unambiguous; stronger claims separately bind identification, functional, estimator and sensitivity. |
| Admission proof | Versioned protocol/SAP-like or target-trial mapping, amendments/rationale, producer, assumptions, data compatibility and transport. `estimand_present=true` is insufficient. |
| Ceiling | Semantic binding authorises only “defined target”; identification/estimator proof adds “analysis targets it under assumptions”. No relation, unbiasedness, precision, transport, mandate or action authority. |
| Re-entry | Change to population, treatments, standard of care, outcome/horizon, intercurrent events, contrast, purpose, protocol or transport. |
| Deeper terminal | Ill-defined/impossible target or defined-but-non-identifiable target. Imprecision is not this terminal. |

Rows cannot choose among legitimate questions; they are useful after target binding.

### 4.5 `owner_writability`

| Answer | Semantics |
| --- | --- |
| Producer | Canonical truth/change authority or verified delegate, plus technical security owner. DBA/requester/API account cannot self-create substantive authority. |
| Sufficient | Exact operation/object/field/purpose right, valid operation ontology/preconditions, and current least-privilege executor grant. Submission, adjudication and execution remain distinct. |
| Admission proof | Owner/delegation and legal/governance basis, operation semantics, decision/evidence, credential/status, audit/provenance and system/version binding. ACL/DSA alone is insufficient. |
| Ceiling | Exact system, object/field, operation, purpose, parties, evidence condition, actor/delegation depth and interval. No other operation, truth, legal or normative power follows. |
| Re-entry | Owner policy/delegation/credential/purpose/ontology/law/system/evidence/revocation change. |
| Deeper terminal | Operation absent from authoritative ontology, no competent change authority or substantive right barred. A different operation means terminal-for-this-route. |

A data passport admits a value to its overlay; it does not confer mutation authority in another
owner’s system.

### 4.6 `legal_mandate`

| Answer | Semantics |
| --- | --- |
| Producer | Competent constitutional/statutory authority or valid delegator within hierarchy/redelegation rules. PolicyOS/LLM cannot issue it. |
| Sufficient | Enabling norm, jurisdiction/institution competence, every delegation link, current role/identity and exact act-in-scope are established. |
| Admission proof | Resolved norm/version, hierarchy/competence, delegations, role occupancy, effective windows, conflicts/supersession, action mapping and attributable use record. |
| Ceiling | Action/function, actor, object/population, jurisdiction, instrument, fiscal facet where relevant, conditions, interval and delegation depth. One authority facet does not imply another. |
| Re-entry | Amendment/repeal/supersession, delegation issue/revocation/expiry, competence transfer, holder, jurisdiction or requested act/window change. |
| Deeper terminal | Higher-order prohibition or no competent grantor under the current order. A superior-grant route is recoverable, not terminal. |

Facts may satisfy conditions; rows cannot create enabling power or a delegation chain.

### 4.7 `normative_authorization`

| Answer | Semantics |
| --- | --- |
| Producer | Regime-defined person/body/institution: subject/representative, properly constituted review body, institutional authority or formal process. No issuer is invented for informal social licence. |
| Sufficient | Every required consent/waiver/approval/participation/institutional determination applies to exact purpose, protocol/action, population, site, procedures, risk and version. |
| Admission proof | Determination, protocol/version, consent or waiver findings, minutes/reasons, reliance allocation, identity, status, withdrawal/suspension and exact scope. Consultation/popularity is not automatically authorization. |
| Ceiling | Approved purpose, protocol/version, procedures, population, sites, consent/risk conditions and review triggers. No legal competence, execution, write or effectiveness follows. |
| Re-entry | Material protocol/purpose/population/procedure/site/risk change, withdrawal/suspension/complaint/review/reliance change. |
| Deeper terminal | Competent non-waivable disapproval or regime-established absence of a route. Informal no-issuer legitimacy remains `not_established` unless a competent regime makes it terminal. |

Evidence informs review; the competent determination creates the object.

### 4.8 `implementation_capacity_evidence`

| Answer | Semantics |
| --- | --- |
| Producer | Accountable delivery owner supplies first-line evidence; material/irreversible commitment needs competent independent challenge. Vendor/sponsor is not sole admissibility source. |
| Sufficient | Delivery system, scale/environment/time, causal core, reach/dose/fidelity/quality and every critical prerequisite are predeclared and pass stage-specific thresholds. Critical zero cannot average away. |
| Admission proof | Prospective assessment and direct evidence register for workforce, contracts, suppliers, facilities, technology/interfaces, training, throughput/dependencies; assumptions, outside view, conflicts, threshold, baseline, outcome and next commitment. |
| Ceiling | Only next stage/tranche/load/environment/period directly demonstrated. Not probability guarantee or automatic full rollout. |
| Re-entry | Stage/scope/scale/deadline/funding/supplier/workforce/technology/regulation/dependency/signal/expiry/pilot/reset change. Preserve old forecast for calibration. |
| Deeper terminal | Capacity absent and no credible build path, narrower valuable stage or alternative delivery channel within the decision horizon. Red/not-ready with recovery is provisional. |

Many rows cannot substitute for absent staff, contracts, authority, integration or demonstrated load.

### 4.9 `competent_human_decision`

| Answer | Semantics |
| --- | --- |
| Producer | Identified human with resolved standing, role authority, domain competence, task scope and validity at decision time. No generic signer is appointed today. |
| Sufficient | Question/subject/version fixed; inputs actually reviewed; required judgment performed; contrary evidence/uncertainty/out-of-scope matters handled; attributable responsibility accepted. |
| Admission proof | Reconstructable record: person/credential/issuer/validity, role/mandate, competence scope, subject/version, question, inputs, criteria/method, contrary evidence, uncertainty, referrals, reasoning, conclusion, authentication, supersession/triggers. |
| Ceiling | Exact decision/action, subject/version, conditions and competence/role scope. Another expert’s input does not expand it; conclusion is not universal truth. |
| Re-entry | Subject/evidence/material fact/rule/standard/credential/role/competence/condition change. Recheck person standing and decision validity separately. |
| Deeper terminal | No competent authorised decision-maker and no governed referral/alternative. This is source-unavailable, not a negative decision. |

Presence/signature without reconstructable work is ceremony, not acquisition.

### 4.10 `independent_audit`

| Answer | Semantics |
| --- | --- |
| Producer | Competent assurance person/body with relational eligibility across team, firm/network, funding/fees, appointment, prior/future relations and threats. No generic provider is appointed today. |
| Sufficient | Exact subject/version/period, responsible party, criteria, scope and level; threats managed; sufficient appropriate procedures/evidence, limitations, contrary evidence and quality review recorded. |
| Admission proof | Engagement terms; body/partner identity/standing; threat register/safeguards; subject/criteria/scope/period/level; procedures/evidence/contradictions/review/limitations/conclusion/report/current relationship. |
| Ceiling | Only stated subject, criteria, period/version, assurance level, scope and limitations. AUP is not assurance; audit does not create management decision or outside claims. |
| Re-entry | Subject/control/data/criteria/scope/period or relationship/threat/rotation/provider/material-evidence change. |
| Deeper terminal | No competent independent provider or unremediable threats; separately, valid adverse audit or scope limitation. Unavailability and adverse result never merge. |

More auditee records do not create independence, engagement scope or adequate work.

### 4.11 Genuine differences and possible shared bases

- relation and estimand share same-stream invariance but acquire world structure versus target meaning;
- legal, normative and write cases may share a `ScopedAuthorityGrant` base, but their sources of power
  and effects remain independent discriminators;
- decision and audit share reconstructability, while audit adds relational independence, criteria and
  assurance level;
- capacity may consume audit/decision artifacts, but neither substitutes for direct delivery evidence.

No pair can be collapsed without losing a gate-relevant producer/proof/ceiling distinction.

### 4.12 Checkability today

| Type | Complete ceiling checkable today? |
| --- | --- |
| relation | No — partial CG/reference primitives; producer/claim-strength/transport ceiling absent. |
| estimand | No — partial hooks; target-binding producer/artifact/bridge absent. |
| writability | No — only data-specific rights/passport path. |
| mandate | No — Lex fragments; appointed producer and complete exact-action bridge absent. |
| normative | No — regime producer registry and generic intake absent. |
| capacity | No — canonical evidence owner, thresholds, assessor standing and bridge absent. |
| human decision | No — partial HumanDecisionRecord/delegation seed; deployed producer/consumers absent. |
| audit | No — packaging fragments; provider/relationship evidence and demanding gate absent. |

Aggregate: `absent/unallocated`, not `contract_only`.

## 5. Counterexamples And Failure Modes

| Counterexample | Unsafe implementation concludes | Correct result |
| --- | --- | --- |
| One million observational rows preserve two causally indistinguishable models with different effects. | Relation gap closed by scale. | `grounding_relation` remains open or deepens to scoped non-identifiability. |
| Protocol contains `estimand=true` but omits intercurrent-event handling. | Estimand acquired by field presence. | Admission refused; target remains unbound. |
| Valid API token can update a register, but no substantive operation right exists. | Writability acquired. | Technical capability only; `owner_writability` open/terminal-for-route. |
| Signed delegation comes from an issuer without competence/redelegation right. | Mandate acquired by signature. | Resolve chain fails; mandate remains absent. |
| Action is lawful and writable but required consent/ethics approval is absent. | Legal power implies normative authorization. | Separate normative case remains blocked. |
| Capacity score is 82/100 while the only supplier and trained workforce are absent. | Average readiness authorises rollout. | Critical-zero no-go or narrower tranche. |
| Licensed expert signs an AI-produced conclusion without reviewing inputs or outside task scope. | Competent decision acquired. | Ceremony; no decision artifact admitted. |
| External firm audits controls it designed and depends on the same fee relationship. | `external=true` proves independence. | Independent audit not acquired. |
| Search times out after extensive effort. | Deep terminal because work was costly. | Provisional refusal; no new boundary proof. |
| Relation and owner-write right are both absent, but one case closes. | Compound gap closed by one branch. | Ordered `split_required`; both owner gates must close. |
| New mandate arrives after the target action/window changed. | Re-entry auto-closes old case. | Rebind and rerun; old mandate may not fit. |
| Valid audit for period A/criteria X is used for period B/criteria Y. | Audit is universal trust badge. | Ceiling escape blocked. |

Three required P38 divergences are explicit:

1. **property:** non-data object acquired; **proxy:** row count increased — million-row mandate case;
2. **property:** relational independence; **proxy:** `external=true` — self-reviewing vendor case;
3. **property:** competent work performed; **proxy:** signature present — out-of-scope rubber stamp.

## 6. Benchmark Or Fixture Proposal

The full operational/fixture ledger is
`docs/research/policy-operations/int-r2/operational-closure-and-fixtures.md`.

### 6.1 Public denominator

The proposed minimum public regression denominator is **63 executable cases**:

| Family | Count |
| --- | ---: |
| One synthetic happy path per discriminator | 8 |
| One trust-by-form adversary per discriminator | 8 |
| Three protected types × four row counts `{0,1,1_000,1_000_000}` | 12 |
| Eight provisional/deeper-terminal pairs | 16 |
| One re-entry case per discriminator | 8 |
| One ceiling escape per discriminator | 8 |
| Three N13 capstones | 3 |
| **Total** | **63** |

Synthetic positives are `contract_testing` only and cannot simulate real institutional authority.
A separate ordinary data-gap positive control must close on valid observation growth, proving the
harness can observe legitimate closure rather than always refuse.

### 6.2 Acceptance measures

| Measure | Required result |
| --- | ---: |
| Happy-path closure | 8/8 after admission and demanding-gate re-entry. |
| Trust-by-form false close | 0/8. |
| Protected row-inflation false close | 0/12. |
| Provisional/deeper discrimination | 16/16. |
| Automatic re-entry closure | 0/8. |
| Ceiling escape | 0/8. |
| Capstone data-default/false single type | 0/3. |
| Overall unsafe false close/escape | 0/63. |

Add 16 sealed near-variants, two per discriminator, covering synonyms, cross-bound IDs, stale status,
partial scope, issuer succession, sibling consumers, network independence and non-representative
capacity evidence. Only typed aggregate results escape.

### 6.3 Required edge classes

The public pack covers happy path, missing evidence, late event, duplicate event, conflicting
authority, owner unavailable, malicious actor, degraded mode, partial success, rollback and historical
replay. Every re-entry passes through the demanding gate; no receipt directly closes or approves.

## 7. Artifact Contract Sketch

These are research sketches, not canonical runtime contracts.

### 7.1 Process state machine

```text
UNCLASSIFIED_REFUSAL
→ SHAPE_ASSESSING
   → SHAPE_NOT_ESTABLISHED
   → CLASSIFIED
      → ROUTED
         → EVIDENCE_RECEIVED
            → ADMISSION_REFUSED
            → ADMITTED_REENTRY_REQUIRED
               → REENTRY_CLOSED
               → REENTRY_PROVISIONAL_REFUSAL
               → DEEPER_TERMINAL

closed/provisional/deeper --material trigger→ STALE_REVALIDATION_REQUIRED
```

These are acquisition-process states, not a second Atlas authority/readiness lattice. They emit or
reference the status input owned by the demanding gate. No state means approved/publishable/governed.
Owners, clocks, expiry, public meaning and transitions are fully defined in the support ledger.

### 7.2 Typed artifact family

- `GapShapeAssessment` — pre-union missing-object classification and P37 provenance;
- `GapAcquisitionCase` — eight-way union with the common identity/provenance envelope;
- `AcquisitionArtifactEnvelope` — producer standing, exact subject/version, work/procedure,
  verification, admission and ceiling;
- `AuthorityCeiling` — subset-testable purpose/scope/time/strength/operation boundary;
- `GapAcquisitionReentryReceipt` — targeted event, invalidation, rebinding and demanding-gate result;
- `DeeperTerminalRecord` — new admitted evidence, routes excluded/narrowed, scoped terminal and named
  re-entry conditions.

All are content-bound and require resolve-bind-verify. Presence, shape, self-declared verifier role or
signature alone never admits them.

### 7.3 Canonical-owner disposition

- extend the canonical acquisition planner; do not build a second planner;
- relation re-enters CGF owners;
- estimand extends method/grounding owners;
- legal mandate extends Lex;
- competent decision extends the existing `HumanDecisionRecord`/delegation chain;
- audit extends `core/audit` packaging and runtime assurance intake while the provider stays external;
- Atlas renders canonical outputs and cannot invent the union;
- residual shape, generic capacity evidence and the non-data producer plane currently have no admitted
  owner: `absent/unallocated`.

Time, rule/schema/reference versions, valid/transaction time, revocation, succession, expiry and
historical replay remain load-bearing.

## 8. Later Integration Handoff

The complete handoff is
`docs/research/policy-operations/int-r2/integration-handoff-and-finding-register.md`.

Safe order:

1. independent audit/amendment/verification, consolidation and ratification;
2. appoint canonical classifier/non-data acquisition owner and register gate vocabularies;
3. extend the canonical planner boundary;
4. bind each branch to its existing domain owner or explicit external producer;
5. persist admitted artifacts, ceilings, re-entry and terminal receipts;
6. wire demanding gates to recompute closure and enforce ceilings;
7. pass public and sealed semantic batteries;
8. project through the one Atlas lattice.

The draft `gap_acquisition_case_union` consumer row is demand evidence only until merged and backed by
a ratified producer/artifact. Capstones enter through `GapShapeAssessment`; none defaults to N13 data
acquisition. The custody cycle retains historical refusal, admitted artifact, ceiling, trigger,
re-entry and terminal records without turning GY into an administrative subsystem.

All eight future chains currently lack one or more producer, artifact, bridge, consumer, verification,
surface or institutional prerequisites. Their aggregate label remains `absent/unallocated`.

## 9. Promotion And Kill Rules

### 9.1 Current and later levels

- **research_only — current:** Markdown evidence only; no runtime consumer or authority effect.
- **prototype_allowed:** explicit contract-testing scope, synthetic identities, no production artifact,
  complete classifier/ceiling/no-auto-close behaviour, 0/63 unsafe outcomes, no default-enabled
  consumer.
- **governed_allowed:** ratified semantics; named owner; registered vocabularies; persistent
  resolve-bind-verify artifacts; standing/currentness re-resolution; exact demanding-gate bridges;
  one-lattice composition; public/sealed/corruption/replay tests; fail-closed absent institutions.
- **production_candidate:** real institutions operating; retention/revocation/succession/contest and
  incident/reissue exercised; source-specific law/professional/assurance maintained; orchestration and
  external surfaces complete; production-shaped unsafe false close remains zero.

Research ratification alone is not governed capability.

### 9.2 Kill rules

Block the affected implementation if any occurs:

1. unclassified residual defaults to data or a branch;
2. rows close relation/estimand/mandate without the object;
3. form, keyword, signature, `external=true` or self-verifier substitutes for resolution/provenance;
4. broader or unknown-ceiling use is permitted;
5. scarcity turns PolicyOS/internal staff into the missing institution;
6. producer/route self-closes without demanding-gate recomputation;
7. timeout/effort/near-pass emits `deeper_terminal`;
8. surface mints authority/readiness;
9. unregistered external term drives a gate;
10. compound objects are collapsed so one closes another.

Legislation, ethics adjudication, consent, register adjudication, licensing, assurance service and
policy delivery remain out of scope; PolicyOS integrates evidence and owns its reaction.

## 10. Open Questions For Consolidation

1. placement of the common envelope: narrow waist now, or only after one producer path is proven;
2. appointment of the residual-shape and generic non-data acquisition owner — CG5 cannot own it;
3. mapping/registration of relation strength, estimand strength, operation, capacity stage and
   assurance-level vocabularies;
4. domain-specific causal adjudication and claim ceilings; universal threshold remains open;
5. social licence without a canonical issuer;
6. capacity owner, critical thresholds, independence and longitudinal calibration;
7. ordering/dependency graph for compound gaps;
8. import and independent reconciliation of the later 15-row classification, including identity of
   the one data-shaped member;
9. consolidation with INT-R5/GY-PA2/Atlas DS9 rather than a second competence certificate;
10. audit intake extending `core/audit` while provider remains external;
11. consumer readiness of the unmerged union row;
12. one-lattice status composition;
13. institutional signer/provider availability.

Recommended consolidation is cross-owner: Wave-8 consolidator with GY architecture, Lex,
human-decision, core-audit, Atlas and the future acquisition owner represented.

### 10.1 Finding classification and Pattern Pass

The support register classifies **F01–F40**. No finding is left unclassified. Its research outcomes are
`confirmed`, `accepted_narrow_scope` or `deferred_open_problem`; capability and gate standing remain
separate.

The recorded Pattern Pass covers P01–P05, P07–P16, P20–P22, P26–P33 and P35–P38. Load-bearing results:

- no contract-only capability claim (P01/P02);
- no parallel lattice or owner (P04/P27);
- checkable ceilings and no projection authority (P05/P15);
- semantic, adversarial and sibling variants (P10/P29/P33);
- weakest-link capacity and explicit mandate/normative/human authority (P21/P22/P26);
- resolve/content-bind/non-producer provenance (P32);
- complete denominators and holder attribution; supplied zero not settled (P35);
- finding IDs, not adjacent prose (P36);
- P37 provenance classification and fail-closed unknowns;
- P38 divergences: rows versus non-data object, `external=true` versus independence, signature versus
  competent work.

Final standing:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This package is authoritative only as stage-1 research input. It moves no capability, appoints no
owner or signer and opens no gate.

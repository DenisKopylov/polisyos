# INT-R5 Decision Authority Graph And Certificate Specification — Amended

## 1. Status, authority boundary and non-goals

This is a research-level contract sketch. It defines the proposition a future implementation must
prove and the evidence needed to prove it. It does not appoint an owner, grant authority, select a
jurisdiction's substantive law, register final wire vocabulary, authorize implementation or create a
new global status lattice.

`DecisionAuthorityGraph` is the typed provenance graph for one exact decision-authority claim.
`DelegationValidityCertificate` is a pre-action reduction of that graph against one exact decision,
actor or body, decision time and intended effect.

The PolicyOS custody signature means only:

> PolicyOS computed this bounded result from these identified rules and admitted evidence at this
> time.

It does not mean PolicyOS appointed the decision-maker, created the external power, adjudicated a
legal dispute or made the underlying decision.

## 2. Propositions to be proven

For exact decision `D`, actor or body `P` and independently established decision time `t_d`:

```text
PreActionAuthority(P, D, t_d) :=
    trusted authority root exists
    ∩ at least one valid provenance path reaches P or the competent body
    ∩ each path link was valid when created and at t_d
    ∩ effective scope contains D
    ∩ office, role, forum and decision mode apply
    ∩ amount, place and reserved-matter predicates hold
    ∩ required collegial predicates hold
    ∩ required separation and conflict predicates hold
    ∩ required recognition predicates hold
    ∩ the act-effect profile identifies P/body as operative maker
    ∩ every decisive fact has admissible provenance and freshness
```

For exact protected effect `E` and independently generated commit time `t_e`:

```text
InstitutionalEffectAuthority(E, t_e) :=
    valid pre-action certificate bound to E
    ∩ certificate not replayed or substituted
    ∩ t_e is within the admitted freshness bound
    ∩ every profile-required revalidation checkpoint passed
    ∩ no legally effective revocation or invalidating event applies

ProtectedEffectAdmissible(E, t_e) :=
    InstitutionalEffectAuthority(E, t_e)
    ∩ DS20 exact operation/resource/permission/step-up admission
    ∩ (
        PAO-R4 crossing-gate receipt
        if individual_case_or_pointwise_recoverable(E)
      )
```

The future protected-effect bridge or route consumer must evaluate the complete conjunction. No
certificate, DS20 allow or PAO-R4 receipt may infer either of the other predicates.

Required two-direction negatives:

```text
valid INT-R5 certificate + missing/failed PAO-R4 receipt
    -> zero individual-case effect

valid PAO-R4 receipt + missing/failed INT-R5 certificate
    -> zero protected effect
```

`PAO-R4` remains a separate owner and artifact family. INT-R5 does not absorb its semantic-class,
individual-fact or case-use analysis.

## 3. Information-limit proposition

Mutable authority does **not** imply that authority actually changes between check and use. An
unchanged history may satisfy:

```text
authority(H, t0) = authority(H, t1)
```

The defensible information-limit proposition is instead:

```text
There exist admissible histories H0 and H1 such that:

  observations(H0, <= t0) = observations(H1, <= t0)
  authority(H0, t1) != authority(H1, t1)
  where t1 > t0
```

A certificate computed from evidence available through `t0` cannot distinguish those histories and
therefore cannot determine authority at `t1` across all admissible future histories. This is a
non-inferability proposition, not a claim that inequality occurs in every history and not a legal
rule selecting the effect of revocation.

The consequence remains load-bearing: every certificate records `as_of`, `fresh_until`, mutable
dependencies and one profile-derived temporal mode:

- `snapshot_by_explicit_rule`;
- `issuer_authorized_lease`;
- `revalidate_before_commit`;
- `continuous_checkpoint_revalidation`.

Equal-state histories are allowed; future-state certainty from pre-future evidence is not.

## 4. Graph identity and commitments

```yaml
DecisionAuthorityGraph:
  graph_id: content-addressed identifier
  schema_version: research candidate
  decision_commitment:
    decision_id: canonical identifier
    canonical_payload_hash: sha256
    decision_type: registered or profile-qualified token
    subject_matter_refs: [content-addressed refs]
    amount_claim_ref: optional content-addressed ref
    affected_resource_refs: [content-addressed refs]
    intended_legal_effect_ref: content-addressed ref
  effect_commitment:
    operation_id: versioned runtime operation
    resource_digest: sha256
    effect_class_ref: versioned classification receipt
    effect_parameters_hash: sha256
    pao_r4_applicability: required | not_required | not_established
  evaluation:
    decision_time_ref: independently produced event/timestamp receipt
    requested_effect_time: caller candidate only or null
    effect_commit_time_ref: protected-consumer event receipt or null before commit
    jurisdiction_profile_applicability_ref: independently reconciled receipt
    rule_profile_applicability_refs: [independently reconciled receipts]
    revalidation_mode_ref: reducer-derived receipt
  graph_root_hash: sha256
```

The requester may submit candidate material. A candidate becomes decisive only after the field's
semantic producer and verifier named in §8 establish it. Canonicalization then commits the admitted
facts. It does not upgrade requester provenance.

```text
canonicalize(requester_value) -> integrity of requester_value
canonicalize(admitted_semantic_fact) -> integrity of an independently established fact
```

Only the second may be decisive for a positive.

## 5. Node and edge vocabulary

Candidate node classes:

| Node | Required meaning |
|---|---|
| `AuthoritySource` | versioned source creating root power |
| `JurisdictionRuleProfile` | versioned competence, defect, cure and temporal rules |
| `ProfileApplicabilityDecision` | competent selection of profiles for this matter |
| `Institution` | legally identified external body |
| `Office` | office or seat distinct from current holder |
| `Principal` | issuer-qualified person, service or body identity |
| `Appointment` | election, appointment, designation or qualification event |
| `VacancyOrTrigger` | event activating acting or emergency authority |
| `DelegationInstrument` | signed/versioned grant of defined power |
| `RecognitionRule` | legal/trust gateway for specified reliance |
| `ExternalAct` | consultation, recommendation, approval, decision or status assertion |
| `DecisionForum` | board, plenary, committee or permitted alternative mode |
| `MeetingSession` | session identity and event timeline |
| `DecisionItem` | exact motion/proposal/decision event |
| `ParticipationEvent` | join, leave, disconnect, recusal, vote-open/cast/close |
| `ConflictRecord` | disclosed, detected or indicated conflict fact |
| `RecusalOrManagementDecision` | competent recusal, waiver or management act |
| `SeparationRequirement` | incompatible roles and controlling-subject rule |
| `AmountValuation` | economic transaction, currency, aggregation and valuation |
| `EmergencyPredicate` | trigger, necessity/urgency finding and exceptional scope |
| `RevocationOrInvalidationEvent` | creation, legal effect and observation of negative state |
| `EffectClassification` | reversible, conditionally reversible or irreversible profile result |
| `ActEffectProfile` | formal type, binding effect, condition precedent and operative maker |
| `CureEffect` | profile-specific temporal legal effect of cure/validation |
| `EvidenceAssertion` | typed statement from a named producer |

Candidate edge kinds remain non-collapsible:

```text
CREATES_POWER
CONSTITUTES_BODY
CREATES_OR_IDENTIFIES_OFFICE
APPOINTS_OR_ELECTS
QUALIFIES_HOLDER
DELEGATES
SUBDELEGATES
ACTS_UNDER_SUCCESSION
ACTS_UNDER_IMPLIED_DEPARTMENTAL_AUTHORIZATION
ACTS_UNDER_EMERGENCY_AUTHORITY
RECOGNISES_UNDER
REQUIRES_FORUM
REQUIRES_QUORUM
REQUIRES_VOTE_RULE
REQUIRES_COSIGNATURE
REQUIRES_SEPARATION
PROPOSED_BY
MATERIALLY_CONTRIBUTED_BY
APPROVED_BY
EXECUTED_BY
INDEPENDENTLY_REVIEWED_BY
CONFLICT_APPLIES_TO
RECUSED_FROM
WAIVED_OR_MANAGED_BY
REVOKES
SUSPENDS
SUPERSEDES
CURES_OR_VALIDATES
CONSULTED_BY
RECOMMENDED_BY
CONDITION_PRECEDENT_APPROVED_BY
BINDINGLY_DECIDED_BY
```

One `AUTHORIZED_BY`, `APPROVED_BY` or `TRUSTED` edge would erase outcome-determinative distinctions.

## 6. Common claim envelope

Every load-bearing node and edge carries:

```yaml
claim_envelope:
  claim_id: stable identifier
  claim_type: namespaced token
  subject_ref: graph node or edge
  assertion: canonical typed payload
  source_jurisdiction: required for legal claims
  governing_instrument_ref: required when profile says so
  rule_version_ref: required
  origin:
    producer_role_ref: named institutional or system role, never requester
    producer_instance_ref: appointed holder or not_established
    issuer_id: external or internal issuer
    source_class: legal_register | appointment_register | meeting_system |
      conflict_register | declaration | transaction_ledger | identity_provider |
      recognition_register | protected_effect_ledger | PolicyOS_recomputation |
      other_typed_source
  admission:
    predicate_provenance: recomputed | independently_reconciled |
      consumer_asserted | institutionally_supplied | not_established
    decisive_for_positive: boolean
    verifier_receipt_refs: [content-addressed refs]
  time:
    asserted_at: timestamp
    legally_effective_from: timestamp or condition
    legally_effective_until: timestamp or condition or null
    observed_at: timestamp
    fresh_until: timestamp
  evidence_refs: [content-addressed refs]
  authoritative_for: [purposes]
  may_not_use_for: [purposes]
```

`institutionally_supplied` describes origin relative to PolicyOS; it is not positive by itself.
Issuer, signature, content, scope, time and applicability must be verified so the gate predicate is
`recomputed` or `independently_reconciled`. Missing producer instance or adjudicator yields a typed
negative, never a fallback.

## 7. Semantic fact versus byte commitment

The canonicalizer owns only deterministic representation, commitment and mismatch detection. It does
not own the truth of amount, recipient, decision time, effect class, jurisdiction or legal effect.

The field lifecycle is:

```text
requester candidate
  -> authoritative producer or competent external issuer
  -> verifier/admission receipt
  -> semantic fact with provenance
  -> canonicalizer/hash
  -> graph/certificate commitment
```

A valid hash with non-positive provenance remains non-positive.

## 8. Required producers for every decisive coordinate

The roles below are candidate requirements, not appointments. If no competent holder/source exists,
the result is `not_established` with the missing role named.

| Decisive coordinate | Semantic producer | Verifier/admission | Requester control | Required fail-closed test |
|---|---|---|---|---|
| decision payload fields | source transaction/case/decision system for each field | field-specific resolver plus canonicalizer after admission | candidate only | canonical hash matches but source value differs → refuse |
| `decision_time` | constitutive decision-event system; where needed, trusted timestamp issuer | decision-event receipt verifier and profile determining legally relevant act | cannot backdate or choose | caller time inside delegation but event time outside → refuse |
| `issued_at` / `as_of` | PolicyOS server clock plus trusted timestamp/custody event where required | custody verifier | none | caller-supplied timestamp ignored; missing trusted time when required → `not_established` |
| requested effect time | requester may state scheduling intent only | never decisive until effect consumer produces commit event | candidate only | candidate time cannot satisfy expiry/currentness |
| effect/commit time | protected-effect consumer or commit ledger | signed/event-bound commit receipt verifier | none | mismatch or absent receipt before claimed commit → refuse |
| `effect_class` | versioned effect-classification profile owner over registered operation/resource semantics | operation-registry/profile resolver | cannot downgrade | irreversible→reversible caller mutation with valid bytes → refuse |
| jurisdiction/profile applicability | competent jurisdiction/profile governance role using matter, institution, place and effective date | independent applicability resolver | cannot profile-shop | favourable caller profile conflicts with resolver → refuse |
| rule-profile applicability | competent body/instrument/profile source | source/version/applicability verifier | candidate reference only | unknown or conflicting mandatory profile → `not_established` |
| `revalidation_mode` | graph reducer derives mode from admitted profile, revocability and effect class | deterministic recomputation receipt | cannot select | caller requests snapshot while profile requires checkpoint → refuse |
| actor/key/tenant | verified identity issuer plus DS20 binding | identity/key/currentness verification | cannot override | alias or tenant mismatch → refuse |
| office/seat holder | appointment/election register or constitutive record | appointment chain verifier | assertion only | absent/unappointed holder → `not_established` |
| root power/reserved matters | jurisdiction/profile owner over versioned source | legal-source and applicability verifier | prose citation non-positive | unsupported or personally reserved power → refuse |
| delegation/subdelegation | signed instrument/register | chain, creation-time power and attenuation verifier | inline grant forbidden | parent lacked subdelegation power at creation → refuse |
| amount/aggregation | transaction/contract/budget owner | recomputing valuation procedure | submitted amount non-decisive | split invoice below limit but aggregate above → refuse |
| forum/roster/participation | constitution/profile, appointment register and meeting event system | item-level replay and profile resolver | chair/minutes conclusion evidence only | wrong forum or missing event branch → refuse |
| quorum/vote | PolicyOS recomputation from admitted roster/events | deterministic threshold receipt | cannot submit `quorum=true` | one used branch invalid → recompute/refuse |
| transaction roles | workflow lineage owner | controlling-subject resolver | display role non-positive | alias closes both roles → refuse |
| conflict/recusal | register, participant declaration, competent ethics/adjudication owner | bounded record/declaration/adjudication verifier | conflicted actor not sole exception producer | missing required adjudicator → `not_established` |
| revocation/currentness | status/revocation sources and dependency index | checkpoint resolver | cached request non-positive | newer legal-effective revocation → refuse |
| recognition | recognition-rule owner and accepting body's acceptance producer | purpose/scope/status/refusal-ground verifier | source agency cannot self-authorize local effect | authenticity without acceptance basis → refuse |
| act effect/operative maker | versioned jurisdiction profile plus admitted source act | effect classifier and responsibility resolver | UI verb diagnostic only | title says approval but operative effect unresolved → `not_established` |
| certificate result | PolicyOS graph reducer | independent recomputation/custody proof | cannot construct positive | any decisive receipt non-positive → no positive |

Minimum red tests for this producer discipline are defined in `adversarial-fixtures.md`: backdated
decision time, effect-class downgrade, jurisdiction profile shopping, revalidation-mode downgrade and
valid-hash/non-positive-provenance substitution.

## 9. Authority path reduction

For each root-to-actor/body candidate path:

```text
effective_scope    := root_scope
effective_validity := root_validity
remaining_depth    := root_depth_limit

for each link from root toward actor:
    verify issuer identity and signature
    verify issuer equals prior subject/authorized grantor
    verify prior link allowed this delegation kind
    verify grantor held creation power at creation_time
    verify link and activation conditions at decision_time
    verify mandatory constraints are understood
    verify no applicable revocation/suspension/supersession

    effective_scope    := intersection(effective_scope, link.scope)
    effective_validity := intersection(effective_validity, link.validity)
    remaining_depth    := reduce_and_check(remaining_depth, link)

    reject path if scope or validity becomes empty
```

A child cannot amplify a parent. Unknown mandatory constraints reject the path. One invalid path does
not destroy an independent valid path; a conjunction/threshold fails only when surviving branches no
longer satisfy it.

Acting/succession paths additionally require vacancy/trigger, applicable succession rule,
qualifications, nomination restrictions, start/end events and saving provisions. Emergency paths
require a named source, competent issuer, trigger, necessity/urgency finding where required,
exceptional scope, expiry and post-event evidence. Neither is silently converted to delegation.

Amount reduction uses the economic transaction, not one invoice:

```text
economic_transaction_total :=
    base_commitment
    + counted variations/options
    + related orders or instalments
    + counted liabilities/taxes under valuation_rule

authorized_amount :=
    currency_normalization_valid
    ∩ economic_transaction_total <= effective_amount_limit
    ∩ budget_scope_contains_transaction
```

## 10. Collegial, separation and conflict reduction

A body path is evaluated per exact decision item:

1. competent body and actual forum/mode;
2. lawful seats/holders at decision time;
3. item-specific conflicts, recusals and eligibility;
4. event-sourced participation under the profile's presence test;
5. profile-specific quorum denominator, threshold and temporal scope;
6. each vote branch and result rule;
7. alternative decision mode requirements;
8. constitutive authentication/co-signature separately;
9. saving/cure effect without rewriting history.

`actual_forum != competent_forum` refuses before quorum can be used as a rescue.

All transaction roles resolve to a controlling subject. Account inequality is not independence.
Configured structural self-approval is non-waivable:

```text
controlling_subject(proposer_or_material_contributor)
  != controlling_subject(final_approver)
```

Conflict output remains bounded:

- prohibited role overlap found/not found;
- registered conflict found/not found in named records;
- record-indicated conflict requiring adjudication;
- current declaration received/missing;
- competent management/waiver/recusal decision present/missing;
- undisclosed/off-system conflict absence **not provable**.

No certificate may state that no undisclosed conflict exists.

## 11. Cross-agency and act-effect reduction

For each external act:

```text
acceptance :=
    legal_gateway_applies
    ∩ source_identity_and_competence_verified
    ∩ act_type_and_current_status_verified
    ∩ scope_and_purpose_match
    ∩ authenticity_and_assurance_verified
    ∩ no_refusal_ground_triggered
    ∩ accepting_body_residual_duties_completed
    ∩ responsibility_allocation_complete
```

The graph stores `recognised_as` and `not_recognised_as`. Authenticity, identity or qualification does
not imply truth, local authorization or competence to bind the accepting body.

Act effect follows the governing profile, not the button label:

```yaml
act_effect:
  formal_source_type: consultation | recommendation | opinion | approval |
    endorsement | binding_decision | other_profiled
  formal_binding_effect: true | false | contested
  condition_precedent_for_final_act: true | false
  recipient_legally_free_to_depart: true | false | qualified
  departure_requires_reasons: true | false
  creates_legal_consequences: true | false | contested
  operative_act_ref: content-addressed ref
  ultimate_decision_maker_ref: principal/body ref
  direct_reviewability: true | false | jurisdiction_dependent
  practical_departure_cost: diagnostic only
```

## 12. Freshness and mid-operation semantics

```text
fresh_until = min(
    path_expiry,
    status_next_update,
    appointment_or_attribute_expiry,
    conflict_declaration_expiry,
    meeting/decision evidence expiry if any,
    recognition_status_expiry,
    policy lease,
    effect deadline
)
```

`fresh_until` is an evidence bound, not a guarantee that no emergency revocation can occur sooner.
The reducer derives the temporal mode; the caller cannot choose it.

Before an irreversible effect, a legally effective revocation invalidates effect admission. After an
irreversible effect, PolicyOS preserves the historical certificate, stops later dependent effects and
routes invalidation, incident, reissue, withdrawal, correction or external remedy. It never claims a
rollback that did not occur.

## 13. Certificate result union

```yaml
DelegationValidityCertificate:
  certificate_id: content-addressed identifier
  schema_version: research candidate
  local_result: pre_action_valid | refused | not_established | not_applicable
  issued_at_ref: server/custody timestamp receipt
  as_of_ref: independently established evaluation-time receipt
  fresh_until: timestamp
  revalidation_mode_ref: reducer-derived receipt
  decision_commitment: exact canonical hash
  effect_commitment: exact operation/resource/parameter hash
  principal_or_body: refs
  graph_id: ref
  graph_root_hash: sha256
  jurisdiction_profile_applicability_refs: [refs]
  effective_authority: surviving paths, scope, amount/place and interval
  predicate_receipts: [producer, evidence, provenance, evaluated_at, fresh_until]
  dependency_refs: [every mutable ancestor/status source]
  reason_ids: [namespaced versioned candidate IDs]
  missing_role_or_owner_refs: [refs]
  limitations: [bounded claim limitations]
  authoritative_for: [this exact pre-action proposition]
  may_not_use_for:
    - any other decision or effect
    - individual-case authorization under PAO-R4
    - legal sufficiency outside named profiles
  custody_proof: PolicyOS component, reducer/policy version, graph hash and attestation
```

The local result union is family-native input to the existing Atlas/system status lattice. DS4 or its
successor owns projection. No second global `authority_status` lattice is created.

## 14. Candidate reason identity and crosswalk

Every research reason uses the namespace and version shape:

```text
polisyos.int_r5.reason.<slug>@0.1.0-candidate
```

Examples:

```text
polisyos.int_r5.reason.missing_appointed_holder@0.1.0-candidate
polisyos.int_r5.reason.self_approval@0.1.0-candidate
polisyos.int_r5.reason.delegation_expired@0.1.0-candidate
polisyos.int_r5.reason.forum_not_competent@0.1.0-candidate
polisyos.int_r5.reason.quorum_lost_at_decision@0.1.0-candidate
polisyos.int_r5.reason.authority_not_preexisting@0.1.0-candidate
polisyos.int_r5.reason.certificate_stale@0.1.0-candidate
polisyos.int_r5.reason.revalidation_required@0.1.0-candidate
polisyos.int_r5.reason.pao_r4_receipt_missing@0.1.0-candidate
```

These are candidate semantic identities, not registered final wire codes. Fixtures may assert them
as research-oracle IDs, but implementation must use the ratified registry/crosswalk.

Collision/crosswalk record at the baseline:

| INT-R5 candidate | Existing family identity | Relationship now | Projection owner |
|---|---|---|---|
| `...certificate_stale@0.1.0-candidate` | `polisyos.eval_safety.certificate_stale@1.0.0` | semantic sibling; **not an alias** until ratified | DS4/status + owning families |
| `...revalidation_required@0.1.0-candidate` | no exact registered identity established by this pass | unmapped candidate | DS4/status + INT-R5 future owner |
| all other INT-R5 reasons | no exact registered identity established by this pass | unmapped family-native candidate | DS4/status + INT-R5 future owner |

Crosswalk invariants:

- mapping may preserve or weaken information but may never upgrade `not_established`/`refused` to a
  positive;
- sibling identities remain distinct until an owner ratifies alias/equivalence;
- implementation cannot strip namespace/version and fall back to bare uppercase tokens;
- the crosswalk does not create a second status lattice.

## 15. Unappointed-holder behavior

A required role exists independently of a current holder:

```yaml
required_role:
  role_id: exact institutional role
  appointing_authority_ref: known or not_established
  required_for: exact predicate
  current_holder_set: []
```

When no qualifying appointment resolves:

```yaml
local_result: not_established
reason_ids:
  - polisyos.int_r5.reason.missing_appointed_holder@0.1.0-candidate
missing_role_or_owner_refs: [exact required role]
```

This is a normal typed result. Candidate computation, demonstrations and negative replay remain
available. A later appointment changes graph evidence, not the model. A team, maintainer, runtime role
or adjacent signer may not substitute for the institutional holder.

## 16. Cure and temporal legal effect

The original historical certificate answers whether authority existed for the original act at its
original decision time. It is immutable. A later cure or validation is a new event and new result.

Every cure result must carry:

```yaml
cure_effect:
  kind: prospective | relation_back | saved_act | limited | unresolved
  legally_effective_from: timestamp | event_ref | unresolved
  affects_original_legal_effect: yes | no | qualified | unresolved
  protected_interval_or_scope: optional profile-qualified value
  source_profile_ref: required
  competent_cure_actor_ref: required or not_established
  conditions_satisfied_refs: [refs]
  historical_certificate_mutated: false
```

`relation_back` is representable where the named regime supplies it. `saved_act` records a statutory
saving rule rather than pretending a later actor ratified the act. `unresolved` is required where no
competent profile/adjudication exists. No result backdates issuance or inserts future evidence into
the original snapshot.

## 17. Historical replay

Replay preserves two questions:

1. What did the certificate establish from admitted rules/evidence at its `as_of`?
2. What is its current standing after later revocation, correction, cure or discovery?

Later events append current-state, cure, invalidation or supersession evidence. They do not rewrite the
original graph, erase a refusal or fabricate pre-existing authority.

## 18. Repository placement and missing bridges

Existing reusable placements:

| Concern | Existing placement | Corrected conclusion |
|---|---|---|
| operational mandate/PA2 | `mandate_bounded_delegation.py`; `agent_action_authority.py` | bounded subset to extend, not full authority model |
| human-decision source/currentness/custody | DS9 contracts/service/routes | candidate future certificate consumer |
| runtime permission/resource/step-up | DS20 Python/Rego owners | retain as narrow final floor |
| acquisition route | `routes/control.py::ingest_data` and `run_data_ingestion` | DS20-only today; PA2/DS9 institutional bridge missing |
| PAO-R4 | independent individual-use firewall | conditional separate receipt required at effect boundary |
| Atlas/DS14 | Atlas owner | future projection/consumer, never producer |

Required future acquisition bridge:

```text
exact acquisition decision/effect commitment
  -> INT-R5 graph reduction and certificate/currentness
  -> optional PAO-R4 crossing receipt when applicable
  -> DS20 EVIDENCE_ACQUIRE/resource/step-up admission
  -> run_data_ingestion
```

No such production call edge exists at the baseline. This specification does not appoint its owner or
claim implementation.

## 19. Non-effect and standing

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
```

This amendment corrects research claims only. It does not implement the graph/certificate, register
wire vocabulary, allocate a canonical owner, appoint institutional holders, create a production
bridge, authorize an individual decision or open any gate.

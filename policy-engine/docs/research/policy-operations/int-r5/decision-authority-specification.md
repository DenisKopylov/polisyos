# INT-R5 Decision Authority Graph And Certificate Specification

## 1. Status, authority boundary and non-goals

This is a research-level contract sketch. It defines the proposition a future implementation must
prove and the evidence needed to prove it. It does not appoint an owner, grant authority, select a
jurisdiction's substantive law, create a new global status lattice, or authorize implementation.

`DecisionAuthorityGraph` is the complete typed provenance graph for one decision-authority claim.
`DelegationValidityCertificate` is a pre-action reduction of that graph against an exact decision,
principal or body, time and intended effect.

The certificate's PolicyOS custody signature means only:

> PolicyOS computed this bounded result from these identified rules and evidence at this time.

It does **not** mean that PolicyOS appointed the decision-maker, created the external power,
adjudicated a dispute, or made the underlying decision.

## 2. Proposition to be proven

For exact decision commitment `D`, intended protected effect `E`, actor or body `P`, decision time
`t_d` and effect time `t_e`, the positive proposition is:

```text
PreActionAuthority(P, D, t_d) :=
    trusted authority root exists
    ∩ at least one valid provenance path reaches P or the competent body
    ∩ every path link was valid when created and at t_d
    ∩ effective scope contains D
    ∩ correct office, role, forum and decision mode apply
    ∩ amount and place predicates hold
    ∩ required collegial predicates hold
    ∩ required separation and conflict predicates hold
    ∩ required recognition predicates hold
    ∩ the legal-effect profile identifies P/body as the operative decision-maker
    ∩ every decisive fact has admissible provenance and freshness
```

A positive pre-action result is not automatically sufficient at `t_e`:

```text
EffectAuthority(E, t_e) :=
    valid pre-action certificate bound to E
    ∩ certificate not replayed or substituted
    ∩ t_e is before fresh_until
    ∩ every revalidation checkpoint required by the profile passed
    ∩ no legally effective revocation or invalidating event applies
```

The distinction prevents a certificate valid at `t_d` from becoming an unlimited bearer token.

## 3. Graph identity and commitment

A graph instance is bound to one exact subject:

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
    effect_class: reversible | conditionally_reversible | irreversible
    effect_parameters_hash: sha256
  evaluation:
    decision_time: timestamp
    requested_effect_time: timestamp or null
    jurisdiction_profile_refs: [versioned refs]
    rule_profile_refs: [versioned refs]
  graph_root_hash: sha256
```

The requester can supply raw candidate input. The requester cannot supply the canonical commitment
or graph root. A canonicalizer recomputes both from immutable resolved inputs. Changing amount,
recipient, resource, subject matter, decision mode or intended effect creates a different graph and
invalidates the certificate.

## 4. Node vocabulary

The following are research candidate node classes, not registered repository vocabulary.

| Node | Required meaning |
| --- | --- |
| `AuthoritySource` | statute, constitutive instrument, charter, regulation, order or other source that creates the root power |
| `JurisdictionRuleProfile` | versioned interpretation profile for competence, defects, saving/cure and temporal semantics |
| `Institution` | legally identified external body or organization |
| `Office` | office or seat distinct from its current holder |
| `Principal` | issuer-qualified person, service identity or legally recognized body identity |
| `Appointment` | election, appointment, designation or qualification event linking principal to office/seat |
| `VacancyOrTrigger` | event activating acting or emergency authority |
| `DelegationInstrument` | signed/versioned grant of a defined power or subset |
| `RecognitionRule` | legal/trust gateway allowing specified reliance on an external assertion |
| `ExternalAct` | external consultation, recommendation, approval, decision, certificate or status assertion |
| `DecisionForum` | board, plenary, committee, written-consent procedure or other legally identified forum/mode |
| `MeetingSession` | session identity and event timeline, not merely a minutes document |
| `DecisionItem` | exact motion, proposal or decision event inside a session |
| `ParticipationEvent` | join, leave, disconnect, reconnect, recusal, vote-open, vote-cast and vote-close event |
| `ConflictRecord` | disclosed, detected or indicated conflict facts and their sources |
| `RecusalOrManagementDecision` | competent decision applying recusal, waiver or management measures |
| `SeparationRequirement` | incompatible roles and the controlling-subject comparison rule |
| `AmountValuation` | economic transaction identity, currency, aggregation and valuation result |
| `EmergencyPredicate` | trigger, necessity/urgency decision and exceptional scope |
| `RevocationOrInvalidationEvent` | creation, legal effect and observation of a negative authority event |
| `ActEffectProfile` | formal type, binding effect, condition precedent and operative decision-maker |
| `EvidenceAssertion` | typed statement from a named producer with provenance, time and evidence ref |

## 5. Edge vocabulary and non-collapse

Candidate edge kinds:

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

The graph must not replace these with one `AUTHORIZED_BY`, `APPROVED_BY` or `TRUSTED` edge. Their
issuer competence, temporal behavior and legal consequences differ.

## 6. Common claim envelope for every node and edge

Every load-bearing graph statement carries:

```yaml
claim_envelope:
  claim_id: stable identifier
  claim_type: namespaced token
  subject_ref: graph node or edge
  assertion: canonical typed payload
  source_jurisdiction: required for legal claims
  governing_instrument_ref: optional/required by profile
  rule_version_ref: required
  origin:
    producer_id: named producer, never requester
    issuer_id: external or internal issuer
    source_class: legal_register | appointment_register | meeting_system |
      conflict_register | declaration | transaction_ledger | identity_provider |
      recognition_register | PolicyOS_recomputation | other_typed_source
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

`institutionally_supplied` describes the fact's origin relative to PolicyOS. It cannot alone produce
an authority-grade positive. Admission must verify the issuer, signature, content binding, scope,
currentness and applicable profile so the gate predicate is `recomputed` or
`independently_reconciled`. `consumer_asserted`, `institutionally_supplied` and `not_established`
remain non-positive under W4-K02/P37.

## 7. Required independent producers

Every decisive certificate field has a producer distinct from the requester.

| Predicate | Required producer or verifier | Requester statement treatment |
| --- | --- | --- |
| exact decision/effect commitment | PolicyOS canonicalizer over resolved immutable input | candidate only |
| actor/key/tenant identity | verified identity issuer plus DS20 principal binding | cannot override verified identity |
| office/seat holder | appointment/election register or signed constitutive record plus verifier | assertion alone is non-positive |
| root legal power and reserved matters | jurisdiction/legal-profile owner over versioned sources | prose citation is non-positive |
| delegation/subdelegation | delegation-register or signed instrument resolver plus chain verifier | inline grant forbidden |
| amount and aggregation | transaction/contract/budget owner plus recomputing valuation procedure | submitted amount cannot settle total value |
| place and subject matter | authoritative object/territory registry plus profile | free-text scope is non-positive |
| forum and decision mode | body constitution/profile plus meeting-system identity | role label cannot create forum |
| roster and participation | appointment register plus event-sourced meeting record | minutes conclusion alone is insufficient |
| quorum and vote | PolicyOS recomputation from admitted roster/events under profile | chair's `quorum=true` is evidence only |
| co-signature | external signature verifier plus rule profile | number of signatures cannot imply purpose |
| proposer/contributor/executor/reviewer | transaction/workflow lineage owner | user-selected role labels are non-positive |
| registered conflicts | interest/conflict register resolver | self-declaration supplements but does not replace register check |
| undisclosed-conflict declaration | participant attestation, with issuer/time binding | bounded human assertion, never proof of absence |
| recusal/waiver/management | competent adjudicator or authorized ethics owner | conflicted subject cannot be sole producer |
| emergency trigger/necessity | named emergency source and competent determiner | `emergency=true` from caller is forbidden |
| revocation/currentness | status/revocation register and dependency index | cached request field is non-positive |
| cross-agency recognition | recognition-rule owner plus accepting body's own acceptance producer | source agency cannot self-authorize local effect |
| act effect and operative maker | versioned jurisdiction profile plus independently verified source act | UI verb/title is diagnostic only |
| certificate result | PolicyOS graph reducer | caller cannot construct positive result |

Where the producer or adjudicator does not exist, the result is a typed refusal or
`not_established`, not an exception and not a silent fallback.

## 8. Authority path reduction

### 8.1 Root-to-actor validation

For each candidate path from a trusted root to the actor/body:

```text
effective_scope    := root_scope
effective_validity := root_validity
remaining_depth    := root_depth_limit

for each link from root toward actor:
    verify exact issuer identity and signature
    verify issuer equals the prior subject/authorized grantor
    verify the prior link allowed this type of delegation
    verify the grantor held the power to create this link at creation_time
    verify link and all activation conditions at decision_time
    verify every mandatory constraint is understood
    verify no applicable revocation/suspension/supersession event

    effective_scope    := intersection(effective_scope, link.scope)
    effective_validity := intersection(effective_validity, link.validity)
    remaining_depth    := reduce_and_check(remaining_depth, link)

    reject this path if scope or validity becomes empty
```

A child cannot amplify its parent. Unknown mandatory constraints reject the path. One invalid path
does not destroy an independent valid path; authority fails only when no qualifying path remains or
the profile requires a conjunction the surviving paths cannot satisfy.

### 8.2 Acting, succession and emergency

An acting path additionally requires:

- the activating vacancy/absence/trigger;
- the correct succession or designation rule at that time;
- holder qualifications and disqualifications;
- nomination or other event restrictions where applicable;
- office-specific scope and saving provisions;
- end conditions and currentness.

An emergency path additionally requires a named exceptional source, competent issuer, trigger,
scope, necessity/urgency decision where the profile requires it, expiry/end condition and mandatory
post-event evidence. Emergency authority is never a permanent expanded role.

### 8.3 Amount and anti-splitting

```text
economic_transaction_total :=
    base_commitment
    + counted variations
    + counted options
    + related orders or instalments
    + counted associated liabilities
    + taxes or exclusions under valuation_rule

authorized_amount :=
    currency_normalization_valid
    ∩ economic_transaction_total <= effective_amount_limit
    ∩ budget_scope_contains_transaction
```

The valuation rule and transaction identity are certificate dependencies. A change to either
requires revalidation.

## 9. Collegial-body reduction

A body path is evaluated per exact decision item, never only per meeting:

1. resolve the legally competent body and actual forum/mode;
2. resolve authorized seats and lawful holders at the decision time;
3. apply item-specific conflicts, recusals and other eligibility exclusions;
4. replay participation events under the profile's legal presence test;
5. calculate the quorum denominator and threshold at the required temporal scope;
6. validate each vote branch and the vote-result rule;
7. validate written-consent or alternative-mode requirements when used;
8. validate constitutive authentication/co-signature separately;
9. preserve any applicable saving/cure rule without backdating the original result.

A threshold proof contains the identities and valid authority branches used to satisfy `k-of-n`; it
is not merely `approval_count = k`. If one used branch is invalid, the threshold is recomputed.

`actual_forum != competent_forum` is a hard pre-action refusal even when the same people sit in both.

## 10. Separation of duties and conflict reduction

### 10.1 Controlling subject

All role comparisons resolve to a controlling-subject identity that closes aliases, delegated-user
sessions, impersonation and other equivalent identities. Account inequality is not independence.

### 10.2 Structural separation

The jurisdiction/process profile names the incompatible role pairs and whether they are static,
dynamic per transaction, or both. At minimum, `self_approval` is non-waivable:

```text
controlling_subject(proposer_or_material_contributor)
    != controlling_subject(final_approver)
```

Reviewer separation in DS9 is retained as one narrow predicate and generalized only when a complete
transaction-lineage producer exists.

### 10.3 Conflict status and detectability

The reducer outputs separate facts:

- prohibited role overlap found/not found;
- registered conflict found/not found;
- record-indicated conflict requiring adjudication;
- current declaration received/missing;
- competent recusal/waiver/management decision present/missing;
- undisclosed/off-system conflict absence **not provable**.

A positive certificate states its record boundary. It never claims psychological neutrality or the
absence of information not available to the named systems.

If the applicable regime requires a competent adjudicator and none is appointed, return
`ADJUDICATOR_UNAPPOINTED` or `CONFLICT_DETERMINATION_NOT_ESTABLISHED`. Do not borrow the requester,
chair or PolicyOS as adjudicator.

## 11. Cross-agency reliance reduction

For every external act, compute:

```text
acceptance :=
    legal_gateway_applies
    ∩ source_identity_and_competence_verified
    ∩ act_type_and_current_status_verified
    ∩ scope_and_purpose_match
    ∩ authenticity_and_required_assurance_verified
    ∩ no_refusal_ground_triggered
    ∩ accepting_body_residual_duties_completed
    ∩ responsibility_allocation_complete
```

The graph stores both `recognised_as` and `not_recognised_as`. Identity, authenticity, qualification
or origin can be accepted without accepting truth, substantive validity, local authorization or
competence to bind the accepting institution.

## 12. Act-effect classification

The classification follows the governing profile and consequences, not the word on the button:

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

A recommendation followed automatically by a downstream system is flagged for possible hidden
binding effect, but adoption rate alone does not change the formal type. An approval that creates
legal effect can itself be the binding decision under the applicable profile.

## 13. Freshness and mid-operation semantics

### 13.1 Freshness horizon

```text
fresh_until = min(
    path_expiry,
    revocation_status_next_update,
    appointment_or_attribute_expiry,
    conflict_declaration_expiry,
    meeting_or_decision_record_expiry_if_any,
    recognition_status_expiry,
    jurisdiction_policy_lease,
    requested_effect_deadline
)
```

`fresh_until` is an evidence bound, not a guarantee that no revocation can occur sooner.

### 13.2 Permitted modes

The certificate records exactly one profile-selected mode:

- `snapshot_by_explicit_rule` — only where the governing regime protects an operation already
  validly commenced;
- `issuer_authorized_lease` — only where the issuer may legally make the authority non-revocable or
  limited-revocable until a stated time;
- `revalidate_before_commit` — default for revocable authority;
- `continuous_checkpoint_revalidation` — required for long-running multi-effect operations where
  intermediate authority changes matter.

A caller cannot choose the least restrictive mode.

### 13.3 Revocation before and after effect

If a legally effective revocation arrives before an irreversible effect:

- invalidate the commit authorization;
- persist the refusal and dependency event;
- prevent the effect;
- preserve candidate/demo behavior outside the authority band where allowed.

If it arrives after an irreversible effect:

- do not claim rollback when none occurred;
- stop later dependent effects;
- append invalidation/incident evidence;
- route reissue, withdrawal, correction and external remedy under their owners;
- preserve the historical certificate and its original as-of proposition.

## 14. `DelegationValidityCertificate` result union

This local union is an input to the one Atlas/system lattice. It is not a new global status system.
The DS4/status owner must define any projection mapping later.

```yaml
DelegationValidityCertificate:
  certificate_id: content-addressed identifier
  schema_version: research candidate
  local_result: pre_action_valid | refused | not_established | not_applicable
  issued_at: timestamp
  as_of: timestamp
  fresh_until: timestamp
  revalidation_mode: profile-selected value
  decision_commitment: exact canonical hash
  effect_commitment: exact operation/resource/parameter hash
  principal_or_body:
    principal_ref: optional
    body_ref: optional
    office_or_role_refs: [refs]
  graph:
    graph_id: ref
    graph_root_hash: sha256
    jurisdiction_profile_refs: [refs]
    rule_profile_refs: [refs]
  effective_authority:
    surviving_path_refs: [refs]
    subject_matter_scope: canonical set
    amount_scope_ref: optional
    place_scope_ref: optional
    valid_interval: intersection
    legal_effect_ref: ref
  predicate_receipts:
    - predicate_id
      result: satisfied | failed | not_established | not_applicable
      producer_ref
      evidence_refs
      predicate_provenance
      evaluated_at
      fresh_until
  dependency_refs: [every mutable ancestor/status source]
  refusal_codes: [stable local reason codes]
  missing_role_or_owner_refs: [refs]
  limitations: [bounded claim limitations]
  authoritative_for:
    - this exact pre-action authority proposition
  may_not_use_for:
    - any other decision or effect
    - individual-case authorization under PAO-R4
    - legal-sufficiency claim outside the named profiles
  custody_proof:
    PolicyOS_component_id
    policy_hash
    reducer_version
    graph_root_hash
    technical_signature_or_attestation_ref
```

A positive certificate is single-purpose and replay-bound. A change to any committed field or
mutable dependency requires revalidation or a new certificate.

## 15. Refusal vocabulary

Candidate local reason codes include:

```text
MISSING_APPOINTED_HOLDER
APPOINTMENT_NOT_CURRENT
JURISDICTION_PROFILE_MISSING
AUTHORITY_ROOT_NOT_ESTABLISHED
AUTHORITY_PATH_INVALID
SUBDELEGATION_NOT_PERMITTED
DELEGATION_EXPIRED
DELEGATION_REVOKED
SUBJECT_MATTER_OUT_OF_SCOPE
AMOUNT_SCOPE_NOT_ESTABLISHED
AMOUNT_LIMIT_EXCEEDED
FORUM_NOT_COMPETENT
COMPOSITION_NOT_ESTABLISHED
QUORUM_NOT_MET_AT_DECISION
QUORUM_LOST_AT_DECISION
VOTE_THRESHOLD_NOT_MET
REQUIRED_COSIGNATURE_MISSING
SELF_APPROVAL
SEPARATION_OF_DUTIES_FAILED
CONFLICT_RECORD_UNRESOLVED
CONFLICT_DETERMINATION_NOT_ESTABLISHED
ADJUDICATOR_UNAPPOINTED
EMERGENCY_PREDICATE_NOT_ESTABLISHED
CROSS_AGENCY_ACCEPTANCE_NOT_ESTABLISHED
ACT_EFFECT_NOT_ESTABLISHED
AUTHORITY_NOT_PREEXISTING
CERTIFICATE_STALE
REVALIDATION_REQUIRED
REVOCATION_OBSERVED_BEFORE_EFFECT
DECISION_OR_EFFECT_COMMITMENT_MISMATCH
```

The final registered vocabulary, namespaces and projection consequences remain downstream design
work.

## 16. Unappointed-holder behavior

The institution currently has no appointed holders for several authority roles. The graph models a
required role independently of its holder:

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
refusal_codes: [MISSING_APPOINTED_HOLDER]
missing_role_or_owner_refs: [exact role]
```

This is a normal typed output, not an exception and not a disabled feature. Candidate computation,
demo surfaces and negative-path replay remain available under the authority-band/candidate-band
split. When a holder is later appointed, the same graph and certificate model consume the new
appointment evidence; no schema or rule redesign is required.

A positive result cannot be manufactured by substituting a team name, repository maintainer,
runtime role or adjacent signer for the missing institutional holder.

## 17. Historical replay

Replay preserves two different questions:

1. What did the certificate establish under the rules and evidence admitted at `as_of`?
2. What is the certificate's current standing after later revocation, correction, law change or
   discovery of a prior defect?

The historical result is immutable. Later knowledge appends invalidation, supersession, correction
or current-status evidence; it does not rewrite the original graph or pretend later authorization
existed before the decision.

## 18. Canonical-owner map and reuse path

| Concern | Existing owner to extend/reuse | Research conclusion |
| --- | --- | --- |
| operational mandate/delegation | `runtime/quality/design_axes/mandate_bounded_delegation.py`; `agent_action_authority.py` | extend, do not replace |
| human decision intake/currentness/persistence | DS9 `human_decision_contracts.py` and `human_decisions.py` | natural certificate consumer and revalidation chokepoint |
| operation/resource/permission enforcement | DS20 authorization/resource-binding/step-up/Rego owners | retain as narrow enforcement floor |
| acquisition approval | `routes/control.py::ingest_data` plus DS9/PA2 composition | first candidate consumer seam |
| CAS, signatures, event/audit/idempotency | existing runtime owners | reuse |
| jurisdiction/legal power profiles | no complete owner in this chain | external dependency plus later owner decision |
| appointments and body constitution | external institution | INTEGRATE contract; no PolicyOS appointment function |
| meeting/quorum evidence | external body/meeting system | INTEGRATE event contract |
| COI/recusal adjudication | external ethics/governance authority | INTEGRATE; absent adjudicator stays visible |
| recognition and act effect | external legal/governance source plus accepting-body producer | INTEGRATE and recompute |
| Atlas rendering/DS14 | Atlas owner | projection/consumer only |
| individual-use firewall | PAO-R4 | separate and mandatory where applicable |

This research establishes no new canonical owner. Until a later design/implementation act allocates
the complete chain, capability standing remains `absent/unallocated`.

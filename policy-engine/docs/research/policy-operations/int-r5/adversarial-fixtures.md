# INT-R5 Red-First Authority Fixtures — Amended

## 1. Fixture contract and reason identity

These fixtures specify behavior for a future implementation. They do not authorize code, register
wire types or allow a test to pass by constructing a refusal object in isolation. Every fixture must
run through the real graph reducer, the currentness/persistence bridge and one real protected-effect
consumer.

Research-oracle reason identities use:

```text
polisyos.int_r5.reason.<slug>@0.1.0-candidate
```

They are namespaced/versioned candidate semantic IDs. They are not aliases for another family's live
blocker and must be mapped by the future registered crosswalk before implementation. In particular:

```text
polisyos.int_r5.reason.certificate_stale@0.1.0-candidate
```

is a semantic sibling of, not currently an alias for:

```text
polisyos.eval_safety.certificate_stale@1.0.0
```

Common assertions for every refusing fixture:

- no `pre_action_valid` certificate is emitted;
- no protected effect occurs;
- DS20 allow or fresh step-up cannot compensate for failed institutional authority;
- a PAO-R4 receipt cannot compensate for failed INT-R5 authority, and vice versa;
- exact failed predicate, producer, evidence refs and reason identity are visible;
- unrelated-field mutation does not change the result;
- a valid near-pass succeeds without weakening another predicate;
- historical replay reproduces the original result under pinned evidence/rules;
- graph and output are bound to one exact decision and effect commitment;
- a valid hash never upgrades caller-authored or otherwise non-positive provenance.

## 2. Fixture F1 — self-approval

### 2.1 Property

One controlling subject may not materially propose or produce a decision and then serve as final
approver where the applicable profile requires independent approval. Disclosure cannot cure the
structural incompatibility.

### 2.2 Given

```yaml
decision:
  decision_id: purchase-17
  type: approve_purchase
  amount: 40000 EUR
  proposer_principal: issuer-A::person-7
  material_contributors: [issuer-A::person-7]
  requested_approver: issuer-A::person-7-alt-account
identity_equivalence:
  issuer-A::person-7-alt-account:
    controlling_subject: issuer-A::person-7
profile:
  incompatible_roles:
    - [proposer_or_material_contributor, final_approver]
  self_approval_waivable: false
runtime:
  exact_permission: present
  DS20_admission: valid
  step_up: fresh
```

### 2.3 When

The reducer resolves transaction lineage, identity equivalence and the separation profile before the
approval effect.

### 2.4 Then

```yaml
local_result: refused
reason_ids:
  - polisyos.int_r5.reason.self_approval@0.1.0-candidate
  - polisyos.int_r5.reason.separation_of_duties_failed@0.1.0-candidate
failed_predicate: final_approver_independent_of_proposer_and_contributors
protected_effect_count: 0
```

`conflict_disclosed=true`, a higher runtime role or new MFA cannot change the result.

### 2.5 Near-pass

Replace the final approver with `issuer-A::person-9`; prove no controlling-subject equivalence; prove
that actor's own authority path; keep all other admitted inputs byte-identical. The separation
predicate may pass.

### 2.6 Mutations

- alternate account, service impersonation or delegated-user session for the same subject;
- formal author differs but approver is a material contributor;
- display-name mutation only;
- conflicted actor attempts to issue their own exception;
- two distinct people share one credential: identity is `not_established`, not independent.

## 3. Fixture F2 — expired delegation and authoritative decision time

### 3.1 Property

The path must be valid at an independently established legally relevant decision time and every
required pre-effect checkpoint. Runtime permission cannot revive an expired grant, and a caller may
not backdate the decision into a valid interval.

### 3.2 Given

```yaml
delegation:
  instrument_id: delegation-55
  valid_from: 2026-08-01T00:00:00Z
  valid_until: 2026-08-28T23:59:59Z
  status: active
  scope: approve_acquisition up to 50000 EUR
caller_candidate:
  decision_time: 2026-08-28T23:59:00Z
constitutive_decision_event:
  decision_time: 2026-08-29T09:00:00Z
  producer: decision-event-system
  verifier_receipt: valid
effect_commit_event:
  effect_time: 2026-08-29T09:00:05Z
  producer: protected-effect-ledger
runtime:
  identity: valid
  exact_permission: evidence.acquire
  step_up: fresh
```

### 3.3 When

The canonicalizer can validly hash both timestamps, but the reducer admits only the constitutive event
producer's timestamp and intersects all path intervals at that time.

### 3.4 Then

```yaml
local_result: refused
reason_ids:
  - polisyos.int_r5.reason.delegation_expired@0.1.0-candidate
  - polisyos.int_r5.reason.caller_time_not_authoritative@0.1.0-candidate
surviving_path_count: 0
protected_effect_count: 0
```

### 3.5 Near-pass

The constitutive decision event and effect commit event both occur inside the effective interval and
no revocation/status event applies. The path may pass.

### 3.6 Mutations

- child expires after parent: effective expiry remains the minimum;
- parent expired but child record says active;
- expiry is event-triggered by vacancy fill;
- cached envelope is active while status source is expired;
- fresh MFA after expiry;
- caller edits `valid_until` without a new admitted instrument;
- timestamp is canonical and signed by the requester but not by the time/event producer.

## 4. Fixture F3 — wrong forum

### 4.1 Property

Membership equivalence is not organ equivalence. The actual body/forum/mode must be competent for the
matter under the applicable profile.

### 4.2 Given

```yaml
matter:
  decision_id: reserved-capital-decision
  competent_forum: full_board
  delegable_to_committee: false
actual_event:
  forum: finance_committee
  participants: [director-A, director-B, director-C]
  signatures_present: true
  apparent_quorum_if_treated_as_board: true
profile:
  jurisdiction: profile-example
  governing_instrument_ref: constitution-v4
```

### 4.3 When

The reducer resolves `REQUIRES_FORUM`, actual legal capacity and the reserved-matter rule before
calculating quorum.

### 4.4 Then

```yaml
local_result: refused
reason_ids:
  - polisyos.int_r5.reason.forum_not_competent@0.1.0-candidate
failed_predicate: actual_forum_equals_competent_forum_for_matter
quorum_result: not_applicable_to_wrong_forum
protected_effect_count: 0
```

### 4.5 Near-pass

A properly constituted full-board event uses the same people, correct forum identity, permitted
mode/notice and valid item-level quorum/vote.

### 4.6 Mutations

- plenary members acting as caucus;
- full board using a forbidden decision mode;
- committee with general delegation acting on reserved matter;
- two external signatures without competent internal act;
- one virtual meeting link reused under another legal capacity.

## 5. Fixture F4 — quorum loss under profile-relative time

### 5.1 Property

Quorum is recomputed for each decision item at the temporal scope selected by the jurisdiction/body
profile. Opening quorum is not a permanent meeting property.

### 5.2 Given

```yaml
meeting:
  meeting_id: board-2026-08-29
  competent_forum: full_board
  authorized_seats: 5
  quorum_rule:
    threshold: 3
    temporal_scope: at_vote
  events:
    - {time: 10:00:00Z, type: join, member: A}
    - {time: 10:00:01Z, type: join, member: B}
    - {time: 10:00:02Z, type: join, member: C}
    - {time: 10:00:03Z, type: join, member: D}
    - {time: 10:20:00Z, type: leave, member: C}
    - {time: 10:21:00Z, type: recusal_begin, member: D, item: item-7}
    - {time: 10:22:00Z, type: vote_open, item: item-7}
    - {time: 10:23:00Z, type: vote_close, item: item-7}
```

### 5.3 When

The reducer replays events, applies item-specific eligibility and computes quorum under the selected
profile at the required point(s).

### 5.4 Then

```yaml
local_result: refused
reason_ids:
  - polisyos.int_r5.reason.quorum_lost_at_decision@0.1.0-candidate
  - polisyos.int_r5.reason.quorum_not_met_at_decision@0.1.0-candidate
eligible_participants_at_decision: [A, B]
required_quorum: 3
protected_effect_count: 0
```

A signed minute saying `quorum present` remains evidence, not the recomputed result.

### 5.5 Required profile variants

The same event stream must be run under:

1. `at_vote`;
2. `throughout_meeting`;
3. `presumptive_until_challenged`.

A single global result for all three profiles is a fixture failure.

### 5.6 Near-pass and mutations

Near-pass: C remains through vote close or an eligible replacement lawfully joins before the vote.
Mutations include remote communications failure, abstainer present without affirmative vote,
conflicted member incorrectly counted, vacancy-dependent denominator and invalid written consent.

## 6. Fixture F5 — post-hoc cure without historical mutation

### 6.1 Property

A pre-action certificate cannot be created or backdated from authority granted after the original
decision. A later cure is a separate event/result whose temporal legal effect is profile-specific and
may include relation back.

### 6.2 Given

```yaml
decision:
  decision_id: commitment-88
  made_at: 2026-08-29T11:00:00Z
original_actor:
  authority_at_decision: false
later_event:
  type: ratification_or_cure
  made_at: 2026-08-29T14:00:00Z
  ratifier_authority: true
profile:
  cure_semantics: profile_parameter
```

### 6.3 Historical invariant

```yaml
original_certificate:
  local_result: refused
  reason_ids:
    - polisyos.int_r5.reason.authority_not_preexisting@0.1.0-candidate
  issued_as_if_at_11_00: forbidden
  historical_certificate_mutated: false
protected_effect_before_valid_cure: 0
```

The later event is not inserted into the 11:00 snapshot.

### 6.4 Separate cure result

Every new cure evaluation must emit:

```yaml
cure_effect:
  kind: prospective | relation_back | saved_act | limited | unresolved
  legally_effective_from: timestamp | event_ref | unresolved
  affects_original_legal_effect: yes | no | qualified | unresolved
  protected_interval_or_scope: optional profile-qualified value
  source_profile_ref: required
  competent_cure_actor_ref: required or not_established
  historical_certificate_mutated: false
```

Required variants:

- `prospective`: current/future effect only;
- `relation_back`: profile deems the cured act effective from an earlier point while the historical
  certificate still records absence of pre-existing authority;
- `saved_act`: statute preserves effect without pretending a later grant existed earlier;
- `limited`: only named scope/period/intermediate acts are protected;
- `unresolved`: no competent profile/adjudication establishes effect;
- non-ratifiable: refusal remains.

No fixture may deny relation-back regimes universally or convert relation back into a backdated
certificate.

### 6.5 Near-pass and mutations

Near-pass: a valid authority path exists before 11:00. Mutations cover unauthorized ratifier,
additional uncured defect, missing condition precedent, current-state historical replay, work begun
before grant and a backdated approval record.

## 7. Producer-independence fixture family

### 7.1 F6 — effect-class downgrade

```yaml
authoritative_effect_profile: irreversible
caller_candidate: reversible
canonical_hash_valid: true
expected:
  local_result: refused
  reason_ids:
    - polisyos.int_r5.reason.effect_class_mismatch@0.1.0-candidate
  protected_effect_count: 0
```

The effect-classification profile owner, not the caller, is decisive.

### 7.2 F7 — jurisdiction profile shopping

```yaml
applicability_resolver: jurisdiction-strict-v3
caller_candidate: jurisdiction-permissive-v1
both_refs_well_formed: true
expected:
  local_result: refused
  reason_ids:
    - polisyos.int_r5.reason.profile_applicability_mismatch@0.1.0-candidate
```

Unknown/conflicting mandatory applicability returns `not_established`; it never selects the most
permissive profile.

### 7.3 F8 — revalidation-mode downgrade

```yaml
profile_and_effect_class_derive: revalidate_before_commit
caller_candidate: snapshot_by_explicit_rule
expected:
  local_result: refused
  reason_ids:
    - polisyos.int_r5.reason.revalidation_mode_mismatch@0.1.0-candidate
```

### 7.4 F9 — valid hash, non-positive provenance

A requester supplies correctly canonicalized amount, recipient, time and profile refs, but no
admitted producers. Expected result is `not_established`; integrity cannot substitute for provenance.

## 8. PAO-R4 two-direction fixture family

### 8.1 F10 — authority valid, PAO-R4 missing

```yaml
target: individual_case_or_pointwise_recoverable
INT_R5_certificate: pre_action_valid
DS20_admission: valid
PAO_R4_receipt: missing
expected:
  protected_effect_count: 0
  reason_ids:
    - polisyos.int_r5.reason.pao_r4_receipt_missing@0.1.0-candidate
```

### 8.2 F11 — PAO-R4 valid, authority missing

```yaml
target: individual_case_or_pointwise_recoverable
PAO_R4_receipt: valid
DS20_admission: valid
INT_R5_certificate: missing_or_refused
expected:
  protected_effect_count: 0
  reason_ids:
    - polisyos.int_r5.reason.institutional_authority_missing@0.1.0-candidate
```

These fixtures keep owners separate. Neither receipt can be manufactured or inferred by the other's
consumer.

## 9. Acquisition topology fixture

### 9.1 Current-baseline red

At baseline `dc7bdf79a`, the real `ingest_data -> run_data_ingestion` path has DS20 permission/resource
binding and `ACQUISITION_APPROVAL` step-up but no PA2/DS9 institutional-authority bridge.

A semantic test against that real consumer must be red or explicitly unsupported:

```yaml
expected_current_baseline:
  can_express_full_INT_R5_pre_effect_chain: false
  acquisition_authority_bridge: missing
  production_positive_certificate_claim: forbidden
```

A test that passes because it calls the separate human-decision service without proving the
acquisition call edge is invalid.

### 9.2 Future acceptance

A future test may turn green only when the exact acquisition route consumes:

1. decision/effect commitment;
2. graph certificate/currentness receipt;
3. conditional PAO-R4 receipt where applicable;
4. DS20 exact admission;
5. effect count/readback proving no sibling bypass.

## 10. Extended adversarial matrix

| ID | Scenario | Expected result/observation |
|---|---|---|
| `F12` | required institutional role has no holder | `not_established` + `polisyos.int_r5.reason.missing_appointed_holder@0.1.0-candidate`; candidate lane remains |
| `F13` | adjudicator absent for disputed recusal | `not_established`; no borrowed maintainer/requester |
| `F14` | transaction split below amount limit | refused after aggregate valuation |
| `F15` | child scope wider than parent | offending path invalid; no amplification |
| `F16` | displayed successor title with invalid predecessor | descendant path invalid |
| `F17` | requester-only emergency | `not_established`; no permanent elevation |
| `F18` | authenticated foreign assertion used as local authority | refuse; show `recognised_as`/negative perimeter |
| `F19` | recommendation automatically executed | refuse or act effect `not_established` |
| `F20` | revocation after certificate before effect | no effect; dependency event persisted |
| `F21` | revocation after irreversible effect | history retained; downstream stopped; no false rollback |
| `F22` | duplicate certificate use | second use refused by replay binding |
| `F23` | amount/recipient mutation | exact commitment mismatch; no partial acceptance |
| `F24` | one path revoked, independent path valid | positive only if alternate path independently satisfies all conjunctions |
| `F25` | conflict register unavailable | `not_established`, never positive |
| `F26` | late leave/recusal event | current certificate invalidated/revalidation required; original snapshot retained |
| `F27` | duplicate/out-of-order revocation | one idempotent governed transition |
| `F28` | conflicting appointment records | `not_established`; contradiction and owner named |
| `F29` | historical replay after profile change | original result plus separate current reinterpretation |

## 11. Benchmark, holdout and fault injection

The frozen public pack contains the mandatory five fixtures, all named profile variants, near-pass
controls, one mutation per decisive field, unappointed-holder, cross-agency negative perimeter,
title-versus-effect, producer-substitution and PAO-R4 two-direction cases.

The sealed holdout changes identities, edge order, titles, aliases and harmless metadata and includes
structurally novel equivalents. Oracle labels concern authority admissibility under declared profiles,
not ultimate legal truth.

Metrics:

```text
false_grant
false_refusal
wrong_reason_identity
missed_dependency
stale_certificate_use
commitment_replay_or_substitution
profile_collapse
post_hoc_backdating
unbounded_conflict_claim
PAO_R4_substitution
caller_fact_upgrade
```

`false_grant` is primary. A passing structural test without a real producer, bridge and consumer is
vacuous.

Required fault injections include provider loss before effect, delayed/duplicate/out-of-order
revocation, corrupted parent grant, removed quorum branch, late recusal, conflicting recognition,
guarded-store failure, profile change and mass root invalidation. Recovery must fail closed, remain
idempotent, preserve history and execute no protected effect without final currentness.

## 12. Red-first acceptance rule

For every fixture:

1. demonstrate current inability or unsafe behavior against the real consumer;
2. write the failing semantic/e2e test;
3. implement the smallest owner-first mechanism under separate authority;
4. show red before and green after;
5. run near-pass, mutations and sealed holdout;
6. prove no sibling consumer bypass;
7. read back persisted graph, receipt/events and exact effect count;
8. verify corruption of producer evidence, profile, time or commitment is detected.

A reason string alone is never proof that the property is enforced.

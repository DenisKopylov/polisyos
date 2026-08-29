# INT-R5 Red-First Authority Fixtures

## 1. Purpose and fixture discipline

These fixtures specify observable behavior for a later implementation. They do not authorize code
or freeze final wire types. Each fixture must exercise the real graph reducer and the real protected
consumer. A test that only constructs a refusal object or searches for a reason-code string does not
satisfy the fixture.

Common assertions for every refusing fixture:

- no `pre_action_valid` certificate is emitted;
- no protected effect occurs;
- no DS20 allow or fresh step-up can compensate for the failed institutional predicate;
- the exact failed predicate and evidence refs are visible;
- changing an unrelated field does not change the result;
- a valid near-pass control succeeds without weakening another predicate;
- historical replay reproduces the original result from the pinned rules/evidence;
- the fixture is bound to an exact decision and effect commitment.

## 2. Fixture F1 — self-approval

### 2.1 Property

One controlling subject may not materially propose or produce an exact decision and then act as its
final approver where the profile requires independent approval. Disclosure does not cure the
structural role incompatibility.

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
permissions:
  runtime_permission: present
  step_up: fresh_and_valid
```

The two accounts intentionally resolve to one controlling subject.

### 2.3 When

The reducer resolves transaction lineage, identity equivalence and the separation profile before the
approval effect.

### 2.4 Then

```yaml
local_result: refused
refusal_codes: [SELF_APPROVAL, SEPARATION_OF_DUTIES_FAILED]
failed_predicate: final_approver_independent_of_proposer_and_contributors
protected_effect_count: 0
```

The certificate must not downgrade the failure to a warning because `conflict_disclosed=true`, MFA
is fresh, or the approver has a higher runtime role.

### 2.5 Near-pass control

Replace the final approver with `issuer-A::person-9`, prove no identity-equivalence edge to the
proposer/contributors, prove the approver's own authority path and keep all other inputs byte-identical.
The separation predicate may then pass.

### 2.6 Mutation variants

- same person under service impersonation;
- same person through delegated-user session;
- approver not formal author but recorded as material contributor;
- proposer changes only display name;
- conflicted subject attempts to issue their own exception;
- two genuinely distinct actors share one credential: identity is `not_established`, not independent.

## 3. Fixture F2 — expired delegation

### 3.1 Property

The authority path must be valid at the legally relevant decision time and at every required
pre-effect checkpoint. A current runtime permission cannot revive an expired institutional grant.

### 3.2 Given

```yaml
delegation:
  instrument_id: delegation-55
  valid_from: 2026-08-01T00:00:00Z
  valid_until: 2026-08-28T23:59:59Z
  status: active
  scope: approve_acquisition up to 50000 EUR
decision_time: 2026-08-29T09:00:00Z
effect_time: 2026-08-29T09:00:05Z
principal:
  identity: valid
  runtime_permission: evidence.acquire
  step_up: fresh
```

### 3.3 When

The reducer intersects all path validity intervals and evaluates them at `decision_time`; the DS9
consumer re-resolves the raw path before effect.

### 3.4 Then

```yaml
local_result: refused
refusal_codes: [DELEGATION_EXPIRED]
surviving_path_count: 0
protected_effect_count: 0
```

No grace period is inferred from the actor's lack of notice. A profile may separately recognize a
specific legal saving rule, but it must be present and proven; it is not a default.

### 3.5 Near-pass control

Move `decision_time` and `effect_time` inside the interval while retaining every other field and
prove no revocation/status event. The path may pass.

### 3.6 Mutation variants

- child grant expires after parent: effective expiry remains the minimum;
- parent expires while child still says active;
- expiry depends on vacancy being filled rather than a fixed date;
- stale cached envelope says active while status source says expired;
- actor obtained fresh MFA after expiry;
- requester edits `valid_until` without a new signed instrument.

## 4. Fixture F3 — wrong forum

### 4.1 Property

Membership equivalence is not organ equivalence. The actual forum/mode must be competent for the
matter under the applicable profile.

### 4.2 Given

```yaml
matter:
  decision_id: reserved-capital-decision
  competent_forum: full_board
  delegable_to_committee: false
actual_event:
  forum: finance_committee
  participants:
    - director-A
    - director-B
    - director-C
  signatures_present: true
  apparent_quorum_if_treated_as_board: true
profile:
  jurisdiction: profile-example
  governing_instrument_ref: constitution-v4
```

All committee members are also directors. The fixture deliberately makes person identity and
signature appearance favorable.

### 4.3 When

The reducer resolves `REQUIRES_FORUM`, the actual meeting capacity and the reserved-matter rule
before considering the vote.

### 4.4 Then

```yaml
local_result: refused
refusal_codes: [FORUM_NOT_COMPETENT]
failed_predicate: actual_forum_equals_competent_forum_for_matter
quorum_result: not_applicable_to_wrong_forum
protected_effect_count: 0
```

The system must not attempt to rescue the act by saying that the same people could have formed a
full-board quorum.

### 4.5 Near-pass control

Create a legally constituted full-board decision event with the same participants, proper forum
identity, required notice/mode and a valid item-level quorum/vote. The forum predicate may pass.

### 4.6 Mutation variants

- plenary members acting as an informal caucus;
- full board using a decision mode not permitted by the governing instrument;
- committee with general delegation but matter appears on the reserved list;
- external document carries two signatures but no competent internal act;
- same virtual meeting URL reused for a different legal capacity.

## 5. Fixture F4 — quorum loss

### 5.1 Property

Quorum is recomputed at the temporal scope selected by the jurisdiction/body profile. Opening quorum
is not a permanent property of the meeting.

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

At vote time only A and B are eligible participants.

### 5.3 When

The reducer replays the event timeline, applies item-specific recusal and computes quorum under the
profile at `vote_open`/`vote_close`.

### 5.4 Then

```yaml
local_result: refused
refusal_codes: [QUORUM_LOST_AT_DECISION, QUORUM_NOT_MET_AT_DECISION]
eligible_participants_at_decision: [A, B]
required_quorum: 3
protected_effect_count: 0
```

A signed minute stating `quorum present` cannot override the recomputation.

### 5.5 Profile variants

The fixture family must include three explicit rule profiles:

1. `at_vote` — failure begins when the item is put without quorum;
2. `throughout_meeting` — failure begins when the required composition is lost;
3. `presumptive_until_challenged` — apply the profile's procedural challenge/count machinery rather
   than treating physical departure as automatic nullity.

The same event stream must produce profile-dependent results. A single global quorum algorithm is a
fixture failure.

### 5.6 Near-pass control

Member C remains through vote close, or an eligible replacement joins under a valid appointment and
participation rule before the vote. The reducer must recompute the exact branch set rather than edit
a count.

### 5.7 Mutation variants

- remote participant loses the legally required communications capability;
- abstainer remains present but does not supply an affirmative vote;
- conflicted member is incorrectly counted for both quorum and vote;
- vacancy changes denominator under one profile but not another;
- written consent is used instead of a meeting and fails its own unanimity/mode conditions.

## 6. Fixture F5 — post-hoc authorization

### 6.1 Property

A pre-action certificate cannot be created or backdated from authority granted after the decision.
Any later statutory cure is a separate event and separate result under a named jurisdiction profile.

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

### 6.3 When

The reducer is asked to issue a certificate for the original decision as of 11:00.

### 6.4 Then — invariant across profiles

```yaml
original_certificate:
  local_result: refused
  refusal_codes: [AUTHORITY_NOT_PREEXISTING]
  issued_as_if_at_11_00: forbidden
protected_effect_before_valid_cure: 0
```

The later event is never inserted into the 11:00 graph snapshot.

### 6.5 Separate cure outcomes

The fixture then evaluates a **new** graph under three profiles:

- `cure_permitted_if_conditions_satisfied` — emit a new current result only after every statutory
  condition and competent ratifier predicate passes;
- `cure_forbidden` — retain refusal, for example where the profile makes the action non-ratifiable;
- `cure_effect_not_established` — return `not_established` where the legal consequence is disputed or
  no competent profile/adjudication exists.

No profile may mutate the original certificate from refused to valid.

### 6.6 Near-pass control

A valid delegation exists and is effective before 11:00; the original decision is made within its
scope; no later cure is needed. The original pre-action result may pass.

### 6.7 Mutation variants

- ratifier had authority at 14:00 but not at 11:00;
- attempted cure fixes authority but another defect remains;
- cure instrument is signed but its condition precedent is missing;
- system uses current state to replay historical authority;
- actor starts work before grant and commits after grant;
- approval recorded after effect but timestamp is backdated.

## 7. Extended fixture matrix

| ID | Scenario | Expected result | Required observation |
| --- | --- | --- | --- |
| `F6` | valid individual delegation | `pre_action_valid` | exact path, scope, amount, identity, currentness and effect binding |
| `F7` | required institutional role has no holder | `not_established` + `MISSING_APPOINTED_HOLDER` | role and appointing authority named; demo path remains available |
| `F8` | required adjudicator absent for disputed recusal | `not_established` + `ADJUDICATOR_UNAPPOINTED` | no borrowed maintainer/requester adjudicator |
| `F9` | amount appears below limit only because invoices were split | refused + `AMOUNT_LIMIT_EXCEEDED` | economic transaction aggregation visible |
| `F10` | child grant widens parent amount or subject scope | refused + `AUTHORITY_PATH_INVALID` | intersection and offending edge visible |
| `F11` | successor's displayed title is valid-looking but predecessor path invalid | refused | root succession failure invalidates descendant path |
| `F12` | emergency flag supplied only by requester | `not_established` + `EMERGENCY_PREDICATE_NOT_ESTABLISHED` | no elevated authority or permanent role |
| `F13` | authenticated external assertion used as local authorization | refused + `CROSS_AGENCY_ACCEPTANCE_NOT_ESTABLISHED` | `recognised_as`/`not_recognised_as` and retained duties visible |
| `F14` | recommendation automatically executed as if binding | refused or effect `not_established` | operative act and ultimate maker unresolved |
| `F15` | revocation after certificate, before irreversible effect | refused + `REVOCATION_OBSERVED_BEFORE_EFFECT` | no effect; dependency event persisted |
| `F16` | revocation after irreversible effect | historical certificate retained; current state invalidated | no false rollback; downstream effects stopped |
| `F17` | duplicate certificate presentation | second use refused | replay store and exact effect commitment |
| `F18` | same certificate with amount/recipient changed | refused + commitment mismatch | no partial binding acceptance |
| `F19` | one authority path revoked, independent path valid | positive only if complete alternate path satisfies all conjunctions | path-level, not principal-level invalidation |
| `F20` | conflict register unavailable in degraded mode | `not_established`, never pass | degraded source named; candidate band may continue |
| `F21` | late meeting event arrives showing member left before vote | current certificate invalidated/revalidation required | original snapshot and correction both preserved |
| `F22` | duplicate revocation event | idempotent single transition | no double side effect or duplicate incident |
| `F23` | conflicting appointment records | `not_established` | contradiction and required adjudicator/owner named |
| `F24` | historical replay after law/profile change | reproduce original result and separately report current reinterpretation | no use of current rule as historical fact |

## 8. Benchmark proposal

### 8.1 Frozen public regression pack

The public pack contains:

- the five required fixtures;
- all profile variants explicitly named above;
- valid near-pass controls;
- one mutation per decisive field;
- one exact decision/effect commitment substitution test;
- one unappointed-holder test;
- one cross-agency negative-perimeter test;
- one act-type title-versus-effect test.

The oracle labels authority **admissibility**, not ultimate legal truth. Every fixture declares its
jurisdiction/profile and source assumptions.

### 8.2 Sealed holdout pack

The sealed pack changes names, edge order, document titles, account aliases and harmless metadata;
it also includes structurally novel but semantically equivalent instances. This prevents teaching a
checker to the literal witness names or refusal codes.

### 8.3 Metrics

```text
false_grant
false_refusal
wrong_refusal_reason
missed_dependency
stale_certificate_use
commitment_replay_or_substitution
profile_collapse
post_hoc_backdating
unbounded_conflict_claim
```

`false_grant` is the primary safety metric. A structural-only pass with no real consumer effect is
not a successful fixture run.

## 9. Tabletop and fault injection

A later implementation must execute, not merely discuss, the following drills:

1. kill the appointment/status provider after graph resolution but before effect;
2. delay a revocation event until after pre-action issuance but before commit;
3. deliver revocation twice and out of order;
4. corrupt one parent delegation while leaving the child signature valid;
5. remove the meeting event that establishes one required quorum branch;
6. send a late recusal event that changes both quorum and voting denominator;
7. return conflicting external-recognition status from two sources;
8. make the guarded store unavailable after validation;
9. change the jurisdiction profile between historical replay and current evaluation;
10. simulate a mass invalidation of one authority root and enumerate all dependent certificates.

Required recovery observations:

- no false grant during provider failure;
- typed `not_established` or revalidation-required state;
- idempotent event handling;
- preserved original graph/certificate;
- dependency-complete invalidation;
- no silent substitution of current law/state into historical replay;
- no effect without a final currentness checkpoint.

## 10. Red-first acceptance rule

For each fixture:

1. demonstrate the current implementation cannot express or enforce the property without the new
   graph/certificate chain;
2. write the failing semantic/e2e test against the real consumer;
3. implement the smallest owner-first mechanism;
4. show the named failure turns red before the fix and green after it;
5. run near variants and the sealed holdout;
6. prove no sibling consumer bypass exists;
7. read back persisted evidence and effect count.

A test that passes because the protected producer or consumer does not exist is vacuous and cannot
close a fixture.

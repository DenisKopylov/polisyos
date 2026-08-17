---
title: PAO-R36 - Formal Argument Audit
status: delivered_independent_audit
audit_id: PAO-R36
verified_commit: 1bccc012b636d6a13930735a4f748d1f8cf7b9cf
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
audit_branch: research/pao-r36-independent-audit
research_only: true
authoritative_for:
  - pao_r36_passes_iii_to_vi
  - pao_r36_two_boundary_argument_audit
  - pao_r36_completeness_and_falsifier_dispositions
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, media-type, or API contract
  - canonical owner, vendor, custodian, or service appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog, or system-design decision
---

# PAO-R36 formal argument audit

## 1. Executive formal verdict

The central idea is good: distinguish the append-only current-authority transition from the later,
bounded claim that controlled dissemination has completed. That construction is materially stronger
than either “one write means corrected everywhere” or unconstrained eventual consistency.

The submitted formal contract does not yet prove its own safety claim. Three defects are blocking:

1. the primary report orders `t_authority` before the authority fence and public notice, while the
   detailed contract requires both before `t_authority`;
2. the record set `R` contains the effective declaration while `Complete(R)` is a precondition for
   creating that declaration; and
3. the rule that determines whether affected-party receipt is synchronous can still be decided after
   the transaction starts.

A compliant implementer can therefore follow one submitted artifact and produce observations the
other artifact calls forbidden. This is a contract contradiction, not an implementation detail.

## 2. Pass III — two-boundary contract

### 2.1 The two boundaries are conceptually justified

The research defines:

- `t_authority`: the append-only current-head event; and
- `t_effective`: a later bounded declaration after synchronous fan-out verification
  (`pao-r36-public-correction-and-durable-notice.md:205-216`;
  `pao-r36/ordered-fanout-and-completeness-contract.md:61-82`).

This distinction answers a real distributed-consistency problem. Current authority can change at one
canonical owner before every independently failing projection/cache/feed has been observed. The later
boundary prevents that partial physical convergence from being misrepresented as completed
controlled dissemination.

### `PAO-R36-III-006` — commendation — the two-boundary construction should survive consolidation

The conceptual split is precise, useful, and not inherited from any external regime. It is the main
original contribution of PAO-R36.

### 2.2 The submitted order contradicts itself

The primary report says:

1. Step 8 transitions current authority;
2. Step 9 enforces the fence; and
3. Step 10 publishes the notice/version relation
   (`pao-r36-public-correction-and-durable-notice.md:218-253`).

The detailed contract says:

1. Step 3 creates a complete notice and requires it to become visible no later than the transition
   (`pao-r36/ordered-fanout-and-completeness-contract.md:178-199`);
2. Step 9 arms the authority fence and makes it a pre-authority gate
   (`:300-326`); and
3. Step 10 then appends `t_authority` (`:327-344`).

Both texts present themselves as the ordered contract. The detailed document is the safer one, but
nothing in the package declares it controlling over the primary step table.

### Sequence A — stale predecessor-current after a compliant authority transition

1. Freeze all denominators and stage the successor under primary Steps 0-7.
2. Execute primary Step 8: append `v2` as current at `t_authority`.
3. The process crashes before primary Step 9 arms the authority fence.
4. `public_page` continues serving the cached `v1` current response.
5. The implementation followed the primary order, yet the observer sees predecessor-current after
   `t_authority`, which the invariant forbids.

### Sequence B — successor-current without the public notice

1. Complete primary Steps 0-7, including an internally prepared but not yet public notice.
2. Append `t_authority` at primary Step 8.
3. A current API reads the canonical head and serves `v2` current.
4. Publication fails before primary Step 10 publishes the notice/version link.
5. The public observer sees successor-current without a resolvable public correction notice. That is
   expressly listed as dangerous at `pao-r36-public-correction-and-durable-notice.md:298-305`.

### `PAO-R36-III-001` — blocking — no single controlling order

The two sequences are compliant under one submitted artifact and forbidden under another. Reconcile
the package into one controlling order in which the notice is safely visible and the fence is armed
before the current-head append. A prose cross-reference to the detailed file is insufficient while
the primary table remains contradictory.

### 2.3 `Complete(R)` is self-referential

The primary report defines `R` to include “the effective declaration”
(`pao-r36-public-correction-and-durable-notice.md:258-267`). The detailed contract requires
`Complete(R)` before Step 12 appends that effective declaration
(`pao-r36/ordered-fanout-and-completeness-contract.md:357-379`).

There are only three readings, and none supports the submitted wording:

- the declaration does not yet exist, so `R` is incomplete and effect can never be declared;
- a draft declaration counts, so `Complete(R)` becomes partly self-attested by the object it is meant
  to authorize; or
- the declaration is excluded for the precondition, contradicting the stated membership of `R`.

### `PAO-R36-III-002` — blocking — circular effective gate

Split the pre-effect record/evidence closure from the effective-declaration event. The effective event
may join the historical record set only after it is appended; it cannot be a member of its own
precondition.

### 2.4 Synchronous versus asynchronous notification is not frozen

Step 0 freezes the `N` snapshot and identifies whether an institutional decision requires `P`
(`ordered-fanout-and-completeness-contract.md:113-125`). Step 8 later says the institutional
classifier decides whether members of `P` require actual receipt before effect (`:278-301`). The
primary table likewise says an adverse rule “may require” receipt (`pao-r36-public-correction-and-durable-notice.md:247-253`).

Freezing cohort membership is not the same as freezing the obligation applied to that cohort. A
classifier can initially admit delivery as asynchronous, observe failures, and then decide that the
case did not require pre-effect receipt. The denominator stays frozen while the decisive predicate
changes.

### `PAO-R36-III-003` — blocking — the effect-gate class can change after admission

The transaction must freeze, before `t_authority`, both cohort membership and the authorized
obligation class: no direct cohort; admission-before-effect; or receipt-before-effect. An unresolved
classification blocks. A later institutional amendment must be another append-only decision and
cannot retroactively manufacture a pass.

### 2.5 State-space partition

The primary predicate is:

`forall s in S, forall t >= t_authority: state(s,t) in {successor_current_linked, predecessor_historical_linked, unavailable_fail_closed}`

at `pao-r36-public-correction-and-durable-notice.md:284-310`.

As an abstract partition of **authority/currentness posture**, the three classes are sensible. As the
complete public-observation predicate, they are not exhaustive because `state` does not bind all
load-bearing dimensions. Reachable observations include:

- `successor_current_linked`, but linked to a staged, wrong, or superseded correction notice;
- `successor_current_linked` under an unauthenticated or stale `as_of` snapshot;
- `successor_current_linked` in one authoritative language while that language widens permission;
- `predecessor_historical_linked`, but linked to the wrong successor correction identity; and
- `unavailable`, while a separate convenience projection still asserts old-current authority.

Those observations can satisfy the three-label predicate while violating the intended invariant.
The prose separately forbids some of them, but a formal invariant is not the union of unbound prose
statements.

### `PAO-R36-III-004` — material — observation state is under-specified

Define the observation predicate over a tuple including at least correction identity, selected
version, currentness disposition, authenticated cutoff, notice relation/phase, projection parity, and
language parity. The three authority-posture labels can remain a projection of that tuple.

### `PAO-R36-III-007` — commendation — bounded mixed states are the right safety model

The rule that physical convergence may expose successor-current, predecessor-historical-with-link,
or fail-closed unavailable—while forbidding predecessor-current—is a strong and practical safety
invariant once the tuple binding and order defects are repaired.

### 2.6 Time order is asserted, not falsifiably enforced

Both main documents state `t_stage <= t_authority <= t_effective`. They do not define:

- append/event precedence independent of displayed timestamps;
- whether equal display timestamps are allowed and how order is then proved;
- a detector for an effective event appended before its member evidence;
- a detector for a later event carrying a backdated `effective_at`; or
- the rule that a derived surface cannot select an earlier effective time from stale evidence.

F13 checks version selection immediately before/after `t_authority`; it does not test append order or
backdating.

### `PAO-R36-III-005` — material — no event-order proof

Require an append-order predicate such as staging event precedes authority event precedes effective
event, and require the displayed times/cutoffs not to contradict that order. Add backdated,
equal-time, and stale-effective-snapshot attacks.

## 3. Pass IV — enumerated completeness

### 3.1 Claim inventory

The package's load-bearing completeness claims bind as follows:

| Claim | Declared denominator | Freeze point | Audit verdict |
| --- | --- | --- | --- |
| Every canonical transaction record/evidence item | `R` | Step 0 admission | Bound, but circular because `R` includes the effective declaration. |
| Every controlled authority-bearing public surface | `S` | Step 0 / controlled-surface snapshot | Properly named and frozen at admission. |
| Every controlled cache/variant serving `S` | `C` | Step 0 / cache inventory snapshot | Properly named and frozen at admission. |
| Every registered subscriber eligible at cutoff | `N` | Step 0 / subscriber snapshot | Properly named; actual receipt separately reported. |
| Every directly affected party required by an institutional rule | `P` | Separate institutional cohort decision | Membership can be frozen, but the receipt-before-effect obligation is not fixed early enough. |
| Every controlled correction-feed partition/projection | `F` | Step 0 / machine-consumer snapshot | Properly named and frozen. |
| Every archive/copy included in the bounded claim | `A` | Step 0 / archive-custody snapshot | Properly named and frozen. |
| Every authoritative language | `L` | Step 0 / D4 plus future INT-R6 admission | Properly named; mechanism correctly deferred. |
| Every signature/key/status/currentness item required for the reported outcome | `K` | Step 0 / INT-R7 closure | Properly named and outcome-relative. |
| “All subscribers notified” | `N` delivery receipts | Frozen `N` snapshot | Properly prohibited unless all member receipts qualify. |
| “All public copies/internet corrected” | none | none | Explicitly prohibited rather than asserted. |

No positive “all caches,” “all subscribers,” “all archives,” or “all public copies” claim was found
without one of the named sets. The structural denominator discipline therefore holds except for the
`R` circularity and the membership-churn problem below.

### 3.2 Controlled membership can grow after the snapshot

The contract freezes `S` and `C` at admission. It does not bind those snapshots to an immutable
registry/config generation that remains the only deployable/control-plane generation until
`t_effective`.

A compliant sequence can therefore be:

1. freeze `S0={page,api}` and `C0={page_edge,api_edge}`;
2. stage the correction;
3. deploy a new registered public route `download_current` or a new locale/cache variant after the
   cutoff;
4. transition authority and verify all members of `S0/C0`; and
5. declare effect while the new controlled member serves the predecessor as current.

The completion claim is true over its old denominator but no longer describes every controlled
surface at effect time. Treating the new member as an “external exclusion” would be dishonest because
PolicyOS controls it.

### `PAO-R36-IV-001` — material — no registry-generation/control-plane freeze

Bind the set snapshots to the actual controlled registry/config generation and prohibit unaccounted
membership changes until effect. A controlled membership change must extend/restart the transaction
or remain fail-closed; it cannot be silently excluded.

### `PAO-R36-IV-002` — commendation — uncontrolled copies are treated honestly

The package consistently excludes unknown browser copies, screenshots, third-party mirrors, search
indexes, and external caches, and F14 rejects any universal “internet cleared” statement
(`ordered-fanout-and-completeness-contract.md:102-105,459-467`;
`falsifier-suite.md:276-290`). No quiet universal implication was found.

### `PAO-R36-IV-003` — commendation — denominator discipline is structural

Snapshots carry identity, owner, membership rule, cutoff, exact/resolvable members, count, member
outcomes, exclusions, and independent recomputation. F16 removes one member result while preserving
green markers. This is materially stronger than a narrative “all systems updated” claim.

## 4. Pass V — hard cases

### 4.1 Risk-increasing correction

The fixture changes a threshold in the adverse direction and reaches a decidable protocol outcome:
unknown risk direction or missing affected-party decision blocks authority/effect; the predecessor is
preserved; the affected class and direction are disclosed without exposing protected identities; and
an institutional decision determines whether direct receipt is required
(`pao-r36/comparative-models-and-hard-cases.md:103-147`; F10 at
`pao-r36/falsifier-suite.md:211-226`).

### `PAO-R36-V-001` — commendation — adverse correction is worked, not merely named

The research correctly refuses the common assumption that correction always reduces harm. It does
not claim its notice is legally sufficient.

### 4.2 Legally significant old version

The fixture preserves `v1`, binds past decisions to exact version and `as_of`, makes `v2` the later
current default, and leaves voidness/reconsideration/grandfathering/remedy to a separate competent
institutional act (`comparative-models-and-hard-cases.md:148-184`).

### `PAO-R36-V-002` — commendation — prior-decision meaning is preserved

The outcome is operationally decidable: a past decision can retrieve and identify the exact version
it used without the correction pretending to settle the legal effect of that use.

### 4.3 Since-revoked signing key

The fixture keeps four propositions separate: content/signature match, issuance-time authorization,
compromise certainty, and present current authority. It preserves the original signature and signs
the successor under current authority, consuming INT-R7 rather than choosing algorithms, services,
or a new key owner (`comparative-models-and-hard-cases.md:185-230`).

### `PAO-R36-V-003` — commendation — revoked-key disposition consumes INT-R7 correctly

The worked table distinguishes pre-revocation issuance, unresolved compromise interval,
post-revocation unauthorized issuance, and missing/stale status. The result does not erase bytes or
turn historical authenticity into current authority.

## 5. Pass VI — falsifier suite

### 5.1 Per-fixture audit

| ID | Detector | Expected outcome audit | Verdict |
| --- | --- | --- | --- |
| F01 | Protected-query comparison across all `L` members | Separate pre-/post-authority outcomes are stated. It requires, but does not define, the future INT-R6 parity mechanism. | **Executable interface fixture.** |
| F02 | Query all 5/5 `S` members at one post-authority cutoff | Names attacked member, surface gate, no-effect, and incident. | **Executable.** |
| F03 | Compare stable `v1` identity/content and traverse successor relation | Pre-claim outcome is exact, but post-claim behavior is introduced conditionally (“If detected after a claim”). | **Split required.** |
| F04 | Probe all 4/4 cache members and corresponding surface | Exact post-effect response; preserves historical receipt while appending incident. | **Executable.** |
| F05 | Recompute from all 3/3 `N` members | Ordinary-subscriber outcome is exact, but `NO_EFFECTIVE` depends on whether the same member belongs to a pre-effect `P` rule. | **Split ordinary `N` and synchronous `P` fixtures.** |
| F06 | PV-K04 protected-query comparison | Pre-authority exact; post-authority uses `FAIL_CLOSED` without naming the member(s). | **Member-specific revision required.** |
| F07 | Round-trip traversal and content identity over 2/2 `A` | Phase-specific outcomes are explicit and member-bound. | **Executable.** |
| F08 | Recompute one current head and query all `S` | Expected outcome is conditional on phase and uses `FAIL_CLOSED(S)` although the outcome vocabulary requires a member. It covers simultaneous forked heads, not serialized stale-base correction. | **Split and extend.** |
| F09 | Evaluate issuance-time authorization, key status, compromise interval, and GY-N12 currentness separately | Both laundering directions have one exact red outcome and no current positive. | **Executable and substantive.** |
| F10 | Semantic effect comparison plus institutional decision inspection | Exact pre-authority blockers. | **Executable.** |
| F11 | Compare restored append order/head/notice/safe states | Uses `FAIL_CLOSED(S)` rather than named members and assumes an incident can be appended without saying by which surviving authority path. | **Member/outcome clarification required; seam attack itself is valid.** |
| F12 | Resolve frozen `N`, not live registry | Exact red aggregate against denominator 3. | **Executable.** |
| F13 | Query immediately before/after `t_authority` | Attack is a disjunction; “no effective completeness” is ambiguous after an already-effective declaration. It does not test event append order/backdating. | **Split into historical-query and current-query variants; add event-order attack.** |
| F14 | Compare assertion to `S`, `C`, exclusions | Exact rejection of amplified universal claim. | **Executable.** |
| F15 | Traverse notice to successor across exposing `S/F/A` members | Explicit pre-/post-authority outcomes and attacked member set. | **Executable.** |
| F16 | Independently join frozen `C` to member-bound evidence | Exact removal-of-one-member failure while aggregate markers remain. | **Executable and strong.** |

### `PAO-R36-VI-001` — material — five fixtures are not single exact specifications

F03, F05, F08, F11, and F13 contain conditional, disjunctive, phase-dependent, or set-wide outcomes
that the suite's own vocabulary does not define. F06 also omits its `FAIL_CLOSED(member)` argument.
Split them into deterministic variants with one initial phase, one attacked member/cohort class, and
one exact terminal outcome.

### `PAO-R36-VI-002` — commendation — F13 is a sharp temporal attack

F13 catches the public-presentational form of retroactivity: a historical query cannot silently use
the later version, and a current query cannot select the earlier head. Preserve it after splitting
the two directions and adding append-order coverage.

### `PAO-R36-VI-003` — commendation — F16 tests semantics, not markers

F16 embodies P29: deleting a live member result while retaining count/green strings must fail an
independent denominator/evidence join. This is one of the suite's strongest rows.

### `PAO-R36-VI-006` — commendation — F09 is a real laundering attack

F09 is not a restatement of PV-K02. It supplies two concrete false inferences—current revocation
rewrites historical authenticity, and historical signature validity proves current authority—and an
oracle that must keep four propositions separate.

### 5.2 Attacks not caught by F01-F16

#### A17 — serialized stale-base corrections lose an intervening correction

1. C1 stages `v1 -> v2`.
2. C2 stages `v1 -> v3` under the same old head.
3. C1 transitions and becomes the sole current head.
4. C2 later transitions by last-writer semantics and becomes the sole current head.
5. There are never two simultaneous current heads, so F08 can pass.
6. C2 nevertheless bypassed `v2`, its reasons, notice, and adverse-effect classification.

Required detector: the predecessor/base-head identity used for transition must equal the canonical
head immediately before the append, or C2 must be rebased/supersede the new head through a new
transaction.

### `PAO-R36-VI-004` — material — no stale-base/lost-update attack

Add a two-correction fixture that remains red even when exactly one current head exists after each
serialized append.

#### A18 — controlled-set growth after snapshot

1. Freeze `S/C`.
2. Add a new controlled authority route or representation variant before effect.
3. Complete the old denominator.
4. New member serves predecessor-current.
5. F02/F04 use the fixture denominators and do not require registry-generation continuity.

Required detector: recompute set membership from the exact controlled registry/config generation at
effect and fail if it differs from the admitted generation.

This attack supports `PAO-R36-IV-001`.

#### A19 — receipt replay across corrections

1. Correction C1 over `S@G` obtains valid per-member receipts.
2. Correction C2 has the same member names/count but a different successor, notice, cutoff, or
   required state.
3. A malicious or defective aggregator reuses C1 receipts to satisfy C2.
4. No receipt is deleted, so F16 remains green if evidence is joined only by member identity/count.

### `PAO-R36-VI-005` — material — no cross-correction receipt-replay attack

Every member receipt and completion join must be content-bound to correction identity, snapshot
identity/generation, required predicate, selected version/notice, and cutoff. Add a replay attack that
keeps all marker strings and all member rows.

#### A20 — staged-notice substitution

A surface selects the correct successor/current head but links a notice for another correction or a
notice still marked staged. The current three-label predicate can classify it
`successor_current_linked`; F15 tests unreachable successor, not wrong-notice phase/identity.

Required detector: correction identity and notice phase are part of the observer tuple.

#### A21 — backdated effective declaration

The effective event is appended after verification but carries an earlier displayed cutoff, or is
appended before the final member receipt and later receives that receipt. F13 checks version selection,
not event order.

Required detector: append/event precedence plus evidence cutoffs not later than the effective event.

## 6. Formal conclusion

The research has a strong mathematical spine: bounded asynchronous convergence, frozen denominators,
and adversarial independent recomputation. The submitted contract is nevertheless `NO_GO` until the
three blocking defects are repaired. Once they are repaired, the two-boundary construction,
external-copy honesty, hard cases, F09, F13, and F16 should survive consolidation rather than being
replaced wholesale.

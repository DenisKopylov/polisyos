# INT-R5 Formal Argument Audit

## 1. Scope And Method

This artifact attacks the package's arguments rather than its arithmetic. It tests whether each
conclusion follows from the stated premises, whether universal quantifiers are earned, whether a
technical control is being asked to prove a legal fact, and whether a named refusal is actually
reachable through an enforcing consumer.

The controlling package coordinates are:

- `int-r5-decision-authority-validity.md` §§1–10;
- `int-r5/decision-authority-specification.md` §§2–19;
- `int-r5/adversarial-fixtures.md` §§2–9;
- `int-r5/repository-baseline.md` §§2–8;
- `int-r5/external-evidence-ledger.md` §§3–8.

The formal audit uses one rule throughout:

> A statement about what a system can prove is valid only if its decisive operands have identified
> non-requester producers, its denominator covers the complete claimed set, and a real consumer
> rejects the divergent case before the protected effect.

## 2. Information-Limit Claim

### 2.1 What the package writes

Section 4.2 labels an “information-limit theorem” and writes:

```text
authority_at_check(t0) != authority_at_use(t1)
```

unless snapshot, lease or revalidation semantics apply.

### 2.2 Counterexample

Let authority be mutable in principle but unchanged in the actual history:

```text
authority_at_check(t0) = valid
authority_at_use(t1)   = valid
no intervening revocation, expiry, appointment change or policy change
```

The displayed inequality is false in that admissible history. Mutability does not entail a state
transition.

### 2.3 The result the evidence actually supports

The supplied pre-action survey supports an epistemic proposition:

```text
From state observed at t0 alone,
authority_at_use(t1) is not determined
when an authority-changing event may occur in (t0, t1].
```

Equivalent quantified form:

```text
There exist two histories H0 and H1 that are indistinguishable at t0,
but authority_at_use(t1, H0) != authority_at_use(t1, H1).
```

Therefore a certificate issued at `t0` cannot, from its own pre-`t1` information, prove which history
will obtain. That is a genuine information limit. It warrants explicit snapshot, lease or revalidation
semantics.

### 2.4 Downstream impact

Weakening the equation does **not** change any downstream requirement. `as_of`, `fresh_until`, mutable
dependency references, revocation events and pre-effect revalidation remain necessary. The error is a
false universal statement and an over-authoritative label, not a failed architecture.

Disposition: `INT-R5-A-001`, **material**.

## 3. Shipped-Component Verdicts

### 3.1 What would establish wrongness

For each shipped component, the audit looked for:

- a caller assertion accepted as an authority fact;
- a universal rule that conflicts with a named regime;
- a mismatch that can still yield a positive;
- an expired/revoked/mismatched authority path that reaches an effect;
- a projection or step-up token treated as institutional competence;
- a claimed integration absent from the actual call path.

### 3.2 GY-PA2

The narrow PA2 claim is supported. The decision is a conjunction over verified identity, exact
permission, mandate-bounded delegation, operation/envelope match and live accountability. The code
binds operation, subject, tenant, resource, time interval and active/revoked state and refuses
mismatch, ambiguity, expiry and revocation.

No counterexample was found in which those five **declared** predicates fail and the PA2 decision
still admits. This does not prove the complete institutional-authority proposition; it supports the
package's narrower “sound but incomplete” verdict for PA2.

### 3.3 DS9

The narrow DS9 claim is also supported. The route and service separate caller-authored fields from
custody fields, use a strict source union, re-resolve raw PA2 or production-approval inputs, check
currentness and place the write behind reservation/idempotency and guarded persistence.

No case was found in the inspected DS9 path where a serialized positive alone substitutes for current
source resolution. The package is justified in treating DS9 as a suitable future certificate consumer.
It is not justified in treating every operation protected by DS20 as already consuming DS9.

### 3.4 DS20

The DS20 verdict is correctly bounded. DS20 answers whether a verified runtime principal may perform
one exact operation over one exact resource under current permission and step-up policy. It does not
claim that the principal occupies a lawful office or that a body had quorum. The package does not
upgrade DS20's `allow` into institutional competence in its component description.

### 3.5 Acquisition approval

The acquisition verdict fails.

At the pinned route:

```text
POST /api/v1/control/data/ingest
  -> _INGEST_DATA_AUTHZ
     RuntimePermission.EVIDENCE_ACQUIRE
     request-bound runtime.evidence.acquisition resource
  -> _INGEST_DATA_STEP_UP
     StepUpClass.ACQUISITION_APPROVAL
  -> ControlPlaneService.run_data_ingestion
  -> Fabric ingestion modes/orchestrator
```

The route has no PA2 dependency, no DS9 human-decision dependency and no call to the human-decision
service. `run_data_ingestion` constructs dataset/connector inputs and executes ingestion. It does not
resolve a mandate, human-decision record, reviewer separation or guarded decision store.

The package's statement that acquisition “composes” DS20, GY-PA2 and DS9 is therefore not an
incomplete truth. It is a false production-topology claim. The components are adjacent and reusable;
they are not wired on the protected acquisition effect.

Disposition: `INT-R5-A-002`, **material**.

### 3.6 T2 conclusion

The comfortable-verdict hypothesis is **partly established**:

- PA2, DS9 and DS20 retain their narrow sound verdicts after direct attack;
- acquisition must move from “sound but incomplete composition” to “bridge/consumer missing”.

The package did test for wrongness at the component-contract level, but it did not test the full route
composition it described.

## 4. Attribute Partition

### 4.1 Operational meaning of `partial`

The four `partial` rows are not empty midpoint labels:

| Attribute | Represented fragment | Named missing part | Audit result |
|---|---|---|---|
| temporal and subject-matter delegation | operation/action, subject, tenant, resource, `valid_from`, `valid_until`, active/revoked state | source-law competence, amount/valuation, reserved matters, full purpose scope | earned fragment |
| separation of duties | exact DS9 reviewer separation against named reviewed actors | proposer/contributor/executor/reviewer lineage and controlling-subject closure | earned fragment |
| expiry and emergency authority | envelope expiry and status | emergency source, trigger, necessity, urgency, exceptional scope and expiry profile | asymmetric composite; still not a content-free hedge |
| revocation mid-operation | currentness re-resolution before DS9 protected use | checkpoint/cancel/irreversible-effect semantics and post-effect consequence | earned fragment, but not on acquisition route |

The table should ideally split expiry from emergency, but the word `partial` itself is operationally
explained by a positive coordinate plus an explicit gap.

### 4.2 `not representable`

The six negative rows are substantively plausible. The problem is their warrant. The package defines
“not representable” as no field, producer **and consumer** in the strict canonical chain, then claims
the inspected ten files are the complete owner closure.

They are not. At minimum the direct and call closure contains omitted:

- security and runtime-principal owners;
- authority metadata and reconciliation;
- event log and artifact writer;
- candidate-firewall and memory/provenance owners;
- idempotency/reservation storage;
- production-approval resolution;
- the real human-decision route;
- the control service that executes acquisition.

A selected ten-file subject slice can identify candidate absences. It cannot settle a repository or
production-chain zero under P35/W4-K01. The audit therefore does **not** reverse the six rows to
represented; it changes them to `not established by this denominator` pending a complete closure.

Disposition: `INT-R5-A-003`, **material**.

## 5. Producer Independence

### 5.1 Correctly named producers

The specification names credible producer classes for identity, appointments, source law,
delegations, amount aggregation, forum/session evidence, quorum recomputation, transaction lineage,
conflict registers, recusal decisions, emergency predicates, revocation status, recognition and act
effect.

It also correctly says requester statements are candidate-only and that PolicyOS produces only the
certificate result and custody proof.

### 5.2 Missing or circular producers

The universal statement fails on several decisive coordinates:

| Decisive coordinate | Specification treatment | Missing producer problem |
|---|---|---|
| `decision_time` | field in graph evaluation; used for path validity | no server/event-time or trusted timestamp owner is named; caller backdating can change expiry and appointment results |
| `requested_effect_time` / `as_of` | graph and certificate fields | no authoritative clock/commit event producer is named |
| `effect_class` | reversible / conditionally reversible / irreversible | no owner decides this classification; a caller could choose the class that changes checkpoint behavior |
| `jurisdiction_profile_refs` and `rule_profile_refs` | supplied to evaluation | the legal-profile owner is named generically, but the producer that selects the applicable profile for this matter is not |
| `revalidation_mode` | “profile-selected” | no concrete selector/owner binds the mode; saying the caller cannot choose it is a negative, not a producer |
| semantic decision/effect commitment | “PolicyOS canonicalizer over resolved immutable input” | canonicalization proves byte identity, not that caller-originated amount, recipient, decision time or legal effect is true or authoritative |

The distinction is decisive:

```text
canonicalize(requester_value) -> recomputed hash of requester_value
```

is not:

```text
independently establish the semantic fact represented by requester_value
```

A caller-supplied timestamp that is perfectly canonical remains caller-supplied. Because authority
validity turns on that timestamp, one missing producer defeats the package's universal producer
property.

Disposition: `INT-R5-A-004`, **material**.

## 6. Status Vocabulary

### 6.1 Global lattice hypothesis

The package explicitly states that:

```text
pre_action_valid | refused | not_established | not_applicable
```

is a local family union and that the DS4/status owner must later define projection into the existing
system lattice. This is consistent with a common port carrying family-native payloads. The audit does
not establish a second global lattice.

### 6.2 Refusal-code collision

The reason-code layer is different. Section 15 lists bare, stable-looking tokens and the fixtures use
them as oracle values:

```text
CERTIFICATE_STALE
REVALIDATION_REQUIRED
DELEGATION_REVOKED
...
```

The live repository already uses namespaced and versioned blocker semantics, including
`polisyos.eval_safety.certificate_stale@1.0.0`. The package neither namespaces its codes nor maps them
to existing families. “Final vocabulary remains downstream work” does not prevent fixtures from
freezing the provisional strings in practice.

The defect is not the existence of family-specific reasons. It is absence of identity, namespace,
version and crosswalk while claiming stable local reason codes.

Disposition: `INT-R5-A-006`, **material**.

## 7. Conflict Detectability

The audit attempted to find an unbounded conflict claim in the certificate, graph or fixtures and did
not find one.

The package separates:

1. prohibited role overlap that can be recomputed from transaction lineage;
2. registered conflict state;
3. record-indicated facts requiring adjudication;
4. current participant declaration;
5. off-system/undisclosed facts that are not disprovable;
6. evaluative appearance questions needing a competent decider.

The strongest positive is expressly bounded to named reconciled records and current declarations.
The package says undisclosed/off-system absence is **not provable**, and the degraded conflict-register
fixture yields `not_established`, never a positive.

`T7` is therefore **not established**. This is commendation `INT-R5-A-C04`.

## 8. Cure And Retroactivity

### 8.1 What the fixture actually freezes

The fixture freezes the historical certificate answering:

```text
Did the original actor possess pre-existing authority at 11:00?
```

When the answer is no, a ratification at 14:00 cannot make that pre-action computation truthful as if
it had been issued at 11:00. Preserving the refusal is correct historical custody.

### 8.2 What the package allows later

The fixture then evaluates a new graph under three profile classes:

- cure permitted if conditions pass;
- cure forbidden;
- cure effect not established.

The graph also has a `CURES_OR_VALIDATES` edge and its claim envelope can carry
`legally_effective_from`. This means the architecture need not deny legal relation-back.

### 8.3 Remaining ambiguity

The fixture does not require the new result to distinguish:

```text
prospective cure
relation-back cure
saved act despite original defect
validation with limited protected interval
legal effect unresolved
```

Without that required coordinate, a consumer could preserve the historical certificate correctly but
still misstate the current legal effect of the original act. The repair is to add relation-back/current
legal-effect semantics, not to mutate the old certificate.

`T8`'s expected universal defect is **not established**. The narrower omission is
`INT-R5-A-008`, **minor**.

## 9. PAO-R4 Boundary

### 9.1 Conceptual boundary

The package is explicit that INT-R5 answers who or which body had authority, while PAO-R4 controls
whether a policy-level artifact may cross toward an individual determination. It forbids substitution
in both directions and repeats the anti-role boundary in `may_not_use_for`.

This is substantively consistent with PAO-R4: authority competence and individual-use admissibility
are different predicates.

### 9.2 Handoff gap

The positive formulas and integration sequence omit the actual conditional conjunction:

```text
if effect targets an individual case or a pointwise-recoverable artifact:
    require PAO-R4 crossing-gate receipt before the effect
```

Instead the path is described as certificate → DS9 revalidation → DS20 protected effect. A negative
use restriction in the certificate does not force the effect consumer to obtain PAO-R4 evidence.

The resulting seam permits both teams to remain “on their side” while no component owns the
conjunction. That is the classic boundary gap the package otherwise warns against.

Disposition: `INT-R5-A-007`, **material**.

## 10. Additional Argument Attacks

### 10.1 External evidence and independent reproducibility

The external ledger carefully classifies claim type and jurisdiction, but its exact warrant is not
replayable from the branch. Named statutes and cases are not a claim-to-source ledger. The five
survey artifacts have no committed identity, content hash, stable link, bibliographic record or line
anchor. A hostile reader cannot distinguish a faithful transfer from a synthesis that exceeded the
survey without leaving the branch.

Disposition: `INT-R5-A-005`, **material**.

### 10.2 Ordering arithmetic

The stage-1 orientation says the must-land-before condition was violated three times. The task row's
predicate is narrower:

```text
must land before GY-PA2 or Atlas DS9/DS14 consumers close
```

and separately says the task feeds DS20 vocabulary and acquisition approvals. At the pin GY-PA2 and
DS9 were closed, DS14 was unstarted. DS20 is a missed input/feed, but it is not a third instance of the
same closure predicate.

Disposition: `INT-R5-A-009`, **minor**.

### 10.3 Threshold proof versus legal quorum

The package correctly does not equate a SPKI-style `k-of-n` threshold with legal quorum. The threshold
mechanism proves branch count and authority; the jurisdiction profile separately defines authorized
seats, eligibility, presence, temporal scope and voting rules. No false universal threshold theorem
was found.

### 10.4 Monotonic attenuation

The graph's child-scope intersection is a valid general safety invariant: it prevents the technical
reducer from granting more than a parent path. The package correctly retains exceptions such as
acting authority, implied departmental authorization and emergency power as separate source edges
rather than pretending they are widening subdelegations.

## 11. Conclusion

The formal core is worth retaining. The audit's material defects are all boundary defects in the
package's own sense:

- wrong quantifier at the time boundary;
- nonexistent composition at the route boundary;
- incomplete set at the denominator boundary;
- caller-derived facts at the producer boundary;
- missing trace at the evidence boundary;
- unmapped tokens at the vocabulary boundary;
- omitted conjunction at the PAO-R4 boundary.

They explain why `GO` is unavailable and why `NO_GO` would be disproportionate. Each has a bounded
revision with a falsifiable closure condition.

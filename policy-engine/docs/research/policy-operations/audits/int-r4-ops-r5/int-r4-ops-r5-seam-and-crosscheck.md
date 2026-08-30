# INT-R4 ‖ OPS-R5 — Seam And Crosscheck

Audited package head: `c3999897b5be2308513846935f1c4fb68157bcb3`

## Joint Vocabulary Seam

### What genuinely must be shared

INT-R4 and OPS-R5 observe the same movement and cannot safely assign contradictory **source semantics**
when that source type controls posterior eligibility. At minimum they must share or reconcile:

- the comparison identity and estimand;
- observation/selection validity;
- intervention and exposure version;
- context/interference scope;
- behavioral-path evidence;
- model-compatible versus model-relevant residual;
- unresolved competitors and missing discriminator;
- which contributors block learning;
- the exact version of the diagnosis rule.

This part of the “one vocabulary approached from two directions” framing is sound.

### What need not be identical

The two tasks do not ask only one question:

```text
INT-R4: may this movement alter a causal effect posterior or world edge?
OPS-R5: what operational action may be requested, under what authority and reversibility?
```

A source diagnosis, an accountable destination, an operational action family and a public validity
state are different objects. The package already proves this by retaining:

- SMDV-1 source diagnosis;
- S13 destination/component attribution;
- OPS A0–A6 action families;
- E/X/V/C response/claim coordinates;
- continuous-governance public validity statuses.

Therefore the invariant should be:

```text
one governed source-diagnosis semantics
OR a versioned, total, tested crosswalk that preserves update eligibility and unresolved behavior
```

It should not be:

```text
one representational vocabulary and owner for every purpose; any fork kills the design
```

A domain refinement is safe when it is a conservative partition or annotation that cannot map a
non-learning source into `prediction_error`, cannot erase a blocking contributor and cannot turn
unresolved into a positive. This is the repair for `AUD-F10`.

## INT-R4 To OPS-R5 Routing Seam

### Intended seam

```text
MovementComparisonRecord
→ MovementDiagnosisRecord (SMDV-1 primary + contributors)
→ EffectUpdateAdmissionRecord for INT-R4
→ ResponseRequest / TransitionDecision for OPS-R5
```

The package correctly separates the two consumers. A diagnosis can support a protective operational
response while denying effect learning.

### Required routing matrix

| SMDV-1 result | INT-R4 learning | OPS-R5 minimum response possibilities | Mandatory lane |
|---|---|---|---|
| `expected_variation` | no discrepancy repair; routine path disputed | observe/mature; no threshold tampering | calibration/monitoring only if architect permits |
| `observation_process_change` | freeze substantive update unless valid bridge | refresh definition/source, bridge/backcast, mark series break, investigate | measurement/semantic epoch |
| `intervention_delivery_or_version` | no old-version effect update | repair delivery, narrow, reissue or create new estimand/version | implementation/version owner |
| `behavioral_response` | response-model update only under identified estimand | mechanism review, anti-gaming design, scope/implementation action | behavior/mechanism owner |
| `context_or_interference` | no clean local prediction-error update | context review, exposure-map repair, scope action, reissue | regime/coupling/interference owner |
| `prediction_error` | update proposal only after all remaining gates | investigate, recalibrate/redesign/reissue as authorized | predictive mechanism + S13 attribution |
| `diagnosis_unresolved` | freeze posterior/world write | investigate, acquire, no-expand, contain or preauthorized pause | unresolved case owner/clock |

### Missing contributor invariant

The package says a blocking contributor blocks learning, but OPS routing is expressed primarily by
`primary_class`. The seam must require:

```text
for every supported contributing_class:
    create or link the required lane obligation
    assign its owner/route
    record closure, supersession or explicit non-applicability
```

Divergent fixture:

```text
primary = observation_process_change
contributors = [behavioral_response]
```

A consumer that opens only measurement refresh and omits behavior/mechanism review must fail even
though learning remains correctly frozen. This closes the masking risk in `AUD-F04`.

### O1 disputed seam

`expected_variation` is currently not safe to route to an effect-posterior consumer. Until an architect
amends GY-O1, the only lawful mapping is:

```text
expected_variation → no effect-posterior mutation
```

A distinct observation-model or forecast-calibration owner may later be allowed, but it must not be
smuggled through the same effect-posterior field. This is the seam-level consequence of `AUD-F05`.

## SMDV-1 To S13 Seam

### Correct architectural distinction

SMDV-1 asks where the observed movement originated relative to the comparison. S13 asks which
accountable component/destination receives a divergence and what learning/reissue controls apply.
The package’s order is therefore correct:

```text
source diagnosis first
→ model-relevant admission decision
→ S13 destination attribution/accountability
```

S13 is not a substitute for SMDV derivation, and SMDV must not replace S13 accountability.

### Non-isomorphic mapping

| SMDV-1 | S13 candidates | Crosswalk condition |
|---|---|---|
| `expected_variation` | no S13 divergence | must not fabricate attribution |
| `observation_process_change` | `evidence_error` | preserve policy-caused selection/intensity versus ordinary bad evidence |
| `intervention_delivery_or_version` | `implementation_failure`, sometimes no error | planned version change is not necessarily failure |
| `behavioral_response` | `strategic_response` | preserve intended/non-adversarial mediation |
| `context_or_interference` | `world_change`, `regime_error`, `coupling_error` | one-to-many destination mapping |
| `prediction_error` | `design_error`, `evidence_error`, `coupling_error`, other component after evidence | prediction error is not yet component blame |
| `diagnosis_unresolved` | `pending` or `unattributable` | preserve whether more evidence can resolve it |

This crosswalk must be a versioned artifact. It cannot be implemented as a string lookup that silently
widens authority.

### S13 producer boundary

At the pin:

- `DivergenceRecord` requires `attribution_class` and `attribution_status`;
- validators ensure learning status/owner consistency and prevent an implementation failure from
  refuting theory without independent evidence;
- canonical fixtures supply class/status values.

No cited S13 owner derives SMDV from a conditioned comparison. The package’s bounded gap is correct.
A future producer should not be hidden inside a validator. It must emit evidence of elimination and
unresolved alternatives.

## DDM And GY-O2 Seam

### Existing semantics

DDM separates:

- calibrated shift;
- estimated/realized degradation;
- data-quality signals;
- readiness state;
- incident payload;
- root-cause localization bundle.

GY-O2 explicitly consumes reusable detectors/FDR and emits `candidate_unverified`; it is build-new as a
controller and cannot edit the world directly. The stage-1 orientation and package baseline are
accurate here.

### `RootCauseBundle` naming hazard

The record called `RootCauseBundle` contains localized features/slices, upstream versions,
data-quality violations, stationarity regimes and supporting event IDs. Its name does not make it a
causal proof of:

- policy-induced observation change;
- intervention/version mismatch;
- behavior reaching latent outcome;
- interference;
- genuine prediction error.

Consumer invariant:

```text
DDM event type, risk level, readiness score, root-cause bundle presence,
completion flag or local threshold may open diagnosis;
none may set SMDV primary_class or authorize action by itself.
```

Required divergent case: a perfectly localized feature shift caused by a measurement-schema change.
A proxy consumer that maps localization to `prediction_error` must fail.

### GY-O2 to O1 firewall

The package preserves the plan’s firewall:

```text
anomaly under FDR
→ candidate hypothesis
→ frozen estimand/version/outcome and prospective evidence
→ O1 comparison and SMDV diagnosis
→ only then possible high-authority update
```

This seam is a commendable reuse boundary. It must remain explicit in later architecture.

## N8 Typed-Carrier Seam

### What exists

N8/value contracts already provide:

- strict receipt identity and world-model content binding;
- `ValueOuterSet` interval/scenario/unknown representations;
- point/partial/proxy/blocked identification;
- assumptions, calibration, trust and epoch;
- explicit pending/blocked/ready observations.

The stage-1 prompt’s typed-carrier statement is accurate. The package correctly refuses scalar-only
comparison.

### Missing comparator registry

A `MovementComparisonRecord` is not enough. Each representation family requires an admitted comparator
contract:

| Carrier form | Comparator question | Unsafe shortcut |
|---|---|---|
| point/interval | compatibility, coverage, effect movement under declared uncertainty | subtract point estimates only |
| set/polytope | containment, support-function or partial-order relation | choose arbitrary centroid |
| scenario set | scenario correspondence and version identity | compare means across different scenario bases |
| distribution | calibrated predictive check under fixed observation model | p-value alone becomes cause |
| unknown/blocked | evaluability refusal | coerce to zero/missing |

The package names carrier-specific comparison/refusal but does not select or validate the comparator
owners. That is a later engineering/research blocker, correctly not called implemented.

### Identity seam

Prediction and realization must share:

- target construct/estimand;
- intervention/exposure version;
- population/subgroup frame;
- measurement schema and time roles;
- world/epoch basis.

Content equality of one scalar does not repair a mismatch in any of these identities.

## Fabric, Quarantine, And World-Store Seam

### Fabric capabilities correctly reused

Fabric supplies:

- observed/scenario branches and retained snapshots;
- bitemporal query coordinates;
- append-only assertion, correction and revocation;
- governed branch-head movement and merge evidence;
- replay without overwriting historical facts.

`WorldModelRecord` also exposes `DEPLOYMENT_UPDATE` mode and `DeploymentUpdateRefs`, while explicitly
stating that these are Phase-6 forward hooks and not an updater.

The stage-1 orientation and package are accurate: the substrate is real; the admitted O1/O3 consumer is
not.

### Required O1/O3 write seam

```text
EffectUpdateAdmissionRecord allowed
AND update target/version exact
AND signer/authority valid
AND idempotency key unused
→ posterior/world branch proposal
→ append-only commit receipt
```

Forbidden proxy predicates include:

- SMDV class-name presence;
- `learning_allowed` supplied by caller;
- successful quarantine reprocess;
- world branch mode named `deployment_update`;
- S13 attribution status alone;
- DDM readiness green.

The consumer must recompute the admission property or consume an independently reconciled admission
record. Markers are not the property.

### Generic quarantine versus semantic refusal

Generic quarantine is intentionally reprocessable. O3 requires a narrower semantic invariant:

```text
this exact evidence set may never confirm this exact substantive edge
```

A future `SelfConfirmationQuarantineRecord` must include:

- prohibited operation and target identity;
- evidence/claim/edge content identities;
- observation-ancestry basis;
- permanent historical disposition;
- what type of genuinely new independent evidence may create a new record;
- consumer-side deny rule;
- no operation that mutates the old quarantine into admission.

Storage may reuse Fabric quarantine. Semantic ownership belongs to the O3 admission profile/consumer,
not to generic dead-letter mechanics.

## H2, Continuous-Governance, And Atlas Seams

### H2 custody runtime

The backlog routes Group-B durable mechanics to H2. OPS-R5’s candidate durable artifacts fit that
boundary:

- `KPIControlContract`;
- `KPIObservationRecord`;
- `ResponseRequest`;
- `TransitionDecision`;
- `ActionExecutionRecord`;
- `RestartEvidenceRecord`.

H2 would own long-lived transition state, clocks, idempotency, retries and recovery. GY remains the
learning/design/world consumer. The package correctly avoids turning GY into a parallel custody
platform.

Missing before H2 architecture:

1. the constrained E/X/V/C state invariant from `AUD-F06`;
2. per-operation OPS-R6 transition semantics from `AUD-F02`;
3. authority references from INT-R5 or an equivalent appointed institutional source;
4. correction and late-event semantics compatible with the adopted custody time model;
5. actual response fixtures from `AUD-F08`.

### Continuous governance

Existing continuous-governance monitors can recommend monitor/stale/review/reissue/withdrawal review
and emit public validity states. A validator explicitly prevents a monitor recommendation from directly
withdrawing an artifact. That is the right separation.

Required bridge:

```text
OPS TransitionDecision / external execution evidence
→ canonical claim consumer
→ stale/reissue/supersede/withdraw lifecycle evidence
```

Continuous governance must not infer that external policy action occurred merely because OPS requested
it.

### Atlas

Atlas may project:

- current E/X/V/C state;
- diagnosis and contributors;
- unresolved discriminator and clock;
- requested versus authorized versus executed action;
- current claim/public validity;
- restart evidence and history.

Atlas must not:

- convert a threshold or alert into action authority;
- hide unresolved behind an aggregate status;
- mint a signer from an owner label;
- collapse requested, authorized and executed;
- rewrite historical claim state after correction.

The package’s one-lattice and projection-cannot-mint-authority posture is correct.

## Cross-Task And Cross-Package Analogues

### INT-R2 — acquisition of non-data gaps

`diagnosis_unresolved` often names a structural gap—independent sensor, causal relation, exposure map,
competent decision—not merely missing rows. Reopening must route through a typed acquisition case. Many
additional contaminated rows must not close the gap.

### INT-R5 — decision authority

OPS-R5 can specify that a signer is required, but only the authority-graph work can establish that the
specific actor/body had the right for this transition, scope, time and conflict posture. Owner strings
remain insufficient.

### INT-R9 — positive promotion

Any future claim that SMDV or the response model works must use a preregistered case/criteria,
independent adjudication, sealed holdout and no case-specific code. Authored 24/20 inventories cannot
provide that proof by themselves.

### OPS-R4 — adopted custody time model

The candidate artifacts use many time roles. They should consume the adopted sparse temporal profile
and family-native semantics rather than introduce a universal event envelope. Late correction must
create a new reaction record, not silently mutate historical state.

### OPS-R15 — custody capstone

The capstone is the natural end-to-end consumer of OPS-R5 semantics, but scoring remains blocked until
an independent oracle/evaluator exists. The missing concrete response fixtures are therefore not a
cosmetic omission: they are inputs to the independent capstone oracle.

### W4-K04 / P37 / P38

The seam audit repeatedly finds marker/property risks:

- declared sensor independence versus causal independence;
- class label versus evidence-derived diagnosis;
- branch mode versus write admission;
- owner string versus competence;
- threshold versus authorized action;
- quarantine status versus permanent semantic refusal.

Every later gate needs a divergent case retaining the marker while violating the property.

### W4-K06

Research sketches remain `absent/unallocated`, not `contract_only`, until admitted repository types
exist. This crosscheck directly produces `AUD-F09`.

## Seam Conclusions

| Seam | Existing fragment | Missing bridge | Audit status |
|---|---|---|---|
| comparison inputs | N8 typed carriers | carrier-specific post-deploy comparator registry | `missing` |
| signals | DDM/FDR | evidence-derived SMDV producer | `missing` |
| source diagnosis | SMDV research sketch | registered/admitted type, producer and oracle | `missing` |
| destination attribution | S13 | versioned many-to-many SMDV crosswalk | `missing` |
| learning admission | GY-O1 plan | architect ruling on expected variation; consumer gate | `blocked/missing` |
| world write | Fabric + WorldModelRecord hooks | O3 admission and actual writer invariant | `missing` |
| semantic quarantine | generic Fabric quarantine | claim-specific never-write profile and consumer | `missing` |
| operational response | DDM/monitoring/continuous fragments | H2 durable constrained transition engine | `missing` |
| action authority | required role described | appointed/preauthorized institution | `blocked` |
| public surface | Atlas plan | projection after canonical state, no authority minting | `future` |
| verification | narrative 24/20 specifications | concrete packets, independent oracle/evaluator | `missing` |

The package’s reuse topology is sound. Its missing bridges are honestly labelled. The audit revisions
are concentrated at the semantic interfaces—precedence, contributor routing, O1 update eligibility,
state invariants, standing tokens and executable fixtures—not at the repository-owner census.

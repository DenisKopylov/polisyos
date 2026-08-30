# INT-R4 ‖ OPS-R5 — Recommended Revision

Audited package head: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Audit verdict: `GO_WITH_REVISIONS`

This document specifies what would close each finding. It does not supply replacement package prose,
appoint an owner or authorize implementation.

## Revision Principles

1. **Repair the argument, not the line count.** The defect is not that the package is short; it is that
   some absorbed questions and design transitions lack an independent rule/falsifier.
2. **Route contradictions before optimizing them.** GY-O1 remains controlling until explicitly amended.
3. **Separate semantic factors from legal state space.** E/X/V/C may remain distinct coordinates, but
   reachable tuples and co-transitions must be declared.
4. **Treat abstention as measured performance.** `diagnosis_unresolved` is legitimate, but useful
   selective coverage must be evaluated rather than assumed.
5. **Turn examples into fixtures.** A corpus exists only when inputs, oracle, assertions and mutations
   are delivered.
6. **Keep standing vocabularies exact.** Research sketch is not a capability label.
7. **Preserve the package’s strongest corrections.** Do not regress the S13 baseline, P35 restraint,
   protection/learning asymmetry or reuse-first topology while repairing defects.

## Blocking Revisions

The audit register has **zero `blocking` findings**. No defect requires abandoning the package or
changing its subject.

The nine material revisions below are nevertheless prerequisites to a clean consolidation/architecture
handoff. If any is omitted, the package remains `GO_WITH_REVISIONS`, not `GO`.

## Material Revisions

### `REV-M01` — Discharge absorbed OPS-R7

Closes: `AUD-F01`.

Add an OPS-R7 closure matrix with a substantive section and falsifier for each question:

1. version-specific versus mixture versus dynamic-regime estimand selection;
2. endogenous version assignment;
3. sequential exchangeability and positivity, or an explicit statement that only randomized/design-
   based paths are admitted;
4. treatment-history/carryover representation;
5. interference and exposure-map misspecification;
6. repeated looks/optional stopping/error control;
7. claim reset versus equivalence/pooling across versions;
8. exploratory-to-confirmatory promotion after adaptation;
9. delayed/censored/zero-inclusion harm.

Each row must contain:

```text
question
bounded answer
required evidence/assumptions
unsafe conclusion prevented
admissible operation
falsifying case
remaining open problem
```

Do not close a row with only a field name or section pointer.

### `REV-M02` — Discharge absorbed OPS-R6 operation by operation

Closes: `AUD-F02`.

For each of the thirteen named operations—observe, early warning, diagnose, refresh, recompute,
recalibrate, adjust implementation, narrow scope, partial reissue, redesign, pause, rollback and
terminate—provide either:

- an independent transition charter; or
- a formal equivalence argument proving that sharing an action family preserves trigger, evidence,
  authority, reversibility, version, claim, public-notice and restart semantics.

At minimum split these current aggregates:

```text
A3: refresh | recompute | recalibrate
A4: implementation repair | scope narrowing | partial reissue
A5: pause | rollback
A6: redesign | terminate
```

Add a conflict rule for VOI versus legal/safety clocks and for waiting harm versus premature-action
harm. A list of both fields is not a decision rule.

### `REV-M03` — Measure unresolved absorption and substantive coverage

Closes: `AUD-F03`.

Do not invent a universal acceptable unresolved rate. Deliver the measurement contract first:

```text
class-specific precision/recall
blocking-contributor recall
false-resolution rate
false-abstention rate
coverage by domain and consequence class
risk–coverage curve
unresolved reason/missing-discriminator distribution
comparison to all-unresolved and trust-quarantine baselines
```

Evaluation sets must include:

- a sealed domain-stratified holdout not used to author SMDV;
- multi-causal realistic cases;
- nonidentified cases whose correct result is unresolved;
- uniquely diagnosable cases where unresolved is a false block;
- cross-domain cases that test class transfer.

Production thresholds remain deferred until domain consequence and oracle evidence exists.

### `REV-M04` — Recast precedence as admission order and bind contributors to action

Closes: `AUD-F04`.

Revise the formal object to distinguish:

```text
admission_gate_order
primary_routing_disposition
contributing_classes
blocking_contributors
mandatory_contributor_lane_obligations
```

Requirements:

1. observation-first remains a validity gate, not a claim that observation is the dominant physical
   cause;
2. justify or remove the relative ordering of intervention/version, context/interference and behavior;
3. primary class selects the requested operation’s controlling disposition only;
4. every supported contributor opens or links its required lane;
5. no consumer may route solely on the primary string;
6. incompatible supported routes produce unresolved;
7. blocking contributor remains blocking irrespective of primary.

Required divergent case:

```text
primary = observation_process_change
contributors = [behavioral_response]
```

A consumer that refreshes measurement but omits behavior/mechanism review must fail.

### `REV-M05` — Obtain architect disposition on GY-O1 `expected_variation`

Closes: `AUD-F05`.

The revision must classify the current difference as a contradiction/amendment request. Two lawful
closures exist.

#### Closure A — preserve written GY-O1

```text
expected_variation → no effect-posterior mutation
prediction_error    → only possible effect-posterior proposal
```

Routine observation-model diagnostics may exist elsewhere but cannot alter the causal effect posterior.

#### Closure B — amend GY-O1 explicitly

The architect/ratification record must distinguish the allowed target from causal effect repair and
bind all of:

- sealed pre-deployment schedule;
- no outcome-adaptive schedule changes;
- exact update-target whitelist;
- same observation-ancestry/version/context/interference/maturity gates;
- independent identification for any causal-posterior movement;
- cumulative confidence-gain/interval-shrinkage cap;
- claim/version consequences;
- authority and audit record;
- negative self-produced-compatible-data fixture.

Until one closure is recorded, all `expected_variation` effect-posterior paths remain `NO_GO`.

### `REV-M06` — Define constrained E/X/V/C state space

Closes: `AUD-F06`.

Retain the four semantic factors but replace “orthogonal/independent” with “factored and constrained”
unless a stronger proof is delivered.

Add:

```text
State = (E, X, V, C)
StateInvariant(state, history, contract, authority)
AllowedTransition(old, event, evidence, authority)
```

The invariant must cover:

- forbidden tuples;
- required co-transitions;
- material `V` change → claim review/reset unless equivalence passes;
- termination/confirmed-unacceptable → claim consequences;
- rollback → no full exposure without restart gate;
- external action that can continue after causal-claim withdrawal;
- partial orders and terminal states per axis;
- history-dependent constraints;
- human-discretion points where more than one next state is lawful.

Add pairwise and three-way mutation fixtures that fix three coordinates and attempt an illegal fourth.

### `REV-M07` — Materialize the 24 diagnosis fixtures

Closes: `AUD-F07`.

Deliver twenty-four immutable packets, not only a table of counts. Each requires:

```text
case_id and content hash
prediction/effect carrier
estimand
intervention/exposure/version history
population/subgroups
measurement schema and all time roles
context/interference evidence
behavioral paths
maturity/censoring/missingness
independent channels
sealed expected primary/contributors
permitted and forbidden consumers
oracle/adjudicator provenance
```

The O3 case must be split into five independent mutations:

1. wrong diagnosis;
2. false independent ancestry;
3. effect-posterior consumer escape;
4. world-writer escape;
5. generic reprocess defeats permanence.

Also include a neighboring valid independent-evidence case so a hard-coded “all targeted discovered
events are quarantined” implementation fails.

The corpus acceptance report must include the selective-classification measures from `REV-M03`.

### `REV-M08` — Materialize the 20 response scenarios

Closes: `AUD-F08`.

Deliver twenty named event-sequence packets with:

```text
initial E/X/V/C state
KPI contract and observation
maturity/measurement posture
SMDV result or protective basis
authority/preauthorization
waiting and premature-action losses
reversibility vector and blast radius
clock/event sequence including duplicates/corrections
expected transition and forbidden alternatives
version/claim/public consequences
restart evidence
sealed oracle
```

Required paired divergent cases hold the observed threshold movement constant while varying:

- authority;
- maturity;
- waiting harm;
- reversibility;
- version identity;
- first event versus duplicate;
- alert disappearance versus independent restart probe.

The evaluator must assert requested, authorized and executed state separately.

### `REV-M09` — Correct W4-K06 capability labels

Closes: `AUD-F09`.

Audit all per-finding `capability_standing` cells. Replace every use of:

```text
contract_only as research sketch/proposal/rule
```

with the applicable registered repository state, normally:

```text
absent/unallocated
not_established
bridge_missing
verification_missing
implemented for bounded existing owner scope
```

Move `research contract sketch` into a separate descriptive field. The revision must leave the
top-level `absent/unallocated` standing unchanged unless a real admitted type lands in a later stage.

## Minor Revisions

### `REV-m01` — Narrow the one-vocabulary invariant

Closes: `AUD-F10`.

Change the invariant from representational monopoly to authority-preserving semantic compatibility:

- one source-diagnosis contract **or** a total versioned crosswalk;
- no map may turn non-learning/unresolved into `prediction_error`;
- no map may erase a blocking contributor;
- purpose-specific S13, OPS action and public validity taxonomies remain permitted;
- conservative domain partitions/annotations are allowed when tested;
- a fork is fatal only when it creates contradictory eligibility or has no total map.

### `REV-m02` — Add row-level evidence links

Closes: `AUD-F11`.

Preserve the useful six disposition columns and add either:

```text
evidence_refs
kind_or_transfer
falsifier_or_resolution
```

or a stable claim-ledger backlink for every finding. External survey refs should gain stable content
hashes/artifact IDs so duplicate filenames cannot become the only identity.

## Commendations To Preserve

### `KEEP-01` — Greenfield correction

Do not regress to “no typed attribution exists.” Preserve the exact distinction between S13
caller/fixture-supplied destination attribution and the missing evidence-derived source-diagnosis
producer.

### `KEEP-02` — P35 restraint

Keep the complete census `not_established`; do not use connector search as a denominator. A later
controlled walk may append evidence without retroactively changing who executed this package.

### `KEEP-03` — Receipt provenance

Keep terminal and connector evidence separate. Preserve complete transport stderr when CLI output is
unavailable.

### `KEEP-04` — `refuted` universal ladder

Preserve OPS-F06’s negative standing while repairing the substitute state model.

### `KEEP-05` — `blocked` institutional authority

Preserve the external appointment/preauthorization blocker. Do not turn repository owner/team strings
into institutional competence.

### `KEEP-06` — Reuse-first owner topology

Keep N8, DDM, monitoring, S13, Fabric, continuous governance and Atlas in their current bounded owner
roles. Do not create a parallel post-deployment platform.

### `KEEP-07` — Protection/learning and source/destination separation

Preserve the rule that protective containment may precede complete diagnosis while posterior/world
learning remains frozen, and that SMDV source diagnosis precedes rather than replaces S13 destination
accountability.

## Closure Tests

### `CT-01` — Absorbed-task completeness

Fail if any OPS-R7 or OPS-R6 row closes with only a section pointer, artifact field or family name.
Pass only when every independent question has answer, evidence, failure mode, fixture and open residue.

### `CT-02` — O1 contradiction

```text
assert exactly one:
  GY-O1 unchanged and expected_variation cannot change effect posterior
  GY-O1 explicitly amended by competent architect/ratification record with bounded routine path
```

Fail if the package still says “no contradiction” while permitting a non-prediction-error effect
posterior change.

### `CT-03` — Self-produced compatible evidence

Use a case where policy increases observation density and resulting data remain perfectly model
compatible. Fail if any routine path increases causal effect confidence without an independent
identification bridge.

### `CT-04` — Contributor masking

Use observation-primary plus behavioral contributor. Fail if the behavior lane is absent even when
learning is correctly frozen.

### `CT-05` — Selective coverage

Compare SMDV against all-unresolved and simple quarantine baselines on a sealed holdout. Fail if it has
no useful resolved coverage, resolves nonidentified cases unsafely, or hides class failures behind
aggregate accuracy.

### `CT-06` — State legality

Attempt at least these illegal tuples/transitions:

```text
material V2 + C0 without equivalence
E4 + X4 + intact acceptable claim
V4 rollback + X0 without restart evidence
C3 withdrawn automatically treated as external policy termination
```

Fail if the state engine accepts them without the named distinguishing evidence.

### `CT-07` — Five independent O3 negatives

Each O3 output must fail independently while the other four remain correct. A single conjunction test
does not pass.

### `CT-08` — Response proxy cases

Paired packets with identical observed metric/threshold but different authority, maturity,
reversibility or version consequence must take different transitions. Fail any threshold-only or
owner-string-only gate.

### `CT-09` — Standing-token audit

A repository search of revised finding registers must find no capability cell containing
`contract_only` solely because a Markdown research sketch exists.

### `CT-10` — Crosswalk totality

For every SMDV terminal and contributor combination used in the fixture corpus, the S13/OPS mapping
must be total, versioned and unable to widen learning. Missing map fails closed.

### `CT-11` — Evidence traceability

Select any finding row. A reviewer must reach the supporting repository/source evidence, evidence kind,
transfer boundary and falsifier without reconstructing the entire package.

### `CT-12` — Delivery integrity

The revision delta must remain Markdown-only under the declared package/audit paths and contain no
source, workflow, staging, binary, `AGENTS.md` or pattern-register edit.

## Matters Not Requiring Revision

The following are correct residuals or external dependencies, not defects to “fix” in research:

- no appointed institutional signer/adjudicator;
- overall `capability_standing: absent/unallocated`;
- overall `gate_standing: NO_GO`;
- complete census `not_established` after transport failure;
- connector-based remote receipt clearly labelled as such;
- no universal domain threshold, horizon, detector sensitivity or acceptable unresolved rate;
- classifier reliability and production prevalence left open with named evidence routes;
- no automatic world write, policy action or publication authority created by the package.

Do not fill these gaps with synthetic owner names, default numbers or stronger prose.

## Revision Conclusions

```yaml
blocking_revisions: 0
material_revisions: 9
minor_revisions: 2
preserve_items: 7
closure_tests: 12
post_revision_target_verdict: GO
```

`GO` after revision requires every closure test above to pass and a fresh independent readback. It does
not require solving the institutional absence, executing the P35 census in this audit environment or
implementing the capability. It requires that the stage-1 research package become internally complete,
falsifiable and faithful to its governing riders and standing vocabularies.

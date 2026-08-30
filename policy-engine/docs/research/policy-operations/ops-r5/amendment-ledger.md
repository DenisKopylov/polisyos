# OPS-R5 — Stage 3 Amendment Ledger

Amendment stage: `stage_3_amendment`  
Package head answered: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Audit head answered: `ea2eac5575e5b8fb4a5462c068a37bb913076952`  
Amendment branch: `research/int-r4-ops-r5-amendment`  
Joint pair: `OPS-R5` with `INT-R4`  
Ledger ownership: this file owns `AUD-F02`, `AUD-F06`, `AUD-F08`, `AUD-F11`, `AUD-F15`,
`AUD-F16`, `AUD-F17`, and `AUD-F18`. The INT-R4 ledger owns the other ten findings. No finding is
duplicated between ledgers.

This is the OPS-R5 append-only response record. It may supersede stage-1 package propositions, but it
does not alter audit artifacts, appoint authority, execute an action, register a contract or state
machine, or lift the audit verdict.

## 1. Standing And Non-Effect

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
audit_verdict: GO_WITH_REVISIONS
```

The action and state rules below remain research contracts. No signer, executor, durable H2 consumer or
production threshold is supplied by this amendment.

## 2. `AUD-F02` — Absorbed OPS-R6 Discharge

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:108`.  
Disposition: `accepted`.

The action families remain useful navigation, but sharing a family no longer implies that the
operations are semantically equivalent. Each operation below has an independent entry condition,
authority delta, version/claim consequence, reversibility, exit rule and divergent case.

### 2.1 `A3`: refresh, recompute and recalibrate

#### Refresh

**Object changed:** definition, source, schema, instrument, denominator rule, semantic epoch or
measurement bridge.

**Entry evidence:** identified observation-process defect or planned definition revision; affected
vintages and decisions; old/new definitions; bridge, dual run, backcast or explicit break decision.

**Authority and version:** metric-definition or source-change authority is required. Refresh creates a
new measurement/semantic version; it does not by itself create a new policy-effect version.

**Claim consequence:** causal claims depending on comparability move to `under_review` until bridge
evidence is admitted. Where no bridge exists, the old and new series are non-comparable.

**Exit/restart:** publish or retain the revision/break record, recompute only where the revision policy
permits, and re-open causal interpretation only after measurement validity is restored.

**Divergent case:** the formula is unchanged but the case definition or ascertainment source changes.
A conforming consumer selects refresh, not recompute or recalibrate.

#### Recompute

**Object changed:** calculated values or derived artifacts under an unchanged governed definition and
unchanged decision rule.

**Entry evidence:** corrected inputs, deterministic logic fix, late data or reproducible calculation
failure; proof that construct, population, measurement specification and policy version did not change.

**Authority and version:** custody/computation authority may re-run the calculation. A new data vintage
or correction record is created; the intervention version is unchanged.

**Claim consequence:** downstream decisions and claims are not silently rewritten. Each receives a
reaction record: unchanged, corrected, superseded, reissued or withdrawn.

**Exit/restart:** deterministic replay and reconciliation must close; idempotency prevents duplicate
correction; historical values remain linked to the original vintage.

**Divergent case:** identical input content produces a different result after a calculation bug fix.
A conforming consumer recomputes and records a correction; it does not call the change recalibration.

#### Recalibrate

**Object changed:** an explicitly named calibration mapping, predictive distribution, operating
threshold or noise parameter—not the raw observation definition.

**Entry evidence:** admitted out-of-calibration evidence from a predeclared calibration target and
valid evaluation source; unchanged or explicitly versioned treatment and measurement relation.

**Authority and version:** recalibration requires the authority assigned to the calibrated artifact.
It creates `V1_recalibrated` or another explicit model/version identity when the predictive object
changes.

**Claim consequence:** a signed statement whose point, interval, confidence, population or assumptions
change receives a new claim/version identity. Under current GY-O1, `expected_variation` cannot mutate
the causal effect posterior; the INT-R4 routed request does not change that rule.

**Exit/restart:** validate on held-out or independently identified evidence, bind the calibration
operator and effective time, and require a new probe before expanded exposure where action thresholds
changed.

**Divergent case:** the source data and formula are correct, but predicted probabilities are
systematically miscalibrated on an independent validation set. This is recalibration, not refresh or
recompute.

### 2.2 `A4`: implementation adjustment, scope narrowing and partial reissue

#### Implementation adjustment

**Object changed:** delivery fidelity, staffing, procedure, integration or execution mechanism intended
to realize the same policy design.

**Entry evidence:** implementation/version diagnosis, intended-versus-realized comparison, affected
population/exposure and evidence that the causal theory itself has not yet been tested by the failed
delivery.

**Authority and version:** implementation authority may repair delivery within its mandate; a material
delivery change creates a new realized intervention version even if policy intent is unchanged.

**Claim consequence:** implementation failure does not refute theory. The deployed-effect claim stays
`under_review` until the repaired version accumulates admissible evidence.

**Exit/restart:** verify repair, exposure identity and bounded execution evidence; restart uses a
separate probe rather than alert disappearance.

**Divergent case:** eligibility, dose and policy text are unchanged, but a required service was not
delivered. A conforming consumer adjusts implementation and does not narrow the target population.

#### Scope narrowing

**Object changed:** eligibility, geography, subgroup, dose, exposure ceiling, permissions or
population denominator.

**Entry evidence:** subgroup/guardrail harm, insufficient maturity outside a bounded population,
capacity constraint, interference boundary or legal/protective basis for no expansion.

**Authority and version:** changing who may receive the intervention requires the competent scope
authority. It changes exposure to `X2_narrowed` and creates a new population/estimand version.

**Claim consequence:** evidence for the former population does not automatically validate the narrowed
population, and evidence from the narrowed population cannot be generalized back without transport
evidence.

**Exit/restart:** declare the excluded and included populations, public meaning, review clock and
criteria for any expansion. Expansion requires fresh authority and evidence.

**Divergent case:** implementation is faithful for eligible units, but a vulnerable subgroup has
unacceptable harm. The operation is scope narrowing, not implementation repair.

#### Partial reissue

**Object changed:** a bounded subset of the operative artifact, rule, claim or guidance is replaced
while the remainder continues.

**Entry evidence:** exact affected components, dependency/impact graph, replacement content, version
compatibility and proof that unaffected portions remain valid.

**Authority and version:** reissue authority is required for the named object. A `V2_patched_or_reissued`
identity and append-only supersession relation are mandatory.

**Claim consequence:** claims depending on the changed subset move to review, exploratory or withdrawn;
unaffected claims may remain only after dependency analysis. Mixed old/new exposure is separately
represented.

**Exit/restart:** publication, custody and external execution receipts must identify which version
applies to whom and when; no silent overwrite.

**Divergent case:** one annex or decision module changes while the rest is retained. A conforming
consumer records partial reissue rather than treating the whole intervention as merely adjusted.

### 2.3 `A5`: pause and rollback

#### Pause

**Object changed:** permission for new or continuing exposure; the intervention artifact may remain
unchanged.

**Entry evidence:** credible safety concern, unresolved high waiting harm, invalid measurement where
continued exposure is not defensible, or a predeclared protective trigger.

**Authority and version:** only a preauthorized pause within its envelope or a competent decision may
set `X3_paused`. A threshold or owner string is not authority.

**Claim consequence:** pause does not prove the causal theory false. The operative claim normally moves
to `under_review`; learning remains frozen where diagnosis/identification is unresolved.

**Reversibility and exit:** pause has control reversibility only. Past exposure, state change, outcomes
and inferential history remain. Restart requires repair evidence, measurement health, bounded probe and
renewed authority.

**Divergent case:** no prior version is safe or available, so exposure stops while the current artifact
is retained for investigation. That is pause, not rollback.

#### Rollback

**Object changed:** future control returns to an explicitly identified prior intervention/configuration
version.

**Entry evidence:** a known prior version, compatibility with current state/data, rollback feasibility,
migration or compensation plan, and evidence that reverting future control reduces risk.

**Authority and version:** rollback authority must cover the target version and affected scope. State
becomes `V4_rolled_back` with exposure normally paused or narrowed during recovery.

**Claim consequence:** rollback does not erase outcomes under the reverted version or restore the
earlier experiment. Claims about both versions retain their histories and may require review.

**Reversibility and exit:** control may be reversible while state, outcome and inference are not.
`V4 + X0_full` is forbidden without a separate restart record and bounded probe.

**Divergent case:** a prior compatible artifact is restored for future decisions after a defective
release. This is rollback; simply stopping the defective release without restoring an earlier version
is pause.

### 2.4 `A6`: redesign and termination

#### Redesign

**Object changed:** the policy mechanism, decision rule, treatment content or architecture is materially
reconceived.

**Entry evidence:** identified theory/design failure, unacceptable mechanism, persistent unresolved
state past a decision clock where a new design is legally permitted, or a ratified redesign mandate.

**Authority and version:** redesign cannot be inferred from a threshold. It requires competent design
and adoption authority. The result is `V3_redesigned`, a new causal object.

**Claim consequence:** the old claim does not validate the redesign. New estimand, assumptions and
prospective evidence are required; old evidence remains historical context only.

**Exit/restart:** redesign exits through a new design/adoption/ratification path, not the restart gate
of the prior version.

**Divergent case:** the delivery worked as designed but the mechanism caused strategic substitution.
Changing the mechanism is redesign, not implementation adjustment.

#### Termination

**Object changed:** legal or operational permission to continue the named intervention or exposure.

**Entry evidence:** competent terminal decision based on confirmed unacceptable state, legal expiry,
prohibition, exhausted authority, or another declared terminal basis. Cause may remain uncertain if the
legal/safety clock independently compels termination.

**Authority and version:** only the competent terminal authority may set `X4_terminated`. Research does
not appoint that authority.

**Claim consequence:** termination and causal-claim withdrawal are distinct. A historical causal claim
may remain true after termination; conversely a causal claim may be withdrawn while an external policy
continues under a separate legal or protective basis.

**Exit/restart:** terminal for the named authorization. Reintroduction is a new authorization/version,
not ordinary restart.

**Divergent case:** no redesign is adopted and permission ends. A conforming consumer terminates rather
than inventing a replacement design.

### 2.5 Conflict rules: VOI, clocks and asymmetric loss

The following order governs a proposed transition:

1. **Hard legal or safety constraint:** a prohibition, expiry, maximum exposure or mandatory review
   clock cannot be bought off by expected information value. Reach the required terminal, containment
   or escalation disposition by the clock.
2. **Protective envelope:** before the hard clock, compare the value of additional information with
   measurement cost, expected harm while waiting and irreversible exposure while waiting. If continued
   exposure exceeds the predeclared envelope, contain or pause even when cause is unresolved.
3. **Premature-action loss:** choose the least irreversible action that controls waiting harm. A
   reversible no-expansion or pause may be admissible at lower causal certainty than redesign or
   termination.
4. **No common scalar by default:** benefit, guardrail harm, authority, legal constraint and
   reversibility are non-compensable predicates unless a competent regime explicitly declares a lawful
   decision rule.
5. **Evidence will not arrive before the clock:** escalate to the competent decision maker with
   uncertainty preserved. Do not fabricate certainty or silently continue.

This discharges the conflict question: VOI informs choices inside the lawful protective envelope; it
does not override law, authority or a predeclared safety ceiling.

## 3. `AUD-F06` — Factored But Constrained State Product

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:112`.  
Disposition: `accepted`.

E/X/V/C is retained and the orthogonality claim is withdrawn. The authoritative amended predicates and
forbidden tuples are in `amendment-state-invariants.md`.

The state model now requires:

```text
StateInvariant(E, X, V, C, history, authority)
AllowedTransition(old_state, event, evidence, authority)
```

and encodes at minimum:

- `V2_patched_or_reissued + C0_confirmatory_intact` is forbidden absent valid equivalence evidence;
- `E4_confirmed_unacceptable + X4_terminated + C0_confirmatory_intact` is forbidden for the same
  unacceptable positive claim object;
- `V4_rolled_back + X0_full` is forbidden without separate restart evidence and bounded probe;
- `C3_withdrawn` does not imply `X4_terminated` when an independently evidenced legal, protective or
  emergency basis permits external policy continuation;
- termination does not automatically erase a historically valid causal claim;
- every cross-axis co-transition carries its own evidence and competent authority.

No state engine or mutation suite is claimed implemented.

## 4. `AUD-F08` — Response Corpus Falsifiability

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:114`.  
Disposition: `accepted_with_variation`.

No twenty thin scenarios were produced. Grounded initial states, event sequences, authority records,
sealed expected transitions and an independent evaluator do not exist at the pin. Placeholder inputs
would make the package appear falsifiable without creating a property-bearing fixture.

`amendment-response-corpus-gap.md` is the authoritative gap record. It:

- records zero instantiated and zero placeholder packets;
- specifies immutable packet identity, current state, ordered events, expected/forbidden transition,
  authority, execution, claim/version and restart fields;
- requires requested, authorized and executed state to be asserted separately;
- requires identical-threshold paired cases that diverge on authority, maturity, waiting harm,
  reversibility, version, duplicate status or restart evidence;
- separately exercises all operations discharged in §2;
- encodes the required illegal E/X/V/C tuples and the independent-basis reverse case;
- leaves `closure_test_AUD-F08: unmet`.

The stage-1 “20-scenario response corpus” is amended to “specified future 20-scenario response corpus”
until real packets, oracle records and an evaluator are delivered.

## 5. `AUD-F11` — Evidence-Register Traceability

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:117`.  
Disposition: `accepted`.

The audit's rejected list hypothesis remains rejected: both registers retain their original six
substantive columns. The surviving traceability cost is accepted. Both evidence registers now add:

```text
Evidence refs
Kind / transfer
Falsifier or resolution
Research artifact note
```

Every row therefore links to supporting repository/source IDs or amendment artifacts, states what kind
of evidence is being transferred, and names a falsifier or resolving evidence. The added descriptive
note keeps “research sketch” outside capability standing. This same register revision also implements
`AUD-F09`; it does not restructure the six-column disposition ledger.

## 6. Commendations Owned By OPS-R5

### `AUD-F15` — Rare `refuted` standing preserved

Audit record: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:121`.  
Disposition: `accepted`.

`OPS-F06` remains `refuted`. The amendment does not reintroduce a universal linear ladder; it repairs
the substitute by making E/X/V/C factored but constrained.

### `AUD-F16` — Both institutional blockers preserved

Audit record: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:122`.  
Disposition: `accepted`.

`INT-F17` and `OPS-F14` remain `blocked`, with `capability_standing: absent/unallocated` and
`gate_standing: NO_GO`. The unblocker remains external appointment or preauthorization evidence for
the exact operation, scope and time. No signer, adjudicator, revision board or owner is appointed.

### `AUD-F17` — Reuse-first topology preserved

Audit record: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:123`.  
Disposition: `accepted`.

The amendment continues to reuse N8 carriers, DDM/FDR signals, monitoring, continuous governance, S13,
Fabric and Atlas within their bounded owner roles. It creates no parallel post-deployment platform and
does not treat a fragment as the missing admitted chain.

### `AUD-F18` — Protection/learning and source/destination separation preserved

Audit record: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:124`.  
Disposition: `accepted`.

A preauthorized protective response may still occur at lower causal certainty than effect learning.
Unresolved or observation-invalid evidence freezes posterior/world mutation but need not forbid a
lawfully preauthorized no-expansion, containment or pause. SMDV source diagnosis still precedes and
does not replace S13 destination accountability.

## 7. OPS-Owned Disposition Register

| Audit finding | Severity | Disposition | Audit line | Amendment line | Recorded outcome |
|---|---|---|---|---|---|
| `AUD-F02` | `material` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:108` | `ops-r5/amendment-ledger.md:28-276` | Four collapsed families discharged operation by operation, including authority, version, claim, reversibility and divergent cases. |
| `AUD-F06` | `material` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:112` | `ops-r5/amendment-ledger.md:277-304` | E/X/V/C retained as factored but constrained; predicates and required tuples encoded. |
| `AUD-F08` | `material` | `accepted_with_variation` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:114` | `ops-r5/amendment-ledger.md:305-328` | Thin scenarios refused; packet/evaluator contract registered; closure unmet. |
| `AUD-F11` | `minor` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:117` | `ops-r5/amendment-ledger.md:329-350` | Original six register columns retained and four traceability columns added. |
| `AUD-F15` | `commendation` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:121` | `ops-r5/amendment-ledger.md:351-358` | `refuted` universal ladder preserved. |
| `AUD-F16` | `commendation` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:122` | `ops-r5/amendment-ledger.md:359-367` | Both institutional blockers and external unblocker preserved. |
| `AUD-F17` | `commendation` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:123` | `ops-r5/amendment-ledger.md:368-376` | Reuse-first topology preserved. |
| `AUD-F18` | `commendation` | `accepted` | `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:124` | `ops-r5/amendment-ledger.md:377-386` | Protection/learning and source/destination separation preserved. |

## 8. Cross-Ledger Arithmetic

The INT ledger owns ten findings and records the joint arithmetic. This ledger owns eight:

```text
accepted                     7
accepted_with_variation      1
routed_pending_principal     0
declined_with_reason         0
                           ---
OPS-owned total              8
```

Joint totals, including the INT-owned routed finding:

```text
accepted                    14
accepted_with_variation      3
routed_pending_principal     1
declined_with_reason         0
                           ---
total                       18
```

Severity remains:

```text
0 blocking + 9 material + 2 minor + 7 commendation = 18
```

## 9. Open Closure Tests

```yaml
AUD-F02_research_argument: amended
AUD-F06_factored_constrained_model: amended
AUD-F06_state_engine_and_mutations: absent/unallocated
AUD-F08_response_corpus: absent/unallocated
AUD-F11_register_traceability: amended
audit_verdict_lifted: false
```

Only stage-4 amendment verification may decide whether the findings close.

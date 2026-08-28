---
task_id: INT-R3
stage: 1
artifact_role: benchmark_specification
schema_name: AuthorityUIComprehensionBenchmark
status: research_complete
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - benchmark_protocol_candidate
  - red_first_surface_constraints
  - metric_definitions
  - ground_truth_procedure
may_not_use_for:
  - claim_that_benchmark_was_run
  - operator_comprehension_claim
  - governance_threshold
  - human_subject_authorization
---

# `AuthorityUIComprehensionBenchmark` specification

## 1. Claim under test

For a frozen PolicyOS build and a declared operator population, can an operator under realistic
conditions identify the binding constraint and take an action admitted by the governing rule when the
surface contains:

1. a weakest link;
2. a set-valued quantity;
3. explicit `unknown`;
4. `incomparable`;
5. a conditional δ budget;
6. a stale epoch or invalid validity window;
7. quarantined evidence;
8. an acquisition route?

This instrument measures terminal behavior and interaction trace. Preference, satisfaction,
self-reported clarity and unaudited paraphrase are not correctness outcomes.

## 2. Pre-build red-first contract

A slice may consume this stage-1 result before its surface is finished. Each predicate is stated so a
semantic/component/e2e test can fail before the positive implementation exists.

| ID | Required property | Red witness |
| --- | --- | --- |
| `AUI-R01` | Overall posture is governed by the registered weakest-boundary rule; the binding link is programmatically and textually associated with the result. | `[supported, supported, blocked]` is presented as average/majority supported, or the blocking link cannot be named through the accessible path. |
| `AUI-R02` | Set membership is preserved without inventing a point or an internal distribution. | `[2,8]` is rendered as `5`, a single marker, or a gradient that implies unlicensed density. |
| `AUI-R03` | `unknown`, numeric zero, missing observation, not applicable and unavailable remain distinct types with distinct decision consequences. | A counterfactual twin changes `unknown` to `0` without changing rendered/action state. |
| `AUI-R04` | `incomparable` means that no strict ranking is admissible under the current relation. | The UI orders the pair, emits equal scores as a tie, or permits a ranking-dependent commit without a new criterion/authority act. |
| `AUI-R05` | Every δ figure is inseparable from obligation set, basis, cutoff, unknown remainder, TTL and remaining-versus-spent semantics. | The number remains visible or actionable when its rider is removed from visual and accessibility structures. |
| `AUI-R06` | Observation time, epoch, decision validity and expiry are separately perceivable; stale/invalid evidence cannot be consumed as current. | A stale packet retains the same action affordance and accessible name as its fresh twin. |
| `AUI-R07` | Quarantine is an admission state, not a freshness adjective; quarantined evidence cannot satisfy a required evidence slot. | A quarantined record is selectable as admitted or counted toward pass. |
| `AUI-R08` | A blocked case exposes a concrete next transition: acquire, escalate or abstain/defer, with reason, owner and closure/revisit trigger. | The only safe route is hidden under generic help, hover, pointer-only control or unbound prose. |
| `AUI-R09` | Accessible order preserves `result → binding reason → consequence → available transition → drill-down`; equivalent relations exist without visual adjacency. | All atoms are present in the accessibility tree but the qualifying relation is absent or separated beyond a meaningful group. |
| `AUI-R10` | Unsafe attempt and unsafe committed action are distinct events. | A disabled button is reported as comprehension success without observing the operator’s attempted choice. |
| `AUI-R11` | Confidence is collected after terminal choice and before feedback, against admissibility of that choice. | Confidence is a general comfort rating or is collected after correctness is disclosed. |
| `AUI-R12` | No item is scored without a sealed semantic key, scenario manifest, action-admissibility set and eligibility flags for every denominator. | The answer key is revised after seeing participant responses or reviewer preference. |

## 3. Unit of analysis and terminology

For trial `i`:

- `s_i`: sealed scenario state;
- `A_i*`: non-empty set of admissible terminal actions;
- `a_i`: first terminal action committed by the participant;
- `a_i_attempt`: attempted action before a technical interlock, if any;
- `B_i`: set of true critical blockers;
- `Bhat_i`: blockers explicitly identified through action or required selection;
- `P_i = 1` when `PASS/CLEAR` is prohibited;
- `C_i = 1` when irreversible `COMMIT/EXECUTE` is prohibited;
- `O_i = 1` when the participant is exposed to a prohibited override opportunity;
- `Q_i`: presented evidence items adjudicated invalid because stale, expired or quarantined;
- `p_i`: reported probability in `[0,1]` that `a_i` is admissible;
- `y_i = 1[a_i ∈ A_i*]`;
- `tau_i`: administrative deadline for the trial.

The scenario-bound terminal-action vocabulary may include `PASS`, `COMMIT`, `ACQUIRE`, `ESCALATE`,
`ABSTAIN/DEFER`, `REQUEST_NEW_CRITERION` and `CANCEL`. This benchmark does not create a parallel
PolicyOS status lattice.

## 4. Ground truth

### 4.1 Three layers

1. **Semantic truth** — registered type and composition rules: `unknown` is not zero or missing;
   quarantined is not admitted; stale/invalid cannot satisfy a currentness predicate;
   `incomparable` has no strict order; weakest-boundary composition follows its owner.
2. **Scenario truth** — frozen facts: packet bytes, timestamps, epoch, provenance, blockers,
   authority limits, available routes and distractors.
3. **Normative-operational truth** — the set `A_i*` of actions the governing policy permits for that
   state.

A participant is not required to guess the hidden state of the world. Correctness means acting within
`A_i*` given what is admissibly knowable.

### 4.2 Item authoring and adjudication

1. An item author generates a scenario from the factorial grammar and seals all latent facts.
2. An independent semantic verifier applies the registered vocabulary and composition rules without
   seeing pilot responses.
3. Two operational adjudicators independently classify every candidate action as `required`,
   `acceptable`, `prohibited` or `policy_silent`, citing the governing source.
4. They receive the first-round distribution, discuss only source application and rate again
   independently.
5. `A_i*` contains every `required` or `acceptable` action with no unresolved prohibition.
6. Material disagreement or `policy_silent` produces item state `contestable`. A contestable item is
   excluded from primary correctness and retained separately unless a set-valued key honestly
   resolves the disagreement.
7. A second blinded panel is required before certification use. Inter-panel disagreement remains
   visible.
8. The key, source versions, adjudicator roles, pre/post ratings, dissent, item digest and date are
   sealed before recruitment.

No appointed operational or research adjudicators currently exist in the repository. This is a
candidate procedure with an explicit institutional dependency. A developer, researcher or model may
not impersonate the missing authority.

### 4.3 Item invalidation

An item becomes `invalid` and leaves every primary denominator if:

- the semantic rule is ambiguous or unregistered;
- scenario facts do not reproduce from the sealed manifest;
- the action policy changes after sealing without versioned re-adjudication;
- a display variant leaks the answer through non-semantic wording;
- accessible and visual conditions do not carry equivalent propositional content;
- event logging cannot distinguish attempt, commit and timeout.

## 5. Scenario grammar and item bank

### 5.1 Crossed factors

Construct scenarios by crossing rather than hand-authoring one example per concept:

- weakest-link location: first/middle/last; one versus multiple blockers;
- quantity: point, interval/outer set, explicit unknown, numeric zero, missing, not applicable;
- ordering: strict rank, tie, near-equal, incomparable, insufficient evidence;
- δ: remaining/spent; low/high absolute amount; basis present/absent; TTL current/expired;
- time: fresh/stale; same/different epoch; validity active/expired; six perturbation classes;
- provenance: admitted/quarantined/provisional/contested;
- route: acquisition possible/impossible; owner available/unavailable; authority present/absent;
- consequence: reversible/irreversible; low/high harm;
- deadline: ordinary versus preregistered pressure condition;
- distractor density and position;
- modality: visual/pointer, keyboard-only, screen reader, low-numeracy stratum and intersections.

### 5.2 Counterfactual twins

Each critical family includes twins where exactly one decision-relevant state changes:

- `unknown ↔ 0`;
- `unknown ↔ missing`;
- outer set ↔ probabilistic interval;
- incomparable ↔ tie;
- fresh ↔ stale;
- admitted ↔ quarantined;
- δ remaining ↔ value/benefit signal;
- authority appointed ↔ not appointed;
- acquisition route available ↔ structurally impossible.

Wording and layout remain otherwise matched. A participant never sees both literal twins in one
scored block.

### 5.3 Bank protection

- between-display assignment for the primary comparison;
- different scenario families in any crossover;
- counterbalanced order;
- no correctness feedback during scored blocks;
- held-out factor combinations and paraphrase families;
- versioned bank and leak audit;
- rotate items after exposure;
- analyze participant and scenario as crossed random factors.

## 6. Conditions and accessible-path instrument

Accessibility is part of the instrument, not an annex.

### 6.1 Conditions

1. **Visual/pointer reference condition** on the frozen supported browser.
2. **Keyboard-only:** pointer disabled; focus path, shortcuts, tab stops and traps logged.
3. **Screen reader:** target users operate their own or a supported familiar AT; reader, version,
   browser, speech rate, Braille/magnification and input modality recorded.
4. **Low-numeracy stratum:** measured with a task-relevant instrument; title, education and tenure
   cannot substitute.
5. **Time pressure:** objective deadline and subjective pressure recorded separately.
6. Preregistered intersection cells where recruitment permits; no aggregate accessibility score may
   hide a failing modality.

### 6.2 Semantic equivalence

The accessible representation must expose, as one navigable relation:

`overall state → binding link → why it binds → decision consequence → available safe transition`.

An accessible table containing every component is insufficient if it omits that relation. Overview,
selective query/drill-down and raw detail must all be available. No essential condition may be
hover-only, color-only, icon-only, visually adjacent only or placed after an irreversible action.

### 6.3 Timing origin

Two clocks are recorded:

- `t0_system`: case request to actionable accessible state, end-to-end;
- `t0_interaction`: visual surface stable or, for AT, accessibility tree and initial focus ready.

Primary cognitive/navigation latency uses `t0_interaction`; operational experience also reports
`t0_system`. This prevents rendering latency from being silently counted as comprehension while
preserving its real cost.

Concurrent think-aloud is not used in timed scored trials. Retrospective probing occurs only after
the terminal action and confidence response. Separate formative sessions may use think-aloud.

## 7. Trial procedure and event log

1. Capture participant stratum and environment without exposing scored semantics.
2. Load the sealed scenario and record packet/build/item digests.
3. Declare `t0_system`; declare `t0_interaction` only when the assigned path is actionable.
4. Log every focus, navigation, evidence-open, action-attempt and route-open event monotonically.
5. First terminal commit ends a terminal-decision trial. Recoverable practice trials are separate.
6. Immediately collect `p_i`: “What is the probability, 0–100%, that your chosen action is permitted
   by the rules for this case?”
7. Collect a non-leading retrospective reason and blocker selection for diagnostics.
8. Do not show correctness until the scored block ends.
9. Seal raw event bytes and derive metrics reproducibly.

Required event fields: run, participant pseudonym, item, display/build, condition, AT and browser,
event id, monotonic and wall clocks, action, mode, evidence reference, blocker reference, route,
interlock result, terminality and source digest. Duplicate event ids are idempotent; conflicting
duplicates invalidate the trial pending reconciliation.

## 8. Mandatory metrics

Every metric is reported by construct, condition and operator stratum with numerator, denominator and
uncertainty interval. No metric is satisfied by an opinion.

### 8.1 `false_action`

```text
numerator   = count of trials with C_i = 1 and a_i in {COMMIT, EXECUTE}
denominator = count of scored trials with C_i = 1
```

An attempted prohibited action blocked by an interlock is a separate
`attempted_false_action`. It does not enter the committed numerator and does not count as
comprehension success.

### 8.2 `false_pass`

```text
numerator   = count of trials with P_i = 1 and a_i = PASS/CLEAR
denominator = count of scored trials with P_i = 1
```

This includes blocker-present cases and epistemic cases where pass cannot be established because
required state is `unknown` or evidence is invalid.

### 8.3 `missed_blocker`

Primary scenario-level measure:

```text
numerator   = count of trials where |B_i| > 0 and B_i is not a subset of Bhat_i
denominator = count of scored trials where |B_i| > 0
```

Diagnostic instance-level measure:

```text
sum_i |B_i minus Bhat_i| / sum_i |B_i|
```

Report false-blocker instances separately so an indiscriminate “mark everything blocked” strategy
cannot look competent.

### 8.4 `unsafe_override`

```text
numerator   = count of trials with O_i = 1 where a prohibited override is committed
denominator = count of scored trials with O_i = 1
```

Also report:

- override-attempt rate among `O_i = 1`;
- blocked-attempt rate;
- route abandonment after a blocked attempt;
- appropriate-override rate only for separately adjudicated permitted-override items.

An overall override rate without type and admissibility is forbidden.

### 8.5 Time to correct action

For recoverable non-scored practice:

```text
T_i = first stable entry into A_i* minus t0_interaction
```

No correct state by deadline is right-censored at `tau_i`.

For scored terminal-decision trials, correct and incorrect terminal actions are competing outcomes.
Report:

- `Pr(correct by tau)`;
- `Pr(incorrect terminal by tau)`;
- latency distribution for correct events;
- restricted mean time to correct on the common horizon, alongside probability of correctness;
- end-to-end equivalents from `t0_system`.

Never assign failures `timeout + 1` and average them with successes.

### 8.6 Confidence-versus-correctness calibration

With `y_i = 1[a_i ∈ A_i*]` and confidence `p_i`:

```text
Brier = mean((p_i - y_i)^2)
```

Report a calibration curve with uncertainty, calibration intercept and slope where estimable, and
signed mean bias `mean(p_i) - mean(y_i)`.

The dangerous cell is always direct. For a preregistered governance confidence threshold `h`:

```text
HCW burden_h            = count(y_i=0 and p_i>=h) / all scored trials
HCW share of errors_h   = count(y_i=0 and p_i>=h) / count(y_i=0)
high-confidence error_h = count(y_i=0 and p_i>=h) / count(p_i>=h)
critical HCW_h          = count(critical_i and y_i=0 and p_i>=h) / count(critical_i)
```

Stage 1 does not select `h`; that is a governance predicate requiring an appointed risk owner. Until
then, publish the full threshold curve.

### 8.7 Construct diagnostics

- invalid-evidence acceptance: invalid items used as admissible / all presented invalid items;
- unknown-collapse rate: discriminating unknown items producing a zero/missing response pattern /
  all discriminating unknown items;
- unrankability failure: unsupported strict ranking / all incomparable trials;
- δ-budget inversion: action/reasoning treats low residual allowance as positive value or safety /
  all discriminating δ trials;
- acquisition-route correctness and route-completion latency;
- false-blocker/false-alarm rate.

These diagnostics do not replace the six mandatory metrics.

## 9. Analysis and acceptance discipline

### 9.1 Statistical model

Primary analysis treats participants and scenarios as crossed random factors and includes
surface/condition, construct and preregistered interactions. Repeated trials from one participant are
not independent opportunities. Report raw exposure denominators beside model estimates.

### 9.2 Power and precision

No fixed participant count is established here. Before recruitment, simulate power/precision using:

- target operator and scenario variance;
- baseline eligible error rate;
- minimum operationally important difference or maximum acceptable upper bound;
- clustering and repeated measures;
- multiplicity across co-primary safety endpoints;
- number of **eligible** unsafe-action, pass and override opportunities.

Zero observed events is not zero risk. Any “rule of three” bound is only a simple independent-event
diagnostic and cannot ignore clustering.

### 9.3 Co-primary safety rule

`false_action`, `false_pass`, `missed_blocker` and `unsafe_override` remain separate co-primary safety
cells. No favorable average or expected-loss score compensates for a failed critical cell. An
optional loss matrix may be reported only after an accountable governance owner approves its
weights.

### 9.4 Claim ladder

| Evidence | Permitted claim |
| --- | --- |
| structural/component tests only | surface conforms to named structural properties |
| stage-1 specification | a defensible benchmark candidate exists |
| pilot with target users | instrument usability and item defects characterized; no production claim |
| sealed main study | performance for declared build, population and conditions |
| independent replication | reproducibility for declared scope |
| shadow/field validation | relationship to real operation |
| actual-use evidence | operational comprehension claim for the bounded context |

## 10. Validity and explicit non-claims

### Construct validity

Correct action, blocker detection, invalid-evidence rejection, unrankability and calibration are
separate outcomes. Preference cannot satisfy any of them. A participant can identify a blocker and
still take an unsafe action; both results remain visible.

### Internal validity

Counterfactual twins, sealed keys, blinded adjudication, no scored feedback and exact event-byte
capture reduce answer leakage and post-hoc key movement.

### External validity

A simulation result is not actual use. Operator selection, consequences, workload, hierarchy, local
policy and escalation response can change behavior. Later validation must test transport.

### Accessibility validity

Equivalent atoms without equivalent relations are not equivalent stimuli. Modality-specific timing
and error cells remain visible. A screen-reader condition run only by a sighted researcher is not a
substitute for target users.

### Explicit non-claims

This specification does not establish:

- that any current PolicyOS surface is comprehensible;
- that typed refusals are actionable under pressure;
- that accessibility conformance implies comprehension;
- that a low-numeracy display solution has been found;
- that any acceptance threshold or governance loss matrix is authorized;
- that the literature predicts a PolicyOS error rate;
- that human subjects were recruited or studied.

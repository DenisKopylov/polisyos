---
task_id: INT-R3
stage: 2
artifact_role: formal_argument_audit
audit_target: 819a83a88315a90320fdd4b25fcb328b434c77de
branch: research/int-r3-independent-audit
verdict: GO_WITH_REVISIONS
status: complete
---

# INT-R3 formal argument audit

## Audit method

The audit treated the stage-1 package as a set of falsifiable claims, not as a well-presented
specification. All eight package files were read before the audit branch was written. The audit then
checked the package against:

- `docs/reference/policy-operations-research-pipeline.md`, especially §2, §3.2, §4 and §5;
- `docs/research/policy-operations-and-real-world-runtime-backlog.md`;
- `docs/system-design-decisions/wave4-decision-evidence-ratification.md`, especially `W4-K01`,
  `W4-K05` and `W4-K06`;
- the stage-1 orientation supplied to the researcher;
- the five commissioned survey inputs;
- the pinned source files and active Atlas plan at `dc7bdf79a`.

A claim was accepted only where its source, transfer argument and boundary all held. A limitation was
not treated as a defect merely because it remains open; the test was whether the package states the
resolving evidence and prevents the open state from silently supporting a positive.

## T1 — Executability

**Position: the protocol is coherent and executable in principle, but executability in this programme
is not established.** The stronger hypothesis — “this can never be run here” — was not established.
The package defines a frozen build, scenario manifests, event semantics, eligible denominators,
accessible conditions, blinded adjudication and a layered evidence ladder. Nothing in that design is
logically impossible.

The package nevertheless calls the result an “implementable benchmark specification” without a
programme-specific feasibility basis. The repository supplies no admitted recruitment frame for real
target operators, no operator-population size, no ethics/consent route, no accessible-research support
plan, no staffed adjudication panel, no pilot budget and no precision calculation against a plausible
number of participants and scenarios. Those are not all PolicyOS-owned functions, but they determine
whether this protocol is executable rather than merely specifiable.

The correct current statement is therefore:

```yaml
protocol_coherence: established
technical_implementability: plausible_not_demonstrated
programme_execution_feasibility: not_established
human_study_execution: absent
```

This is `INT-R3-AUD-F007` (`material`). It is repairable by a feasibility gate, not by inventing an
institution: identify a deployment sponsor or recruitment frame; declare the first operator
population; document the ethics/consent determination route and accessibility accommodations; and
show that a pilot and a main-study precision target are feasible under the available operator and item
denominators.

A separate seam defect sharpens this result. The package says the canonical benchmark owner is
missing. The Atlas master plan already states that **DS6 owns the instrument** and that INT-R3 supplies
the benchmark content. The audit does not assume that a closed DS6 slice can still execute that
ownership; it requires the conflict to be adjudicated. Reporting an unqualified zero was wrong.
That is `INT-R3-AUD-F012` (`material`).

## T2 — Falsifiability

**Position: all twelve predicates can fail, but they are not twelve behavioral-comprehension tests.**
Most are surface semantics, enforcement or measurement-integrity constraints. They are useful
preconditions. They cannot establish the human claim.

| Predicate | Can it fail against the named surfaces? | What it actually tests | Can it go green without a real operator? |
| --- | --- | --- | --- |
| `AUI-R01` | yes | weakest-boundary rendering plus, in its action arm, chain use | partially |
| `AUI-R02` | yes | no point/distribution invented from an outer set | yes |
| `AUI-R03` | yes | typed distinction among `unknown`, zero, missing, N/A and unavailable | yes |
| `AUI-R04` | yes | no unsupported strict order or ranking-dependent affordance | yes |
| `AUI-R05` | yes | δ rider remains bound in visual and accessible structures | yes |
| `AUI-R06` | yes | time/currentness presentation and affordance policy | yes |
| `AUI-R07` | yes | quarantine cannot satisfy an admitted-evidence slot | yes |
| `AUI-R08` | yes | a concrete safe transition is exposed | yes |
| `AUI-R09` | yes | accessible propositional relation, not node presence | yes |
| `AUI-R10` | yes | attempted action is distinguishable from committed action | only after an attempt is observed |
| `AUI-R11` | yes | confidence timing and construct validity | yes, as protocol conformance |
| `AUI-R12` | yes | pre-sealed key and denominator integrity | yes |

The package generally knows this: its claim ladder says structural tests prove only structural
properties. The defect is taxonomic. The suite is presented as one red-first battery without a typed
partition between `surface_semantic_contract`, `enforcement_contract`, `instrument_integrity` and
`behavioral_trial`. This invites a later consumer to report “12/12” as behavioral closure. That is
`INT-R3-AUD-F009` (`minor`).

One predicate has a substantive false-positive boundary. `AUI-R06` treats unchanged action affordance
between fresh and stale twins as a red witness. Staleness is not universally action-dispositive: the
affordance may correctly remain available where the act is not currentness-dependent, another current
source satisfies the predicate, or the governing rule permits a recorded override. The package’s own
external synthesis distinguishes stale, provisional and quarantined states. The red must be scoped to
a **currentness-dependent action whose admitted basis is the stale item**. Without that scope, a
correct surface can fail the test. That is `INT-R3-AUD-F008` (`material`).

No predicate was found to be literally unfalsifiable. The audit did find that ten of twelve can be
satisfied before any human trial, which is why none may close comprehension.

## T3 — Transfer arguments

**Position: the transfer discipline is real, but two of the seven `accepted_narrow_scope` rows rely on
a template more than an argument.** The actual stage-1 register has eighteen findings, not ten. Seven
carry `accepted_narrow_scope`: `F004`, `F005`, `F006`, `F007`, `F009`, `F010`, and `F015`.

| Finding | Audit of transfer |
| --- | --- |
| `F004` | earned. Separating notice/recall/preference from action is a measurement-layer argument and maps directly to terminal-action scoring. |
| `F005` | incomplete. Search compression and miss shifts are credible mechanisms, but the package does not bind them to an actual PolicyOS operator role, deadline distribution, interruption topology or decision surface. |
| `F006` | earned as a denominator rule. “Override” is heterogeneous, so prohibited opportunities must be typed and separately adjudicated. No source-domain rate is imported. |
| `F007` | incomplete. The source work concerns conjunctive probabilities and intervention allocation; PolicyOS may use deterministic all-must-pass or governance-min composition. The package names the distinction but does not show which mechanism survives it. |
| `F009` | earned narrowly. Serial access can preserve atoms while losing relations; the benchmark’s relation-parity requirement maps to that mechanism without importing an effect size. |
| `F010` | earned narrowly. Title and tenure are not valid substitutes for measured numeracy or AT proficiency; no population prevalence is transferred. |
| `F015` | not a cross-domain transfer. It is a cautious architectural inference: no direct PolicyOS study was found, so no contradiction with the demonstrability ruling is established. |

`F005` and `F007` need a surface-specific bridge: name the shared causal or information-processing
relation, the target population and workflow, the condition under which the relation is expected to
hold, and one divergent case where the external mechanism would not apply. The repeated phrase
“mechanism transfers; rates do not” is not enough by itself. This is `INT-R3-AUD-F004`
(`material`).

The package deserves a separate commendation for refusing to import override, numeracy or
accessibility rates and for preserving the NDM versus heuristics-and-biases disagreement. That is
`INT-R3-AUD-C005`.

## T4 — System-specific constructs

**Position: PolicyOS-specific content remains, but the four most novel constructs do not have
construct-specific closure evidence.** `F008` correctly marks explicit epistemic `unknown`, pure
outer sets, strict UI incomparability and δ-budget interpretation as `deferred_open_problem`. The
specification still contributes PolicyOS-specific scenario grammar, counterfactual twins, event
semantics, action choices and real-surface integration. It is not merely a generic decision-support
protocol.

The residual is nevertheless under-specified. For each of the four constructs, the package says “run
the benchmark” but does not state the evidence form that resolves the open problem. It omits the
construct-specific target population, comparator, primary behavioral endpoint, required eligible
opportunity count or precision goal, and whether semantic simulation is sufficient or field transport
is required. Governance thresholds may remain unappointed; the **kind of resolving evidence** may
not.

That is `INT-R3-AUD-F005` (`material`). A revision should add a four-row resolution table:

```text
construct -> discriminating contrast -> primary action/error endpoint -> population/condition
          -> minimum precision or appointed threshold dependency -> transport requirement
```

## T5 — Absorbing escapes

**Position: the escape band is unbounded.** No item bank exists, so the audit cannot estimate an
empirical proportion of realistic items that become `contestable` or `invalid`. The logical upper
bound under the current protocol is 100% of a hard construct/condition stratum: policy silence,
adjudicator disagreement, accessibility inequivalence or a logging defect can remove every hard item
from the primary denominator while easy semantic items continue to produce a headline score.

Set-valued `A_i*` is not itself the problem; it is the correct representation when several actions are
admissible. The defect is the absence of:

- a preregistered item-flow report from authored → verified → contestable/invalid → scored;
- minimum scored coverage for every mandatory construct and modality;
- a maximum tolerable contestable/invalid fraction or an appointed rule for setting it;
- a fail-closed result when the coverage floor is not met;
- a prohibition on publishing a single primary score after a hard stratum disappears.

This is `INT-R3-AUD-F006` (`material`). The amendment must not force consensus; it must bound what
exclusion can erase.

## T6 — Borrowed institutions

**Position: the institutional dependency is explicit, not hidden.** The specification says that no
operational or research adjudicators are appointed; requires two first-round adjudicators and a second
blinded panel before certification use; forbids a developer, researcher or model from impersonating
the authority; and leaves thresholds to an appointed risk owner. This satisfies the stage-1 warning
about borrowed institutions and is an acceptable residual rather than a package defect.

`unsafe_override` and `A_i*` therefore cannot be issued for policy-contestable items today. They can
still be derived for formal semantic items where the governing rule already prohibits the action. A
later artifact should preserve that provenance distinction, but the package does not silently claim
that the missing institution exists.

This is recorded as `INT-R3-AUD-C004` (`commendation`).

## T7 — Baseline absence claims

**Position: the key absence claim was not established by a complete walk.** `F003` says no admitted
human-comprehension evidence exists. The baseline method says source search followed concrete names
from the task into selected dashboard, schema, fixture and plan paths. It does not report a complete
tracked-file denominator, an executable census, file-type denominator, positive controls, negative
controls or the executing party. The same problem affects “no canonical behavioral event/result
contract” and “no benchmark owner,” the latter additionally contradicted by the Atlas master plan’s
DS6 allocation.

A sample can produce the right answer and still fail `P35`/`W4-K01`. The historic page counts are
handled better: the package labels them institutionally supplied and does not use them to settle a
zero.

This is `INT-R3-AUD-F002` (`material`). The amendment must either provide a complete pinned walk and
its receipt, or downgrade each zero to `not_established` with the searches actually executed.

The baseline also contains two positive anchor errors:

1. `TrustPosturePage.tsx` is cited as containing `TrustPosturePage` and `TrustPostureContent`; the
   pinned file contains the former and no `TrustPostureContent` symbol.
2. `TimeSemanticsLabel.tsx` is described as accepting `createdAt`, `asOf`, `updatedAt`, `validFrom`,
   `validUntil`, `freshness` and `generic`; the pinned component accepts `cacheAgeLabel`, `freshness`,
   `payloadAsOf`, `txAt` and `validAt`, and renders a different clock vocabulary.

This is `INT-R3-AUD-F001` (`material`).

## T8 — DS12 boundary

**Position: the package’s prose boundary is mostly narrow, but its `gate_standing` is semantically
mis-scoped.** The DS12 gate at the pin is the first governed promotion plus DS11 plus the named
pre-publication inputs `INT-R7`, `INT-R8`, `INT-R1` and preregistered `INT-R9`. INT-R3 is not a DS12
gate input. The master plan instead routes INT-R3 content to the DS6 instrument and then to the stable
bar for interactive authority surfaces.

`W4-K05` defines `gate_standing` as the first-public-signature gate. The package uses
`gate_standing: NO_GO` to mean “do not cite this package as comprehension evidence” and then says it
does not adjudicate unrelated publication gates. That is a useful claim-use restriction, but it is not
the registered meaning of the axis. The token happens to match the global DS12 state at the base, but
for a different reason. This is a P38 shape: correct value, wrong predicate.

This is `INT-R3-AUD-F010` (`material`). A revision must report the actual first-public gate and its
DS12 basis separately from a new sub-annotation such as:

```yaml
comprehension_claim_use: NO_GO
int_r3_is_ds12_gate_input: false
```

No INT-R3 result may open DS12, and absence of a benchmark result does not independently hold DS12
closed unless a later ratified rule adds that dependency.

## Additional attacks

### Metric contamination in `missed_blocker`

`Bhat_i` is defined as blockers identified through action or required selection, while the trial
procedure collects retrospective reason and blocker selection after terminal action and confidence.
If the primary `missed_blocker` numerator admits that retrospective selection, it measures post-choice
recognition and is vulnerable to reconstruction. The primary blocker observation must be an event
before or constitutive of the terminal action; retrospective selection must remain diagnostic. This is
`INT-R3-AUD-F011` (`minor`).

### External source traceability

The committed external-evidence ledger names source families and authors but does not bind its
sixteen `EXT-*` rows to durable URLs, DOI/report identifiers, page/table locators or committed survey
extracts. The five survey documents supplied to the researcher contain the detailed support, but they
are not part of the branch and their conversational citation identifiers are not a durable repository
reference. An independent audit cannot reproduce the claim-to-source chain from the package alone.
This is `INT-R3-AUD-F003` (`material`).

### What survived the hostile pass

Five properties were actively attacked and survived:

- no human-subject result is implied (`INT-R3-AUD-C001`);
- eligible denominators, attempt/commit separation and direct high-confidence-wrong cells are explicit
  (`INT-R3-AUD-C002`);
- accessible relation preservation is part of the core instrument and real AT users are required
  (`INT-R3-AUD-C003`);
- disagreement and missing institutional authority are preserved rather than laundered
  (`INT-R3-AUD-C004`);
- external rates are not imported and a live theoretical disagreement is retained
  (`INT-R3-AUD-C005`).

## Argument verdict

`GO_WITH_REVISIONS`.

No defect was found that a bounded amendment cannot repair. The protocol is not unexecutable in
principle and its central negative — current comprehension is `not_established` — remains correct.
The package cannot proceed unchanged because its mandatory repository baseline contains false
coordinates, its zero claims lack a complete walk, its source chain is not independently resolvable,
its hardest-item escape band is unbounded, its DS6 ownership seam is missed and its gate axis turns on
the wrong predicate.

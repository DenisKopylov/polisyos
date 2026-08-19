---
title: PAO-R4 independent audit — formal argument and falsifier audit
audit_id: PAO-R4
artifact_role: formal-argument-audit
status: independent-audit
research_only: true
verified_commit: a27c3da9942b03881dbee1005a8a1e44e5ac44b4
pinned_repository_commit: 1a7a2d05ebba22fae80e9934329e4b880806588e
authoritative_for:
  - independent Pass III through Pass VII findings for PAO-R4
  - audit counterexamples, compliant-but-undetected scenarios, and missing attacks
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization or API contract
  - canonical owner or vendor appointment
  - authority grant
  - capability claim
  - legal-sufficiency or jurisdictional compliance conclusion
  - permission to publish or open a gate
  - automatic amendment of any plan, backlog or system-design decision
  - modification of the audited branch
---

# PAO-R4 formal argument audit

## 1. Executive formal verdict

The sentence

```text
P ∧ C_B(x)=1 ⊭ I_x
```

captures an important and often neglected truth for **empirical aggregate or probabilistic claims**:
membership in a reference class does not, without more, establish the person's outcome, facts,
authority, or administrative disposition. It is not, however, a theorem over the report's stated
class of `P`. The definition admits singleton classes, pointwise-recoverable functionals, and
normative universal rules. For those objects, membership can entail a person-level result.

The useful result is therefore a typed rule, not bare logic:

> An empirical population summary, calibrated probability, group effect, or aggregate association
> may not fill an individual fact, evidence, reason, score, or determination slot. A normative general
> rule is a different object: it may be applicable to a person only together with competent authority,
> case facts, procedure, and individual reasons. An artifact that is pointwise recoverable is treated
> as individual even when encoded as a “population” aggregate.

PAO-R4 contains pieces of that distinction but does not make it formal. This defect propagates into
the crossing classes, refusal list, material-contribution test, and falsifier suite.

## 2. Pass III — object-by-object audit

| Object | Definition audit | Verdict |
|---|---|---|
| `Ω` | “Universe of possible subjects” is clear as a carrier set but has no subject-type, time, tenant, jurisdiction, or identity-equivalence boundary. | usable only with `B`; not independently closed |
| `B` | Lists population, jurisdiction, time, selection, method, assumptions, use, audience, cutoff. It does not define syntax, admissibility, truth conditions, completeness, or who verifies declarations. | load-bearing but declared rather than derived |
| `C_B` | Binary membership predicate is clear for crisp classes. It does not cover uncertain, disputed, missing, or probabilistic membership. | partial |
| `R_B` | Extensional class derived from `C_B`; may be singleton or pointwise-identifying. No minimum cardinality/non-reconstruction condition appears in the formal definition. | too broad |
| `D_B` | “data-generating or causal object licensed by B” is not operationally defined and can hide the very transport/reference-class judgment under audit. | under-defined |
| `Φ` | May be a mean, rate, distribution, treatment effect, calibrated group risk, elasticity, or “another bounded population proposition.” The last category admits pointwise or universal functionals. | too broad |
| `θ` | Output of `Φ`; type, uncertainty, scope and equality semantics are not fixed. | under-typed |
| `L` | Limitations and denied-use set carried with the proposition. Completeness and truth are declarations; omission is not detectable from the tuple itself. | load-bearing but self-authored |
| `I_x` | `ψ(x,F_x,Q,A)` usefully exposes case facts, competent rule/procedure and authority. It is not a proposition unless output/action semantics are supplied, but it is adequate as research notation. | useful abstraction |

The report itself acknowledges some of these issues later—subject resolution, composition,
non-executability, basis preservation, and purpose binding—but the formal non-entailment is stated
before those exclusion conditions and is written as universal.

## 3. Two required counterexample artifacts

### 3.1 Artifact A — singleton “population” rate

```text
Ω = all applicants
B = {population predicate: exact district + age + rare occupation + filing minute,
     method: descriptive mean, purpose: planning}
R_B = {x}
D_B = one binary outcome eligible(x)=0
Φ(D_B) = mean eligibility in R_B
θ = 0
L = [not for individual eligibility]
```

This satisfies the delivered tuple definition: it is a bounded descriptive population functional
with a declared basis and limitation. Yet `R_B={x}` and `θ=0` reveal the person's outcome. Thus

```text
P ∧ C_B(x)=1 ⊨ eligible(x)=0
```

extensionally, regardless of the author's “population” label. The crossing gate may catch this if it
has a complete auxiliary-information model; the formal definition does not.

### 3.2 Artifact B — full partition with deterministic cells

```text
B = declared population basis over three case features
R_1...R_n = complete mutually exclusive feature cells
for every cell j: Φ_j(D_B) = outcome rate in R_j, θ_j ∈ {0,1}
artifact = table of all (cell predicate, θ_j)
```

Every row is an aggregate claim over a reference class and can have more than one historical member.
For a new subject `x`, the table maps the subject's features to a unique cell and therefore to a
deterministic action. The artifact is functionally an individual decision tree even if no person row,
identifier, score field, or explicit threshold appears.

This counterexample is close to F-03, but its importance is formal: the tuple class does not exclude a
family of population claims whose joint semantics are pointwise.

### 3.3 Artifact C — normative universal rule

```text
G: for every applicant x, if lawful predicate Q(x) is proven, benefit eligibility follows.
```

`G` is a general population-level proposition and is intentionally individually applicable. With
competent authority and proved case facts,

```text
G ∧ Q(x) ⊨ eligible(x).
```

This is not ecological inference or statistical generalization. It is a normative rule. PAO-R4's
crossing table includes “general rule statement” alongside empirical estimates but denies all case
application and refuses any executable rule (`pao-r4-individual-decision-firewall.md:178-210@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). That conflation would block a legitimate
rule-level handoff as well as an illegitimate statistical shortcut.

## 4. Converse and disguised direction

The commission's sharp reverse case is not addressed by the non-entailment alone: an individual
determination can be **dressed as** a population claim. Examples include a cohort selected to contain
one subject, a deterministic partition table, or a query series whose differences isolate one case.
The report's later resolution/composition checks are the right response. The formal section should
name pointwise recoverability as the decisive predicate:

```text
individualizable(a, H) =
  there exists subject x and permitted auxiliary/history H such that a,H determine or materially
  constrain a protected action for x.
```

That is still model-relative; it is at least the correct object of the firewall. “Population” versus
“individual” cannot be decided from the quantifier label alone.

## 5. Decidability audit

The report says material contribution is counterfactual and observable: remove/change the artifact
while holding case facts and rule fixed, and ask whether the action changes
(`pao-r4-individual-decision-firewall.md:132-150@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). This is a useful causal definition, but the
interface later asks the consumer to report whether removal would have changed the action
(`:285-310`). Ordinary event logs do not establish that counterfactual. Without randomized removal,
predeclared procedural dependence, executable data-flow provenance, or a conservative rule that any
consultation counts as use, a good-faith operator may not know the answer.

The same problem appears in `B` and `L`: a complete basis and complete denied-use set are inputs to
the procedure, not products of it. The exporter can detect a missing declared field; it cannot detect
an omitted material assumption or an intentionally narrow auxiliary-information model from the tuple
alone. The report's `NOT_ESTABLISHED` posture is correct when the model is incomplete, but it lacks a
procedure for deciding model completeness.

The formalism therefore makes violations **classifiable once trusted inputs exist**; it does not make
the trustworthiness/completeness of those inputs decidable.

## 6. Pass IV — detection partition audit

### 6.1 What holds

The three-way distinction is high-value:

1. structural/boundary violations that can be decided before release;
2. actual-use violations that exist only in a downstream case process;
3. uses outside any complete observation boundary.

It forces the design to ask where the observable comes from and prevents “policy text” from being
confused with enforcement.

### 6.2 Misassigned export-time items

The report's heading says export-time detectable, but several listed items are not detectable from an
artifact alone:

| Listed item | Required information beyond artifact bytes | Correct classification |
|---|---|---|
| resolvable pseudonym/join key | identity resolver and auxiliary-information model | export-boundary detectable only if model is complete; otherwise `NOT_ESTABLISHED` |
| unsafe small cell/uniqueness | population universe, release history and external information | model-relative export/composition check |
| “complete enough” decision rule | semantic interpreter over code, prose, prompt, table, model and local case facts | behavioral export evaluation; false negatives remain possible |
| known composition exposure | complete controlled transcript and release-family identity | composition-time, not artifact-alone |
| stripped claim basis | authoritative source basis and materiality relation | detectable only for fields already registered as required; semantic omission can escape |

The report sometimes says exactly this (“from artifact, provenance, request, and controlled release
history”), so the defect is category naming and claimed certainty rather than total blindness. The
partition should separate `artifact-local`, `export-context`, `use-context`, and
`outside-declared-boundary` observables.

### 6.3 Exhaustiveness and boundary scope

The partition does not cover every way a population artifact can influence a case while leaving no
recognised individual-use event. Missing families include reference-class shopping, semantic-purpose
synonyms, UI/default ordering, local model training, and multi-consumer relay. Some can be folded into
“uncontrolled derivatives,” but a firewall claim needs an explicit boundary and an honest residual,
not an assumption that the three examples exhaust the world.

The returning section limits completeness to “the declared integration boundary.” That is correct.
The headline/result language should therefore say **firewall over that governed boundary**, not
“policy-level output must never” without the boundary qualifier.

### 6.4 Voluntary evidence argument

The core observational-equivalence argument is sound:

```text
world A: no prohibited use, no report
world B: prohibited use, no report
observed evidence: identical
```

No positive **complete absence-of-prohibited-use** claim follows. This is the strongest and most
portable result in the package.

The sentence that voluntary reporting “reduces the contract to a documented restriction or terms of
use” is too absolute. Voluntary reports can support narrower claims such as “these incidents were
reported,” a lower bound on observed uses, or evidence within a sampled audit. They cannot support the
firewall's universal/complete non-use proposition. The revision should preserve the impossibility
result and narrow the consequence.

## 7. Pass V — refusal list audit

### 7.1 Derived refusals

The following refusals follow directly from detection analysis:

- subject-resolvable rows and mappings;
- deterministic pointwise lookup/decision surfaces;
- composition-unsafe small cells where the controlled model cannot establish safety;
- any artifact whose required use-time evidence is voluntary or unverifiable.

For those classes, permitting export while claiming a firewall creates an unobservable violating
world. Refusal is a real, strong result.

### 7.2 Asserted or over-broad refusals

“Individual scores” and “executable rules” are grouped together without separating:

- a PolicyOS-produced statistical score proposed as an individual fact;
- a competent case system's own score under an external legal procedure;
- an official normative rule whose parameters are supposed to be applied to verified case facts;
- a descriptive calculation tool that has no authority and is gated from protected action.

PAO-R4 can refuse PolicyOS statistical artifacts from case authority without deciding that every
executable general rule is unsafe. The current list and F-03 make executability itself dispositive,
which is over-strict and conflicts with the report's own `Q` object (the competent rule/procedure).

The work does **not** forbid candidate-band computation generally. It limits refusal to crossing
toward case systems, permits a large aggregate in F-12, and states that authority—not computation—is
closed. The Stage-0 candidate-band lens therefore survives except for the normative-rule conflation.

## 8. Pass VI — fully compliant interface, prohibited use still undetected

### Scenario S-1 — cognitive reliance outside the declared instrumentation

1. A planning dashboard lawfully receives F-12's aggregate.
2. The case-system interface records all imports, derivatives, protected actions, and gate verdicts
   inside its declared technical boundary.
3. An operator sees the regional rate during planning, later handles the only applicant from that
   region, and gives the rate decisive weight without copying a file or invoking the artifact in the
   case system.
4. Every specified interface event is returned and reconciles. No event links the prior human memory
   to the case action.

A prohibited population-to-person use occurred, yet the returning interface is fully complied with.
The research acknowledges off-ledger manual use as not detectable; the unqualified firewall claim
must therefore be bounded to technically governed use, not institutional cognition.

### Scenario S-2 — complete logs, false counterfactual reliance record

1. The artifact is displayed in every case and all displays/actions are logged.
2. The operator sincerely records `without_artifact_action_changes=false` because they believe the
   population statistic merely confirmed their judgment.
3. A randomized removal would in fact change a significant number of actions.
4. The issue/use/action denominators and digests reconcile perfectly.

The interface is record-complete but semantically wrong about material contribution. Append-only
content binding proves what was recorded, not the truth of the counterfactual. The report requires a
non-producer verifier only “where a verification claim is made,” but does not define evidence that
can verify reliance.

## 9. Pass VII — falsifier suite

### 9.1 Commissioned and required cases

The suite contains all required subjects:

- F-01 population statistic used for individual eligibility;
- F-02 re-identification by joining permitted aggregates;
- F-03 individually applicable parameterized rule;
- F-04 projection narrows denied use under `PV-K04`;
- F-05 compliant-query sequence reconstructs an individual determination.

F-06 through F-14 add valuable human-review, reasons, correction, synthetic-resolution,
off-ledger, positive aggregate, incomplete-model, and derivative cases.

### 9.2 Core falsifier defect

F-01 declares `purpose: individual_eligibility_determination` before export
(`falsifier-suite.md:48-78@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`). That tests an honest request for a known denied
purpose. The commission's failure is **silent drift**: the consumer receives the artifact for an
allowed planning purpose and later applies it to a case in good faith with no red gate. F-01 must
start with an allowed request, then present a distinct downstream action/use event. Otherwise an
export-purpose block can pass while the actual use-time firewall is absent.

F-01 also specifies `export_or_request_gate`, `consumer_gate`, and `if_consumed_anyway` rather than
one exact world/outcome. A gate can satisfy “at least one pre-action gate” without proving the
consumer-side detector required by the commission.

### 9.3 Conditional fixtures

F-02 combines complete and incomplete history worlds; F-05 combines transcript-present and
transcript-absent worlds; F-07 uses `if_action_occurs`. These are useful requirements but not
single executable cases with one expected outcome. The suite-level statement that every case has an
exact expected verdict is therefore false in form. Split each world into its own fixture.

### 9.4 Three attacks not caught by the suite

#### A-15 — reference-class shopping

The consumer requests several legitimate, non-identifying cohort rates, all logged and permitted.
After seeing the person's features, it selects the cohort with the most adverse rate and uses that as
the reason for enhanced scrutiny. No unique outcome is reconstructed, no parameterized rule is
exported, and the action's declared purpose is “evidence review.” Existing F-02/F-05 do not require a
red result for adversarial reference-class selection.

#### A-16 — semantic-purpose synonym

A protected triage action is declared `workload_balancing`, while its effect is to delay one person's
service. The `may_not_use_for` set contains `individual_priority_or_triage`. The handoff mentions
synonym tests, but no falsifier proves that effect semantics defeat the benign string.

#### A-17 — counterfactual reliance laundering

All events are logged; the operator records that the artifact was not material; the artifact in fact
changed the outcome. F-07 supplies the correct counterfactual as test input instead of testing how it
is established. A marker-complete interface can therefore pass while reliance is misclassified.

#### A-18 — multi-hop human or model relay

Planning system P receives an allowed aggregate and emits an unlinked narrative recommendation.
Case system C never imports the original artifact or a derivative carrying its digest. C uses the
narrative for an individual action. F-14 catches a derivative that declares its source digest and
drops restrictions; it does not catch lineage disappearance before the governed consumer.

## 10. Pass-III through Pass-VII findings

### `PAO-R4-III-001` — blocking — the formal claim class conflates empirical summaries and normative rules

**Evidence:** `pao-r4-individual-decision-firewall.md:82-130,178-210@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

The non-entailment is not valid over every admitted `P`, and the refusal list treats a competent
general rule as though it were a statistical generalization. Consolidation cannot adopt the formal
boundary until those object classes are separated.

### `PAO-R4-III-002` — blocking — violation decidability is relocated into trusted declarations and an unobservable counterfactual

**Evidence:** `pao-r4-individual-decision-firewall.md:90-150,278-320@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

`B`, `L`, auxiliary-information completeness, and “would the action change” are load-bearing inputs
without a verifier/procedure. The contract can classify a trusted record; it does not yet make the
semantic violation decidable.

### `PAO-R4-III-003` — material — two population-form artifacts are individually determinative

Singleton-rate and deterministic-partition artifacts satisfy the tuple definition and determine a
person in practice. The report's later checks might block them, but the formal result must include
pointwise recoverability/non-degeneracy conditions.

### `PAO-R4-III-004` — commendation — empirical population membership is correctly denied individual authority

For non-degenerate empirical aggregates and probabilities, the non-entailment captures reference-
class, ecological-inference, base-rate, fact, procedure, and authority gaps in one compact statement.
That core should survive revision.

### `PAO-R4-IV-001` — material — part of the “export-time” class is only model-relative

**Evidence:** `pao-r4-individual-decision-firewall.md:236-270@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`.

Resolution, uniqueness, semantic executability, material omission and composition require auxiliary
models or histories. The categories must distinguish artifact-local from export-context observables.

### `PAO-R4-IV-002` — material — the firewall claim is not consistently bounded to the governed integration boundary

The detailed interface is boundary-scoped; the headline and standing often read institution-wide.
S-1 proves complete in-boundary evidence cannot establish no off-boundary cognitive use.

### `PAO-R4-IV-003` — material — the voluntary-channel consequence is overstated

Voluntary reporting cannot establish complete absence of prohibited use. It can still establish
reported incidents, lower bounds, or sampled evidence. Preserve the impossibility claim and narrow
the degradation statement.

### `PAO-R4-IV-004` — commendation — the three-class detection partition is the package's strongest organizing result

The distinction makes silent misuse auditable and exposes classes that must be refused rather than
paper-restricted.

### `PAO-R4-IV-005` — commendation — observational equivalence defeats a complete firewall claim under voluntary reporting

F-06 states the argument exactly and refuses to interpret silence as compliance.

### `PAO-R4-V-001` — material — refusal of every executable general rule is not derived

**Evidence:** `pao-r4-individual-decision-firewall.md:178-210@a27c3da9942b03881dbee1005a8a1e44e5ac44b4`; F-03.

The research must distinguish normative rule authority from empirical statistical inference. It may
still refuse PolicyOS-produced pointwise predictors and rules lacking competent external authority.

### `PAO-R4-V-002` — commendation — refusal is correctly limited to governed crossing, not candidate computation

F-12 and the authority-band language preserve useful population analysis. The narrow refusal frontier
is stronger than a broad paper prohibition.

### `PAO-R4-VI-001` — material — a fully compliant declared interface can miss prohibited human reliance

Scenario S-1 establishes the gap. A positive result must be explicitly scoped to technically governed
uses and must not imply institutional non-use.

### `PAO-R4-VI-002` — material — material contribution is not independently verifiable from the specified evidence

Scenario S-2 establishes that complete content-bound records can preserve an incorrect reliance
claim. The contract needs an observable conservative proxy or a method for validating the
counterfactual.

### `PAO-R4-VI-003` — commendation — the returning interface is semantic, evidence-bearing, and fail-closed on absence

It avoids designing a case-system schema, requires denominators and independent reconciliation, and
returns `FIREWALL_CLAIM_NOT_ESTABLISHED` rather than a false negative.

### `PAO-R4-VII-001` — blocking — F-01 does not test the commission's silent-purpose-drift falsifier

The core acceptance probe can pass at request time while downstream use remains invisible. It must be
rewritten as two stages with an initially permitted purpose and an exact mandatory consumer-side red
verdict.

### `PAO-R4-VII-002` — material — several “exact” fixtures are conditional and four untested attack families remain

Split F-01/F-02/F-05/F-07 worlds and add A-15 through A-18 or equivalent property tests.

### `PAO-R4-VII-003` — commendation — all four additional commissioned attacks are present and substantive

The aggregate join, parameterized rule, denied-use projection, and query-sequence reconstruction
cases are real rather than marker-only examples.

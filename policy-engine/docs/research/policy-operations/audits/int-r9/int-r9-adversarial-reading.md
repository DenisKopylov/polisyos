---
title: INT-R9 — Adversarial Reading of the First-Promotion Protocol
status: delivered
kind: independent-audit
research_task: INT-R9
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r9-first-promotion-protocol
audited_commit: f5ad922377e38ee3ddbecb33293300bca25a9ad7
current_repository_commit: d152565dcc11cea457dacd61fadc6e15dc3ecc86
inspection_date: 2026-08-03
authoritative_for:
  - adversarial evaluation of INT-R9 multiplicity, ua-msme disposition, case authorship, repair, materiality, and human-independence mechanisms
  - evidence showing whether motivated actors can comply with every written rule and still obtain the forbidden outcome
  - edge-case disposition review for the proposed protocol state machine
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - alternative protocol specification
  - permission to execute a first-promotion attempt
research_only: true
---

# INT-R9 — Adversarial Reading

## 1. Adversarial standard

The protocol is read literally from the position of an actor who intends to comply with every
written sentence. Covert deletion, forged signatures, bribery, or secret answer theft are not
needed to establish a defect. The relevant question is whether the permitted choices themselves
can produce the outcome the protocol claims to exclude.

This reading applies the P29 stopping rule correctly. It does not invent a future field that might
one day evade a generic mechanism. It traces current canonical source:

- N9's actual scope constructor;
- the confidence ledger's actual scope identity, event loading, ordinal assignment, and spend
  check;
- INT-R9's actual three-slot stopping and between-slot repair rules; and
- the actual unresolved materiality and staffing decisions.

## 2. Pass D — Three-slot multiplicity

### 2.1 Written protocol

INT-R9 fixes exactly three selected case pairs and defines “first” as the earliest slot reaching a
valid positive terminal. It says:

- the order is committed before any input reveal;
- a valid positive stops the sequence;
- refusal or void permits the next slot;
- no slot may be inserted, reordered, replaced, or omitted;
- attempted or void slots keep their chronological ordinal and predictable allocation; and
- no reset, refund, or parallel alpha budget is created.

Those are good anti-substitution rules. They do not establish the stated accounting.

### 2.2 Canonical source path

For each attempt, `confidence_risk_scope_for_problem` constructs the only admissible N11 scope for
one N9 problem binding and sets:

```text
owner_scope_key = design-problem:<design_problem_id>
```

`ConfidenceRiskBudgetScope.scope_id` includes that key. `ConfidenceLedgerSession.start_check`
loads current events for that scope, computes the next ordinal from those events, sums prior spend
from those events, and compares the result with the registry's top-level `delta`. The
Basel-square formula uses that scope-local query index.

No inspected source creates a parent first-promotion family containing three problem scopes.

### 2.3 Compliant multiplicity adversary

The actor does the following without violating an INT-R9 sentence:

1. Precommits six pairs, public randomness, three selected slots, all criteria, the panel, the
   source cutoffs, publication, and stopping.
2. Reveals slot 1 only after freeze.
3. Creates the canonical N9 binding for slot 1 with `design_problem_id = case-A`.
4. N9 derives scope `design-problem:case-A`; the ledger assigns ordinal zero and allocates from
   `delta`.
5. Slot 1 refuses. The actor publishes the refusal and does not refund anything inside scope A.
6. The protocol permits moving to slot 2.
7. Slot 2 is a different case and gets `design_problem_id = case-B`.
8. N9 derives a different scope. Its event history is empty, so ordinal zero and a fresh top-level
   `delta` are available.
9. Repeat for slot 3 if needed, then stop on the first positive.

The actor did not reset a ledger. It opened the exact canonical ledger scope N9 requires for each
new problem. The reset occurs as a consequence of the permitted case-to-scope mapping, not as an
explicit forbidden action.

### 2.4 Arithmetic consequence

Let `E_i` be the event that slot `i` falsely promotes under its own maintained assumptions. Even if
each canonical scope proves:

```text
P(E_i | A_i) <= delta
```

that does not prove:

```text
P(E_1 union E_2 union E_3 | A) <= delta.
```

Without a valid composition theorem or preallocated family budget, the generic union bound is:

```text
P(E_1 union E_2 union E_3 | A) <= 3 * delta.
```

The selected historical event is exactly the union event because the protocol stops on the first
positive. Dependence between attempts does not automatically improve the bound, and no favorable
dependence assumption is stated or proved.

### 2.5 Why “chronological ordinal” does not close it

The protocol's ordinal is a governance slot number. The confidence ledger's execution ordinal is
computed from current events inside one scope. The document never proves those are one canonical
sequence. A public record saying “slot 2” cannot make N9 scope B's first check become ledger ordinal
one if the source calculates zero.

### 2.6 Void/refusal does not consume the next case's allocation

The YAML says a void or refused slot keeps its allocation and receives no refund. That is true only
inside the old scope. A later case creates a new scope with no old spend. Nothing in the current
protocol requires a verifier to reject that state, and nothing in current N9 accepts an INT-R9
family scope in place of the per-problem scope.

### 2.7 Finding

`INT-R9-D-001` — **blocking**. The protocol admits three canonical `delta` budgets while
representing them as one. This is the decisive NO-GO.

## 3. Pass D — Adaptive repair between slots

### 3.1 Written permission

After a public refusal or void, INT-R9 permits “general implementation repair” before the next
input reveal. The next slot receives a new content-bound implementation freeze. Case commitments,
criteria, order, and stopping remain fixed.

This is transparent adaptive development, not hidden run selection. Transparency is valuable, but
it does not make the adaptivity disappear.

### 3.2 Compliant repair adversary

A positive-seeking actor proceeds as follows:

1. Slot 1 exposes that the system loses an otherwise admissible case because its source-scope
   resolver handles one institutional relation too narrowly.
2. The actor publishes the refusal.
3. The actor replaces the narrow branch with a generalized resolver applying to the whole source
   family, writes no literal case ID, and documents the repair as general.
4. The no-case-specific-code scan passes because the code is semantically general and future slot
   2 remains sealed.
5. Slot 2 runs on the repaired revision and succeeds.

This may be legitimate engineering. It also means the later positive is selected from an adaptive
sequence of implementation revisions informed by earlier evaluation outcomes. The protocol must
therefore never imply that one fixed implementation survived three prospectively independent
looks.

### 3.3 Unclosed classification right

The audited artifacts provide no prospective taxonomy or accountable decision rule separating:

- a repair of a genuinely generic defect discovered anywhere;
- a generalized implementation of the exact behavior needed by the failed case;
- a domain-family patch broad enough to avoid a literal case branch; and
- a change that improves future hidden cases only by chance.

“Case-specific repair” is an automatic violation; “general repair” is allowed. That binary carries
outcome-changing force, but the protocol does not specify who classifies it, when, with what
conflict rule, or what evidence makes the classification reproducible.

### 3.4 Disposition

`INT-R9-D-002` — **material**. The protocol can remain a prospective adaptive development program
only if its public claim says so and the repair classification is closed before a favorable later
result. The blocking multiplicity problem remains even if every repair is legitimate.

## 4. Pass D — Material dispute

### 4.1 Written gate

Promotion requires no dispute vote, no unresolved material dissent, and no refusal grounded in a
material criterion. A material dispute halts the sequence.

### 4.2 Compliant materiality adversary

An insider does not suppress dissent. Instead, after seeing that one dissent would block a
positive, the insider classifies the disagreement as non-material under a general-sounding
rationale. The vote, rationale, and dissent remain public. Two approvals then suffice.

The audited artifacts contain a `materiality_rule_ref` and generic accountable assessment shapes,
but section 10 leaves open which canonical owner decides source or obligation materiality and how
pre-seal disagreement is resolved. No current rule prevents direction-sensitive classification by
a friendly assessor.

### 4.3 Disposition

`INT-R9-D-003` — **material**. The protocol has a material-dispute stop rule but not a closed
materiality decision right. This is a real post-result degree of freedom.

## 5. Pass E — The ua-msme horn

### 5.1 Facts verified

The harder horn is supported by four independent repository facts:

1. the full composed loop has run only for ua-msme;
2. S14 development evidence names ua-msme repeatedly;
3. the adjudication answer is committed and visible; and
4. current N9 input carries a ua-msme G4 reference by default.

The case was not selected after the final first-promotion run, but the system has been shaped around
it for a much longer period. Using it as decisive evidence would satisfy prospectivity in form and
violate it in substance.

### 5.2 Audit verdict on exclusion

`INT-R9-E-001` — **commendation**. Exclude ua-msme from decisive primary and adjacent roles. Keep
it as mandatory public regression and calibration material. The cost—possible refusal,
non-convergence, or no promotion—is correctly accepted.

### 5.3 Can ua-msme re-enter indirectly?

- **Public regression:** yes, openly and safely, because its result is not decisive.
- **Panel calibration:** yes, openly and safely, because its answer is public.
- **Positive control:** no route found that would count it as a real positive.
- **Adjacent case:** expressly forbidden by current eligibility language.
- **Replacement after a failure:** expressly forbidden by fixed queue/no-substitution.

No decisive re-entry path was found.

### 5.4 Reopening bar

The report says only a custody and causal-isolation proof could reopen ua-msme. That is coherent as
a falsifier but is close to unattainable for the existing lineage: no new secret label can erase
prior integrated development. The pinned repository supplies affirmative contamination evidence.
The practical standing should therefore be permanent public-regression status unless genuinely
extraordinary evidence defeats the known history.

`INT-R9-E-003` — **minor**. Preserve the falsifier, but do not make reopening sound like a normal
future option.

## 6. Pass E — New case and answer-key authorship

### 6.1 Written construction

One independent case unit creates six primary-adjacent pairs and separate input and
expectation/evaluator packages. The unit cannot contribute to implementation, criteria,
thresholds, or outcome-contingent reward. A separate eligibility reviewer checks metadata. Public
randomness chooses one pair per stratum and orders the three slots.

### 6.2 What this closes

The mechanism closes several real degrees of freedom:

- implementers cannot choose the easiest sealed case after seeing outputs;
- one visibly promising pair cannot be substituted after failure;
- ordering cannot be changed by a person who recognizes tractability; and
- answer keys remain unavailable before the relevant freeze.

### 6.3 What it does not close

The same case unit may author both the six case inputs and all six answer packages. It can comply
with every role restriction while choosing mechanisms, jurisdictions, source forms, and ambiguity
patterns it expects the existing system to handle. Randomness then chooses among six favorable
constructions. This is pool-level authorial selection, not post-selection leakage.

The report partly acknowledges this by saying that a purposive pool proves only no substitution
within the declared pool, not absence of upstream topic-selection judgment. That caveat is the
right boundary. Any later statement that the new cases are simply “uncontaminated” would be too
strong.

`INT-R9-E-002` — **material**. Case secrecy and pool independence must not be conflated. The narrow
claim survives only with explicit residual authorial-selection disclosure.

## 7. Pass F — Independent adjudication

### 7.1 Constructed requirements

The report materially improves on the current repository. It requires:

- identified accountable natural persons;
- signatures;
- three members and two predeclared alternates;
- method/evidence, domain/authority, and custody/public-claim coverage;
- independence from implementation and case-specific bindings;
- independence from case selection/authorship;
- independence from criteria/threshold authorship;
- no answer-key custody before reveal;
- no direct line management of evaluated implementers;
- no outcome-contingent compensation;
- no prior scored outcome access;
- publication of raw votes, abstentions, disagreements, and guide changes; and
- a categorical rule that a synthetic reviewer, model, agent, or role ID cannot qualify.

### 7.2 Satisfiability today

No repository evidence names three qualifying humans or two alternates. Current IDs such as
`reviewer-method-evidence-w11c` are role placeholders. The report accurately treats this as an
automatic block before sealing. It does not quietly permit a model to substitute.

`INT-R9-F-001` — **commendation**.

### 7.3 Positive-seeking insider who follows every rule

The insider appoints three friendly but formally eligible people:

- none wrote implementation code;
- none authored selected cases or thresholds;
- none directly manages the implementers;
- none receives outcome-contingent compensation;
- all disclose affiliations and sign;
- all calibrate on the public corpus; and
- all avoid answer access before reveal.

They may share the same broader funder, governance network, institutional objective, or
reputational stake in a positive milestone. Those facts are disclosed but not always disqualifying,
and the protocol does not require independent corroboration of every disclosure. Two friendly
approvals and a direction-sensitive non-materiality classification can therefore pass.

This does not prove collusion. It proves that seven named dimensions remain partly a
self-declaration framework rather than a complete evidence construction.

`INT-R9-F-002` — **material**.

### 7.4 Reviewer unavailability

If a member becomes unavailable mid-adjudication, only a predeclared alternate without prohibited
access may substitute. Otherwise the attempt becomes disputed. No favorable reviewer may be
chosen after votes are known. This edge case is adequately governed.

### 7.5 Calibration-round correction

The report says the panel calibrates on all fifteen public manifests. That is appropriate as guide
calibration, not independence proof. The repository's current calibration field is not uniformly
null: four manifests carry the deep-pilot round. Existing calibration metadata therefore does not
close the named-human requirement and does not materially change readiness.

## 8. Opposite adversary — blame avoidance and strategic refusal

### 8.1 Compliant strategy

A blame-avoiding insider can:

1. keep the deterministic contract-level positive control green;
2. pass known public groundable seeds;
3. produce precise owner-backed refusal reasons for every unseen real case;
4. emit acquisition or repair records where available;
5. avoid generic “safety” language;
6. publish every refusal; and
7. finish with `exhausted_without_promotion`.

Every written anti-abstention rule is satisfied. The insider has not used a constant refusal path
and has not hidden a result. Yet no unseen case is ever promoted, and personal downside remains
minimized.

### 8.2 What the protocol can and cannot reveal

The protocol can reveal:

- mechanical inability to transition positive;
- unsupported boilerplate refusal;
- failure on known-groundable public seeds;
- stale retrieval or inadequate recall; and
- refusal reasons that do not resolve to owner evidence.

It cannot establish that a defensible owner-backed refusal was strategically motivated or make
risk-taking career-safe. Result-independent publication helps but does not reverse the incentive.

`INT-R9-G-002` — **material**. Tradeoff T6 remains an open organizational/economic problem. The
protocol should claim inspection of refusal quality, not prevention of abstention dominance.

## 9. Hand-coded binding from a departed contributor

This required falsifier is handled well. The no-case-specific-code property requires binding
provenance, first commit, purpose, source inputs, known exposure, and edits; departed authorship
does not cleanse a binding. A direct branch, fingerprint branch, case-only adapter, hidden fixture,
or old hand-coded binding is an automatic NO-GO.

If provenance is missing, the protocol cannot positively establish no bespoke mechanism. It must
block rather than infer cleanliness from contributor absence. No contrary exception was found.

This mechanism is stronger than a literal grep and correctly treats the probe as a witness of a
semantic property rather than the specification.

## 10. Required edge cases

| Edge case | INT-R9 disposition | Audit verdict |
| --- | --- | --- |
| Pre-registered case fails; unregistered case succeeds | unregistered case cannot replace a slot or count; failed slot remains public | adequate |
| Adjudicator unavailable mid-review | only clean predeclared alternate; otherwise disputed | adequate |
| Criterion becomes ambiguous after sealing | old run cannot be rescored under a changed criterion; material ambiguity blocks/disputes and a new version cannot erase old chronology | direction adequate; materiality owner still open |
| Sealed holdout leaks | slot void or disputed; remains in chronology/denominator | adequate, dependent on S0-GAP-02 incident evidence |
| Promotion later found unjustified | append-only correction/suspension/withdrawal/supersession; historical record retained | direction adequate; canonical currentness owner remains a consolidation question |
| Two candidates qualify simultaneously | decisive slots are sequential; parallel execution would violate order. Multiple candidates inside one slot remain governed by canonical N9/run selection, not fully elaborated here | no slot-level cherry-pick path found; candidate-level run-selection must stay owner-bound |
| Preregistration mis-specified before any result is seen | `retired_before_inspection`; may be superseded prospectively without consuming a scored slot | adequate if transaction evidence proves no result-bearing access |
| Preregistration amended after a failed slot | old slot remains scored; new protocol version needs fresh queue and cannot rewrite history | adequate in principle; risk-family relation across versions remains open |
| Source-flip target turns out non-material after reveal | materiality dispute can become direction-sensitive | material gap D-003 |
| Procedurally void slot then next case | protocol says no refund, but canonical next problem scope resets | blocking D-001 |
| General repair after refusal | allowed; later revision selected adaptively | material D-002 |

## 11. Findings summary

| Finding | Severity | Why it matters |
| --- | --- | --- |
| `INT-R9-D-001` | blocking | Three canonical case scopes can each spend fresh delta; the first-positive union is not controlled as claimed. |
| `INT-R9-D-002` | material | Outcome-informed repair can be labeled general without a preclosed classifier. |
| `INT-R9-D-003` | material | Materiality is an outcome-changing unresolved decision right. |
| `INT-R9-E-001` | commendation | ua-msme is correctly excluded despite its tractability. |
| `INT-R9-E-002` | material | Pool-level author bias survives answer secrecy and random selection. |
| `INT-R9-E-003` | minor | ua-msme reopening should be treated as extraordinary, not routine. |
| `INT-R9-F-001` | commendation | Role strings and synthetic reviewers cannot satisfy independence. |
| `INT-R9-F-002` | material | Friendly formally eligible humans can satisfy disclosure-based dimensions. |
| `INT-R9-G-002` | material | Strategic evidence-backed refusal remains compliant and safe. |

## 12. Adversarial conclusion

The protocol succeeds against the obvious cheater who swaps cases, hides failures, changes a
threshold, inserts a literal case branch, chooses a favorable reviewer after votes, or calls a
public answer a holdout.

It fails against a more important actor who follows the rules:

- uses three canonical problem scopes and three fresh budgets;
- learns from a failed slot through a generalized repair;
- operates inside a purposively favorable but properly sealed pool;
- appoints friendly, formally eligible, fully disclosing humans;
- classifies adverse dissent as non-material under an unresolved decision right; and
- stops at the first positive.

That path is enough for `NO_GO` even if no actor ever intends to exploit it. The protocol's purpose
is to make the path unavailable, not merely visible.

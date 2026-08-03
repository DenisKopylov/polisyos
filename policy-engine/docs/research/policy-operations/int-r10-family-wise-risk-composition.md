---
title: INT-R10 — Family-wise Risk Composition over Canonical Confidence Scopes
status: delivered
kind: deep-research
research_task: INT-R10
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-family-wise-risk-composition
repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
authoritative_for:
  - independent research conclusion for composing false-promotion risk over distinct canonical N9 design-problem confidence scopes
  - weighted-union theorem under exact prospective local caps and stated maintained assumptions
  - impossibility result for retaining one delta across several ordinary full-delta scopes without additional canonical composition structure
  - adaptive-continuation theorem boundary and required history-conditional, uniform, or otherwise selection-valid local guarantee
  - research-level handoff constraints for extending the canonical confidence ledger without weakening per-problem scope identity or creating a second ledger
  - bounded claim language that INT-R9 may use before and after a canonical owner extension
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical schema name or package placement
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - assertion that cross-scope composition is implemented at the pinned baseline
  - assertion that INT-R9's outcome-dependent repair policy has a family-wise numeric theorem
  - unconditional claim about false promotion outside the declared obligation sets and maintained assumptions
  - population performance, external validity, legal compliance, institutional competence, or production readiness
research_only: true
---

# INT-R10 — Family-wise Risk Composition over Canonical Confidence Scopes

## Executive Finding

**Result: `accepted_narrow_scope`. Current repository capability: `blocked`.**

A valid family-wise composition is available without weakening the canonical per-problem scope,
without a common null, without exchangeability, and without independence. It is the exact weighted
union composition:

> For an exact prospectively governed family `F`, let `V_i` be the event that reached member `i`
> falsely produces a canonical promotion. If the canonical confidence owner enforces a local
> top-level cap `alpha_i` before member `i` can execute, every local false-promotion theorem is valid
> for that cap under the named maintained assumptions, and `sum_i alpha_i <= delta_F`, then
> `P(any member of F falsely promotes | maintained assumptions) <= delta_F`.

The proof is the union inequality. It applies to heterogeneous design problems because the
controlled object is a union of authority-error events, not a shared estimand or a shared null.
The bound is sharp from the declared information alone: three disjoint false-promotion events of
probability `delta` satisfy all three local bounds and have family probability `3 * delta`.
Therefore no generic improvement below the sum may be claimed without additional verified
structure.

The pinned repository does **not** implement the premises of that theorem. N9 derives a distinct
canonical scope for each `design_problem_id`; each scope has its own immutable root, local event
history, ordinal series, and registry-level `delta`; `start_check()` sums prior spend only from the
current scope; and no cross-scope cap, family binding, or family recomputation path exists
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`, `:518-557`,
`:1301-1364`; `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).
The audit's fully compliant trace therefore remains possible:

```text
slot 1 -> design-problem A -> scope A -> ordinal 0 -> fresh top-level delta
slot 2 -> design-problem B -> scope B -> ordinal 0 -> fresh top-level delta
slot 3 -> design-problem C -> scope C -> ordinal 0 -> fresh top-level delta
stop on first positive
```

For three ordinary scopes, the strongest generic composition of three valid local `delta`
guarantees is

```text
P(false first promotion in the exact family | joint maintained assumptions)
  <= min(1, 3 * delta).
```

With the live registry's `delta = 1/100`, that is `3/100`, not `1/100`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`). This is a theorem
about what follows from valid local guarantees; it is not a claim that the current proving ground
has produced a positive governed sequence or a live family certificate.

A compatible future design is available. Preserve the three canonical scope IDs. Before any
family result-bearing execution, bind an exact cap vector—for example `delta_F/3` per member—and a
complete **member-specific implementation/revision plan**. Different members may have different
precommitted revisions, configurations, models, prompts, or evidence cutoffs; the theorem does not
require one identical implementation. What it forbids in the non-adaptive case is selecting or
changing those member plans after family outcomes become known. The existing Basel-square schedule
may then allocate **inside** each local cap, and the **same confidence ledger** may recompute a
family composition projection from the live declaration, live N9 scope derivation, canonical
roots, current-head receipts, and attempt chronology. This is an extension of the canonical owner,
not a parent risk scope or second ledger.

Adaptive continuation is a separate theorem boundary. INT-R9 permits “general implementation
repair” after an earlier refusal or void. A later implementation selected using earlier outcomes
is not covered merely because the next local scope is anytime-valid. A family bound survives that
policy only if each reached member's false-promotion guarantee remains valid conditional on the
full prior history—or under an equivalent uniform or selection-aware theorem—and the allocation is
predictable with a pathwise total at most `delta_F`. The current ledger supplies no such cross-scope
owner theorem. INT-R9 must therefore either precommit the complete member plan, obtain a canonical
adaptive-validity theorem, or withdraw the numeric family claim. Arithmetic alone cannot validate
repair.

E-values do not remove this obligation. Products or martingale mergers require conditional
e-validity or a justified dependence structure and must target the relevant null. The current
registry's executable e-process is the closed constant-one process, which cannot satisfy a
promotion obligation; owner-verified e-value/e-process/sequential instruments are registered under
`owner_theorem_unavailable_v1`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). No empirical
calibration can fill the gap: PolicyOS has no positive governed promotion history from which to
learn a family error rate.

Supporting artifacts:

- [Primary-source and transfer ledger](int-r10/source-and-transfer-ledger.md)
- [Artifact, recomputation, and executable fixture sketch](int-r10/fixture-and-artifact-sketch.md)

---

## 1. Task And Project Fit

### 1.1 Exact question and acceptance target

The research question is:

> When PolicyOS evaluates several design problems in an exact family and reports the first valid
> positive, what composition is available over the canonical per-problem confidence scopes, and
> what may then honestly be claimed?

INT-R9 needed one cumulative risk statement for three precommitted slots. Its audit found that the
canonical source instead creates three risk scopes and gave eight acceptance requirements plus a
mandatory three-fresh-budget falsifier
(`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105`).
INT-R10 answers the missing owner-level arithmetic. It does not redesign INT-R9's case selection,
sealing, adjudication, publication, or public-record machinery.

A valid result must distinguish three questions:

1. **Local validity:** what does each canonical problem scope prove about its own false-promotion
   event?
2. **Family accounting:** how are the local guarantees composed over the exact family event?
3. **Selection validity:** do the local guarantees remain valid when earlier outcomes influence
   later implementation, data, or evaluation choices?

The current repository is strong on local accounting but has no canonical answer to questions 2
or 3.

### 1.2 Exact family event

For an ordered family `F = (1, ..., m)`, define:

- `R_i`: slot `i` is reached under the declared stopping, dispute, and no-substitution rules;
- `P_i`: slot `i` emits a canonical positive promotion terminal;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`: reached slot `i` falsely promotes; and
- `V_F = union_i V_i`: at least one reached member falsely promotes.

Under stop on the first canonical positive, `V_F` is exactly the event that the family's reported
first promotion is false. Earlier refused, void, disputed, or negative members remain in the
family chronology even when they do not themselves promote. Members after a valid positive are
unreached rather than silently deleted.

The controlled quantity is **false authority promotion**. It is not the probability that a useful
design exists, the probability that every external obligation is known, a common-null rejection,
an unbiased effect estimate for the selected design, population performance, or benchmark success.

### 1.3 Why the arithmetic belongs to the confidence ledger

The repository requires owner-first reuse and rejects parallel owner paths and author-written proof
(`AGENTS.md:35-66`, `:71-89`). The confidence ledger already owns risk scopes, exact rational
allocation, proof-profile refusal, risk burning before owner execution, immutable events, canonical
receipts, conditionality, and N9 projections. INT-R9 consumes those outputs; it does not own their
probability arithmetic.

The owner split is therefore:

- **Confidence ledger / N11 lane:** local-cap enforcement, aggregate composition, theorem/refusal
  profile, and live family projection.
- **N9:** canonical design-problem binding and per-problem scope derivation.
- **INT-R9:** family membership/order, case custody, stopping, publication, disputes, and repair
  governance.
- **INT-R1:** each member's declared obligation basis and visible open-world remainder.
- **Existing public projection owner:** display of the bounded claim, never creation of the bound.

### 1.4 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Arithmetic and custody of PolicyOS's family-wise false-promotion statement over its own promotion receipts | **OWN** | Bind family, caps, scope identities, maintained assumptions, member-plan versions, terminal history, currentness, and correction; recompute the statement from canonical artifacts. | Ownership is of PolicyOS's signed risk statement, not of external legal or empirical truth. |
| N9 problem bindings, INT-R1 declarations, owner certificates, evaluators, adjudicators, external sources, and implementation freezes | **INTEGRATE** | Verify, purpose-admit, content-bind, and react fail-closed when these inputs change. | PolicyOS does not become the external source, court, regulator, evaluator, or institutional authority. |
| Unadmitted dependence claims, proposed weights, criticism, suspected coupling, or candidate family definitions | **OBSERVE** | Retain as research/challenge signals; never use them to mint a tighter bound. | Observation or projection cannot establish a theorem premise. |
| Creating legal effect, operating the policy, certifying population efficacy, or deciding institutional competence | **OUT_OF_SCOPE** | Publish only the bounded PolicyOS claim and route external acts to competent owners. | Risk composition does not make PolicyOS an administrator or sovereign authority. |

This follows S0-K05 and S0-K16 and the authority-band/candidate-band lens. Missing composition must
block the numeric cross-problem authority claim, not candidate exploration under a declared
limitation
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`,
`:160-190`).

### 1.5 Result standing

Two standings must remain distinct:

- **Research theorem:** `accepted_narrow_scope`.
- **Current runtime capability:** `blocked` / `cross_scope_composition_missing`.

The result neither appoints a new owner nor authorizes code. A future implementation must be a
separate governed task and must pass the behavioral falsifiers in §6.

---

## 2. Current Repo Baseline

### 2.1 Pinned inspection

- Repository: `https://github.com/DenisKopylov/polisyos`
- Branch inspected: `main`
- Exact baseline: `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`
- Research branch: `research/int-r10-family-wise-risk-composition`
- Inspection date: `2026-08-03`
- Changes made: three new research Markdown files only; no source, test, or existing document was
  modified.

The supplied orientation was materially correct. One precision matters: an ordinal-zero check does
not literally consume the whole `delta`; it receives a scheduled fraction. The defect is that each
fresh scope receives a fresh **top-level delta budget and guarantee series**, not that its first
check spends all of `delta`.

### 2.2 Line-anchored scope, ordinal, allocation, and refusal census

| Repository anchor | Verified fact | Family consequence |
| --- | --- | --- |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52` | The ledger allocates before owner execution, refuses statistical families without a repository-owned theorem verifier, carries exact maintained assumptions, and states that good-event composition uses the union bound without an independence claim. | Conservative event composition is already the owner's style, but only for objects represented in its live path. |
| `.../confidence_ledger.py:156-184` | `ConfidenceRiskBudgetScope` is the stable owner scope for one non-resettable budget; `scope_id` derives from owner, authority purpose, owner-scope key, and epoch. | Per-problem scope identity is deliberate and must not be weakened or replaced by a family ID. |
| `.../promotion_sequence.py:356-375` | `confidence_risk_scope_for_problem()` is the only admissible N11 scope for one N9 binding and sets `owner_scope_key = design-problem:<design_problem_id>`. | Distinct fresh design problems correctly produce distinct canonical scope IDs. |
| `.../confidence_ledger.py:250-390` | Registry policy has one top-level `delta`; schedules have bounded mass; obligation pools must totally partition the declared denominator and sum exactly to one. | Internal allocation is exact relative to one scope/registry, but there is no denominator over design-problem scopes. |
| `.../confidence_ledger.py:518-557` | An immutable root binds one risk scope to registry, schedule, obligation split, `budget_delta`, conditionality, and maintained assumptions. | Each problem scope receives its own root-level budget binding. |
| `.../confidence_ledger.py:723-752` | A canonical receipt recomputes one scope's current head, events, checks, total spend, budget status, good-event clause, and maintained assumptions. | Existing receipts are suitable member evidence for a future family projection, but remain scope-local. |
| `.../confidence_ledger.py:1180-1280` | `prepare_check()` binds claim/instrument facts before outcome; preflight refusals are persisted with zero spend. | Refusal is typed and durable locally; no family terminal/cap disposition is defined. |
| `.../confidence_ledger.py:1301-1364` | `start_check()` reads one scope, assigns the next ordinal from that scope's checks, computes spend from registry `delta`, sums prior spend only inside that scope, rejects only local overspend, and burns risk before owner execution. | Three new scopes each start at local ordinal zero and do not see one another's budget or spend. |
| `.../confidence_ledger.py:3740-3855` | `_instrument_preflight_refusal()` rejects disallowed roles, ineligible profiles, unavailable owner theorems, and non-anytime-valid profiles; receipt validation requires zero-spend refusal semantics. | The current owner is capable of honest refusal and should similarly refuse an unavailable family theorem. |
| `.../confidence_ledger.py:3890-4025` | Receipt validation recomputes contiguous local ordinals and every schedule spend, rejects forged rows/decimal drift, and implements the exact Basel-square allocation. | The within-scope schedule is reproducible; it is not a cross-scope family schedule. |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:1-18` | Live `delta` is exactly `1/100`; registered schedules have mass `1` and `1/2`. | No family cap vector or one-third top-level allocation is registered. |
| `.../confidence_ledger.toml:53-121` | The registry is dominated by deterministic, ineligible, and unavailable-theorem profiles; the only executable e-process is constant one and cannot satisfy a promotion obligation. | No executable e-value/e-process family theorem can be inferred from registry labels. |
| `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` | GY-GAP2 records that per-problem scopes are correct and that no `cross_scope`, `family_wise`, or `parent_scope` composition exists. | The gap is missing composition, not wrong scope identity. |
| `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650` | INT-R9 fixes three slots and stopping but permits “general implementation repair” after refusal/void while asserting cumulative risk. | Its sequence is adaptive unless the complete member-plan vector is precommitted; a fixed-plan theorem cannot be silently extended to repair. |
| `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105` | Audit R1 requires exact family event, canonical-scope relation, no fresh budgets, terminal effects, aggregate proof, adaptive validity or narrowed claim, owner reuse, and live reproduction. | These eight requirements are answered in §4.11 and §6. |
| `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90` | INT-R1 permits only relative obligation coverage and keeps the risk statement conditional on declared basis and validator soundness. | Family composition cannot discharge open-world or validator premises. |

### 2.3 Mandatory falsifier at the pinned baseline

For distinct N9 problem IDs `A`, `B`, and `C`:

1. N9 derives pairwise distinct `scope_A`, `scope_B`, and `scope_C` because the problem ID is in the
   owner-scope key.
2. Each scope receives its own immutable root with registry `budget_delta = 1/100`.
3. Each empty scope can assign its first started check local ordinal zero.
4. Each spend calculation uses the same registry top-level delta and the local obligation/schedule
   factors.
5. Prior spend in `scope_B` excludes `scope_A`; prior spend in `scope_C` excludes both earlier
   scopes.
6. No live source object requires the sum of admitted top-level caps over A/B/C to be at most
   `1/100`.

The trace therefore passes local source rules. A prose assertion that the slots are “one cumulative
scope” is not closure evidence.

### 2.4 Current arithmetic and sharpness

Suppose each local canonical theorem supplies only

```text
P(V_A | A_F) <= delta
P(V_B | A_F) <= delta
P(V_C | A_F) <= delta.
```

Then

```text
P(V_A union V_B union V_C | A_F) <= 3 * delta.
```

This is not merely conservative wording. For `delta <= 1/3`, construct three disjoint events, each
with probability `delta`, and identify them with the three false-promotion events. Every local
bound holds and the family probability is exactly `3 * delta`. A tighter generic claim is false.

### 2.5 Honest empirical state

The repository has no empirical basis for a learned dependence correction or outcome-calibrated
weighting. The live proof registry is dominated by refusal/unavailable/deterministic paths
(`confidence_ledger.toml:53-121`). The proving ground remains unconverted: all 13 cases are typed
blockers, `useful_design_rate = 0`, and D3.8 is not built
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

INT-R10 therefore does not estimate correlation among false-promotion events, learn cap weights
from prior successes, fit a positive base rate, or justify a Šidák/product correction. Such numbers
would be authored assumptions over nonexistent governed outcome data.

### 2.6 Capability-chain verdict

| Capability | Standing at `978e6b958...` |
| --- | --- |
| Stable non-resettable scope per design problem | `implemented` |
| Exact rational within-scope schedule | `implemented` |
| Risk burn before owner execution | `implemented` |
| Typed preflight refusal and unavailable-theorem refusal | `implemented` |
| Immutable scope-local root/event/receipt | `implemented` |
| Conditionality on obligation completeness and validator soundness | `implemented` |
| Prospective cross-scope family declaration admitted by ledger | `missing` |
| Enforced local cap derived from family allocation | `missing` |
| Exact aggregate cap/spend verifier | `missing` |
| Live family projection over canonical scope heads | `missing` |
| Selection-valid theorem for outcome-dependent repair | `missing` |
| Mandatory three-budget behavioral falsifier | `missing` |
| INT-R9 single-`delta` family claim | `blocked` |

---

## 3. External Research Baseline

The detailed transfer analysis is in
[int-r10/source-and-transfer-ledger.md](int-r10/source-and-transfer-ledger.md). Only primary sources
are used for load-bearing transfers.

### 3.1 Multiple testing and online FWER

Holm's step-down procedure controls family-wise error for a finite family of valid p-values and can
improve on single-step Bonferroni without favorable dependence
([Holm 1979, DOI 10.2307/4615733](https://doi.org/10.2307/4615733)). Tian and Ramdas develop online
FWER control for an a priori unbounded sequence; simple Bonferroni-style allocations transfer
broadly, while more adaptive power gains require independence or local-dependence conditions
([Tian & Ramdas 2021, DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381),
[arXiv:1910.04900](https://arxiv.org/abs/1910.04900)).

The directly transferable principle is:

```text
allocate nonnegative local error caps predictably;
prove every local authority-error statement at its assigned cap;
keep the exact total within the declared family bound.
```

PolicyOS does not currently expose one family of valid p-values or a step-down owner, so Holm is a
possible future design family, not a theorem about current artifacts.

### 3.2 Group-sequential designs and alpha spending

Pocock and O'Brien–Fleming show that repeated looks and early stopping must be controlled as one
procedure rather than treated as fresh tests
([Pocock 1977, DOI 10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191);
[O'Brien & Fleming 1979, DOI 10.2307/2530245](https://doi.org/10.2307/2530245)). Lan and DeMets
formalize alpha-spending boundaries indexed by information time
([Lan & DeMets 1983, DOI 10.1093/biomet/70.3.659](https://doi.org/10.1093/biomet/70.3.659)).

What transfers is pre-allocation, cumulative accounting, and no fresh reset after an unfavorable
look. Their boundary formulas do not transfer: those papers analyze repeated observations of one
accumulating experiment under a specified joint model. Three PolicyOS design problems are not
three information times for one effect.

### 3.3 Šidák and model-dependent improvements

Šidák's rectangle inequality is tied to a multivariate-normal probability structure
([Šidák 1967, DOI 10.1080/01621459.1967.10482935](https://doi.org/10.1080/01621459.1967.10482935)).
Product-form corrections can improve on a union bound when their dependence/model assumptions are
true. PolicyOS has no verified common multivariate model, exchangeability premise, or cross-problem
dependence contract. A Šidák number would therefore be an unsupported theorem premise.

### 3.4 Anytime-valid inference and optional continuation

Confidence sequences and nonnegative supermartingales provide time-uniform validity under their
stated filtration/process assumptions
([Howard et al. 2021, DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991);
[Howard et al. 2020, DOI 10.1214/18-PS321](https://doi.org/10.1214/18-PS321)). Ramdas, Grünwald,
Vovk, and Shafer make the predictability boundary explicit: optional stopping or continuation can
be safe, but choosing a betting strategy after seeing its result is not
([Ramdas et al. 2023, DOI 10.1214/23-STS894](https://doi.org/10.1214/23-STS894),
[arXiv:2210.01948](https://arxiv.org/abs/2210.01948)).

This transfers directly to INT-R9. A local anytime-valid process does not automatically validate
the outcome-dependent choice of the next implementation. The actual filtration must include every
earlier reveal, result, repair decision, model/configuration change, adjudication, and source fact
used to select the later procedure.

### 3.5 E-values

E-values can be calibrated and combined; averaging merges e-values for one null under arbitrary
dependence
([Vovk & Wang 2021, DOI 10.1214/20-AOS2020](https://doi.org/10.1214/20-AOS2020)). Sequential
merging uses martingale constructions and conditional validity, while independent merging is a
separate structured case
([Vovk & Wang 2020, arXiv:2007.06382](https://arxiv.org/abs/2007.06382)). Multiple-testing gains
for independent or sequential e-values state those assumptions explicitly
([Vovk & Wang 2020, arXiv:2003.00593](https://arxiv.org/abs/2003.00593)).

“E-values multiply” is not a family theorem. The merger must have the correct null/target and every
factor must satisfy its conditional or dependence premise. A product often targets a joint or
global null; PolicyOS needs strong control of the event that **any** authority promotion is false
across heterogeneous truth configurations.

### 3.6 Selective inference

Inference after selection must account for the selection event
([Fithian, Sun & Taylor, arXiv:1410.2597](https://arxiv.org/abs/1410.2597)). A prospective family
bound can include stop-on-first-positive selection in its error event. It does not thereby supply
an unbiased effect estimate, representativeness, population generalization, or protection against
upstream case-pool selection.

### 3.7 Transfer verdict

| Method family | INT-R10 disposition |
| --- | --- |
| Exact weighted union / Bonferroni event accounting | **Transfers directly** once local guarantees and caps are canonical and real. |
| Holm step-down | **Potential future option** requiring valid family p-values and a canonical family procedure. |
| Šidák/product correction | **Does not transfer** without verified joint structure. |
| Pocock/O'Brien–Fleming/Lan–DeMets | **Accounting lesson only**; their repeated-look boundary theorem does not cross heterogeneous problems. |
| Confidence sequences/e-processes | **Transfers within a valid process**; adaptive families additionally need history-conditional, uniform, or selection-valid local guarantees. |
| E-value multiplication/merging | **Not automatic**; correct target and conditional/dependence premises are required. |
| Selective inference | **Constrains meaning**, not a current composition implementation. |
| Empirical calibration | **Unavailable** at the current project state. |

---

## 4. Result

### 4.1 Explicit epistemic classification

| Category | Result |
| --- | --- |
| **Theorem** | Weighted-union composition over heterogeneous canonical scopes; adaptive extension under predictable/pathwise-bounded allocations and history-conditional, uniform, or equivalent selection-valid local guarantees. |
| **Empirical rule** | None is required for the theorem. Learned weights or dependence corrections would require governed data the project does not have. |
| **Design pattern** | Preserve every canonical per-problem scope; prospectively bind local caps and the complete member-specific plan; run the existing local schedule inside each cap; recompute one ledger-owned family projection. |
| **Governance protocol** | Exact family/order commitment, no substitution, durable earlier terminals, no outcome-dependent refund by default, result-independent disclosure, and explicit fixed-plan versus adaptive standing. |
| **Impossibility result** | Three ordinary full-`delta` scopes do not imply one `delta`; `3 * delta` is sharp without extra structure. A fixed-plan theorem cannot silently cover outcome-dependent repair. |
| **Engineering convenience** | Three slots, equal `delta_F/3` caps, conservative no-refund, and placeholder artifact names. Other choices are permitted if the invariants and proof remain. |

### 4.2 Theorem A — prospectively fixed family composition

Let `F = {1, ..., m}` be an exact family. Before any family result-bearing execution, prospectively
bind:

- member identity and order;
- each exact N9 problem binding and canonical scope derivation;
- local nonnegative exact rational cap `alpha_i`;
- each member's implementation/revision/configuration/model/prompt/evidence-cutoff plan;
- stopping, dispute, retry, and no-substitution rules; and
- the joint maintained-assumption set `A_F`.

Different members may have different precommitted plans. “Fixed” means the complete vector is fixed
before family outcomes, not that all members run identical bytes.

Let `M(A_F)` be the class of execution/data processes satisfying the named assumptions. Suppose the
canonical owner enforces each `alpha_i` before result-bearing execution and, for every process in
`M(A_F)`, provides the local guarantee

```text
P(V_i) <= alpha_i
```

for the actual member plan and family reach rule. Suppose also

```text
alpha_i >= 0
sum_i alpha_i <= delta_F.
```

Then

```text
P(V_F) = P(union_i V_i)
       <= sum_i P(V_i)
       <= sum_i alpha_i
       <= delta_F.
```

No common null, shared estimand, exchangeability, or independence appears in the proof. The local
owner may use different valid statistical instruments for different members; the family theorem
only requires that each local false-authority event is genuinely bounded at its assigned cap.

The public shorthand may be

```text
P(any reached member falsely promotes in exact family F
  | named maintained assumptions) <= delta_F.
```

The model-class formulation above clarifies that assumptions are premises, not random facts whose
truth probability was estimated.

### 4.3 Impossibility and sharpness theorem

For `m * delta <= 1`, construct `m` disjoint events, each with probability `delta`, and let them be
the local false-promotion events. Every local `delta` guarantee holds while

```text
P(union_i V_i) = m * delta.
```

Therefore no generic procedure using only the local upper bounds can prove a smaller universal
family bound. Precommitment of names/order is valuable governance but does not itself change the
arithmetic.

A tighter result requires an additional verified property, such as smaller owner-enforced caps, a
valid family testing procedure, a justified dependence model, conditionally valid e-values with a
correct family merger, or another canonical theorem.

### 4.4 Corollary for the current three-scope semantics

If three valid local problem-scope guarantees are each bounded only at the registry `delta`, then

```text
P(false first promotion in the exact three-member family | joint assumptions)
  <= min(1, 3 * delta).
```

At `delta = 1/100`, the arithmetic bound is `3/100`. The current repository has no family receipt
and no positive governed sequence, so this is the strongest generic implication of hypothetical
valid local guarantees—not a claim of demonstrated real-world performance.

### 4.5 Design pattern — capped canonical scopes

A compatible family composition has four semantic layers:

1. **Canonical scopes remain unchanged.** N9 derives one scope from each problem binding.
2. **Prospective family relation.** Before family outcomes, bind family event, member order,
   member-specific plan vector, exact caps, family delta, theorem profile, and assumptions.
3. **Local enforcement.** Before owner execution, the confidence ledger constrains member scope
   `i` to an effective top-level ceiling no greater than `alpha_i`. Existing Basel-square
   allocation then runs over local ordinals and obligation weights inside that ceiling.
4. **Family projection.** The same ledger recomputes the relation from the declaration, live N9
   scope derivation, canonical roots/current-head receipts, source/deployment identities, and
   consumer chronology.

The family object is a composition relation, not another `ConfidenceRiskBudgetScope`. It owns no
local ordinal, owner invocation, mutable head, or independent delta registry.

Equal allocation is transparent:

```text
delta_F = 1/100
alpha_1 = alpha_2 = alpha_3 = 1/300
sum alpha_i = 1/100.
```

Unequal exact weights are equally valid if prospectively fixed and summed exactly. No weight may be
chosen after observing family outcomes unless an adaptive theorem explicitly covers that rule.

### 4.6 Governance protocol — terminal and cap effects

The following is a conservative protocol, not the only mathematical possibility:

| Earlier member state | Family chronology | Default cap disposition |
| --- | --- | --- |
| Preflight refusal before owner execution | Retain and publish; advance only under the declared rule. | Actual spend may be zero, but assigned cap retires for this family version. |
| Proven infrastructure failure before any result-bearing exposure | Retry only as the same member, same scope, same cap, under a prospective deterministic retry rule. | No new cap. |
| Owner refusal/error after `started` | Retain as result-bearing terminal. | Reserved spend is burned; unused cap retires. |
| Result-bearing void | Retain; no substitution. | Spend remains; unused cap retires. |
| Dispute | Halt until prospectively resolved. | No cap becomes available to a later scope. |
| Completed negative / grounded refusal | Advance to next committed member. | Unused cap retires. |
| Valid positive | Stop permanently. | Spend remains charged; later caps expire unused. |
| Unreached after positive | Record as unreached. | Assigned cap expires unused. |

A prospective recycling rule may be mathematically possible, but it needs its own canonical theorem
and falsifiers. No-refund is the minimal auditable rule available without that proof.

### 4.7 Theorem B — adaptive continuation

Let `H_{i-1}` be the complete history before member `i`, including all earlier reveals, outputs,
terminal reasons, adjudication, source changes, implementation/model/prompt/configuration changes,
and repair decisions. Let `R_i` and local cap `alpha_i(H_{i-1})` be determined before member `i`'s
result. Require the pathwise constraint

```text
alpha_i(H_{i-1}) >= 0
sum_i alpha_i(H_{i-1}) <= delta_F
```

for every allowed history.

Suppose that whenever member `i` is reached, the actual adaptively selected procedure satisfies

```text
P(P_i ∩ W_i | H_{i-1}, R_i) <= alpha_i(H_{i-1})
almost surely.
```

An equivalent uniform theorem over all implementations selectable by the repair policy, or another
selection-aware theorem proving the same local error statement, is also acceptable.

Then

```text
P(V_i)
  = E[1_{R_i} P(P_i ∩ W_i | H_{i-1}, R_i)]
  <= E[1_{R_i} alpha_i(H_{i-1})].
```

Using the union inequality and the pathwise cap:

```text
P(V_F)
  <= sum_i P(V_i)
  <= E[sum_i 1_{R_i} alpha_i(H_{i-1})]
  <= delta_F.
```

Thus adaptation is not intrinsically incompatible with family control. It is incompatible with
**claiming** control when the local theorem does not cover the adaptive selector.

### 4.8 Adaptive result at the pinned baseline

INT-R9 permits general implementation repair between members
(`int-r9-first-promotion-evaluation-protocol.md:590-650`). The current ledger records local
filtration data and recognizes anytime-valid profiles, but it does not prove that a later procedure
selected using earlier family outcomes remains valid. Relevant owner-verified confidence sequence,
e-value, e-process, and sequential-test profiles are registered as unavailable
(`confidence_ledger.toml:53-121`).

Therefore:

- a **prospectively fixed member-plan vector** is mathematically composable after canonical caps
  and family projection are implemented;
- **outcome-dependent repair** remains numerically blocked until a selection-valid owner theorem is
  delivered; and
- adaptive development may continue in the candidate band if public language omits the family
  probability claim and preserves the limitation.

Prospective governance of whether a repair is “general” or “case-specific” is still necessary, but
that classification alone is not a statistical theorem.

### 4.9 Empirical rule disposition

No empirical rule is used to close the theorem. Equal thirds are a governance/engineering choice,
not an observed optimum. Learned weights, empirical correlations, or historical false-promotion
rates remain unavailable until PolicyOS has an adequate, governed, non-selected evidence base.

### 4.10 E-value disposition

E-values remain a possible local instrument or future family input; they are not appointed as the
answer. A valid merger must define the target event/null, truth configurations, filtration, and
conditional/dependence premises. The current registry refuses the relevant owner theorem. External
literature cannot be cited as if it were a live repository verifier.

### 4.11 Audit R1 acceptance matrix

| Audit R1 requirement | INT-R10 answer |
| --- | --- |
| 1. Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)`: any reached member in the stop-on-first-positive family falsely promotes. |
| 2. Relationship to canonical scopes | Every member binds one live N9 problem binding and its recomputed, distinct canonical scope ID; scopes are not collapsed. |
| 3. No fresh unaccounted budgets | Valid composition requires pre-execution local caps whose exact sum is at most `delta_F`; current source lacks this and therefore fails the requirement. |
| 4. Earlier terminal effects | Refusal, void, dispute, negative, positive, retry, and unreached effects are explicit; no default refund, substitution, or new cap. |
| 5. Aggregate proof | Theorem A proves weighted-union composition; the disjoint-event witness proves the current `3 * delta` bound is sharp. |
| 6. Adaptive continuation | Theorem B states predictable/pathwise cap and selection-valid local premises. INT-R9's current repair policy has no such owner theorem and the numeric claim is withdrawn. |
| 7. Canonical owner reuse | The confidence ledger is extended through a projection; no second ledger, parent risk scope, or duplicate owner is proposed. |
| 8. Live reproducibility | §6 and §7 require recomputation from live scope derivation, family declaration, roots, current heads, cap enforcement, deployment/registry identity, and chronology. Author-written records fail. |

The mandatory falsifier is **not blocked at the pinned baseline**. The result states that plainly and
specifies what a canonical extension must enforce before a single-`delta_F` claim becomes eligible.

### 4.12 Honest claim boundaries

**Current baseline:**

> Three distinct design problems use three distinct canonical non-resettable scopes. The current
> repository has no canonical single-`delta` family composition. From three valid local `delta`
> guarantees, the strongest generic family implication is `min(1, 3 * delta)` under their joint
> maintained assumptions. No numeric theorem is established for outcome-dependent repair.

**After a fixed-plan canonical extension:**

> For exact family `F`, exact canonical scope vector `S`, exact local-cap vector `alpha`, exact
> prospectively committed member-plan vector `R`, theorem/registry versions `G`, obligation bases
> `O`, maintained assumptions `A`, and stopping rule `T`, the canonical confidence-ledger
> projection proves `P(any reached member falsely promotes | A) <= delta_F`.

**After adaptive repair:** the same sentence is allowed only when the canonical projection binds a
verified theorem satisfying Theorem B or an equivalent selection-valid result. Otherwise only the
governance chronology may be claimed, with no family probability.

---

## 5. Counterexamples And Failure Modes

### 5.1 Three fully compliant fresh scopes

A, B, and C each use the canonical N9 derivation and each receive an ordinary top-level `delta`.
Stopping on first positive does not make their union a one-`delta` event. **Required reaction:**
`family_composition_missing`, not prose override.

### 5.2 Disjoint local errors

Three disjoint error events attain `3 * delta`. **Diagnostic:** name the verified dependence premise
that rules out disjointness. If none exists, a tighter bound is unsupported.

### 5.3 Collapsing distinct problems to one scope

Changing all owner keys to one family key would make the local Basel schedule look cumulative but
would corrupt problem ownership, replay, and audit identity. **Required reaction:** reject canonical
scope derivation mismatch.

### 5.4 Parent family scope or second ledger

A new risk scope with its own head, ordinal, or registry beside the member roots duplicates the
canonical owner. **Required reaction:** reject P27/P28 design; a family ID may identify a relation,
not a replacement risk-budget scope.

### 5.5 Post-outcome cap equalization

After slot 1 fails, its recorded cap is reduced and the difference is moved to slot 2 while the
final total remains `delta_F`. Exact arithmetic cannot rescue non-prospective allocation.

### 5.6 Refund after refusal or void

Unused cap is transferred to a new scope without a prospective recycling theorem. This reopens the
search-until-positive path. Conservative default: retire the cap.

### 5.7 Outcome-dependent repair under a fixed-plan theorem

Earlier failure class `X` selects later implementation `R_X`; the local certificate covered `R_X`
only when fixed independently of `X`. Aggregate caps are correct but selection validity is absent.
**Required reaction:** `adaptive_validity_unproved`.

### 5.8 “Anytime-valid” treated as universal permission

Optional stopping inside one valid process is confused with post hoc selection among processes.
**Required reaction:** verify the actual filtration and selector theorem.

### 5.9 E-value product targets the wrong event

Three local e-values are multiplied and labeled family FWER evidence without a registered merger
or correct truth-configuration theorem. **Required reaction:** `family_owner_theorem_unavailable`.

### 5.10 Author-written family receipt

INT-R9 stores `within_family_budget: true` but no canonical verifier opens roots, heads, or local
cap bindings. **Required reaction:** corrupt a real cap/head while retaining markers; validation
must turn red.

### 5.11 After-the-fact spend check

Actual spend happens to sum below `delta_F`, but members executed under larger nominal local
thresholds. The protected property is the error cap governing execution, not merely observed spend.
**Required reaction:** require pre-execution effective-cap evidence.

### 5.12 Conditionality disappears

Family arithmetic is valid but public language omits member obligation bases or validator
soundness. This silently reverses INT-R1. **Required reaction:** refuse incomplete family
conditionality.

### 5.13 Learned weights from nonexistent history

Weights are described as empirically calibrated despite no governed positive history. **Required
reaction:** relabel as prospective governance choice or refuse the empirical claim.

### 5.14 Strictness leaks into the candidate band

Missing family composition is used to prohibit all multi-problem candidate work. **Required
reaction:** block only the numeric authority claim; carry the limitation while candidate work
continues.

### 5.15 Pattern pass

| Pattern | Risk | Correct pattern |
| --- | --- | --- |
| P27 | Parallel family ledger/scope beside N11 | Confidence-ledger-owned relation/projection over unchanged scopes. |
| P28 | INT-R9 prose remains a shadow authority path | Consumer requires canonical projection or publishes the narrower/no numeric claim. |
| P29 | Hand-authored green record | Live recomputation plus property-removal negative control. |
| P31 | Special-case only three named slots | Generic finite/predictable family relation. |
| P32 | Trust IDs/fields without executing source | Recompute scopes, roots, caps, spends, heads, and chronology. |
| P33 | Validator recognizes only literal A/B/C fixture | Generate substitutions, refunds, stale heads, fourth scope, and adaptive repair. |

---

## 6. Benchmark Or Fixture Proposal

The full executable specification is in
[int-r10/fixture-and-artifact-sketch.md](int-r10/fixture-and-artifact-sketch.md). This research adds
no test code.

### 6.1 Fixture identity

```yaml
fixture_id: INT-R10-FWC-001
baseline_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
family_delta: {numerator: 1, denominator: 100}
family_size: 3
stopping_rule: stop_on_first_canonical_positive
member_plan_mode: prospectively_fixed_vector
members:
  - order: 1
    design_problem_id: FWC-A
    local_cap: {numerator: 1, denominator: 300}
    implementation_revision_hash: sha256:<R-A>
  - order: 2
    design_problem_id: FWC-B
    local_cap: {numerator: 1, denominator: 300}
    implementation_revision_hash: sha256:<R-B>
  - order: 3
    design_problem_id: FWC-C
    local_cap: {numerator: 1, denominator: 300}
    implementation_revision_hash: sha256:<R-C>
```

`R-A`, `R-B`, and `R-C` may differ but all must be committed before any family result-bearing
execution. Problem contents, hashes, owner fixtures, and expected scope identities must be
deterministically generated from committed inputs rather than copied from expected output.

### 6.2 Positive future-conformance trace

```text
slot 1 -> problem A -> canonical scope A -> local ordinal 0 -> refused/negative
slot 2 -> problem B -> canonical scope B -> local ordinal 0 -> result-bearing void/negative
slot 3 -> problem C -> canonical scope C -> local ordinal 0 -> positive
stop
```

Required assertions:

1. Live N9 derivation produces three pairwise distinct scope IDs.
2. All three scopes may start at local ordinal zero; the fixture does not invent one family ordinal.
3. Before any probabilistic owner call, each scope is constrained to its assigned `1/300` cap.
4. Every local scheduled reservation is recomputed from that effective cap and refuses overspend.
5. Exact allocated-cap sum is `1/100`; exact aggregate actual spend is at most the cap sum and
   therefore at most `1/100`.
6. Earlier refused, void, disputed, or negative members remain in the projection.
7. No cap is refunded, transferred, or silently reused.
8. The positive comes from the registered third scope and stops the family.
9. The projection is recomputed from live source, roots, current-head receipts, member-plan hashes,
   and consumer chronology.
10. Conditionality names every member's obligation/validator premises and family premises.
11. Revalidation yields the same semantic projection.
12. Corrupting a cap, member plan, scope binding, earlier terminal, registry/deployment identity,
    or head makes validation fail.

At the current baseline, this positive control should refuse `family_composition_unavailable`; that
is an honest baseline result.

### 6.3 Mandatory negative control

Execute the audit falsifier against the live ordinary registry:

```text
scope A -> top-level 1/100
scope B -> top-level 1/100
scope C -> top-level 1/100
```

Baseline characterization must show distinct scope IDs, independent local ordinal-zero histories,
root `budget_delta = 1/100` for each, and no cross-scope cap/projection. A future implementation
must make the same trace go red **before** any single-`1/100` family claim, with an equivalent of:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
```

An INT-R9 sentence or author-written boolean cannot override the failure.

### 6.4 Required metamorphic negatives

The implementation fixture must also reject:

- refunding cap after refusal or void;
- omitting an earlier terminal;
- substituting problem/scope D after seeing A fail;
- swapping supplied scope IDs while preserving field shape;
- duplicate member scope/problem identities;
- changing cap weights after an outcome while preserving final sum;
- changing an uncommitted later member plan after an earlier result;
- adaptive repair without a selection-valid theorem;
- hand-authored green projection without live heads;
- stale member receipt while a later head exists;
- missing one member's maintained assumptions;
- rational overspend hidden by display rounding;
- unregistered e-value multiplication;
- positive from an unregistered fourth scope; and
- collapsing three problems to one scope.

The P29 property-removal control is mandatory: remove effective local-cap enforcement from the real
owner path while keeping every schema field and marker. The verifier must fail.

### 6.5 Sharpness and adaptive fixtures

A pure theorem fixture constructs three disjoint probability events of `1/100` and asserts their
union is `3/100`.

An adaptive fixture lets slot 1's result select slot 2's implementation. Cap arithmetic remains
valid, but the supplied local theorem covers only a plan fixed independently of slot 1. The family
projection must refuse `adaptive_validity_unproved`. A paired positive differs only by supplying a
canonical theorem whose verifier covers the selector and full history.

### 6.6 Fixture authority boundary

Passing proves only the composition property for the named source revision and fixtures. It does
not prove local statistical soundness on real data, open-world obligation completeness, validator
truth, a positive promotion, production readiness, or policy efficacy.

---

## 7. Artifact Contract Sketch

Names below are placeholders, not final schemas.

### 7.1 `FamilyRiskCompositionDeclaration`

Purpose: prospectively bind the exact union event and the member-cap/plan vector before any family
result-bearing execution.

Minimum semantic content:

- schema/theorem-profile versions and content-derived family ID;
- family purpose and confidence-ledger owner reference;
- exact consumer protocol, repository, deployment, and registry bindings;
- exact rational `family_delta`;
- ordered members containing slot ID, design-problem ID, problem content hash, recomputed canonical
  scope ID, local cap, member-specific implementation/revision/configuration digest, local theorem
  profile, and obligation-set reference;
- stopping, dispute, retry, no-substitution, and cap-disposition rules;
- `prospectively_fixed_member_plan` or an adaptive policy plus theorem reference;
- local and family maintained assumptions;
- exact controlled event;
- independently visible commitment evidence preceding result-bearing execution; and
- explicit `authoritative_for`, `may_not_use_for`, and `research_only` fields.

**Authoritative for:** proposing an exact family relation and cap/member-plan vector for canonical
verification.

**May not use for:** proving local certificates, proving the aggregate bound, promotion authority,
production capability, changing per-problem scope identity, or creating a second ledger.

### 7.2 `FamilyRiskCompositionProjection`

Purpose: canonical confidence-ledger recomputation of the family relation over live member roots
and current-head receipts.

Minimum semantic content:

- declaration/family identity and artifact reference;
- family delta, theorem profile, source/deployment/registry identity;
- member-plan standing: prospectively fixed or adaptive theorem verified/refused;
- each member's exact canonical scope, local cap, plan digest, root/receipt/head references, total
  spend, terminal, and cap disposition;
- exact aggregate allocated cap and aggregate actual spend;
- canonical-scope, current-head, chronology, no-refund/no-substitution, and no-unregistered-positive
  results;
- full conditionality and maintained assumptions;
- eligibility/refusal state; and
- recomputed projection hash.

**Authoritative for:** the canonical owner's recomputation that the named family cap relation holds
over the bound live artifacts.

**May not use for:** open-world completeness, validator soundness, external validity, legal
compliance, institutional competence, production readiness, or any family/member plan/assumption
outside the projection.

### 7.3 Anti-duplication constraints

Neither artifact may own:

- a second mutable confidence head;
- local owner checks or invocation;
- a family execution ordinal used to price local checks;
- an independent registry/delta;
- a replacement `ConfidenceRiskBudgetScope`;
- a second promotion decision; or
- an author-supplied green boolean trusted without recomputation.

The declaration is an admitted prospective constraint. The projection is derived by the existing
owner. Local roots/receipts remain authoritative for local accounting.

### 7.4 Required pre-execution observable

A later implementation must prove that the assigned cap constrained the local scope **before** the
first result-bearing probabilistic start:

```text
effective_local_ceiling <= assigned_family_cap
prior_local_spend + next_reservation <= effective_local_ceiling
```

After-the-fact `total_spend <= cap` is insufficient because the local procedure may have executed
under a larger nominal error threshold.

### 7.5 Canonical recomputation outline

A verifier must:

1. validate exact rationals and recompute declaration/family identity;
2. verify prospective visibility before all result-bearing execution;
3. derive every scope through live `confidence_risk_scope_for_problem()`;
4. reject duplicate, substituted, or omitted members;
5. sum local caps exactly and require the result at most `delta_F`;
6. validate every canonical root/current-head receipt through the existing ledger;
7. verify the effective cap was bound before local execution and total local spend is within it;
8. reconstruct terminal chronology from live protocol/ledger artifacts;
9. verify the prospectively fixed member-plan vector, or require the adaptive theorem;
10. preserve member obligation/validator assumptions and currentness; and
11. recompute the projection hash from live source and artifacts.

---

## 8. Later Integration Handoff

### 8.1 Canonical owner

**Owner to extend:** `polisyos.runtime.quality.confidence_ledger` / N11 confidence-ledger lane.

The extension is a cross-scope composition projection over existing roots. It is not owned by
INT-R9, N9, Atlas, or a new family service. GY-GAP2 already records this owner seam
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

### 8.2 Minimum owner-first integration chain

```text
prospective family declaration
-> live member-scope derivation
-> pre-execution effective local-cap enforcement
-> existing local owner execution and immutable receipts
-> exact cap/spend aggregation
-> member-plan or adaptive-theorem verification
-> consumer chronology verification
-> canonical family projection
-> INT-R9 consumption and bounded public claim
-> correction/suspension and behavioral falsifiers
```

No package, field spelling, storage topology, or final schema is ratified here.

### 8.3 What INT-R9 may claim

| Standing | Permitted statement |
| --- | --- |
| Current baseline | The repository has three distinct canonical scopes and no single-`delta` family composition. If three valid local `delta` guarantees exist, their strongest generic family composition is `min(1, 3 * delta)` under joint assumptions. No adaptive numeric theorem is established. |
| Future exact family with prospectively fixed member-plan vector and canonical caps/projection | `P(any reached member falsely promotes in exact family F | named assumptions) <= delta_F`, bound to exact scope, cap, member-plan, registry, obligation, evaluator, and source versions. |
| Outcome-dependent repair | The same numeric claim only when a canonical selection-valid theorem is verified; otherwise governance chronology only, with no family probability. |

INT-R9 may not restore “one cumulative scope.” It should reference the family projection while
retaining three canonical scope IDs.

### 8.4 INT-R1 handoff

Every member must bind its exact obligation declaration/closure basis, cutoff, compiler/validator
versions, and unresolved remainder. The family projection may relate these declarations but may
not manufacture one universal family obligation set or remove the open-world rider.

A later-discovered obligation or validator defect may suspend a member's current authority and the
family claim. Correction appends and reissues; historical proof is not rewritten into eternal
current validity.

### 8.5 Public projection handoff

A public surface must expose at least family identity, member count, prospectively fixed versus
adaptive posture, family delta/cap profile, canonical projection reference/currentness,
obligation/validator conditionality, terminal standing, bounded authority scope, and correction or
suspension status. It must not translate research acceptance into implemented capability.

---

## 9. Promotion And Kill Rules

### 9.1 Research promotion rule

Consolidation may accept INT-R10 only with both conclusions intact:

1. weighted-union composition is valid under exact owner-enforced local caps and the stated local
   guarantees; and
2. the current repository lacks those cross-scope caps/projection and lacks a theorem for INT-R9's
   outcome-dependent repair.

Adopting the theorem while deleting the blocked capability statement would recreate the false
single-`delta` implication.

### 9.2 Conditions before implementation authorization

A separate implementation task must first have:

- ratified owner-first semantics naming the confidence ledger;
- exact family event and theorem profile;
- decision between prospectively fixed member-plan vector and adaptive selection;
- effective local-cap design that preserves canonical scope identity/replay;
- INT-R1 member obligation interfaces;
- live-source recomputation and currentness design;
- terminal/no-refund or separately proved recycling semantics;
- public correction/suspension path; and
- §6 fixtures as acceptance criteria.

### 9.3 Kill rules

Any proposal is **NO-GO** if it:

- weakens `design-problem:<design_problem_id>` identity;
- resets/reuses a scope for fresh budget;
- creates a second confidence ledger, parent risk scope, independent head, or duplicate theorem
  owner;
- asserts composition only in INT-R9 prose or an author-written record;
- checks caps only after result-bearing execution;
- uses floats/display rounding in budget authority;
- changes caps or uncommitted member plans after outcomes without a verified adaptive theorem;
- refunds, substitutes, or inserts a fourth scope without a prospectively proved rule;
- omits earlier refusal/void/dispute from chronology;
- imports Holm, Šidák, clinical boundaries, or e-value products without their required objects and
  assumptions;
- claims adaptive validity from a local anytime-valid label alone;
- hides INT-R1 conditionality;
- accepts stale heads or supplied scope IDs without live recomputation;
- lets a marker-only validator pass after local-cap enforcement is removed;
- generalizes to policy efficacy, legal compliance, or production readiness; or
- blocks candidate exploration merely because authority-band composition is missing.

### 9.4 GY-GAP2 closure evidence

GY-GAP2 closes only when the full chain exists: producer/admission of the prospective family
relation, local-cap enforcement, canonical member receipts, aggregate recomputation, consumer
bridge, public/audit projection or explicit boundary, correction path, and behavioral positive/
negative/adaptive tests. A schema alone is `contract_only`, not closure.

### 9.5 Benchmark passage rule

Passing INT-R10 fixtures proves only the named composition property for the tested revision and
artifacts. It does not prove local theorem soundness on real data, open-world obligation
completeness, existence of a positive promotion, or production readiness. S0-K16 remains binding.

---

## 10. Open Questions For Consolidation

1. Will INT-R9 use a complete prospectively fixed member-plan vector, or retain outcome-dependent
   repair and commission a selection-valid theorem?
2. What owner-internal mechanism constrains a scope to `alpha_i` before execution while preserving
   the canonical `scope_id`, root semantics, replay, and deployment binding?
3. Which existing custody mechanism proves that membership, order, cap vector, and member-plan
   vector were independently visible before result-bearing execution?
4. Should the first implementation support only an exact finite family or a predictable online cap
   stream with pathwise total at most `delta_F`?
5. Are equal thirds acceptable governance, or should prospectively declared consequence weights be
   used? No empirical weighting is currently justified.
6. Is conservative no-refund sufficient, or is a prospective recycling theorem worth the added
   complexity?
7. Which local proof profiles, if any, can establish validity conditional on earlier family history
   and implementation selection? `owner_theorem_unavailable_v1` may remain the honest answer.
8. How should the family projection expose different obligation bases, cutoffs, validators, and
   unresolved remainders without manufacturing one universal denominator?
9. Does the separate INT-R1 obligation-instance identity gap block a family claim for any member
   whose decisive obligation instances cannot yet be represented?
10. When a disputed member is later corrected, may the same family version resume, or must an
    append-only new family version be issued?
11. Which changes—registry, theorem profile, source, validator, problem content, member plan,
    evaluator, or obligation basis—suspend versus invalidate the family projection?
12. What minimum public language prevents `delta_F` from being read as a world-wide probability of
    policy harm or missed obligation?
13. If real owner-verified e-processes arrive, is the desired target still strong family-wise false
    authority control, or a different global-null/evidence claim?
14. If future scopes expose compatible valid p-values, is Holm/closed testing worth the complexity,
    or is weighted union preferable for transparent heterogeneous authority semantics?
15. What competent evidence, if any, could justify a stronger-than-union dependence correction
    across design problems? At the pinned baseline the answer is none.
16. Should consolidation amend INT-R9 immediately to the current no-single-`delta` position, or keep
    it fully blocked until a canonical family projection exists? It must not retain the implication
    that three ordinary scopes share one top-level budget.

The central answer is stable despite these open choices: **today, three ordinary problem scopes
provide at most the generic composition of three valid local guarantees—`3 * delta` in the live
three-member case. A future single-`delta_F` family claim is available only through prospective
local caps enforced and recomputed by the canonical confidence ledger. Outcome-dependent repair
additionally requires a selection-valid local theorem.**
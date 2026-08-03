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

A valid family-wise composition exists without weakening the canonical per-problem scope, without
a common null, without exchangeability, and without independence. It is the exact weighted-union
composition:

> For an exact prospectively governed family `F`, let `V_i` be the event that reached member `i`
> falsely produces a canonical promotion. If the canonical confidence owner enforces a local
> top-level cap `alpha_i` before member `i` can execute, every local false-promotion theorem is valid
> for that cap under the named maintained assumptions, and `sum_i alpha_i <= delta_F`, then
> `P(any member of F falsely promotes | maintained assumptions) <= delta_F`.

The proof is the union inequality. It applies to heterogeneous design problems because the
controlled object is a union of authority-error events, not one shared estimand or null. The bound
is sharp from the declared information alone: three disjoint false-promotion events of probability
`delta` satisfy all three local bounds and have family probability `3 * delta`. No generic
improvement below the sum may be claimed without additional verified structure.

The pinned repository does **not** implement the premises of that theorem. N9 derives a distinct
canonical scope from each `design_problem_id`
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`). Each scope has its own
root-level `budget_delta` and immutable local history
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`). `start_check()` assigns
ordinals and sums prior spend only inside the current scope
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`). GY-GAP2 explicitly
records that no cross-scope/family composition exists and that per-problem scope identity is not the
defect
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

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

The live registry sets `delta = 1/100`, so the corresponding arithmetic bound is `3/100`, not
`1/100`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`). This is a theorem
about what follows from valid local guarantees, not a claim that the current proving ground has
produced a positive governed sequence or a live family certificate. The proving ground remains at
13 typed blockers, `useful_design_rate = 0`, and an unbuilt D3.8 gate
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

A compatible future design is available. Preserve the three canonical scope IDs. Before any
family result-bearing execution, bind an exact cap vector—such as `delta_F/3` per member—and a
complete **member-specific implementation/revision plan**. Different members may have different
precommitted revisions, configurations, models, prompts, evaluators, or evidence cutoffs; the
non-adaptive theorem does not require identical implementations. It requires the complete member
plan vector to be fixed before family outcomes. The existing Basel-square schedule may then
allocate **inside** each local cap, and the **same confidence ledger** may recompute a family
composition projection from the live declaration, live N9 scope derivation, canonical roots,
current-head receipts, and attempt chronology. This is an extension of the canonical owner, not a
parent risk scope or second ledger.

Adaptive continuation is a separate theorem boundary. INT-R9 permits “general implementation
repair” after an earlier refusal or void
(`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
A later implementation selected using earlier outcomes is not covered merely because its local
process is anytime-valid. A family bound survives that policy only if every reached member's
false-promotion guarantee remains valid conditional on the full prior history—or under an
equivalent uniform or selection-aware theorem—and the allocation is predictable with a pathwise
total at most `delta_F`. The live registry marks the relevant owner-verified confidence-sequence,
e-value, e-process, and sequential-test profiles as theorem-unavailable
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). INT-R9 must
therefore precommit the complete member plan, obtain a canonical adaptive-validity theorem, or
withdraw the numeric family claim.

E-values do not remove this obligation. Products or martingale mergers require conditional
e-validity or a justified dependence structure and must target the relevant null. External theory
cannot replace a repository-owned verifier. No empirical calibration can fill the gap because the
project lacks governed positive promotion history
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

Supporting artifacts:

- [Primary-source and transfer ledger](int-r10/source-and-transfer-ledger.md)
- [Artifact, recomputation, and executable fixture sketch](int-r10/fixture-and-artifact-sketch.md)

---

## 1. Task And Project Fit

### 1.1 Exact question

The question is:

> When PolicyOS evaluates several design problems in an exact family and reports the first valid
> positive, what composition is available over the canonical per-problem confidence scopes, and
> what may then honestly be claimed?

INT-R9 needed one cumulative risk statement for three precommitted slots. Its audit found three
canonical scope IDs instead and supplied eight acceptance requirements plus a mandatory
three-fresh-budget falsifier
(`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105`).
INT-R10 answers that missing owner-level arithmetic. It does not redesign INT-R9's case selection,
sealing, adjudication, publication, or public-record protocol.

A valid answer must keep three questions separate:

1. **Local validity:** what does each problem scope prove about its own false-promotion event?
2. **Family accounting:** how are the local guarantees composed over the exact family event?
3. **Selection validity:** do local guarantees remain valid when earlier outcomes influence later
   implementation, data, evaluation, or cap choices?

### 1.2 Exact family event

For ordered family `F = (1, ..., m)`, define:

- `R_i`: slot `i` is reached under the declared stopping, dispute, retry, and no-substitution rules;
- `P_i`: slot `i` emits a canonical positive promotion terminal;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`: reached slot `i` falsely promotes; and
- `V_F = union_i V_i`: at least one reached member falsely promotes.

Under stop on first canonical positive, `V_F` is exactly the event that the family's reported first
promotion is false. Earlier refused, void, disputed, or negative members remain in the family
chronology. Members after a valid positive are recorded as unreached, not silently erased.

The controlled quantity is **false authority promotion**. It is not the probability that a useful
design exists, the probability that every external obligation is known, a common-null rejection,
an unbiased effect estimate, population performance, or benchmark success.

### 1.3 Canonical owner

Repository rules require owner-first reuse and reject parallel owners and author-written proof
(`AGENTS.md:35-66`, `AGENTS.md:71-89`). The confidence ledger already owns risk scopes, exact
rational allocation, typed theorem refusal, risk burning before owner execution, immutable events,
canonical receipts, conditionality, and N9 projections
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752`).

The owner split is:

- **Confidence ledger / N11:** local-cap enforcement, family composition theorem/refusal, exact
  aggregate, and live family projection.
- **N9:** canonical problem binding and per-problem scope derivation
  (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
- **INT-R9:** exact family/order, case custody, stopping, disputes, publication, and repair
  governance
  (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
- **INT-R1:** each member's declared obligation basis and visible open-world remainder
  (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`).
- **Existing public projection owner:** display of the bounded claim, never creation of the bound.

### 1.4 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Arithmetic and custody of PolicyOS's family-wise false-promotion statement over its own promotion receipts | **OWN** | Bind family, caps, scope identities, assumptions, member-plan versions, terminal history, currentness, and correction; recompute the statement from canonical artifacts. | Ownership is of PolicyOS's signed statement, not external legal or empirical truth. |
| N9 problem bindings, INT-R1 declarations, owner certificates, evaluators, adjudicators, external sources, and implementation freezes | **INTEGRATE** | Verify, purpose-admit, content-bind, and react fail-closed when inputs change. | PolicyOS does not become the external source, court, regulator, evaluator, or implementation operator. |
| Unadmitted dependence hypotheses, proposed weights, criticism, suspected coupling, or candidate families | **OBSERVE** | Retain as research/challenge signals; never mint a tighter bound from observation. | Observation or projection does not establish a theorem premise. |
| Creating legal effect, operating the policy, certifying population efficacy, or deciding institutional competence | **OUT_OF_SCOPE** | Publish only the bounded PolicyOS claim and route external acts to competent owners. | Composition does not make PolicyOS an administrator or sovereign authority. |

S0-K05, S0-K16, and the authority-band/candidate-band lens require missing composition to block the
numeric authority claim, not candidate exploration under a declared limitation
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`,
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`).

### 1.5 Standing

- **Research theorem:** `accepted_narrow_scope`.
- **Current runtime capability:** `blocked` / `cross_scope_composition_missing`, as registered by
  GY-GAP2
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

The result appoints no new owner and authorizes no code.

---

## 2. Current Repo Baseline

### 2.1 Pinned inspection

- Repository: `https://github.com/DenisKopylov/polisyos`
- Branch inspected: `main`
- Exact baseline: `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`
- Research branch: `research/int-r10-family-wise-risk-composition`
- Inspection date: `2026-08-03`

The task orientation was materially correct. One precision matters: an ordinal-zero check does not
spend the whole `delta`; it receives a scheduled fraction. The defect is that each fresh scope
receives a fresh **top-level delta budget and guarantee series**, not that its first check consumes
all of `delta`
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3998-4025`).

### 2.2 Line-anchored census

| Repository anchor | Verified source fact | Family consequence |
| --- | --- | --- |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52` | The ledger allocates before owner execution, refuses statistical families without a repository-owned theorem verifier, carries exact maintained assumptions, and states that local good-event accounting uses the union bound without an independence claim. | Conservative composition is already the owner's mathematical style, but only for represented owner objects. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184` | `ConfidenceRiskBudgetScope` is the stable scope for one non-resettable budget; `scope_id` derives from owner, authority purpose, owner-scope key, and epoch. | Per-problem scope identity is deliberate and must not be weakened or replaced by a family ID. |
| `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` | `confidence_risk_scope_for_problem()` is the only admissible N11 scope for one N9 binding and uses `design-problem:<design_problem_id>`. | Distinct fresh design problems correctly produce distinct scope IDs. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:250-390` | Registry policy has one top-level `delta`; schedules have bounded mass; obligation pools must totally partition the declared denominator and sum exactly to one. | Exact local allocation exists, but there is no denominator or cap relation over design-problem scopes. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557` | An immutable root binds one risk scope to registry, schedule, obligation split, `budget_delta`, conditionality, and maintained assumptions. | Every problem scope receives its own root-level budget binding. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752` | A canonical receipt recomputes one scope's current head, events, checks, total spend, budget status, good-event clause, and assumptions. | Receipts are suitable member evidence for a future family projection but remain scope-local. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1175-1298` | `prepare_check()` binds claim/instrument facts before outcome and persists preflight refusal with zero spend. | Local refusals are typed and durable; no family terminal/cap disposition exists. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364` | `start_check()` reads one scope, assigns the next local ordinal, computes spend from registry `delta`, sums only local prior spend, rejects only local overspend, and burns risk before owner execution. | Three fresh scopes each start at local ordinal zero and do not see one another's budget or spend. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3740-3855` | `_instrument_preflight_refusal()` rejects disallowed roles, ineligible profiles, unavailable owner theorems, and non-anytime-valid profiles; validation requires coherent zero-spend refusal. | The owner already has the correct fail-closed pattern for an unavailable family theorem. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025` | Receipt validation recomputes contiguous local ordinals and schedule spend, rejects forged rows/decimal drift, and implements exact Basel-square allocation. | The within-scope schedule is reproducible; it is not a cross-scope family schedule. |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:1-18` | Live `delta` is exactly `1/100`; schedules have mass `1` and `1/2`. | No family cap vector or one-third top-level allocation is registered. |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121` | Profiles are dominated by deterministic, ineligible, and unavailable-theorem paths; the executable constant-one e-process cannot satisfy a promotion obligation. | No executable e-value/e-process family theorem follows from registry labels. |
| `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` | GY-GAP2 records that per-problem scopes are correct and no cross-scope/family/parent-scope composition exists. | The gap is missing composition, not wrong scope identity. |
| `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650` | INT-R9 fixes three slots and stopping but permits general implementation repair after refusal/void while asserting cumulative risk. | Its sequence is adaptive unless the complete member-plan vector is precommitted. |
| `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105` | Audit R1 requires exact family event, canonical-scope relation, no fresh budgets, terminal effects, aggregate proof, adaptive validity or narrower claim, owner reuse, and live reproduction. | These are answered in §4.11 and §6. |
| `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90` | INT-R1 permits only relative obligation coverage and keeps risk conditional on declared basis and validator soundness. | Family composition cannot discharge open-world or validator premises. |

### 2.3 Mandatory falsifier

For distinct problem IDs `A`, `B`, and `C`:

1. N9 derives pairwise distinct scopes from the three problem IDs
   (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
2. Each scope receives its own root with registry-level `budget_delta`
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`).
3. Each empty scope can assign local ordinal zero; spend and prior-spend checks remain local
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`).
4. No live family object requires the sum of A/B/C top-level caps to be at most `1/100`
   (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

The trace therefore passes local source rules. A sentence saying “one cumulative scope” is not
closure evidence.

### 2.4 Current arithmetic and sharpness

If each canonical problem scope supplies only

```text
P(V_A | A_F) <= delta
P(V_B | A_F) <= delta
P(V_C | A_F) <= delta,
```

then

```text
P(V_A union V_B union V_C | A_F) <= 3 * delta.
```

For `delta <= 1/3`, choose three disjoint events of probability `delta`. Every local bound holds and
the union probability is exactly `3 * delta`. The factor is attainable, not merely cautious.

### 2.5 Empirical state

The live registry supplies no calibrated family base rate; its executable probabilistic path is
mostly refusal/unavailable and the only executable e-process is constant one
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). The proving ground
has no positive governed design and D3.8 is unbuilt
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

INT-R10 therefore does not learn dependence, cap weights, or false-promotion rates from historical
outcomes. Equal thirds are a governance choice, not an empirical estimate.

### 2.6 Capability verdict

| Capability | Standing and evidence |
| --- | --- |
| Stable non-resettable scope per problem | `implemented` — `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`; `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` |
| Exact within-scope schedule and recomputation | `implemented` — `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025` |
| Risk burn before owner execution | `implemented` — `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364` |
| Typed unavailable-theorem refusal | `implemented` — `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3740-3855` |
| Cross-scope family declaration/cap binding | `missing` — `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` |
| Live family projection over canonical heads | `missing` — `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` |
| Selection-valid theorem for outcome-dependent repair | `missing` — `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`; `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650` |
| INT-R9 single-`delta` family claim | `blocked` — `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105` |

---

## 3. External Research Baseline

Detailed source-by-source transfer judgments are in
[int-r10/source-and-transfer-ledger.md](int-r10/source-and-transfer-ledger.md).

### 3.1 Multiple testing and online FWER

Holm controls family-wise error for a finite family of valid p-values without requiring favorable
dependence
([Holm 1979, DOI 10.2307/4615733](https://doi.org/10.2307/4615733)). Tian and Ramdas develop online
FWER control; simple Bonferroni-style predictable allocations transfer broadly, while stronger
adaptive procedures require stated independence or local-dependence conditions
([Tian & Ramdas 2021, DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381),
[arXiv:1910.04900](https://arxiv.org/abs/1910.04900)).

The directly transferable principle is:

```text
allocate nonnegative local error caps predictably;
prove every local authority-error statement at its assigned cap;
keep the exact total within the declared family bound.
```

PolicyOS does not currently expose one family of valid p-values or a step-down owner, so Holm is a
future option, not a theorem about current artifacts.

### 3.2 Group-sequential designs

Pocock and O'Brien–Fleming show that repeated looks and early stopping must be priced as one
procedure
([Pocock 1977, DOI 10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191);
[O'Brien & Fleming 1979, DOI 10.2307/2530245](https://doi.org/10.2307/2530245)). Lan and DeMets
formalize alpha-spending boundaries indexed by information time
([Lan & DeMets 1983, DOI 10.1093/biomet/70.3.659](https://doi.org/10.1093/biomet/70.3.659)).

Pre-allocation, cumulative accounting, and no fresh reset transfer. Their boundary formulas do not:
those papers analyze repeated observations of one accumulating experiment under a specified joint
model. Three PolicyOS problems are not three information times for one effect.

### 3.3 Model-dependent corrections

Šidák's rectangle inequality relies on a multivariate-normal probability structure
([Šidák 1967, DOI 10.1080/01621459.1967.10482935](https://doi.org/10.1080/01621459.1967.10482935)).
PolicyOS has no verified common multivariate model or cross-problem dependence contract
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). A Šidák/product
number would therefore be an unsupported premise.

### 3.4 Anytime-valid inference

Confidence sequences and nonnegative supermartingales provide time-uniform validity under their
filtration/process assumptions
([Howard et al. 2021, DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991);
[Howard et al. 2020, DOI 10.1214/18-PS321](https://doi.org/10.1214/18-PS321)). Ramdas, Grünwald,
Vovk, and Shafer distinguish safe optional continuation from choosing a strategy after observing
results
([Ramdas et al. 2023, DOI 10.1214/23-STS894](https://doi.org/10.1214/23-STS894),
[arXiv:2210.01948](https://arxiv.org/abs/2210.01948)).

The actual filtration must include every earlier reveal, terminal, repair decision, source change,
model/configuration choice, and adjudication used to select the later procedure. A local
anytime-valid label does not prove that adaptive selection is valid.

### 3.5 E-values

E-values can be calibrated and combined; averaging can merge e-values for one null under arbitrary
dependence
([Vovk & Wang 2021, DOI 10.1214/20-AOS2020](https://doi.org/10.1214/20-AOS2020)). Sequential merging
requires martingale/conditional validity, and independent merging is a separate structured case
([Vovk & Wang 2020, arXiv:2007.06382](https://arxiv.org/abs/2007.06382)). Multiple-testing gains for
independent or sequential e-values state those assumptions
([Vovk & Wang 2020, arXiv:2003.00593](https://arxiv.org/abs/2003.00593)).

“E-values multiply” is not a family theorem. The merger must have the correct target and every
factor must satisfy its conditional/dependence premise. PolicyOS needs strong control of the event
that **any** authority promotion is false across heterogeneous truth configurations.

### 3.6 Selection

Post-selection inference must account for the selection event
([Fithian, Sun & Taylor, arXiv:1410.2597](https://arxiv.org/abs/1410.2597)). A prospective family
bound can include stop-on-first-positive selection. It does not provide an unbiased selected-effect
estimate, representativeness, population generalization, or protection against upstream case-pool
selection.

### 3.7 Transfer verdict

| Method | Disposition |
| --- | --- |
| Exact weighted union / Bonferroni event accounting | **Transfers directly** once local guarantees and caps are canonical. |
| Holm | **Possible future option** requiring valid family p-values and a canonical procedure. |
| Šidák/product correction | **Does not transfer** without verified joint structure. |
| Pocock/O'Brien–Fleming/Lan–DeMets | **Accounting lesson only**; repeated-look boundaries do not cross heterogeneous problems. |
| Confidence sequences/e-processes | **Transfer within a valid process**; adaptive families require selection-valid local guarantees. |
| E-value multiplication/merging | **Not automatic**; correct target and conditional/dependence premises are required. |
| Selective inference | **Meaning constraint**, not a current composition implementation. |
| Empirical calibration | **Unavailable** at the current project state, as shown by `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`. |

---

## 4. Result

### 4.1 Explicit epistemic classification

| Category | Result |
| --- | --- |
| **Theorem** | Weighted-union composition over heterogeneous canonical scopes; adaptive extension under predictable/pathwise-bounded allocations and history-conditional, uniform, or equivalent selection-valid local guarantees. |
| **Empirical rule** | None is required. Learned weights/dependence corrections would require governed data absent at `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`. |
| **Design pattern** | Preserve every canonical scope; prospectively bind local caps and the complete member-plan vector; run the local schedule inside each cap; recompute one ledger-owned family projection. |
| **Governance protocol** | Exact family/order commitment, no substitution, durable earlier terminals, no outcome-dependent refund by default, and explicit fixed-plan versus adaptive standing. |
| **Impossibility result** | Three ordinary full-`delta` scopes do not imply one `delta`; `3 * delta` is sharp. A fixed-plan theorem does not cover outcome-dependent repair. |
| **Engineering convenience** | Three slots, equal `delta_F/3` caps, conservative no-refund, and placeholder artifact names. Other choices are permitted if the theorem and invariants remain. |

### 4.2 Theorem A — prospectively fixed family

Before any family result-bearing execution, bind:

- exact member identities/order and canonical problem bindings;
- exact nonnegative local caps `alpha_i`;
- each member's implementation/revision/configuration/model/prompt/evaluator/evidence-cutoff plan;
- stopping, dispute, retry, and no-substitution rules; and
- joint maintained assumptions `A_F`.

Different members may have different precommitted plans. “Fixed” means the complete vector is fixed
before family outcomes, not that every member uses identical bytes.

Suppose the canonical owner enforces each `alpha_i` before execution and supplies

```text
P(V_i | A_F) <= alpha_i
```

for the actual member plan and reach rule, with

```text
alpha_i >= 0
sum_i alpha_i <= delta_F.
```

Then

```text
P(V_F | A_F)
  = P(union_i V_i | A_F)
  <= sum_i P(V_i | A_F)
  <= sum_i alpha_i
  <= delta_F.
```

No common null, estimand, exchangeability, or independence appears in the proof.

### 4.3 Sharpness and impossibility

For `m * delta <= 1`, choose `m` disjoint events of probability `delta` and identify them with the
local false-promotion events. Every local guarantee holds while the family probability is
`m * delta`. No smaller generic bound follows from local upper bounds alone.

A tighter result requires additional verified truth-bearing structure: smaller owner-enforced caps,
a valid family testing procedure, a justified dependence model, conditionally valid e-values with
a correct merger, or another canonical theorem.

### 4.4 Current three-scope corollary

Because the live source gives each ordinary problem scope the registry top-level delta
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`) and has no family cap
relation
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`), three valid local
`delta` guarantees compose generically to `min(1, 3 * delta)`. At the live `1/100`, that is
`3/100`.

### 4.5 Design pattern — capped canonical scopes

1. **Keep canonical scopes.** N9 continues deriving one scope per exact problem binding
   (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
2. **Admit a prospective family relation.** Bind family event, member order, member-plan vector,
   exact caps, family delta, theorem profile, and assumptions before outcomes.
3. **Enforce local caps.** Before owner execution, the confidence ledger constrains member `i` to
   an effective top-level ceiling no greater than `alpha_i`. The existing Basel-square schedule
   then allocates over local ordinals/obligations inside that ceiling; current schedule behavior is
   at `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`.
4. **Recompute a family projection.** The same owner verifies the declaration, live N9 scope
   derivation, roots/current heads, cap enforcement, member plans, chronology, assumptions, and
   source/deployment identities.

The family object is a relation over scopes, not another `ConfidenceRiskBudgetScope`. It owns no
local ordinal, invocation, independent delta registry, or mutable head.

Equal allocation is transparent:

```text
delta_F = 1/100
alpha_1 = alpha_2 = alpha_3 = 1/300
sum alpha_i = 1/100.
```

Unequal exact weights are also valid if prospectively fixed. No weight may be selected after
outcomes without an adaptive theorem.

### 4.6 Governance protocol — terminal effects

| Earlier member state | Family chronology | Default cap effect |
| --- | --- | --- |
| Preflight refusal before owner execution | Retain/publish; advance only under declared rule. | Actual spend may be zero; assigned cap retires for this family version. |
| Proven infrastructure failure before result-bearing exposure | Retry only same member/scope/cap under a prospective deterministic rule. | No new cap. |
| Owner refusal/error after `started` | Retain as result-bearing terminal. | Reserved spend is burned; unused cap retires. |
| Result-bearing void | Retain; no substitution. | Spend remains; unused cap retires. |
| Dispute | Halt until prospectively resolved. | No cap becomes available to a later scope. |
| Completed negative / grounded refusal | Advance to next committed member. | Unused cap retires. |
| Valid positive | Stop permanently. | Spend remains charged; later caps expire unused. |
| Unreached after positive | Record as unreached. | Assigned cap expires unused. |

No-refund is a conservative governance protocol, not a theorem that recycling can never be valid.
A recycling rule requires its own canonical theorem and falsifiers. Typed local preflight and
unavailable-theorem refusal already provide the fail-closed precedent
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1175-1298`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3740-3855`).

### 4.7 Theorem B — adaptive continuation

Let `H_{i-1}` be the complete history before member `i`, including earlier reveals, outputs,
terminal reasons, adjudication, source changes, implementation/model/prompt/configuration changes,
and repair choices. Let cap `alpha_i(H_{i-1})` be determined before member `i`'s result, with the
pathwise constraint

```text
alpha_i(H_{i-1}) >= 0
sum_i alpha_i(H_{i-1}) <= delta_F.
```

If every reached adaptively selected procedure satisfies

```text
P(P_i ∩ W_i | H_{i-1}, R_i, A_F) <= alpha_i(H_{i-1})
almost surely,
```

or an equivalent uniform/selection-aware theorem, then

```text
P(V_i | A_F)
  = E[1_{R_i} P(P_i ∩ W_i | H_{i-1}, R_i, A_F)]
  <= E[1_{R_i} alpha_i(H_{i-1})],
```

and therefore

```text
P(V_F | A_F)
  <= E[sum_i 1_{R_i} alpha_i(H_{i-1})]
  <= delta_F.
```

Adaptation is not intrinsically impossible. Claiming control is impossible when the local theorem
does not cover the adaptive selector.

### 4.8 Adaptive baseline result

INT-R9's general repair clause makes later member plans outcome-dependent unless the complete
vector was already fixed
(`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
The live registry does not provide the necessary owner theorem
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). Therefore:

- a prospectively fixed member-plan vector is mathematically composable after canonical caps and a
  family projection are implemented;
- outcome-dependent repair remains numerically blocked until a selection-valid owner theorem
  exists; and
- adaptive candidate work may continue if the public numeric family claim is omitted and the
  limitation is preserved, consistent with
  `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`.

### 4.9 Empirical and e-value dispositions

No empirical rule closes the theorem because governed positive history is absent
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).
Equal thirds are governance, not calibration.

E-values remain a possible local instrument or future family input. They are not appointed as the
answer because the live owner lacks the relevant theorem profile
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

### 4.10 Honest claims

**At the pinned baseline:**

> Three distinct problems use three distinct canonical scopes. The repository has no canonical
> single-`delta` family composition
> (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). From three valid
> local `delta` guarantees, the strongest generic implication is `min(1, 3 * delta)` under joint
> maintained assumptions. No numeric theorem covers outcome-dependent repair
> (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

**After a prospectively fixed-plan canonical extension:**

> For exact family `F`, scope vector `S`, local-cap vector `alpha`, prospectively committed
> member-plan vector `R`, theorem/registry versions `G`, obligation bases `O`, assumptions `A`, and
> stopping rule `T`, the canonical confidence-ledger projection proves
> `P(any reached member falsely promotes | A) <= delta_F`.

**After adaptive repair:** the same numeric sentence is allowed only when the projection binds a
verified theorem satisfying §4.7 or an equivalent selection-valid result.

### 4.11 Audit R1 matrix

| R1 requirement | Answer |
| --- | --- |
| Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)`. |
| Relationship to canonical scopes | Every member binds one live N9 problem binding and its recomputed distinct scope; scope identity stays unchanged. |
| No fresh unaccounted budgets | Valid composition requires pre-execution local caps whose exact sum is at most `delta_F`; the baseline lacks this. |
| Earlier terminal effects | Refusal, retry, void, dispute, negative, positive, and unreached effects are explicit; no default refund/substitution. |
| Aggregate proof | §4.2 proves weighted union; §4.3 proves `3 * delta` sharpness. |
| Adaptive continuation | §4.7 states the predictable/pathwise cap and selection-valid local premise; the current repair claim is blocked. |
| Canonical owner reuse | The confidence ledger emits a projection; no second ledger or parent risk scope is proposed. |
| Live reproducibility | §6 and §7 require live scope derivation, roots, heads, cap enforcement, member plans, source identities, and chronology. |

The mandatory falsifier is **not blocked at the pinned baseline**, exactly as GY-GAP2 records
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

---

## 5. Counterexamples And Failure Modes

1. **Three compliant fresh scopes.** Each receives ordinary `delta`; stopping does not make their
   union one-`delta`. Baseline source permits this at
   `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` and
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`.
2. **Disjoint local errors.** They attain `3 * delta`; no unverified favorable dependence may be
   assumed.
3. **Collapse three problems to one scope.** This contradicts the canonical one-problem scope rule
   at `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`.
4. **Parent family scope or second ledger.** This violates owner-first/P27/P28 constraints at
   `AGENTS.md:35-66` and `AGENTS.md:71-89`.
5. **Post-outcome cap equalization.** Final arithmetic may look correct while predictability is
   false.
6. **Refund after refusal/void.** Without a prospective theorem, this reopens search-until-positive.
7. **Outcome-dependent repair under fixed-plan theorem.** Correct caps do not prove selection
   validity; INT-R9's repair clause is at
   `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`.
8. **“Anytime-valid” as universal permission.** Local optional stopping is not post hoc choice among
   procedures; live unavailable profiles are at
   `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.
9. **E-value product targets wrong event.** A product/global-null result is not automatically strong
   FWER for any false authority promotion.
10. **Author-written family receipt.** Markers without live roots/heads are P29/P32, prohibited by
    `AGENTS.md:35-66` and `AGENTS.md:71-89`.
11. **After-the-fact spend check.** Small realized spend does not prove execution used the smaller
    error cap; current risk is burned before owner execution at
    `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`.
12. **Conditionality disappears.** This reverses INT-R1's relative-coverage result at
    `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`.
13. **Learned weights from nonexistent history.** The project state at
    `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`
    cannot support calibration.
14. **Strictness leaks into candidate band.** S0-K06 permits candidate work under declared limits;
    only the authority claim must fail closed
    (`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`).

### Pattern pass

| Pattern | Risk | Correct pattern |
| --- | --- | --- |
| P27/P28 | Parallel family ledger/scope | One confidence-ledger projection over unchanged scopes (`AGENTS.md:71-89`). |
| P29/P32 | Hand-authored green record | Live behavioral recomputation (`AGENTS.md:35-66`, `AGENTS.md:71-89`). |
| P31 | One special patch for INT-R9 | Generic finite/predictable family relation (`AGENTS.md:35-66`). |
| P33 | Validator recognizes only literal A/B/C | Generate substitutions, refunds, stale heads, fourth scope, and adaptive repair (`AGENTS.md:35-66`, `AGENTS.md:71-89`). |

---

## 6. Benchmark Or Fixture Proposal

The complete specification is in
[int-r10/fixture-and-artifact-sketch.md](int-r10/fixture-and-artifact-sketch.md). No test code is
added by this research.

### 6.1 Fixed inputs

```yaml
fixture_id: INT-R10-FWC-001
baseline_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
family_delta: {numerator: 1, denominator: 100}
stopping_rule: stop_on_first_canonical_positive
member_plan_mode: prospectively_fixed_vector
members:
  - {order: 1, problem: FWC-A, local_cap: 1/300, revision: sha256:<R-A>}
  - {order: 2, problem: FWC-B, local_cap: 1/300, revision: sha256:<R-B>}
  - {order: 3, problem: FWC-C, local_cap: 1/300, revision: sha256:<R-C>}
```

`R-A`, `R-B`, and `R-C` may differ, but all plans must be committed before any family
result-bearing execution.

### 6.2 Positive future-conformance fixture

```text
slot 1 -> A -> scope A -> local ordinal 0 -> refused/negative
slot 2 -> B -> scope B -> local ordinal 0 -> result-bearing void/negative
slot 3 -> C -> scope C -> local ordinal 0 -> positive
stop
```

Required assertions:

- live N9 derivation produces three distinct scopes, as required by
  `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
- all three local ordinal-zero starts remain valid; no family ordinal replaces them;
- each scope is constrained to `1/300` before any probabilistic owner call;
- local schedule reservations are recomputed inside that cap and overspend fails before execution;
- exact allocated-cap sum equals `1/100` and exact aggregate actual spend is at most `1/100`;
- earlier terminals remain; no refund/substitution occurs;
- the positive is the registered third member and stops the family;
- the exact precommitted member-plan vector is verified;
- live roots/current heads, registry/deployment identity, assumptions, and chronology are
  recomputed; and
- corrupting any cap, plan, scope, terminal, root/head, or source identity fails.

The current baseline should refuse this positive control because GY-GAP2 is open
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

### 6.3 Mandatory negative control

Execute the exact current path:

```text
scope A -> top-level 1/100
scope B -> top-level 1/100
scope C -> top-level 1/100
```

Baseline characterization must show distinct scopes
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`), independent local
ordinal-zero histories and local spend
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`), three root-level
budgets
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`), and no family binding
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

A future implementation must make the trace go red before any single-`1/100` family claim, with an
equivalent of:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
```

### 6.4 Required negatives

Reject cap refund, omitted earlier terminal, member substitution, scope swap, duplicate scope,
outcome-dependent cap change, uncommitted later-plan change, adaptive repair without theorem,
hand-authored green projection, stale head, missing member conditionality, rational overspend hidden
by display rounding, unregistered e-value product, unregistered fourth positive, identity collapse,
and after-the-fact-only cap checking.

The P29 property-removal control must delete effective cap enforcement while retaining all marker
fields. Validation must fail, consistent with `AGENTS.md:35-66`.

A paired adaptive fixture lets member 1's result select member 2's implementation. It must refuse
without a selection-valid theorem and pass only when the canonical verifier covers the selector and
full history. The live registry currently has no such theorem
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

### 6.5 Fixture boundary

Passing proves only family-composition behavior for the tested source/artifacts. It does not prove
local theorem soundness on real data, open-world completeness, validator truth, positive promotion,
or production readiness, consistent with S0-K16
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`).

---

## 7. Artifact Contract Sketch

Names are placeholders, not final schemas.

### 7.1 `FamilyRiskCompositionDeclaration`

Prospectively binds:

- exact family event/purpose and content-derived family ID;
- repository/deployment/registry/theorem identities;
- exact rational `family_delta`;
- ordered members with problem binding/hash, recomputed canonical scope, local cap, member-specific
  implementation/configuration/model/prompt/evaluator/evidence-cutoff digest, local theorem
  profile, and obligation-set reference;
- stopping/dispute/retry/no-substitution/cap-disposition rules;
- fixed member-plan vector or adaptive policy plus theorem reference;
- assumptions; and
- independently visible commitment evidence before result-bearing execution.

**Authoritative for:** proposing an exact family/cap/member-plan relation for canonical verification.

**May not use for:** proving a local certificate, proving the aggregate bound, promotion authority,
production capability, replacing a scope, or creating a second ledger.

### 7.2 `FamilyRiskCompositionProjection`

The confidence ledger recomputes:

- declaration/family identity and source/deployment/registry bindings;
- fixed-plan or adaptive-theorem standing;
- every member's canonical scope, cap, plan digest, root/current-head receipt, local spend, terminal,
  and cap disposition;
- exact aggregate cap and actual spend;
- scope derivation, currentness, chronology, no-refund/no-substitution, and no-unregistered-positive
  results;
- full conditionality and assumptions; and
- eligibility/refusal plus projection hash.

**Authoritative for:** the canonical owner's recomputation that the named family relation holds over
bound live artifacts.

**May not use for:** open-world completeness, validator soundness, external validity, legal
compliance, institutional competence, production readiness, or any family/plan/assumption outside
the projection.

### 7.3 Anti-duplication constraints

Neither artifact may own a second mutable head, local owner checks, a family ordinal used to price
local checks, an independent delta registry, a replacement risk scope, or a second promotion
decision. These prohibitions follow the owner rules in `AGENTS.md:35-66` and `AGENTS.md:71-89` and
the canonical scope rule in
`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`.

### 7.4 Pre-execution observable

A verifier must establish:

```text
effective_local_ceiling <= assigned_family_cap
prior_local_spend + next_reservation <= effective_local_ceiling
```

before the first result-bearing probabilistic start. After-the-fact `total_spend <= cap` is
insufficient because current owner execution burns risk before invocation
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`).

### 7.5 Live recomputation

The canonical verifier validates exact rationals, prospective visibility, family/member-plan hashes,
live N9 scope derivation, distinct members, aggregate caps, each canonical root/current-head
receipt, effective cap enforcement, local spend, chronology, assumptions, and fixed/adaptive
standing. It emits the family projection only after those checks. This extends the existing
receipt-recomputation pattern at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`.

---

## 8. Later Integration Handoff

### 8.1 Canonical owner

**Owner to extend:** `polisyos.runtime.quality.confidence_ledger` / N11 lane. GY-GAP2 already places
the gap there and states that N11's per-problem scope is not wrong
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

Minimum chain:

```text
prospective family declaration
-> live member-scope derivation
-> pre-execution local-cap enforcement
-> existing local owner execution and receipts
-> exact cap/spend aggregation
-> member-plan or adaptive-theorem verification
-> chronology verification
-> canonical family projection
-> INT-R9 consumption/public bounded claim
-> correction/suspension and behavioral falsifiers
```

### 8.2 INT-R9 claim handoff

| Standing | Permitted claim |
| --- | --- |
| Current baseline | No canonical single-`delta` composition exists (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). Three valid local `delta` guarantees compose generically to `min(1, 3 * delta)`; no adaptive numeric theorem exists (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). |
| Future exact family with prospectively fixed member-plan vector and canonical caps/projection | `P(any reached member falsely promotes in exact family F | named assumptions) <= delta_F`, bound to exact scope/cap/plan/registry/obligation/evaluator/source versions. |
| Outcome-dependent repair | Same numeric claim only with a canonical selection-valid theorem; otherwise chronology/governance claim only. |

INT-R9 must not restore “one cumulative scope.” It must reference one family projection while
retaining all canonical member scope IDs
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).

### 8.3 INT-R1 and public handoff

Every member binds its exact closure basis, cutoff, compiler/validator versions, and unresolved
remainder; a family projection cannot manufacture one universal obligation set
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`).

A public surface exposes family identity, member count, fixed/adaptive posture, family delta/caps,
canonical projection/currentness, obligation/validator conditionality, terminal standing, authority
scope, and correction/suspension. Projection cannot mint authority by itself, consistent with
S0-K05/S0-K16
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`).

---

## 9. Promotion And Kill Rules

### 9.1 Research promotion

Consolidation may accept INT-R10 only with both conclusions intact:

1. weighted-union composition is valid under exact owner-enforced local caps and stated local
   guarantees; and
2. the current repository lacks cross-scope caps/projection and lacks an adaptive theorem, as
   recorded by
   `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` and
   `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.

### 9.2 Preconditions for later implementation authorization

A separate task needs ratified owner-first semantics, exact family event/theorem profile, a decision
between fixed member-plan vector and adaptive selection, effective local-cap design preserving
scope identity/replay, INT-R1 member obligation interfaces, live recomputation/currentness,
terminal/refund semantics, public correction/suspension, and §6 fixtures. This document does not
authorize implementation.

### 9.3 Kill rules

A proposal is **NO-GO** if it weakens problem scope identity, resets/reuses scope for fresh budget,
creates a second ledger or parent risk scope, asserts composition only in prose, checks caps only
after execution, uses floats, changes caps/plans after outcomes without theorem, refunds/substitutes
without proof, omits earlier terminals, imports statistical devices without assumptions, claims
adaptive validity from an anytime-valid label, hides INT-R1 conditionality, trusts stale/supplied
heads or scopes, passes a marker-only validator, generalizes to efficacy/compliance/readiness, or
blocks candidate work merely because authority composition is missing.

These kill rules follow the canonical scope path
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`), owner/refusal and
behavioral-verification rules (`AGENTS.md:35-66`, `AGENTS.md:71-89`), INT-R1 conditionality
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`),
and candidate-band rule
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`).

### 9.4 GY-GAP2 closure evidence

GY-GAP2 closes only after the full producer/admission -> local-cap enforcement -> member receipts ->
aggregate recomputation -> consumer bridge -> public/audit projection -> correction path ->
behavioral fixtures chain exists. A schema alone is `contract_only`. The gap and owner are recorded
at `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`.

### 9.5 Passage boundary

Passing INT-R10 fixtures proves only the named composition behavior. It does not prove local theorem
soundness on real data, open-world completeness, positive promotion, or production readiness. That
is the bounded-passage rule in
`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`.

---

## 10. Open Questions For Consolidation

1. Will INT-R9 use a complete prospectively fixed member-plan vector, or retain outcome-dependent
   repair and commission a selection-valid theorem?
2. What owner-internal mechanism constrains a scope to `alpha_i` before execution while preserving
   the canonical identity/replay semantics at
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184` and
   `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`?
3. Which custody mechanism proves that membership, order, cap vector, and member-plan vector were
   independently visible before result-bearing execution?
4. Should the first implementation support only an exact finite family or a predictable online cap
   stream with pathwise total at most `delta_F`?
5. Are equal thirds acceptable governance, or should prospective consequence weights be used?
   Empirical weighting is not supported by
   `policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`.
6. Is conservative no-refund sufficient, or is a prospective recycling theorem worth the added
   complexity?
7. Which local proof profiles can establish validity conditional on prior family history and
   implementation selection? Current owner profiles remain unavailable at
   `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.
8. How should the projection expose different obligation bases/cutoffs/validators without creating
   one universal denominator, contrary to
   `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`?
9. Does the separate obligation-instance identity gap block any member's composition standing?
10. When a disputed member is corrected, may the same family version resume or must append-only
    reissue occur?
11. Which registry, theorem, source, validator, problem, member-plan, evaluator, or obligation
    changes suspend versus invalidate the projection?
12. What minimum public language prevents `delta_F` from being read as world-wide policy-harm or
    missed-obligation probability?
13. If real owner-verified e-processes arrive, is the target still strong family-wise false
    authority control or a different global-null/evidence claim?
14. If compatible valid p-values arrive, is Holm/closed testing worth the complexity or is weighted
    union preferable for heterogeneous authority semantics?
15. What competent evidence could justify a stronger-than-union dependence correction? None is
    represented by the current gap/registry at
    `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` and
    `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`.
16. Should consolidation amend INT-R9 immediately to the no-single-`delta` position or keep it fully
    blocked until a family projection exists? It must not retain the implication that three
    ordinary scopes share one top-level budget.

The central answer is stable: **today, three ordinary problem scopes provide at most the generic
composition of three valid local guarantees—`3 * delta` in the live three-member case. A future
single-`delta_F` family claim is available only through prospective local caps enforced and
recomputed by the canonical confidence ledger. Outcome-dependent repair additionally requires a
selection-valid local theorem.**
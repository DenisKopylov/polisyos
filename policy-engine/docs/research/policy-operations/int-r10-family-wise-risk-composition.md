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
  - independent research conclusion for family-wise false-promotion composition over distinct canonical N9 design-problem confidence scopes
  - proof of the weighted-union composition theorem under exact prospective local caps and stated maintained assumptions
  - impossibility result for retaining one delta across several ordinary full-delta scopes without additional composition structure
  - research-level adaptive-continuation theorem boundary and required history-conditional validity premise
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
  - assertion that the adaptive INT-R9 repair policy has a family-wise numeric theorem
  - unconditional claim about false promotion outside the declared obligation sets and maintained assumptions
  - population performance, external-validity, legal-compliance, or institutional-competence conclusion
research_only: true
---

# INT-R10 — Family-wise Risk Composition over Canonical Confidence Scopes

## Executive Finding

**Result: `accepted_narrow_scope`. Current runtime capability: `blocked`.**

A valid family-wise composition is available without weakening the canonical per-problem scope,
without a common null, without exchangeability, and without independence. It is the exact weighted
union composition:

> For an exact prospectively governed family `F`, let `V_i` be the event that reached member `i`
> falsely produces a canonical promotion. If the canonical confidence owner enforces a local
> top-level cap `alpha_i` before member `i` can execute, every local false-promotion theorem is valid
> for that cap under the named maintained assumptions, and `sum_i alpha_i <= delta_F`, then
> `P(any member of F falsely promotes | maintained assumptions) <= delta_F`.

The proof is the union inequality. It is valid for heterogeneous design problems because the
controlled object is a union of authority-error events, not a shared statistical estimand. The
bound can be sharp: three disjoint local false-promotion events of probability `delta` satisfy all
three local bounds and have family probability `3 * delta`. No generic improvement follows from
three local bounds alone.

The pinned repository does **not** implement the premises of that theorem. N9 derives a different
canonical scope for each `design_problem_id`; each scope has its own immutable root, local event
history, ordinal sequence, and registry-level `delta`; `start_check()` sums prior spend only from
that scope; and no cross-scope cap, family binding, or family recomputation path exists
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`;
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`, `:518-557`,
`:1301-1364`; `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).
Consequently the audit’s fully compliant trace remains live:

```text
slot 1 -> problem A -> scope A -> fresh top-level delta
slot 2 -> problem B -> scope B -> fresh top-level delta
slot 3 -> problem C -> scope C -> fresh top-level delta
stop on first positive
```

For three ordinary scopes the only generic family statement is
`P(false first promotion | maintained assumptions) <= min(1, 3 * delta)`. With the live registry’s
`delta = 1/100`, that is `3/100`, not `1/100`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`). A sentence saying
“one cumulative scope” cannot alter this result.

A compatible future pattern is available: preserve the three canonical scope IDs; prospectively
bind each to a local cap, such as `delta_F / 3`; let the existing Basel-square schedule allocate
**inside** that local cap; and have the **same confidence ledger** recompute a composition projection
from the live family declaration, live N9 scope derivation, canonical roots, current-head receipts,
and consumer chronology. This is an extension of the canonical owner, not a parent scope or second
ledger. Equal thirds are an engineering convenience; any exact nonnegative cap vector summing to
at most `delta_F` satisfies the theorem.

Adaptive continuation is a separate theorem boundary. INT-R9 permits “general implementation
repair” after an earlier refusal or void. A later implementation selected using earlier outcomes
is not another fixed look. A family bound survives that policy only if each reached member’s local
false-promotion guarantee holds conditional on the full prior history—or uniformly over every
implementation the repair policy may select—and the allocation is predictable with a pathwise
sum at most `delta_F`. The current ledger has no such cross-scope owner theorem. Therefore INT-R9
must either freeze one decisive implementation across the family, obtain a canonical adaptive
validity theorem, or withdraw the numeric family claim. Arithmetic alone cannot validate repair.

E-values do not remove this obligation. Products or martingale mergers require conditional
e-validity or justified dependence structure and must target the relevant null. The current
registry’s executable e-process is the closed constant-one process, which cannot satisfy a
promotion obligation; owner-verified e-value/e-process profiles are registered as
`owner_theorem_unavailable_v1`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). No empirical
calibration can fill the gap: the project has no positive governed promotion history from which to
learn a family error rate.

The supporting research package is:

- [primary-source and transfer ledger](int-r10/source-and-transfer-ledger.md); and
- [artifact, recomputation, and executable fixture sketch](int-r10/fixture-and-artifact-sketch.md).

---

## 1. Task And Project Fit

### 1.1 Exact research question

The question is not whether several probabilities can be added in the abstract. It is:

> When several PolicyOS design problems are evaluated in a prospectively governed sequence and
> the first valid positive becomes an authority-bearing promotion, what exact event is controlled,
> how does that event relate to the canonical per-problem confidence scopes, and what bound can be
> reproduced from the live owner artifacts?

INT-R9 required one cumulative confidence budget across three precommitted slots, but its audit
found that the canonical source creates three scope IDs and supplies no family arithmetic. The
audit made eight properties mandatory and supplied the three-fresh-scope falsifier
(`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-83`).
INT-R10 answers that owner-level arithmetic question. It does not re-design the case-selection,
sealing, adjudication, or publication protocol.

### 1.2 Exact family event

For a prospectively committed ordered family `F = (1, ..., m)`, define:

- `R_i`: member `i` is reached under the family’s stopping and dispute rules;
- `P_i`: member `i` emits a valid canonical positive promotion terminal;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`: reached member `i` falsely promotes; and
- `V_F = union_i V_i`: at least one reached member falsely promotes.

Under stop on the first canonical positive, `V_F` is exactly the event that the reported first
promotion is false. Reachability matters: a member after a prior positive is never part of the
realized authority path, while an earlier refusal, void, dispute, or negative remains part of the
family chronology and cap disposition.

The controlled quantity is therefore **family-wise false authority promotion**, not:

- a common-null rejection event;
- the probability that a useful design exists;
- the probability that every external obligation is known;
- an effect-estimation error for the selected design;
- population performance; or
- a benchmark success rate.

### 1.3 Why the arithmetic belongs to the confidence ledger

The repository’s operating rule is reuse-first and owner-first: extend the live semantic owner
instead of creating plan-local authority; P27/P28 reject parallel owners and unstrangled duplicate
paths, while P29 rejects author-written proof
(`AGENTS.md:35-66`, `:71-89`). The confidence ledger already owns risk scopes, exact allocation,
owner-proof profiles, risk burning, immutable events, current-head receipts, conditionality, and
N9 projections. INT-R9 consumes those outputs; it does not own their probability arithmetic.

Accordingly:

- **the confidence ledger owns** family cap composition, local-cap enforcement, and the live
  composition projection;
- **N9 owns** canonical problem binding and per-problem scope derivation;
- **INT-R9 owns** the prospective queue, case custody, stopping, publication, and repair governance;
- **INT-R1 supplies** each member’s declared obligation basis and keeps the open-world remainder
  visible; and
- **Atlas or the existing public projection owner** may later display the bounded claim without
  becoming its source.

### 1.4 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Arithmetic and custody of a PolicyOS family-wise false-promotion claim over its own canonical promotion receipts | **OWN** | Bind the exact family, cap vector, scope identities, maintained assumptions, terminal history, source versions, and correction standing; recompute the claim from the canonical owner. | Ownership is of PolicyOS’s risk claim, not of the external truth of every obligation or policy effect. |
| N9 problem bindings, INT-R1 obligation declarations, owner certificates, evaluator/adjudicator records, external source facts, and implementation freezes | **INTEGRATE** | Verify, purpose-admit, content-bind, and react fail-closed when these inputs change. | PolicyOS does not become the external legal, empirical, evaluator, or institutional authority. |
| Unadmitted dependence hypotheses, empirical base-rate suggestions, criticism, suspected scope coupling, or proposed family definitions | **OBSERVE** | Retain as candidate research or challenge signals; never use observation to mint a tighter bound. | Observation and projection do not establish an assumption or theorem. |
| Creating legal effect, certifying population efficacy, deciding external institutional competence, or operating the underlying policy | **OUT_OF_SCOPE** | Publish only the bounded PolicyOS claim and route external acts/evidence to their competent owners. | A risk composition theorem does not make PolicyOS an administrator, regulator, court, or implementation operator. |

This follows S0-K05’s no-authority-by-observation rule and S0-K16’s bounded-passage rule. It also
uses the authority-band/candidate-band lens: absence of family composition blocks the numeric
cross-problem authority claim but must not prohibit candidate exploration under a declared
limitation
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:45-112`,
`:160-190`).

### 1.5 Result standing

The result has two different standings that must not be compressed:

1. **Research theorem standing: accepted narrow scope.** Weighted union composition under exact
   prospective caps is established, as is the adaptive conditional-validity boundary.
2. **Repository capability standing: blocked.** The pinned source has no canonical cross-scope cap
   or recomputed family receipt, so neither the fixed-family `delta_F` claim nor the adaptive claim
   is executable today.

A negative runtime finding is part of the result, not a reason to soften the frontmatter. The
research does not appoint an owner—the owner already exists—and does not authorize code.

---

## 2. Current Repo Baseline

### 2.1 Pinned inspection

- Repository: `https://github.com/DenisKopylov/polisyos`.
- Branch inspected: `main`.
- Exact baseline: `978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`.
- Research branch: `research/int-r10-family-wise-risk-composition`, created from that exact commit.
- Inspection date: `2026-08-03`.
- Source changes: none. This branch adds research Markdown only.

The task’s supplied anchors were materially correct. One precision is important: an ordinal-zero
check does not literally spend the whole `delta` in one operation. It receives a scheduled fraction
of the scope’s top-level budget. The defect is that each fresh scope owns a fresh **top-level
`delta` guarantee and allocation series**, not that its first check consumes all of `delta`.

### 2.2 Line-anchored census

| Repository anchor | Verified source fact | Family consequence |
| --- | --- | --- |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52` | The ledger allocates before owner execution, fails closed when a statistical theorem verifier is absent, declares exact maintained assumptions, and says its good-event composition uses the union bound without an independence claim. | The existing mathematical style already supports conservative event composition, but only for objects actually inside the owner path. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184` | `ConfidenceRiskBudgetScope` is the stable scope for one non-resettable budget. `scope_id` is derived from owner, purpose, owner-scope key, and epoch; mutable owner content is a root binding. | Scope identity is deliberately stable and must not be weakened or replaced by a family ID. |
| `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375` | `confidence_risk_scope_for_problem()` is documented as the only N11 scope for one N9 binding and sets `owner_scope_key = design-problem:<design_problem_id>`. | Distinct fresh design problems naturally and correctly produce distinct canonical scope IDs. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:257-377` | The registry has one top-level `delta`; schedules have bounded mass; obligation pools must totally partition the obligation enum and weights must sum exactly to one. | Internal allocation is exact relative to the registry, but there is no second denominator over problem scopes. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557` | An immutable root binds one `risk_scope` to registry, schedule, obligation split, `budget_delta`, conditionality, and maintained assumptions. | Every problem scope receives its own root and its own top-level budget binding. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752` | A canonical receipt recomputes one scope’s current durable head, events, checks, total spend, budget status, good-event clause, and maintained assumptions. | The receipt is rich enough to be a member input to a future family projection, but it is scope-local. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364` | `start_check()` loads one scope’s state, assigns the next ordinal from that scope’s current checks, computes spend from the registry’s `delta`, sums prior spend from those checks, blocks only if that local total exceeds the registry `delta`, and burns risk before the owner call. | Three fresh scopes each begin at ordinal zero and do not see one another’s spend or top-level budget. |
| `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3998-4024` | `basel_square_v1` allocates `delta * obligation_weight * mass * c/(t+1)^2` with an exact rational lower bound for `6/pi^2`; the projection hash binds kernel, coefficient, delta, and obligation weights. | Basel-square is a correct **within-scope** ordinal schedule. It is not a cross-scope family schedule. |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:1-18` | Live `delta` is exactly `1/100`; schedules have mass `1` and `1/2`. | No `1/3` family allocation or family cap is registered. Schedule mass changes local schedule mass; it does not bind three roots into one family. |
| `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121` | Profiles are dominated by refusal/unavailable/deterministic paths; the only executable e-process is constant one and cannot satisfy obligations; owner-verified e-value/e-process/sequential instruments use an unavailable-owner theorem profile. | There is no executable e-value composition or empirical family theorem to reuse. |
| `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10` | GY-GAP2 records that per-problem scopes are correct, no `cross_scope`, `family_wise`, or `parent_scope` implementation exists, and three fresh problems can obtain three fresh top-level budgets. | The gap is a missing composition capability, not a defect in N11 scope identity. |
| `policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:600-650` | INT-R9 permits general implementation repair between refused/void slots while asserting one cumulative risk scope. | The queue is adaptive in implementation, not merely sequential in observation; a fixed-look theorem cannot be assumed. |
| `policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105` | Audit R1 requires the exact family event, canonical-scope relation, no fresh budgets, terminal effects, aggregate proof, adaptive validity or narrowed claim, owner reuse, and live reproduction. | These are the acceptance conditions applied in §4.12 and the fixture package. |
| `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90` | INT-R1 accepts only completeness relative to a declared closure basis and keeps the risk statement conditional on that basis and validator soundness. | Family composition can add local bounds; it cannot discharge open-world obligation or validator assumptions. |

### 2.3 The mandatory falsifier at the pinned baseline

Take three newly authored N9 problem bindings with distinct IDs `A`, `B`, and `C`.

1. N9 derives `scope_A`, `scope_B`, and `scope_C` from the three IDs. They are pairwise distinct
   because the owner-scope key participates in the scope hash
   (`promotion_sequence.py:356-375`; `confidence_ledger.py:156-184`).
2. Each scope opens a separate root with registry `budget_delta = 1/100`
   (`confidence_ledger.py:518-557`; `confidence_ledger.toml:1-18`).
3. Each empty scope’s first started check receives local ordinal zero. Its spend is calculated from
   the same top-level registry delta, obligation weight, schedule mass, and Basel coefficient
   (`confidence_ledger.py:1301-1364`, `:3998-4024`).
4. Prior spend for `scope_B` excludes `scope_A`; prior spend for `scope_C` excludes both earlier
   scopes.
5. No live source object requires `cap_A + cap_B + cap_C <= 1/100`.
6. Stopping on the first positive changes which events are observed, but it does not reduce the
   probability of their union below the sum of valid local upper bounds without additional
   structure.

Thus the trace is not blocked. If each scope supplies only
`P(V_i | A_i) <= delta`, the generic family statement is:

```text
P(V_A union V_B union V_C | joint maintained assumptions)
  <= P(V_A) + P(V_B) + P(V_C)
  <= 3 * delta.
```

At the registry instance:

```text
delta = 1/100
3 * delta = 3/100.
```

### 2.4 Why `3 * delta` is not merely conservative rhetoric

For `delta <= 1/3`, take a probability space with three disjoint events `E_A`, `E_B`, `E_C`, each
of probability `delta`. Let the three local false-promotion events equal those events. Every local
scope satisfies its `delta` guarantee, while:

```text
P(E_A union E_B union E_C) = 3 * delta.
```

This witness proves that the factor three is attainable under the information currently declared.
A stronger generic bound would be false. Perfect positive dependence could instead produce a
family probability of only `delta`, but the repository neither asserts nor verifies that dependence.
One cannot choose the favorable dependence after seeing the desired answer.

### 2.5 Honest empirical state

The registry does not supply a calibration route. Its statistical production path has essentially
no demonstrated positive use, while deterministic and refusal profiles dominate
(`confidence_ledger.toml:53-121`). The broader project records no positive governed promotion,
`useful_design_rate = 0`, and an unbuilt D3.8 promotion gate
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:404-430`).

Therefore INT-R10 does not estimate correlation among false-promotion events, learn unequal cap
weights from historical outcomes, fit a prior probability of success, or justify a Šidák/product
correction empirically. Such values would be authored assumptions over nonexistent data.

### 2.6 Capability-chain verdict

| Capability element | Standing at `978e6b958...` |
| --- | --- |
| Per-problem stable non-resettable scope | `implemented` |
| Exact rational within-scope allocation | `implemented` |
| Risk burn before owner execution | `implemented` |
| Immutable scope-local root/event/receipt chain | `implemented` |
| Conditionality on obligation completeness and validator soundness | `implemented` |
| Cross-scope family declaration admitted by ledger | `missing` |
| Enforced local cap derived from family allocation | `missing` |
| Aggregate exact cap verifier | `missing` |
| Recomputed family projection over live scope heads | `missing` |
| Adaptive-repair owner theorem | `missing` |
| Behavioral mandatory-falsifier test | `missing` |
| INT-R9 single-`delta` family claim | `blocked` |

The correct baseline description is: **per-scope accounting implemented; family composition and
adaptive validity missing**.

---

## 3. External Research Baseline

The detailed citation and transfer ledger is preserved in
[int-r10/source-and-transfer-ledger.md](int-r10/source-and-transfer-ledger.md). This section records
the load-bearing conclusions.

### 3.1 Multiple testing: what directly transfers

Holm’s step-down procedure controls family-wise error for a finite family of valid p-values and can
improve on single-step Bonferroni without relying on favorable dependence
([Holm 1979](https://doi.org/10.2307/4615733)). Tian and Ramdas extend online FWER control to
sequences of hypotheses; simple Bonferroni-style allocations extend directly, while their more
adaptive power improvements require independent or locally dependent p-values
([Tian & Ramdas 2021](https://doi.org/10.1177/0962280220983381),
[arXiv:1910.04900](https://arxiv.org/abs/1910.04900)).

The transferable core is not a p-value algorithm. It is:

```text
choose nonnegative allocations predictably;
prove each local error statement at its allocation;
keep the aggregate allocation within the family bound.
```

PolicyOS does not currently expose one valid p-value per scope or a family rejection ordering, so
Holm is not directly executable. Weighted union accounting is executable as a theorem once local
caps and local guarantees are real.

### 3.2 Group sequential and alpha-spending designs

Pocock and O’Brien–Fleming show that repeated looks and early stopping must be priced as one
procedure rather than fresh tests
([Pocock 1977](https://doi.org/10.1093/biomet/64.2.191);
[O’Brien & Fleming 1979](https://doi.org/10.2307/2530245)). Lan and DeMets formalize an
alpha-spending function whose boundary depends on past/current information times rather than all
future looks ([Lan & DeMets 1983](https://doi.org/10.1093/biomet/70.3.659)).

What transfers is pre-allocation, cumulative accounting, and no reset. The boundary formulas do
not transfer: those papers concern repeated analyses of one accumulating experiment under a
specified joint model. Three PolicyOS design problems are not three information times for one
estimand. Calling slot number “information time” would be a category error.

### 3.3 Šidák and stronger dependence-based corrections

Šidák’s rectangle result is grounded in a multivariate-normal probability structure
([Šidák 1967](https://doi.org/10.1080/01621459.1967.10482935)). Product-form corrections can be
stronger than a union bound when the required dependence/model premises hold. PolicyOS has no
verified common multivariate distribution or exchangeability relation over heterogeneous design
problems. A Šidák number would therefore be an unsupported empirical/theoretical assumption.

### 3.4 Anytime-valid inference and optional continuation

Confidence sequences and nonnegative supermartingales can preserve validity uniformly over time
and at stopping times under their process assumptions
([Howard et al. 2021](https://doi.org/10.1214/20-AOS1991);
[Howard et al. 2020](https://doi.org/10.1214/18-PS321)). Ramdas, Grünwald, Vovk, and Shafer make the
filtration and predictability boundary explicit: optional stopping or continuation can be safe,
but selecting a betting strategy after seeing outcomes is not
([Ramdas et al. 2023](https://doi.org/10.1214/23-STS894),
[arXiv:2210.01948](https://arxiv.org/abs/2210.01948)).

This transfers directly to INT-R9 repair. If earlier failures influence a later implementation,
the later local theorem must be valid conditional on that complete history or uniformly over the
permitted selector. “Anytime-valid” inside the later scope does not retroactively validate how
that scope’s implementation was selected.

### 3.5 E-values: combination is target- and assumption-specific

Vovk and Wang show that e-values can be calibrated and combined; averaging can merge e-values for
one hypothesis under arbitrary dependence
([Vovk & Wang 2021](https://doi.org/10.1214/20-AOS2020)). Sequential e-value merging uses
martingale constructions, and independent merging is a separate structured case
([Vovk & Wang 2020, arXiv:2007.06382](https://arxiv.org/abs/2007.06382)); multiple-testing gains
for independent or sequential e-values likewise state those assumptions
([arXiv:2003.00593](https://arxiv.org/abs/2003.00593)).

The slogan “e-values multiply” is insufficient. A product needs conditional e-validity or the
specified independence structure and usually targets a joint/intersection null. PolicyOS needs
strong control of a union event across every relevant truth configuration. A local e-process may
be a useful instrument, but it does not eliminate the family owner, cap allocation, or exact event
definition.

### 3.6 Selective inference

Fithian, Sun, and Taylor formalize that inference after selection must account for the selection
event ([arXiv:1410.2597](https://arxiv.org/abs/1410.2597)). A prospectively bounded family can
include stop-on-first-positive selection in its error event, but the bound does not estimate the
selected policy’s effect without selection bias, prove representativeness, or grant external
validity. INT-R10 closes only the false-authority family event.

### 3.7 External-baseline verdict

| Method family | Transfer verdict |
| --- | --- |
| Exact weighted union / Bonferroni event accounting | **Transfers directly** once local bounds and caps are owner-enforced. |
| Holm step-down | **Potential future option**, but requires valid family p-values and a canonical procedure not present. |
| Šidák/product correction | **Does not transfer** without verified joint structure. |
| Pocock/O’Brien–Fleming/Lan–DeMets | **Accounting pattern only**; boundary theorem does not transfer across different problems. |
| Confidence sequences/e-processes | **Transfers within a valid process** and to adaptive families only with history-conditional/uniform validity. |
| E-value multiplication/merging | **Not automatic**; requires correct target and conditional/dependence premises. |
| Selective inference | **Meaning constraint**, not a family-composition implementation. |
| Empirical calibration | **Unavailable** because the project lacks the required governed outcome history. |

---

## 4. Result

### 4.1 Epistemic classification

| Kind | INT-R10 result |
| --- | --- |
| **Theorem** | Exact weighted-union composition over heterogeneous canonical scopes; adaptive extension under predictable allocations and history-conditional or uniform local validity. |
| **Empirical rule** | None is needed for the theorem. Any learned weighting, dependence correction, or base-rate calibration would require data the project does not have. Equal thirds are not empirical truth. |
| **Design pattern** | Keep every canonical per-problem scope; prospectively bind it to a local cap; run the existing within-scope schedule inside that cap; recompute one ledger-owned family projection over live member receipts. |
| **Governance protocol** | Exact family/order commitment, no substitution, terminal retention, no outcome-dependent refund by default, result-independent disclosure, fixed-revision or theorem-backed adaptive policy, and bounded public wording. |
| **Impossibility result** | Three ordinary full-`delta` scopes do not imply one `delta`; `3 * delta` is sharp without additional structure. A fixed-scope theorem cannot cover arbitrary outcome-dependent repair. |
| **Engineering convenience** | Three slots, equal `delta_F/3` caps, a no-refund rule, placeholder artifact names, and one suggested error-code vocabulary. These are replaceable if the invariants and proof remain. |

### 4.2 Theorem 1 — fixed-family weighted union composition

**Setup.** Let `F = {1, ..., m}` be an exact prospectively declared family. For every member `i`,
let `V_i` be the reached-member false-promotion event defined in §1.2. Let `A_F` denote the named
joint premise set, including each member’s obligation-completeness and validator-soundness premise,
canonical scope derivation, prospective family membership, local-cap enforcement, and source/
revision bindings.

Let `M(A_F)` be the class of data-generating and execution processes under which those premises
hold. Suppose the canonical owner enforces exact nonnegative rational caps `alpha_i` before any
result-bearing probabilistic execution and, for every `P` in `M(A_F)`,

```text
P(V_i) <= alpha_i  for all i,
sum_i alpha_i <= delta_F.
```

**Conclusion.** For every `P` in `M(A_F)`,

```text
P(V_F) = P(union_i V_i) <= delta_F.
```

**Proof.** By subadditivity of probability,

```text
P(union_i V_i) <= sum_i P(V_i) <= sum_i alpha_i <= delta_F.
```

No independence, exchangeability, common null, or common estimand appears in the proof. QED.

The repository’s public style may express this as conditioning on maintained assumptions:

```text
P(any reached member falsely promotes in family F
  | named maintained assumptions) <= delta_F.
```

The model-class statement above clarifies that the assumptions are theorem premises, not a
probability claim that the assumptions themselves are true.

### 4.3 Corollary — current three-scope bound

At the pinned baseline, every ordinary problem scope is bound only by the registry top-level
`delta`. Taking `alpha_1 = alpha_2 = alpha_3 = delta` gives:

```text
P(false first promotion in the exact three-slot family
  | joint local maintained assumptions) <= min(1, 3 * delta).
```

At `delta = 1/100`, the bound is `3/100`. The `min(1, ...)` is needed for general `delta`; the live
instance is below one.

This is the strongest generic statement available from the current owner semantics. It is not a
recommendation to advertise `3/100`; the current probabilistic path is largely refused and the
family protocol remains operationally blocked. It is the arithmetic upper bound that prevents a
false `1/100` implication.

### 4.4 Impossibility result — no stronger generic bound from local bounds alone

The disjoint-event construction in §2.4 satisfies every local `delta` statement and attains
`3 * delta`. Therefore no procedure that observes only the three local upper bounds can prove a
smaller universal family bound. A smaller bound requires at least one additional truth-bearing
property, such as:

- smaller owner-enforced local caps;
- a verified dependence/model relation;
- valid family p-values with a family testing procedure;
- conditionally valid e-values and a merger targeted to the family event; or
- a different exact theorem supplied and verified by the canonical owner.

Precommitment of names and order is necessary governance but not one of those mathematical
properties.

### 4.5 Design pattern — capped canonical scopes

A compatible fixed-family composition has four layers:

1. **Canonical scope layer.** N9 continues deriving one scope from each exact problem binding.
   Scope IDs remain pairwise distinct.
2. **Prospective family allocation.** Before any result-bearing execution, an exact family
   declaration binds member order, problem hashes, expected canonical scope IDs, family `delta_F`,
   and local caps `alpha_i` with exact sum at most `delta_F`.
3. **Local enforcement.** The confidence ledger constrains member scope `i` to an effective
   top-level ceiling no greater than `alpha_i` before owner execution. Its existing Basel-square
   schedule then allocates over local ordinals and obligation weights inside that ceiling.
4. **Family projection.** The confidence ledger recomputes the family result from the declaration,
   live scope derivation, canonical roots/current-head receipts, terminal chronology, and source
   identities. INT-R9 consumes the projection.

This does not require one family scope. The composition object is a relation over scopes, just as a
verified aggregate can relate several owner receipts without owning their local event histories.

For equal allocation:

```text
delta_F = 1/100
alpha_1 = alpha_2 = alpha_3 = 1/300
sum alpha_i = 1/100.
```

For weighted allocation, choose prospective exact weights `w_i >= 0`, `sum w_i <= 1`, and set
`alpha_i = w_i * delta_F`. The theorem is unchanged. Choosing weights after seeing outcomes is
invalid.

### 4.6 Governance protocol — terminal effects and no bypass

A cap vector closes the audit only if terminal states cannot be used to mint a new unaccounted
budget.

| Earlier member terminal | Family effect | Cap effect |
| --- | --- | --- |
| Preflight refusal before result-bearing owner execution | Retain and publish; advance only if protocol allows. | Actual spend may be zero, but the assigned cap is retired for this family version. |
| Prospectively defined infrastructure failure proved before any result-bearing execution | Retry may occur only as the same member, same scope, same cap. | No new cap or scope; no advancement by relabeling. |
| Owner refusal/error after start | Retain as result-bearing terminal. | Reserved spend is burned; unused member cap is retired. |
| Result-bearing void | Retain in chronology; no substitution. | Spend remains; unused cap is retired. |
| Dispute | Halt until prospectively resolved. | No cap is made available to a later scope. |
| Completed negative / grounded refusal | Advance to the next exact member. | Unused cap is retired. |
| Valid positive | Stop permanently. | Its spend remains charged; later caps expire unused. |
| Unreached after positive | Record as unreached. | Assigned cap expires unused. |

No-refund is a conservative governance protocol, not a theorem that recycling is impossible. A
prospective recycling rule could be valid with its own owner proof. The current repository has no
such proof, so recycling cannot be implied.

### 4.7 Theorem 2 — adaptive continuation under conditional validity

Let `H_{i-1}` be the complete history before member `i`, including all earlier inputs, outputs,
terminal reasons, adjudication, source changes, implementation/model/prompt/config changes, and
repair decisions. Let reachability `R_i` and cap `alpha_i` be measurable before member `i`’s
result. Caps may depend on history if they are predictable, nonnegative, and satisfy the **pathwise**
constraint:

```text
sum_i alpha_i(H_{i-1}) <= delta_F
```

for every allowed history.

Suppose that, whenever member `i` is reached, the selected implementation’s local theorem gives:

```text
P(P_i ∩ W_i | H_{i-1}, R_i) <= alpha_i(H_{i-1})
almost surely.
```

Then:

```text
P(V_F) <= delta_F.
```

**Proof.** Because `R_i` is determined by prior history,

```text
P(V_i)
  = E[1_{R_i} * P(P_i ∩ W_i | H_{i-1}, R_i)]
  <= E[1_{R_i} * alpha_i(H_{i-1})].
```

Summing and using the union inequality:

```text
P(V_F)
  <= sum_i P(V_i)
  <= E[sum_i 1_{R_i} * alpha_i(H_{i-1})]
  <= E[sum_i alpha_i(H_{i-1})]
  <= delta_F.
```

QED.

An equivalent uniform local theorem over every implementation selectable by the repair policy is
also sufficient. The proof does not require that later implementations equal earlier ones; it
requires the local guarantee to remain valid for the actual adaptive selector and history.

### 4.8 Adaptive result at the pinned baseline

INT-R9’s §4.6 permits general implementation repair after an earlier refused or void member
(`int-r9-first-promotion-evaluation-protocol.md:600-650`). The current confidence ledger records a
filtration reference for checks and supports anytime-valid profile metadata, but it does not own a
cross-scope theorem proving that a repaired implementation selected from prior family outcomes
satisfies Theorem 2. Registry profiles for owner-verified confidence sequences, e-values,
e-processes, and sequential tests are explicitly unavailable
(`confidence_ledger.toml:53-121`).

Therefore:

- **fixed implementation family:** mathematically composable after local caps and family
  recomputation are implemented;
- **adaptive implementation family:** numeric composition remains blocked until a verified
  history-conditional or uniform theorem exists;
- **adaptive governance without numeric theorem:** may still run as candidate/development work if
  public language omits the family probability bound and preserves all limitations.

The audit’s distinction between “general” and “case-specific” repair is also a governance problem:
classification after seeing a favorable later result can itself be selective. A future adaptive
protocol must decide repair admissibility at a prospectively governed time, from specified evidence,
with a conflict rule and a fail-closed consequence. Even that governance does not replace the
conditional statistical theorem.

### 4.9 E-value disposition

E-values are neither rejected nor appointed as the family mechanism.

- A local e-process can provide optional-stopping validity inside one scope if its owner theorem is
  real.
- Sequential products can be e-valid if every factor is conditionally valid given prior history.
- Multiple-testing procedures over e-values can control specified error criteria under their own
  assumptions.

But the current family target is a union of false authority promotions across distinct problem
truth configurations. Multiplying three unrelated e-values does not automatically provide strong
family-wise protection for that event. The family target, local nulls, merger theorem, filtration,
and truth configurations would all need canonical definition and verification. The live registry
currently refuses the relevant owner theorem, so e-values are a deferred instrument option, not a
closure claim.

### 4.10 What may honestly be claimed

#### At the pinned baseline

INT-R9 may say:

> The three precommitted design problems use three distinct canonical non-resettable confidence
> scopes. Subject to each scope’s declared obligation set and maintained assumptions, the current
> generic upper bound on any false first promotion across the exact three-member family is
> `min(1, 3 * delta)`. The repository does not implement a canonical single-`delta` family
> composition, and no numeric bound is established for outcome-dependent implementation repair.

It may **not** say:

- “all slots share one cumulative `delta`”;
- “the first promotion has false-promotion probability at most `delta`”;
- “Basel-square automatically spans the queue”;
- “precommitment removes multiplicity”;
- “e-values make the scopes composable”; or
- “general repair is covered by optional stopping.”

#### After a fixed-family canonical owner extension

If the confidence ledger enforces prospective caps, verifies their exact total, and recomputes the
family projection over live member artifacts, INT-R9 may say:

> For exact family `F`, exact member scope IDs `S`, exact cap vector `alpha`, fixed implementation
> revision `R`, registry and theorem profile `G`, declared obligation bases `O`, validator and
> family maintained assumptions `A`, and stop-on-first-canonical-positive rule `T`, the canonical
> confidence-ledger composition proves
> `P(any reached member falsely promotes | A) <= delta_F`.

The claim must name or link the exact family receipt and retain INT-R1’s open-world rider.

#### After adaptive repair

The same numeric sentence is allowed only if the receipt also binds a verified canonical theorem
satisfying Theorem 2 for the permitted repair selector. Otherwise INT-R9 may describe a
prospectively governed adaptive development sequence but must omit a family numeric guarantee.

### 4.11 Why this is not a second ledger

The family projection has no independent local checks, risk burns, ordinals, owner routes, or
mutable head. It consumes the existing ledger’s exact scope roots and current-head receipts,
recomputes the prospective cap relation, and emits one bounded projection. The confidence ledger
remains the sole owner of the arithmetic and local evidence. This is analogous to an owner-provided
aggregate projection, not a peer authority.

A proposed “family scope” that receives its own `ConfidenceRiskBudgetScope`, then contains or
reprices the problem scopes, would create two risk identities for the same protected claim and
would fail P27/P28. A family ID may identify the declaration/union event, but it cannot replace the
member scope IDs or become another execution budget root.

### 4.12 Audit R1 acceptance criteria

| Requirement | INT-R10 answer |
| --- | --- |
| 1. Exact family event | `V_F = union_i(R_i ∩ P_i ∩ W_i)`: any reached member in the stop-on-first-positive family falsely promotes. |
| 2. Relation to canonical scopes | Every member binds one live N9 problem binding and its recomputed, distinct canonical scope ID; no collapse or replacement. |
| 3. No fresh unaccounted budgets | A valid future composition requires prospective local caps whose exact sum is at most `delta_F` and which bind before owner execution. Current source fails this requirement. |
| 4. Earlier terminal effects | Refusal, void, dispute, negative, positive, and unreached semantics are explicit; no default refund, substitution, or new scope. |
| 5. Aggregate proof | Theorem 1 proves weighted-union composition; the disjoint-event witness proves the current `3 * delta` result is sharp. |
| 6. Adaptive continuation | Theorem 2 states the exact predictable-allocation and history-conditional/uniform validity requirements. Current adaptive repair claim is withdrawn/blocked. |
| 7. Canonical owner reuse | The confidence ledger is extended through a projection; no second ledger, parent risk scope, or duplicate owner is proposed. |
| 8. Live reproducibility | The artifact/fixture sketch requires recomputation from live scope derivation, family declaration, roots, current-head receipts, cap enforcement, source identity, and chronology. Author-written records fail. |

The mandatory falsifier is **not blocked at the pinned baseline**. This research says so plainly.
It specifies the exact canonical extension and negative fixture that would have to block it before
a single-`delta` claim becomes eligible.

---

## 5. Counterexamples And Failure Modes

### 5.1 F1 — three compliant fresh budgets

```text
A -> scope A -> root delta
B -> scope B -> root delta
C -> scope C -> root delta
stop on first positive
```

Everything is canonical locally. The family receives three local guarantees. Without a family cap,
`delta_F = delta` is false; the generic bound is `3 * delta`.

**Diagnostic:** derive every scope from live N9 and sum its top-level admitted family cap, not its
slot number or author-written “cumulative” label.

### 5.2 F2 — sharp disjoint errors

Three disjoint false-promotion events each have probability `delta`. Local checks are perfectly
valid, yet the family error is `3 * delta`.

**Diagnostic:** ask which verified dependence premise rules out disjoint errors. If none, a tighter
bound is unsupported.

### 5.3 F3 — collapse three problems into one scope

An implementation changes all member keys to one family key so the current within-scope Basel
schedule supplies one budget.

**Failure:** this weakens canonical problem identity, mixes unrelated owner histories, creates a
wrong replay/audit unit, and contradicts the explicit “only N11 scope for one N9 problem binding.”
It fixes arithmetic by corrupting ownership.

**Required result:** reject scope mismatch; preserve three scope IDs.

### 5.4 F4 — family scope as a parent budget owner

A new `ConfidenceRiskBudgetScope` is created for the family, with member scopes nested beneath it,
while local roots continue to exist.

**Failure:** two budget identities and two potential mutable histories now govern one family claim.
Unless the existing ledger itself defines this as one internal projection with no duplicate owner,
it is P27/P28.

**Required result:** family ID is a declaration/projection identity, never a replacement risk scope.

### 5.5 F5 — post-outcome equalization

Slot 1 fails. The protocol reduces its recorded cap and reallocates the difference to slot 2 while
keeping the final sum at `delta_F`.

**Failure:** the allocation was selected using result-bearing information. The final arithmetic is
correct but the theorem premise is false.

**Required result:** `allocation_not_prospective` or equivalent.

### 5.6 F6 — refund after refusal or void

A refused slot spent little or zero, so the protocol gives its unused amount to a new problem scope.

**Failure:** absent a prospective recycling theorem, opening the next scope can search repeatedly
while presenting only one nominal total. The audit’s bypass remains.

**Required result:** assigned cap retires; retry before result exposure stays in the same member,
scope, and cap.

### 5.7 F7 — adaptive repair under a fixed theorem

After seeing failure class `X` in slot 1, developers choose implementation `R_X` for slot 2. The
local certificate for `R_X` was valid only when `R_X` was fixed independently of slot-1 output.

**Failure:** local validity does not hold for the selector. This is not repaired by exact cap sums.

**Required result:** `adaptive_validity_unproved`; no numeric family claim.

### 5.8 F8 — “anytime-valid” as universal permission

A later scope uses an e-process, so the protocol declares every prior repair and scope choice safe.

**Failure:** optional stopping within a valid process is not post hoc choice among processes. The
actual filtration and conditional construction must cover the selection.

**Required result:** verify the owner theorem against the full history and repair policy.

### 5.9 F9 — e-value product targets the wrong event

Three e-values for three local nulls are multiplied, and the product is labeled the probability
that any false promotion occurred.

**Failure:** product e-validity needs conditional/independence premises and a defined joint null;
FWER for a union across arbitrary truth configurations is a different target.

**Required result:** refuse without a registered family theorem and verifier.

### 5.10 F10 — author-written family receipt

INT-R9 stores `within_family_budget: true` and three scope IDs but no canonical verifier opens the
scope roots or heads.

**Failure:** markers restate the claim. They do not prove cap enforcement, currentness, or complete
member history; this is P29/P32.

**Required result:** corrupt a real member head/cap while retaining markers; validation must turn
red.

### 5.11 F11 — obligation conditionality disappears

The cap arithmetic is valid, but public text says `P(false first promotion) <= delta_F` without
naming the declared obligation bases and validator-soundness premise.

**Failure:** family composition controls only errors relative to the local theorem inputs. It does
not bound an unknown obligation outside the basis. This silently reverses INT-R1.

**Required result:** family projection refuses missing/mismatched member conditionality.

### 5.12 F12 — strictness leaks into the candidate band

Because family composition is absent, the system prohibits all generation, analysis, or candidate
repair across multiple problems.

**Failure:** S0-K06 binds the affected authority action, not candidate computation. The correct
reaction is to block the numeric family claim and carry a typed limitation, not disable learning.

### 5.13 F13 — learned weights from nonexistent history

The protocol claims slot 1 is safer and gives it a larger cap based on “observed promotion rates,”
but no governed positive history exists.

**Failure:** the weighting rationale is fabricated. Prospective policy weights may be chosen for
resource or consequence reasons, but must be labeled governance choices, not calibrated risks.

### 5.14 Pattern pass

| Pattern | Risk in this task | Correct pattern |
| --- | --- | --- |
| P27 owner-bypass duplication | Family scope/ledger beside N11 | Confidence-ledger-owned projection over unchanged scopes. |
| P28 unstrangled legacy | INT-R9 prose path remains able to assert cumulative delta | Consumer must require the canonical family receipt or publish the narrower bound/no bound. |
| P29 authorial proof | Markdown/YAML boolean accepted as closure | Live recomputation plus property-removal negative control. |
| P31 instance patch | Special-case only INT-R9’s three slots | Generic exact family relation over any finite/predictable sequence. |
| P32 trust by form | IDs/fields present but caps not enforced | Execute real scope derivation, root, reservation, and head validation. |
| P33 teaching to test | Validator rejects only literal A/B/C trace | Generate scope substitutions, cap refunds, stale heads, fourth scope, and adaptive repair. |

---

## 6. Benchmark Or Fixture Proposal

The complete executable specification is in
[int-r10/fixture-and-artifact-sketch.md](int-r10/fixture-and-artifact-sketch.md). No test is added by
this research branch.

### 6.1 Fixture identity and fixed inputs

```yaml
fixture_id: INT-R10-FWC-001
baseline_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
family_delta: {numerator: 1, denominator: 100}
family_size: 3
stopping_rule: stop_on_first_canonical_positive
revision_policy: fixed_revision_only
members:
  - {order: 1, design_problem_id: FWC-A, local_cap: 1/300}
  - {order: 2, design_problem_id: FWC-B, local_cap: 1/300}
  - {order: 3, design_problem_id: FWC-C, local_cap: 1/300}
```

Problem contents, hashes, owner fixtures, and expected scope IDs must be deterministically generated
from committed inputs. Expected IDs must not be fed into the implementation under test.

### 6.2 Positive future-conformance trace

```text
slot 1 -> problem A -> canonical scope A -> local ordinal 0 -> refused/negative
slot 2 -> problem B -> canonical scope B -> local ordinal 0 -> result-bearing void/negative
slot 3 -> problem C -> canonical scope C -> local ordinal 0 -> positive
stop
```

Required assertions:

1. live N9 derivation produces three distinct scope IDs;
2. all three local ordinal-zero starts remain valid—the fixture does not force one ordinal stream;
3. each scope is constrained to `1/300` **before** any probabilistic owner call;
4. existing within-scope allocation runs inside that cap and refuses a reservation exceeding it;
5. exact cap sum is `1/100` using `Fraction`-equivalent arithmetic;
6. slot 1 and slot 2 terminals remain in the family projection;
7. no cap is refunded or transferred;
8. the first positive comes from the registered third scope and stops the family;
9. the confidence ledger recomputes the family projection from live source, roots, current heads,
   receipts, and chronology;
10. public conditionality names every member’s obligation/validator premises and family premises;
11. a second recomputation is semantically identical; and
12. corrupting a cap, scope binding, earlier terminal, or head makes validation fail.

The current baseline is expected to refuse this positive control as
`family_composition_unavailable`; that is not a fixture failure.

### 6.3 Mandatory negative control

Run the exact audit falsifier with the ordinary live registry:

```text
scope A -> top-level 1/100
scope B -> top-level 1/100
scope C -> top-level 1/100
```

At the pinned baseline the fixture must demonstrate:

- distinct live scope IDs;
- independent local ordinal-zero histories;
- root `budget_delta = 1/100` for each;
- no cross-scope cap or composition receipt; and
- aggregate admitted top-level family allocation `3/100` if all three are counted.

After a future extension, the same trace must go red before any family claim with one of these
semantics or an equivalent:

```text
family_declaration_missing
family_member_cap_missing
family_budget_exceeded: allocated=3/100, declared=1/100
```

A prose flag from INT-R9 must not override the result.

### 6.4 Required negative/metamorphic set

The implementer must also cover:

- refunding cap after refusal;
- omitting an earlier void/refusal;
- substituting a fourth problem after failure;
- swapping supplied scope IDs while preserving field shape;
- duplicate problem/scope identities;
- changing cap weights after an outcome while preserving final sum;
- adaptive repair without a conditional/uniform theorem;
- hand-authored green receipt without live heads;
- stale member receipt when a newer head exists;
- missing one member’s maintained assumptions;
- decimal-rounding overspend hidden by display strings;
- unregistered e-value multiplication;
- positive from an unregistered fourth scope; and
- collapsing distinct problems to one scope.

The property-removal control is mandatory: remove local-cap enforcement from the real owner path
while keeping every schema field and marker. The validator must fail. Otherwise it is form-based.

### 6.5 Theorem fixture

A deterministic mathematical test constructs three disjoint events of probability `1/100` and
asserts their union is `3/100`. This prevents future reviewers from treating the factor three as
merely a cautious approximation.

### 6.6 Adaptive fixture

Slot 1’s failure selects a repaired implementation for slot 2. Cap arithmetic remains valid, but
the supplied local theorem covers only an implementation fixed independently of slot 1. The
family projection must refuse `adaptive_validity_unproved`. A paired positive control differs only
by supplying a canonical theorem whose verifier covers the selector and full history.

### 6.7 Fixture authority boundary

The fixture is authoritative only for the observable composition property it samples. It may not
be used for production readiness, open-world obligation completeness, validator soundness,
population performance, or proof that a real positive promotion exists.

---

## 7. Artifact Contract Sketch

The full non-normative shapes and recomputation pseudocode are in
[int-r10/fixture-and-artifact-sketch.md](int-r10/fixture-and-artifact-sketch.md). Two semantic
objects are sufficient for research handoff.

### 7.1 `FamilyRiskCompositionDeclaration` — placeholder

Purpose: prospectively bind the exact union event and local cap vector before any result-bearing
member execution.

Minimum semantic fields:

- schema and theorem-profile versions;
- content-derived family ID;
- family purpose and confidence-ledger owner reference;
- exact consumer protocol and repository/deployment/registry references;
- exact rational `family_delta`;
- exact ordered members with slot ID, design-problem ID, problem content hash, recomputed canonical
  scope ID, and exact local cap;
- stopping/dispute/no-substitution rule;
- fixed or adaptive revision policy;
- adaptive theorem reference when applicable;
- local and family maintained assumptions;
- exact controlled event;
- commitment/transaction evidence preceding result-bearing execution; and
- `authoritative_for`, `may_not_use_for`, `research_only` boundaries.

**Authoritative for:** declaring a proposed exact family and cap vector for canonical verification.

**May not use for:** proving local certificates, proving the aggregate bound, promotion authority,
production capability, changing scope identity, or creating a second ledger.

### 7.2 `FamilyRiskCompositionReceipt` — placeholder

Purpose: canonical confidence-ledger recomputation of the family relation over live member roots
and current-head receipts.

Minimum semantic fields:

- declaration/family identity and content reference;
- family `delta`, theorem profile, source/deployment/registry identity;
- revision-policy result;
- each member’s exact canonical scope, local cap, root/receipt/head references, local total spend,
  terminal, and cap disposition;
- exact aggregate cap and violation counts;
- canonical-scope, current-head, chronology, no-refund, and no-unregistered-positive results;
- full conditionality and maintained assumptions;
- eligibility/refusal state; and
- recomputed projection hash.

**Authoritative for:** the canonical owner’s recomputation that the named family cap relation holds
over the bound live artifacts.

**May not use for:** open-world completeness, validator truth, external validity, legal compliance,
institutional competence, production readiness, or any family/revision/assumption outside the
receipt.

### 7.3 Anti-duplication constraints

Neither object may own:

- a second mutable event head;
- local confidence checks or owner invocation;
- a second execution ordinal;
- an independent registry or budget delta;
- a replacement `ConfidenceRiskBudgetScope`;
- a second promotion decision; or
- a boolean trusted without recomputation.

The declaration is an admitted prospective constraint. The receipt is a projection from the
canonical ledger. Local roots and receipts remain authoritative for local accounting.

### 7.4 Required local-cap observable

A later implementation must expose evidence that the local cap constrained the scope before the
first probabilistic `started` event. After-the-fact `total_spend <= cap` is not sufficient by
itself because the local owner may have executed under a larger threshold. Acceptable internal
architectures are left open, but the observable property is fixed:

```text
before owner execution:
  effective local ceiling <= assigned family cap
  prior local spend + next reservation <= effective local ceiling
```

The within-scope Basel kernel then remains the allocation mechanism inside that ceiling.

---

## 8. Later Integration Handoff

### 8.1 Canonical owner to extend

**Owner:** `polisyos.runtime.quality.confidence_ledger` / the N11 confidence-ledger lane.

The extension is cross-scope composition over existing roots. It is not owned by INT-R9, N9, an
Atlas surface, or a new family service. The repository itself already records GY-GAP2 in the
confidence-ledger lane
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).

### 8.2 Minimum integration properties

A later implementation/consolidation sequence must deliver, in owner-first order:

1. an admitted prospective family declaration or semantically equivalent owner input;
2. exact local-cap enforcement before probabilistic execution while preserving scope ID;
3. existing Basel-square allocation evaluated inside the local cap;
4. exact rational aggregate verification;
5. live canonical scope derivation for every member;
6. current-root/current-head receipt verification for every member;
7. terminal chronology and no-refund/no-substitution verification;
8. fixed-revision eligibility and adaptive-theorem refusal/verification;
9. one recomputed family projection consumed by INT-R9; and
10. behavioral positive, mandatory negative, adaptive negative, and property-removal fixtures.

No package, field spelling, or storage layout is ratified here.

### 8.3 INT-R9 handoff

INT-R9 must amend every “one cumulative scope/budget” sentence to one of three positions.

| Execution mode | What INT-R9 may claim |
| --- | --- |
| Current baseline, three ordinary scopes | Generic family bound `min(1, 3 * delta)` under joint local assumptions; no implemented family receipt; no adaptive numeric theorem. |
| Future fixed implementation, ledger-owned caps and receipt | `P(any reached member falsely promotes in exact family F | named assumptions) <= delta_F`, with exact member scopes/caps/revisions/receipt. |
| Adaptive repair | Same numeric claim only with a verified history-conditional or uniform owner theorem; otherwise governance claim only, no family probability. |

A family receipt does not make a positive result exist. Refusal, dispute, void, and exhaustion remain
valid protocol outcomes.

### 8.4 INT-R1 handoff

Each member must bind its own exact `ObligationSetDeclaration` or consolidation-approved
successor. The family projection must preserve member-specific closure basis, cutoff, compiler/
validator versions, and open-world remainder. It may summarize compatible assumptions but may not
replace them with one bare family boolean.

A later-discovered obligation or validator defect can invalidate a member’s current authority and
therefore the family claim’s current standing. Correction must append and reissue; the historical
receipt remains evidence of what was proved under its actual premises, not eternal authority.

### 8.5 Public projection handoff

Any public surface must display at least:

- exact family identity and member count;
- fixed versus adaptive revision posture;
- family `delta_F` and cap profile reference;
- canonical family receipt reference and currentness;
- obligation/validator conditionality;
- first positive, exhausted, disputed, or blocked terminal;
- scope of authority and external-validity limits; and
- correction/suspension status.

The surface must not translate `accepted_narrow_scope` research into implemented capability or
compress “relative to declared obligation sets” into “all obligations.”

### 8.6 Reuse map

| Existing owner asset | Reuse | Extension needed |
| --- | --- | --- |
| `ConfidenceRiskBudgetScope` | Preserve unchanged per problem. | None to identity. |
| Exact `RationalSpec` / `Fraction` path | Reuse for caps and totals. | Family exact-sum projection. |
| Registry and theorem profiles | Reuse as source of local theorem eligibility. | Family theorem profile/refusal route, if ratified. |
| Basel-square schedule | Reuse inside each local cap. | Bind effective local ceiling before schedule allocation. |
| Immutable root/event/current-head receipt | Reuse as member evidence. | Cross-scope recomputed projection. |
| Deployment/registry/schedule hashes | Reuse for reproducibility. | Bind all members and family declaration together. |
| Conditionality clause / maintained assumptions | Reuse per member. | Preserve and reconcile in family projection. |
| N9 scope derivation | Reuse live, never copy IDs. | Family membership verifier calls/recomputes it. |
| INT-R9 queue chronology | Consume as governance evidence. | Canonical bridge from protocol artifacts to family projection. |

---

## 9. Promotion And Kill Rules

### 9.1 Research promotion rule

This research result may be consolidated as `accepted_narrow_scope` only with both halves intact:

- weighted-union composition is a valid theorem under exact prospective owner-enforced caps; and
- the current repository does not implement those caps or an adaptive theorem, so INT-R9’s
  single-`delta` claim remains blocked.

Consolidation that adopts the theorem while deleting the blocked capability statement would turn a
conditional design result into a false current claim.

### 9.2 Conditions before implementation authorization can even be considered

A separate implementation task must have:

1. a ratified semantic owner handoff naming the confidence ledger, not a new service;
2. a decision whether the decisive INT-R9 family is fixed-revision or adaptive;
3. a local-cap enforcement design reviewed against scope identity and replay semantics;
4. a declared family event and theorem profile;
5. INT-R1 member obligation interfaces;
6. a live-source recomputation design;
7. terminal/no-refund semantics;
8. a public correction/suspension path; and
9. the fixtures in §6 as acceptance criteria.

This document supplies research inputs, not authorization.

### 9.3 Kill rules

Any proposed consolidation or implementation is **NO-GO** if it does any of the following:

- weakens `design-problem:<design_problem_id>` scope identity;
- resets or reuses a per-problem scope to obtain fresh budget;
- creates a second confidence ledger, parent risk scope, independent head, or duplicate theorem
  owner;
- asserts a family cap only in INT-R9 prose or a hand-authored record;
- checks caps after result-bearing execution instead of enforcing them before owner calls;
- uses floats or rounded display decimals in budget authority;
- permits outcome-dependent cap changes, refunds, substitution, or a fourth scope without a
  prospective verified theorem;
- treats an earlier refusal/void/dispute as absent from chronology;
- imports Holm, Šidák, clinical boundaries, or e-value products without the required statistical
  objects and assumptions;
- claims adaptive validity from a fixed implementation theorem;
- hides INT-R1’s obligation/validator conditionality;
- accepts stale member heads or supplied scope IDs without live recomputation;
- lets a marker-only validator pass after local-cap enforcement is removed;
- converts the family result into population performance, legal compliance, or production
  readiness; or
- blocks candidate exploration merely because authority-band family composition is absent.

### 9.4 Evidence required to close GY-GAP2

GY-GAP2 is not closed by a schema or unit test. Closure requires the full chain:

```text
prospective family declaration
-> canonical member-scope derivation
-> pre-execution local-cap enforcement
-> local owner checks and immutable receipts
-> exact aggregate recomputation
-> consumer chronology verification
-> family projection
-> INT-R9 consumption/public bounded claim
-> mandatory negative and adaptive falsifiers
```

Missing producer, bridge, consumer, verifier, or behavioral fixture must be labeled precisely
rather than called complete.

### 9.5 Benchmark passage rule

Even after implementation, passing the INT-R10 fixture proves only the family-composition property
for the named revision and test artifacts. It does not prove that any real owner certificate is
statistically sound, that obligation bases are externally complete, that a real positive exists,
or that the system is ready for production. S0-K16 remains controlling.

---

## 10. Open Questions For Consolidation

1. **Fixed or adaptive decisive sequence.** Will INT-R9 freeze one implementation across the three
   decisive members, or retain repair? Fixed revision gives the earliest defensible numeric path;
   adaptive repair requires a materially stronger owner theorem and governance classifier.
2. **Local-cap representation.** What owner-internal mechanism constrains a scope to `alpha_i`
   before execution while preserving its canonical `scope_id`, root semantics, replay, and
   deployment binding? This research fixes the observable property, not the field layout.
3. **Family commitment time.** Which existing custody mechanism proves that membership, order,
   cap vector, and revision policy were independently visible before every result-bearing
   execution? INT-R10 needs the property but does not duplicate S0-GAP-02’s commitment owner.
4. **Finite versus online families.** Should the first implementation support only an exact finite
   family, or a predictable unbounded allocation stream with pathwise total at most `delta_F`?
   The theorem supports both; the narrower finite path is easier to audit.
5. **Weight selection.** Are equal thirds acceptable governance, or should weights reflect
   prospectively declared consequence/materiality differences? No empirical weighting is
   currently available.
6. **Cap recycling.** Is conservative no-refund sufficient, or is there a real need for prospective
   recycling? Any recycling proposal needs a canonical theorem and additional adversarial tests.
7. **Adaptive theorem owner.** Which local proof profiles could establish validity conditional on
   prior family history and implementation selection? The current `owner_theorem_unavailable_v1`
   posture is honest and may remain the answer.
8. **Member obligation compatibility.** How should the family projection expose different
   obligation bases, cutoffs, validators, and unresolved remainders without manufacturing one
   universal family obligation set?
9. **Instance identity.** INT-R1’s audit records a separate obligation-instance identity gap. Does
   family verification need to bind instance-level obligation declarations before it can claim
   member assumptions are complete enough for composition? This must be coordinated, not solved by
   adding another denominator here.
10. **Dispute resolution and cap standing.** When a disputed earlier member is later corrected,
    does the same family version resume, or must a new family declaration/version be issued? The
    no-rewrite custody rule favors append and explicit reissue.
11. **Currentness and perturbation.** Which change classes—registry, theorem profile, source,
    validator, problem content, implementation, evaluator, obligation basis—suspend the family
    claim, and which require a full new family version?
12. **Public wording.** What minimum surface text prevents `delta_F` from being read as a world-wide
    probability of policy harm or missed obligation?
13. **E-value future path.** If real owner-verified e-processes arrive, is the desired object still
    strong FWER over false authority promotion, or a different global-null/evidence claim? The
    target must be chosen before a merger.
14. **Holm or closed testing.** If future scopes expose valid p-values for compatible local nulls,
    is a step-down family procedure worth the complexity, or is weighted union preferable for
    transparency and heterogeneous authority semantics?
15. **Dependency evidence.** What evidence would be competent to justify any stronger-than-union
    dependence correction across design problems? The current answer is none.
16. **Correction of INT-R9.** Consolidation must decide whether to amend INT-R9 immediately to the
    current `3 * delta`/no-adaptive-bound position or keep it fully blocked until a ledger extension
    exists. It must not retain the single-`delta` implication.

The open questions do not weaken the central answer. **Today, three ordinary problem scopes mean
three local top-level budgets and at most `3 * delta` generically. A future single-`delta_F` family
claim is mathematically available only through prospective local caps enforced and recomputed by
the canonical confidence ledger. Adaptive repair additionally requires a history-conditional or
uniform owner theorem.**
---
title: INT-R10 — Independent Adversarial Audit
status: delivered
kind: independent-audit
research_task: INT-R10
audit_verdict: NO_GO
repository: https://github.com/DenisKopylov/polisyos
audited_branch: research/int-r10-family-wise-risk-composition
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
research_only: true
authoritative_for:
  - independent adversarial audit of the INT-R10 mathematical research package at the exact audited commit
  - verdict on Theorem A, sharpness/current-source composition, and Theorem B
  - verification of repository anchors, external transfers, R1 conformance, fixtures, artifacts, standing, and supplied orientation
  - identification of INT-R10 conclusions safe for immediate use by the parallel INT-R9 amendment
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - replacement family-composition theorem
  - assertion that a live cross-scope family projection exists
  - permission to merge or consolidate the audited research without amendment and independent re-verification
---

# INT-R10 — Independent Adversarial Audit

## Executive verdict

**Verdict: `NO_GO`.**

INT-R10 contains a correct and valuable fixed-family theorem:

> If each reached member has a valid local false-promotion bound under the same named assumptions,
> the local cap is bound before execution, and the prospective caps sum to at most `delta_F`, then
> the union of reached-member false-promotion events is bounded by `delta_F`.

That theorem needs no common null, common estimand, exchangeability, or independence. The exact
family event, INT-R1 conditionality, canonical-owner boundary, and current block on adaptive repair
are all strong.

The deliverable nevertheless fails at its load-bearing canonical-source application. It treats each
scope's root-level `budget_delta` as if a member-level false-promotion event could attain that whole
amount, declares `3 * delta` sharp, instantiates `3/100`, and designs equal `1/300` effective caps
around that premise. The pinned owner exposes stronger information that the report cites but does
not compose:

```text
alpha_t
  = delta
    * expanded_obligation_class_weight(q_t)
    * schedule_mass
    * (76614/126025)
    / (t+1)^2,
```

with one global executed-check ordinal per scope, schedule mass at most one, and maximum live class
weight `3/20`. Therefore every path through one pinned mass-one scope has total scheduled
probabilistic risk strictly below `(3/20) * delta`; three such scopes are strictly below
`(9/20) * delta`. The disjoint events of probability `delta` used as the sharpness witness do not
satisfy those canonical source premises.

This audit does **not** turn that counter-bound into a production family capability. The repository
still has no canonical family declaration, chronology verifier, current-head aggregate projection,
or public owner statement. GY-GAP2 remains real. The finding is that INT-R10's claimed
impossibility, sharpness, `3/100` fixture oracle, and equal-third remedy are not established by the
pinned owner.

The parallel INT-R9 amendment may rely now on the event definition, distinct scopes, absence of a
live family projection, current adaptive-theorem block, owner placement, and INT-R1 conditionality.
It must **not** rely on `3 * delta`, `3/100`, equal `1/300` caps, the present negative-control
probability oracle, or the claim that all eight R1 requirements are closed.

---

## 1. Audit object and scope discipline

GitHub comparison from baseline `978e6b958...` to audited head `317fc9c3...` confirms:

```text
status: ahead
commits: 11
behind: 0
files changed: 3
additions: 1,874
deletions: 0
```

The only changed paths are:

| Path | Status | Additions |
| --- | --- | ---: |
| `docs/research/policy-operations/int-r10-family-wise-risk-composition.md` | added | 1,014 |
| `docs/research/policy-operations/int-r10/fixture-and-artifact-sketch.md` | added | 614 |
| `docs/research/policy-operations/int-r10/source-and-transfer-ledger.md` | added | 246 |

No source file, test, or pre-existing document changed. The audited branch is based exactly on the
declared baseline. The report appoints no new owner, performs no code placement, and repeatedly
disclaims production authority.

Supporting audit files:

- [Formal argument audit](int-r10-formal-argument-audit.md)
- [Claim-evidence ledger](int-r10-claim-evidence-ledger.md)
- [Anchor and citation verification](int-r10-anchor-and-citation-verification.md)
- [Specification conformance](int-r10-specification-conformance.md)
- [Recommended revisions](int-r10-recommended-revision.md)
- [Orientation error ledger](int-r10-orientation-error-ledger.md)

---

## 2. Finding summary

| ID | Pass | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |
| INT-R10-A-001 | A | commendation | Fixed-family weighted-union theorem is correct. | Preserve. |
| INT-R10-A-002 | A | commendation | Dependence and INT-R1 conditionality are handled honestly. | Preserve. |
| INT-R10-B-001 | B | **blocking** | `3 * delta` is not sharp/strongest for the pinned canonical owner. | Re-derive exact source composition. |
| INT-R10-B-002 | B | commendation | Disjoint-event sharpness is valid after retaining only coarse marginal bounds. | Preserve with explicit qualifier. |
| INT-R10-C-001 | C | material | Theorem B omits filtered-space, cap/procedure measurability, and reach measurability. | Formal amendment. |
| INT-R10-C-002 | C | material | “Equivalent uniform/selection-aware theorem” is an unbounded escape clause. | Remove from proved disjunction. |
| INT-R10-C-003 | C | commendation | Pathwise fixed caps/no-refund are feasible and conservative. | Preserve. |
| INT-R10-C-004 | C | commendation | Qualitative adaptive boundary is correct. | Preserve after formal repair. |
| INT-R10-D-001 | D | commendation | External transfer ledger is substantially correct. | Preserve. |
| INT-R10-D-002 | D | minor | Sidak independence and Gaussian-rectangle conditions are conflated. | Split precisely. |
| INT-R10-D-003 | D | commendation | “E-values are not automatic” is the correct live-repository verdict. | Preserve. |
| INT-R10-E-001 | E | material | Self-graded R1 matrix conflates theorem, future criterion, and live capability. | Regrade independently. |
| INT-R10-E-002 | E | **blocking** | R1 requirement 5 fails on exact canonical source. | Block consolidation. |
| INT-R10-E-003 | E | commendation | Current adaptive numeric claim is honestly withdrawn. | Safe for INT-R9. |
| INT-R10-E-004 | E | commendation | R1 requirements 1, 2, 4, and 7 are strong at research level. | Preserve. |
| INT-R10-E-005 | E | commendation | Mandatory falsifier is honestly reported as unblocked today. | Preserve, fix arithmetic meaning. |
| INT-R10-E-006 | E | material | Positive live reproduction is still absent. | Treat as closure criterion, not capability. |
| INT-R10-F-001 | F | material | GY-GAP2 is cited through frontmatter/revision metadata 32 times. | Replace with `:2439-2463`. |
| INT-R10-F-002 | F | material | Burn-before-execution anchors end before durable append. | Extend source range. |
| INT-R10-F-003 | F | commendation | Other repository anchors are substantively adequate. | Preserve. |
| INT-R10-G-001 | G | **blocking** | Fixture's `allocated=3/100` probability oracle inherits the false sharpness premise. | Rebuild numeric oracle. |
| INT-R10-G-002 | G | material | The 614-line “sketch” has hardened into a de facto contract. | Demote replaceable schema/vocabulary. |
| INT-R10-G-003 | G | commendation | Fixture tests pre-execution enforcement and property-removal, and preserves one owner. | Preserve. |
| INT-R10-G-004 | G | commendation | Positive fixture honestly refuses at baseline. | Preserve. |
| INT-R10-H-001 | H | commendation | Diff and research-only scope discipline are exact. | Preserve. |
| INT-R10-H-002 | H | **blocking** | `accepted_narrow_scope` overstates a package with a false load-bearing source corollary. | Mark research blocked pending amendment. |
| INT-R10-H-003 | H | commendation | S0-K05, S0-K16, candidate-band, and INT-R1 boundaries are respected. | Preserve. |
| INT-R10-I-001 | I | **blocking** | Supplied orientation's `3 * delta` conclusion discarded exact schedule structure. | Correct orientation and dependent claims. |
| INT-R10-I-002 | I | minor | “Ordinal zero -> fresh delta” conflates root policy with reservation. | Use exact language. |
| INT-R10-I-003 | I | minor | Five proof profiles are not five instruments. | Add thirteen-instrument census. |
| INT-R10-I-004 | I | commendation | Remaining orientation facts are accurate. | Preserve. |

`INT-R10-B-001` is the decisive finding. `E-002`, `G-001`, `H-002`, and `I-001` are its
specification, fixture, standing, and orientation consequences rather than separate mathematical
counterexamples.

---

## 3. Pass A — Theorem A

### 3.1 Exact event

The report defines reached-member false promotion rather than testing every precommitted member
whether reached or not. This is correct:

```text
V_i = R_i ∩ P_i ∩ W_i
V_F = union_i V_i.
```

Under stop on first canonical positive, `V_F` equals false reported first promotion. Refusals,
voids, disputes, and negatives are not errors merely because they permit continuation.

### 3.2 Proof

Under the common maintained-assumption event `A_F`:

```text
P(V_F | A_F)
 <= sum_i P(V_i | A_F)
 <= sum_i alpha_i
 <= delta_F.
```

The proof is valid. The owner-enforced pre-execution cap is explicitly a premise. No dependence
condition enters the union inequality. Local statistical instruments may still have their own
filtration, model, null, or sampling assumptions; the report does not erase them.

### 3.3 Conditionality

The report consistently inherits:

```text
P(false promotion relative to declared obligations
  | obligation completeness and validator soundness) <= ...
```

It does not convert relative obligation coverage into world completeness. This is a commendable
continuation of INT-R1.

**Pass A verdict:** `GO` for Theorem A itself.

---

## 4. Pass B — sharpness and impossibility

### 4.1 Abstract witness

If all retained information is

```text
P(V_1) <= delta,
P(V_2) <= delta,
P(V_3) <= delta,
```

then three disjoint events of probability delta attain `3 * delta`. The reach/stopping semantics can
be embedded by assigning one disjoint outcome to each first false positive. That abstract
sharpness claim is valid.

### 4.2 Canonical-source witness failure

The pinned owner retains more information:

- `start_check()` uses one global local execution ordinal;
- each check has one obligation class;
- the class weight is expanded from a total pool partition;
- the maximum live class weight is `3/20`;
- schedule mass is at most one;
- exact reservation decays as `(t+1)^-2`; and
- the coefficient is a conservative lower bound for `6/pi^2`.

For any adaptive sequence of executed classes `q_t` in one scope:

```text
sum_t alpha_t
 <= delta * max_q w(q) * mass
    * (76614/126025) * sum_t 1/(t+1)^2
 < delta * 3/20.
```

This is a pathwise envelope: it does not rely on favorable dependence, realized low spend, or
post-outcome cap choice. Three scopes are strictly below `(9/20)delta` before any result is seen.

The report's witness `P(V_i)=delta` therefore violates the pinned schedule premise. Its theorem is
sharp only after intentionally coarsening the local owner to the sentence `P(V_i)<=delta`.

### 4.3 Consequence

The report cannot conclude from the pinned source that:

- `3delta` is strongest;
- live bound is `3/100`;
- current scopes require one-third effective caps; or
- GY-GAP2 is an arithmetic impossibility rather than a missing declaration/projection/reproduction
  capability.

The gap remains real. Its exact mathematical content must be restated.

**Pass B verdict:** `NO_GO`.

---

## 5. Pass C — adaptive continuation

### 5.1 What is correct

The report correctly distinguishes:

- a complete member-plan vector fixed before family outcomes; and
- a later implementation selected using earlier revealed outcomes.

It also correctly requires the local theorem to survive the actual selector/history. Predictable
allocation does not manufacture selection validity.

### 5.2 Missing formal premises

Theorem B needs an explicit filtration `mathcal H_{i-1}` and must state:

- `R_i` is `mathcal H_{i-1}`-measurable;
- the cap and selected procedure are `mathcal H_{i-1}`-measurable;
- the conditional-law convention under `A_F`; and
- the local almost-sure inequality under the actual selected procedure.

Only then does

```text
E[1_Ri E[1_(Pi∩Wi) | H_(i-1), A_F] | A_F]
```

justify the tower step. “Chosen before the result” is not a complete measurability statement.

### 5.3 Escape clause

“Or an equivalent uniform/selection-aware theorem” does not identify an equivalence relation,
controlled event, assumptions, or verifier. It may remain an open option, not a proved alternate
premise.

### 5.4 Current handoff

The current registry has no such owner theorem. INT-R10's practical conclusion—no numeric theorem
for INT-R9's outcome-dependent repair—is correct.

**Pass C verdict:** `GO_WITH_MATERIAL_REVISIONS` for the adaptive result; current blocked handoff is
safe.

---

## 6. Pass D — external transfers

All thirteen cited primary sources exist and materially support the attributed method family.

### 6.1 Correct transfers

- weighted union/Bonferroni: direct event accounting;
- Holm: future step-down option if valid p-values exist;
- online FWER: predictable bounded allocation, with stronger methods requiring dependence
  conditions;
- Pocock/O'Brien–Fleming/Lan–DeMets: aggregate-procedure and pre-allocation lesson only;
- confidence sequences/e-processes: validity relative to the actual filtration/process;
- e-value mergers: available under same-null averaging, independence, or sequential conditional
  validity as appropriate—not automatic across scopes;
- selective inference: selection changes meaning and must enter the controlled procedure; and
- empirical calibration: unavailable.

### 6.2 Sidak precision

The report should distinguish exact product control under independent tests from Sidak's 1967
multivariate-normal rectangle inequality. Its bottom-line non-transfer to arbitrary PolicyOS
problem events is correct.

**Pass D verdict:** `GO_WITH_MINOR_REVISION`.

---

## 7. Pass E — R1 specification conformance

Independent grades:

| R1 requirement | Grade |
| --- | --- |
| 1. exact family event | met |
| 2. relation to canonical scopes | met |
| 3. no fresh unaccounted budgets | future criterion; exact source arithmetic wrong |
| 4. earlier terminal effects | met at research level; not implemented |
| 5. aggregate proof under maintained assumptions | **not met / blocking** |
| 6. adaptive continuation or narrow claim | current claim honestly narrowed; theorem needs revision |
| 7. canonical owner reuse | met |
| 8. live reproduction | negative absence reproducible; positive capability missing and fixture oracle wrong |

The report's matrix is P29-shaped: it grades proposed future properties as if they answered the
acceptance evidence. It should separate research theorem, future closure criterion, and live
capability.

The mandatory three-fresh-scope trace remains possible and the report admits it. That honesty is a
strength. What fails is the assigned `3/100` probability meaning, not the scope trace itself.

**Pass E verdict:** `NO_GO`.

---

## 8. Pass F — anchor quality

### 8.1 Frontmatter-anchor set

The exact weak anchor

```text
policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10
```

appears 32 times:

- 17 in the primary report;
- 5 in the fixture/artifact sketch; and
- 10 in the source/transfer ledger.

The gap is only mentioned in revision metadata there. The substantive owner, consequence, warning,
and closure signal are at `:2439-2463`.

### 8.2 Burn-order anchor

`confidence_ledger.py:1301-1364` proves local ordinal/spend computation. It does not extend through
the durable `started` append and entry into owner execution. Uses asserting that ordering need
`:1356-1382` or a containing range.

### 8.3 Remaining anchors

N9 scope, root, receipt, refusal, schedule, registry, INT-R1, custody-kernel, and proving-ground
anchors were substantively correct. `INT-R1:1-90` is broad but contains the exact theorem at
35–79.

**Pass F verdict:** `GO_WITH_MATERIAL_REVISIONS`.

---

## 9. Pass G — fixture and artifact sketch

### 9.1 Positive control

The future positive control genuinely demands:

- cap binding before owner execution;
- exact rational recomputation;
- live scope/root/head verification;
- chronology and no-substitution;
- plan/source identity; and
- property-removal negatives that keep markers while deleting enforcement.

It honestly expects refusal at the pinned baseline.

### 9.2 Negative control

The trace of three roots is a good structural negative. Its expected numeric failure

```text
family_budget_exceeded: allocated=3/100
```

is not a valid probability oracle for the pinned owner. Root budgets and exact scheduled risk are
not interchangeable.

### 9.3 Contract hardening

The 614-line sketch supplies named classes, schema strings, package-like references, exhaustive
fields, enumerated terminal/refusal vocabularies, a 14-step algorithm, and nineteen mutation IDs.
Despite disclaimers, an implementation team could treat it as the final contract. This repeats the
shape problem found in INT-R9, and it is especially unsafe while the core arithmetic is wrong.

### 9.4 Owner boundaries

No second ledger, parent risk scope, family ordinal, or weakened `design-problem` identity is
proposed. The intended family object is a declaration/projection over existing roots. Preserve that
constraint.

**Pass G verdict:** `NO_GO` because the load-bearing numeric oracle is wrong; otherwise strong
behavioral intent.

---

## 10. Pass H — scope and standing

### 10.1 Diff discipline

Confirmed: three new Markdown files only; no code/test/existing-document modification. Research
frontmatter excludes implementation, authority, capability, and benchmark passage.

### 10.2 Standing

`accepted_narrow_scope` would be appropriate if the abstract theorem and canonical-source
application were both sound while capability remained missing. They are not. A false sharpness
claim is not a mere implementation gap. The research package must be `blocked` pending amendment.

### 10.3 Custody kernel and INT-R1

The report respects:

- S0-K05: observation, transport, and projection do not create authority;
- S0-K16: fixture passage is bounded;
- authority-band/candidate-band separation;
- confidence ledger as existing owner; and
- obligation completeness/validator soundness as maintained assumptions.

**Pass H verdict:** `NO_GO` on standing; scope discipline is commendable.

---

## 11. Pass I — supplied orientation

### 11.1 Verified facts

Confirmed independently:

- per-problem scope constructor and owner key;
- non-resettable local scope;
- scope-local ordinal/prior-spend calculation;
- absence of the three cross-scope symbols;
- 232-line registry;
- five proof profiles and two Basel schedules;
- thirteen instruments;
- exact delta `1/100`;
- exact rational/Basel/partition machinery;
- proving-ground 0/13 state; and
- essentially unexercised useful probabilistic path.

### 11.2 Orientation error

The supplied conclusion “only generic family-wise statement is `3delta`” is true only after
retaining the coarse root guarantee and discarding exact schedule structure. It is not a complete
statement of what follows from the pinned source. The shorthand “ordinal zero -> fresh delta” is
safe only when explicitly labeled root-level policy, not reservation or event probability.

**Pass I verdict:** one blocking arithmetic orientation error; remaining facts verified.

---

## 12. P29 stopping rule

This audit does not reject INT-R10 because a future registry might add a new profile, a future
selector might evade an otherwise generic verifier, or a stronger method might be desirable. The
blocking counterexample is present now:

- the report claims source-sharpness;
- the source contains exact schedule constraints;
- the witness violates those constraints; and
- the false conclusion is copied into the current fixture and INT-R9 handoff.

That is an actual premise failure, not a hypothetical meta-level gap.

---

## 13. Safe and unsafe reliance for INT-R9

### 13.1 Safe now

The parallel INT-R9 amendment may rely on:

1. `V_F = union_i(R_i ∩ P_i ∩ W_i)`;
2. fixed-family weighted union under genuine prospective local caps;
3. no common-null/exchangeability/independence requirement in that union step;
4. distinct canonical problem scopes must remain distinct;
5. no canonical family declaration/projection exists at the baseline;
6. the confidence ledger/N11 lane owns composition;
7. current outcome-dependent repair has no numeric theorem;
8. all probability remains relative to declared obligations and validator soundness;
9. no-refund/no-substitution is a safe conservative governance pattern; and
10. missing numeric authority does not block candidate exploration.

### 13.2 Must wait

It must wait for amendment and independent verification before relying on:

1. `3delta` as sharp or strongest for the pinned owner;
2. `3/100` as the live three-scope bound;
3. equal `1/300` caps as necessary;
4. the present negative-control budget-exceeded oracle;
5. Theorem B's displayed proof;
6. the support file as an implementation contract;
7. the §4.11 claim that all eight R1 rows are answered; or
8. `accepted_narrow_scope` as consolidation standing.

---

## 14. Final decision

The right disposition is **`NO_GO` with preservation of substantial verified results**.

INT-R10 should be amended, not discarded. The amendment must:

- re-derive family arithmetic from the exact canonical schedule and class weights;
- withdraw unsupported source-sharpness, `3/100`, and equal-third-necessity claims;
- repair the fixture oracle;
- formalize or narrow Theorem B;
- correct the pervasive anchors;
- demote the de facto schema to research invariants; and
- change standing until the amended mathematics is independently verified.

Until that happens, the only safe numeric public position is that **the current repository has no
canonical live family-wise projection and therefore cannot publish the intended INT-R9 family
bound**. That negative capability result is supported. INT-R10's present explanation of the
arithmetic is not.
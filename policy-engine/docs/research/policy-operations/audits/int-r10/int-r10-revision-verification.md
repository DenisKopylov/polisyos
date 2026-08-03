---
title: INT-R10 — Revision Conformance Verification
status: delivered
kind: revision-verification
research_task: INT-R10
verification_verdict: CONFORMS
repository: https://github.com/DenisKopylov/polisyos
verified_branch: research/int-r10-revision
verified_commit: a334f7d844733bfd17f1857a4cb56fbf219378ef
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
independent_audit: research/int-r10-independent-audit@7f41bf8b7f6ca8e20bc885656314563de2e2cfc6
current_repository_commit: 01a9ec884a4a3193ebdea7d8431542ac55c47cda
inspection_date: 2026-08-03
authoritative_for:
  - bounded conformance verification of the INT-R10 revision against the published independent-audit finding list
  - confirmation that the corrected canonical-source envelope, formal adaptive theorem boundary, fixture semantics, anchors, and standing are present in the revised text
  - identification of revised INT-R10 conclusions safe for synthesis
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, or serialization contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - assertion that a live family declaration, chronology verifier, aggregate current-head projection, or public owner statement exists
  - assertion that outcome-dependent repair currently has a numeric family theorem
  - a new audit of questions outside the published INT-R10 audit finding list
research_only: true
---

# INT-R10 — Revision Conformance Verification

## Executive verdict

**Verdict: `CONFORMS`.**

The revision at `a334f7d844733bfd17f1857a4cb56fbf219378ef` executed the published INT-R10 audit list in the revised text, rather than only in its self-authored revision ledger.

The five blocking defects are repaired:

1. the canonical-source application is re-derived from the exact Basel reservation law and the complete expanded obligation-class map;
2. R1 requirement 5 now separates the established fixed-family mathematics from the missing live owner projection;
3. the fixture no longer counts root policy ceilings as a probability oracle;
4. `accepted_narrow_scope` is consistently restricted to the theorem and corrected source envelope while runtime capability remains blocked; and
5. the former root-budget orientation is replaced by exact reservation language and a complete registry census.

The revision preserves the abstract union-bound sharpness theorem only for the deliberately coarsened information state in which the local owner has been reduced to marginal statements `P(V_i | A_F) <= b_i`. It does not present that witness as sharp for the pinned owner.

The exact source calculation independently reproduced at `01a9ec884a4a3193ebdea7d8431542ac55c47cda` is:

```text
alpha_{s,t}
  = delta_s
    * expanded_class_weight(q_{s,t})
    * schedule_mass_s
    * (76614/126025)
    / (t+1)^2,
```

with maximum expanded class weight `3/20` on `calibration`. Since `76614/126025 < 6/pi^2`, one scope has the pathwise all-check envelope

```text
sum_t alpha_{s,t} < delta_s * schedule_mass_s * 3/20,
```

and an exact three-scope, mass-one, common-delta family has the mathematical envelope

```text
P(V_F | A_F) < (9/20) * delta.
```

At the live root policy `delta = 1/100`, the right-hand side is `9/2000`, strictly interpreted as an all-path mathematical envelope under the named assumptions—not a live family projection or an empirical estimate.

A synthesis pass may now cite as settled research:

- the reached-member event definition;
- the fixed-family weighted-union theorem;
- the explicitly qualified coarse-information sharpness result;
- the exact pinned canonical envelope;
- the absence of a live family declaration/projection/reproduction chain;
- the confidence ledger/N11 lane as the existing risk-accounting owner to be extended without changing per-problem scope identity;
- the continued INT-R1 conditionality; and
- the present absence of a numeric theorem for outcome-dependent repair.

A synthesis must not say that the repository already emits a canonical family bound, that the fixture grants authority, or that INT-R9's adaptive protocol has a numeric family-wise theorem.

---

## 1. Verification object and bounded method

The controlling inputs were read before the reviser's ledger:

- the independent audit and its formal-argument analysis;
- the recommended-revision file;
- the independent R1 specification grading;
- the revised primary report;
- the revised source/transfer ledger; and
- the revised fixture/semantic-handoff sketch.

Only after those checks was `int-r10/revision-ledger.md` read and compared with the independently formed result.

This is not a second audit. The verification asks whether each published finding was executed and whether each audited strength survived. No new theorem, owner design, or implementation requirement is introduced.

### 1.1 Diff boundary

Comparison from the revision baseline `f5c9103ba390d471dd3f2806ca10e2b0f1288a08` to the verified head shows five commits and exactly four added Markdown files:

| Path | Status | Lines added |
| --- | --- | ---: |
| `policy-engine/docs/research/policy-operations/int-r10-family-wise-risk-composition.md` | added | 991 |
| `policy-engine/docs/research/policy-operations/int-r10/fixture-and-artifact-sketch.md` | added | 405 |
| `policy-engine/docs/research/policy-operations/int-r10/source-and-transfer-ledger.md` | added | 392 |
| `policy-engine/docs/research/policy-operations/int-r10/revision-ledger.md` | added | 265 |

No source file, test, audit file, or unrelated pre-existing document changed on the revision branch. The later current-main baseline does not change the confidence-ledger source, registry, or corrected GY-GAP2 predicates used here.

---

## 2. Check 1 — five blocking findings

### 2.1 `INT-R10-B-001` / `INT-R10-I-001` — canonical-source application

#### Independent source census

The complete live registry at `01a9ec884...` contains:

```text
registry_line_count = 232
schedule_profiles = 2
obligation_pools = 7
proof_profiles = 5
instruments = 13
certificate_class_routes = 6
pool_weight_sum = 1
expanded_class_weight_sum = 1
expanded_class_count = 15
max_expanded_class_weight = calibration: 3/20
```

All seven pools were enumerated:

| Pool | Pool weight | Classes | Expanded class weight |
| --- | ---: | --- | ---: |
| `value` | `1/5` | `normative`, `value` | `1/10` each |
| `ground` | `3/20` | `syntax`, `type`, `slot`, `param` | `3/80` each |
| `id` | `1/5` | `effect`, `identification`, `measurement` | `1/15` each |
| `cal` | `3/20` | `calibration` | `3/20` |
| `data` | `1/10` | `data` | `1/10` |
| `eval` | `1/10` | `implementation`, `eval_safety` | `1/20` each |
| `mc` | `1/10` | `coupling`, `equilibrium` | `1/20` each |

The source divides each pool weight by its class count before allocation. The maximum entering `_schedule_alpha()` is therefore `3/20` on `calibration`, not a sampled pool value or a root ceiling.

The source also confirms:

- one local executed-check ordinal and the same schedule index;
- exact `Fraction` arithmetic;
- schedule mass at most one;
- the certified rational coefficient `76614/126025`; and
- durable append of the `started` reservation before owner invocation.

#### Independent derivation

For every local path,

```text
alpha_{s,t}
  = delta_s * w(q_{s,t}) * M_s * c_B / (t+1)^2,
```

where `c_B = 76614/126025 < 6/pi^2`, `M_s <= 1`, and `w(q_{s,t}) <= 3/20`. Thus

```text
sum_t alpha_{s,t}
  <= delta_s * M_s * (3/20) * c_B * sum_t 1/(t+1)^2
  =  delta_s * M_s * (3/20) * c_B * pi^2/6
  <  delta_s * M_s * 3/20.
```

The revision contains this derivation in the primary report and repeats it in the source ledger and fixture oracle. It also states the check-to-member bridge as conditional on a valid local theorem, obligation completeness, validator soundness, exact family membership, and the represented source/root identities.

#### Abstract sharpness retained correctly

The primary report retains the disjoint-event construction under the explicit premise:

> “Suppose all schedule-, class-, process-, and spend-specific information is intentionally discarded.”

It then states that the result is **not** a sharpness witness for the richer pinned owner. This is the required middle position: no over-correction and no under-correction.

**Finding `INT-R10-V-001` — commendation.** The blocking canonical-source defect is repaired, with the exact source law independently reproducible.

### 2.2 `INT-R10-E-002` — R1 requirement 5

The regraded R1 matrix now says requirement 5 is mathematically met for a fixed exact family through the §4.4 source-derived envelope, while the canonical family projection and useful positive probabilistic path remain absent.

This is not silence or relabelling. The report gives the complete calculation from checks to member to family and separately records what a future owner must reproduce from current roots, schedules, heads, chronology, and assumptions.

**Finding `INT-R10-V-002` — commendation.** Requirement 5 is repaired at research level and remains honestly unavailable as live owner capability.

### 2.3 `INT-R10-G-001` — fixture oracle

The fixture now has two independent layers:

- exact mathematical recomputation of each reservation, exact path sum, and all-path envelope; and
- a structural family-custody decision over membership, chronology, current heads, local theorem standing, and assumptions.

The mandatory negative control goes red because canonical family custody is absent, not because three roots are numerically counted. It explicitly says:

```text
local accounting is valid
mathematical cross-scope envelope is derivable
canonical family membership/currentness/chronology is not attested
public family statement is unavailable
```

The audited strengths survive:

- reservation must be appended before invocation;
- property-removal keeps markers while deleting the real behavior;
- the confidence ledger remains the single owner;
- per-problem scope identity is preserved; and
- the positive future fixture must refuse at the pinned baseline.

**Finding `INT-R10-V-003` — commendation.** The fixture oracle is repaired without losing its behavioral falsifiers.

### 2.4 `INT-R10-H-002` — standing

All four revision files carry `result_type: accepted_narrow_scope`. The body consistently limits that standing to the fixed-family theorem, the qualified abstract sharpness result, and the corrected source envelope.

The primary Executive Finding, §1.5, §4.9–§4.11, §8, and §9 all keep these separate:

- research mathematics: accepted narrowly;
- canonical family declaration/projection: blocked/missing;
- useful selector-valid theorem for outcome-dependent repair: blocked/unavailable.

The fixture requires baseline refusal, the source ledger says family projection is a future criterion, and the revision ledger denies capability authority. No body passage converts the research standing into live runtime standing.

**Finding `INT-R10-V-004` — commendation.** The standing is consistent across frontmatter, executive language, matrix, fixture, and handoff.

---

## 3. Check 2 — refuted arithmetic is absent as a claim

Literal repository searches and complete-file inspection were applied to all four revision files for:

```text
3 * delta
3*delta
3/100
1/300
```

No revision file asserts any of those figures. No equal-share prescription, `delta_F/3` rule, or decimal equivalent of the withdrawn result remains.

The revision instead uses:

```text
one scope:  < delta_s * M_s * 3/20
three mass-one scopes: < (9/20) * delta
live policy instance: < 9/2000
```

### 3.1 Derivation attempt

The only route to the withdrawn figures would be:

```text
three roots
x root policy delta
= three attainable member-event deltas.
```

The revised text blocks the second step explicitly:

> “A root policy value must never stand in for a member-event probability or an ordinal-zero reservation.”

It then supplies the exact reservation law. Following the text therefore yields the strict `(9/20) * delta` envelope, not any withdrawn figure. No independent reader can derive the old result without contradicting an explicit source premise in the revision.

**Finding `INT-R10-V-005` — commendation.** The refuted arithmetic is not derivable from the revised package.

---

## 4. Check 3 — Theorem B formal repair

The revised §4.7 states:

- a probability space `(Omega, F, P)`;
- a maintained-assumption event `A_F` with positive probability;
- the conditional law `P_F`;
- a filtration `H_0 subseteq ... subseteq H_m`;
- `R_i` is `H_{i-1}`-measurable;
- the selected procedure is `H_{i-1}`-measurable;
- nonnegative allocation `a_i` is `H_{i-1}`-measurable; and
- the reached pathwise allocation satisfies `sum_i R_i a_i <= delta_F`.

The local premise is explicitly for the **actually selected** procedure:

```text
1_{R_i} * P_F(P_i intersect W_i | H_{i-1})
  <= 1_{R_i} * a_i
```

almost surely.

Because `R_i` is history-measurable, the displayed tower step is valid:

```text
P_F(V_i)
 = E_F[1_{R_i} 1_{P_i intersect W_i}]
 = E_F[1_{R_i} E_F[1_{P_i intersect W_i} | H_{i-1}]]
 <= E_F[1_{R_i} a_i].
```

Summation and the pathwise constraint yield the stated family bound.

The former undefined disjunct is absent from the theorem. Possible alternatives are now a separate note naming example theorem families and requiring each to define its event, filtration, assumptions, owner profile, verifier, source binding, and falsifier.

The qualitative boundary survives verbatim in substance:

> “adaptation is not intrinsically impossible” and “predictable arithmetic alone does not validate outcome-selected repair.”

The live registry still supplies no useful theorem satisfying the premise, so the current adaptive numeric claim remains withdrawn.

**Finding `INT-R10-V-006` — commendation.** Theorem B's formal and claim-boundary repairs are complete.

---

## 5. Check 4 — GY-GAP2 and anchors

### 5.1 Current substantive block

At `01a9ec884...`, the substantive `GY-GAP2` block is `GY-engine-subordination.md:2440-2476`. It states all of the following:

- per-problem N11 scopes remain correct;
- the earlier root-budget wording was wrong;
- the exact schedule uses expanded class weights;
- one scope is below `delta * 3/20 * mass` and three mass-one scopes are below `(9/20) * delta`;
- the correction is safe-directional;
- no family declaration, chronology verifier, or aggregate current-head projection exists; and
- closure must extend the existing ledger, not create a second owner.

The revision agrees with that row. It does not silently diverge.

### 5.2 Current citation census

Every full `GY-engine-subordination.md:` citation across the four revision files was enumerated:

| Revision file | Current citations |
| --- | ---: |
| primary report | 12 |
| fixture/semantic-handoff sketch | 6 |
| source/transfer ledger | 11 |
| revision ledger | 1 |
| **Total** | **30** |

The complete current range set is:

```text
{2440-2476}
```

All thirty citations land inside the substantive block. No metadata-only `:1-10` citation remains.

The audit's historical count was thirty-two sites in the three superseded files. The revision ledger separately accounts for all thirty-two historical sites: some were re-anchored and some disappeared with the refuted claim they supported. The current count is therefore not required to remain thirty-two.

**Finding `INT-R10-V-007` — commendation.** GY-GAP2 is correctly characterized and every current anchor is substantive.

---

## 6. Check 5 — audited commendations survive

All commendations named in the audit's finding table survive in the revised text. The detailed location and quoted-fragment ledger is in `int-r10-revision-conformance-ledger.md`.

The two sibling-critical strengths are especially clear:

### 6.1 `INT-R10-E-003` — adaptive numeric withdrawal

The primary report says:

> “current outcome-dependent repair has no numeric family theorem”

and:

> “This withdrawal is load-bearing and must not be softened.”

The INT-R9 handoff repeats that its adaptive protocol must not attach a numeric family claim.

### 6.2 `INT-R10-E-005` — mandatory falsifier remains open

The primary report and fixture say the original trace remains possible and is:

> “unblocked as a family-custody trace”

while removing the former inflated probability interpretation. This preserves the audit's honesty requirement exactly.

**Finding `INT-R10-V-008` — commendation.** No audited commendation was lost or weakened into a heading-only claim.

---

## 7. Check 6 — material/minor findings and boundaries

### 7.1 Material and minor dispositions

| Finding | Verification disposition | Textual evidence |
| --- | --- | --- |
| `INT-R10-C-001` | executed | filtered space, conditional law, reach/procedure/allocation measurability, and tower proof in primary §4.7 |
| `INT-R10-C-002` | executed | undefined alternate disjunct removed; alternatives separated and characterized |
| `INT-R10-D-002` | executed | independent product calculation separated from Gaussian Sidak rectangle theorem |
| `INT-R10-E-001` | executed | R1 matrix split into research result, future criterion, and pinned capability |
| `INT-R10-E-006` | executed | positive reproduction repeatedly identified as future criterion; baseline positive fixture refuses |
| `INT-R10-F-001` | executed | current full-path GY citation range set is only `2440-2476`; historic sites accounted |
| `INT-R10-F-002` | executed | arithmetic uses `1301-1364`; durable burn-order claims use `1356-1382` |
| `INT-R10-G-002` | executed | class names, schema strings, loadable YAML, fixed package/refusal vocabulary removed; choices explicitly unresolved |
| `INT-R10-I-002` | executed | “fresh root-level policy and schedule series” distinguished from exact reservation |
| `INT-R10-I-003` | executed | complete 13/5/7/2/6 census and instrument names recorded programmatically |

No item was merely declined or relabelled.

### 7.2 Independent instrument census

The live registry independently yields:

```text
[[instruments]] = 13
[[proof_profiles]] = 5
[[obligation_pools]] = 7
[[schedule_profiles]] = 2
[[certificate_class_routes]] = 6
```

The revision records the same counts and enumerates the thirteen instruments rather than treating five proof profiles as the inventory.

### 7.3 Owner and constitutional boundaries

The revised text:

- preserves `design-problem` scope identity;
- forbids a second ledger, parent risk scope, family ordinal, second mutable head, and second promotion decision;
- identifies the existing confidence ledger/N11 lane without appointing a new owner;
- leaves class names, package placement, serialization, identity format, lifecycle vocabulary, public shape, and error codes unresolved;
- carries obligation completeness and validator soundness as maintained assumptions;
- preserves S0-K05's no-authority-by-projection rule;
- preserves S0-K16's bounded-passage rule; and
- permits candidate-band work only under an explicit limitation.

**Finding `INT-R10-V-009` — commendation.** All material/minor repairs and all audit boundaries conform.

---

## 8. Reviser ledger cross-check

The self-authored revision ledger was read last. Its statements agree with the independently verified files on:

- exact schedule arithmetic;
- qualified sharpness;
- R1 regrading;
- fixture restructuring;
- Theorem B formalization;
- anchor correction;
- schema demotion;
- registry census;
- commendation preservation; and
- blocked live capability.

The ledger is therefore an accurate index of the revision. The conformance verdict does not rely on the ledger as proof.

---

## 9. Final synthesis boundary

### Settled and citable

A synthesis may cite:

```text
For a fixed exact family, valid reached-member bounds under one maintained-assumption event compose by Boole's inequality. At the pinned confidence owner, exact Basel reservations and the complete expanded class map give each scope an all-path envelope below delta_s * schedule_mass_s * 3/20; an exact three-member mass-one common-delta family is below (9/20) * delta. The repository nevertheless lacks canonical family membership, chronology/current-head verification, and an aggregate public owner projection. Outcome-dependent repair has no current numeric theorem.
```

### Still open as capability

The following remain future work rather than revision gaps:

- live prospective family declaration;
- chronology and omitted-positive verification;
- aggregate current-head owner projection;
- consumer/public correction and suspension lifecycle; and
- useful selector-valid local theorem for outcome-dependent repair.

Those items do not prevent synthesis from citing the revised mathematical conclusions. They prevent synthesis from claiming the runtime already supplies the corresponding authority capability.

## 10. Verification decision

`research/int-r10-revision@a334f7d844733bfd17f1857a4cb56fbf219378ef` **conforms to the published independent-audit repair list**. Synthesis may proceed using the bounded conclusions above.

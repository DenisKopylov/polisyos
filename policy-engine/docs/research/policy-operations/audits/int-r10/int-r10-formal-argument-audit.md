---
title: INT-R10 — Formal Argument Audit
status: delivered
kind: independent-audit
research_task: INT-R10
audited_branch: research/int-r10-family-wise-risk-composition
audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
overall_verdict: NO_GO
research_only: true
authoritative_for:
  - independent step-by-step audit of INT-R10 Theorem A, the sharpness/current-source corollary, and Theorem B
  - identification of stated, unstated, satisfied, and unsatisfied mathematical premises
  - separation of the valid abstract union theorem from the invalid live-source sharpness claim
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - replacement family-composition theorem
  - certification that the schedule-derived counter-bound is implemented as a public family claim
---

# INT-R10 — Formal Argument Audit

## 1. Audit standard

This file audits the mathematics before the proposed governance or artifact shapes. It asks, for
each displayed result:

1. what probability space, event, conditioning event, filtration, and cap are used;
2. whether every premise is stated;
3. whether the pinned repository satisfies the premise claimed for it;
4. whether the displayed inference follows; and
5. whether a statement proved from deliberately coarsened information is later represented as
   sharp for the richer live source.

The central distinction is decisive:

- **Theorem A as an abstract result from local event bounds is correct.**
- **The claim that `3 * delta` is sharp, or the strongest available bound, for the pinned canonical
  source is not established and is contradicted by source structure INT-R10 itself cites but does
  not compose.**

That second point is load-bearing because the report's impossibility result, fixture arithmetic,
INT-R9 handoff, and proposed `1/300` cap vector all depend on it.

## 2. Notation recovered from the audited report

For ordered family `F = (1, ..., m)` the report defines:

- `R_i`: member `i` is reached;
- `P_i`: member `i` produces a canonical positive promotion;
- `W_i`: that promotion is false relative to the member's declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`; and
- `V_F = union_i V_i`.

`A_F` denotes the joint maintained assumptions. The report inherits the ledger's exact maintained
assumptions `obligation_completeness` and `validator_soundness`, and does not claim to remove
INT-R1's open-world boundary. The live clause is visible at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:28-43` and
`policy-engine/architecture/production_quality/confidence_ledger.toml:1-6`.

Under stop on first canonical positive, `V_F` is the event that the family's reported first
promotion is false. The event definition is correct: later members are unreached after a positive,
while earlier refusals, voids, disputes, and negatives remain in chronology.

---

## 3. Pass A — Theorem A, prospectively fixed family

### 3.1 Claim audited

Theorem A assumes, for nonnegative caps `alpha_i`, that the canonical owner enforces each cap before
member `i` executes, that

```text
P(V_i | A_F) <= alpha_i,
```

and that

```text
sum_i alpha_i <= delta_F.
```

It concludes

```text
P(V_F | A_F) <= delta_F.
```

### 3.2 Step-by-step verification

#### Step A1 — the event is the correct union

By definition,

```text
V_F = union_i V_i.
```

This is exactly the controlled authority-error event. The reached indicator is not omitted; a
member that is never executed contributes the empty event on that path.

**Verdict:** valid.

#### Step A2 — conditional union inequality

Provided `P(A_F) > 0` or a regular conditional-probability formulation is used,

```text
P(union_i V_i | A_F) <= sum_i P(V_i | A_F).
```

No common null, common estimand, exchangeability, or independence is used. Heterogeneous problems
are permitted because the proof composes event probabilities, not test statistics.

**Verdict:** valid. The report could state `P(A_F) > 0` for formal completeness, but that omission
does not alter the finite-family argument in its intended setting.

#### Step A3 — substitution of local caps

The assumed local inequalities give

```text
sum_i P(V_i | A_F) <= sum_i alpha_i.
```

This step is correct only because the theorem assumes the local guarantee under the same `A_F`.
Separate statements of the form `P(V_i | A_i) <= alpha_i` would not in general remain valid after
conditioning on a stronger conjunction `A_F`; the report's displayed theorem avoids that error by
writing the common conditioning event directly.

**Verdict:** valid as stated.

#### Step A4 — aggregate cap

The prospective exact inequality `sum_i alpha_i <= delta_F` yields the conclusion.

**Verdict:** valid.

### 3.3 Why pre-execution enforcement is load-bearing

The report repeatedly states that `alpha_i` must bind before result-bearing execution. That is not
administrative timing; it is part of the probability premise. If a cap can be selected after the
outcome, an actor can assign a small cap to a favorable result and larger caps to unfavorable
results while making the final written sum look compliant. The selected cap then has no valid local
theorem.

The current ledger has the right local pattern: it computes and durably burns a schedule slot before
owner invocation at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1368`. INT-R10 is correct that
an after-the-fact total-spend check is not a substitute.

### 3.4 Dependence and local theorem premises

The union proof itself needs no dependence assumption. A *local* certificate may still require its
own sampling, filtration, null, exchangeability, or martingale conditions. The report keeps that
burden local and requires an owner-verified theorem. It does not use “no independence is needed for
Bonferroni” to erase assumptions inside a confidence sequence, e-process, sequential test, or
validator.

### 3.5 Maintained assumptions

The report preserves the conditionality

```text
P(false promotion | maintained assumptions) <= delta
```

and names obligation completeness and validator soundness. It also binds member-specific obligation
sets rather than claiming completeness of the world. This is consistent with
`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:41-79`.

### 3.6 Finding

#### INT-R10-A-001 — The fixed-family weighted-union theorem is correct

- **Severity:** `commendation`
- **Disposition:** preserve exactly, while distinguishing it from the later live-source corollary.
- **Evidence:** §4.2 of the audited report; elementary conditional union inequality; explicit common
  conditioning event and prospective cap premise.

Theorem A is safe for INT-R9 to cite only as an `if` theorem: it does not establish that the pinned
runtime has effective local caps or a family projection.

#### INT-R10-A-002 — The report correctly carries conditionality and rejects hidden dependence

- **Severity:** `commendation`
- **Disposition:** preserve.
- **Evidence:** audited §§1.2, 3.1, 4.2, 4.10; ledger clause at
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:28-43`; INT-R1 at
  `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:41-79`.

---

## 4. Pass B — sharpness and the live-source impossibility claim

### 4.1 The abstract sharpness statement

From *only* the marginal bounds

```text
P(V_i | A_F) <= delta,
```

one can construct, for `m * delta <= 1`, a probability space with mutually disjoint events
`E_1, ..., E_m`, each of probability `delta`, set `A_F = Omega`, and identify `V_i = E_i`.
Then

```text
P(union_i V_i | A_F) = m * delta.
```

For stop on first positive, the construction can assign outcome `i` to “all earlier members are
negative and member `i` falsely promotes”; the events remain disjoint and the reach rule is
satisfied. Fixed caps `alpha_i = delta` are prospective.

**Verdict:** the abstract lower-bound witness is valid. It proves that the union bound is sharp when
one intentionally retains only the coarse local marginal bounds.

### 4.2 What the audited report then claims about the pinned source

The report goes further. It says that because three scopes each have a root-level `budget_delta =
delta`, the strongest generic pinned-source statement is `3 * delta`; that this is sharp for the
canonical owner; and that a future family must therefore reduce each effective top-level cap to,
for example, `delta_F / 3`.

That inference discards a stronger, mechanically verified premise in the live owner: `budget_delta`
is not assigned directly to one member-level false-promotion event. Eligible probabilistic checks
are priced by the exact schedule

```text
alpha_t
  = delta
    * obligation_weight(q_t)
    * schedule_mass
    * (76614 / 126025)
    / (t + 1)^2.
```

The source facts are:

1. there is one global executed-check ordinal inside a scope, and
   `schedule_query_index = execution_ordinal`
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1318-1347`);
2. a pool weight is divided equally across the classes in that pool
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:409-419`);
3. the live pool/class configuration has maximum expanded class weight `3/20`, for the single
   `calibration` member of the `cal` pool
   (`policy-engine/architecture/production_quality/confidence_ledger.toml:18-50`);
4. schedule mass is at most one and the default is one
   (`policy-engine/architecture/production_quality/confidence_ledger.toml:8-16`;
   `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:265-290`);
5. `_schedule_alpha()` uses the exact formula above
   (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3998-4015`); and
6. the N11 good-event argument assigns each executed probabilistic false-claim event its schedule
   slot and composes those events by tower property plus union bound
   (`policy-engine/docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:120-151`,
   `policy-engine/docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:235-248`).

For any path and any adaptively chosen obligation-class sequence `q_t`, therefore,

```text
sum_t alpha_t
  <= delta * (3/20) * schedule_mass
     * (76614/126025) * sum_t 1/(t+1)^2
  < delta * (3/20).
```

The strict inequality follows because `76614/126025 < 6/pi^2`. Across three ordinary scopes using
the live maximum-mass profile, the same source-level union accounting is strictly below

```text
3 * (3/20) * delta = (9/20) * delta.
```

At live `delta = 1/100`, that envelope is strictly below `9/2000 = 0.0045`, not `3/100`.

This calculation is not offered as a new public PolicyOS capability. The repository still lacks a
canonical cross-scope declaration/projection, and no real positive probabilistic promotion profile
exists. It is a falsifier of INT-R10's *sharpness claim*: the disjoint events of probability
`delta` do not satisfy the pinned owner's stronger schedule premise. A theorem may be sharp after
throwing away source information and still fail to be sharp for the source.

### 4.3 Programmatic exact-rational census

The audit enumerated the pinned registry values and executed exact `Fraction` arithmetic. The
reproducible output was:

```text
proof_kernel_counts= {'closed_constant_unit_e_process_v1': 1,
                      'deterministic_owner_v1': 1,
                      'ineligible_v1': 2,
                      'owner_theorem_unavailable_v1': 1}
schedule_kernel_counts= {'basel_square_v1': 2}
schedule_masses= ['1', '1/2']
pool_weight_sum= 1
expanded_class_weight_sum= 1
class_count= 15
max_class_weight= calibration 3/20
delta= 1/100
basel_coefficient= 76614/126025
ordinal_zero_max_spend_ratio_to_delta= 114921/1260250
per_scope_total_spend_ratio_to_delta_strictly_less_than= 3/20
three_scope_total_spend_ratio_to_delta_strictly_less_than= 9/20
```

The ordinal-zero maximum is about `0.091189 * delta`, which independently confirms the report's own
precision note that ordinal zero does not spend the entire root delta. The report notices that
fact, but its sharpness/current-corollary sections do not carry the consequence through.

### 4.4 What this does and does not prove

It proves that these audited sentences are not presently justified:

- “`3 * delta` is sharp” when referring to the canonical pinned owner rather than only coarse
  marginal statements;
- “the strongest generic implication at the pinned baseline is `3 * delta`”;
- “the mandatory negative control represents aggregate risk of `3/100`”; and
- “one-third top-level caps are mathematically necessary for the three-slot family.”

It does **not** prove that INT-R9 may publish a live `delta` family claim today. Requirement R1 also
requires an exact family binding, chronology, current-head verification, maintained-assumption
composition, and a canonical projection. GY-GAP2 correctly says those owner artifacts do not exist
at the baseline
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2439-2463`). Moreover,
the registry has no useful positive probabilistic owner theorem. The honest current standing remains
“numeric family capability blocked,” but for a different and narrower reason than INT-R10 states.

### 4.5 Findings

#### INT-R10-B-001 — The live-source `3 * delta` sharpness/impossibility claim is false as stated

- **Severity:** `blocking`
- **Disposition:** withdraw every pinned-source `3 * delta` / `3/100` / equal-third necessity claim;
  re-run composition from the exact canonical schedule, obligation weights, scope count, and local
  good-event semantics before consolidation.
- **Falsifier:** the current source's one-ordinal-per-check allocation and maximum class weight yield
  a strict three-scope envelope below `(9/20) * delta`. The disjoint-`delta` witness cannot satisfy
  those source premises.
- **Affected locations:** primary report Executive Finding, §§2.4, 4.1, 4.3, 4.4, 4.10, 4.11,
  6.3, 8.2, 10 and final conclusion; fixture §§7.3, 7.5, 10; source ledger §§4.1 and 6.

This is the audit's decisive `NO_GO` finding. The finding is not that a tighter operational claim is
already implemented. It is that INT-R10's claimed impossibility and sharpness do not describe the
pinned owner.

#### INT-R10-B-002 — Sharpness from deliberately coarse marginal bounds is valid

- **Severity:** `commendation`
- **Disposition:** preserve only with an explicit qualifier such as “after discarding all
  schedule-, class-, and spend-specific canonical information.”
- **Evidence:** disjoint-event construction above.

---

## 5. Pass C — Theorem B, adaptive continuation

### 5.1 Claim audited

The report lets `H_{i-1}` be the complete history before member `i`, chooses
`alpha_i(H_{i-1})` before member `i`'s result, imposes a pathwise total at most `delta_F`, and assumes

```text
P(P_i ∩ W_i | H_{i-1}, R_i, A_F)
  <= alpha_i(H_{i-1})
```

almost surely, “or an equivalent uniform/selection-aware theorem.” It then writes

```text
P(V_i | A_F)
  = E[1_{R_i} P(P_i ∩ W_i | H_{i-1}, R_i, A_F)]
  <= E[1_{R_i} alpha_i(H_{i-1})].
```

### 5.2 Necessary measurable structure

A rigorous version needs a filtered probability space and at least:

1. `H_{i-1}` denotes a sigma-field `mathcal H_{i-1}`;
2. the selected member procedure and cap are `mathcal H_{i-1}`-measurable;
3. `R_i` is `mathcal H_{i-1}`-measurable, because reach is determined by prior chronology;
4. `P(A_F) > 0`, or all statements use a regular conditional law under `A_F`;
5. the local conditional bound holds under the actual adaptive selector; and
6. the cap constraint holds pathwise on the same sample path. A sufficient version may use
   `sum_i R_i alpha_i <= delta_F`; the report uses the stronger sum over all members.

The report states “determined before the result,” but does not state sigma-field measurability. It
does not state that `R_i` is history-measurable. Those are not cosmetic additions: they are what
permit the indicator to be pulled through the conditional expectation.

### 5.3 Tower-property step

With the missing premises supplied, the clean identity is

```text
P(V_i | A_F)
 = E[ 1_{R_i}
      E[1_{P_i ∩ W_i} | mathcal H_{i-1}, A_F]
      | A_F ].
```

On the event `R_i`, history-measurability makes conditioning additionally on `R_i` redundant. The
report's formula can then be read as a shorthand version of the same identity. Without
`R_i ∈ mathcal H_{i-1}`, the displayed equality does not follow.

The expectations in the report also omit the explicit `| A_F` decoration. That is tolerable prose
notation only after the conditional probability space has been declared; in a load-bearing theorem
it should be written.

### 5.4 Predictability of the cap

“Chosen early” is insufficient. `alpha_i` must be a predictable/history-measurable rule. A timestamp
alone cannot prove that the cap did not depend on information outside the declared filtration, and
an author-written field cannot establish predictability. The source ledger uses the phrase
“measurable before outcome,” but the primary theorem should carry the formal premise itself.

### 5.5 Pathwise budget feasibility

The pathwise constraint is achievable. Fixed `delta_F/3` caps satisfy it, and the report's default
no-refund table makes clear that early unused allocations do not become free wealth later. More
adaptive allocation is possible only if every branch reserves enough mass for all possible future
choices. The report does not treat the constraint as free; its examples are conservative.

This is a strength. The problem is formal statement, not feasibility.

### 5.6 The “equivalent theorem” clause

The exact conditional premise is a sufficient theorem. “Or an equivalent uniform/selection-aware
theorem” is not an identified equivalence class. It could mean:

- a single simultaneous theorem uniform over the selector menu;
- a closed e-process under optional continuation;
- sample splitting with selector-independent evaluation data;
- a conditional e-value sequence;
- a selective-inference construction; or
- an unsupported `anytime_valid` label.

Those objects have different premises and targets. The phrase therefore cannot serve as an
acceptance test, registry theorem profile, verifier rule, or INT-R9 citation. It is acceptable as an
open-research pointer only if removed from the theorem's disjunctive premise and replaced by “any
other theorem must be stated and audited independently.”

### 5.7 Substantive conclusion

Once formalized, the report's qualitative conclusion is exactly right:

- adaptation is not intrinsically impossible;
- predictable spending alone does not protect an outcome-selected later procedure; and
- a fixed-procedure local theorem cannot be invoked after the procedure was selected using earlier
  family outcomes unless the theorem is valid for that selector/history.

The live registry's relevant owner-theorem profile is unavailable
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). Therefore the
current INT-R9 repair policy has no numeric family theorem even apart from the sharpness error.

### 5.8 Findings

#### INT-R10-C-001 — Theorem B omits the measurable premises needed for its tower step

- **Severity:** `material`
- **Disposition:** state a filtered probability space; require both the cap/selected procedure and
  `R_i` to be `mathcal H_{i-1}`-measurable; write expectations conditional on `A_F`; state the
  non-null/regular-conditional convention.
- **Why actual:** the displayed equality does not follow from “chosen before the result” alone.

#### INT-R10-C-002 — “Equivalent uniform/selection-aware theorem” is an unbounded escape clause

- **Severity:** `material`
- **Disposition:** remove it from the proved theorem. Record alternative theorem families as open
  options, each requiring its own exact target, assumptions, owner profile, proof, and falsifier.
- **Why actual:** the present phrase can absorb the entire adaptive-validity burden and is not
  verifier-reproducible.

#### INT-R10-C-003 — The pathwise allocation discipline is feasible and honestly conservative

- **Severity:** `commendation`
- **Disposition:** preserve fixed caps and no-refund as one safe governance option; continue to
  label recycling as requiring a separate theorem.

#### INT-R10-C-004 — The qualitative adaptive-continuation boundary is correct

- **Severity:** `commendation`
- **Disposition:** preserve after repairing the formal statement.

---

## 6. Formal verdict table

| Result | Abstract validity | Pinned-premise validity | Audit verdict |
| --- | --- | --- | --- |
| Theorem A: weighted union under prospective local caps | Valid | Premises not implemented | Preserve as conditional theorem |
| Abstract sharpness from only `P(V_i) <= delta` | Valid | Deliberately ignores stronger live information | Preserve only with explicit coarse-information qualifier |
| Current-source corollary `3 * delta`, sharp at `3/100` | Invalid/over-broad | Contradicted by exact schedule/class structure | **Blocking** |
| Theorem B sufficient conditional branch | Valid after measurable premises are added | Relevant owner theorem unavailable | Material revision |
| “Equivalent uniform/selection-aware theorem” branch | Not a theorem | No registry/verifier identity | Material revision |
| “Adaptation is not intrinsically impossible” | Correct | Capability absent today | Preserve |

## 7. What INT-R9 may rely on now

INT-R9 may safely rely on:

- the exact family event `union_i(R_i ∩ P_i ∩ W_i)`;
- the conditional union theorem under genuine owner-enforced local caps;
- the fact that the union proof needs no common null, exchangeability, or independence;
- the fact that the baseline has distinct canonical scopes and no canonical family projection;
- the pre-execution/predictability requirement; and
- the need for a selector-valid local theorem if repair is outcome-dependent.

INT-R9 must wait for revision before relying on:

- `3 * delta` or `3/100` as the best or sharp pinned-source bound;
- equal `1/300` caps as a mathematically necessary remedy;
- the mandatory negative control's `allocated=3/100` probability interpretation;
- Theorem B's present displayed proof without measurable premises; or
- the statement that all eight R1 requirements are closed.

Until those revisions are independently verified, the current runtime remains blocked from a
family-wise numeric promotion claim, but INT-R10 cannot be used to explain that block by a sharp
`3 * delta` theorem.
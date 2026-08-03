---
title: INT-R10 — Orientation Error Ledger
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
  - independent verification of the repository orientation supplied to INT-R10
  - exact set-level census of the pinned confidence-ledger registry and schedule inputs
  - identification of false, stale, materially incomplete, or misleading orientation facts
  - distinction between a root-level delta policy and the exact schedule envelope actually executable in a scope
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, or database contract
  - canonical owner appointment
  - authority grant or capability claim
  - benchmark passage
  - permission to promote a PolicyOS design
  - replacement for a canonical family projection
  - assertion that a cross-scope public risk claim is implemented
---

# INT-R10 — Orientation Error Ledger

## 1. Method

Every supplied orientation fact was checked against baseline
`978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d`. Set-valued facts were enumerated rather than inferred
from one sampled row. The audit used:

- exact source ranges in `promotion_sequence.py` and `confidence_ledger.py`;
- the complete 232-line `confidence_ledger.toml` registry;
- exact `Fraction` arithmetic over all schedule profiles and all fifteen expanded obligation
  classes;
- repository-wide searches for the three proposed cross-scope tokens;
- the frozen N11 contract and its real/conformance projections; and
- the proving-ground and GY-N11 limitation records.

The orientation was mostly accurate. Its load-bearing arithmetic summary was not. The phrase
“three fresh scopes, therefore only `3 * delta`” discards exact schedule and obligation-weight
structure that is part of the pinned canonical owner. That omission propagated directly into the
audited research result.

---

## 2. Set-level registry census

### 2.1 Full-file facts

`policy-engine/architecture/production_quality/confidence_ledger.toml` ends at line 232. A request
for lines 225–240 returns exactly the eight final lines 225–232 and no further content. The policy
block at lines 1–6 declares

```text
delta = 1/100
conditionality = obligation completeness + validator soundness
```

and lines 8–16 declare two schedule profiles:

| Profile | Kernel | Mass |
| --- | --- | ---: |
| `default_basel_square` | `basel_square_v1` | `1` |
| `half_mass_basel_square` | `basel_square_v1` | `1/2` |

### 2.2 Proof-profile census

The complete proof-profile set is:

| Proof kernel | Number of proof profiles | Profiles |
| --- | ---: | --- |
| `closed_constant_unit_e_process_v1` | 1 | `closed_constant_unit_e_process` |
| `owner_theorem_unavailable_v1` | 1 | `owner_theorem_unavailable` |
| `deterministic_owner_v1` | 1 | `deterministic_owner` |
| `ineligible_v1` | 2 | `bayesian_credible_interval_ineligible`, `fixed_time_ineligible` |

The supplied “two ineligible, one unavailable, one deterministic, one e-process” statement is
therefore exact **at proof-profile level**.

### 2.3 Instrument census

The same wording is not an instrument count. The complete thirteen-instrument set maps as follows:

| Proof-kernel disposition | Instrument count | Instruments |
| --- | ---: | --- |
| constant-unit e-process conformance | 1 | `constant_unit_e_process` |
| owner theorem unavailable | 4 | owner-verified confidence sequence, e-value, e-process, sequential test |
| deterministic owner | 2 | deterministic owner proof, deterministic refusal certificate |
| ineligible | 6 | Bayesian interval, fixed-time interval, causal-sensitivity metric, online-FDR controller, empirical confidence proxy, split conformal interval |

This fuller census strengthens, rather than weakens, the “no useful probabilistic promotion path”
orientation. It also prevents a later reader from mistaking five proof profiles for five live
instruments.

### 2.4 Obligation partition and exact weights

The seven configured pools total exactly one and expand to fifteen typed classes:

| Pool | Pool weight | Members | Expanded member weight |
| --- | ---: | --- | ---: |
| `value` | `1/5` | normative, value | `1/10` each |
| `ground` | `3/20` | syntax, type, slot, param | `3/80` each |
| `id` | `1/5` | effect, identification, measurement | `1/15` each |
| `cal` | `3/20` | calibration | `3/20` |
| `data` | `1/10` | data | `1/10` |
| `eval` | `1/10` | implementation, eval_safety | `1/20` each |
| `mc` | `1/10` | coupling, equilibrium | `1/20` each |

The maximum expanded class weight is `3/20`, attained by `calibration`.

### 2.5 Exact arithmetic transcript

The audit recomputed the registry using `Fraction` values, not decimal approximations. The
programmatic output was:

```text
proof_kernel_counts = {
  closed_constant_unit_e_process_v1: 1,
  deterministic_owner_v1: 1,
  ineligible_v1: 2,
  owner_theorem_unavailable_v1: 1
}
schedule_kernel_counts = {basel_square_v1: 2}
schedule_masses = [1, 1/2]
pool_weight_sum = 1
expanded_class_weight_sum = 1
class_count = 15
max_class_weight = calibration: 3/20
delta = 1/100
basel_coefficient = 76614/126025
ordinal_zero_max_spend_ratio_to_delta = 114921/1260250
per_scope_total_spend_ratio_to_delta < 3/20
three_scope_total_spend_ratio_to_delta < 9/20
```

The last two lines are consequences of the actual source formula, not registry metadata:

```text
alpha_t
  = delta * obligation_weight(q_t) * schedule_mass
    * (76614/126025) / (t+1)^2.
```

Because the ledger has one global executed-check ordinal in each scope and because
`76614/126025 < 6/pi^2`, every path through one mass-one scope satisfies

```text
sum_t alpha_t < delta * max_q obligation_weight(q) = (3/20) * delta.
```

Three such scopes satisfy a source-level union envelope strictly below `(9/20) * delta`. This does
not create a live family projection, but it refutes the orientation's claim that `3 * delta` is the
only bound available after retaining all pinned source structure.

---

## 3. Orientation fact ledger

| ID | Supplied fact | Verification | Verdict |
| --- | --- | --- | --- |
| O-01 | `confidence_risk_scope_for_problem()` is the only admissible N11 scope for one N9 problem and uses `design-problem:<design_problem_id>`. | `policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`. | confirmed |
| O-02 | `ConfidenceRiskBudgetScope` is one stable non-resettable risk budget. | Class docstring and `scope_id` derivation at `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`. | confirmed |
| O-03 | Ordinals and prior spend are computed only from the current scope. | `start_check()` at `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1368`. | confirmed |
| O-04 | `cross_scope`, `family_wise`, and `parent_scope` occur nowhere in the ledger. | Three exact token searches over `confidence_ledger.py` returned no match. | confirmed |
| O-05 | Registry has 232 lines; proof-profile counts are 2/1/1/1 and two Basel schedules. | Full-file and set census in §2. | confirmed, with proof-profile-level qualifier |
| O-06 | Live policy delta is exactly `1/100`. | Registry lines 1–6 and frozen contract rational pair. | confirmed |
| O-07 | Budget arithmetic uses `Fraction`; Basel-square uses a certified rational lower coefficient; obligation pools must totally partition and total one. | `confidence_ledger.py:20-52`, `250-390`, `3998-4025`. | confirmed |
| O-08 | The proving ground is 0 of 13, `useful_design_rate = 0`, and D3.8 is unbuilt. | `universal-policy-design-system-vision-and-organizing-rules.md:390-398`. | confirmed |
| O-09 | GY-N11's useful probabilistic path has essentially never run on real data. | Frozen contract has deterministic real evidence rows and one constant-unit, non-promotable conformance e-process; registry useful profiles are unavailable/ineligible. | confirmed |
| O-10 | Three fresh scopes imply that the only generic pinned-source family statement is `3 * delta`. | Root-level policy alone gives that coarse union statement, but the live owner also exposes exact per-check schedules, one global ordinal, and maximum class weight `3/20`; those imply a strictly smaller prospective envelope. | **materially misleading / false as a complete pinned-source claim** |
| O-11 | Each ordinal-zero scope receives a “fresh delta.” | Each root receives a fresh `budget_delta`, but ordinal zero receives only a scheduled fraction. The largest possible ordinal-zero spend is about `0.091189 * delta`. | imprecise; minor if read as root budget, material when used as event probability |

---

## 4. Detailed source verification

### 4.1 Scope constructor

The source returns a new `ConfidenceRiskBudgetScope` whose identity contains:

```text
owner_scope_key = design-problem:<binding.design_problem_id>
owner_projection_hash = binding.problem_content_hash
```

The docstring says it is the only admissible N11 risk scope for one N9 problem binding. Distinct
problem IDs therefore correctly yield distinct scope IDs. This fact was not stale.

### 4.2 Non-resettable local owner

The scope object is content-derived. The ledger root binds the scope, registry, schedule,
conditionality, and top-level policy delta. Tombstone/root/head checks detect reset or rebinding.
Nothing in this audit suggests weakening the scope identity.

### 4.3 Local execution sequence

`start_check()`:

1. loads the current scope's immutable chain;
2. calculates the next ordinal from current checks in that scope;
3. assigns the same value as `schedule_query_index`;
4. recomputes spend from exact delta, expanded class weight, schedule mass, coefficient, and index;
5. sums prior spend from current checks in that scope;
6. rejects local overspend; and
7. appends `started` with the full reservation before owner invocation.

The supplied scope-local description is exact. Its consequence was incompletely stated: the same
code also makes the root delta a loose ceiling, not an amount available to one attempt-level event.

### 4.4 No cross-scope symbols

Exact searches for:

```text
cross_scope
family_wise
parent_scope
```

returned no source match in `confidence_ledger.py`. The absence is real. It means there is no
canonical family declaration, projection, chronology verifier, or public owner statement. It does
not erase source-level inequalities that a later family projection could recompute.

### 4.5 Proving-ground and empirical standing

The empirical orientation is honest:

- no governed positive promotion exists;
- the constant-unit e-process is a no-power conformance witness;
- owner-verified confidence sequence/e-value/e-process/sequential profiles all refuse because the
  owner theorem is unavailable;
- current real evidence rows are deterministic; and
- no empirical family base rate is available.

No revision may replace the missing theorem with learned calibration.

---

## 5. Findings

### INT-R10-I-001 — Supplied `3 * delta` orientation discarded stronger live schedule information

- **Severity:** `blocking`
- **Disposition:** the research must not treat `3 * delta` as sharp or strongest for the pinned
  owner. Recompute the family envelope from the exact schedule, class weights, profile mass, and
  permitted execution sequence; then state separately that a canonical family projection is still
  missing.
- **Actual falsifier:** under the pinned registry and source, every scope's total scheduled
  probabilistic risk is strictly below `(3/20) * delta`; three scopes are strictly below
  `(9/20) * delta`.
- **Why this matters:** this orientation premise became the report's impossibility theorem,
  `3/100` handoff, equal-third cap design, and fixture oracle.

### INT-R10-I-002 — “Ordinal zero gets delta” conflates root policy with reserved alpha

- **Severity:** `minor`
- **Disposition:** say “fresh root-level delta policy and schedule series,” then record the exact
  ordinal-zero reservation. Do not use the shorthand in probability arithmetic.

### INT-R10-I-003 — Registry profile wording needs a level qualifier

- **Severity:** `minor`
- **Disposition:** retain the supplied five-profile count but add the thirteen-instrument census.

### INT-R10-I-004 — Remaining supplied orientation facts were accurate

- **Severity:** `commendation`
- **Disposition:** preserve the verified scope identity, owner, refusal, exact-rational,
  conditionality, empirical-state, and no-cross-scope-capability facts.

---

## 6. Consequence for the audit

The orientation errors do not make the canonical ledger wrong. They demonstrate the opposite: its
exact conservative schedule contains more mathematical structure than the research prompt and
report carried into their cross-scope argument.

The safe orientation for consolidation is:

> The pinned owner has no canonical family object or family projection, so no live public
> cross-scope bound is implemented. Nevertheless, an audit must compose the exact prospective
> schedule envelopes actually enforced by each scope before claiming `3 * delta` is sharp or that
> each scope must be recapped to `delta/3`.

That distinction is the basis of the blocking formal finding `INT-R10-B-001`.
---
title: INT-R10 — Primary-Source, Canonical-Envelope, and Transfer Ledger
status: delivered
kind: deep-research-support
research_task: INT-R10
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-revision
historical_audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: f5c9103ba390d471dd3f2806ca10e2b0f1288a08
revised_after_audit: research/int-r10-independent-audit@7f41bf8b7f6ca8e20bc885656314563de2e2cfc6
inspection_date: 2026-08-03
authoritative_for:
  - primary-source orientation for the revised INT-R10 result
  - exact programmatic census of the pinned confidence-ledger registry
  - derivation of the pinned all-path schedule envelope from live source
  - transfer and non-transfer judgments for family-wise error control, sequential design, anytime-valid inference, e-values, and selective inference
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, or serialization contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - assertion that a canonical family projection exists
  - assertion that an imported method applies without its stated assumptions
research_only: true
---

# INT-R10 — Primary-Source, Canonical-Envelope, and Transfer Ledger

## 1. Purpose and transfer standard

The target event is:

> at least one reached member of an exact governed PolicyOS family falsely produces a canonical
> promotion, with stop-on-first-positive reporting.

A source transfers only when its guarantee can be rewritten over that event without silently
importing a common estimand, common null, exchangeability, independence, valid p-values that do not
exist, a calibrated base rate, or one accumulating data stream.

This ledger keeps four layers separate:

1. **event accounting** — composition of valid upper bounds on heterogeneous authority-error
   events;
2. **canonical local allocation** — the exact reservations and all-path envelope imposed by the
   pinned confidence owner;
3. **family custody** — evidence that exact membership, roots, current heads, chronology, and
   assumptions are complete and current; and
4. **power improvements** — methods requiring additional statistical objects or dependence
   assumptions.

The revised result accepts the first two as mathematics, records the third as a missing live
capability, and refuses to infer the fourth from method names.

---

## 2. Pinned repository predicates

The revised baseline is `f5c9103ba390d471dd3f2806ca10e2b0f1288a08`.

- N9 derives one canonical scope per design-problem binding
  (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
- Each scope has one stable root-level policy and local immutable history
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`,
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`).
- The registry expands pool weights equally over the typed members of each pool
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:405-419`).
- The next ordinal, exact reservation, and prior-spend check use the current scope's history
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`).
- The `started` reservation is durably appended before owner invocation
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1356-1382`).
- Exact spend is recomputed under the Basel-square kernel
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`).
- The live root policy delta is `1/100`; schedule masses are `1` and `1/2`
  (`policy-engine/architecture/production_quality/confidence_ledger.toml:1-16`).
- No live family declaration, chronology verifier, current-head aggregate projection, or public
  owner statement exists
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).
- INT-R9 permits general implementation repair between members
  (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
- INT-R1 keeps probability conditional on declared obligation coverage and validator soundness
  (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-79`).
- The project has no governed positive promotion history from which to calibrate a family model
  (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

The gap is missing family custody and reproduction, not a defect in per-problem scope identity
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 3. Programmatic registry census

### 3.1 Enumeration method

The revision reran this exact-rational census against the complete live registry:

```python
from collections import Counter
from fractions import Fraction
from pathlib import Path
import tomllib

path = Path("architecture/production_quality/confidence_ledger.toml")
registry = tomllib.loads(path.read_text(encoding="utf-8"))

for key in (
    "schedule_profiles",
    "obligation_pools",
    "proof_profiles",
    "instruments",
    "certificate_class_routes",
):
    print(key, len(registry[key]))

expanded = {}
for pool in registry["obligation_pools"]:
    pool_weight = Fraction(pool["weight"]["numerator"], pool["weight"]["denominator"])
    member_weight = pool_weight / len(pool["obligation_classes"])
    for obligation_class in pool["obligation_classes"]:
        expanded[obligation_class] = member_weight

print("schedule_ids", [item["profile_id"] for item in registry["schedule_profiles"]])
print("proof_profile_ids", [item["profile_id"] for item in registry["proof_profiles"]])
print("instrument_ids", [item["instrument_id"] for item in registry["instruments"]])
print("route_ids", [item["certificate_class"] for item in registry["certificate_class_routes"]])
print("proof_kernel_counts", Counter(item["proof_kernel_id"] for item in registry["proof_profiles"]))
print("pool_weight_sum", sum(
    Fraction(item["weight"]["numerator"], item["weight"]["denominator"])
    for item in registry["obligation_pools"]
))
print("expanded_class_weight_sum", sum(expanded.values()))
print("max_expanded_class_weight", max(expanded.items(), key=lambda item: item[1]))
```

### 3.2 Reproduced output

```text
registry_line_count = 232
schedule_profiles = 2
obligation_pools = 7
proof_profiles = 5
instruments = 13
certificate_class_routes = 6

schedule_ids =
  default_basel_square
  half_mass_basel_square

proof_profile_ids =
  closed_constant_unit_e_process
  owner_theorem_unavailable
  deterministic_owner
  bayesian_credible_interval_ineligible
  fixed_time_ineligible

instrument_ids =
  constant_unit_e_process
  owner_verified_confidence_sequence
  owner_verified_e_value
  owner_verified_e_process
  owner_verified_sequential_test
  deterministic_owner_proof
  deterministic_refusal_certificate
  bayesian_credible_interval
  fixed_time_confidence_interval
  causal_sensitivity_e_value
  ddm_online_fdr_controller
  foundry_empirical_confidence_sequence
  split_conformal_interval

route_ids =
  n8_fixed_time_calibration_candidate
  n8_data_trust_promotion_candidate
  owner_acquisition_route
  estimand_binding_refusal
  owner_data_gap
  admission_passport

proof_kernel_counts =
  closed_constant_unit_e_process_v1: 1
  deterministic_owner_v1: 1
  ineligible_v1: 2
  owner_theorem_unavailable_v1: 1

pool_weight_sum = 1
expanded_class_weight_sum = 1
max_expanded_class_weight = calibration: 3/20
```

The set ranges are:

- schedules: `confidence_ledger.toml:8-16`;
- pools: `:18-51`;
- proof profiles: `:53-95`;
- instruments: `:96-172`; and
- certificate routes: `:174-232`.

Five proof profiles are therefore not an instrument inventory. The thirteen instruments map as:

| Disposition | Count | Instruments |
| --- | ---: | --- |
| constant-unit conformance e-process | 1 | `constant_unit_e_process` |
| owner theorem unavailable | 4 | owner-verified confidence sequence, e-value, e-process, sequential test |
| deterministic owner | 2 | owner proof, deterministic refusal certificate |
| ineligible | 6 | Bayesian interval, fixed-time interval, causal-sensitivity metric, online-FDR controller, empirical confidence proxy, split conformal interval |

This complete census strengthens the negative empirical result: the registry contains no useful
probabilistic promotion path. It does not change the missing family-custody standing
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 3.3 Expanded obligation-class weights

| Pool | Pool weight | Classes | Expanded weight per class |
| --- | ---: | --- | ---: |
| `value` | `1/5` | normative, value | `1/10` |
| `ground` | `3/20` | syntax, type, slot, param | `3/80` |
| `id` | `1/5` | effect, identification, measurement | `1/15` |
| `cal` | `3/20` | calibration | `3/20` |
| `data` | `1/10` | data | `1/10` |
| `eval` | `1/10` | implementation, eval_safety | `1/20` |
| `mc` | `1/10` | coupling, equilibrium | `1/20` |

The maximum is `3/20`, not a pool-level maximum copied without expansion.

---

## 4. Canonical envelope derivation

### 4.1 Per-check law

The source defines

```text
c_B = 76614/126025 < 6/pi^2
```

and, for probabilistic local ordinal `t`,

```text
alpha_t = delta * w(q_t) * M * c_B / (t+1)^2,
```

where `w(q_t)` is the expanded class weight and `M` is schedule mass
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:20-52`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3998-4015`).

### 4.2 All-path local envelope

The class sequence may be selected adaptively from prior local history. That does not defeat the
bound because every path satisfies `w(q_t) <= 3/20`:

```text
sum_t alpha_t
  <= delta * M * (3/20) * c_B * sum_t 1/(t+1)^2
  =  delta * M * (3/20) * c_B * pi^2/6
  <  delta * M * (3/20).
```

The strict final step uses the certified downward coefficient. This is prospective and pathwise;
it is not a statement about realized low spend.

### 4.3 From checks to one member

The N11 design requires the selected local theorem to establish the protected false-claim bound
conditional on prior local history, and defines the good event as the intersection of executed
probabilistic good events
(`policy-engine/docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:120-151`,
`policy-engine/docs/superpowers/plans/2026-07-20-gy-n11-honest-confidence-ledger.md:235-248`).
For promotion-role checks, false member promotion must be contained in the union of those false-
claim events under the maintained assumptions. Therefore the member event inherits the all-path
schedule envelope.

This bridge remains conditional on local theorem soundness, obligation completeness, and validator
soundness. Accounting does not manufacture those premises.

### 4.4 Exact family union

For an exact family of scopes `s in F`,

```text
P(V_F | A_F)
  <= sum_s P(V_s | A_F)
  <  sum_s delta_s * M_s * 3/20.
```

For the exact current three-scope, mass-one, common-delta case, the right-hand side is below
`(9/20) * delta`, and at the live policy value it is below `9/2000`.

That mathematical result does not establish live family eligibility. The owner still cannot attest
that the scope set is complete, current, chronologically coherent, and free of omitted positives
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 4.5 Abstract sharpness after coarsening

If one deliberately discards the schedule, class weights, masses, ordinals, and executable-profile
restrictions and retains only marginal statements

```text
P(V_i | A_F) <= b_i,
```

then mutually disjoint events of probabilities `b_i` attain `sum_i b_i`. The union bound is sharp
for that **coarsened information state**. It is not a source-sharpness claim about the pinned owner.

---

## 5. Primary-source transfer ledger

| ID | Primary source | Object and assumptions | Transfer to INT-R10 | Non-transfer / pinned limit |
| --- | --- | --- | --- | --- |
| S01 | Holm, “A Simple Sequentially Rejective Multiple Test Procedure,” 1979, [DOI 10.2307/4615733](https://doi.org/10.2307/4615733) | finite family of valid p-values; step-down strong FWER | possible future family procedure | no canonical PolicyOS p-value family or step-down owner (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`) |
| S02 | Pocock, “Group Sequential Methods in the Design and Analysis of Clinical Trials,” 1977, [DOI 10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191) | repeated looks at one accumulating comparison under paper's model | early stopping belongs to one controlled procedure | heterogeneous PolicyOS problems are not one information stream |
| S03 | O'Brien and Fleming, “A Multiple Testing Procedure for Clinical Trials,” 1979, [DOI 10.2307/2530245](https://doi.org/10.2307/2530245) | fixed maximum analyses and joint statistic model | aggregate-procedure lesson | no direct boundary across different problems or implementations |
| S04 | Lan and DeMets, “Discrete Sequential Boundaries for Clinical Trials,” 1983, [DOI 10.1093/biomet/70.3.659](https://doi.org/10.1093/biomet/70.3.659) | information-time alpha spending in one sequential experiment | predictable allocation and cumulative accounting | local Basel schedule is already scope-specific; no family information time |
| S05 | Tian and Ramdas, “Online Control of the Familywise Error Rate,” 2021, [DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381), [arXiv:1910.04900](https://arxiv.org/abs/1910.04900) | sequential valid p-values; predictable allocation; stronger methods use independence/local dependence | supports predictable bounded family allocation | no live cross-scope p-value controller or family owner (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`) |
| S06 | Howard et al., “Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences,” 2021, [DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991) | specified process, filtration, estimand, time-uniform construction | local certificate must match actual filtration | does not validate a repaired procedure selected after earlier family outcomes |
| S07 | Howard et al., “Time-Uniform Chernoff Bounds via Nonnegative Supermartingales,” 2020, [DOI 10.1214/18-PS321](https://doi.org/10.1214/18-PS321) | valid supermartingale/sub-psi process and filtration | explains history-conditional local validity | no theorem for arbitrary post-outcome procedure selection |
| S08 | Ramdas, Grunwald, Vovk, and Shafer, “Game-Theoretic Statistics and Safe Anytime-Valid Inference,” 2023, [DOI 10.1214/23-STS894](https://doi.org/10.1214/23-STS894) | predictable strategies and valid e-process/CS conditions | supports the filtered adaptive premise | an `anytime_valid` label is not selector-validity evidence |
| S09 | Vovk and Wang, “E-values: Calibration, Combination, and Applications,” 2021, [DOI 10.1214/20-AOS2020](https://doi.org/10.1214/20-AOS2020) | e-values for a named null; averaging for one null under arbitrary dependence | e-values can merge when target aligns | one-null averaging is not strong control of any false authority promotion |
| S10 | Vovk and Wang, “Merging Sequential E-values via Martingales,” 2020, [arXiv:2007.06382](https://arxiv.org/abs/2007.06382) | conditional sequential e-validity or explicit independence; correct merger target | product/martingale route possible under its conditions | current registry supplies no useful cross-scope sequence or merger theorem |
| S11 | Vovk and Wang, “True and False Discoveries with Independent and Sequential E-values,” 2020, [arXiv:2003.00593](https://arxiv.org/abs/2003.00593) | independent or sequential e-values plus a family criterion | confirms multiplicity methods can exist | objects and owner are absent |
| S12 | Fithian, Sun, and Taylor, “Optimal Inference After Model Selection,” [arXiv:1410.2597](https://arxiv.org/abs/1410.2597) | defined statistical model and selection event | selection must enter claim meaning | does not supply a PolicyOS family owner or population-validity theorem |
| S13 | Sidak, “Rectangular Confidence Regions for the Means of Multivariate Normal Distributions,” 1967, [DOI 10.1080/01621459.1967.10482935](https://doi.org/10.1080/01621459.1967.10482935) | multivariate-normal rectangle inequality | verified Gaussian structure could justify conservative product-style regions | repository has no cross-problem Gaussian model (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`) |

### 5.1 Independent product versus Gaussian rectangle

For precision:

- **Independent tests:** exact product calculations require independence of the relevant component
  events or valid independent p-values.
- **Sidak 1967:** the conservative rectangle result is tied to multivariate-normal structure.

Neither may be generalized to arbitrary positive dependence, and neither is represented by current
PolicyOS family artifacts.

### 5.2 E-value disposition

“Not automatic” is not an under-claim. A future route needs:

- target-aligned local e-values;
- a declared null/error polarity;
- conditional sequential validity or verified independence as required;
- a specified family criterion;
- a repository-owned merger verifier; and
- live family custody.

The current registry instead maps four owner-verified sequential/e-value instruments to an
unavailable theorem profile.

---

## 6. Assumption and capability ledger

| Premise | Why required | Revised standing |
| --- | --- | --- |
| Exact family membership/order | defines the union and prevents substitution | research criterion established; live family declaration missing (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`) |
| Exact canonical scope derivation | preserves per-problem ownership | implemented |
| Root/registry/schedule identity | determines `delta_s`, mass, weights, and coefficient | implemented locally; not aggregated as a family |
| Exact check reservations | replaces root-budget shorthand | implemented and recomputable |
| Check-to-member false-promotion implication | accounting cannot invent local validity | conditional on valid local theorem and validator soundness |
| Cross-scope exact sum | gives mathematical family envelope | established for an exact declared family in §4 |
| Complete chronology/current heads | prevents omitted terminals and stale evidence | live family verifier missing (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`) |
| Fixed member plans or adaptive selector theorem | prevents post-outcome procedure choice from using a fixed theorem | fixed theorem available; useful adaptive owner theorem unavailable |
| INT-R1 assumptions | preserves relative coverage boundary | mandatory and not discharged |
| One canonical owner | prevents P27/P28 duplication | required; no second owner proposed |

A family projection remains a **future closure criterion**, not a live capability
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 7. Carried conclusions

1. The fixed-family weighted-union theorem is valid.
2. Abstract disjoint-event sharpness is valid only after deliberately discarding canonical
   schedule information.
3. The exact pinned local envelope is below `delta_s * mass_s * 3/20`.
4. An exact three-member mass-one family is mathematically below `(9/20) * delta` under the named
   assumptions.
5. The arithmetic result does not create family custody or a public owner statement.
6. No second ledger, parent risk scope, or weakened problem identity is needed.
7. Outcome-dependent repair has no current numeric family theorem.
8. E-values remain a possible future instrument family, not an automatic answer.
9. No empirical calibration route exists.
10. `GY-GAP2` remains `contract_missing` until family membership, chronology, current heads,
    aggregate recomputation, consumer projection, and correction are behaviorally wired
    (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

The revised result is therefore mathematically accepted in a narrow scope while the runtime family
capability remains blocked.
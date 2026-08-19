---
title: INT-R10 — Family-wise Risk Composition over Canonical Confidence Scopes
status: delivered
kind: deep-research
research_task: INT-R10
result_type: accepted_narrow_scope
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-revision
historical_audited_commit: 317fc9c36e710ac75634096c4d14a714b8bff504
current_repository_commit: f5c9103ba390d471dd3f2806ca10e2b0f1288a08
revised_after_audit: research/int-r10-independent-audit@7f41bf8b7f6ca8e20bc885656314563de2e2cfc6
inspection_date: 2026-08-03
authoritative_for:
  - fixed-family weighted-union theorem over reached-member false-promotion events
  - exact canonical-source schedule envelope at the pinned repository baseline
  - separation of abstract marginal-bound sharpness from canonical-source sharpness
  - formal adaptive-continuation theorem boundary on a filtered conditional probability space
  - research-level closure criteria for a confidence-ledger-owned family declaration and aggregate projection
  - bounded claim language that INT-R9 may quote without restoring a numeric adaptive-family claim
may_not_use_for:
  - production implementation authorization
  - final code, wire, schema, package, database, or serialization contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - assertion that a live family declaration, chronology verifier, aggregate current-head projection, or public owner statement exists
  - assertion that outcome-dependent repair currently has a numeric family theorem
  - unconditional claim outside declared obligation sets and maintained assumptions
  - population performance, external validity, legal compliance, institutional competence, or production readiness
research_only: true
---

# INT-R10 — Family-wise Risk Composition over Canonical Confidence Scopes

## Executive Finding

**Result: `accepted_narrow_scope`. Current repository capability: `blocked`.**

The independent audit preserved the central theorem and refuted its former application to the
canonical owner. This revision keeps the theorem, replaces the arithmetic, and narrows the live
claim.

Three conclusions now stand separately.

1. **Fixed-family theorem.** For an exact governed family, let `V_i` be the event that reached
   member `i` falsely produces a canonical promotion. If every member has a valid local bound
   `P(V_i | A_F) <= b_i` under the same named maintained-assumption event `A_F`, every `b_i` is
   fixed and enforced before member execution, and `sum_i b_i <= delta_F`, then
   `P(union_i V_i | A_F) <= delta_F`. This is Boole's inequality. It requires no common null,
   common estimand, exchangeability, or independence.

2. **Pinned canonical envelope.** The live confidence owner exposes more information than one
   root-level policy ceiling per scope. Every probabilistic reservation is

   ```text
   alpha_t
     = delta
       * expanded_class_weight(q_t)
       * schedule_mass
       * (76614 / 126025)
       / (t + 1)^2.
   ```

   The scope has one global executed-check ordinal; the coefficient is strictly below `6/pi^2`;
   schedule mass is at most one; and the maximum expanded class weight in the complete registry is
   `3/20`, attained by `calibration`. Consequently, for any adaptive sequence of executed classes
   in one current-registry scope,

   ```text
   sum_t alpha_t
     <= delta * schedule_mass * (3/20)
        * (76614/126025) * sum_t 1/(t+1)^2
     <  delta * schedule_mass * (3/20).
   ```

   For an exact three-member family whose three roots use the current mass-one profile and common
   pinned policy delta, the mathematical union envelope is strictly below `(9/20) * delta`. At the
   live `delta = 1/100`, it is strictly below `9/2000` (`0.0045`). This is a prospective
   all-path envelope, not observed spend and not an empirical estimate.

3. **Adaptive continuation.** Outcome-dependent repair is not covered by the fixed-family theorem.
   A numeric adaptive result requires history-measurable reach, procedure selection, and allocation,
   plus a local almost-sure guarantee valid for the procedure actually selected from that history.
   The live registry supplies no such useful owner theorem. INT-R9's adaptive sequence must
   therefore continue to withdraw every numeric family-wise claim.

The source-level envelope does **not** create a live PolicyOS capability. The repository still has
no canonical family declaration, chronology verifier, aggregate current-head projection, or public
owner statement. `GY-GAP2` is therefore unchanged and real, but it is a missing declaration,
projection, and reproduction capability—not an arithmetic impossibility
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`). The earlier
error was safe-directional: the live schedule is more conservative than the root-budget shorthand
implied, never less.

The exact sibling-document sentence is:

> For a fixed exact family, valid prospective local bounds compose by weighted union; at the pinned
> PolicyOS owner the exact Basel schedule gives each current-registry scope an all-path envelope
> below `delta * schedule_mass * 3/20`, so three mass-one scopes are below `(9/20) * delta`, but no
> canonical family declaration or aggregate projection exists, and outcome-dependent repair has no
> current numeric theorem.

Supporting artifacts:

- [Primary-source and transfer ledger](int-r10/source-and-transfer-ledger.md)
- [Fixture and semantic-handoff sketch](int-r10/fixture-and-artifact-sketch.md)
- [Audit-revision disposition ledger](int-r10/revision-ledger.md)

---

## 1. Task And Project Fit

### 1.1 Exact research question

The question is:

> When PolicyOS makes a risk-bounded claim over several design problems, attempts, or a
> precommitted sequence, what composition is available over the canonical per-problem confidence
> scopes, and what may honestly be claimed?

INT-R9 needed a family statement for a three-slot stop-on-first-positive sequence. Its audit found
that N9 derives a distinct scope for every design problem and required eight properties before any
family claim could be accepted
(`policy-engine/docs/research/policy-operations/audits/int-r9/int-r9-recommended-revision.md:30-105`).
INT-R10 answers the owner-level composition question. It does not own INT-R9's case authorship,
sealing, panel, materiality, stopping, publication, or repair policy.

### 1.2 Exact controlled event

For ordered family `F = (1, ..., m)`, define:

- `R_i`: member `i` is reached under the declared stopping, dispute, retry, and no-substitution
  rules;
- `P_i`: member `i` emits a canonical positive promotion terminal;
- `W_i`: that promotion is false relative to its declared obligation set and maintained
  assumptions;
- `V_i = R_i ∩ P_i ∩ W_i`; and
- `V_F = union_i V_i`.

Under stop on first canonical positive, `V_F` is exactly the event that the family's reported first
promotion is false. Earlier refused, void, disputed, or negative members remain in the chronology.
Members after a valid positive are unreached rather than erased.

The controlled quantity is false **PolicyOS authority promotion**. It is not the probability that a
useful design exists, that every obligation in the world was found, that a policy is effective, or
that an external institution acted lawfully.

### 1.3 Owner placement

The confidence ledger already owns risk scopes, exact rational allocation, theorem refusal, durable
pre-execution reservation, immutable events, canonical receipts, and N9 projections
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752`). Any future family object
must be a relation and projection over those canonical scopes inside the same owner lane. It must
not become a second ledger, parent risk scope, second promotion gate, or mutable family head.

`GY-GAP2` places the missing family capability in the confidence-ledger/N11 lane and explicitly
forbids weakening per-problem scope identity
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 1.4 Four-way boundary verdict

| Plane | Verdict | PolicyOS responsibility | Boundary retained |
| --- | --- | --- | --- |
| Arithmetic and custody of PolicyOS's signed family-risk statement over its own promotion receipts | **OWN** | Bind exact family membership, scope identities, schedule/root versions, assumptions, chronology, currentness, correction, and the bounded statement. | Ownership is of PolicyOS's statement, not external truth or legal effect. |
| N9 bindings, INT-R1 declarations, certificate owners, evaluators, adjudicators, evidence sources, and implementation freezes | **INTEGRATE** | Purpose-admit, content-bind, verify, and react fail-closed when inputs change. | PolicyOS does not become the external source, evaluator, court, or implementation operator. |
| Proposed dependence models, candidate allocations, criticism, or unadmitted family groupings | **OBSERVE** | Retain as research/challenge signals; never mint a tighter authority claim from observation alone. | S0-K05 and S0-K07 remain controlling. |
| Creating legal effect, operating a policy, certifying population efficacy, or deciding institutional competence | **OUT_OF_SCOPE** | Publish only the bounded PolicyOS claim and route external acts to competent owners. | Composition does not make PolicyOS an administrator. |

The Stage-0 authority-band/candidate-band rule means missing family custody blocks only the numeric
authority claim. Candidate work may continue under an explicit limitation
(`policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:160-190`).

### 1.5 Standing

- **Research theorem and corrected source envelope:** `accepted_narrow_scope`.
- **Live family declaration/projection capability:** `blocked` / `contract_missing`.
- **Outcome-dependent repair theorem:** `blocked` / owner theorem unavailable.

This standing is narrower than implementation authorization. It says the mathematics is now
available and the canonical public capability is not
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 2. Current Repository Baseline

### 2.1 Pinned inspection

- Repository: `https://github.com/DenisKopylov/polisyos`
- Baseline branch: `main`
- Exact baseline: `f5c9103ba390d471dd3f2806ca10e2b0f1288a08`
- Revision branch: `research/int-r10-revision`
- Audited research head: `317fc9c36e710ac75634096c4d14a714b8bff504`
- Audit head: `7f41bf8b7f6ca8e20bc885656314563de2e2cfc6`
- Inspection date: `2026-08-03`

The baseline differs from the original INT-R10 baseline only in the directly relevant correction of
`GY-GAP2`. The corrected row matches the independently re-derived arithmetic in §4.4
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 2.2 Canonical per-problem scope

`confidence_risk_scope_for_problem()` remains the only admissible N11 scope for one N9 binding and
uses:

```text
owner_scope_key = design-problem:<design_problem_id>
```

(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`). Distinct problem IDs
therefore remain distinct scope IDs. Nothing in this result recommends changing that identity.

`ConfidenceRiskBudgetScope` remains the stable owner scope for one non-resettable root budget
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`). A root binds one scope
to registry, schedule profile, root `budget_delta`, conditionality, and maintained assumptions
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`).

### 2.3 Root budget is not one reservation

`start_check()` loads one scope's current events, assigns the next local execution ordinal, resolves
the expanded obligation-class weight, computes the exact schedule reservation, sums local prior
spend, and checks the root policy ceiling
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`). The reservation is
then placed in the `started` record and durably appended before owner execution
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1356-1382`).

The exact language is therefore:

> A fresh design problem obtains a fresh root-level delta policy and local schedule series; its
> ordinal-zero probabilistic check receives only the schedule reservation determined by the
> expanded class weight, profile mass, and Basel coefficient.

A root policy value must never stand in for a member-event probability or an ordinal-zero
reservation.

### 2.4 Exact registry census

Programmatic enumeration of the complete 232-line registry gives:

| Set | Count | Content summary |
| --- | ---: | --- |
| schedule profiles | 2 | both `basel_square_v1`, masses `1` and `1/2` |
| obligation pools | 7 | exact pool weights sum to `1` |
| expanded obligation classes | 15 | exact expanded weights sum to `1`; maximum `3/20` on `calibration` |
| proof profiles | 5 | one constant-unit e-process, one unavailable-theorem, one deterministic, two ineligible |
| instruments | 13 | one conformance e-process, four unavailable, two deterministic, six ineligible |
| certificate-class routes | 6 | two promotion candidates, three refusal/acquisition routes, one admission route |

The full names, script, and output are recorded in
[int-r10/source-and-transfer-ledger.md](int-r10/source-and-transfer-ledger.md). Source ranges are
`confidence_ledger.toml:1-232`; pool expansion is implemented at
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:405-419`.

### 2.5 Exact schedule law

The code uses `Fraction` and a certified coefficient:

```text
c_B = 6 * 113^2 / 355^2 = 76614 / 126025 < 6/pi^2.
```

(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:20-52`). For a probabilistic check
at local ordinal `t` and expanded class weight `w(q_t)`:

```text
alpha_t = delta * w(q_t) * mass * c_B / (t+1)^2.
```

(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3998-4015`). Receipt validation
recomputes contiguous ordinals and every exact spend row rather than trusting display decimals
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`).

### 2.6 What remains missing

No live source object declares an exact family, binds chronology across scopes, verifies current
heads as one family, or publishes an aggregate owner projection. The corrected gap is therefore
about **custody and reproducibility**, not lack of conservative arithmetic
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

The mandatory three-scope trace remains possible:

```text
slot 1 -> problem A -> root/scope A -> local ordinal zero reservation
slot 2 -> problem B -> root/scope B -> local ordinal zero reservation
slot 3 -> problem C -> root/scope C -> local ordinal zero reservation
stop on first positive
```

The trace does not violate local source rules. It also does not, by itself, prove any family
probability. A public family claim still requires canonical evidence that A/B/C are the complete
family, the relevant roots/heads are current, the exact schedule arithmetic is recomputed, and the
chronology and maintained assumptions hold.

### 2.7 Empirical state

The live registry does not provide a useful positive probabilistic promotion route. The executable
constant-unit e-process is conformance-only and cannot satisfy an obligation; owner-verified
confidence-sequence, e-value, e-process, and sequential-test instruments map to an unavailable
owner theorem; other statistical instruments are ineligible
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-172`).

The proving ground remains 0 of 13, `useful_design_rate = 0`, and D3.8 remains unbuilt
(`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).
No empirical calibration route exists.

### 2.8 Capability census

| Capability | Standing |
| --- | --- |
| Per-problem scope identity | implemented |
| Exact within-scope schedule and receipt recomputation | implemented |
| Durable reservation before owner execution | implemented |
| Typed unavailable/ineligible theorem refusal | implemented |
| Mathematical cross-scope envelope derivable for an exact declared family | established in this research |
| Canonical family declaration | missing |
| Cross-scope chronology/current-head verifier | missing |
| Aggregate public owner projection | missing |
| Useful selection-valid theorem for outcome-dependent repair | missing |

The missing rows are the substantive content of `GY-GAP2`
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

---

## 3. External Research Baseline

Detailed source-by-source dispositions are in the supporting source ledger.

### 3.1 Exact weighted union and online FWER

Boole's inequality directly composes heterogeneous event bounds. Online-FWER work confirms the
broader pattern of predictable nonnegative allocations whose pathwise total stays within a family
budget, while stronger procedures require their stated p-value and dependence conditions
([Tian & Ramdas 2021, DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381)).

The transfer is event accounting only. PolicyOS must still establish each local authority-error
bound and custody the exact family.

### 3.2 Holm

Holm's step-down procedure strongly controls family-wise error for a finite family of valid
p-values without favorable dependence
([Holm 1979, DOI 10.2307/4615733](https://doi.org/10.2307/4615733)). PolicyOS has no canonical family
of valid p-values or step-down owner. Holm remains a possible future method, not a live result.

### 3.3 Group-sequential designs

Pocock, O'Brien–Fleming, and Lan–DeMets show that repeated looks and stopping belong to one overall
procedure
([Pocock 1977](https://doi.org/10.1093/biomet/64.2.191),
[O'Brien & Fleming 1979](https://doi.org/10.2307/2530245),
[Lan & DeMets 1983](https://doi.org/10.1093/biomet/70.3.659)). Pre-allocation, cumulative accounting,
and no silent reset transfer. Their boundary formulae do not turn heterogeneous design problems
into one accumulating clinical comparison.

### 3.4 Sidak conditions, separated

Two different results must not be conflated:

- under independent component tests, the familiar product calculation gives exact family
  non-rejection probability as a product; and
- Sidak's 1967 result gives a conservative rectangle inequality under multivariate-normal
  structure, even for dependence covered by that Gaussian theorem
  ([Sidak 1967](https://doi.org/10.1080/01621459.1967.10482935)).

Neither condition is represented across current PolicyOS problem scopes. No arbitrary positive-
dependence or product correction transfers.

### 3.5 Anytime-valid inference

Confidence sequences and nonnegative supermartingales are valid relative to their declared process
and filtration
([Howard et al. 2021](https://doi.org/10.1214/20-AOS1991),
[Howard et al. 2020](https://doi.org/10.1214/18-PS321)). Optional continuation inside a valid
process is not arbitrary post-outcome selection among repaired procedures
([Ramdas et al. 2023](https://doi.org/10.1214/23-STS894)).

### 3.6 E-values

E-values can be merged under exact conditions: averaging for one null under arbitrary dependence,
products under independence or sequential conditional e-validity, and multiple-testing procedures
under their stated family criterion
([Vovk & Wang 2021](https://doi.org/10.1214/20-AOS2020),
[Vovk & Wang 2020a](https://arxiv.org/abs/2007.06382),
[Vovk & Wang 2020b](https://arxiv.org/abs/2003.00593)).

That is not an automatic heterogeneous-family solution. The current repository lacks useful
owner-verified e-values, target-aligned merger semantics, and a cross-scope verifier. “E-values are
not automatic” remains the correct repository verdict.

### 3.7 Selective inference and empirical calibration

Selection affects what the reported first passing result means
([Fithian, Sun & Taylor](https://arxiv.org/abs/1410.2597)). A prospective union event can include
stop-on-first-positive selection, but it does not establish an unbiased selected effect,
representativeness, or population validity.

Empirical weighting remains unavailable because the project has no governed positive promotion
history.

### 3.8 Transfer verdict

| Method | Revised disposition |
| --- | --- |
| Exact weighted union | transfers directly once the actual local bounds and exact family are identified |
| Canonical Basel schedule | directly determines the pinned all-path local envelope; must not be replaced by root-budget shorthand |
| Holm | possible future option with valid p-values and canonical step-down procedure |
| Independent product correction | unavailable without verified independence |
| Gaussian Sidak rectangle inequality | unavailable without a verified multivariate-normal family model |
| Group-sequential boundaries | accounting lesson only for heterogeneous problems |
| Confidence sequences/e-processes | transfer only within the valid process and filtration |
| E-value merging | not automatic; target and conditional/dependence conditions are load-bearing |
| Selective inference | meaning constraint, not current owner implementation |
| Empirical calibration | unavailable |

---

## 4. Result

### 4.1 Explicit epistemic classification

| Category | Revised result |
| --- | --- |
| **Theorem** | Fixed-family weighted union; filtered adaptive theorem under the exact history-conditional premise; exact pinned all-path schedule envelope. |
| **Empirical rule** | None. No calibration data is used. |
| **Design pattern** | Preserve every canonical scope; introduce only a prospective family relation and recomputed projection inside the same confidence owner. |
| **Governance protocol** | Exact family/order commitment, durable earlier terminals, no substitution, conservative no-refund, and explicit fixed versus adaptive standing. |
| **Impossibility result** | From coarse marginal bounds alone, no generic bound below their sum follows; this is not a sharpness claim about the pinned owner. A fixed-procedure theorem cannot validate an outcome-selected repair. |
| **Engineering convenience** | Finite family size, allocation presentation, record names, serialization, and refusal vocabulary remain unresolved implementation choices. |

### 4.2 Theorem A — fixed exact family

Let `A_F` be the named maintained-assumption event with `P(A_F) > 0`. For exact family
`F = (1, ..., m)`, suppose each reached-member false-promotion event satisfies

```text
P(V_i | A_F) <= b_i,
```

where `b_i >= 0` is fixed and enforced before member `i` executes, and

```text
sum_i b_i <= delta_F.
```

Then

```text
P(V_F | A_F)
  = P(union_i V_i | A_F)
  <= sum_i P(V_i | A_F)
  <= sum_i b_i
  <= delta_F.
```

The proof contains no common null, estimand, exchangeability, or independence. Those conditions may
still be required inside a local theorem; the union step does not erase them.

### 4.3 Abstract sharpness after deliberate coarsening

Suppose all schedule-, class-, process-, and spend-specific information is intentionally discarded,
and the only retained facts are

```text
P(V_i | A_F) <= b_i,
```

with `sum_i b_i <= 1`. A conditional probability model can choose mutually disjoint events of
probabilities `b_i`. Their union then has probability `sum_i b_i`. Therefore no generic improvement
below the sum follows from those coarse marginal statements alone.

This construction is **not** a sharpness witness for a repository that also exposes smaller
predictable reservations, expanded class weights, profile mass, a global local ordinal, and
restricted executable theorem profiles. The pinned canonical result must use that extra structure.

### 4.4 Canonical-source derivation

Fix one canonical scope `s`. Let:

- `delta_s` be the root policy delta;
- `M_s` be the root-bound schedule mass, with `0 <= M_s <= 1`;
- `q_{s,t}` be the expanded obligation class selected predictably at local executed-check ordinal
  `t`;
- `w(q)` be the expanded class weight; and
- `c_B = 76614/126025 < 6/pi^2`.

For each valid probabilistic local theorem, the owner reserves

```text
alpha_{s,t}
  = delta_s * w(q_{s,t}) * M_s * c_B / (t+1)^2.
```

The complete registry expands seven pools over fifteen classes. Its maximum is

```text
w_max = max_q w(q) = 3/20.
```

The maximum occurs at `calibration`, the only member of the `cal` pool. Therefore, on every path,
including paths that adaptively select the next class from prior local history,

```text
sum_t alpha_{s,t}
  <= delta_s * M_s * w_max * c_B * sum_t 1/(t+1)^2
  =  delta_s * M_s * w_max * c_B * pi^2/6
  <  delta_s * M_s * w_max
  =  delta_s * M_s * 3/20.
```

The first inequality is pathwise because every selected `w(q_{s,t})` is at most `w_max`. The strict
inequality follows from the certified downward coefficient. No dependence assumption is used.

Under the local owner theorem and maintained assumptions, false promotion in member `s` must be
contained in the union of the relevant executed promotion-role false-claim events. Tower property
plus the within-scope union bound therefore gives

```text
P(V_s | A_F) <= E[sum_t alpha_{s,t} | A_F]
             < delta_s * M_s * 3/20.
```

For exact family `F` of canonical scopes,

```text
P(V_F | A_F)
  <= sum_{s in F} P(V_s | A_F)
  <  sum_{s in F} delta_s * M_s * 3/20.
```

For the three-member current-registry case with common `delta` and mass-one roots,

```text
P(V_F | A_F) < (9/20) * delta.
```

At `delta = 1/100`, the right-hand side is `9/2000`. This is the corrected mathematical envelope.
It remains conditional on obligation completeness, validator soundness, local theorem soundness,
exact family membership, root/registry identity, and the check-to-promotion implication.

### 4.5 Why this does not close GY-GAP2 as a capability

The derivation answers the arithmetic question. It does not produce an owner artifact proving that:

- the named scopes are the complete family;
- their roots and current heads are canonical and current;
- no earlier terminal or unregistered positive was omitted;
- all roots use the represented registry/schedule versions;
- the exact check-level events are the ones relevant to the family promotion;
- the fixed/adaptive posture is truthful; or
- a public statement remains current after correction or source drift.

Those are custody and reproduction properties. The current repository has no family declaration,
chronology verifier, aggregate current-head projection, or public owner statement
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

A future family relation need not reduce the root delta merely to make the current three-scope
arithmetic fit below one policy delta. It must instead expose and verify the exact source-derived
envelope, while retaining the option for separately justified tighter prospective caps. No equal
cap vector is prescribed by this research.

### 4.6 Terminal effects and conservative no-refund

| Earlier member state | Family chronology criterion | Risk treatment criterion |
| --- | --- | --- |
| Preflight refusal before owner execution | retain and publish; advance only under declared rule | zero actual spend; no new member or replacement allocation is created |
| Proven deterministic infrastructure failure before result-bearing exposure | retry only the same member under a prospective deterministic rule | same root and applicable schedule history; no fresh family member |
| Owner refusal/error after `started` | retain as result-bearing terminal | reservation remains burned |
| Result-bearing void | retain; no substitution | recorded reservations remain; no outcome-dependent transfer |
| Dispute | halt until prospectively resolved | no later member obtains authority while dispute is open |
| Completed negative or grounded refusal | advance to next committed member | prior history remains visible |
| Valid positive | stop | later members are unreached |
| Unreached after positive | record as unreached | no check executes |

No-refund is a feasible conservative governance rule, not a theorem that every recycling rule is
impossible. Any recycling proposal requires a separate theorem and behavioral falsifier.

### 4.7 Theorem B — adaptive continuation on a filtered space

Let `(Omega, F, P)` be a probability space. Let `A_F in F` have positive probability, and work under
the conditional law `P_F(B) = P(B | A_F)`. Let

```text
H_0 subseteq H_1 subseteq ... subseteq H_m subseteq F
```

be the family-history filtration. Before member `i`:

1. reach indicator `R_i` is `H_{i-1}`-measurable;
2. the selected procedure `Pi_i`, including implementation, configuration, model, prompt,
   evaluator, evidence cutoff, and local theorem profile, is `H_{i-1}`-measurable;
3. nonnegative allocation `a_i` is `H_{i-1}`-measurable; and
4. the pathwise reached allocation satisfies

   ```text
   sum_i R_i * a_i <= delta_F.
   ```

Assume the local theorem is valid for the **actually selected** procedure and gives, almost surely,

```text
1_{R_i}
  * P_F(P_i intersect W_i | H_{i-1})
  <= 1_{R_i} * a_i.
```

Then, because `R_i` is history-measurable,

```text
P_F(V_i)
  = E_F[1_{R_i} * 1_{P_i intersect W_i}]
  = E_F[
      1_{R_i}
      * E_F[1_{P_i intersect W_i} | H_{i-1}]
    ]
  <= E_F[1_{R_i} * a_i].
```

Therefore,

```text
P_F(V_F)
  <= sum_i P_F(V_i)
  <= E_F[sum_i R_i * a_i]
  <= delta_F.
```

The theorem does not include an undefined alternative disjunct. Other routes—such as a uniform
menu theorem, conditionally valid e-process, selector-independent sample split, or a specified
selective procedure—might also suffice, but each is a separate theorem requiring its own event,
filtration, assumptions, owner profile, verifier, source binding, and falsifier.

### 4.8 Current adaptive result

INT-R9 permits general repair between slots, so later procedures may be selected from earlier
outcomes
(`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
The live owner does not provide the theorem in §4.7 for useful promotion instruments. Therefore:

- adaptation is not intrinsically impossible;
- predictable arithmetic alone does not validate outcome-selected repair;
- current outcome-dependent repair has no numeric family theorem; and
- candidate development may continue only without the numeric authority claim.

This withdrawal is load-bearing and must not be softened.

### 4.9 Honest claim language

**Mathematical fixed-family claim:**

> Valid reached-member bounds under one maintained-assumption event compose by weighted union.

**Pinned source-envelope claim:**

> For an exact family using the pinned confidence owner, each scope's valid probabilistic
> false-claim sequence has an all-path envelope below `delta_s * schedule_mass_s * 3/20`; family
> composition is below the sum of those scope envelopes.

**Pinned capability claim:**

> No canonical live family declaration, chronology verifier, aggregate current-head projection, or
> public owner statement exists
> (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

**Adaptive repair claim:**

> No numeric family-wise claim is available for outcome-dependent repair until the actual selector
> is covered by a canonical, verified local theorem.

### 4.10 R1 conformance regraded

| R1 requirement | Research theorem/result | Future closure criterion | Pinned capability |
| --- | --- | --- | --- |
| 1. Exact family event | **met**: `V_F = union_i(R_i ∩ P_i ∩ W_i)` | preserve event and stop rule exactly | event can be described; no family artifact exists |
| 2. Relation to N9 scopes | **met**: one member binds one recomputed canonical scope | preserve distinct scope identity | local scope derivation implemented |
| 3. No fresh unaccounted budgets | **met mathematically at envelope level**: root budgets are not event caps; exact reservations compose below the source-derived envelope | family declaration must bind complete membership, root/schedule versions, and aggregate calculation before public use | declaration and aggregate owner projection missing |
| 4. Earlier terminal effects | **met as governance result** | chronology verifier must retain refusal, void, dispute, negative, positive, and unreached states without substitution | verifier missing |
| 5. Aggregate allocation/composition | **met for the fixed exact family**: §4.4 derives the all-path scope and family envelope from live source under named assumptions | owner must reproduce the exact derivation from current roots, schedules, checks, and family membership | no canonical family projection; no useful positive probabilistic path |
| 6. Adaptive continuation | **met by narrowing plus formal theorem boundary**: §4.7 is sufficient under its measurable premises; current repair claim is withdrawn | any alternate theorem must be specified and independently verified | useful adaptive owner theorem unavailable |
| 7. Canonical owner reuse | **met**: confidence ledger remains sole risk-accounting owner | family relation must add no second head, registry, local ordinal, risk scope, or promotion decision | no extension implemented |
| 8. Live reproducibility | **not a current research capability claim** | live scope derivation, roots, current heads, exact reservations, chronology, assumptions, and source identity must be recomputed behaviorally | positive family verifier missing; negative absence is reproducible |

The mandatory trace remains unblocked as a **family-custody trace**, not as evidence of an inflated
probability. Its current failure is that no owner object proves the exact family relation or emits a
current aggregate statement
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

### 4.11 Standing after revision

`accepted_narrow_scope` is justified because:

- the fixed-family theorem is correct;
- the abstract sharpness result is now explicitly limited to deliberately coarsened marginal
  information;
- the exact pinned-source envelope is derived from live source and registry values;
- Theorem B now states its filtered-space and measurability premises;
- the current adaptive numeric claim remains withdrawn; and
- no live family capability is claimed.

The standing would revert to `blocked` if any downstream document treats the mathematical envelope
as a canonical public projection, omits maintained assumptions, or restores a numeric adaptive
claim.

---

## 5. Counterexamples And Failure Modes

1. **Root ceiling substituted for reservation.** A root `budget_delta` is read as the probability
   of one member error. The exact schedule disproves that substitution.
2. **Coarse sharpness presented as source sharpness.** Disjoint marginal events attain their sum
   only after discarding the canonical schedule and class-weight restrictions.
3. **After-the-fact low spend.** Realized spend below a threshold does not prove the owner executed
   under the represented prospective law.
4. **Family markers without family custody.** A document lists A/B/C but does not rederive scopes,
   roots, current heads, chronology, or omitted positives.
5. **Collapse several problems into one scope.** This violates canonical problem identity.
6. **Second ledger or parent risk scope.** This violates owner-first and P27/P28.
7. **Outcome-selected repair under fixed theorem.** Correct arithmetic does not establish local
   selection validity.
8. **Timestamp in place of measurability.** A cap recorded before output may still use information
   outside the declared history.
9. **Undefined alternate theorem label.** “Uniform” or “selection-aware” is accepted without a
   controlled event and verifier.
10. **Refund after an unfavorable terminal.** Unused allocation is transferred under an unproved
    recycling rule.
11. **E-value product with wrong target.** A global-null product is represented as strong control
    of any false authority promotion.
12. **Conditionality disappears.** Family arithmetic is represented as protection against unknown
    obligations or validator failure.
13. **Empirical weights from absent history.** The project calibrates a family model from no
    governed positive promotions.
14. **Strictness leaks into candidate work.** Missing authority composition is used to prohibit
    transparent candidate development.
15. **Projection mints authority.** A family display is treated as the source of local theorem
    validity or promotion.

Pattern disposition:

| Pattern | Required protection |
| --- | --- |
| P27/P28 | one confidence owner; unchanged problem scopes; no parent risk scope |
| P29/P32 | behavioral recomputation from live roots, heads, schedules, and source; no marker-only green record |
| P31 | generic family relation, not a special INT-R9 patch |
| P33 | generated substitutions, stale heads, omitted terminals, source drift, and property-removal controls |

---

## 6. Benchmark Or Fixture Proposal

The detailed fixture sketch is intentionally semantic rather than schema-complete.

### 6.1 Positive future-conformance fixture

Use three distinct problems and preserve three distinct canonical scopes. For each scope, execute a
known sequence of probabilistic reservations whose classes and schedule profile are fixed in the
fixture. The verifier must:

1. call live N9 scope derivation;
2. recompute every ordinal and exact `alpha_{s,t}` from the root-bound registry and schedule;
3. verify the reservation was durably appended before owner execution;
4. sum the exact per-scope reservations and verify the all-path source envelope;
5. bind the exact family, earlier terminals, stopping, and current heads;
6. preserve INT-R1 assumptions; and
7. refuse at the pinned baseline because no family owner projection exists.

### 6.2 Mandatory structural negative control

Run three ordinary distinct scopes with valid local histories but provide no canonical family
relation. The expected red property is:

```text
local scope accounting valid
cross-scope arithmetic independently reproducible
family membership/chronology/currentness not canonically attested
public family claim ineligible
```

The negative must not infer a probability merely by counting root policy ceilings.

### 6.3 Property-removal control

Retain all family-shaped markers while deleting one real behavior at a time:

- pre-execution reservation;
- live scope derivation;
- exact schedule recomputation;
- current-head validation;
- earlier-terminal retention;
- complete family membership; or
- maintained-assumption projection.

The verifier must go red. This preserves the audit-commended P29 test.

### 6.4 Adaptive pair

Let member 1's outcome select member 2's procedure. The negative version supplies only a theorem for
a procedure fixed independently of member 1 and must refuse. A positive version is only a future
closure criterion: it must provide a separately specified canonical theorem satisfying §4.7.

### 6.5 Fixture boundary

Passing proves only the named family-composition behavior. It does not prove local theorem
soundness on real data, world completeness, positive promotion, legal compliance, or production
readiness, consistent with S0-K16.

---

## 7. Artifact Contract Sketch

This section states semantic invariants only. It does **not** name final classes, schema versions,
package paths, serialization keys, enum values, or refusal codes.

### 7.1 Prospective family declaration — semantic role

A future owner-internal declaration must make independently visible before result-bearing family
execution:

- exact controlled event and purpose;
- ordered member identities and recomputed canonical scopes;
- root, registry, schedule, source/deployment, and local theorem identities;
- fixed member plans or explicit adaptive posture;
- stopping, dispute, retry, substitution, and allocation-disposition rules;
- maintained assumptions; and
- evidence of prospective visibility.

The declaration proposes a relation. It proves neither local certificate validity nor aggregate
eligibility.

### 7.2 Aggregate projection — semantic role

A future confidence-owner projection must recompute:

- declaration identity and prospective standing;
- live N9 scope derivation;
- canonical roots and current heads;
- exact check-level reservations and source-derived scope envelopes;
- complete chronology and registered positives;
- fixed/adaptive theorem standing;
- assumptions and conditionality; and
- aggregate family bound plus current eligibility.

It may not own a second mutable head, registry, local ordinal, replacement risk scope, local theorem
verifier route, or promotion decision.

### 7.3 Unresolved design choices

A separate owner-design task must still decide record names, package placement, serialization,
content-identity rules, reissue/suspension lifecycle, public projection vocabulary, and exact error
codes. This research does not appoint those choices.

---

## 8. Later Integration Handoff

### 8.1 Canonical owner to extend

The only owner to extend is the existing confidence ledger / N11 lane. The family capability must
be a projection over unchanged per-problem roots and receipts, not another accounting system
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`).

Minimum semantic chain:

```text
prospective exact family relation
-> live member-scope derivation
-> existing local pre-execution schedule reservations
-> canonical local receipts/current heads
-> exact cross-scope envelope recomputation
-> chronology and selector standing
-> confidence-owner aggregate projection
-> bounded consumer/public statement
-> correction, suspension, and reissue
```

### 8.2 INT-R9 handoff

INT-R9 may state:

- its controlled event is the union of reached-member false promotions;
- distinct problem scopes remain distinct;
- fixed valid local bounds compose by weighted union;
- the pinned schedule gives each scope an envelope below `delta_s * mass_s * 3/20`;
- an exact three-member mass-one family is mathematically below `(9/20) * delta` under the named
  assumptions;
- no canonical family declaration/projection exists today; and
- outcome-dependent repair has no current numeric theorem.

INT-R9 must not attach a numeric family claim to its adaptive protocol. Its Option-B withdrawal
remains correct and insulated from this revision.

### 8.3 INT-R1 and public handoff

Every member retains its own declared closure basis, cutoff, compiler/validator versions, and
unresolved remainder. Family composition does not create a universal obligation denominator or
remove the risk rider
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:35-79`).

A public projection may display only a current owner result. Projection cannot mint authority,
consistent with S0-K05 and S0-K16.

---

## 9. Promotion And Kill Rules

### 9.1 Research promotion

Consolidation may accept this revised result only if it preserves all three statements together:

1. weighted union is valid under genuine local bounds and one maintained-assumption event;
2. the pinned canonical envelope is derived from exact schedule reservations and expanded class
   weights; and
3. live family custody and adaptive repair remain blocked.

### 9.2 Later implementation preconditions

A separate implementation authorization requires owner-first semantics, prospective family
visibility, live root/current-head recomputation, exact schedule aggregation, chronology, INT-R1
interfaces, fixed/adaptive theorem standing, correction/suspension, public projection, and the §6
behavioral fixtures.

### 9.3 Kill rules

A proposal is `NO_GO` if it:

- substitutes root delta for exact reservation or event probability;
- calls a coarse marginal witness sharp for the canonical owner;
- weakens problem scope identity;
- creates a second ledger, parent scope, family ordinal, or second promotion decision;
- checks arithmetic only after execution;
- uses floats in the authority path;
- trusts supplied scopes, roots, heads, or spend rows;
- omits earlier terminals or unregistered positives;
- changes procedures or allocations after outcomes without the §4.7 premise;
- accepts an undefined theorem label;
- hides obligation/validator conditionality;
- treats a fixture pass as authority; or
- blocks candidate work merely because family authority is unavailable.

### 9.4 GY-GAP2 closure evidence

`GY-GAP2` closes only when the exact family relation, live scope/root/current-head inputs, schedule
arithmetic, chronology, consumer bridge, public/audit projection, correction path, and behavioral
fixtures form one working chain
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`). A document,
schema, or calculated inequality alone is `contract_only`.

### 9.5 Passage boundary

Passing a family fixture proves only the represented composition behavior. It carries no authority
beyond the named family, assumptions, sources, plans, theorem profiles, and current artifacts.

---

## 10. Open Questions For Consolidation

1. What minimal owner-internal relation represents exact family membership without becoming a
   parent risk scope?
2. How will the owner prove prospective visibility of family membership and fixed/adaptive posture?
3. Must the first implementation support only finite fixed families, or also predictable online
   membership?
4. Which local theorem profiles can establish the check-to-member false-promotion implication for
   real promotion evidence?
5. How should mixed root schedule masses and registry versions be handled or refused?
6. Is the all-path maximum-class envelope sufficient for the public claim, or should the projection
   expose the tighter exact path sum as well?
7. What source or root changes suspend versus invalidate the aggregate projection?
8. How are disputed and corrected members reissued without rewriting history?
9. Is conservative no-refund sufficient, or is a separately proved recycling rule worth the
   complexity?
10. Which custody evidence proves that no unregistered scope produced a family-relevant positive?
11. How should member-specific obligation bases remain visible without creating one universal
    denominator?
12. What public wording prevents the family bound from being read as a world-wide harm or efficacy
    probability?
13. If useful e-processes arrive, do they target strong any-false-promotion control or another
    global-null statement?
14. If valid p-values arrive, does Holm add enough value to justify a new canonical family
    procedure?
15. What exact behavioral evidence closes the missing declaration/projection/reproduction chain
    registered by `GY-GAP2`
    (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:2440-2476`)?

The stable conclusion is:

> The fixed-family weighted-union theorem survives. The pinned owner is already conservative enough
> that an exact three-scope mass-one mathematical envelope lies below `(9/20) * delta`, not above one
> policy delta. The unresolved gap is canonical family custody and reproduction. Outcome-dependent
> repair remains numerically blocked until its actual selector is covered by a verified theorem.
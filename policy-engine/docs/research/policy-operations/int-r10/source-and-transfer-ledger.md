---
title: INT-R10 — Primary-Source and Transfer Ledger
status: delivered
kind: deep-research-support
research_task: INT-R10
repository: https://github.com/DenisKopylov/polisyos
repository_branch: research/int-r10-family-wise-risk-composition
repository_commit: 978e6b958c5c86d41f8fcbeff45b8d533c8c7b8d
inspection_date: 2026-08-03
authoritative_for:
  - primary-source orientation for the INT-R10 research result
  - research-level transfer and non-transfer judgments for family-wise error control, sequential design, anytime-valid inference, e-values, and selective inference
  - citation provenance for theorem and impossibility conclusions in the primary INT-R10 deliverable
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal or regulatory compliance conclusion
  - assertion that PolicyOS currently implements cross-scope composition
  - assertion that a cited statistical method applies without its stated assumptions
research_only: true
---

# INT-R10 — Primary-Source and Transfer Ledger

## 1. Purpose and transfer standard

The target is not generic statistical significance. It is the authority event:

> at least one reached member of an exact governed PolicyOS family emits a false promotion, and the
> family reports the first such canonical positive.

A source transfers only when its guarantee can be rewritten over that event without silently
importing a common estimand, common null, exchangeability, independence, valid p-values that do not
exist, a calibrated base rate, or one accumulating data stream.

Three layers must remain separate:

1. **event accounting** — composition of valid upper bounds on heterogeneous false-promotion events;
2. **local bound construction** — the canonical per-problem confidence owner's theorem and
   maintained assumptions; and
3. **power improvements** — procedures requiring additional statistical objects or dependence
   assumptions.

The union inequality used by INT-R10 is proved directly in the primary deliverable. External
sources are used to determine whether stronger or adaptive transfers are justified.

## 2. Pinned repository predicates used in transfer judgments

The following repository facts delimit what can be imported:

- N9 derives one canonical confidence scope per design-problem binding
  (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`).
- Each scope owns one root-level non-resettable budget and local receipt/history
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:156-184`,
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
  `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:723-752`).
- Local ordinals and prior spend are calculated only inside the current scope; risk is burned
  before owner execution
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1301-1364`).
- Exact local spend is recomputed under the Basel-square kernel
  (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`).
- The live top-level delta is `1/100`
  (`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`).
- Relevant owner-verified e-value/e-process/sequential profiles are unavailable, while the
  executable constant-one e-process cannot satisfy a promotion obligation
  (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).
- GY-GAP2 records no cross-scope/family/parent-scope composition
  (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`).
- INT-R9 permits general implementation repair between slots
  (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`).
- INT-R1 keeps every probability statement conditional on a declared obligation basis and
  validator soundness
  (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`).
- The project has no positive governed promotion history from which to calibrate a family model
  (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).

## 3. Primary-source ledger

| ID | Primary source | Result inspected | Required object/assumption | Transfer | Non-transfer / limit |
| --- | --- | --- | --- | --- | --- |
| S01 | Sture Holm, “A Simple Sequentially Rejective Multiple Test Procedure,” *Scandinavian Journal of Statistics* 6(2), 65–70 (1979), [DOI 10.2307/4615733](https://doi.org/10.2307/4615733), [JSTOR 4615733](https://www.jstor.org/stable/4615733). | Step-down control of at least one type-I error for any configuration of true hypotheses. | A finite family of valid local p-values and the ordered rejection procedure. | Confirms that a canonical family procedure can improve on single-step Bonferroni when its p-values exist. | PolicyOS exposes no family of valid p-values and no step-down owner at the pinned baseline (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |
| S02 | Stuart J. Pocock, “Group Sequential Methods in the Design and Analysis of Clinical Trials,” *Biometrika* 64(2), 191–199 (1977), [DOI 10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191). | Repeated looks can be designed as one overall-size-controlled procedure. | One accumulating treatment comparison and the paper's response model. | Early stopping must be included in the controlled procedure. | Three PolicyOS design problems are not repeated looks at one statistic; canonical scope derivation is per problem (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`). |
| S03 | Peter C. O'Brien and Thomas R. Fleming, “A Multiple Testing Procedure for Clinical Trials,” *Biometrics* 35(3), 549–556 (1979), [DOI 10.2307/2530245](https://doi.org/10.2307/2530245), [PubMed 497341](https://pubmed.ncbi.nlm.nih.gov/497341/). | A fixed maximum number of interim tests can preserve overall size while allowing early termination. | One accumulating comparison, fixed maximum analyses, and the paper's statistic model. | Same aggregate-procedure lesson as S02. | Does not establish one O'Brien–Fleming boundary across different problems, claims, evidence sets, or implementations. |
| S04 | K. K. Gordon Lan and David L. DeMets, “Discrete Sequential Boundaries for Clinical Trials,” *Biometrika* 70(3), 659–663 (1983), [DOI 10.1093/biomet/70.3.659](https://doi.org/10.1093/biomet/70.3.659). | Alpha-spending can determine boundaries from past/current information times. | A sequential experiment with meaningful information time and a valid joint model. | Transfers “allocate before use; cumulative allocation stays within total” and supports unused mass remaining unused. | Does not turn several unrelated design problems into one trial. PolicyOS's Basel schedule is local to each scope (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`). |
| S05 | Jinjin Tian and Aaditya Ramdas, “Online Control of the Familywise Error Rate,” *Statistical Methods in Medical Research* 30(4), 976–993 (2021), [DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381), [arXiv:1910.04900](https://arxiv.org/abs/1910.04900). | FWER can be controlled over an a priori unbounded online sequence; stronger adaptive algorithms use independence/local dependence. | Sequential valid p-values and predictable allocation; extra dependence assumptions for stronger procedures. | Strongly supports predictable nonnegative family caps with bounded total. | PolicyOS lacks cross-scope p-values/controller (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`); outcome-dependent repair also needs local conditional validity. |
| S06 | Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, and Jasjeet Sekhon, “Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences,” *Annals of Statistics* 49(2), 1055–1080 (2021), [DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991), [arXiv:1810.08240](https://arxiv.org/abs/1810.08240). | Simultaneous coverage over time and validity at stopping times. | Specified process, filtration, estimand, and time-uniform construction. | A local certificate intended to survive continuation must be valid for the actual filtration. | Time-uniform validity inside one process does not compose separately selected processes or repaired implementations. |
| S07 | Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, and Jasjeet Sekhon, “Time-Uniform Chernoff Bounds via Nonnegative Supermartingales,” *Probability Surveys* 17, 257–317 (2020), [DOI 10.1214/18-PS321](https://doi.org/10.1214/18-PS321), [arXiv:1808.03204](https://arxiv.org/abs/1808.03204). | Nonnegative supermartingales provide time-uniform line-crossing control. | A filtration and valid supermartingale/sub-ψ process. | Explains why predictable history-adapted choices can remain valid when the local process is conditionally valid. | Does not certify an arbitrary implementation selected after earlier outcomes. |
| S08 | Aaditya Ramdas, Peter Grünwald, Vladimir Vovk, and Glenn Shafer, “Game-Theoretic Statistics and Safe Anytime-Valid Inference,” *Statistical Science* 38(4), 576–601 (2023), [DOI 10.1214/23-STS894](https://doi.org/10.1214/23-STS894), [arXiv:2210.01948](https://arxiv.org/abs/2210.01948). | E-process/confidence-sequence validity under optional continuation depends on predictability relative to the filtration. | Test martingale/e-process conditions, declared filtration, predictable bets. | Direct support for history-conditional local validity in INT-R10's adaptive theorem. | “Anytime-valid” is not selection-proof across an arbitrary menu of processes. INT-R9's repair clause is outcome-dependent unless separately proved (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`). |
| S09 | Vladimir Vovk and Ruodu Wang, “E-values: Calibration, Combination, and Applications,” *Annals of Statistics* 49(3), 1736–1754 (2021), [DOI 10.1214/20-AOS2020](https://doi.org/10.1214/20-AOS2020), [arXiv:1912.06116](https://arxiv.org/abs/1912.06116). | E-values are nonnegative with expectation at most one under a null; arithmetic averaging can merge e-values for one hypothesis under arbitrary dependence. | Valid e-values and a merger targeted to the named null. | Shows e-values can be easier to merge when the target aligns. | One-null averaging is not strong FWER for “any false authority promotion” across different problem truth configurations. |
| S10 | Vladimir Vovk and Ruodu Wang, “Merging Sequential E-values via Martingales” (2020), [arXiv:2007.06382](https://arxiv.org/abs/2007.06382). | Sequential e-values can be merged through martingale constructions; independent merging is separately structured. | Sequential conditional e-validity or explicit independence, plus correct merger target. | Product/martingale composition is valid only when every factor meets its conditional premise. | The pinned PolicyOS registry exposes no such cross-scope conditional e-value sequence (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). |
| S11 | Vladimir Vovk and Ruodu Wang, “True and False Discoveries with Independent and Sequential E-values” (2020), [arXiv:2003.00593](https://arxiv.org/abs/2003.00593). | Multiple-testing procedures for independent or sequential e-values. | Independent or sequentially valid e-values and a family procedure. | Confirms e-value multiplicity is possible when objects/assumptions are real. | Neither independence nor sequential conditional e-validity across PolicyOS scopes is implemented (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). |
| S12 | William Fithian, Dennis Sun, and Jonathan Taylor, “Optimal Inference After Model Selection” (2014/2017), [arXiv:1410.2597](https://arxiv.org/abs/1410.2597). | Valid post-selection inference accounts for the selection event. | Statistical model, defined selection event, conditional inference. | “Report first passing result” changes the inferential target; selection/stopping must be inside the controlled procedure. | Does not turn a selected PolicyOS promotion into a population-effect or generalization theorem. |
| S13 | Zbyněk Šidák, “Rectangular Confidence Regions for the Means of Multivariate Normal Distributions,” *Journal of the American Statistical Association* 62(318), 626–633 (1967), [DOI 10.1080/01621459.1967.10482935](https://doi.org/10.1080/01621459.1967.10482935), [JSTOR 2283989](https://www.jstor.org/stable/2283989). | Rectangle-probability inequality for multivariate normal distributions. | Specified multivariate-normal structure. | Demonstrates that model/dependence structure can improve on a union bound. | PolicyOS has no verified cross-problem joint model or family object (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |

## 4. Transfer conclusions

### 4.1 Weighted union transfers directly

Let `V_i` be reached-member false promotion and suppose a valid local theorem gives

```text
P(V_i | A_F) <= alpha_i.
```

Then, without independence, exchangeability, a common null, or a common estimand,

```text
P(union_i V_i | A_F)
  <= sum_i P(V_i | A_F)
  <= sum_i alpha_i.
```

For `m * alpha <= 1`, disjoint events of probability `alpha` attain `m * alpha`; no stronger generic
bound follows from local upper bounds alone.

At the pinned baseline, three canonical problem scopes each receive the ordinary registry-level
budget structure
(`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`,
`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:518-557`,
`policy-engine/architecture/production_quality/confidence_ledger.toml:1-18`), while no cross-scope
cap relation exists
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). Hence the best
generic composition of three valid local `delta` guarantees is `min(1, 3 * delta)`; at live
`delta = 1/100`, `3/100`.

### 4.2 Sequential boundaries transfer only as an accounting analogy

Pocock, O'Brien–Fleming, and Lan–DeMets support:

- include early stopping in the controlled procedure;
- allocate error before result-bearing execution;
- do not reset after an unfavorable look; and
- leave unused allocation unused unless a prospective theorem permits recycling.

They do not supply clinical critical values, information time, or a common-effect model for three
PolicyOS problems. The repository's Basel-square kernel is a predictable **within-scope** schedule
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`); it does not create a
family ordinal.

### 4.3 Online FWER supports predictable caps, not silent repair

The minimal transferable adaptive arithmetic is:

```text
alpha_i is measurable before outcome i;
alpha_i >= 0;
sum_i alpha_i <= delta_F pathwise.
```

For later implementation chosen from earlier outcomes, arithmetic is only half of the theorem. The
local false-promotion guarantee must remain valid conditional on the same history. INT-R9 permits
general repair
(`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`),
but the live owner lacks the corresponding theorem
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

### 4.4 Anytime-valid inference solves within-process stopping

Time-uniform methods remain valid relative to their actual filtration. That filtration must include
earlier outputs, disclosed case facts, adjudication, repair choice, model/configuration changes, and
all information used to select the later procedure.

A sufficient local adaptive premise is:

```text
P(V_i | H_{i-1}, R_i, A_F) <= alpha_i(H_{i-1}) almost surely,
```

or an equivalent uniform/selection-aware theorem. A fixed-procedure theorem invoked after the
procedure was selected from `H_{i-1}` does not satisfy this premise.

### 4.5 E-values are not an automatic heterogeneous-family solution

Do not conflate:

1. averaging e-values for one null under arbitrary dependence;
2. multiplying sequential e-values under conditional e-validity;
3. multiple-testing procedures over many nulls under their own criterion/assumptions.

PolicyOS controls a union of false authority events. Even if local e-values later exist, a product
generally targets a joint/global-null object rather than strong control of “any false promotion”
under every truth configuration. The live registry currently refuses the relevant owner theorem
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).

### 4.6 Selective inference limits meaning

A prospective family bound can include stop-on-first-positive selection because the reported false
first positive lies in the union of local false-promotion events. It does **not** provide an
unbiased effect estimate, population validity, representativeness, immunity from upstream case-pool
selection, or unconditional validity after obligation/validator assumptions fail. INT-R1's
conditionality remains controlling
(`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`).

## 5. Assumption ledger for a family theorem

| Premise | Why required | Pinned standing |
| --- | --- | --- |
| Exact family membership/order | Defines the union and prevents substitution. | INT-R9 sketches a queue, but N11 has no family binding (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`; `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |
| Exact canonical scope derivation | Preserves per-problem ownership. | Implemented (`policy-engine/src/polisyos/runtime/quality/promotion_sequence.py:356-375`). |
| Prospective nonnegative cap per member | Makes every local top-level allocation checkable before result. | Missing across scopes (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |
| Exact/pathwise aggregate cap | Blocks three fresh top-level deltas and outcome-dependent refunds. | Missing (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |
| Valid local false-promotion theorem | Accounting cannot manufacture local validity. | Mostly refused/unavailable on the probabilistic path (`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). |
| Joint obligation/validator assumptions | Preserves INT-R1 conditionality. | Declared locally; no family projection (`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:1-52`; `policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`). |
| Precommitted member-plan vector or selection-valid adaptive theorem | Prevents outcome-dependent repair from using a fixed theorem. | INT-R9 permits repair; owner theorem unavailable (`policy-engine/docs/research/policy-operations/int-r9-first-promotion-evaluation-protocol.md:590-650`; `policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). |
| Live-source verifier | Prevents author-written proof. | Missing for family composition (`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). |
| No duplicate owner | Preserves P27/P28. | Required by repository rules (`AGENTS.md:17-27`, `AGENTS.md:37-55`). |

## 6. Negative findings and carried conclusion

1. No inspected primary source proves that arbitrary heterogeneous authority claims share one
   `delta` merely because names/order are precommitted and execution stops at first positive.
2. No source turns a per-problem anytime-valid certificate into a cross-problem family guarantee
   without a family allocation/composition rule.
3. No e-value theorem makes multiplication valid after arbitrary outcome-dependent process choice.
4. No clinical sequential theorem makes a repaired implementation on another problem another look
   at one experiment.
5. No multiplicity method removes obligation completeness or validator soundness; INT-R1 remains
   controlling
   (`policy-engine/docs/research/policy-operations/int-r1-obligation-coverage-and-open-world-completeness.md:1-90`).
6. No historical calibration route is available at the current empirical state
   (`policy-engine/docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md:390-398`).
7. No stronger-than-union generic bound follows from current local statements alone.

The established research conclusion is:

> Preserve every canonical per-problem scope. Before family outcomes, bind exact local caps and the
> complete member-specific plan vector. Require the canonical confidence ledger to enforce each
> cap before execution and recompute the exact aggregate from live source and receipts. If
> outcome-dependent repair is allowed, additionally require a history-conditional, uniform, or
> otherwise selection-valid local theorem.

Equal `delta_F/3` caps for a three-member family are a transparent engineering choice, not a
uniquely optimal theorem. The existing Basel-square schedule may allocate inside each local cap but
cannot itself enforce their sum because it is scope-local
(`policy-engine/src/polisyos/runtime/quality/confidence_ledger.py:3890-4025`).

Under the pinned source, the necessary cross-scope binding/projection is missing
(`policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md:1-10`). Three ordinary
full-`delta` scopes therefore retain only the generic `min(1, 3 * delta)` composition of valid local
guarantees. The intended single-`delta` INT-R9 claim remains blocked, and outcome-dependent repair
has no family numeric theorem while the relevant owner profiles remain unavailable
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`).
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
  - citation provenance for the theorem and impossibility conclusions stated in the primary INT-R10 deliverable
may_not_use_for:
  - production implementation authorization
  - final code or wire contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal or regulatory compliance conclusion
  - assertion that PolicyOS currently implements cross-scope composition
  - assertion that a cited statistical method applies without the assumptions stated here
research_only: true
---

# INT-R10 — Primary-Source and Transfer Ledger

## 1. Purpose and transfer standard

This supporting artifact records which external results can be carried into the PolicyOS
question and which cannot. The target is not generic statistical significance. The target event
is an authority event:

> at least one member of an exact, prospectively governed family of PolicyOS evaluations emits a
> false promotion that is accepted as the first valid positive.

A source is transferable only when its guarantee can be rewritten over that event without
silently importing a common estimand, a common null, exchangeability, independence, an observed
p-value, a calibrated historical base rate, or a single accumulating data stream that PolicyOS
does not have.

The decisive distinction is between:

1. **event accounting**, which can combine upper bounds on heterogeneous false-promotion events;
2. **construction of each local bound**, which remains the responsibility of the canonical
   per-problem confidence owner and its maintained assumptions; and
3. **power improvements**, which generally require extra statistical objects or dependence
   assumptions and therefore cannot be treated as free arithmetic.

The elementary union inequality used by INT-R10 is proved directly in the primary deliverable.
It does not need an external authority. The sources below are used to test whether a stronger or
more adaptive transfer is available.

## 2. Primary-source ledger

| ID | Primary source | Result inspected | Assumptions or object supplied by the source | Transfer to INT-R10 | Non-transfer / limit |
| --- | --- | --- | --- | --- | --- |
| S01 | Sture Holm, “A Simple Sequentially Rejective Multiple Test Procedure,” *Scandinavian Journal of Statistics* 6(2), 65–70 (1979), [JSTOR 4615733](https://www.jstor.org/stable/4615733), [DOI 10.2307/4615733](https://doi.org/10.2307/4615733). | A step-down multiple-testing procedure with protection against at least one type-I error for any configuration of true hypotheses. | A finite family of valid local p-values and an ordered rejection procedure. No beneficial dependence assumption is needed for the classical Holm guarantee. | Confirms that family-wise control can be stronger than a single-step equal Bonferroni allocation when the family exposes valid comparable p-values and a family procedure owns the ordering. | The PolicyOS ledger does not expose one p-value per design problem, has no family-level step-down owner, and decides authority obligations rather than a homogeneous p-value family. Holm is therefore an available future design family, not a theorem about the current artifacts. |
| S02 | Stuart J. Pocock, “Group Sequential Methods in the Design and Analysis of Clinical Trials,” *Biometrika* 64(2), 191–199 (1977), [DOI 10.1093/biomet/64.2.191](https://doi.org/10.1093/biomet/64.2.191). | Repeated significance tests over accumulated observations can be designed to control the overall procedure rather than treating each look as fresh. | A specified group-sequential experiment, repeated looks at one accumulating treatment comparison, and the paper’s normal-response design model. | Transfers the governance lesson that stopping at an early positive must be included in the error-controlled procedure. | Three distinct PolicyOS design problems are not repeated looks at one accumulating statistic. Pocock boundaries cannot be copied as cross-problem arithmetic. |
| S03 | Peter C. O’Brien and Thomas R. Fleming, “A Multiple Testing Procedure for Clinical Trials,” *Biometrics* 35(3), 549–556 (1979), [DOI 10.2307/2530245](https://doi.org/10.2307/2530245), [PubMed 497341](https://pubmed.ncbi.nlm.nih.gov/497341/). | A fixed maximum number of interim tests can preserve the overall size of one clinical-trial procedure while allowing early termination. | One treatment comparison, accumulated data, a fixed maximum number of analyses, and the paper’s test-statistic model. | Transfers the same aggregate-procedure lesson as S02. | Does not establish that different estimands, implementations, evidence sets, or authority claims can share one O’Brien–Fleming boundary. |
| S04 | K. K. Gordon Lan and David L. DeMets, “Discrete Sequential Boundaries for Clinical Trials,” *Biometrika* 70(3), 659–663 (1983), [DOI 10.1093/biomet/70.3.659](https://doi.org/10.1093/biomet/70.3.659). | An alpha-spending function can determine a boundary from past and current decision times without fixing all future decision times. | A sequential experiment with a meaningful information-time scale and a valid joint model for its repeated analyses. | Transfers the accounting pattern “allocate before use; cumulative spend must stay within the declared total.” It also supports leaving unspent mass unused. | The paper’s information-time boundary theorem does not turn several unrelated design problems into looks at one trial. PolicyOS may reuse the spending metaphor, not the clinical boundary theorem. |
| S05 | Jinjin Tian and Aaditya Ramdas, “Online Control of the Familywise Error Rate,” *Statistical Methods in Medical Research* 30(4), 976–993 (2021), [DOI 10.1177/0962280220983381](https://doi.org/10.1177/0962280220983381), [arXiv:1910.04900](https://arxiv.org/abs/1910.04900). | Family-wise error can be controlled for an a priori unbounded online sequence. Bonferroni-style allocations extend directly; the paper’s more adaptive gains require independent or locally dependent p-values. | Sequentially arriving valid p-values; predictable allocation rules; extra dependence conditions for the stronger adaptive algorithms. | Strongly supports predictable nonnegative allocations whose total is bounded, even when the future family length is not known. This is the closest external analogue to a ledger-owned cap vector or spending stream. | PolicyOS currently has neither cross-scope p-values nor a family controller. The paper does not make outcome-dependent repair safe unless the local evidence remains valid conditional on the enlarged history under the procedure’s assumptions. |
| S06 | Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, and Jasjeet Sekhon, “Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences,” *Annals of Statistics* 49(2), 1055–1080 (2021), [DOI 10.1214/20-AOS1991](https://doi.org/10.1214/20-AOS1991), [arXiv:1810.08240](https://arxiv.org/abs/1810.08240). | Confidence sequences provide simultaneous coverage over time and therefore remain valid at stopping times under the paper’s conditions. | A specified stochastic process, filtration, estimand, and time-uniform construction. | Supports the requirement that a local certificate intended to survive optional continuation must be valid with respect to the actual filtration. | Time-uniform validity within one process does not compose several separately selected processes, estimands, or repaired implementations into one family claim. |
| S07 | Steven R. Howard, Aaditya Ramdas, Jon McAuliffe, and Jasjeet Sekhon, “Time-Uniform Chernoff Bounds via Nonnegative Supermartingales,” *Probability Surveys* 17, 257–317 (2020), [DOI 10.1214/18-PS321](https://doi.org/10.1214/18-PS321), [arXiv:1808.03204](https://arxiv.org/abs/1808.03204). | Nonnegative supermartingales and line-crossing inequalities provide time-uniform control under stated process assumptions. | A filtration and a supermartingale or sub-ψ process satisfying the stated conditions. | Supplies the mathematical reason predictable, history-adapted choices can remain valid when the local process is conditionally valid. | It does not certify an arbitrary implementation chosen after earlier results. The process and conditional supermartingale property must actually include that adaptation. |
| S08 | Aaditya Ramdas, Peter Grünwald, Vladimir Vovk, and Glenn Shafer, “Game-Theoretic Statistics and Safe Anytime-Valid Inference,” *Statistical Science* 38(4), 576–601 (2023), [DOI 10.1214/23-STS894](https://doi.org/10.1214/23-STS894), [arXiv:2210.01948](https://arxiv.org/abs/2210.01948). | E-processes and confidence sequences can remain valid under optional stopping or continuation, because the wager at each step is predictable relative to the filtration. The paper also distinguishes valid continuation from choosing a betting strategy after observing its outcome. | Test martingale/e-process conditions, a declared filtration, and predictable bets. | Directly supports INT-R10’s adaptive theorem condition: the slot-i error guarantee must hold conditional on the full prior history, and its allocation must be fixed before the slot-i outcome. | “Anytime-valid” is not “selection-proof across any collection of processes.” Running many strategies and reporting the best is explicitly not legitimized. A later repaired implementation needs its own conditional/uniform theorem. |
| S09 | Vladimir Vovk and Ruodu Wang, “E-values: Calibration, Combination, and Applications,” *Annals of Statistics* 49(3), 1736–1754 (2021), [DOI 10.1214/20-AOS2020](https://doi.org/10.1214/20-AOS2020), [arXiv:1912.06116](https://arxiv.org/abs/1912.06116). | E-values are nonnegative evidence variables with expectation at most one under a null. For multiple tests of a single hypothesis, e-values can be merged by arithmetic averaging under arbitrary dependence; the paper also develops multiple-testing uses. | Valid e-values for named null hypotheses and the combining rule’s stated target. | Shows that e-values can be easier to combine than p-values when the null target and validity conditions align. | Averaging evidence against one null is not the PolicyOS family event. Three design problems need not share a null or estimand. A merged e-value does not by itself control “any false authority promotion” under every configuration. |
| S10 | Vladimir Vovk and Ruodu Wang, “Merging Sequential E-values via Martingales” (2020), [arXiv:2007.06382](https://arxiv.org/abs/2007.06382). | Sequential e-values can be merged through martingale constructions; independent e-value merging is a separate, more structured problem. | Sequential conditional e-validity or an explicitly stated independence structure, plus a merger targeted to the relevant null. | Supports product/martingale composition only when each factor is valid conditionally on the past and the merged object tests the intended null. | The current PolicyOS registry’s different problem scopes do not expose such a cross-scope conditional e-value sequence. Multiplication is not a free replacement for family-wise event accounting. |
| S11 | Vladimir Vovk and Ruodu Wang, “True and False Discoveries with Independent and Sequential E-values” (2020), [arXiv:2003.00593](https://arxiv.org/abs/2003.00593). | Multiple-testing gains are developed for independent or sequential e-values. | Independent or sequentially valid e-values and a multiple-testing procedure. | Confirms that e-value-based multiplicity is possible when those objects and assumptions are real. | Neither independence nor sequential conditional e-validity across PolicyOS design problems is established at the pinned baseline. |
| S12 | William Fithian, Dennis Sun, and Jonathan Taylor, “Optimal Inference After Model Selection” (2014/2017), [arXiv:1410.2597](https://arxiv.org/abs/1410.2597). | Valid post-selection inference must account for the selection event; the paper controls selective type-I error conditional on selection in exponential-family settings. | A statistical model, a defined selection event, and inference conditional on that event. | Transfers the warning that “report the first passing result” changes the inferential target. Family control must include the selection/stopping rule. | The paper does not convert one selected PolicyOS promotion into a population-performance or effect-estimation theorem. INT-R10 controls only the false-promotion family event, not post-selection estimation or generalization. |
| S13 | Zbyněk Šidák, “Rectangular Confidence Regions for the Means of Multivariate Normal Distributions,” *Journal of the American Statistical Association* 62(318), 626–633 (1967), [DOI 10.1080/01621459.1967.10482935](https://doi.org/10.1080/01621459.1967.10482935), [JSTOR 2283989](https://www.jstor.org/stable/2283989). | A rectangle-probability inequality for multivariate normal distributions underlies Šidák-style simultaneous regions. | A specified multivariate-normal structure; modern Šidák corrections additionally rely on a justified joint structure rather than arbitrary heterogeneous events. | Demonstrates that a product-form correction can improve on a union bound when its dependence/model conditions hold. | PolicyOS has no common multivariate-normal model, exchangeability premise, or verified cross-problem dependence structure. A Šidák number would therefore be authored convenience, not a proven bound. |

## 3. Transfer conclusions by method family

### 3.1 Weighted union / Bonferroni accounting transfers directly

Let `V_i` be the event that the reached slot `i` falsely promotes, and let a valid local theorem
provide

```text
P(V_i | A_F) <= alpha_i
```

for the exact family assumptions `A_F`. Then, without independence, exchangeability, a common
null, or a common estimand,

```text
P(any false promotion in the family | A_F)
  = P(union_i V_i | A_F)
  <= sum_i P(V_i | A_F)
  <= sum_i alpha_i.
```

This is event algebra, not a transfer of biomedical-trial authority. It applies because the
controlled event is a union. The local theorems may concern different design problems, provided
each one genuinely bounds its own false authority event and the family assumptions are jointly
maintained.

The bound can be sharp under the stated information. For `m * alpha <= 1`, construct disjoint
false-promotion events with probability `alpha` each. Every local guarantee holds and the family
probability is exactly `m * alpha`. Therefore no generic improvement below the sum can be claimed
from local upper bounds alone.

### 3.2 Classical sequential boundaries transfer only as an accounting analogy

Pocock, O’Brien–Fleming, and Lan–DeMets solve repeated-look problems with one accumulating
experiment and a modeled joint path. PolicyOS’s three fresh design problems have different
problem identities, evidence, claim scopes, and potentially different implementations. The
following transfers:

- include early stopping in the controlled procedure;
- allocate error before the result-bearing look;
- do not reset after an unfavorable look;
- leave unspent allocation unused unless a valid prospective rule permits reuse.

The following does not transfer:

- a clinical critical-value boundary;
- information time inferred from slot number;
- the assumption that all slots estimate one treatment effect;
- the assumption that changing implementation between slots is merely taking another look.

The repository’s Basel-square kernel is already a within-scope predictable spending schedule. It
is mathematically analogous to an alpha-spending allocation over execution ordinals, but that
analogy does not make its scope-local ordinal a family ordinal.

### 3.3 Online FWER supports predictable family caps, not silent repair

Tian and Ramdas show that simple online Bonferroni allocations can control FWER over a growing
sequence, while more adaptive power gains require explicit independence or local-dependence
conditions. The transferable minimal rule is:

```text
alpha_i is measurable before outcome i, alpha_i >= 0,
and the realized path satisfies sum_i alpha_i <= delta_F.
```

For a PolicyOS sequence whose later implementation may depend on earlier outcomes, that arithmetic
is only half of the theorem. The local false-promotion guarantee must also be valid conditional on
the same prior history. Otherwise a repair process can search over implementations until it finds
one whose nominal local certificate is no longer valid for the selection mechanism.

### 3.4 Anytime-valid inference solves within-process optional stopping

Howard et al. and Ramdas et al. justify arbitrary stopping or continuation when the evidence
process is a valid nonnegative supermartingale/e-process relative to the actual filtration. The
word **actual** is load-bearing. The filtration must include earlier slot outputs, disclosed case
facts, adjudication, repair choices, model changes, and any other information used to select the
next implementation.

Thus the valid adaptive condition is of the form

```text
P(V_i | H_{i-1}, slot i is reached, A_F) <= alpha_i almost surely,
```

or an equivalent uniform theorem covering every implementation that the permitted repair policy
can select. A certificate proved only for a fixed implementation and then invoked after
outcome-dependent implementation selection does not satisfy this condition.

### 3.5 E-values are not an automatic heterogeneous-family solution

The e-value literature supplies three distinct operations that must not be conflated:

1. **averaging e-values for one null** under arbitrary dependence;
2. **multiplying sequential e-values** when each factor is conditionally e-valid given the past;
3. **multiple-testing procedures over many nulls** with their own error criterion and dependence
   assumptions.

The PolicyOS target is instead a union of false authority events over different problem scopes.
Even if each scope someday exposes an e-value, multiplying them generally produces evidence for a
joint/intersection target, not direct strong-FWER protection against any false promotion under all
truth configurations. E-values may become local instruments or inputs to a future family
procedure, but the target event, conditional validity, and family verifier still have to be
specified.

The pinned registry makes this distinction operationally decisive. Its only executable
statistical e-process is the closed constant-one process, which is anytime-valid but cannot reject
or satisfy a promotion obligation; owner-verified e-value/e-process instruments are registered
under `owner_theorem_unavailable_v1`
(`policy-engine/architecture/production_quality/confidence_ledger.toml:53-121`). External theory
cannot fill that repository-owned proof gap by citation.

### 3.6 Selective inference limits the meaning of a first passing result

A prospectively fixed family-wise bound can include the stop-on-first-positive selection event:
the event that the reported first positive is false is contained in—and with reached-slot events,
equal to—the union of false slot promotions. That handles the family error event.

It does **not** provide:

- an unbiased estimate of the selected design’s effect;
- population or domain generalization;
- a claim that the selected case was representative;
- a guarantee against upstream case-pool selection;
- a guarantee that implementation repair was non-selective; or
- an unconditional claim after the obligation or validator assumptions fail.

Those remain separate selective-inference, external-validity, custody, and governance questions.

## 4. Assumption ledger for a PolicyOS family theorem

A family-wise statement must name, rather than compress, the premises below.

| Premise | Why it is required | Current baseline standing |
| --- | --- | --- |
| Exact family membership and order | Defines the union being bounded and prevents favorable substitution. | INT-R9 sketches a queue; N11 has no canonical cross-scope binding. |
| Exact canonical scope derivation | Preserves the per-problem owner and prevents scope weakening. | Implemented per problem in `confidence_risk_scope_for_problem()`. |
| Prospective nonnegative cap per member | Makes each top-level allocation checkable before its result. | Missing across scopes. |
| Pathwise aggregate cap | Blocks three fresh top-level deltas and outcome-dependent refunds. | Missing across scopes. |
| Valid local false-promotion theorem | Supplies `P(V_i) <= alpha_i`; accounting cannot manufacture it. | Mostly refused/unavailable on the probabilistic path. |
| Jointly maintained obligation/validator assumptions | Preserves INT-R1 and the ledger’s conditionality. | Declared per receipt; no family projection. |
| History-conditional or uniform validity for adaptation | Keeps the theorem valid after earlier outputs influence later implementation. | Not established. |
| Recomputable live-source verifier | Prevents an author-written family record from becoming its own proof. | Missing. |
| No duplicate family owner | Preserves P27/P28 and the confidence ledger’s authority. | Required design constraint. |

## 5. Negative findings

1. No inspected primary source proves that arbitrary heterogeneous authority claims can share a
   single `delta` merely because they are precommitted and stopped at the first positive.
2. No source turns a per-problem anytime-valid certificate into a cross-problem family guarantee
   without an allocation/composition rule.
3. No e-value result makes multiplication valid after arbitrary outcome-dependent choice of the
   next e-value process.
4. No sequential-clinical result justifies treating a repaired implementation on a different
   design problem as another look at the same experiment.
5. No multiplicity procedure removes the ledger’s maintained assumptions about obligation
   completeness and validator soundness.
6. No cited theorem supplies the historical calibration data that PolicyOS does not have.
7. No stronger-than-union generic bound follows from the current local statements alone.

## 6. Research conclusion carried to the primary deliverable

The only composition established without new statistical objects or dependence assumptions is:

> preserve every canonical per-problem scope; prospectively bind each family member to a local
> top-level cap; require the canonical confidence-ledger owner to verify that the caps sum to at
> most the family bound; and require every local false-promotion theorem to remain valid under the
> declared joint assumptions and, where adaptation is permitted, conditional on the actual prior
> history.

For a fixed three-slot family, equal caps `delta_F / 3` are a transparent engineering choice, not
a uniquely optimal theorem. Unequal weights are equally valid if prospectively fixed and summed
exactly. The existing within-scope Basel-square schedule can then allocate **inside** each local
cap. It cannot itself enforce the sum of caps across three independent scope roots.

Under the pinned source, no such binding or verifier exists. Consequently, three ordinary scopes
with top-level `delta` retain only the generic `min(1, 3 * delta)` family bound. The intended
single-`delta` INT-R9 claim remains blocked. Adaptive repair remains numerically unbounded at the
family level until a history-conditional or uniform owner theorem is delivered.
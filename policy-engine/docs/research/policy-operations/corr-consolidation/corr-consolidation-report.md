# CORR — Stage 6 consolidation report

**Самое существенное открытие волны: четыре пакета пока не поддерживают публикацию `δ_ground` в предложенной численной форме.** CORR‑R2 корректно выводит `n=299` для фиксированной односторонней биномиальной ошибки внутри заранее объявленной страты, но действующая CGF‑спецификация по‑прежнему формулирует `δ_ground` как вероятность **хотя бы одного** `confident_wrong_bind` до stopping time `τ` и раскладывает её на несколько компонент риска. CORR‑R3 сам обнаружил эту разницу estimands. Поэтому `299` — валидный локальный calibration design при определённых предпосылках, но **не доказательство текущего системного обещания `δ_ground`**, пока архитектор не установит мост между per-unit rate и horizon-level guarantee.

Второй результат меняет экономику исходного решения. CORR‑R1 показывает, что causal-atom correspondence и statute-to-lever correspondence имеют общий procedural envelope, но **два разных substantive truth predicates**. Один физический человек потенциально может исполнять обе функции, но только как отдельно квалифицированный и отдельно назначенный для двух purposes. Следовательно, **the rule's economic argument fails and the rule is still correct but no longer cheap.**

## Evidence-weight limitation

У CORR нет audit line. Все четыре inputs — Stage‑1 packages: отсутствуют независимый Stage‑2 hostile audit, amendment и amendment verification. Ни один вывод ниже не имеет того же evidence weight, что candidate из стандартной полностью прошедшей pipeline wave.

Hostile reading, выполненный здесь, — **consolidator hostile read, not a Stage‑2 audit**. Он используется для disposition и routing, а не как заменитель отсутствующего audit line.

## 1. Disposition of the five-point standing rule

**Disposition: `SURVIVES_AMENDED`.**

| Point | Disposition | Reason |
|---|---|---|
| 1. Gold one-sided | **unchanged** | Gold относится к confident-wrong safety claim, не recall/completeness. |
| 2. Stratum pre-declared and dated | **unchanged** | Post-hoc stratum недопустима. |
| 3. Negatives from construction, positives from appointment | **amended** | Положительное correspondence иногда может быть доказано construction, если обе стороны уже находятся в одной authoritative typed vocabulary. Для двух blocking seams такого класса пока нет. |
| 4. Until appointment: custody/no number/refusal | **amended for scope only** | Верно для positive correspondence, not discharged by valid constructibility proof. |
| 5. One appointment discharges both iff acceptance rule is same | **refuted as written; replaced** | R1 устанавливает два predicates и два authority purposes. |

### Exact replacement — point 3

> **Correspondence may be discharged by construction only for a pre-declared class in which both semantic identities are independently authoritative and the correspondence follows mechanically from a non-circular recognition rule. Outside that class, known mismatches may supply constructed negative gold, while positive correctness requires independent purpose-qualified adjudication.**

### Exact replacement — point 4

> **For every positive correspondence not discharged by a valid constructibility proof, absence of the required purpose-qualified appointment leaves the correspondence in custody with no numerical correctness claim, and every consumer requiring that claim refuses.**

### Exact replacement — point 5

> **`CAUSAL_INSTANTIATION` and `LEGAL_GOVERNANCE_CORRESPONDENCE` share one procedural `CorrespondenceAcceptanceEnvelope` but remain distinct substantive acceptance predicates with distinct qualification profiles and distinct authority purposes. One physical person may perform both only if separately qualified and separately appointed for both purposes. No appointment discharges the other purpose merely because the procedural envelope is shared.**

## 2. One adjudicator or two

| Object being counted | Result |
|---|---|
| Procedural envelopes | **1** |
| Substantive acceptance predicates | **2** |
| Competence profiles | **2** |
| Named authority purposes | **2** |
| Required appointments | **2 purpose-specific appointments** |
| Minimum physical humans established | **not established as 2** |
| Could one human hold both? | **Yes, if separately qualified and appointed twice** |

Wave не имеет warrant для proposition «обязательно два физических adjudicators». Она имеет warrant для **двух competencies и двух authority purposes**.

**The rule's economic argument fails and the rule is still correct but no longer cheap.**

Экономия остаётся на schema, sealing/provenance, review state machine, disagreement records, fixture tooling и custody plumbing. Она не установлена на truth predicate, domain qualification, positive gold population или calibration count.

## 3. Estimator, sample size and pre-declaration

### 3.1 Local fixed-binomial design

Для frozen Bernoulli loss:

\[
L_i=1\{\text{confident bind and independent gold says wrong}\}
\]

при fixed-horizon iid/effectively-independent observations:

\[
U=\mathrm{BetaQuantile}(1-\alpha;k+1,n-k).
\]

При `k=0`:

\[
U=1-\alpha^{1/n}.
\]

Для:

```yaml
target_local_error_ceiling: 0.01
alpha_cal: 0.05
k_confident_wrong: 0
```

получаем:

```yaml
n: 299
U: 0.0099691468
```

### 3.2 Critical semantic mismatch

Current CGF defines:

\[
P(\exists t\le\tau: confident\_wrong\_bind_t)\le\delta_{ground}
\]

with multiple risk components. Это не то же самое, что local per-draw `P(confident bind ∧ wrong)`.

Следовательно:

**packages do not converge on one estimator/sample size that may currently be published as the full PolicyOS `delta_ground`.**

`299` остаётся valid **conditional local design**, not the current end-to-end theorem.

### 3.3 CP vs Learn-then-Test

- Frozen binary loss + fixed final `n`: **exact one-sided binomial/Clopper–Pearson**.
- Threshold/rule selected from a family using calibration data: **Learn‑then‑Test**.
- Outcome-dependent stopping/adaptive label acquisition: **confidence sequence/e-process / active anytime-valid RCPS**, chosen before observation 1.

### 3.4 What `299` does and does not mean

It means:

- per declared stratum;
- effectively independent units;
- fixed final horizon;
- zero observed confident-wrong events;
- one local 95% upper confidence statement.

It does **not** mean:

- 299 arbitrary rows;
- 299 total across multiple hard strata;
- 299 plus unlimited synthetic negatives;
- sequential stop-when-green.

### 3.5 Executable procedure for next week

1. Freeze/content-bind binder, retrieval logic, corpus/reference snapshot, rule, validator and epoch.
2. Name the estimand explicitly before writing `delta_ground`.
3. Define independent source-cluster unit.
4. Define every load-bearing stratum before outcomes, including outcome-blind difficulty tier.
5. Enumerate eligible frame; retain denominator and hash.
6. Freeze sampling algorithm and seed.
7. Freeze `alpha_cal`, local ceiling, estimator, `n`, stopping rule and expiry.
8. Version constructed mismatches separately; do not add them to positive denominator merely because they are cheap.
9. Obtain purpose-qualified independent positive labels only after institutional lane exists.
10. Use `n=299,k=0` only if the ratified object is the fixed per-unit Bernoulli `.01/.05` rate.
11. Under-population, drift, error above target or missing gold terminates as `not_established`/historical.

**Do not spend the 299-positive adjudication budget until the `delta_ground`/horizon ambiguity is resolved.**

## 4. Adopt or invent

### Statistical side

Adopt, do not invent:

- selective/reject-option semantics;
- exact one-sided binomial inference for frozen binary loss;
- Learn‑then‑Test when rule selection is load-bearing;
- active anytime-valid RCPS when querying/stopping are adaptive.

Potential PolicyOS novelty is at most the **provenance-aware composition** of constructed oracle cases, independently appointed positive truth, predeclared strata and authority/custody semantics. That is currently a liability to validate, not an earned research-contribution claim.

### Legal side

Adopt:

- exact/versioned source anchoring;
- explicit interpretation trace;
- scope/exceptions/temporal competence;
- reverse/round-trip representation;
- separation of technical validation from legal alignment;
- substantive independent legal review.

**No checked source provides an expert-free general acceptance oracle for `Provision P governs named parameter θ`.**

PolicyOS would need a narrow conjunction:

```text
source identity
AND operative legal rule
AND legal subject
AND legal instrument
AND scope / jurisdiction / time / exceptions
AND quantity semantics
AND explicit semantic path to lever
AND independent legal alignment
```

## 5. Constructible correspondence classes

### Legal

R4 reports:

```text
executable current law→lever population:
  constructible: 0
  residue: 3
  denominator: 3

broader L3 threshold rows:
  capable of completing subject-aware proof
  against current lever schema: 0 / 374,516
```

These are **package-reported, unaudited counts**, not consolidator-recomputed facts.

L3 has legal-subject semantics; L6 lever lacks a canonical same-namespace legal-subject key. Units/range/threshold/provision/registry uniqueness cannot repair that missing semantic dimension.

### Did R4 run the legal transposition probe?

**No — not as a production execution.**

R4 accepts the original budget/tax mutation as commission-supplied and analytically applies its recognition rule. Under current schema both original and transposed pairs terminate `ambiguous` because the lever-side subject key is absent.

### Dimension match without subject match?

**R4's proposed rule does not admit it.** Missing subject yields `ambiguous` before unit/bound matching can prove correspondence.

Future risk: simply adding `legal_subject_id` is not enough if the same producer mints the field whose truth it is supposed to establish.

### Causal

R4 reports:

```text
internal proposal → owner atom:
  constructible: 3 / 3

canonical independent causal claims:
  constructible: 0 / 7,868

raw causal claims:
  constructible: 0 / 137,589
```

The `3/3` result is real only on the internal owner-controlled typed seam. It does **not** move the blocking independent evidence-binding seam.

### Critical path

Constructibility removes adjudication from:

```text
internal proposal → owner atom
```

It does not remove it from:

```text
independent causal evidence → proposal/typed atom
authoritative legal rule → lever
```

Therefore current constructibility **does not move the GY Phase‑5 critical path**.

## 6. Cheapest action that unblocks GY Phase 5

| Rank | Candidate | Relative cost | What it closes | What remains |
|---|---|---|---|---|
| **0** | Resolve `delta_ground` estimand/component semantics | Very low | Prevents wrong calibration campaign | No gold/appointment yet |
| **1** | One dual-qualified person, **two purpose-specific appointments** | Lowest direct institutional cost if available | Possible positive oracle for both | Two qualification showings; two appointments; separate populations/counts |
| **2** | Separate causal and legal specialists | Higher recurring cost | Cleanly supplies both lanes | Separate calibration burdens |
| **3** | Build non-circular legal subject spine + causal adjudicator | Significant engineering/legal-authority cost | Could shrink future legal residue | CG2 remains |
| **4** | Build typed external causal-evidence producer / active acquisition | Highest R&D cost | Could shrink future causal volume | Legal blocker remains |

One dual-qualified person can save **headcount**, not predicates or samples.

## 7. Contradictions

| ID | Position A | Position B | Disposition |
|---|---|---|---|
| C-01 | One substantive rule could discharge both | R1: two substantive predicates | **R1 better supported; replace point 5** |
| C-02 | R2: exact CP | R3: LTT core | **Layered reconciliation** |
| C-03 | R2: `.01,n=299` as `delta_ground` | R3/repository: horizon/composite `delta_ground` | **R3/repository better supported for current semantics** |
| C-04 | R1: positive correspondence needs adjudication | R4: some positive correspondence constructible | **Both true at different seams** |
| C-05 | Future legal subject spine enables construction | Legal-formalization literature retains substantive judgement | **Subject spine needs independently authoritative provenance** |
| C-06 | R1 suggests two reviewers + arbiter | Standing rule speaks of an adjudicator | **Open; do not ratify reviewer-count minimum** |

No disagreement found on `false bind > abstain`, publication grade ≠ gold, signature ≠ correctness, no post-outcome stratum, fail-closed missing gold, or subject ≠ units.

## 8. Citation verification

Load-bearing citations checked externally: TIDieR, Cochrane Handbook, BioCause, EU legislation annotation, LegalRuleML, Clopper–Pearson, RCPS, Geifman–El‑Yaniv, Learn‑then‑Test, Xu et al., TAC KBP, Mintz et al., Hoffmann et al., Kiryo et al., OECD Law as Code, Catala, Abidi–Libal, Bartolini–Lenzini–Santos, Witt et al., UCUM and target-trial methodology.

Results:

- **central citation not found:** none;
- **central citation misattributed:** none found;
- **material overstatement:** OECD supports “shared framework remains unsettled,” not a universal literature zero;
- **most important wave defect:** semantic mismatch between R2 local estimator and current CGF `delta_ground`.

## 9. Cross-package analogue sweep

| Defect | Sweep result |
|---|---|
| Legal transposition not freshly executed | **Analogue found in R1 and R4** |
| Per-unit vs horizon estimand mismatch | **R3 catches what R2 leaves unresolved** |
| Unit/dimension proxy replacing subject identity | **No unremarked sibling analogue** |
| Outcome-selected stratum | **No further analogue found** |
| Denominator mixing / sample-as-census | **No further analogue found** |
| Shared infrastructure mistaken for shared truth predicate | **No sibling repeats the error** |
| Upstream declaration treated as construction | **Future R4 risk; R3 supplies analogue** |
| Universal negative inferred from consultation | **R3 only; no sibling analogue** |

## 10. Consolidated result

1. Five-point rule survives **amended**.
2. Two substantive predicates, two competence profiles, two authority purposes.
3. One dual-qualified physical person remains possible, through two appointments.
4. `n=299` is supported only for a local fixed Bernoulli `.01/.05/k=0` design.
5. Statistical core should be adopted, not reinvented.
6. Legal prior art supplies validation procedure but no expert-free provision→parameter oracle.
7. Current constructibility does not remove either blocking correspondence from critical path.
8. Cheapest staffing route: one dual-qualified person with two appointments, after estimand semantics are resolved.
9. Nothing here opens GY Phase 5, promotes a capability, or appoints anyone.

---
title: Policy Design as a Causal Operating System — North Star
status: draft design decision — strategic direction (north star)
owner: team-architecture
created: 2026-06-24
last_reviewed: 2026-06-24
decision_status: proposed — the strategic frame the whole build is converging toward
supersedes: nothing
informs:
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
related:
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/system-design-decisions/policy-design-execution-topology.md
  - docs/reference/policy-design-case-failure-patterns.md
---

# Policy Design as a Causal Operating System — North Star

This is the one-page strategic frame the build is converging toward. The constitution
(`universal-policy-design-system-vision-and-organizing-rules.md`) is the law; this doc is
the **mental model** behind it. It is deliberately short.

## 1. The frame

The system is a **causal operating system for policy**. The mapping to a real OS is, in
places, exact — and where it breaks is where the value is:

| OS | This system |
|---|---|
| Physical memory / disk | Raw data (production data) |
| Processes / files (named objects over bytes) | Abstractions ("worker", "firm") as **communities over a causal variable graph** |
| System call | An **intervention** = a `do()` operation |
| Running machine state | The **world model** (a structural causal model) |
| Protection rings (kernel/user) | The **two-ring waist** / firewalls (candidate vs authority) |
| Virtual memory; page fault → page in | **Required vs available data**; a gap → **acquisition** |
| Scheduler / kernel | The control loop |

Unlike an OS, this one is **probabilistic, partially observable, with delayed and
confounded effects**: a "system call" returns a *distribution over future state changes*,
not a result. And unlike an OS, **leaky abstractions are the point** — operating on
"income" *must* leak into expenses, taxes, savings. We model the leakage; we do not
isolate it.

## 2. Everything reduces to data — but the causal STRUCTURE is not data

Abstractions are constructed from data. A "worker" is not an object; it is an
**identifier for a community in the variable graph** — a label asserting that an operation
on `income` will, with high probability, change the variables that compose it (expenses,
taxes, …). This is the structural-causal-model (SCM) view, and it is what makes the system
**universal**: no per-domain ontology, just variables + couplings + interventions.

Two load-bearing subtleties hide under "everything is data":

- **Couplings must be causal, not correlational.** An intervention propagates along
  `do()` edges, not co-variation. Confounded "high probability" makes interventions
  systematically wrong. The world model needs the *interventional* graph, not just the
  observational one (the identification problem; dowhy/econml).
- **The causal skeleton is a distinct, harder, partly-irreducible kind of knowledge.**
  Values are data; *structure* (which variable affects which) often cannot be learned from
  observation alone — it needs assumptions, experiments, and literature priors. This is why
  literature grounding (GY-K) and causal identification are load-bearing, not optional.

Communities are **context-relative** ("worker" in Kenya ≠ "worker" in Germany), so the
world model is regional and structure reuse across contexts is **transport** (cf. the
`transported_limited` forecast tier).

## 3. Interventions: the atom

An intervention is **direct** (a `do()` — a deterministic state edit: reduce budget by the
subsidy, hire a worker) carrying a **predicted distribution over downstream change** —
`P(Y | do(X))`, the **indirect** effect over time. The right atom is:

> **(one operator, one target-slot, one bundle of direct effects, one declared intended
> downstream effect)** — defined *relative to the world model's variable resolution*.

Refinements over the naive "one goal, one operation, one datum":

- Atomicity is about **one cause, not one effect**: "hire" is one operation with a
  *bundle* of immediate effects (budget −, headcount +, capacity +). Forcing "one datum"
  creates false decompositions; allow a structured effect record.
- **Goals are a separate selection layer.** One operation serves many goals; one goal
  needs many operations. Interventions declare an intended effect; *designs select and
  compose* interventions to meet goals. Do not bind one goal per intervention.
- **Atomicity is relative to model resolution.** "Reduce budget" is atomic iff budget is a
  node; against line-items it is a composite. Define the atom against the variable schema.

## 4. Designs: composition checked by simulation

A design is a composition of hundreds or thousands of atomic interventions, validated in
three stages: **individual** probable consequences → **pairwise** consistency → **joint**
consequences when applied together. Pairwise consistency does **not** imply global
consistency (interactions, general equilibrium, feedback). Joint validity requires
**simulation in the world model**, not a sum of effects. This combinatorial joint check is
the hardest technical wall.

## 5. Data, acquisition, and the real product

Data is **required vs available**; required is always larger. Available is the world model
(production data) where consequences are simulated; the gap is filled by **acquisition** —
finding/collecting what is missing (e.g. probable prices online). Acquisition is **VOI-
driven demand paging**: page in the data whose absence most threatens the *decision*, not
every missing datum.

The strategic consequence: **the primary product is the growing causal world model.**
Policies are programs/queries against it. The moat is the world model, not the generator.

## 6. The policy keeps living: two-tier observation grows the world model

A deployed policy is monitored and its effect is Bayesian-updated. This is **two contours
with different authority**, not a choice between them:

- **Confirmatory (high authority).** Pre-registered, powered, counterfactual-backed
  observation of the variables the design predicted it would change → clean attribution →
  Bayesian effect update. Rigorous but blind to surprises.
- **Exploratory (low authority).** Monitor the *whole* variable space for **anomalies** —
  changes the model did not predict — under false-discovery control
  (`ddm/calibration/multiple_testing`) and drift detection (`ddm/detectors`). An anomaly is
  a **candidate hypothesis** that must earn authority by passing into the confirmatory
  contour (a new edge in the graph, a new required-data spec, a new experiment).

The exploratory contour is the **engine of world-model growth**: discovered unpredicted
couplings become new modeled edges. It is more valuable *and* harder — and it runs on the
**same candidate→authority promotion** discipline as everything else.

## 7. The safety kernel: honest grounding is why this works

A thousand "universal policy engines" fail; an OS works because the kernel enforces
protection. Here, the protection is the **honest-grounding firewall**: every effect,
abstraction, and value is a **candidate until its causal grounding is resolved and
validated**; nothing becomes authority by presence/shape/self-attestation; the metric
reflects reality. The most dangerous failure of this OS is a **confident-wrong effect
prediction** — the world model says "this helps" on a fake or weak coupling — whose
consequence is not a red test but a harmful policy on real people. The whole grounding
discipline (entailment-not-lexical, honest-zero, no-relabel, candidate-firewall, the two-
ring waist) is therefore the **safety kernel** of this OS, not hygiene. See the failure
register (`docs/reference/policy-design-case-failure-patterns.md`).

## 8. The three binding constraints

1. **World-model fidelity** is the binding constraint — a poor model yields confident-wrong
   designs. Today integration is depth-1; this is the early game.
2. **Causal structure** is the hardest-to-ground, partly-irreducible knowledge — do not let
   "everything is data" hide it.
3. **Joint consistency** over thousands of interventions is a combinatorial wall — pairwise
   ≠ global; it needs joint simulation.

## 9. Relationship to the current build

This frame is the **B-on-A Generation Cycle at full zoom**. The generation cycle
(propose atomic interventions → ground their effects in the world model → value → revise →
promote → deploy → observe) is the first turn of this OS; the world model is the causal
engine (`foundry`) + the data substrate; acquisition is demand paging; the firewalls are
the safety kernel. GY-N0..N7 (the `GY-engine-subordination` plan, Phase 5) build the first
real cycle; the post-deployment two-contour observation loop is the next horizon beyond it.

## 10. Identity and boundary (ratified 2026-07-20)

The OS metaphor now has a ratified kernel boundary: the system is the **epistemic
custodian of policy justification** — it owns everything it signs for as long as the
signature stands, consumes everything others sign as typed evidence, and makes no claims
it cannot custody. §6's "the policy keeps living" is therefore not an optional next
horizon but the second half of the identity. The decades-scale horizon (a policy OS for
institutions — fleets, portfolios, interagency reliance) is reached by institutional
**adoption** of this custodial core, never by building an ERP. Scope adjudication:
`policyos-identity-and-custody-boundary.md`.

## Adopted reading clarification — 2026-10-21 (SDD-B01)

Approved by the human principal on G’s 2026-10-20 proposal. The
[decision record](../research/universal-policy-design/system-design-review-20261020/03-adoption-20261021.md)
records the options, scope, costs and revisit triggers. This scoped adoption does
not promote the standing of other sections or certify runtime implementation.

This dated clarification preserves the historical strategic frame above. It does
not ratify a new runtime contract or certify implementation.

- In §2, a singular world-model reference need not mean a single certain causal
  structure. The CGF §3 and search target already admit credal/set-valued
  references and competing admissible completions. Reuse those targets.
- In §3, `do()` is a model-side intervention. An institutional lever requires a
  separately grounded implementation relation, capacity, take-up/compliance,
  and relevant strategic responses. PolicyOS owns its scoped prediction and
  justification, not the external act or its execution (identity boundary).
- In §5, required versus available data is one part of required versus available
  grounds. W5-K01 also distinguishes relations, estimands, mandate, capacity,
  licence, authority and assurance. More observations cannot substitute for
  these objects. The size of a data gap is task-relative, not necessarily
  positive for every bounded task.
- In §7, grounding is claim-type-specific: causal effects and asserted causal
  relations require causal grounds; measurement claims require construct and
  method grounds; value choices require a declared frame and, for use on behalf
  of a principal, the applicable mandate. Causal identification cannot prove a
  political objective. Hypothetical value frames remain usable for explicit
  conditional candidate analysis under S0-K06.

Discriminator for future implementation: retain the same observation, trace,
model fit and source signature while falsifying the claimed semantic relation;
authority must not survive on those proxies. Conversely, an explicitly
hypothetical value frame must remain available for exploration without being
published as the principal's choice. No such test was run for this clarification.

## Adopted target extensions — 2026-10-21 (SDD-C01/C02)

Approved by the human principal on G’s 2026-10-20 proposal. The
[decision record](../research/universal-policy-design/system-design-review-20261020/03-adoption-20261021.md)
records the options, scope, costs and revisit triggers. This scoped adoption does
not promote the standing of other sections or certify runtime implementation.

C01 and C02 below are adopted changes to the target wording of §§4/6/8.
They qualify those historical passages without erasing them. Both choices were
explicitly approved on 2026-10-21; implementation admission remains separate.

**C01 — joint evaluation witness.** Retain the whole-design joint evaluation
obligation in §§4/8. In addition to simulation, allow an exact joint derivation
or another validated joint witness to establish the concrete property it
actually proves. This is not permission to replace joint analysis by pairwise
checks or sums of marginal effects. Neither mathematical exactness nor simulation
establishes the empirical truth of the model; grounding and implementation
obligations remain separate. Cost: each alternative needs an explicit property,
assumptions, consumer and falsifier. Revisit if a shortcut omits an interaction.

**C02 — inference plurality.** Retain Bayesian confirmatory updates as a supported
target, while permitting explicitly justified frequentist, sequential, robust
or partial-identification profiles for the proposition they support. Do not
silently mix posterior probability, coverage, identification sets and procedural
no-number claims. This expands the wording of §6; it does not appoint a method
owner or authorize posterior mutation. W5-K03 diagnosis/admission and current
profile-specific obligations still apply. Cost: inference semantics and bridges
must be qualified per method. Revisit if changing methods changes the estimand
or the claimed guarantee without being exposed.

> **Archived:** This document reflects plans as of 2026-04-01.
> See [current docs](../../explanation/index.md) for up-to-date information.

# PolicyOS Causal Engine — Research Agenda

> **Version**: 2.0
> **Date**: 2026-04-01
> **Status**: research-first; no implementation until each track's prerequisite result is in hand
> **Companion document**: `CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md`
>
> This document is the research companion to the implementation plan.
> It contains every task that cannot be scheduled as an engineering ticket
> because it requires a new theorem, an impossibility proof, or a formalization
> of an open mathematical problem before it can be implemented.
>
> **How to read this document**: each research track begins with an open problem,
> specifies what constitutes a sufficient result, defines the deliverable form,
> states which implementation-plan tasks depend on it, and identifies what can
> be run in parallel with other tracks.
>
> **Interpretation rule**: references to implementation-plan tasks in this
> document denote engineering scope and dependency targets, not completion
> status, unless an explicit dated implementation note says otherwise.
>
> **How research integrates with the system**: research artifacts enter as
> `FrontierSketch` objects with `max_readiness = PROOF_ONLY`. They are invisible
> to Layer D (governance, promotion) until their `required_for_promotion` checklist
> is satisfied and they graduate to full `FrontierArtifact`. They are never
> self-certifying. See `CAUSAL_ENGINE_IMPLEMENTATION_PLAN.md` section 3.4.

---

## Contents

1. [Overview: Why These Tasks Require Research First](#1-overview)
2. [Research Track 1 — Compositional Causality: Advanced Problems](#2-research-track-1)
3. [Research Track 2 — Sharp Bounds: Automation and Novel Families](#3-research-track-2)
4. [Research Track 3 — Continuous-Time: Rough Paths, Neural SDEs, and DSCM Semantics](#4-research-track-3)
5. [Research Track 4 — Distributional OT under Partial Identification](#5-research-track-4)
6. [Research Track 5 — Strategic Causality: Complex Equilibria and Performative Loops](#6-research-track-5)
7. [Research Track 6 — Causal Abstraction: Approximate and Continuous Bounds](#7-research-track-6)
8. [Research Track 7 — Algebraic Structure Beyond Conditional Independence](#8-research-track-7)
9. [Research Track 8 — Latent Representation Learning](#9-research-track-8)
10. [Research Track 9 — Hypergraph and Topological Interference](#10-research-track-9)
11. [Research Track 10 — Proximal Causal Inference: Bridge Functions and Operator Identification](#11-research-track-10)
12. [Research Track 11 — Recoverability and Missing-Data Calculus](#12-research-track-11)
13. [Research Track 12 — Intervention Hierarchy: Edge, Path, Stochastic, and Policy Interventions](#13-research-track-12)
14. [Research Track 13 — RKHS and Operator-Valued Causal Inference](#14-research-track-13)
15. [Research Track 14 — Causal Inference under Differential Privacy](#15-research-track-14)
16. [Research Track 15 — Causal Discovery via Nonstationarity and Regime Shifts](#16-research-track-15)
17. [Dependency and Parallelization Map](#17-dependency-and-parallelization-map)
18. [Anti-Swamp Governance for Research Tracks](#18-anti-swamp-governance)
19. [Research Economics and Kill Rules](#19-research-economics-and-kill-rules)

---

## 1. Overview

### 1.1. What "research-first" means here

A task is research-first if at least one of the following holds:

1. **No known theorem covers it**: the mathematical result needed does not yet exist or is not known to apply to the system's setting. Implementing without it means either building a system with false guarantees or building a system that silently falls back to a worse solution without saying so.

2. **The theorem exists but the formalization is open**: the result is known in the literature but translating it into a typed contract, a computable certificate, or a sound estimator requires non-trivial work that cannot be done without first understanding the formal conditions.

3. **The approach is inherently assumption-heavy and the right assumptions are unknown**: the implementation would require making choices that determine the mathematical soundness of the system, and those choices require research to validate.

4. **The deliverable is inherently a counterexample or impossibility result**: you cannot implement "the proof that X is impossible" without doing the mathematics first.

### 1.2. What counts as a sufficient research result

For each track, this document specifies what constitutes a result that unlocks the corresponding implementation. The bar is:

- a **theorem with conditions** (sufficient conditions that are machine-checkable, or a clear statement that says under which inputs the result holds), or
- an **impossibility result with a counterexample class** (which tells the system when to block and why), or
- a **reduction to a known solvable problem** (which tells the system what to compute and with what tool).

A sketch, a conjecture, or a heuristic that "usually works" does not unlock implementation.

### 1.3. How research runs alongside implementation

Research tracks can run in parallel with the implementation plan. They are not blockers for Wave 1 or Wave 2 engineering. The dependency is the other direction: implementation results from Wave 1 (in particular, A.1 + A.2 + A.4) make research more productive by providing:

- a canonical form for proof artifacts (`ProofBundle`, `BoundsBundle`);
- a data readiness oracle for empirical research questions;
- a judge stack that can give machine-readable verdicts on research artifacts when they mature.

Research conducted before these are available produces correct mathematics, but the integration work on graduation is higher.

### 1.4. Priority among research tracks

Not all tracks are equal. Based on the implementation plan's architecture, the policy system's needs, and external expert review (v2.0):

| Priority | Tracks | Reason |
|----------|--------|--------|
| Highest | Track 1 (compositional), Track 2 (sharp bounds) | Directly unlock production features; compositional is the primary moat |
| Highest | Track 10 (proximal), Track 11 (recoverability), Track 12 (intervention hierarchy) | **Expand the class of queries the proof kernel can accept.** These three tracks are the most practical gaps: they convert the engine from "strong identifier of effects" into "operating system of causal queries". Proximal handles hidden confounding via proxies (ubiquitous in admin data); recoverability handles missingness (ubiquitous in government data); intervention hierarchy handles realistic policy actions (which are never `do(X=x)`) |
| High | Track 3 (continuous-time + DSCM), Track 4 (OT) | Clear policy relevance; DSCM adds causal semantics for continuous-time/cyclic settings distinct from rough-path representation |
| High | Track 9 (topology / Hodge interference) | **Upgraded from long-horizon.** External review identifies this as the single most direct Fabric moat — it opens a problem class (higher-order group interactions, tenders, consortia, clustered spillovers) where EconML/CausalML have no native language |
| Medium | Track 5 (strategic), Track 6 (abstraction) | Unlock deeper versions of already-scoped reduced-scope engineering features |
| Medium | Track 7 (algebraic + semialgebraic) | Unlocks stronger version of E.1; semialgebraic negative certificates are architecturally valuable for proof kernel |
| Lower (long horizon) | Track 8 (latent), Track 13 (RKHS) | Very high potential moat; very high assumption load or does not expand query class |

---

## 2. Research Track 1 — Compositional Causality: Advanced Problems {#2-research-track-1}
**Status in implementation plan**: Phase B places B.4a (d-separation preservation) in engineering scope. B.4b and all items below remain research-first.

### 2.1. Open problem: identifiability preservation under latent interface variables

**What the problem is**: in Phase B, composition is restricted to observed interfaces between fragments. But real policy systems often share only latent common causes across domains (e.g., "institutional quality" mediates between a governance fragment and an economic fragment without being directly measured in either).

The question: under what conditions does a query that is identifiable in two individual fragments remain identifiable after composition through a latent interface, and what new assumptions does it require?

**Why it cannot be implemented without research**: the current d-separation preservation checker works on observed interfaces. For latent interfaces, the result is unknown in general. A "implementation" without the theorem would either falsely claim preservation or block all latent-interface compositions — both are wrong.

**Sufficient result**: a theorem family of the form "query Q is identifiable after composition through latent interface L if and only if conditions C hold", together with a constructive proof that generates a `CompositionCertificate` when C holds and a `NegativeCertificate` with a blocking set when C fails.

**Deliverable form**: theorem + counterexample library + formal conditions that can be checked at composition time.

**What it unlocks in the implementation plan**: B.4b; the full `CompositionCertificate.status = "preserved"` claim for non-trivial interface types.

---

### 2.2. Open problem: transfer of do-calculus derivations across fragment boundaries

**What the problem is**: B.4a checks d-separation graphically. The stronger question is whether a full do-calculus derivation or ID derivation produced in one fragment can be transported, composed, or reused after the fragment is glued with another — rather than re-derived from scratch on the composed graph.

**Why it cannot be implemented without research**: compositional do-calculus / ID is an active research area. The conditions under which proof traces compose are not fully characterized. Implementing "reuse the proof" without this characterization risks producing a system that claims identifiability by reusing a proof that no longer applies.

**Sufficient result**: a formal definition of "composable proof trace" and conditions under which a proof generated on fragment A remains valid for the same query on the composed graph, or a reduction showing that re-derivation is always required (which would justify caching results differently).

**Deliverable form**: theorem + proof trace format that records composability status + integration spec for `ProofBundle`.

---

### 2.3. Open problem: cyclic SCM fragment composition

**What the problem is**: the implementation plan restricts composition to acyclic DAG/ADMG fragments. But some policy domains have feedback loops that cannot be eliminated (e.g., price-wage dynamics, adaptive enforcement). A compositional engine that only handles acyclic fragments cannot address these cases.

**Why it cannot be implemented without research**: cyclic SCM semantics is an active research area with multiple competing formalizations (acyclic interventional, equilibrium-based, σ-calculus subfamilies). Composing cyclic fragments requires first establishing what "composition" means semantically for the chosen cyclic subfamilies and under what conditions the result has a well-defined interventional distribution.

**Sufficient result**: a formal semantics for a restricted class of cyclic fragments (e.g., equilibrium-stable cycles with known solution existence conditions) and conditions under which their composition is well-defined and auditable.

**Deliverable form**: theorem + scope statement (which cycle families are covered) + counterexample families (which cycles block composition) + integration spec for `SCMFragment` to declare cycle type.

---

### 2.4. Open problem: automatic latent bridge synthesis

**What the problem is**: the current `LATENT_BRIDGE` alignment type is human-mediated. The research question is whether it can be automatically proposed from measurement models, multi-environment evidence, or proxy data — without becoming a hallucination engine.

**Why it cannot be implemented without research**: the risk of false bridge synthesis (inserting a latent that "helps" alignment but is not real) is high. Automatic synthesis requires formal conditions under which a latent bridge hypothesis is testable, falsifiable, and improvement-over-no-bridge demonstrable.

**Sufficient result**: conditions under which a latent bridge can be proposed automatically (not just suggested) with a falsification test included, and conditions under which synthesis should be blocked entirely.

**Deliverable form**: formal conditions + synthesis algorithm (if feasible) + falsification test family + integration spec for `VariableAlignmentCertificate.latent_bridge_ref`.

---

### 2.5. Open problem: category-theoretic completeness

**What the problem is**: the implementation plan's compositional engine makes no completeness claim — it says "this is what we check" but not "this is everything that can be checked". A strong architectural claim would be that the composition certificate is complete: if the certificate says "preserved", it is actually preserved for all queries in a defined class.

**Why it cannot be implemented without research**: completeness requires a mathematical proof that the certificate captures all relevant identifiability information. This is a category-theoretic or algebraic claim that depends on which algebraic structure the composition is built on.

**Sufficient result**: a completeness theorem for the certificate for at least one well-defined subclass of queries, or a formal impossibility result showing that completeness cannot be achieved in general (which sets the expectation correctly).

**Deliverable form**: theorem + scope statement + integration as documentation annotation in `CompositionCertificate`.

---

## 3. Research Track 2 — Sharp Bounds: Automation and Novel Families {#3-research-track-2}
**Status in implementation plan**: Direction II places known bounds families (Balke-Pearl, Manski, existing semiparametric, transport bounds, sensitivity bounds) in engineering scope. The problems below remain research-first.

### 3.1. Open problem: sharpness proofs for complex query families

**What the problem is**: the `BoundsBundle` has a `sharpness_status` field. For known bounds (LP bounds, Manski), sharpness is established in the literature and can be claimed directly. But for more complex query families — e.g., policy-relevant conditional queries, cross-graph queries after composition, queries with multiple treatment arms — sharpness is often unknown.

**Why it cannot be implemented without research**: claiming `sharpness_status = "sharp"` without a proof is misleading. The only honest alternative is `"inner_approx"` or `"outer_approx"`, which weakens the system's value proposition for non-trivial queries.

**Sufficient result**: a sharpness theorem for at least one class of non-trivial queries that arises in the policy use cases, with a dual certificate form that can be stored in `dual_certificate_ref`.

**Deliverable form**: theorem family by query class + dual certificate format + integration spec for `BoundsBundle.dual_certificate_ref`.

**Practical priority**: high. Every non-trivial query that the system returns bounds for but cannot certify as sharp is an opportunity to build a moat that competitors cannot match.

---

### 3.2. Open problem: automated bound tightening with soundness guarantees

**What the problem is**: bounds can often be tightened by adding assumptions, conditioning on additional variables, or using instrument families. An automated procedure that searches for tighter bounds is useful — but only if it comes with a soundness guarantee: it either returns a provably tighter bound or stops and says why it cannot.

**Why it cannot be implemented without research**: a search procedure without soundness guarantees is just heuristic tightening. It might produce bounds that are not valid, or might silently drop to a weaker result without disclosure. The implementation plan requires that every `sharp` claim comes with a dual witness. Without the theory, the procedure cannot produce such witnesses.

**Sufficient result**: a sound search procedure with formal stopping conditions: it either returns a certified tighter bound or returns a proof that the current bound is the best achievable in the given class.

**Deliverable form**: algorithm + soundness proof + integration spec for `BoundsBundle` and `RecoveryPlan`.

---

## 4. Research Track 3 — Continuous-Time: Rough Paths, Neural SDEs, and DSCM Semantics {#4-research-track-3}
**Status in implementation plan**: Phase C places C.1–C.3 (linear SDE + piecewise ODE) in engineering scope. C.4 and the problems below remain research-first.

> **Architectural note (v2.0)**: this track now explicitly separates two orthogonal concerns that were previously conflated:
> 1. **Representation** — how to encode irregular/asynchronous trajectories numerically (rough paths, signatures). This is primarily a Fabric/C-layer concern.
> 2. **Causal semantics** — what interventions, counterfactuals, and identification mean in continuous-time, cyclic, or latent-confounded dynamic settings (DSCM, σ-separation). This is primarily an A-layer/proof-kernel concern.
>
> Rough paths alone do not provide causal semantics; DSCM/σ-separation provides semantics but not necessarily the numerical representation. The engine needs both, and they must be developed with clear interface contracts between them.

### 4.1. Open problem: causal semantics for rough-path and irregular sampling regimes

**What the problem is**: real policy data often arrives at irregular intervals (administrative records, event-driven data, emergency registrations). The continuous-time engine assumes a sampling scheme. For irregular sampling, the connection between the observed discrete samples and the underlying continuous causal process requires a causal theory that is more general than standard SDE/ODE semantics.

**Why it cannot be implemented without research**: rough path theory provides a mathematical framework for irregular paths, but the causal interpretation of interventions and counterfactuals in this regime is not established. "What does do(X(t) = x) mean when t is from an irregular grid?" requires a formal answer before any estimator can claim causal validity.

**Sufficient result**: a formal definition of causal interventional semantics in the rough-path regime, with conditions under which trajectory-level estimands are identifiable, and what constitutes a proof artifact for such estimands.

**Deliverable form**: formal semantics + identifiability conditions + proof artifact format + integration spec for `EffectTrajectoryBundle.path_representation`.

---

### 4.2. Open problem: identification theory for neural SDE / neural CDE

**What the problem is**: the implementation plan covers linear SDE and piecewise ODE backends. Neural SDE and neural CDE are more flexible models with better empirical fit in complex systems. But their use as causal objects (not just predictive models) requires an identifiability theory: under what conditions is a trajectory-level causal estimand identified when the data-generating process is a neural SDE?

**Why it cannot be implemented without research**: neural SDE/CDE are universal approximators. Universality is a problem for identification: you can fit the observed data with infinitely many different causal structures. Without a theory that specifies which identifiable functionals can be estimated from a neural SDE model, any causal claim made from such a model is ungrounded.

**Sufficient result**: an identifiability theorem for at least one class of trajectory-level estimands under a neural SDE / neural CDE model class, with explicit assumptions stated.

**Deliverable form**: theorem + assumption list + scope statement + integration spec for `EffectTrajectoryBundle`.

---

### 4.3. Open problem: conditions for valid discrete-to-continuous causal translation

**What the problem is**: the system uses discretization as a fallback. But discretization changes not just the numerical approximation error — it can change the causal meaning of the estimand. The question is: when does a discretized version of a continuous causal query produce an answer that is causally equivalent to the continuous answer, and when does it produce a causally distinct (and potentially misleading) quantity?

**Why it cannot be implemented without research**: the numerical literature on discretization error says nothing about causal equivalence. A system that reports `discretization_error = 0.001` but doesn't know whether the discretized estimand has the same causal interpretation as the continuous estimand is hiding a potentially large error from the user.

**Sufficient result**: formal conditions under which a discretization scheme preserves causal meaning (not just numerical approximation), and a certificate that can be attached to `EffectTrajectoryBundle.solver_diagnostics_ref` when those conditions are met.

**Deliverable form**: theorem + certificate format + integration spec.

---

### 4.4. Open problem: dynamic SCM semantics and σ-separation for proof kernel

**What the problem is**: the current proof kernel operates on DAG/ADMG with discrete time steps. Dynamic SCM (DSCM) formalizes endogenous variables as functions of continuous time, admits cycles and latent confounding, and uses σ-separation (not d-separation) as the graphical Markov criterion. The Forré-Mooij framework provides graphical Markov properties for cyclic and latent-variable settings, but translating these into machine-checkable certificates for the proof kernel is an open problem.

This is distinct from rough paths (4.1) and neural SDE (4.2): those problems concern representation and estimation. DSCM/σ-separation concerns the semantics of what "cause" means when the system has feedback loops, continuous-time evolution, and latent confounders simultaneously.

**Why it cannot be implemented without research**: the proof kernel's identification algorithms (ID, IDC, transport) are built on d-separation and acyclic semantics. Extending them to σ-separation requires: (a) a formal mapping from σ-separation conditions to identification certificates, (b) conditions under which cyclic identification is well-defined (solution existence and uniqueness for the structural equations), (c) a clear specification of which intervention types are admissible in cyclic/dynamic settings. Without this, the proof kernel would either reject all cyclic queries (too conservative) or accept them without proper certificates (unsound).

**Sufficient result**: a formal integration of σ-separation into the proof kernel's certificate system, with: (a) conditions under which a DSCM query is identifiable via σ-separation, (b) a constructive certificate that records the σ-separation argument, (c) explicit scope statement for which cycle families (equilibrium-stable, convergent, etc.) are covered, (d) formal connection to local independence for continuous-time processes.

**Key literature starting points**: Forré-Mooij (2018, 2020) on Markov properties for cyclic/latent SCMs; Mogensen-Hansen on local independence and causal graphs for continuous-time processes; Bongers et al. (2021) on foundations of structural causal models.

**Deliverable form**: σ-separation certificate format + identification algorithm extension + cycle-family scope statement + integration spec for `ProofBundle` to accept DSCM-based proofs.

**Relationship to other track items**: Track 3.1 (rough-path semantics) provides the representation layer that DSCM queries will ultimately be estimated on. Track 1.3 (cyclic composition) addresses composing cyclic fragments; this track addresses the semantics within a single cyclic/dynamic system. Track 3.2 (neural SDE identification) is a downstream consumer: neural SDE is a model class, DSCM is the semantic framework that says which queries on that model class are identifiable.

---

### 4.5. Open problem: local independence and Granger-causal semantics in continuous time

**What the problem is**: for continuous-time event processes (point processes, marked processes, administrative event logs), the natural causal notion is local independence, not d-separation. Local independence gives graphical Markov properties for counting processes and filtration-based models. The question is: when does local independence yield identification of policy-relevant causal effects, and how does this relate to the proof kernel's certificate system?

**Why it cannot be implemented without research**: local independence is well-studied in the statistics literature (Didelez, Mogensen-Hansen), but it has not been formalized as a proof-kernel-compatible identification procedure. The gap is: local independence gives testable implications and conditional independence structures, but the translation to "this causal effect is identified" requires conditions that are not yet formalized in a certificate-carrying form.

**Sufficient result**: identification conditions for at least one class of causal effects in continuous-time event processes via local independence, with a certificate format compatible with `ProofBundle`.

**Deliverable form**: theorem + certificate format + integration spec for event-process queries in the proof kernel.

---

## 5. Research Track 4 — Distributional OT under Partial Identification {#5-research-track-4}
**Status in implementation plan**: Phase D places D.1 in reduced engineering scope with `justification = SCENARIO` as default. `BOUNDED` and `IDENTIFIED` justification for distributional estimands remain research-gated by the work below.

### 5.1. Open problem: causally justified OT couplings under partial identification

**What the problem is**: the implementation plan's `DistributionalJustification` enum has three levels. Currently, the system can only support `SCENARIO` without a proof kernel extension. The `BOUNDED` level requires knowing which distributional bounds are valid under partial identification, and the `IDENTIFIED` level requires a theory of when the full counterfactual distribution is identified.

**Why it cannot be implemented without research**: OT produces beautiful couplings between distributions. The question of whether a specific coupling is causally meaningful — i.e., whether it corresponds to a counterfactual joint distribution — depends on the underlying identification argument. Without this theory, any `BOUNDED` or `IDENTIFIED` claim is false precision.

**Sufficient result**: conditions under which the counterfactual distribution of Y under do(X=x) is identified or bounded, together with a proof artifact format that the proof kernel can produce for distributional queries.

**Deliverable form**: theorem + proof artifact extension for distributional estimands + integration spec for `DistributionalEffectBundle.justification` and `causal_assumptions`.

**Practical priority**: high. The `SCENARIO` level is already useful, but the moat requires being able to say "this distributional comparison is causally valid" — not just "this is an interesting scenario".

---

### 5.2. Open problem: bounded distributional effects for tail risk and subgroup shifts

**What the problem is**: even without full identification, it may be possible to bound specific distributional quantities — tail probabilities, quantile shifts, concentration changes — under partial identification assumptions. This would allow the system to say "we cannot identify the full counterfactual distribution, but we can certify that the top decile share decreases by at least X%" under stated assumptions.

**Why it cannot be implemented without research**: distributional bounds under partial identification is an active research area. The bounds depend on which assumptions are invoked and which query functional is targeted. Implementing bounds for specific functionals without knowing whether they are valid under partial ID would produce false confidence.

**Sufficient result**: bounds theorems for at least two policy-relevant distributional functionals (e.g., tail probability change, quantile shift) under partial identification, with the conditions stated explicitly.

**Deliverable form**: theorem family + bound format extending `BoundsBundle` for distributional queries + integration spec.

---

### 5.3. Open problem: extending the proof kernel to distributional estimands

**What the problem is**: currently, the proof kernel (`ProofKernel.identify`) works on scalar and functional estimands. The `justification` field in `DistributionalEffectBundle` must be set by the proof kernel (not by the OT module), but the proof kernel does not currently have a formalization of "identify the counterfactual distribution of Y under do(X=x)".

**Why it cannot be implemented without research**: formalizing distributional estimands in the proof kernel requires extending the ID algorithm to distribution-valued queries. This is a known open problem in the identification literature — it is not simply "run ID on each quantile separately".

**Sufficient result**: a formal definition of the distributional estimand class that the proof kernel can handle, and an extension of the ID/IDC algorithm to these estimands (or a reduction showing that identification of the full distribution reduces to known scalar results under specific conditions).

**Deliverable form**: algorithm extension + proof artifact format + integration spec for `ProofKernel.identify` to accept distributional queries.

---

## 6. Research Track 5 — Strategic Causality: Complex Equilibria and Performative Loops {#6-research-track-5}
**Status in implementation plan**: Phase D places D.2 in reduced engineering scope for Stackelberg / simple best-response equilibrium with fatal compute budget. The problems below remain research-first.

### 6.1. Open problem: equilibrium computation for complex strategic environments

**What the problem is**: the implementation plan restricts strategic computation to simple game forms. For more realistic policy environments — e.g., oligopolistic markets, multi-agency regulatory responses, strategic financial compliance — the game structure is more complex and the equilibrium may not exist, may not be unique, or may be NP-hard to compute.

**Why it cannot be implemented without research**: the question is not just "which algorithm to use" but "which game classes are admissible for policy recommendations at all". For some game classes, the system should block entirely (non-existence or NP-hard). For others, it should return strategic bounds. The classification of game classes by their tractability and their policy-appropriate fallback behavior requires research.

**Sufficient result**: a classification of policy-relevant game classes by: (a) equilibrium existence conditions, (b) computational complexity class, (c) appropriate fallback in the `StrategicFallbackMode` hierarchy. This classification becomes part of the `StrategicSCM` contract.

**Deliverable form**: classification table + existence theorem per game class + integration spec for `StrategicSCM.equilibrium_concept` to be extended with new game types.

---

### 6.2. Open problem: performative prediction convergence and instability

**What the problem is**: when the policy system issues a recommendation, agents adapt to it, changing the data-generating process. The next recommendation is then made on the new process. This creates a feedback loop ("policy → adaptation → new data → revised policy"). Whether this loop converges, oscillates, or diverges is not determined by the causal structure alone — it depends on the strategic learning dynamics of the agents.

**Why it cannot be implemented without research**: the system currently models strategic adaptation at a single point in time (one-shot equilibrium). The question of convergence in the policy loop is a dynamic game theory / performative prediction question. Without convergence theory, the system cannot know whether iterating recommendations is safe or whether it is amplifying instability.

**Sufficient result**: convergence conditions for the policy loop under at least one realistic adaptive agent model, and a formal definition of the instability certificate that should be issued when those conditions fail. The certificate should be attached to `StrategicResponseBundle.performative_shift_ref`.

**Deliverable form**: convergence theorem + instability certificate format + integration spec.

---

### 6.3. Open problem: decomposition of post-policy outcome into causal and strategic components

**What the problem is**: the `StrategicResponseBundle` already requires a decomposition into `causal_component_ref` and `strategic_closure_ref`. But the conditions under which this decomposition is unique, well-defined, and interpretable are not established in general. For some game structures, the two components may not be separable.

**Why it cannot be implemented without research**: if the decomposition is not uniquely defined, reporting two numbers as "causal" and "strategic" is misleading. The implementation plan's cardinal rule says strategic output must not present post-adaptation policy value as a simple causal effect. This rule requires knowing when the decomposition is valid.

**Sufficient result**: formal conditions under which the causal-strategic decomposition is unique and interpretable, and conditions under which it does not exist (which trigger a `BLOCKED` mode with explicit failure card).

**Deliverable form**: theorem + decomposition conditions + integration spec for `StrategicResponseBundle`.

---

### 6.4. Open problem: Mean Field Game equilibrium for macro-policy causal inference

**What the problem is**: Track 5 covers Stackelberg games and performative prediction, which treat strategic interaction as discrete best-response cycles between a small number of agents. When a policy acts on millions of independent agents — pension age changes, income tax structure, housing benefit rules — the discrete-agent approach is computationally intractable. Mean Field Game (MFG) theory models this as a continuum limit: each agent solves a Hamilton-Jacobi-Bellman (HJB) control problem given the population distribution, while the distribution itself evolves according to a Fokker-Planck (FP) equation. The resulting equilibrium is a fixed point of the coupled HJB-FP system.

The open problem: how do `do(X=x)` interventions on the structural causal model translate into well-defined perturbations of the MFG equilibrium, and what are the identifiability conditions for causal effects estimated against an MFG background distribution?

**Why it cannot be implemented without research**: integrating SCM semantics with MFG requires resolving three open questions simultaneously: (a) what constitutes a "causal intervention" in the continuum-agent setting — is it a node intervention on the representative agent's HJB, a distributional shift in the population, or both; (b) whether the interventional distribution `P(Y | do(X=x))` computed against the MFG background satisfies any form of d-separation or σ-separation that the proof kernel can exploit; (c) stability — an intervention may shift the system to a different MFG equilibrium, in which case the post-intervention outcome is not simply the pre-intervention outcome with a perturbation but a solution to a new fixed-point problem. Without resolving these, any numerical estimate of a "causal effect" in an MFG setting is uninterpretable.

**Sufficient result**: a formal mapping from SCM interventions to MFG perturbations, with: (a) conditions under which the perturbed MFG has a unique equilibrium, (b) identification conditions for the policy-level causal effect against the MFG background, (c) a convergence bound on the Fokker-Planck evolution toward the new equilibrium, (d) a certificate format that records the equilibrium stability argument.

**Key literature starting points**: Lasry-Lions (2007) for the original MFG formulation; Carmona-Delarue (2018) for probabilistic MFG theory; Cardaliaguet et al. for master equation approaches; Achdou et al. for numerical MFG methods (finite difference for HJB-FP systems).

**Deliverable form**: formal mapping theorem (SCM intervention → MFG perturbation) + equilibrium uniqueness conditions + causal identification conditions in MFG setting + certificate format for `StrategicResponseBundle.mfg_equilibrium_ref` + integration spec for Fabric macro-simulation numerics.

**Relationship to other tracks**: this is the canonical bridge between Track 3 (continuous-time dynamics and Fokker-Planck evolution) and Track 5 (strategic equilibrium and performative causality). Track 12 (stochastic interventions) provides the intervention type — in the MFG setting, macro-policy interventions are naturally stochastic (distributional) rather than point-valued. Track 6 (causal abstraction) is the dual: MFG is one principled way to perform micro-to-macro aggregation, and its approximation error relative to a discrete multi-agent model is a special case of Track 6's abstraction bounds.

---

## 7. Research Track 6 — Causal Abstraction: Approximate and Continuous Bounds {#7-research-track-6}
**Status in implementation plan**: Phase D places D.3 in engineering scope for exact abstraction verification in finite-state SCMs. The problems below remain research-first.

### 7.1. Open problem: approximate abstraction error bounds for continuous and non-finite models

**What the problem is**: exact abstraction (the implementation plan's D.3 scope) verifies that a macro-level model is a faithful image of a micro-level model. For continuous-state models, exact verification is generally impossible. The question is: can we bound the error introduced by an approximate abstraction — and make that bound computable and meaningful for policy recommendations?

**Why it cannot be implemented without research**: approximate abstraction in continuous models requires a theory of abstraction loss. Heuristic aggregation ("average the micro-level effects") does not constitute an abstraction bound. Without a formal bound, the system cannot tell the analyst whether the macro-level recommendation is reliable or whether it is dominated by abstraction error.

**Sufficient result**: a computable error bound for at least one class of continuous-state SCM abstractions, with conditions under which the bound is tight, and a certificate format that can be stored in `AbstractionCertificate.error_bound`.

**Deliverable form**: theorem + error bound computation algorithm + integration spec for `AbstractionCertificate`.

---

### 7.2. Open problem: conditions for faithful micro-to-macro causal transport

**What the problem is**: the `AbstractionCertificate.preservation_type` field has four values including "approximate". The question is: when is a macro recommendation a faithful projection of the micro structure, as opposed to a useful-but-misleading aggregation? This is the core question of causal abstraction theory.

**Why it cannot be implemented without research**: the faithfulness condition in causal abstraction is known for specific abstraction types (omega-consistency) but not for the general case relevant to policy systems. Without this characterization, the system cannot populate `preserved_queries` reliably for the approximate case.

**Sufficient result**: formal conditions for faithful micro-to-macro causal transport for at least one policy-relevant class of aggregations (e.g., averaging over agent types, spatial aggregation), together with the set of estimands that are preserved under each condition.

**Deliverable form**: theorem + preserved estimand characterization + integration spec for `AbstractionCertificate`.

---

## 8. Research Track 7 — Algebraic Structure Beyond Conditional Independence {#8-research-track-7}
**Status in implementation plan**: Phase E places E.1 in engineering scope for known CI-based and standard algebraic constraints. The problems below remain research-first.

> **Scope expansion (v2.0)**: this track now explicitly includes semialgebraic statistics and computational algebraic geometry as a subfield. The original scope focused on "constraints beyond CI" in general terms. The expanded scope recognizes that polynomial constraints, Groebner bases, hidden-variable invariants, and model-class membership testing form a distinct and valuable capability — particularly for the proof kernel's negative certificates. Sometimes one can prove that an observed distribution is incompatible with a given SCM class *before* attempting effect estimation, which is a powerful form of model falsification that no current causal library offers.

### 8.1. Open problem: algebraic model testing beyond conditional independence

**What the problem is**: the current `AlgebraicConstraintReport` covers constraints that reduce to conditional independence tests and standard tetrad/overcomplete system checks. A richer class of constraints — trek rules, generalized Verma constraints, algebraic geometry constraints on the parameter space — would allow the system to test model validity more powerfully and to rank graphs more accurately.

**Why it cannot be implemented without research**: algebraic constraints beyond CI require: (a) a characterization of the constraint set for the model class, (b) a test procedure for finite samples, (c) severity semantics (what does a violation imply for the causal claim?). None of these are fully established for the general case.

**Sufficient result**: a characterized family of algebraic constraints beyond CI that are testable in finite samples with known Type I/II error rates, together with severity semantics that tell the system whether a violation is a blocker, a warning, or an info signal for graph ranking.

**Deliverable form**: constraint family definition + test procedures + severity mapping + integration spec for `AlgebraicConstraintReport`.

---

### 8.2. Open problem: finite-sample algebraic model testing under noise and misspecification

**What the problem is**: even for constraints that are known in theory, testing them on finite, noisy, possibly misspecified data requires its own research. The question is not "does the constraint hold in the population?" but "what is the appropriate tolerance and power for the test, and how do we calibrate severity?"

**Why it cannot be implemented without research**: algebraic constraint tests on finite samples can have very different behavior than their population-level counterparts. Under misspecification, a valid model may fail its own algebraic tests. Without calibration research, the system cannot set severity tiers without either blocking too many valid graphs or missing real violations.

**Sufficient result**: calibration benchmarks for at least one class of algebraic tests beyond CI, with Type I/II error characterization under realistic misspecification scenarios.

**Deliverable form**: calibration benchmark suite + severity tier mapping + provisional threshold recommendations for `JudgeThresholdRegistry`.

---

### 8.3. Open problem: semialgebraic negative certificates and SCM class incompatibility

**What the problem is**: beyond testing individual constraints, a structurally deeper question is whether the observed joint distribution is compatible with a given *class* of SCMs at all. Polynomial constraints on observed distributions implied by latent-variable models can sometimes prove that no member of a hypothesized model class could have generated the data. This is a negative certificate of a fundamentally different kind from non-identification: it says "the model is wrong", not "the effect is unidentifiable".

Groebner bases and elimination theory provide the algebraic machinery to derive such constraints. Hidden-variable invariants (e.g., the instrumental inequality, Bell-type inequalities for causal structures) are special cases of this general framework.

**Why it cannot be implemented without research**: deriving the complete set of polynomial constraints for a given SCM class is computationally expensive (doubly exponential in the worst case) and not currently automated for general causal structures. The questions are: (a) for which SCM classes can the constraint set be computed tractably, (b) how to test membership in finite samples with calibrated error rates, (c) how to integrate the result as a `NegativeCertificate` in the proof kernel.

**Sufficient result**: a tractable computation of the polynomial constraint set for at least one policy-relevant SCM class with hidden variables, together with a finite-sample test and a certificate format that the proof kernel can use to block estimation on incompatible data.

**Key literature starting points**: Geiger-Meek on polynomial constraints for DAGs with hidden variables; Garcia-Stillman-Sturmfels on algebraic geometry of Bayesian networks; Kang-Tian on inequality constraints for causal inference.

**Deliverable form**: constraint computation algorithm (for tractable classes) + finite-sample test + `NegativeCertificate` format for model-class incompatibility + integration spec for proof kernel.

---

## 9. Research Track 8 — Latent Representation Learning {#9-research-track-8}
**Status in implementation plan**: Phase E places E.3 in engineering scope as a governance gate (`PROOF_ONLY` cap). Latent variable proposals remain blocked from promotion until the problems below are resolved.

### 9.1. Open problem: latent variable cardinality identification from distributional shifts

**What the problem is**: the system can detect that "there is probably a hidden variable here" from multi-environment data, but it cannot determine how many latent variables are needed, what their type is, or what their causal role is. This distinction matters enormously: proposing one hidden confounder versus three latent trait dimensions leads to very different models and very different policy implications.

**Why it cannot be implemented without research**: latent cardinality identification is an open problem in general. Results exist for specific model classes (linear models, specific measurement models), but these are rarely directly applicable to the policy system's setting. Without a cardinality identification theory for the relevant model classes, the system cannot know whether it is hallucinating a single confounder when there are three.

**Sufficient result**: conditions under which the number and role (confounder, mediator, moderator) of latent variables is identified from multi-environment distributional shifts, for at least one policy-relevant model class.

**Deliverable form**: theorem + identification conditions + integration spec for `LatentDiscoveryBundle.proposed_latent_nodes` and `identification_conditions`.

---

### 9.2. Open problem: separating latent confounding, proxy mismatch, and measurement error

**What the problem is**: when the system detects an anomaly in the data (poor fit, unexpected correlations, environment-specific inconsistencies), it must distinguish between three explanations: (1) there is a hidden confounder, (2) a proxy variable is a bad proxy, (3) there is measurement error. These three explanations have different implications for recovery.

**Why it cannot be implemented without research**: distinguishing these three explanations from observational data requires both a formal model that nests all three and an identification argument that separates them. In general, they are confounded with each other.

**Sufficient result**: conditions under which at least two of the three explanations can be separated from multi-environment or multi-proxy data, together with a falsification test that distinguishes them.

**Deliverable form**: theorem + falsification test family + integration spec for `LatentDiscoveryBundle.trust_level` promotion conditions.

---

### 9.3. Open problem: promotion criteria for latent artifacts above PROOF_ONLY

**What the problem is**: the current system permanently caps latent artifacts at `PROOF_ONLY`. To ever allow latent proposals to influence policy-grade analysis (even at `BOUNDS_READY`), the system needs formal promotion criteria: what evidence is sufficient to say "this latent variable hypothesis is not just a speculation"?

**Why it cannot be implemented without research**: promotion criteria for latent artifacts require a formal theory of falsifiability for latent variable hypotheses. Unlike observed variables, latent variables cannot be directly validated. The question is what combination of testable implications, environment stability, and external evidence is sufficient to elevate a latent proposal above pure speculation.

**Sufficient result**: formal promotion criteria specifying which falsification tests, environment assumptions, and external evidence are sufficient to elevate a `LatentDiscoveryBundle` from `trust_level = "research"` to `trust_level = "conditional"`, and from `"conditional"` to `"validated"`.

**Deliverable form**: promotion criteria document + integration spec for `LatentDiscoveryBundle.trust_level` and `FrontierArtifact.readiness_cap`.

---

## 10. Research Track 9 — Hypergraph and Topological Interference {#10-research-track-9}
**Status in implementation plan**: Phase F places F.1 (`InteractionComplex` and `InterferenceCertificate` contracts) in engineering scope. F.2–F.4 remain research-first.

> **Priority clarification (v2.0)**: external review elevated this track's practical priority. The topological interference engine is the single most direct Fabric moat — it moves the system from "estimate CATE on rows" to "reason over group interactions, markets, tenders, consortia, clustered spillovers". This is a problem class where EconML/CausalML have no native language. The Hodge/simplicial module should be the first heavy Fabric numeric kernel, not a distant horizon lane.
>
> **Recommended first benchmark proxy**: an auction micro-complex on 10 nodes — two 2-simplices σ1=(A,B,C) and σ2=(D,E,F), one bridge edge C—D, one government procurer G, and three peripheral nodes U,V,W. Treatment is a subsidy or preference assigned to node A or edge G-A. Outcome is noise-free: `Y_i = α·direct_i + β·pairwise_exposure_i + γ·simplex_exposure_i + δ·bridge_exposure_i`. This gives four verifiable regimes: (1) γ>0, β=δ=0 reveals pure higher-order effect; (2) removing B2 must eliminate the higher-order channel; (3) moving treatment to peripheral U must zero simplex spillover; (4) reversing simplex orientation must not change node-level outcomes but must predictably flip edge-flow quantities. This is minimal, analytically transparent, and tests exactly what the Hodge module is built for.

### 10.1. Open problem: simplicial complex identification theory for interference

**What the problem is**: pairwise interference estimation (the current production capability) assumes that spillovers travel along edges in a graph. For many policy-relevant settings (classrooms, supply chains, household networks), spillovers are group-level: the effect on unit i depends on the joint treatment status of a group, not just individual neighbors.

The identification question: when is a group-level interference effect identified from experimental or observational data, under what exposure model assumptions, and what are the structural conditions on the simplicial complex that allow identification?

**Why it cannot be implemented without research**: simplicial complex identification theory is an emerging research area. Unlike pairwise interference (where identification results are established for clustered and network-based designs), the identification theory for simplicial / hypergraph interference is not yet available in a form that can be directly translated into certificates.

**Sufficient result**: an identification theorem for at least one class of group-level interference effects on a defined class of simplicial complexes, together with the exposure model assumptions that are required, and a proof that the estimate reduces to known pairwise/clustered estimators under the appropriate simplicial structure.

**Deliverable form**: theorem + exposure model class + proof of reduction to pairwise baseline + integration spec for `InterferenceCertificate.supported_query_family`.

---

### 10.2. Open problem: exposure-complex estimators with honest pairwise fallback

**What the problem is**: assuming that a simplicial identification theorem exists (Track 9.1), the next question is what estimator to use. The requirement from the architecture is that this estimator honestly reduces to pairwise or clustered estimators when the topology is not identified — rather than silently producing a number that looks like a pairwise estimate but is actually based on an invalid hypergraph assumption.

**Why it cannot be implemented without research**: designing an estimator with this honest-reduction property requires specifying the exact conditions under which the hypergraph structure is estimable, and ensuring the fallback is triggered at the right moment. This is an estimation theory question, not just a software engineering question.

**Sufficient result**: an estimator that comes with: (a) conditions for when the hypergraph structure is estimable from data, (b) a provably correct fallback to pairwise/clustered mode when those conditions fail, and (c) a certificate that records which mode was used.

**Deliverable form**: estimator + estimability conditions + fallback certificate format + integration spec for `InterferenceCertificate.fallback_mode`.

---

### 10.3. Open problem: bounds on reduction error from hypergraph to pairwise projection

**What the problem is**: the implementation plan's `InterferenceCertificate.reduction_error_bound` field is currently `None` in the contracts. When the system reduces a complex interference topology to pairwise or clustered mode, it does so with a currently unbounded error. For policy recommendations to be honest, this error must be characterized.

**Why it cannot be implemented without research**: bounding the reduction error requires a formal model of what is lost when you project a simplicial complex into a graph. This loss depends on the topology, the intervention type, and the exposure model.

**Sufficient result**: an error bound for the pairwise/clustered projection for at least one class of simplicial complexes and one class of intervention designs.

**Deliverable form**: theorem + bound computation algorithm + integration spec for `InterferenceCertificate.reduction_error_bound`.

---

## 11. Research Track 10 — Proximal Causal Inference: Bridge Functions and Operator Identification {#11-research-track-10}
**Status in implementation plan**: the implementation plan mentions proximal settings in Direction II (bounds/recovery) but does not treat proximal causal inference as a first-class identification framework. The engineering scope covers standard IV and sensitivity analysis as fallbacks for hidden confounding. Proximal inference is a fundamentally different approach that expands the class of identifiable queries and requires its own research track.

> **Why this track matters**: proximal causal inference (Miao, Shi, Tchetgen Tchetgen 2018+) formalizes identification under hidden confounding through two groups of proxy variables and "bridge functions" — solutions to operator/integral equations. This is not "one more estimator" but an expansion of what the proof kernel can certify as identifiable. For PolicyOS-type systems operating on administrative registries, text corpora, and event logs, hidden confounders are nearly inevitable but proxies are often available. This track is the most practically valuable gap in the current proof kernel.
>
> **Layer placement**: A-layer (proximal identification conditions and certificates) + B-layer (bridge estimators, orthogonal proximal scores).

### 11.1. Open problem: machine-checkable proximal identification certificates

**What the problem is**: the proximal identification framework requires two sets of proxies (treatment-inducing and outcome-inducing confounding proxies) and bridge functions that solve specific integral equations. The proof kernel must determine whether the proximal conditions are met for a given graph and variable set, and produce a certificate that records the identification argument.

**Why it cannot be implemented without research**: the graphical conditions for proximal identification are known for simple cases (Miao et al. 2018, Tchetgen Tchetgen et al. 2020), but: (a) the conditions have not been formalized as machine-checkable graph criteria analogous to the ID algorithm's hedge/fixing conditions, (b) the completeness of the graphical characterization is not established for general ADMG structures, (c) the interaction between proximal identification and other identification strategies (transport, composition, bounds) is not characterized.

**Sufficient result**: a constructive algorithm that, given a causal graph with marked proxy variables, returns either a `ProximalIdentificationCertificate` (with the identification functional and bridge function specification) or a `NegativeCertificate` explaining which proximal condition fails. The algorithm must be sound; completeness for at least one well-defined graph class is desirable but not required for v1.

**Deliverable form**: algorithm + certificate format + integration spec for `ProofBundle` to accept proximal identification proofs + scope statement for covered graph classes.

---

### 11.2. Open problem: bridge function existence and completeness conditions

**What the problem is**: proximal identification relies on bridge functions that satisfy integral equations of the form `E[Y|Z,X] = integral h(U,X) f(U|Z) dU`. The existence of a solution depends on completeness-type conditions on the conditional distributions involved. These conditions are not directly testable from data and are not graphically characterized.

**Why it cannot be implemented without research**: without verifiable bridge existence conditions, the system cannot distinguish between "proximal identification succeeds" and "the bridge function does not exist, so the proximal estimand is not well-defined". Implementing proximal estimation without checking bridge existence produces answers that may be meaningless.

**Sufficient result**: (a) graphical or semi-parametric sufficient conditions for bridge function existence, (b) a plausibility diagnostic that can flag when completeness is unlikely to hold, (c) formal connection between completeness failure and the bounds/fallback ladder (what does the system do when the bridge doesn't exist?).

**Key literature starting points**: Miao-Geng-Tchetgen Tchetgen (2018) for the basic framework; Cui et al. (2023) for semiparametric efficiency bounds; Ghassami et al. (2022) for graphical proximal identification in general ADMG; Tchetgen Tchetgen et al. (2024) for extensions to text, synthetic control, and time-varying settings.

**Deliverable form**: sufficient conditions document + plausibility diagnostic spec + fallback integration spec for `BoundsBundle` when bridge existence fails.

---

### 11.3. Open problem: proximal mediation and path-specific proximal effects

**What the problem is**: the basic proximal framework identifies total causal effects under hidden confounding. For policy systems, the more relevant question is often path-specific: "what is the effect of X on Y *through* mediator M, when there is hidden confounding?" Proximal mediation analysis extends the bridge function approach to path-specific effects, but the identification conditions are more complex and less well-characterized.

**Why it cannot be implemented without research**: proximal path-specific identification requires additional bridge functions and additional completeness conditions. The conditions under which proximal mediation is identified, partially identified, or not identified at all are not fully established.

**Sufficient result**: identification conditions for proximal path-specific effects for at least one mediator topology, with certificate format and fallback to bounds when conditions fail.

**Deliverable form**: theorem + certificate format + integration spec for path-specific proximal queries in the proof kernel.

---

## 12. Research Track 11 — Recoverability and Missing-Data Calculus {#12-research-track-11}
**Status in implementation plan**: the implementation plan mentions recoverability in passing (Direction II) but does not treat graphical missing-data theory as a first-class proof-kernel capability. The engineering scope covers standard complete-case and IPW approaches. Graphical recoverability is a fundamentally different framework that answers: "given this missingness pattern, can the target causal functional be recovered at all?"

> **Why this track matters**: a universal causal engine must answer not only "is the effect identifiable?" but also "is the effect recoverable from data with this missingness pattern?" For government administrative data, census records, and registry datasets, missingness is almost always MNAR-like or administratively selective. Standard imputation or complete-case analysis is not just suboptimal — it can be provably inconsistent. Graphical models of missingness (Mohan-Pearl) distinguish transparency, recoverability, and testability, providing the formal foundation the proof kernel needs.
>
> **Layer placement**: A-layer (recoverability conditions and certificates) + B-layer (recoverability-aware estimators, compile-time strategy selection).

### 12.1. Open problem: recoverability certificates for proof kernel integration

**What the problem is**: the Mohan-Pearl framework provides graphical conditions under which a statistical functional is recoverable from data with a specific missingness pattern. These conditions depend on the missingness graph (an extension of the causal graph with missingness indicator nodes). The proof kernel must determine recoverability before attempting estimation — and must distinguish between "recoverable", "recoverable under additional assumptions", and "not recoverable".

**Why it cannot be implemented without research**: the recoverability algorithm exists in the literature for basic cases, but: (a) the algorithm has not been formalized as a proof-kernel-compatible procedure that produces typed certificates, (b) the interaction between recoverability and identification (what if the effect is identified but not recoverable, or recoverable but not identified?) is not fully characterized as a joint decision procedure, (c) the extension to complex MNAR patterns typical of administrative data requires additional formalization.

**Sufficient result**: a joint identification-recoverability decision procedure that, given a causal graph with missingness indicators, returns one of: (a) `IdentifiedAndRecoverable` with recovery strategy, (b) `IdentifiedButNotRecoverable` with a specification of what additional data or assumptions would enable recovery, (c) `NotIdentified` (with the standard non-ID certificate), (d) `RecoverableButNotIdentified` (recoverable functional exists but the causal estimand is not identified — the system should still report what can be computed).

**Deliverable form**: joint decision algorithm + certificate format + integration spec for `ProofBundle` and `DataReadinessReport`.

---

### 12.2. Open problem: recoverability under administrative and selective missingness

**What the problem is**: standard graphical missingness models assume that the missingness mechanism is part of the causal model. In administrative data, missingness is often a function of administrative processes (e.g., records are missing because the unit didn't apply, because the office was closed, because the data system changed). These mechanisms create missingness patterns that are systematically MNAR but with structure that can be exploited if modeled correctly.

**Why it cannot be implemented without research**: administrative missingness patterns do not fit neatly into the standard MCAR/MAR/MNAR trichotomy. They require domain-specific missingness graphs. The question is: for which classes of administrative missingness patterns can recoverability be established, and what does the proof kernel need to know about the administrative process to certify recovery?

**Sufficient result**: a taxonomy of administrative missingness patterns with their graphical representations and recoverability conditions for at least three common administrative data scenarios (registration-based, compliance-based, system-change-based).

**Key literature starting points**: Mohan-Pearl (2021) for graphical models of missing data; Nabi et al. (2020) for testability of missing data assumptions; Bhattacharya et al. (2020) for identification with missing data in semiparametric models.

**Deliverable form**: missingness pattern taxonomy + graphical models + recoverability conditions + integration spec for `DataReadinessReport.missingness_assessment`.

---

### 12.3. Open problem: compile-time recovery strategy selection

**What the problem is**: when the A-layer certifies recoverability, the B-layer must select a recovery strategy: complete-case, IPW, augmentation, doubly robust, or explicit refusal. The choice depends on the recoverability proof structure. The question is: can the B-layer automatically select the optimal recovery strategy given the recoverability certificate, or does it require human guidance?

**Why it cannot be implemented without research**: the mapping from recoverability proof type to optimal estimator family is not characterized. Different recovery proofs (e.g., recovery via conditioning, recovery via reweighting, recovery via augmentation) suggest different estimator families, but the conditions under which each dominates are not established.

**Sufficient result**: a decision procedure mapping recoverability certificate types to estimator families, with efficiency comparisons for at least one data regime.

**Deliverable form**: decision procedure + efficiency analysis + integration spec for the estimand/estimator compiler.

---

## 13. Research Track 12 — Intervention Hierarchy: Edge, Path, Stochastic, and Policy Interventions {#13-research-track-12}
**Status in implementation plan**: the implementation plan's proof kernel supports `do(X=x)` node interventions. Stochastic interventions and modified treatment policies are mentioned in Direction V but not formalized as a proof-kernel-level query language extension.

> **Why this track matters**: real policies almost never look like `do(X=x)`. They look like: "change the assignment rule" (stochastic intervention), "break this specific causal channel" (edge intervention), "modify only the effect through mediator M" (path-specific intervention), "shift the treatment distribution by 10%" (modified treatment policy), "change the network of interactions" (interference-aware intervention). Without a formal hierarchy of intervention types in the proof kernel, the engine is stuck in the world of `do(X=x)`, which covers ATE but misses the vast majority of policy-relevant queries.
>
> **Layer placement**: A-layer (intervention type system, identification conditions per type) + B-layer (estimand compilation for each intervention type).

### 13.1. Open problem: formal intervention type system for proof kernel

**What the problem is**: the proof kernel needs a typed intervention language that covers at minimum: node interventions, conditional interventions, stochastic interventions, edge interventions, path interventions, modified treatment policies, transport interventions, and interference-aware interventions. Each type has different identification conditions, different estimand forms, and different certificate requirements.

**Why it cannot be implemented without research**: individual pieces of this hierarchy are formalized in different papers and frameworks (Correa-Bareinboim for the graphical hierarchy, Diaz-van der Laan for modified treatment policies, Avin-Shpitser-Pearl for edge interventions, Shpitser for path-specific effects). But no unified type system exists that covers all of them with consistent identification certificates, consistent estimand forms, and consistent fallback behavior. Building such a type system requires resolving interactions between intervention types (e.g., can you compose a stochastic intervention with a path-specific query?).

**Sufficient result**: a formal type system for interventions with: (a) at least 6 intervention types, (b) identification conditions for each type (or a reduction to known ID results), (c) a consistent certificate format across types, (d) a specification of which type compositions are well-defined and which are not.

**Key literature starting points**: Correa-Bareinboim (2020) on general interventions; Diaz-van der Laan on stochastic interventions; Avin-Shpitser-Pearl on edge/path interventions; Henckel et al. on optimal adjustment for different intervention types.

**Deliverable form**: type system specification + identification conditions per type + certificate format + composition rules + integration spec for `ProofBundle` query language.

---

### 13.2. Open problem: identification and estimation for stochastic and modified treatment policies

**What the problem is**: stochastic interventions (replacing do(X=x) with do(X ~ g(x|L))) and modified treatment policies (shifting the natural treatment mechanism) are the most practically relevant intervention types for policy systems. Identification conditions for these are known under specific assumptions, but the estimator landscape is complex and the conditions under which each estimator is efficient are not fully characterized.

**Why it cannot be implemented without research**: the proof kernel must determine whether a stochastic intervention query is identified under the given graph and assumptions. The B-layer must then select an appropriate estimator. Both steps require formalization beyond what exists in a single paper. The interaction with proximal identification (Track 10) and recoverability (Track 11) adds further complexity: can a stochastic intervention effect be identified via proximal inference? Can it be recovered from data with missingness?

**Sufficient result**: identification conditions for stochastic interventions and modified treatment policies in the proof kernel, with at least one estimator family per type and diagnostics for efficiency.

**Deliverable form**: identification algorithm extension + estimator family + diagnostics + integration spec.

---

### 13.3. Open problem: path-specific and edge-specific effect identification at scale

**What the problem is**: path-specific effects (the effect of X on Y only through a specific set of paths) and edge-specific effects (the effect of removing or modifying a single edge in the SCM) are essential for policy analysis ("which channel does this subsidy work through?"). Identification theory for these effects exists but is limited to relatively simple graph structures. For complex policy-relevant graphs with many mediators and confounders, the identification conditions become complex and the estimands become high-dimensional.

**Why it cannot be implemented without research**: the computational complexity of path-specific identification in large graphs is not well-characterized. The interaction between path-specific effects and other identification strategies (transport, bounds, proximal) is also not established.

**Sufficient result**: a scalable identification procedure for path-specific effects in graphs with at least 15-20 nodes and multiple mediator layers, with computational complexity guarantees and fallback to bounds when identification fails.

**Deliverable form**: scalable algorithm + complexity analysis + fallback spec + integration spec for proof kernel path-specific queries.

---

### 13.4. Open problem: optimal recourse intervention and causal manifold geometry

**What the problem is**: the intervention hierarchy in Tracks 13.1–13.3 focuses on population-level and policy-designer interventions. A complementary problem arises when the causal engine is used for individual-level decisions (subsidy eligibility scoring, automated benefit determination, license approval). If the system returns an adverse outcome for an individual unit, that unit may legitimately ask: what is the minimum-cost set of interventions I could make to achieve outcome Y = 1?

This is the Algorithmic Recourse problem, formulated causally: find `argmin_a cost(a)` such that `P(Y = 1 | do(X = a)) ≥ τ`, where `a` ranges over interventions that are feasible for the individual. The problem has two structural complications: (1) some variables are immutable (age, birth country) — interventions must be constrained to mutable nodes; (2) the cost function must be defined on the causal manifold rather than on Euclidean input space, because naive Euclidean distance ignores causal dependencies (shifting income while holding education fixed may be causally inconsistent if the two are structurally linked).

**Why it cannot be implemented without research**: causal recourse requires: (a) a formal cost geometry on the space of interventions that respects the causal structure — i.e., assigns zero marginal cost to changes that are causally entailed by a primary intervention and infinite cost to interventions on immutable nodes; (b) a tractable algorithm for finding the minimum-cost causal intervention under the constraint graph; (c) a proof that the recommended recourse is actionable — that is, the individual can actually execute it without violating the SCM's functional constraints. Without this, the system produces counterfactual advice that is structurally impossible for the individual to follow.

**Sufficient result**: (a) a formal definition of `InterventionCostManifold` — a cost function on do-interventions that is consistent with the structural equations and treats causally entailed changes as zero marginal cost; (b) an algorithm for `OptimalRecourseIntervention` that solves the constrained shortest-path problem on this manifold with mutable/immutable node constraints; (c) conditions under which the solution is unique and computationally tractable (polynomial in graph size for tractable sub-families; NP-hardness characterization for the general case); (d) a certificate that the recommended recourse is structurally feasible.

**Key literature starting points**: Ustun-Spangher-Liu (2019) on actionable algorithmic recourse; Karimi et al. (2020) on algorithmic recourse under causal models; Mahajan et al. (2019) on preserving causal constraints in counterfactual explanations; Wachter et al. for the counterfactual explanations baseline without causal structure; Vonk et al. for complexity results on causal recourse.

**Deliverable form**: `InterventionCostManifold` formal spec + `OptimalRecourseIntervention` query type definition + algorithm + complexity analysis + feasibility certificate + integration spec for the proof kernel as a new query type.

**Relationship to other tracks**: this is a direct extension of Track 12.1 (intervention type system) — `OptimalRecourseIntervention` is a new intervention query type that combines `do(X = x)` with a cost-minimization constraint. Track 11 (recoverability) provides a prerequisite: recourse recommendations are only valid if the causal effect estimates they are based on are recoverable from the available data. Track 8 (latent representation) is a downstream consumer: if hidden confounders are present, the recourse recommendation may be structurally incorrect unless the latent structure is accounted for.

---

## 14. Research Track 13 — RKHS and Operator-Valued Causal Inference {#14-research-track-13}
**Status in implementation plan**: not previously scoped. This is a new horizon-lane track that provides a functional-analytic layer for causal inference — operating on entire distributions, conditional distributions, and operator-valued causal objects rather than scalar summaries.

> **Why this track matters**: kernel embeddings of distributions and operator-valued regression allow the causal engine to work with distributional effects, conditional distributional effects, and operator-valued causal objects in a nonparametric way. Many such computations reduce to linear algebra on Gram matrices and operators, which is well-suited to JAX. This track is complementary to Track 4 (OT): OT provides geometry-aware comparison of distributions, while RKHS provides a function-space framework for estimating distributional causal objects.
>
> **Layer placement**: primarily B-layer (estimation) and C-layer (Fabric numerics). Not an A-layer concern — RKHS does not replace graphical identification but provides powerful estimation machinery once identification is established.
>
> **Priority**: lower than Tracks 10-12. This track does not expand the class of queries the proof kernel can accept (unlike proximal, recoverability, and intervention hierarchy). It provides better estimation tools for already-identified queries. Important for long-term moat but not for immediate universality.

### 14.1. Open problem: kernel causal effect operators with identification guarantees

**What the problem is**: kernel mean embeddings can represent entire conditional distributions as elements of an RKHS. "Kernel causal effects" — the difference between embedded counterfactual distributions — are natural objects for distributional causal inference. The question is: under what conditions is a kernel causal effect operator identified from observational data, and how does this interact with the proof kernel's identification certificates?

**Why it cannot be implemented without research**: kernel causal effect operators are studied in the ML literature (Muandet et al.), but the identification conditions are typically stated in terms of completeness and kernel universality, not in terms of graphical conditions. Bridging the gap between graphical identification (proof kernel) and functional-analytic estimation (RKHS) requires formalization that does not yet exist.

**Sufficient result**: conditions under which the proof kernel's `EstimandAST` can be translated into a kernel estimator with provable consistency, together with diagnostics for kernel choice and regularization.

**Deliverable form**: translation conditions + estimator spec + diagnostics + integration spec for the estimand/estimator compiler.

---

### 14.2. Open problem: operator-valued regression for multi-output causal effects

**What the problem is**: when the outcome is multivariate or functional (e.g., an entire policy trajectory, a spatial distribution of outcomes, a distributional response), the causal effect is naturally an operator between function spaces, not a scalar or vector. Operator-valued regression in RKHS provides a framework for estimating such objects.

**Why it cannot be implemented without research**: operator-valued causal estimation requires extending the B-layer's estimand language to operator-valued targets, which is not currently supported. The conditions under which such operators are estimable, the appropriate regularization, and the connection to the proof kernel's identification results are open questions.

**Sufficient result**: an estimand language extension for operator-valued targets, with at least one estimator family and convergence guarantees under stated conditions.

**Deliverable form**: estimand language extension + estimator + convergence analysis + integration spec.

---

## 15. Research Track 14 — Causal Inference under Differential Privacy {#15-research-track-14}
**Status in implementation plan**: not previously scoped. This is a new A-layer track directly relevant to policy engine deployments on administrative and tax data.

> **Why this track matters**: policy and government systems inevitably process data subject to strict legal privacy constraints — administrative registries, tax records, health data, education records. When data has been processed through ε-differential privacy mechanisms (Laplace noise, Gaussian mechanisms, randomized response), the observed joint distribution P̃(V) is not the true P(V). Classical conditional independence tests break down: a CI test on DP-noised data may reject true independencies or fail to detect real dependencies. Many d-separation guarantees, which rely on testing conditional independence, no longer hold. Transportability results that assume P(V) is the true distribution may fail if the observed distribution is a privatized proxy.
>
> **Layer placement**: A-layer (modified identification and transportability conditions under DP distortion) + B-layer (CI tests calibrated for DP noise; DP-robust estimators). This track is architecturally complementary to Track 11 (Recoverability): Track 11 handles structural missingness patterns, Track 14 handles probabilistic distortion through privacy mechanisms.
>
> **Policy relevance**: extremely high. Any deployment on real administrative or tax data in regulated jurisdictions must contend with privacy-preserving data sharing. The engine's identification and transportability certificates are currently not robust to DP distortion.

### 15.1. Open problem: identification conditions under DP-distorted distributions

**What the problem is**: the proof kernel's ID algorithm operates on P(V) — the true joint distribution over observed variables. When the analyst has access only to P̃(V) — a differentially private version of P(V) via, e.g., the Laplace or Gaussian mechanism — the standard identification conditions (front-door, back-door, ID algorithm) may not transfer. For which identification arguments does the certificate remain valid when P(V) is replaced by P̃(V), and what are the formal conditions?

**Why it cannot be implemented without research**: there is no existing theory mapping DP distortion types to identification certificate validity. A naive approach — run the ID algorithm on P̃(V) — produces answers that are provably wrong for some graph structures (noise can create spurious conditional independencies or break real ones). Implementing a DP-aware proof kernel without this theory means that users operating on DP data will silently receive invalid identification certificates.

**Sufficient result**: a characterization of which ID-algorithm steps remain valid under bounded DP distortion, with: (a) formal conditions on ε and δ (the DP parameters), the graph structure, and the query type under which the certificate degrades gracefully — switching from `IDENTIFIED` to `BOUNDED` or `UNIDENTIFIABLE` with a correct explanation; (b) a formal definition of `DPRobustnessCertificate` that records the DP parameters used, the identification validity scope, and any necessary sample-size amplification requirements; (c) conditions under which the certificate is entirely invalidated and the system should block estimation.

**Deliverable form**: formal characterization + `DPRobustnessCertificate` format + conditions for graceful degradation vs. hard block + integration spec for `ProofBundle` to record DP distortion context.

---

### 15.2. Open problem: conditional independence tests calibrated for DP noise

**What the problem is**: causal discovery and constraint-based identification both rely on CI tests. Under DP noise, the sampling distribution of test statistics changes. A CI test calibrated for clean data will have the wrong Type I and Type II error rates under DP noise — it may reject too often (producing spurious edges) or fail to reject (missing real independencies). This affects both discovery (Track 15) and constraint-based identification (Track 7).

**Why it cannot be implemented without research**: recalibrating CI tests under DP requires: (a) a model of how DP noise propagates through the test statistic's distribution, (b) sample-size conditions under which the DP-corrected test has sufficient power, (c) an account of how graph structure affects robustness to DP noise. Without calibration theory, the system cannot run any meaningful CI test on DP-noised data.

**Sufficient result**: DP-corrected CI tests for at least two standard test families (kernel-based, χ²-based or G²-based), with: (a) sample-size requirements as a function of ε, δ, and the target power; (b) integration with the system's `JudgeThresholdRegistry` to report DP-corrected thresholds when DP context is present; (c) formal bounds on the inflation of the false-positive rate under standard tests applied naively to DP data.

**Key literature starting points**: Dwork-Roth (2014) for the DP framework; Gaboardi et al. for differentially private hypothesis testing; Cai et al. for DP conditional independence tests; Rogers et al. for the interaction between privacy and statistical estimation; Acharya et al. for optimal DP testing rates.

**Deliverable form**: corrected test procedures + sample-size requirement bounds + `JudgeThresholdRegistry` extension spec for DP context + integration spec.

---

### 15.3. Open problem: transportability and recoverability under DP distortion

**What the problem is**: transportability results (Track 1's composition certificates, Track 11's recoverability framework) assume that the analyst has access to the true distributions P(V; domain_i). When different domains supply data through different DP mechanisms — different ε, different mechanisms, different variable sets protected — the transport maps between domains become uncertain or invalid. Which transportability arguments remain valid when source and target distributions are replaced by their DP versions, and which are broken?

**Why it cannot be implemented without research**: this is a new intersection of three active research areas (DP theory, transportability/selection diagrams, missing-data calculus) that has not been studied systematically. A naive application of transport maps to DP-noised data can produce transport certificates that are formally invalid because the noise distorts the marginals and conditionals that the transport argument relies on.

**Sufficient result**: formal conditions under which a transport certificate remains valid under DP distortion, with: (a) a distortion tolerance map — given the transport argument's structure, what is the maximum DP noise level that preserves validity; (b) a formal definition of `PrivacyAwareTransportCertificate` that extends the existing transport certificate with DP validity scope; (c) conditions under which transport should be blocked entirely and what alternative queries remain valid.

**Deliverable form**: formal conditions + `PrivacyAwareTransportCertificate` format + integration spec for the composition and transport modules.

---

## 16. Research Track 15 — Causal Discovery via Nonstationarity and Regime Shifts {#16-research-track-15}
**Status in implementation plan**: not previously scoped as a discovery-oriented track. The implementation plan covers structure learning as a background capability but does not treat nonstationarity as a first-class identification tool.

> **Why this track matters**: purely observational causal discovery typically yields Markov equivalence classes (MECs) — sets of DAGs that are indistinguishable from observational data. For the proof kernel to issue identification certificates, it must know the graph, not just the MEC. In government settings, exogenous shocks are constant: new laws, budget cycles, crises, regulatory changes. These regime shifts produce distributional changes that can be exploited as natural experiments. The key insight from Invariant Causal Prediction (Peters et al., 2016) is that the true causal parents of Y produce invariant conditional distributions across environments, while non-causal predictors do not. Nonstationarity is thus not merely a problem to be handled — it is a tool for graph identification.
>
> **Layer placement**: primarily A-layer (formal conditions under which regime shifts yield MEC contraction and graph identification) + B-layer (computational algorithms for ICP-type discovery from regime-shift data) + Foundry (integration with the existing structure learning pipeline).
>
> **Relationship to existing tracks**: Track 8 (Latent Representation) addresses what happens when latent variables cause apparent distributional shifts. This track is complementary: it studies the structural invariances that survive latent variable shifts and can still constrain the graph. Track 7 (Algebraic) is orthogonal: algebraic constraints tighten the MEC using polynomial constraints, this track tightens it using distributional invariances across environments. Both constraint families should be composable.

### 16.1. Open problem: formal conditions for ICP-based MEC contraction

**What the problem is**: Invariant Causal Prediction (Peters et al., 2016) establishes that, under linear models with Gaussian noise, the true causal parents of Y are the unique variable set S such that `P(Y | S, E)` is invariant across environments E. For the policy engine: (a) under what conditions does applying ICP across multiple target variables contract the MEC sufficiently to yield a unique or near-unique graph, (b) what are the formal identifiability conditions when the noise distribution is non-Gaussian or the model is non-linear, and (c) how many and what type of regime shifts are required for full identification?

**Why it cannot be implemented without research**: ICP's theoretical guarantees are tight for linear Gaussian models but poorly understood for the non-linear, heteroskedastic, or discrete models typical of policy data. The conditions under which multi-environment ICP yields a unique graph are not established. Implementing ICP-based discovery without this characterization produces results of unknown reliability.

**Sufficient result**: formal identifiability conditions for ICP-style MEC contraction under at least one non-linear model class relevant to policy data, with: (a) a lower bound on the number and diversity of regime shifts required for unique identification; (b) a certificate format `RegimeShiftIdentificationCertificate` that records the environments used, the invariance test results, and the resulting MEC contraction; (c) conditions under which the environment collection is informative vs. redundant.

**Key literature starting points**: Peters-Bühlmann-Meinshausen (2016) on ICP; Heinze-Deml et al. on nonlinear ICP; Arjovsky et al. (IRM) for out-of-distribution learning using invariance; Rothenhäusler et al. on causal Dantzig; Pfister et al. for characterization under additive noise models.

**Deliverable form**: formal identifiability theorem + `RegimeShiftIdentificationCertificate` format + environment informativeness conditions + integration spec for the Foundry structure learning pipeline.

---

### 16.2. Open problem: distinguishing regime shifts from latent confounding

**What the problem is**: distributional shifts between environments can be caused by (a) true structural change (new law, policy reform — a change in the SCM's structural equations), (b) selection differences (different population subsets observed in each environment), or (c) latent confounders that vary across environments. For ICP-type methods to produce valid identification results, the shift must be primarily of type (a). If the shift is driven by latent confounders (type c), the invariance test produces false positives: variables appear non-invariant not because they are non-causes but because of environment-varying hidden confounding.

**Why it cannot be implemented without research**: the distinction between structural change and latent confounding using only observational data across environments is an active research problem. Without a formal test for this distinction, the system cannot determine when regime-shift data is trustworthy for ICP-type identification and when it may produce spurious graph contractions.

**Sufficient result**: a diagnostic procedure that, given multi-environment data, assesses whether the observed distributional shifts are consistent with (a) structural change only, (b) selection only, or (c) mixed/latent-confounder-driven — with formal guarantees on error rates under each model type. The procedure must produce an input to the `RegimeShiftIdentificationCertificate.shift_type_assessment` field.

**Deliverable form**: diagnostic algorithm + error rate bounds + `shift_type_assessment` field specification + integration spec for the discovery pipeline's pre-screening stage.

---

### 16.3. Open problem: computational tractability and Foundry integration

**What the problem is**: even if the identification conditions are established (16.1) and the shift-type assessment is reliable (16.2), finding the minimum MEC consistent with all invariance tests across all environments and target variables is combinatorially hard in the worst case. For policy-relevant graph sizes (20–100 nodes, 3–10 environment pairs), the algorithm must be tractable.

**Why it cannot be implemented without research**: the computational complexity of multi-target multi-environment ICP is not fully characterized. The interaction between ICP-type constraints and other graphical constraints in the Foundry (tetrad constraints from Track 7, proximal constraints from Track 10) may allow pruning strategies that reduce the search space significantly — but formalizing these interactions requires research.

**Sufficient result**: a tractable algorithm (polynomial or FPT in graph size and number of environments) for multi-target multi-environment ICP-style discovery for a defined graph size regime, with: (a) integration with the Foundry's existing constraint-based discovery pipeline; (b) formal interaction spec between ICP constraints and algebraic/tetrad constraints from Track 7; (c) a certificate of computational feasibility for a given problem instance.

**Deliverable form**: algorithm + complexity analysis + interaction spec with Track 7 constraints + integration spec for the Foundry discovery pipeline.

---

## 17. Dependency and Parallelization Map

### 17.1. What can be started immediately

> **Update (v2.0)**: with the implementation plan largely completed, all research tracks now have their engineering integration targets available. The constraint is no longer "wait for engineering" but "do the math right".

All research tracks can be started as theoretical investigations. The key rule is that they must live as `FrontierSketch` objects with `max_readiness = PROOF_ONLY` and cannot influence production until they graduate.

The most independent tracks (minimal dependencies on other research):

- **Track 2** (sharp bounds): nearly independent; only depends on `BoundsBundle` contract from A.1.
- **Track 7** (algebraic beyond CI): independent; only depends on `AlgebraicConstraintReport` from E.1.
- **Track 9** (topology): independent as pure theory; needs F.1 only for integration.
- **Track 3** (continuous-time): independent as pure theory; needs C.1 for integration.
- **Track 4** (OT): independent; needs D.1 for integration.
- **Track 10** (proximal): independent as pure theory; integration target is `ProofBundle`.
- **Track 11** (recoverability): independent as pure theory; integration target is `ProofBundle` + `DataReadinessReport`.
- **Track 12** (intervention hierarchy): independent as pure theory; integration target is `ProofBundle` query language.
- **Track 13** (RKHS): independent; integration target is estimand/estimator compiler.
- **Track 14** (differential privacy): independent; integration target is `ProofBundle` + `JudgeThresholdRegistry`.
- **Track 15** (nonstationarity / regime shifts): independent; integration target is Foundry discovery pipeline + `ProofBundle`.

### 17.2. What benefits from minimum core being available (after A.1 + A.2 + A.4)

After the minimum viable core (A.1 + A.2 + A.4) is available, all research gains significantly higher integration quality:

- **Track 1** benefits from having `ProofBundle` as the target format for theorem translation.
- **Track 2** benefits from `BoundsBundle` and `BoundJudge` as the integration target.
- **Track 4** benefits from `DataReadinessReport` for empirical research questions.
- **Track 5** benefits from `StrategicResponseBundle` and `ComputeJudge` as the integration target.
- **Track 10** benefits from `ProofBundle` for proximal identification certificates.
- **Track 11** benefits from `DataReadinessReport` for recoverability assessment integration.
- **Track 12** benefits from the proof kernel's query language as the extension target.

### 17.3. Tracks with strong dependencies on other research tracks

| Track | Depends on |
|-------|-----------|
| Track 1 (cyclic composition) | — pure theory |
| Track 1 (automatic latent bridge) | Partial results from Track 8 (latent cardinality) |
| Track 3.4 (DSCM semantics) | — pure theory, but Track 1.3 (cyclic composition) is architecturally related |
| Track 3.5 (local independence) | Track 3.4 (DSCM semantics) provides the framework |
| Track 4 (distributional estimands in proof kernel) | — requires Track 4.3 before Track 4.1 can be integrated |
| Track 5 (convergence theory) | Track 5.1 (game class classification) is prerequisite for Track 5.2 |
| Track 6 (approximate bounds) | Track 6.2 (faithfulness conditions) is prerequisite for Track 6.1 integration |
| Track 9 (estimators) | Track 9.1 (identification theory) is strict prerequisite for Track 9.2 |
| Track 10 (proximal) | — largely independent; Track 10.3 (proximal mediation) benefits from Track 12 (intervention hierarchy) |
| Track 11 (recoverability) | — largely independent; Track 11.3 benefits from Track 10 (proximal) for recovery strategy when proxies are available |
| Track 12 (intervention hierarchy) | — largely independent; Track 12.2 (stochastic) interacts with Track 10 (proximal) and Track 11 (recoverability) |
| Track 13 (RKHS) | Track 4 (OT) provides complementary distributional framework |
| Track 14 (differential privacy) | Track 11 (recoverability) is architecturally related; Track 7 (algebraic CI tests) complements T14.2 |
| Track 15 (nonstationarity / regime shifts) | Track 7 (algebraic constraints) provides complementary MEC constraint types; Track 8 (latent) is the confounding-side dual |

### 17.4. Dependency chains that affect production integration

```text
COMPOSITIONAL STRONG PRODUCTION:
after B.1/B.2 land -> Track 1.1 theorem -> B.4b integration

DISTRIBUTIONAL IDENTIFIED:
after A.1 lands -> Track 4.3 (proof-kernel formalization) -> Track 4.1 (coupling theory) -> D.1 upgrade to BOUNDED/IDENTIFIED

STRATEGIC COMPLEX:
after reduced-scope D.2 lands -> Track 5.1 (game classification) -> D.2 extension for new game classes
                              -> Track 5.2 (convergence) -> StrategicResponseBundle.performative_shift_ref
                              -> Track 5.3 (decomposition conditions) -> stronger strategic decomposition claims

LATENT PROMOTION:
after E.2/E.3/E.4 governance scaffolding lands -> Track 8.1 + Track 8.2 -> Track 8.3 (promotion criteria) -> relaxed readiness cap

TOPOLOGY INTEGRATION:
after F.1 contracts land -> Track 9.1 (identification) -> Track 9.2 (estimators) -> F.2 implementation

PROXIMAL QUERY EXPANSION (new):
Track 10.1 (proximal certificates) -> Track 10.2 (bridge existence) -> ProofBundle proximal path
                                   -> Track 10.3 (proximal mediation) -> combined with Track 12 for path-specific proximal

RECOVERABILITY QUERY EXPANSION (new):
Track 11.1 (recoverability certificates) -> joint ID+recovery decision procedure
                                         -> Track 11.3 (compile-time strategy) -> B-layer estimator selection

INTERVENTION HIERARCHY EXPANSION (new):
Track 12.1 (type system) -> Track 12.2 (stochastic/MTP estimation) -> full policy-query language
                         -> Track 12.3 (path-specific at scale) -> production path-analysis capability

PROOF KERNEL UNIVERSALITY (new, compound chain):
Track 10 + Track 11 + Track 12 + Track 3.4 -> proof kernel accepts proximal, recoverable,
    stochastic, path-specific, dynamic queries -> system transitions from "effect estimator"
    to "causal query OS"

DP CAUSAL INFERENCE (new):
Track 14.1 (identification under DP) -> DPRobustnessCertificate in ProofBundle
                                     -> Track 14.3 (DP transportability) -> PrivacyAwareTransportCertificate
Track 14.2 (DP CI tests) -> JudgeThresholdRegistry DP-corrected thresholds -> feeds Track 15 discovery pipeline

REGIME SHIFT DISCOVERY (new):
Track 15.1 (ICP-based MEC contraction) -> RegimeShiftIdentificationCertificate -> Foundry discovery pipeline
                                       -> Track 15.2 (shift-type diagnostic) -> pre-screening for discovery
                                       -> Track 15.3 (computational tractability) -> tractable MEC contraction algorithm
                                       -> Track 7 (algebraic) constraint interaction -> joint MEC contraction
```

---

## 18. Anti-Swamp Governance for Research Tracks {#18-anti-swamp-governance}
Research tracks are more vulnerable to becoming research swamps than engineering tasks. The following rules apply specifically to research tracks.

### 18.1. Benchmark proxy requirement

A research track that has not produced a benchmark proxy after 2 implementation phases loses its research budget and is downgraded to a "recorded open problem" state. It remains in this document as an open problem but receives no active investment until a benchmark proxy is available.

A **benchmark proxy** for a research track is one of:
- a synthetic dataset on which the claimed result (if true) would produce a measurable signal;
- a counterexample that would be ruled out if the claimed theorem holds;
- a sentinel case that can falsify a wrong implementation of the result.

### 18.2. FrontierSketch integration rule

All research artifacts must be integrated as `FrontierSketch` with:
- `max_readiness = PROOF_ONLY`
- `ttl_phases` set to a concrete number (default: 3 phases)
- `required_for_promotion` populated before work begins, not after

A research artifact that cannot state its `required_for_promotion` checklist before starting is not ready to start.

### 18.3. Parallelism without contamination

Research tracks may be run in parallel with engineering tracks. The contamination rules:

1. A research sketch may not influence a production recommendation, directly or indirectly.
2. A research sketch may not be cited as evidence for raising a readiness cap.
3. A research artifact in `PROOF_ONLY` may be exported for research consumers with explicit "not for decision support" labeling, but may not enter the policy analyst workflow.
4. A research track that has produced a benchmark proxy may request a hidden holdout evaluation. The result of that evaluation is the primary signal for graduation, not the researcher's assessment.

### 18.4. Hypothesis discipline

Each research track entry in this document is a hypothesis about what can be proved. As research progresses, the hypothesis may be:

- **confirmed**: the theorem is proved; integration can proceed;
- **narrowed**: the theorem holds in a smaller scope than initially claimed; scope must be updated in this document and the integration spec adjusted;
- **refuted**: an impossibility result or counterexample is found; the counterexample goes to `CounterexampleRegistry` and the track is closed or redirected;
- **deferred**: no progress in 2 phases; track enters "recorded open problem" state.

All four outcomes are treated as research contributions. Refutation is not failure — it clarifies the system's honest claims.

---

## 19. Research Economics and Kill Rules

### 19.1. Research budget allocation

Research tracks compete for budget with implementation tasks. The allocation rule is:

- Wave 1 and Wave 2 engineering tasks have priority and get first claim on engineering budget.
- Research tracks run on a separate, capped research budget.
- The research budget fraction is determined by the economics score (moat_depth × policy_relevance) of each track.
- Research tracks in "recorded open problem" state receive maintenance-only budget (sufficient to preserve the benchmark proxy and counterexample library, nothing more).

### 19.2. Research track economic scores

> **Updated (v2.0)**: scores adjusted to reflect new tracks and revised priority assessment. The three new A-layer tracks (10, 11, 12) receive high/highest priority because they expand the class of queries the proof kernel can accept — this is the single most impactful dimension for system universality. Track 9 (topology) is upgraded from "long horizon" to "high" based on external review: it is the most direct Fabric moat and opens a problem class absent from all competitor libraries.

| Track | Moat depth | Policy relevance | Research difficulty | Priority |
|-------|-----------|------------------|---------------------|---------|
| Track 1 (compositional advanced) | very high | very high | high | highest |
| Track 2 (sharp bounds) | high | very high | medium | highest |
| Track 10 (proximal causal inference) | high | very high | medium | highest |
| Track 11 (recoverability / missing-data) | high | very high | medium | highest |
| Track 12 (intervention hierarchy) | very high | very high | medium-high | highest |
| Track 3 (continuous-time + DSCM) | high | very high | medium-high | high |
| Track 4 (OT under partial ID) | high | high | high | high |
| Track 9 (topology / Hodge interference) | very high | high | high | high |
| Track 5 (strategic complex) | very high | very high | very high | medium-high |
| Track 6 (abstraction bounds) | high | high | high | medium |
| Track 7 (algebraic + semialgebraic) | high | medium-high | medium | medium |
| Track 8 (latent representation) | very high | medium | very high | medium-long horizon |
| Track 13 (RKHS / operator-valued) | medium-high | medium | high | long horizon |
| Track 14 (differential privacy / DP causal inference) | high | very high | medium | high |
| Track 15 (nonstationarity / regime shifts) | high | very high | medium | high |

### 19.3. Kill rules for research tracks

Consistent with the implementation plan's kill rules (section 8.4):

1. A research track with no benchmark proxy after 2 phases is downgraded to "recorded open problem".
2. A research track where the core hypothesis is refuted is closed; the counterexample is registered.
3. A research track that has not graduated a `FrontierSketch` to a full `FrontierArtifact` after the `ttl_phases` limit is automatically archived.
4. Kill decisions require documented rationale and human review.
5. A killed research track may be reopened if the theoretical landscape changes (new external results) or if new benchmark opportunities appear.

### 19.4. Integration premium for research results

The integration premium logic from the implementation plan applies to research results as well. A research result that unlocks a production implementation is worth more than its isolated moat contribution, because it also amplifies the value of the already-scoped engineering families. For example:

- Track 4.3 (distributional estimands in proof kernel) unlocks `BOUNDED` and `IDENTIFIED` justification in D.1, which in turn compounds with the compositional engine (B.3) to allow causally identified distributional comparisons across composed graphs.
- Track 1.1 (latent interface identifiability) compounds with Track 2 (sharp bounds) to allow bounds on queries in composed graphs with latent interfaces.

Additional compound effects from new tracks:

- Track 10 (proximal) + Track 11 (recoverability): when hidden confounding exists but proxies are available *and* data has missingness, the joint identification-recoverability-proximal decision procedure enables queries that no individual track can handle alone.
- Track 12 (intervention hierarchy) + Track 10 (proximal): proximal identification of stochastic intervention effects — "what is the effect of changing the treatment assignment rule when confounders are hidden but proxied?" — is the quintessential policy query.
- Track 12 (intervention hierarchy) + Track 9 (topology): interference-aware stochastic interventions — "what is the effect of changing subsidy allocation rules when agents interact in higher-order groups?" — is the compound that makes PolicyOS qualitatively distinct from any existing system.
- Track 3.4 (DSCM) + Track 12 (intervention hierarchy): dynamic path-specific effects — "what is the effect of intervening on a specific causal channel in a system with feedback loops and continuous-time evolution?" — requires both DSCM semantics and the intervention type system.

These compound effects should factor into research budget allocation decisions.

---

## Appendix A: Open Problem Catalog

A compact reference of all open problems in this document.

| Track | Problem | Unlocks |
|-------|---------|---------|
| T1.1 | Identifiability preservation under latent interface variables | B.4b |
| T1.2 | Transfer of do-calculus derivations across fragments | Stronger B.4b |
| T1.3 | Cyclic SCM fragment composition semantics | Future `SCMFragment` cyclic support |
| T1.4 | Automatic latent bridge synthesis | Automated `LATENT_BRIDGE` alignment |
| T1.5 | Category-theoretic completeness of composition certificate | Stronger `CompositionCertificate` guarantee |
| T2.1 | Sharpness proofs for complex query families | `BoundsBundle.sharpness_status = "sharp"` for non-trivial queries |
| T2.2 | Automated bound tightening with soundness guarantees | Automated `RecoveryPlan` bound-tightening |
| T3.1 | Causal rough-path semantics | C.4 |
| T3.2 | Neural SDE identification theory | `EffectTrajectoryBundle` for neural SDE |
| T3.3 | Discrete-to-continuous causal translation conditions | `EffectTrajectoryBundle` discretization certificate |
| T3.4 | DSCM semantics and σ-separation for proof kernel | Proof kernel support for cyclic/continuous-time causal queries |
| T3.5 | Local independence and Granger-causal semantics in continuous time | Proof kernel support for event-process causal queries |
| T4.1 | Causally justified OT couplings under partial ID | `DistributionalJustification.BOUNDED` and `.IDENTIFIED` |
| T4.2 | Bounded distributional effects for tail risk under partial ID | Distributional `BoundsBundle` extension |
| T4.3 | Proof kernel extension to distributional estimands | Full distributional query support in Layer A |
| T5.1 | Equilibrium computation for complex strategic environments | D.2 game class extension |
| T5.2 | Performative prediction convergence and instability | `StrategicResponseBundle.performative_shift_ref` |
| T5.3 | Causal-strategic decomposition conditions | `StrategicResponseBundle` decomposition validity |
| T5.4 | MFG equilibrium for macro-policy causal inference | `StrategicResponseBundle.mfg_equilibrium_ref`; Fabric macro-simulation numerics |
| T6.1 | Approximate abstraction error bounds for continuous models | `AbstractionCertificate.error_bound` for continuous case |
| T6.2 | Conditions for faithful micro-to-macro causal transport | `AbstractionCertificate.preservation_type = "approximate"` validity |
| T7.1 | Algebraic constraints beyond CI | Extended `AlgebraicConstraintReport` |
| T7.2 | Finite-sample calibration for algebraic constraint tests | `JudgeThresholdRegistry` entries for algebraic judges |
| T7.3 | Semialgebraic negative certificates and SCM class incompatibility | `NegativeCertificate` for model-class incompatibility in proof kernel |
| T8.1 | Latent cardinality identification from distributional shifts | `LatentDiscoveryBundle.proposed_latent_nodes` |
| T8.2 | Separation of confounding, proxy mismatch, and measurement error | `LatentDiscoveryBundle.trust_level` logic |
| T8.3 | Promotion criteria for latent artifacts | Relaxed readiness cap for latent family |
| T9.1 | Simplicial complex identification theory | `InterferenceCertificate.supported_query_family` extension; F.2 |
| T9.2 | Exposure-complex estimators with honest pairwise fallback | F.2 implementation |
| T9.3 | Bounds on hypergraph-to-pairwise reduction error | `InterferenceCertificate.reduction_error_bound` |
| T10.1 | Machine-checkable proximal identification certificates | `ProofBundle` proximal identification path |
| T10.2 | Bridge function existence and completeness conditions | Proximal estimation validity; fallback to bounds when bridge fails |
| T10.3 | Proximal mediation and path-specific proximal effects | Path-specific queries under hidden confounding via proxies |
| T11.1 | Recoverability certificates for proof kernel integration | Joint identification-recoverability decision procedure |
| T11.2 | Recoverability under administrative and selective missingness | `DataReadinessReport.missingness_assessment` for real-world data |
| T11.3 | Compile-time recovery strategy selection | Automatic B-layer estimator selection from recoverability proof type |
| T12.1 | Formal intervention type system for proof kernel | Full policy-query language (6+ intervention types with certificates) |
| T12.2 | Identification and estimation for stochastic and modified treatment policies | Stochastic/MTP queries in proof kernel + estimator families |
| T12.3 | Path-specific and edge-specific effect identification at scale | Production path-analysis for complex graphs (15+ nodes) |
| T12.4 | Optimal recourse intervention on causal manifold | `OptimalRecourseIntervention` query type; `InterventionCostManifold` spec |
| T13.1 | Kernel causal effect operators with identification guarantees | Distributional causal estimation via RKHS |
| T13.2 | Operator-valued regression for multi-output causal effects | Operator-valued causal targets in estimand language |
| T14.1 | Identification conditions under DP-distorted distributions | `DPRobustnessCertificate`; DP-aware identification in proof kernel |
| T14.2 | CI tests calibrated for DP noise | `JudgeThresholdRegistry` DP-corrected thresholds |
| T14.3 | Transportability and recoverability under DP distortion | `PrivacyAwareTransportCertificate` |
| T15.1 | Formal conditions for ICP-based MEC contraction | `RegimeShiftIdentificationCertificate`; Foundry discovery pipeline |
| T15.2 | Distinguishing regime shifts from latent confounding | `shift_type_assessment` diagnostic; discovery pre-screening |
| T15.3 | Computational tractability and Foundry integration for ICP | Tractable multi-environment ICP algorithm |

---
title: Universal Policy Design — Target Architecture, Gap, And Next Architecture Work (D0-D4)
status: draft design decision — NORTH STAR ACCEPTED (B-on-A, shadow-first)
owner: team-architecture
created: 2026-05-29
last_reviewed: 2026-05-29
decision_status: accepted — B-on-A is the north star; A is the release gate, B is the product ambition
supersedes: nothing
informs:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md
  - docs/plans/active/POLICYOS_POLICY_EVIDENCE_CAPABILITY_GRAPH_PLAN.md
source_audit: _build/.tmp/plan-audit-20260529/ and _build/.tmp/production-quality/
related:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_RESEARCH_PLAN.md
  - docs/backlog/universal-policy-design-case-research-results-consolidation.md
  - docs/adr/0174-policy-evidence-capability-graph.md
  - docs/system-design-decisions/policy-design-best-in-class-operating-model.md
---

# Universal Policy Design — Target Architecture, Gap, And Next Architecture Work (D0-D4)

> **Review note (2026-05-29):** revised after architecture review. Incorporates:
> north-star acceptance (B-on-A, shadow-first); D2 *architecture* unblocked
> immediately; gap-label corrections so existing seeds are not over-declared
> missing and the narrative drafter is not over-rated as a design-space engine;
> D2-D4 draft architecture added for substrate/acquisition, shadow generation,
> and evaluation redesign; second architecture review folded in facet algebra,
> automated acquisition, explicit design grammar, counterfactual-scarcity
> evaluation limits, status/replay/projection/memory guardrails, and normative
> firewall requirements; third architecture review folded in the scale axis:
> recursive design composition, system dynamics/feedback, bounded honest
> abstention, ODD-style certified operation envelopes, A-completeness/spec-gaming
> tests, multi-principal normative firewall, and a narrow-waist invariant; fourth
> architecture review operationalized hidden premise axes: epistemic regime,
> connectivity/modularity, strategic response, lifecycle/brownfield reform,
> lowering, state capacity, reversibility/stakes, measurability,
> knowledge-governance throughput, and per-axis firewalls; fifth architecture
> review applies the same prism back onto PolicyOS itself: cluster ownership,
> orphan clusters, cluster authority dimensions, inter-cluster handshakes, and a
> governed cluster-ownership mapping workflow; sixth architecture review
> replaces the D3 one-pass generator with a counterexample- and
> acquisition-guided design-search control plane; seventh architecture review
> adds the delegation operating model, where human authority enters through
> typed, mandate-bounded decisions rather than a vague autonomous/co-pilot
> switch; eighth architecture review adds the canonical `DesignRecord`,
> projection algebra, and lowering-vs-projection boundary; ninth architecture
> review defines universality as mechanism-generality plus honest boundary, not
> coverage; tenth architecture review reframes cold-start, resource economics,
> and learning as reflexive self-design with envelope revision rather than
> monotonic envelope growth; eleventh architecture review consolidates the
> growing artifact surface through shared abstractions (`TypedDiagnosticRecord`,
> `ValueOfInformationEstimate`, `GovernanceDecisionClass`, projection
> faithfulness) so the document itself does not become a P13 contract gravity
> well.

## Purpose And How To Read

This is a **design-phase artifact (D0-D4), not an ADR and not an implementation
plan.** Its job is to make one decision possible: *what system are we actually
building when we say "universal policy design".* It exists because executing the
two large plans — the Universal Policy Design Case Implementation Plan (W0-W12)
and the Policy Evidence Capability Graph Plan (ADR-0174) — produced a rigorous,
honest result that is **not** a universal policy designer, and we want to
understand why before writing more code.

- **D0** = define the target system and its success criteria. **Decided: B-on-A,
  shadow-first** (see Decision below); the options table is kept as rationale.
- **D1** = the built-vs-needed gap matrix mapped to existing components and to
  the C0-C41 research concepts.
- **D2** = substrate-composition-and-acquisition architecture: facet algebra,
  construct expression ontology, hidden-axis declarations, epistemic-regime and
  coupling/modularity classifiers, recursive design-composition algebra,
  construct-indexed capability ingestion, coverage/abstention measurement, and
  the closed acquisition loop.
- **D3** = generative-design architecture for B: shadow-only design generation,
  prediction, comparison, recommendation, and authority boundary.
- **D4** = evaluation redesign: corpus and metrics that measure design quality,
  not only grounding honesty.

Sequencing discipline: do not start D2 (substrate) / D3 (generative loop)
**implementation** before the target is fixed and the gap is agreed — that is
the mistake the last two plans embodied (exhaustive *implementation* plans that
built an excellently-made shape not matching the stated goal). **But D2
*architecture/design* can and should start immediately:** the substrate +
acquisition loop is invariant to the A/B choice, so designing it is never wasted
work. The latest scale review extends that invariant: recursive
design-composition must be designed with the substrate, because scale demand
changes what evidence and acquisition the substrate must support. The line to
hold is *no Layer-2 code before the target+gap are agreed*, not *no thinking
about the substrate/composition core*.

## Context: What The Two Plans Actually Delivered

Empirical state after the 2026-05-29 audit and the Layer-1 W12 repair:

- The Wave 12 gate is now **honest**: `real_producer` `runtime_useful_design_rate
  = 0.0`, `corpus_stub` ceiling `= 0.9231`, decision `hold_for_remediation`.
- The 0.0 is dominated by `construct_not_observed` (1416 occurrences across 13
  cases): the capability index (~1261 capabilities, mostly L1 dataset catalog +
  L2 scholar) does not observe the constructs real cases require.
- The `construct_registry_v1.yaml` governs **40 constructs** (`construct_count:
  40`) — enough for pilot cases, not for "any policy domain".

The two plans built the **grounding / authority / honesty backbone**. The
Implementation Thesis is explicitly a pipeline whose public output is *"a
projection of a claim-bound evidence graph, not a free-text policy memo"*
(implementation plan, "Implementation Thesis"). That is the hard, rigorous part,
and it works. It is **not** the same system as a universal policy designer.

## The Core Reframe

> A universal policy **designer** =
> **generation** (propose designs) +
> **grounding/authority backbone** (judge them honestly) +
> **a substrate rich enough that grounding succeeds** +
> **graded outcomes** (publish-with-limitation as a real design output).

The updated universality claim has **two independent axes**:

```text
universality =
  facet algebra                    # breadth across domains and constructs
  × design-composition algebra      # breadth across scale and structure
```

Facet algebra is what lets the system handle credit, housing, health,
education, climate, migration, and other domains without enumerating templates.
Design-composition algebra is what lets the same architecture express both a
municipal flower-bed intervention and a country-scale accession program with
thousands of legal amendments, regulatory acts, budget allocations, delivery
programs, dependencies, and feedback loops. A small policy is a leaf
`DesignCandidate`; a mega-policy is a recursive graph of sub-designs with typed
interfaces and emergent system-level obligations. Without the second algebra,
the architecture is domain-broad but scale-bespoke.

That reframe is still incomplete unless we name the hidden assumptions behind
the current runtime. The two visible axes were discovered by asking where the
architecture silently assumed homogeneity. The same method generalizes:

```text
each hidden premise removed
  -> one axis of universality or scalability
  -> one new laundering vector
  -> one verifier/firewall obligation in A
```

The certified operation envelope is therefore not just
`domain x scale x posture`. It is an irregular region in a larger space:

```text
domain
  x scale/composition
  x epistemic regime
  x connectivity/modularity
  x abstraction/lowering level
  x lifecycle stage
  x state capacity / feasibility context
  x reversibility / commitment / stakes
  x strategic response / adversarialness
  x measurability / observability
  x authority posture
```

Universal architecture means the system is parameterized over this space and
declares where it is certified, not that it is equally competent everywhere. A
template fixes a point on all axes; the desired machine composes over axes and
projects its own position and firewall status.

What is built today is the middle term. The research plan's own Goal was to
*"generate a Policy Design Case for any policy domain"* with *"LLMs as policy
formulators that generate candidate hypotheses, risks, facets, obligations …;
runtime contracts decide whether those candidates become admissible evidence,
typed blockers, limitations, or rejected speculation"* (research plan, Goal +
Architecture hypothesis). The generative half was **envisioned but left in
research / advisory status**, the substrate was **seeded but not made
universal**, and "Policy Design **Case**" (the evidentiary *case about* a
design) quietly substituted for "Policy **Design**" (the act of designing).

Six independent reasons the goal did not materialize:

1. **Scope:** W0-W12 grounds and gates a *given* design; it does not generate or
   compare designs. Generation lives in `scientist/agent/drafter*.py` and is
   fenced to advisory by ADR-0174 (an LLM candidate cannot satisfy an authority
   slot). Correct for honesty — but it means nothing *designs*.
2. **Substrate (the binding constraint):** even the judge is starved. 40
   constructs / ~1261 narrow-coverage capabilities cannot serve arbitrary
   policy. This is the dominant cause of `real_producer` 0.0.
3. **Scale:** the current design shape is one-level. Existing seeds
   (`PolicyPortfolio`, Lex bundle inputs, Foundry dynamics/feedback) are
   analysis/legal/method artifacts, not a recursive design-composition algebra.
   The system cannot yet represent a policy program as a graph of sub-designs
   whose interaction effects require their own evidence.
4. **Epistemic regime:** the current backbone mostly behaves as if useful design
   requires risk-regime evidence: identified effects, transportable data, and
   calibrated models. For unprecedented policy, deep uncertainty, ambiguity, or
   ignorance, the honest output should often be robust/adaptive/precautionary
   design with explicit regime declaration, not a permanent hard blocker.
5. **Connectivity:** the composition algebra assumes that a design decomposition
   is semantically valid. But syntactic decomposition is free; semantic
   decomposition is an empirical claim about the system's modularity. In
   entangled systems, composing authority from valid parts is invalid.
6. **Granularity:** the runtime collapses partial evidence into a hard
   `typed_blocker` where experts expect `publish-with-limitation` (9 of 13
   cases). A designer must be able to output a caveated design, not only "yes"
   or "blocked".

## Axes Of Universality And Scalability

The axes are not an open-ended checklist. They come from the structure of the
object being designed: a policy is an actor's intervention into a system,
observed by and responded to by other agents, under a state of knowledge, using
an implementation apparatus, while the designer itself must scale its own
knowledge work.

| Cluster | Axes | Why it matters |
| --- | --- | --- |
| SYSTEM | domain/facet space; construct measurability; connectivity/modularity; nonstationarity/evidence half-life; subject granularity and aggregation level. | Prevents streetlight bias, false decomposition, stale evidence, and ecological errors. |
| KNOWLEDGE | epistemic regime; substrate coverage; model contestability. | Determines what kind of design and what kind of evidence are appropriate. |
| ACTOR | mandate source; state capacity; political feasibility; multi-principal governance. | Prevents "optimal" designs that assume absent legitimacy, enforcement, or administrative ability. |
| INTERVENTION | scale/composition; abstraction/lowering level; instrument modality; lifecycle stage; reversibility/commitment; stakes/asymmetric error cost. | Distinguishes leaf interventions from portfolios, greenfield design from reform, reversible pilots from irreversible commitments. |
| OTHER AGENTS | strategic response; reflexivity; adversarialness/capture/sabotage. | Prevents pre-policy evidence from being transported into a post-policy world whose incentives changed. |
| DESIGNER ITSELF | computational tractability; knowledge-governance throughput; envelope-revision process. | Prevents "universal but not computable", "universal but bespoke-per-construct", and "ratchets only upward" failure modes. |

Two axes are structurally special:

- **Connectivity/modularity gates scale.** A recursive design graph can always be
  written syntactically, but authority can be composed across sub-designs only
  where the underlying system is modular or near-decomposable along those
  boundaries.
- **Measurability biases evidence.** Grounding naturally privileges measurable
  constructs such as income, enrollment, and budgets. Dignity, trust,
  legitimacy, institutional credibility, and informal compliance can disappear
  unless unmeasured constructs are represented as ignorance/limitation rather
  than omitted.

Three meta-laws follow:

1. **Universality-axis -> laundering-axis -> paired firewall.** Every axis that
   B can vary creates a new way to overclaim. A must add a paired firewall for
   each axis before B can be promoted in that region.
2. **The envelope is irregular, not a box.** Competence exists where substrate,
   method contracts, state/capacity assumptions, and axis firewalls all hold.
   The hard corner (national/transnational transformation + ignorance +
   entanglement + high stakes + adversarial response + multi-principal
   legitimacy) will be certified last and may stay advisory for a long time.
3. **Honest output is a vector, not a flag.** Every design projection must
   declare its position on the axes and the status of the relevant firewalls.
   PUBLIC needs the simplified version; REVIEWER/EXPERT/MACHINE need the typed
   vector and evidence refs.

## Architecture Projection: Cluster Ownership And Blind Spots

The same prism is also a diagnostic for the architecture. Each cluster needs a
producer that models the relevant axis and emits a binding artifact into the
design loop. Otherwise the system may speak as if it covers an axis while having
no way to ground it.

> Cluster without owner = axis without grounding = quiet theater of
> universality.

Grounded code scan, using package READMEs and capability-ratchet artifacts as
the first inventory layer, gives this initial ownership map:

| Cluster | Owner / seed in code | Status | What to build |
| --- | --- | --- | --- |
| SYSTEM | Domain/data: `fabric`, `scholar`, `data_forge`; nonstationarity: `ddm` ("Canonical Drift-and-Degradation Monitor"); coupling seed: `foundry/coupling/des_kernel.py`; dynamics seed: `foundry/methods/catalog/simulation/dynamics.py`. | Domain is owned; nonstationarity is owned; coupling/dynamics are strong seeds but not orchestrated into the design loop; measurability and subject granularity are orphan. | Orchestrate coupling/dynamics into D2.6; add producers for measurability adequacy and subject-granularity/aggregation risk. |
| KNOWLEDGE | Coverage/resolution: capability graph and `runtime/quality/capability_resolver.py`; contestability: Scholar contested evidence; regime: D2.5. | Mostly owned or actively being designed. | Build the regime classifier and connect it to design strategy, projection, and evaluation. |
| ACTOR | Legal authority: `lex`, `legal_requirement`; participation: `participation_requirement`; value provenance seed: `foundry/welfare/social_weight_provenance.py`. | Legal is owned; values have a seed; state capacity, mandate/legitimacy, and feasibility are orphan. | Build a state-capacity and feasibility producer: administrative capacity, enforcement, legitimacy, delivery institutions, political feasibility. |
| INTERVENTION | `pdc`, `policy_grammar`, `obligation_graph`, `obligation_rules`, `method_requirement`; D3 `DesignCandidate` grammar. | Core intervention shape is being built; reversibility, lifecycle stage, and stakes remain thin. | Promote reversibility, lifecycle/brownfield reform, transition/termination, and stakes/asymmetric error cost into first-class fields and gates. |
| OTHER AGENTS | Seeds: `foundry/methods/catalog/causal/strategic.py`, `policy_learning.py`, `dtr.py`; robustness-eval seed: `scientist/policy_design/adversary.py`. | Orphan as a cluster. There are method primitives and adversarial tests, but no orchestrated producer for "how governed agents respond to this design." | Build a strategic/behavioral response producer for Goodhart/Lucas/performativity, including claim limitation when response is unmodeled. |
| DESIGNER ITSELF | `runtime/quality` closeout/projection/ratchet; `corpus`; `berl` ("Bounded Explanation Reliability Layer"); acquisition loop; capability ratchet. | Partly owned. Tractability and envelope revision exist as ideas but not as a closed process. | Make envelope revision a governed loop: cluster map -> orphan/action list -> implementation -> ratchet -> envelope expansion or shrink. |

The headline finding is architectural, not merely taxonomic: **OTHER AGENTS**
and the capacity/legitimacy half of **ACTOR** are the largest blind spots. A
second recurring problem is **Foundry as method cemetery**: coupling, strategic,
dynamics, and welfare primitives exist, but many are not orchestrated as
cluster producers consumed by the design loop. That is P02/P12 at cluster
scale.

### Cluster Modulators: Time, Uncertainty, Authority

The clusters are not flat axes. Three modulators pass through every cluster:

| Modulator | Cluster-specific meaning |
| --- | --- |
| Time | SYSTEM has nonstationarity and evidence half-life; KNOWLEDGE has model and source decay; ACTOR has mandate duration and capacity change; INTERVENTION has lifecycle and transition timing; OTHER AGENTS have adaptation speed; DESIGNER ITSELF has envelope-revision cadence. |
| Uncertainty | There is uncertainty about system effects, evidence, state capacity, strategic response, legal lowering, and the designer's own search completeness. Epistemic regime should therefore be evaluated per cluster or per claim, not as one global run setting. |
| Authority | Each cluster contributes its own authority floor. Strong evidence in one cluster cannot average away a weak or missing authority dimension in another. |

So the honest output is not merely a vector. It is a **cluster x modulator
matrix**: each cluster declares time roles/decay, uncertainty/regime, and
authority/firewall status. This is the right schema for multi-audience
projection: PUBLIC sees the simplified cluster posture; REVIEWER/EXPERT/MACHINE
see the typed matrix and evidence refs.

The governed `cluster_ownership_map.toml` is only the ownership graph for this
matrix, not the full matrix itself. It says which cell owns a signal and which
handshake edges exist. Runtime artifacts such as `AxisPositionDeclaration`,
`ClusterInterfaceContract`, `ClusterAuthorityDimensionRecord`, and the eventual
canonical `DesignRecord` must carry the per-cluster modulator values for a
specific design. Otherwise the architecture map would promise per-cluster
regime/time/authority semantics that no runtime artifact can actually express.

### Cluster Authority Dimensions (ADR-0174 C3 Extension)

ADR-0174 C3 already treats authority as composed/min-like across trust,
identification, construct validity, schema regime, time-scope, legal, rights,
independence, and historical-prior boundaries. The cluster prism extends that
calculus:

| Cluster | Added authority dimension | Firewall floor |
| --- | --- | --- |
| SYSTEM | `coupling_validity`, `measurability_adequacy`, `aggregation_validity`. | Do not compose across invalid decomposition; do not optimize a proxy as if it were the unmeasured value. |
| KNOWLEDGE | `regime_appropriateness`, `model_contestability`. | Do not use risk-regime claims in uncertainty/ambiguity/ignorance; do not hide available evidence behind precaution. |
| ACTOR | `capacity_feasibility`, `mandate_legitimacy`. | Do not recommend designs requiring absent state capacity, enforcement, legitimacy, or value mandate. |
| INTERVENTION | `reversibility_stakes_fit`, `lowering_validity`, `lifecycle_fit`. | Do not apply low-stakes/reversible floors to irreversible or catastrophic commitments; do not ground only the intent level. |
| OTHER AGENTS | `strategic_robustness`, `response_model_validity`. | Do not transport pre-policy effects into a post-policy world whose incentives changed. |
| DESIGNER ITSELF | `self_tractability`, `coverage_honesty`, `knowledge_governance_throughput`. | Do not imply exhaustive search, broad coverage, or scalable ontology growth when only partial/manual work happened. |

Cluster authority is **composed, not averaged**. The envelope is the min over
the authority dimensions contributed by all relevant clusters. A missing
cluster producer therefore creates a real authority floor, not a documentation
gap.

This "min" is over **authority dimensions for the same design claim**. It is not
the same operator as cross-level portfolio composition. For recursive
sub-designs, admissibility flows through critical paths, scoped limitations, and
emergent-risk obligations (see D2.6). Said differently: dimensions compose by
floor; sub-design graphs compose by critical path plus explicit limitations.

### Inter-Cluster Handshake

The prism becomes runtime architecture when each cluster publishes typed outputs
and consumes the outputs of others:

```text
SYSTEM.coupling
  -> INTERVENTION.composition

KNOWLEDGE.epistemic_regime
  -> INTERVENTION.design_strategy

ACTOR.capacity_and_mandate
  -> INTERVENTION.feasibility

INTERVENTION.design_graph
  -> OTHER_AGENTS.response_model

OTHER_AGENTS.response_model
  -> SYSTEM.updated_dgp_and_coupling
```

The most dangerous edge is the reflexive loop
`OTHER_AGENTS.response_model -> SYSTEM.updated_dgp_and_coupling`: policy changes
behavior, behavior changes the data-generating process, and pre-policy evidence
can stop transporting. Today both ends of that edge are under-orchestrated. This
is the highest-priority P12 handshake to model before large-scale promotion.

### Cluster Ownership Mapping Workflow

The ownership map is now a governed artifact, not a one-off note:

```text
architecture/policy_design_case/cluster_ownership_map.toml
architecture/policy_design_case/inventory.json
tools/quality/validation/check_policy_design_case_cluster_ownership_map.py
tests/repo_quality/tools/test_policy_design_case_cluster_ownership_map.py
```

The validator reads the capability-ratchet vocabulary from
`architecture/policy_design_case/capability_reality_report.json`, so the map
cannot invent a parallel status lattice. It also checks that the map is listed
in the policy-design-case inventory, every required cluster appears, known blind
spots remain explicit, seed files exist, incomplete cells name a real
consumer/producer gap, and every cell carries authority dimension + firewall +
publish/consume edges. It now also validates the **architecture-core scope**
(`src/polisyos` only): every top-level package is assigned, every
split-required package avoids whole-package coverage, and every immediate
subpackage of those split-required packages is explicitly listed. Finally, it
validates the handshake graph itself: every `publishes` / `consumes` target must
resolve to a declared cell, port, audience, or bus; direct cell-to-cell publish
edges must be reciprocally consumed; the Goodhart/Lucas reflexive flow
`OTHER_AGENTS.strategic_response -> SYSTEM.post_intervention_dgp ->
SYSTEM.dynamics_feedback` is required; and every firewall `Pxx` must exist in
`docs/reference/policy-design-case-failure-patterns.md`.

The map reuses two existing substrates:

- **Capability ratchet:** the existing 63 capability claims and state vocabulary
  (`implemented`, `implemented_but_not_orchestrated`, `bridge_missing`,
  `producer_missing`, `contract_only`, `surface_out_of_scope`, etc.). Do not
  invent a new status system.
- **Package README headers:** package self-description through Owner / Purpose /
  Authority boundary. A package without that header is itself a map finding.

Architecture-core package bucketing for Pass 1:

| Cluster | Packages / subpackages to start from | Note |
| --- | --- | --- |
| SYSTEM | `scholar`, `fabric`, `data_forge`, `ddm`, Foundry coupling/dynamics subpackages. | Split domain/data owners from coupling/dynamics seeds. |
| KNOWLEDGE | `data_requirement`, `evidence`, `calibration`, `scholar_requirement`, `runtime/quality/capability_*`, `ir` proof-carrying analytics. | `ir` is cross-cluster when used for prediction/method evidence. |
| ACTOR | `lex`, `legal_requirement`, `participation_requirement`, Foundry welfare/social-weight provenance. | Capacity/legitimacy remains orphan until a producer exists. |
| INTERVENTION | `pdc`, `policy_grammar`, `obligation_graph`, `obligation_rules`, `method_requirement`. | Add lifecycle/reversibility/stakes fields before declaring full ownership. |
| OTHER AGENTS | Foundry strategic/policy-learning/DTR methods; `scientist/policy_design/adversary.py`. | Seeds only; no owned response producer yet. |
| DESIGNER ITSELF | `runtime/quality`, `corpus`, `berl`, acquisition loop, capability ratchet. | Treat `runtime` as a large package that must be split by subpackage/function. |
| Cross-cutting infra | `common`, `core`, `schemas`, `scientist`. | Do not assign large packages wholesale; split by contracts, runtime authority, orchestration, methods, governance, and generation. |

Validated coverage status for this pass:

| Scope | Count | Gate |
| --- | ---: | --- |
| Top-level `src/polisyos/*` packages | 25/25 | `cluster_ownership_architecture_core_package_missing` if any package is absent. |
| Split-required packages | 12 | `cluster_ownership_split_package_wholesale_assignment` if assigned as a whole-package shortcut. |
| Immediate subpackages under split-required packages | 127/127 | `cluster_ownership_architecture_core_subpackage_missing` if any subpackage is absent. |
| Cluster x axis cells | 27 | Existing ratchet-state vocabulary only; no new status lattice. |
| Handshake graph edges | 123 | `cluster_ownership_handshake_target_dangling` or `cluster_ownership_handshake_cell_edge_not_reciprocal` if the graph becomes decorative. |

Canonical row shape:

```toml
[cell.SYSTEM.connectivity_modularity]
owner_module = ""
seed_files = ["src/polisyos/foundry/coupling/des_kernel.py"]
ratchet_state = "implemented_but_not_orchestrated"
p01_chain = "bridge_missing"
authority_dim = "coupling_validity"
firewall = "P17_decomposition_laundering"
publishes = ["INTERVENTION.composition"]
consumes = ["SYSTEM.domain", "KNOWLEDGE.evidence_graph"]
gap = "no producer routes des_kernel into design-composition precondition checks"
action = "add a SYSTEM connectivity producer that emits CouplingGraph and DecompositionResult before composition authority is assembled"
```

Controlled fields:

| Field | Meaning | Source |
| --- | --- | --- |
| `owner_module` | Package/subpackage emitting the binding artifact. | README Owner or explicit orphan. |
| `seed_files` | Concrete files that already contain primitives. | Code scan. |
| `ratchet_state` | Existing capability-ratchet state vocabulary. | Ratchet + P01 check. |
| `p01_chain` | Whether input -> producer -> artifact -> bridge -> consumer -> effect -> negative test exists. | Capability reality check. |
| `authority_dim` | Cluster authority dimension contributed to the C3 extension. | Cluster authority table. |
| `firewall` | Laundering pattern the cell must block. | Pattern pass / P16 / P17 / existing P IDs. |
| `publishes` / `consumes` | Inter-cluster handshake edges. | Cluster handshake. |
| `gap` / `action` | Orphan, orchestrate seed, merge, add firewall, or explicit N/A. | Architecture review. |

Mapping SOP:

1. **Pass 0:** re-project capability-ratchet claims onto cluster x axis cells.
2. **Pass 1:** assign every top-level package and large subpackage to at least
   one cell; mark every cell owner, seed-only, or orphan.
3. **Pass 2:** run the P01 chain check per cell. A catalog method with no design
   consumer is `implemented_but_not_orchestrated`, not implemented.
4. **Pass 3:** fill authority dimension, firewall, publishes, and consumes.
5. **Pass 4:** produce action list for orphan clusters, Foundry seed
   orchestration, fragmentation, and missing authority boundaries.

Stop rule for the map:

- every architecture-core package is assigned;
- every split-required architecture-core package has each immediate subpackage
  explicitly listed;
- every cluster x axis cell has status;
- every `implemented_but_not_orchestrated` cell names the missing consumer;
- every cell has an authority dimension and firewall, or explicit N/A.

Current status: 27 cells are governed. Ten are already `implemented`; the
others deliberately remain `implemented_but_not_orchestrated`,
`producer_missing`, or `contract_only` where the architecture only has seeds,
contracts, or missing producers. The map is therefore not a success claim; it is
a ratcheted blind-spot inventory that D2/D3/D4 must burn down.

## D0 — Target System Options (rationale; decision recorded below)

| | **A — Universal Grounded Advisor** | **B-on-A — Universal Generative Designer** | **C — Grounding/Assurance Engine (refocus)** |
| --- | --- | --- | --- |
| Input | A proposed design (human/LLM-drafted) + policy question | A policy *problem*: objectives, constraints, context, population | A proposed design + evidence refs |
| Output | Honest grounded case: admissible / limited / contested / blocked + projection | Generated → compared → **recommended** design(s), each a grounded case with limitations | The case + assurance argument only |
| "Good design" means | Honest, well-grounded, correctly limited | The recommended design is effective, admissible, and confidence is **calibrated** | N/A — system does not design |
| Primary new metric | Axis-declaration correctness; construct-coverage; compositional correctness; epistemic-regime accuracy; coupling-classification accuracy; bounded honest abstention; honest `useful_design_rate` rising from 0; graded-outcome correctness | Grammar validity, regime-conditional design recall, design-time dominance, sparse prediction calibration, A-completeness/spec-gaming pass, realized regret only where observable | Assurance completeness; honesty |
| Requires beyond today | Substrate (D2) + acquisition loop + graded outcomes | **All of A** + design-space model + LLM-formulator-as-designer (gated) + outcome predictor + comparison/recommendation | Almost nothing new (finish gating) |
| Build size | Medium | Large | Small |
| Honesty risk | Low (built backbone gates it) | High **only if** A's substrate is skipped → hallucination engine | Lowest |
| Matches "design any policy"? | Partially — it is an advisor/critic, not a designer | **Yes** — this is the stated ambition | No — abandons the goal |

## D0 — Decision: B-on-A, Shadow-First

**North star: B-on-A** — a generative policy designer on top of the strict
grounding/authority backbone. C is rejected: it is honest but capitulatory (a
grounding engine, not a designer). A is adopted as the **nearest product
milestone**, not the final goal.

The decision is framed strictly, as **two roles, not one target**:

- **A is the release gate. B is the product ambition.** The system may be called
  a "universal designer" externally **only when generation passes through the
  A-backbone** (grounded, authority-composed, honestly gated). Until then it is,
  externally, the grounded advisor of milestone A.
- **B-on-A shadow-first.** The design generator (B) may be designed and run on
  the corpus from the start, but it **receives no rollout-authority** — its
  outputs are `shadow` / `advisory` only — **until the A-substrate grounds real
  cases**. This mirrors the existing LLM/sim/historical-prior firewalls in
  ADR-0174: B generates; A decides admissibility; nothing in B can pose as
  authority before A holds.
- Operating consequence: B development is *not* blocked on the substrate, but B
  *promotion* is. We can build and measure the generator in shadow while the
  substrate matures, and flip it to authority-bearing only when A passes real
  cases.

## D0 — Success Criteria (per role, beyond `useful_design_rate`)

Common to A (gate) and B (ambition):
- **Construct coverage rate**: fraction of domain/scale-sampled construct demand
  that the substrate observes with ≥ governed authority. (Today ≈ floor; needs
  a measured denominator — extend `capability_white_space.py`.)
- **Compositional correctness**: recursive design graphs preserve typed
  interfaces, dependency direction, authority boundaries, time roles, and
  system-level risk obligations when decomposed or regrouped.
- **Bounded honest abstention**: for any expressible design inside the declared
  domain × scale × posture envelope, the system either grounds it or abstains
  with a typed blocker/limitation; abstention rate is bounded by posture and
  decreases as substrate/acquisition closes gaps.
- **Certified operation envelope (ODD-style)**: every release names the domain,
  jurisdiction, scale class, epistemic regime, coupling regime,
  abstraction/lowering level, lifecycle stage, state-capacity context,
  reversibility/stakes band, authority posture, and evidence tier where the
  system is certified to operate; outside that envelope it changes strategy,
  degrades to advisory, or abstains honestly.
- **Axis-declaration correctness**: every design declares its position on
  epistemic regime, coupling/modularity, measurability, state capacity,
  strategic-response, reversibility/stakes, lowering level, lifecycle stage, and
  authority posture, plus computational/knowledge-governance status, with
  verifier-owned evidence for each position.
- **Epistemic-regime correctness**: risk, uncertainty, ambiguity, and ignorance
  are classified per claim with asymmetric penalty for false precision.
- **Coupling/modularity correctness**: decomposition is proven before authority
  is composed from parts; false-modular classification is penalized more heavily
  than false-entangled caution.
- **Scalability honesty**: computational tractability and knowledge-governance
  throughput are reported explicitly, so the system cannot be "universal" only
  by assuming unbounded compute or unbounded human ontology work.
- **Acquisition-loop closure rate**: fraction of `blocked_acquisition_required`
  that the loop resolves into a binding within a budget.
- **Graded-outcome correctness**: agreement of runtime
  pass/limitation/blocker with expert adjudication (today 1/13).
- **Closeout honesty stays = 1.0** (non-negotiable safety floor).

Additional for B (measured in shadow until promotion):
- **Design recall**: does the generator surface the design an expert panel would
  choose, within k candidates?
- **Prediction calibration on observable cases**: predicted-vs-realized outcome
  reliability only where historical implementation and credible evaluation
  evidence exist.
- **Design-time dominance / regret proxy**: whether the recommended design was
  dominated by an expert-admissible alternative using evidence available at
  design time. Realized regret is reserved for rare cases with credible
  counterfactual or multi-arm evidence.

## D0 — Operational Definition Of Universality

"Universal" cannot mean coverage of every possible policy. The denominator is
infinite, the hard corners will remain outside certified scope for a long time,
and an aggregate coverage number can hide exactly the axis failures this
architecture is meant to expose.

Universality is therefore a **mechanism claim plus a boundary claim**:

```text
universal policy designer =
  mechanism-generality
  AND honest boundary
  AND grounded authority inside the declared envelope
```

It is not omnipotence. A narrow system can be more universal than a broad
bespoke system if a held-out policy is handled by the same compositional
machinery rather than by case-specific code, construct authoring, report
templates, or manual policy-specific shortcuts.

The operational definition is a conjunction:

1. **Mechanism-generality:** held-out domains, scales, regimes, and coupling
   structures are handled by facet algebra, design-composition algebra,
   projection algebra, and governed cluster producers with sublinear marginal
   bespoke cost.
2. **Honest boundary:** envelope membership is calibrated; out-of-envelope cases
   become limitation, abstention, strategy shift, or acquisition rather than
   confident output.
3. **Grounded authority inside envelope:** in-envelope designs pass A-firewalls,
   claim/evidence binding, value-choice provenance, mandate/capacity checks,
   and projection faithfulness.
4. **Per-axis and hard-corner honesty:** scores are stratified by domain, scale,
   regime, coupling, stakes, capacity, reversibility, and authority posture.
   Aggregates may not hide the hard corner.
5. **Envelope revision dynamics:** certified regions expand through reusable
   mechanism growth and can shrink when disconfirmed.

Six skeptic attacks define the falsification battery:

| Skeptic attack | Falsification test | Failure signal |
| --- | --- | --- |
| "This is bespoke in disguise." | Frozen-system held-out cases, no case-specific code or manual construct/template authoring. | Marginal bespoke cost grows linearly; reuse-rate does not rise. |
| "It is confident theater." | Negative controls and adversarial-against-A cases. | False in-envelope, false pass, or hidden limitation. |
| "It does not know where it fails." | Envelope-membership calibration on axis-stratified held-out cases. | False in-envelope errors, weighted heavily. |
| "It is universal only on one axis." | Per-axis and hard-corner scorecard. | Aggregate pass hides regime/scale/coupling failures. |
| "It works once, then freezes." | Envelope revision over rounds. | No reusable expansion, no shrink on disconfirmation. |
| "Why call it first?" | Compare against bespoke tools, raw LLMs, and expert panels. | Another system satisfies mechanism-generality, honest boundary, and grounded authority together. |

The universality claim itself must be an assurance case. The top claim
decomposes into the five subclaims above, cites the universality test battery,
declares the certified envelope, and records skeptic attacks as defeaters. A
bare statement that the system is "universal" without envelope and battery
evidence is itself a laundering move.

Untested axis combinations are **out of envelope by default**. They can be
explored in shadow, but cannot be counted as certified universality.

## D1 — Built-vs-Needed Gap Matrix (labels corrected after review)

Layer status legend: ✅ built · 🟡 seed/partial · 🔴 missing. Where useful, the
"missing" column uses the capability-ratchet vocabulary (`bridge_missing`,
`implemented_but_not_orchestrated`, `semantic_test_missing`).

| Layer (designer anatomy) | Status | Existing seed (code / C-concept) | What is missing | Move |
| --- | --- | --- | --- | --- |
| Grounding / authority / honesty backbone | ✅ | `capability_resolver.py`, ADR-0174, C1-C3/C9/C13-C15 | nothing structural | — |
| Argument / warrant / assurance case | ✅ | W8.B, `assurance_case.py`, C13-C15 | richer machine-readable warrants (W12.E lesson) | assemble |
| Construct registry / facet grammar | 🟡 | `construct_registry_v1.yaml` (40 constructs), C4 | facet primitives, compositional construct expressions, inherited authority/proxy rules, and governance for new measure primitives | assemble + grow |
| **Universal construct-indexed substrate** | 🔴 | capability index (~1261, narrow); `capability_white_space.py`; C0/C6-C8 | broad ingestion against compositional construct expressions + authority metadata + facet-space coverage denominator | **build-new (core)** |
| **Acquisition loop (close it)** | 🟡 impl-not-closed | typed planner `acquisition_planner.py`; requirement-gap report `producer_pipeline.py:2213` (attached :859); Fabric connector registry/source contracts; C22 | the *loop*: automated discovery/retrieval first, human fallback, source contract validation, capability-index delta, rerun grounding | **orchestrate** (`implemented_but_not_orchestrated` + `bridge_missing`) |
| **Axis declaration + multidimensional envelope** | 🔴 | current authority envelope, feature flags, tuned configs, W12 ODD-like posture language | axis-position vector, per-axis firewall status, irregular envelope membership test, envelope-revision ledger | build-new core surface |
| **Cluster ownership map** | 🔴 with strong substrates | `architecture/policy_design_case/capability_reality_report.json`; package READMEs with Owner/Purpose/Authority boundary (`pdc`, `obligation_graph`); `ddm`, `berl` README identities | governed cluster x axis map, orphan detection, P01 chain per cell, C3 authority-dim extension, cluster handshakes | build governed architecture artifact |
| **Epistemic-regime classifier + regime-conditional strategy** | 🔴 with seeds | Scholar contested evidence, method boundary conditions, substrate coverage gaps, `selected_proxy_with_limitation`, robustness/sensitivity ingredients | per-claim risk/uncertainty/ambiguity/ignorance classifier, regime as A-owned claim, regime-specific design strategies and evidence rules, P16 firewall | build-new core over seeds |
| **Connectivity / modularity classifier** | 🔴 with seeds | `dynamic_graph_dscm.py`, `cyclic_id.py`, `composition_failure_cards.py`, Foundry feedback solver, Scholar/causal graph fragments | `CouplingGraph`, `DecompositionResult`, coupling regime classification, decomposition-validity gate before composing authority, P17 firewall | build-new core over seeds |
| **Design-composition algebra / scale axis** | 🔴 with seeds | `PolicyPortfolio` (`ir/loading/portfolio.py`), `LexPolicyBundleInput` (`lex/intervention_artifacts.py`), `run_hierarchical_policy_search.py`, Foundry feedback/dynamics (`foundry/execute/api.py`, `foundry/feedback/*`, `dynamic_graph_dscm.py`), `scientist/feedback/core.py` | recursive `DesignCandidate` / `PolicyProgram` / `PolicyPortfolio` graph, composition laws, typed sub-design interfaces, cross-level authority calculus, system-level dynamics/equilibrium evidence tiers | build-new core over seeds |
| State capacity / feasibility context | 🔴/🟡 | legal competence checks, participation provenance, cost/SLA gates, human review metadata | capacity-grounded feasibility contract: administrative capacity, enforcement, legitimacy, delivery institutions, political feasibility; no "optimal" design can assume missing capacity | build-new contract over existing gates |
| Strategic response / reflexivity | 🔴/🟡 | adversarial probes, Foundry game-theory/strategic methods, Goodhart-like failure patterns in semantic tests | response model or claim limitation when intervention changes agent behavior, incentives, or data-generating process | extend existing methods + adversarial corpus |
| Lifecycle / brownfield reform / lowering | 🔴/🟡 | rule replay, reissue, Lex bundles, hierarchical search, existing policy grammar | reform/transition/termination as first-class design type; progressive lowering from intent to instrument to legal text/procedure/budget with verification at every level | build-new design algebra extension |
| **Generative design-space** | 🔴 | seed only: `DraftResult`. DrafterAgent is a *"creative hypothesis generator"* (`protocols.py:283`) emitting narrative+interventions (`drafter_clients.py:86`) — **not** design-space search | first-class design grammar: instrument taxonomy, parameter space, feasibility constraints, search/diversification, normative firewall | build-new (B only) |
| **Design-search control plane** | 🔴 with governed map substrate | cluster-ownership map, typed blockers, acquisition planner, `drafter_multipass`, capability resolver, closeout blockers | blackboard-style runtime loop: `ConstraintStoreSnapshot`, `CounterexampleRecord`, `RefinementDecision`, replayable `SearchLedger`, and deterministic control decisions over cluster handshakes | build-new bridge over A/B |
| **Operational delegation layer** | 🔴 | human review metadata, approval/override gates, mandate/participation seeds | `DelegationContract`, `HumanDecisionRequest`, `HumanDecisionRecord`, P26 responsibility-integrity firewall, and mandate-bounded human authority | build-new external surface |
| **Canonical Design Record + projection algebra** | 🔴/🟡 | PDC projection, public export, BERL, assurance case, runtime closeout, `DesignCandidate` draft | replay-frozen canonical `DesignRecord`, distinction between faithful projection and authority-raising lowering, projection grammar over audience x aspect x depth x redaction x format, faithfulness checks | consolidate + build-new projection/lowering boundary |
| **Outcome prediction + comparison/welfare** | 🔴/🟡 | ingredients only: `foundry/methods/catalog/causal/*`, `foundry/feedback/*`, `foundry/methods/catalog/optimization/*`, `methods/selection/advisor.py`, bayesian sensitivity, `consultation.py`; C39/tradeoffs | a runtime contract `DesignGraph + context → outcome distributions + uncertainty + system dynamics/equilibrium caveats + welfare comparison + authority envelope` (does not exist) | build-new contract over ingredients (B only) |
| **Graded outcomes** (publish-with-limitation) | 🟡 | statuses already exist: `selected_proxy_with_limitation` (`capability_resolver.py:509`), `publish_with_limitation` (`acquisition_planner.py`, `closeout_reader.py`, `projection_semantics.py`, `status_deficits.py`) | composition policy + closeout downgrade rules that route partial evidence to limitation instead of hard block (production stays strict) | **wire composition/downgrade** (`bridge_missing` + `semantic_test_missing`); near-term, fork-independent |
| Intake / formulation from arbitrary input | 🟡 | universal policy grammar (W6), `drafter*` | recursive intake: decompose mega-problems into sub-problems/sub-designs with grounded decomposition rationale | build-new (B-leaning) |
| Cold-start bootstrap + resource economics | 🔴/🟡 | capability ratchet, cluster map, `DelegationContract` concept, acquisition planner, human review metadata | demand-pulled bootstrap from typed human acts; seed algebra generators rather than products; robust multi-budget explore/exploit allocation under principal-set mission and budgets | build DESIGNER_ITSELF self-design loop |
| Post-deploy accountability and envelope revision | 🔴/🟡 | DDM, calibration ledger, lifecycle/reissue, corpus, capability ratchet | `DeploymentDossier`, `DivergenceRecord`, attribution-gated `LearningUpdateProposal`, envelope expansion/shrink, anti-learning firewalls, historical-prior boundary | orchestrate |
| Universality assurance / test battery | 🔴 | `assurance_case.py`, D4 corpus, capability ratchet, cluster map | held-out frozen-system universality battery, per-axis scorecard, skeptic defeaters, reuse-rate, universality-claim firewall | build governed assurance artifact |
| Evaluation corpus & metrics | 🟡 | 13 hand-authored grounding cases, `run_universal_outcome_corpus.py` | expert oracle bootstrap, breadth targets, design-time dominance metrics, sparse realized-outcome calibration | rebuild (D4) |

## D1 — Dependency Graph And Sequencing Insight

```text
                 ┌─────────────────────────────────────────┐
                 │  Grounding/authority backbone (BUILT) ✅  │
                 └───────────────┬─────────────────────────┘
                                 │ starved by
                 ┌───────────────▼─────────────────────────┐
   BINDING       │  Universal construct-indexed substrate 🔴 │ ◀── gates A and B
   CONSTRAINT    │  + acquisition + epistemic/coupling A-gates│
                 └───────────────┬─────────────────────────┘
                                 │ binds leaf and composite designs
                 ┌───────────────▼─────────────────────────┐
   SCALE         │  Design-composition algebra 🔴            │ ◀── gates scale universality
   CONSTRAINT    │  recursive programs/portfolios/dynamics   │
                 └───────────────┬─────────────────────────┘
                                 │ enables honest grounding to succeed at scale
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                         ▼
  Graded outcomes 🟡       (A milestone)          Generative design-space 🔴
  (fork-independent,                              + outcome comparison 🔴/🟡
   near-term)                                      (B ambition; shadow until A holds)
```

The substrate-composition-and-acquisition design (D2) is the
facet/construct-demand loop:

```text
facet-space demand denominator → construct expression → capability binding
  → failure/acquisition strategy → automated/human acquisition execution
  → re-index → rerun grounding
```

The design-composition loop is the scale complement:

```text
problem/decomposition demand
  → recursive design graph (leaf candidates + sub-design interfaces)
  → typed dependencies and critical path
  → emergent dynamics/equilibrium obligations
  → cross-level authority composition
  → grounded portfolio/program case or honest abstention
```

Four consequences:

1. **The substrate + acquisition loop is invariant to the A/B choice** and is the
   binding constraint. Designing it (D2 architecture) is never wasted regardless
   of target, and is unblocked now.
2. **Graded outcomes is fork-independent and near-term** — it is a runtime-logic
   wiring (composition policy + closeout downgrade at research/governed;
   production stays strict per ADR-0174), and it alone moves the honest
   `useful_design_rate` off 0 for the 9 cases experts label
   `publish-with-limitation`. The statuses already exist; only the routing is
   missing.
3. **Scale universality is a separate gate** — adding more domain constructs
   will not make a national accession program representable unless recursive
   design composition, critical paths, feedback obligations, and system-level
   authority semantics are first-class.
4. **Epistemic regime and coupling are verifier gates** — a design generator may
   not pick its own uncertainty regime or decomposition boundary. A must
   classify both before B can search or recommend within that region.

## Unifying Abstractions To Prevent P13 Gravity

This document is intentionally broad, but its implementation must not become a
catalog of bespoke artifacts. The next architecture step should consolidate
around a small set of cross-cutting abstractions that reduce surface area while
preserving honesty.

1. **Reflexive self-design:** the system is subject to its own discipline. The
   same grounding, envelope, firewall, faithfulness, and learning rules that
   govern policy recommendations also govern claims about PolicyOS itself:
   universality, envelope membership, architecture ownership, resource
   allocation, and rollout posture.
2. **`TypedDiagnosticRecord`:** a common diagnostic shape for design-time
   `CounterexampleRecord`, post-deploy `DivergenceRecord`, regime/coupling
   misclassification feedback, and adversarial spec-gaming findings. Required
   fields: class, failed axis/firewall, evidence refs, attribution owner,
   allowed moves, learning eligibility, authority boundary, replay refs, and
   whether B may learn from it or A must be repaired first.
3. **`ValueOfInformationEstimate`:** one currency for acquisition, refinement,
   human attention, expert oracle work, corpus labeling, and resource
   allocation. VOI means expected reduction in design/envelope uncertainty per
   unit of constrained budget, with budgets kept typed rather than averaged
   away: compute, acquisition money, expert time, legal access, human attention,
   urgency, and stakes.
4. **Ascending-cost frontier expansion:** begin with cheap, reversible,
   low-stakes, reusable moves; then spend scarce resources only where VOI and
   authority impact justify it. This is the same principle behind multi-fidelity
   search, easy-corner bootstrap, VOI-ranked acquisition, and envelope revision.
5. **`GovernanceDecisionClass`:** `DelegationContract` should be the single
   registry for decisions that cannot be made by B: value authorization,
   `a_spec_gap`, less-cautious regime override, decomposition override,
   acquisition approval, envelope shrink/expansion, promotion, and final
   selection. Otherwise governance authority will fragment across local enums.
6. **Envelope-favorable design operators:** modularization moves, adaptive
   pathways, reversibility-preserving pilots, ring-fencing, phasing,
   severability, buffers, and monitoring triggers are one family of B operators:
   they move a hard-corner design toward a certifiable envelope instead of only
   searching inside the current envelope.
7. **Faithfulness verifier reuse:** the projection faithfulness verifier applies
   both to policy outputs and to the system's self-description. A claim like
   "universal" or "production-capable" must be faithful to the envelope,
   held-out battery, failure modes, and unresolved blockers in the same way a
   public policy brief must be faithful to the canonical `DesignRecord`.

These abstractions are the pressure valve against P13. A future D5 plan should
prefer wiring one of them across D2-D4 over adding another one-off artifact
family.

## Pattern Pass For D2-D4

D2-D4 are architecture work, but they touch the most dangerous runtime seams, so
the pattern register applies before implementation planning.

| Area | Patterns | Target correct pattern | Missing capability labels until implemented |
| --- | --- | --- | --- |
| D2 substrate | P01, P02, P03, P04, P05, P06, P07, P08, P10, P12, P14 | Construct demand is represented as compositional facet-space expressions, then bound to capabilities with authority, lineage, time, replay, and independence semantics; scenario-family shims remain projections only. | `producer_missing`, `artifact_missing`, `bridge_missing`, `verification_missing`, `semantic_test_missing` |
| D2 acquisition loop | P01, P02, P04, P07, P09, P13 | A blocker creates an owned acquisition task; automated discovery/retrieval runs before human fallback; execution produces a source contract/capability-index delta; rerun proves closure without mutating closed-case replay semantics. | `implemented_but_not_orchestrated`, `bridge_missing`, `consumer_missing` |
| D2 axis declaration / envelope | P03, P04, P05, P06, P10, P13 | Every design emits an axis-position vector plus per-axis firewall status; envelope membership is verifier-owned and irregular, not a manually declared marketing scope. | `contract_only`, `producer_missing`, `surface_missing`, `semantic_test_missing` |
| D2 epistemic regime | P04, P05, P10, P13, P15, P16 | Regime is an A-owned per-claim classification, not a B-selected setting. False precision and false precaution are both blocked. | `contract_only`, `producer_missing`, `verification_missing`, `semantic_test_missing` |
| D2 connectivity / modularity | P01, P02, P04, P05, P10, P12, P13, P14, P17 | A decomposition can be used for authority composition only after the coupling graph proves modular or near-decomposable boundaries; entangled systems require system-level grounding or downgrade. | `contract_only`, `producer_missing`, `bridge_missing`, `semantic_test_missing` |
| D2 design composition / scale | P01, P02, P03, P04, P05, P06, P07, P08, P10, P12, P13, P14 | Recursive designs compose through a narrow-waist design graph with typed interfaces, critical paths, explicit limitations, emergent-risk obligations, system-dynamics evidence tiers, replay refs, and audience-visible scale boundaries. | `contract_only`, `producer_missing`, `bridge_missing`, `surface_missing`, `semantic_test_missing` |
| D3 generative loop | P01, P02, P03, P04, P05, P10, P11, P12, P13, P15, P16, P17, P25 | Generation is grammar-constrained, regime-conditional, counterexample-guided, acquisition-aware, replayable, shadow/advisory until A grounds it, visible as shadow in every audience projection, and informed by balanced success/failure memory without becoming authority. A-completeness is treated as a safety dependency: `a_spec_gap` is governance-owned and may not become B-side success. | `contract_only`, `producer_missing`, `bridge_missing`, `surface_missing`, `semantic_test_missing` |
| D3 delegation layer | P03, P04, P05, P09, P10, P13, P20, P22, P26 | Human authority enters through `DelegationContract`, `HumanDecisionRequest`, and `HumanDecisionRecord`; autonomy is capability ∩ permission ∩ bounds; approvals are mandate-checked and informed by limitations/disconfirming evidence. | `contract_only`, `producer_missing`, `surface_missing`, `semantic_test_missing` |
| D4 evaluation | P04, P10, P11, P13, P15, P16, P17, P25, P26 | Metrics separate grounding honesty, substrate coverage, acquisition closure, epistemic-regime accuracy, coupling accuracy, compositional correctness, bounded abstention, counterexample/refinement validity, delegation quality, design-time expert dominance, sparse realized-outcome calibration, post-deploy accountability, recommendation regret where observable, spec-gaming resistance, and success-pattern learning. | `artifact_missing`, `verification_missing`, `semantic_test_missing` |

Universal-design pattern extension used by this document:

- **P16 Epistemic-regime laundering:** upgrade direction = claiming risk-regime
  authority without risk-regime evidence; downgrade direction = hiding available
  evidence behind "uncertainty" or "precaution" to avoid proof. Closure:
  verifier-owned regime classification, asymmetric penalties, and
  regime-shopping ban for B.
- **P17 Decomposition / partial-equilibrium laundering:** claiming the whole is
  admissible because the parts are admissible while the system is entangled.
  Closure: coupling graph and decomposition-validity proof before composing
  authority; false-modular errors weighted heavily.
- **P18 Streetlight measurability laundering:** optimizing measurable proxies
  as if they exhausted the policy value. Closure: measurability adequacy,
  proxy-validity limits, and explicit ignorance for unmeasured constructs.
- **P19 Aggregation laundering:** transporting evidence across individual,
  group, institutional, jurisdictional, or supranational levels without
  aggregation-validity checks. Closure: subject-granularity records and
  ecological-error guards.
- **P20 Normative choice laundering:** silently choosing objectives or social
  weights. Closure: authorized value-choice provenance and frame-indexed
  projections.
- **P21 Capacity-feasibility laundering:** assuming administrative, fiscal,
  enforcement, delivery, or legitimacy capacity the actor does not have.
  Closure: state-capacity grounded feasibility and design-to-build-capacity
  obligations where appropriate.
- **P22 Mandate-legitimacy laundering:** treating goals, weights, or affected
  group authority as authorized without legal, participatory, or governance
  mandate. Closure: mandate/legitimacy records before closeout.
- **P23 Stakes and commitment laundering:** applying low-stakes/reversible floors
  to high-stakes, irreversible, or catastrophic commitments. Closure:
  stakes/reversibility classification and option-value preserving strategies.
- **P24 Strategic-response laundering:** transporting pre-policy effects into a
  post-policy world whose incentives and data-generating process change.
  Closure: response-model validity or explicit claim limitation.
- **P25 Search-control laundering:** projecting a search frontier,
  control-plane summary, or best-so-far candidate as if it were exhaustive,
  replayable, or authoritative. Closure: replayable `SearchLedger`, search
  incompleteness declaration, and clear separation between frontier support and
  producer evidence.
- **P26 Responsibility-integrity laundering:** the system shifts responsibility
  to a human who was not informed enough to approve, or the human shifts
  responsibility to "the AI." Closure: mandate-bounded `HumanDecisionRecord`,
  active choice for high-stakes/value-laden decisions, disconfirming evidence,
  and responsibility-integrity checks.

## D2 — Substrate, Composition, And Acquisition Architecture Draft

**Decision shape:** the substrate is not a larger dataset catalog and not an
ever-growing list of bespoke atomic constructs. It is a compositional
facet-space authority substrate **plus** a compositional design substrate.
Construct demand is expressed as typed facet coordinates or regions, then bound
to capabilities, failure/acquisition nodes, source contracts, and rerun
receipts. Scale demand is expressed as recursive design graphs with typed
sub-design interfaces, dependencies, critical paths, and system-dynamics
obligations. The acquisition planner is not complete until it closes a loop,
not only emits a recommendation.

The D2 artifact should become a dedicated
**substrate-composition-and-acquisition ADR** with these commitments.

### D2.1 Core Runtime Loop

```text
policy/problem/design input
  -> axis-position declaration (domain, scale, regime, coupling, capacity, etc.)
  -> epistemic-regime classification per claim
  -> coupling/modularity classification for proposed decomposition boundaries
  -> compiled claim/obligation/data/method/legal/participation requirements
  -> recursive design graph when the policy has sub-designs or scale structure
  -> construct demand ledger (facet expression + authority posture)
  -> system-dynamics / cross-design risk requirements where composition is non-additive
  -> RequirementToCapabilityResolver
  -> capability binding or typed gap
  -> eligibility-before-ranking acquisition plan
  -> automated source discovery/retrieval or human acquisition task execution
  -> source contract + lineage/quality/legal-use scope
  -> capability-index delta
  -> rerun grounding
  -> admitted / limited / contested / still blocked
```

The loop only closes when a rerun consumes the updated capability index and
changes the binding, limitation, or blocker state. A task marked done by a human
or fetcher is not closure by itself.

### D2.2 First-Class Artifacts

| Artifact | Purpose | Authority boundary |
| --- | --- | --- |
| `FacetPrimitiveRegistry` | Governed primitive values for entity, measure type, unit, time role, population, jurisdiction, instrument, delivery channel, and observation mode. | Authoritative for facet semantics only. |
| `ConstructExpression` | A typed point or region in facet-space, e.g. entity x measure-type x unit x time-role x population x jurisdiction. | Authoritative for construct demand shape, never evidence. |
| `ConstructDemandLedger` | The denominator: every construct expression the case needs, with claim refs, authority level, geography, population, time roles, and evidence family. | Authoritative for demand, never evidence. |
| `ConstructOntologyDelta` | Governed growth of facet primitives and construct expressions: proposed, governed, deprecated, merged, split. | Authoritative for construct/facet semantics only. |
| `AxisPositionDeclaration` | Per-design vector for domain, scale, epistemic regime, coupling/modularity, abstraction/lowering level, lifecycle stage, state-capacity context, reversibility/stakes, strategic response, measurability, computational tractability, knowledge-governance mode, and authority posture. | Authoritative for declared position only after verifier-owned classification. |
| `AxisFirewallStatus` | Per-axis firewall result: passed, limited, contested, missing, out-of-envelope, or verifier-incomplete. | Readiness/projection signal; does not satisfy domain evidence. |
| `ClusterOwnershipMap` | Governed cluster x axis map from package/readme ownership and capability ratchet state to owners, seeds, P01 chain, authority dimension, firewall, publishes, consumes, gap, and action. | Architecture/readiness artifact; cannot satisfy runtime claim authority. |
| `ClusterInterfaceContract` | Typed publish/consume contract between clusters, e.g. SYSTEM.coupling -> INTERVENTION.composition. | Orchestration boundary; not producer evidence. |
| `ClusterAuthorityDimensionRecord` | Declares the authority dimension each cluster adds to the ADR-0174 C3 envelope extension. | Authority calculus input; downstream closeout must still consume it. |
| `TypedDiagnosticRecord` | Common diagnostic record for counterexamples, divergences, misclassification feedback, and spec-gaming findings: class, failed axis/firewall, evidence refs, attribution owner, allowed moves, learning eligibility, authority boundary, and replay refs. | Learning/control input only; may not satisfy evidence or authority slots. |
| `ValueOfInformationEstimate` | Comparable estimate of expected reduction in design/envelope uncertainty per typed budget unit: compute, acquisition money, expert time, legal access, human attention, urgency, and stakes. | Scheduling and governance input; may not override authority floors. |
| `MinimalSeedManifest` | Launch seed of algebra generators, not products: initial facet primitives, instrument primitives, projection primitives, first easy-corner envelope, A-firewalls, budgets, and held-out battery refs. | Bootstrap governance artifact; cannot claim universality by itself. |
| `EpistemicRegimeClaim` | Per-claim classification: risk, uncertainty, ambiguity, ignorance, or contested-model, with evidence refs and asymmetric error policy. | Authoritative for design strategy selection, not for outcome evidence. |
| `CouplingGraph` | Pairwise and boundary-level interaction graph across sub-designs, constructs, institutions, legal acts, fiscal flows, and feedback paths. | Evidence requirement artifact; may not prove decomposition by itself. |
| `CouplingRegimeClassification` | Boundary classification: modular, near-decomposable, hierarchically-coupled, or entangled/general-equilibrium. | Gate for whether authority may be composed across that boundary. |
| `DecompositionResult` | Auditable modules, cross-terms, critical paths, residual interaction ledger, and decomposition validity status. | Decomposition authority only; not claim evidence. |
| `RecursiveDesignGraph` | Leaf `DesignCandidate` nodes plus composite `PolicyProgram` / `PolicyPortfolio` nodes, typed dependencies, critical-path refs, and sub-design interfaces. | Authoritative for design structure only; not evidence or recommendation authority. |
| `DesignInterfaceContract` | Inputs/outputs, authority requirements, time/geography scope, implementation dependency, fiscal dependency, legal dependency, data dependency, and handoff obligations between sub-designs. | Boundary contract; may not satisfy producer evidence. |
| `SystemDynamicsRequirement` | Records when composition is non-additive and requires feedback/equilibrium/dynamic-regime analysis. | Requirement signal; evidence only after Foundry/method validation. |
| `CertifiedOperationEnvelope` | Irregular region in domain x jurisdiction x scale x epistemic regime x coupling x lowering x lifecycle x capacity x reversibility/stakes x authority posture x evidence tier. | Release/readiness boundary; outside it the system changes strategy, degrades, or abstains. |
| `HonestAbstentionReceipt` | Typed reason the system declines to ground or recommend a design inside or outside the envelope. | Honesty/readiness evidence, not useful-design success. |
| `ComputationalTractabilityBudget` | Search-space size, decomposition depth, memoization/reuse refs, anytime cutoff, and approximation status for large design graphs. | Runtime feasibility signal; may not weaken authority requirements. |
| `KnowledgeGovernanceThroughputLedger` | Measures whether facet/source/method/envelope growth is automated, governed, and not linear human work per new construct. | Scalability signal; may not satisfy source authority. |
| `CapabilityBindingResult` | Resolver answer: selected, proxy-with-limitation, context-only, simulation-only, acquisition-required, construct-not-observed, authority/right/freshness blocked. | Binding/admissibility signal, not raw source evidence. |
| `SubstrateCoverageSnapshot` | Demand x capability state, stratified by domain, authority, construct expression, facet primitive, jurisdiction, and time role. | Measurement surface; may not satisfy closeout. |
| `AcquisitionTaskRecord` | Owned task with eligibility, VOI rank, automated/human route, connector/source candidate refs, cost/time, legal-use review, expected authority envelope, TTL, and owner. | Governance/routing artifact, never evidence. |
| `SourceDiscoveryCandidate` | Candidate dataset/API/document found through connector registry, semantic catalog, or human nomination. | Candidate only until SourceContract validation. |
| `SourceContract` / capability-index delta | Persisted source binding with lineage, quality, rights, freshness, construct validity, authority-derivation record, and generated capability refs. | Producer evidence only after adapter/readiness validation. |
| `RerunClosureReceipt` | Proof that the new index was consumed and changed or preserved the case outcome. | Closure evidence for the acquisition loop. |

### D2.3 Facet Algebra And Construct Ontology Breadth

The construct registry should grow by **facet composition plus demand-driven
saturation**, not by domain templates or one-off atomic constructs. A construct
is a typed point or region in a facet space:

```text
entity × measure_type × unit × time_role × population × geography/jurisdiction
  × instrument/context × observation_mode × source_rights × method_need
```

The universal move is compositional inheritance:

- new policy demand first tries to compose existing facet primitives into a
  construct expression;
- authority floors, proxy rules, rights gates, freshness rules, and method
  compatibility attach to facet primitives and facet combinations, then inherit
  into construct expressions;
- coverage denominators measure demanded facet-space regions, not only a list
  of 40+N named constructs;
- named constructs such as `credit_program_enrollment` remain useful aliases or
  governed shortcuts for recurring expressions, but they are not the only path
  to coverage.

This changes the scaling curve from O(N hand-authored constructs) toward
O(facet primitives + governed composition rules). The honest limit remains:
new measure primitives, novel units, new legal-use classes, and proxy
transport-validity claims still sometimes require human/governance input. D2
must name those cases explicitly instead of hiding them behind "universal"
language.

A new facet primitive or named construct expression can be added when at least
one of these is true:

- a corpus or runtime case emits repeated construct demand that cannot be
  expressed by existing facet primitives or composition rules;
- an acquisition source has stable measurement semantics that deserve a
  construct target or new measure primitive;
- an existing construct expression is overloaded and needs split/merge
  governance;
- expert adjudication marks a missed obligation because the facet expression was
  absent or miscomposed.

Each governed facet primitive and construct expression needs: aliases,
disallowed aliases, domain tags, entity scope, geography/time-role requirements,
admissible evidence modes, authority floors per posture, proxy validation
rules, legal-use constraints, allowed method contracts, corpus bindings, and
sunset behavior if it replaces a legacy projection. Scenario-family names stay
compatibility aliases and never become authority selectors.

### D2.4 Axis Declarations And Multidimensional Envelope

D2 must make the hidden premise axes explicit. Every design, sub-design, claim,
and projection should carry an `AxisPositionDeclaration` plus
`AxisFirewallStatus` records. At minimum:

| Axis | Declaration | Firewall question |
| --- | --- | --- |
| Epistemic regime | risk / uncertainty / ambiguity / ignorance / contested-model per claim. | Is the design strategy and evidence type appropriate for this regime? |
| Connectivity/modularity | modular / near-decomposable / hierarchically-coupled / entangled per boundary. | Is authority composition across this boundary allowed? |
| Abstraction/lowering | intent, instrument, legal text, regulation, procedure, budget, implementation plan, monitoring rule. | Has each lowered level been grounded independently? |
| Lifecycle stage | greenfield, reform, transition, termination, grandfathering, emergency, recovery. | Are legacy constraints, transition costs, and path-dependence represented? |
| State capacity | implementing institutions, enforcement, administrative load, legitimacy, participation capacity. | Does the design assume capacity that the context lacks? |
| Reversibility/stakes | reversible, pilotable, option-preserving, lock-in, irreversible; low/high/catastrophic stakes. | Are floors and strategy appropriate for asymmetric error cost? |
| Strategic response | passive, adaptive, gaming-prone, adversarial/capture/sabotage. | Is agent response modeled or the claim limited? |
| Measurability | directly observed, proxy-observed, qualitative, contested, unmeasured. | Are unmeasured values surfaced as ignorance/limitation rather than omitted? |
| Computational tractability | exact, approximate, memoized, incremental, anytime-bounded, infeasible. | Is search/model incompleteness projected honestly? |
| Knowledge-governance throughput | automated proposal, human-reviewed, institution-owned, manual bespoke. | Can the envelope revise without linear hand-authoring per new construct/source? |

The envelope is an irregular, governed region in this axis space. A design is
inside the envelope only where substrate coverage, method contracts, state
capacity assumptions, coupling classification, epistemic regime, and per-axis
firewalls all hold. At a frontier, the correct behavior is not silent failure:
the system should change design strategy, degrade to advisory, publish with
limitation, or abstain with a typed receipt.

This also defines envelope revision. The designer improves by expanding the
certified region through substrate acquisition, method contracts, validated
firewalls, and knowledge-governance throughput, and by shrinking regions when
deployment evidence, spec-gaming, or classifier error disconfirms them.
Expansion should start from the easy corner (low stakes, reversible, modular,
measurable, risk-regime, local scale) and move outward. The hard corner
(large-scale, entangled, high-stakes, irreversible, adversarial,
multi-principal, ignorance/ambiguity) is likely to remain shadow/advisory
longest; that is honesty, not failure.

### D2.5 Epistemic-Regime Architecture

Epistemic regime is the root axis because the existing backbone is strongest
when evidence exists and is relevant. For unprecedented or weakly studied
policy, "not enough risk-regime evidence" should not always mean "no design."
It should change the type of design, the type of admissible evidence, and the
form of honest output.

The regime taxonomy follows a two-dimensional incertitude matrix:

| | Probabilities tractable | Probabilities problematic |
| --- | --- | --- |
| Outcomes/possibilities tractable | **Risk** | **Uncertainty** |
| Outcomes/possibilities problematic | **Ambiguity** | **Ignorance** |

`contested_model` is a practical runtime label for cases where models, frames,
or causal stories are materially disputed even if some evidence exists.

Each regime changes the full design contract:

| Regime | Evidence/method | Design strategy | Claim semantics | Honest output |
| --- | --- | --- | --- | --- |
| Risk | Identified causal estimates, calibrated models, RCT/quasi-experimental evidence with transport checks. | Expected-welfare optimization, sensitivity analysis, point design. | Effect claims with intervals; production possible if other axes hold. | Optimized design + grounded effect graph. |
| Uncertainty | Partial identification, bounds, intervals, multi-prior, scenario sets. | Robust decision making, satisficing, minimax-regret, exploratory modeling. | Robust over a declared scenario/range; generally governed/research. | Robust design + scenario envelope (`robust_to` / `fragile_to`). |
| Ambiguity | Plural frames, MCDA, deliberative/stakeholder value elicitation, extended peer review. | Multi-frame design, deliberative mapping, explicit incommensurability. | Valid under frames F1..Fn; no single best design without authorized value input. | Portfolio of frame-indexed designs + value-choice provenance. |
| Ignorance | Analogies, red-team/horizon scan, near-miss monitoring, surprise ledger; no completeness claim. | Resilience, reversibility, diversification, safe-to-fail pilots, adaptive pathways with triggers, option value. | Process/precaution properties only; outcome claims prohibited. | Adaptive/precautionary design + monitoring/triggers + ignorance ledger. |

Four invariants keep this axis from becoming a loophole:

- **Regime is a claim, not a setting.** It needs evidence: substrate coverage,
  transport/boundary conditions, model contestability, precedent, expert
  disagreement, and validated models where relevant.
- **Regime is per-claim.** One design may be risk-regime for a well-studied
  effect and ignorance-regime for a novel second-order mechanism.
- **Regime composes through design composition.** The portfolio regime is
  dominated by the worst regime on the critical path, while non-critical
  ignorance can become scoped limitation if posture permits.
- **A classifies, not B.** The generator may not choose the easiest regime.
  Defaults err toward more uncertainty when evidence is insufficient; false
  risk is more dangerous than false caution.

P16 has two firewalls:

- **Overconfidence firewall:** no risk-regime authority without risk-regime
  evidence.
- **Precaution/robustness-laundering firewall:** no "uncertainty" or
  "precaution" downgrade when risk-regime evidence was available and should have
  been used.

The W12 over-blocking hypothesis becomes testable: classify the original
13 cases by regime. If the 9 expert `publish-with-limitation` cases are mostly
uncertainty/ambiguity rather than risk, a regime-aware engine should return
robust/limited designs without weakening production evidence floors.

### D2.6 Design-Composition Algebra, Coupling, And Scale Axis

Facet algebra gives domain breadth; it does not by itself represent policy
scale. D2 must therefore define a second algebra: recursive composition of
designs. A `DesignCandidate` can be:

- a **leaf**: one bounded intervention, rule, procurement, service change,
  information campaign, budget line, or municipal action;
- a **composite**: a `PolicyProgram` / `PolicyPortfolio` graph whose nodes are
  sub-designs and whose edges are typed dependencies, conflicts, complements,
  substitutions, feedback paths, and sequencing constraints.

The seed artifacts already exist, but at the wrong layer: `PolicyPortfolio` in
IR can score feasible policy sets, `LexPolicyBundleInput` can carry legal
bundles, and Foundry/Scientist have dynamic, feedback, equilibrium, and
hierarchical-search ingredients. D2's move is to lift these into a
design-level algebra rather than leave them as isolated analysis/legal/method
objects.

The precondition is coupling. A design can always be decomposed syntactically,
but semantic decomposition is an empirical claim about the world. D2 must build
`CouplingGraph`, `CouplingRegimeClassification`, and `DecompositionResult`
before it composes authority from sub-designs.

| Coupling regime | Composition operator | Design strategy | Authority aggregation | Honest output |
| --- | --- | --- | --- | --- |
| Modular | Full decomposition; modules independent. | Design modules in parallel. | Whole authority composes from independent module authority plus critical-path min. | Independent module designs + clean composition receipt. |
| Near-decomposable | Decomposition plus explicit weak interface terms and time-scale separation. | Design modules, then coordinate cross-terms. | Module authority plus grounded interface terms; residual interaction becomes limitation. | Module designs + interface ledger + limited residual claim. |
| Hierarchically-coupled | DAG decomposition with strong directed dependencies. | Design in topological order; upstream constraints propagate downstream. | Weak upstream nodes cap downstream claims. | Dependency-ordered design + propagated-constraint graph. |
| Entangled / general-equilibrium | No clean decomposition; feedback/cycles dominate. | Holistic system design, fixed-point/equilibrium simulation, adaptive pathways. | Whole authority cannot be assembled from parts; needs system-level evidence or downgrade. | System design + equilibrium/dynamics model + explicit non-decomposable boundary. |

This is the strict version of "connectivity gates scale": the existing
critical-path + emergent-risk calculus is valid for modular,
near-decomposable, and hierarchical cases. In entangled cases it is not enough.
The system must route to system-level Foundry dynamics/feedback/equilibrium
methods or downgrade to advisory/limited/abstained status.

Coupling classification has four invariants:

- modules are discovered results, not user input;
- coupling is boundary-specific, not a single global label;
- A classifies coupling, not B, so the generator cannot declare a convenient
  decomposition;
- defaults err toward more coupling when evidence is missing, because
  false-modular classification is the dangerous error.

Composition must have laws, not templates:

- **identity/no-op**: a no-op design can serve as baseline and must not change
  the portfolio's authority state;
- **associativity/regrouping invariance**: regrouping sub-designs into programs
  or portfolios must preserve interfaces, dependencies, and closeout-relevant
  evidence refs;
- **typed interface compatibility**: a sub-design's outputs, legal acts, budget
  allocations, data products, and delivery commitments must match the consumer
  sub-design's inputs;
- **critical-path monotonicity**: critical dependencies may block or limit the
  portfolio, but non-critical limitations should not collapse a large portfolio
  into global hard block when the authority posture permits scoped limitation;
- **prove-decomposition-before-composing**: a portfolio may compose authority
  from parts only across boundaries classified modular, near-decomposable, or
  hierarchical with grounded interface terms;
- **explicit boundary refs**: every cross-level handoff carries authority,
  provenance, rule version, time role, geography, population, and audience
  purpose.

Cross-level authority is the hard semantic problem. Portfolio admissibility is
not `min(all sub-designs)` (large programs would never publish) and not an
average (ADR-0174 forbids authority dilution). The proposed calculus is:

```text
portfolio posture =
  critical_path_admissibility
  + scoped limitations for non-critical gaps
  + emergent cross-design risk obligations
  + public/audit projection of all downgraded, contested, and blocked nodes
```

This means a portfolio can be `admissible_with_limitation` when its critical
path is grounded and non-critical gaps are scoped, owned, and projected. But
composition creates its own obligations: systemic fiscal pressure, legal
sequencing risk, delivery bottlenecks, strategic response, market displacement,
general-equilibrium effects, institutional overload, and feedback instability
are not inherited from leaf evidence. They require separate
`SystemDynamicsRequirement` records.

P17 is the paired firewall: decomposition / partial-equilibrium laundering is
blocked by requiring a coupling graph and decomposition-validity proof before
the system can claim "the whole is admissible because the parts are admissible."
Strategic agents can also break modularity by arbitraging boundaries, so
decomposition validity must be stress-tested against strategic response where
stakes justify it.

System dynamics is where composition stops being additive. The effect of a
thousand simultaneous legal, fiscal, and delivery changes is not the sum of a
thousand leaf effects. Rather than creating a second forecast vocabulary, system
claims use the D3.5 `ForecastSupport` dictionary plus a system-scope qualifier:

| System-level label | D3.5 base origin + scope | Meaning |
| --- | --- | --- |
| `leaf_only_no_system_claim` | grounded leaf claims + `claim_scope=leaf_only` | Leaf designs are grounded, but no system-level effect is claimed. |
| `simulation_only_system_effect` | `simulation_only` + `claim_scope=system_effect` | Useful for exploration; must project as simulation/advisory. |
| `transported_with_heavy_limitation` | `transported_scholar_estimate` + `claim_scope=system_effect` + heavy context limit | External dynamic or equilibrium evidence is transported with strong context limits. |
| `validated_local_dynamic_model` | `validated_local_model` + `claim_scope=system_effect` + dynamic/equilibrium checks | Local data, method validity, calibration, and sensitivity checks support a governed system-level claim. |
| `historical_prior_system_context` | `historical_prior` + `claim_scope=system_effect` | Routing/review influence only; never current-run system-effect evidence. |
| `equilibrium_contested` | `equilibrium_contested` + `claim_scope=system_effect` | Multiple equilibria, unstable feedback, or strategic response prevents a single authoritative system prediction. |

For country-scale or transnational transformations, the expected honest default
will often be `simulation_only_system_effect` or
`transported_with_heavy_limitation`, not production authority. That is not a
failure; it is the correct abstention boundary for unobservable
counterfactuals.

Recursive intake is part of the same algebra. A mega-request cannot remain one
`ProblemFrame`. Decomposing it into sub-problems and sub-designs is itself a
grounded design act with provenance, alternatives, reviewer visibility, and
closeout effects. The intake layer must therefore produce a
`RecursiveDesignGraph` or an honest abstention when decomposition cannot be
justified.

Modularization can also be a design move. A mature generator may propose
ring-fencing, pilots, phase sequencing, severability clauses, firebreaks,
buffers, transition periods, or sunset rules to turn an entangled reform into a
near-decomposable program. That proposal remains a design candidate until A
grounds the new interfaces, coupling reduction, and residual risks.

### D2.7 Coverage Measurement

D2 should replace raw capability counts with denominator-aware metrics:

- **construct demand coverage**: demanded constructs with any resolver result
  better than `blocked_construct_not_observed`;
- **facet-space coverage**: demanded facet expressions covered by existing
  primitives and composition rules, regardless of whether a named construct
  shortcut exists;
- **authority-weighted coverage**: demanded constructs with a binding meeting the
  requested authority posture;
- **proxy-limited coverage**: demanded constructs served only by proxy,
  simulation, context-only, or scholar-only bindings;
- **gap mix**: construct-not-observed, acquisition-required, rights, freshness,
  authority, time-role, sample-size, and construct-validity gaps;
- **domain/posture coverage**: coverage by domain and authority level, not only
  aggregate;
- **scale/posture coverage**: leaf, program, portfolio, national, and
  transnational demands stratified by authority posture and evidence tier;
- **compositional coverage**: recursive design graphs whose typed interfaces,
  dependencies, critical path, and emergent-risk obligations can be represented;
- **epistemic-regime coverage**: demanded claims classified by regime with
  regime-appropriate evidence/design strategy available;
- **coupling coverage**: decomposition boundaries with coupling classification,
  grounded interface terms, and residual interaction status;
- **axis-firewall coverage**: which axis positions have passing, limited,
  contested, missing, or out-of-envelope firewall status;
- **computational tractability**: whether the search/composition/model path is
  exact, approximate, memoized, incremental, anytime-bounded, or infeasible;
- **knowledge-governance throughput**: fraction of new facet/source/method
  growth that can be proposed, validated, and governed without one-off human
  authoring per construct;
- **revalidation decay**: bindings that fall out of coverage because of TTL,
  rule change, data freshness, rights, or construct-validity downgrade.

The current `~1261 capabilities` number is therefore not a success metric by
itself. It becomes useful only when divided by demanded facet-space regions,
construct expressions, and authority postures.

For an effectively infinite policy space, "coverage of all policies" is not a
well-formed denominator. D2 should instead report **compositional correctness**
and **bounded honest abstention** by certified operation envelope: for each
domain x jurisdiction x scale x epistemic-regime x coupling x capacity x
reversibility/stakes x posture slice, what fraction of expressible demands
ground, change strategy, publish with limitation, or abstain honestly, and is
the abstention rate falling as acquisition closes gaps?

### D2.8 Acquisition Loop Closure

The existing typed planner is a strong seed; the missing piece is execution and
rerun closure. Automated source discovery/retrieval through the existing Fabric
connector registry is mandatory for scale; human tasks are the fallback for
credentialed, legally sensitive, institution-owned, or semantically ambiguous
sources. D2 should define acquisition states:

```text
gap_detected
  -> eligibility_checked
  -> ranked_by_voi
  -> connector_discovery_started | human_task_opened
  -> source_candidate_found | human_source_nominated
  -> source_acquired
  -> source_contract_validated
  -> capability_index_updated
  -> rerun_started
  -> rerun_consumed_delta
  -> closed_as_binding | closed_as_limitation | closed_as_still_blocked
```

Eligibility precedes ranking. Non-overridable gates cannot be routed around by
VOI. Weak proxies may produce `selected_proxy_with_limitation` only where the
authority posture permits it; production remains strict unless a separate ADR
changes the authority policy.

The automated branch must reuse connector-registry surfaces such as CKAN,
Socrata, OpenDataSoft, SPARQL endpoints, REST/JSON, SDMX, and catalog
connectors where available. Discovery candidates remain candidates until source
contracts pass lineage, quality, rights, freshness, time-role, and construct
validity checks.

Rule-versioned replay is a hard invariant: acquisition deltas may improve an
open case or a deliberate reissue, but they must not silently re-ground closed
PDCs. Closed cases replay under frozen capability-index refs, construct/facet
registry refs, rule refs, and source-contract refs unless a reissue is
explicitly created.

Status composition is also load-bearing. D2 must define how acquisition states
compose with existing support, publishability, admissibility, validity,
freshness, faithfulness, readiness, review, and closeout states. New acquisition
states are local lifecycle states, not new top-level closure statuses, unless
the status lattice composition is explicitly updated and tested.

### D2.9 Authority Derivation For Sources

Authority metadata cannot appear by decree. A source contract's trust tier,
rights envelope, legal-use scope, freshness, construct-validity status, and
method compatibility must be derived through an auditable procedure:

```text
connector/profile metadata
  + source documentation
  + schema/lineage/quality probes
  + rights/legal-use review
  + construct-validity checks
  + reviewer or governed ratification where required
  -> authority derivation record
```

Heuristics may propose authority fields, but governed/production authority
requires provenance and, where required, ratification. This prevents P05/P10
drift where a high trust tier is hand-assigned without evidence.

### D2.10 First Acquisition Slice

The first slice should stay narrow and real: Ukrainian MSME credit constructs
already implicated by the Wave 12 failure mode.

| Construct | Needed source contract | Minimum authority metadata |
| --- | --- | --- |
| `credit_program_enrollment` | Program registry / bank participation / NBU or ministry source, with firm-level or aggregate eligibility keys. | legal-use scope, coverage period, update cadence, linkage key quality, construct validity review. |
| `firm_survival` | Tax, registry, payroll, or business-status panel; proxy acceptable only for research/governed with limitation. | observation time, exit definition, right-censoring policy, lineage, sample coverage. |
| `regional_displacement_pressure` | IDP/administrative displacement series, regional population denominator, or validated proxy. | geography role, freshness, wartime reliability caveat, source rights. |
| `credit_access` | Loan application/approval/terms data or validated credit-market proxy. | construct validity, borrower population, adverse-selection caveat, legal-use constraints. |
| `fiscal_burden_per_beneficiary` | Program budget outlay + beneficiary denominator. | public finance lineage, time window, double-counting controls. |

This slice should prove the loop, not universal breadth: blockers become tasks,
tasks become source contracts, source contracts become capability-index entries,
and W12.D real-producer results move from hard typed blockers to pass or
publish-with-limitation where expert labels support it.

### D2.11 D2 Acceptance Signals

D2 architecture is ready for implementation planning when it names:

- facet primitive schema, construct expression schema, demand denominator schema,
  and owner;
- construct/facet governance lifecycle and merge/split rules;
- axis-position declaration schema, per-axis firewall status schema, and
  envelope membership test;
- cluster ownership map schema, governed path, inventory registration, and
  validator:
  `architecture/policy_design_case/cluster_ownership_map.toml`,
  `architecture/policy_design_case/inventory.json`, and
  `tools/quality/validation/check_policy_design_case_cluster_ownership_map.py`;
- cluster interface contracts for SYSTEM, KNOWLEDGE, ACTOR, INTERVENTION, OTHER
  AGENTS, and DESIGNER ITSELF, with producer/consumer refs;
- cluster authority dimension records extending ADR-0174 C3 and closeout
  composition rules;
- epistemic-regime classifier contract, regime evidence rules, per-claim
  composition rules, and P16 overconfidence/precaution firewalls;
- coupling graph, coupling-regime classifier, decomposition result, residual
  interaction ledger, and P17 decomposition firewall;
- recursive design graph schema, sub-design interface schema, dependency edge
  taxonomy, and critical-path calculus;
- cross-level authority composition rules: critical path, scoped limitations,
  emergent-risk obligations, and projection requirements;
- system-dynamics/equilibrium evidence tiers and the requirement trigger for
  non-additive composite designs;
- certified operation envelope and bounded honest-abstention metrics by domain,
  jurisdiction, scale, epistemic regime, coupling, capacity,
  reversibility/stakes, and posture;
- computational tractability budget for search/composition/model execution,
  including incremental re-grounding, memoization, and anytime behavior;
- knowledge-governance throughput ledger so ontology/source/envelope growth does
  not become bespoke linear human work;
- coverage snapshot schema and metrics;
- acquisition execution boundary, including automated connector discovery as the
  default scalable branch and human fallback criteria;
- source contract minimum fields for authority, lineage, quality, rights,
  freshness, time roles, and construct validity;
- authority derivation record and ratification policy;
- capability-index delta and rerun closure receipt;
- replay invariant for closed cases;
- status lattice composition rules and mixed-status tests;
- first Ukrainian MSME acquisition slice with owners, TTLs, legal-use review,
  and rerun command evidence expectations.

## D3 — Generative Design Architecture Draft (B, Shadow-First)

**Decision shape:** B is not "let the LLM write a better memo." B is a
structured design-space loop whose candidates are generated, grounded,
predicted, compared, and then either recommended with limitations or blocked.
Until A holds on real cases, every B output is shadow/advisory and may not
satisfy authority slots.

The central safety law for B-on-A is:

> The more universal and emergent B becomes, the more complete A must be.

If the admissibility/authority spec in A is incomplete, an exploratory
generator will eventually discover designs that pass A while violating an
unmodeled legal, fiscal, participation, rights, delivery, or system-dynamics
constraint. That is spec-gaming/reward-hacking in policy form. Therefore D3
promotion depends not only on A soundness ("bad evidence is blocked") but on
A-completeness within the certified operation envelope ("the important ways a
design can be bad are actually represented").

The concrete version of A-completeness is per-axis: the honesty surface equals
the product of the axis firewalls. B may become more expressive only where A can
classify regime, coupling, capacity, measurability, reversibility/stakes,
strategic response, lowering, and authority boundaries well enough to prevent
laundering on those axes.

D3 also needs a **narrow-waist invariant**:

- the universal core may contain facet algebra, design-composition algebra,
  status/authority/time/provenance algebra, evidence/replay semantics, and
  projection boundaries;
- the universal core must not contain domain templates, jurisdiction-specific
  legal rules, source-family strings, instrument-specific heuristics, or
  domain-specific welfare weights;
- domains, jurisdictions, instruments, and scales enter as dialects/lowerings
  around the core, not as shortcuts inside it.

The D3 artifact should become a **generative-design ADR** with these
commitments.

### D3.1 Design Grammar And Candidate Contract

D3 must define a first-class design grammar before it defines the LLM role. The
grammar is the producer of the candidate space; the LLM operates inside it. At
minimum it needs:

| Grammar layer | Required content |
| --- | --- |
| Instrument taxonomy | Cash/transfer, credit/guarantee, tax, regulation, service delivery, public investment, information, procurement, insurance, institutional reform, enforcement, and hybrid instruments. |
| Parameter space | Eligibility, targeting, benefit formula, intensity, duration, frequency, geographic scope, delivery channel, funding source, compliance burden, monitoring cadence, appeal path. |
| Feasibility constraints | Legal competence, fiscal envelope, delivery capacity, data availability, administrative burden, political/participation constraints, rights/privacy limits. |
| Lifecycle/lowering rules | Greenfield/reform/transition/termination/grandfathering posture; intent -> instrument -> legal text -> procedure -> budget -> monitoring lowering checks. |
| Composition rules | Which instruments can combine, substitute, dominate, or conflict; what baselines/alternatives must exist. |
| Search/diversification strategy | Enumerate instrument families first, then sample or optimize parameters under constraints; require diversity across instruments, target rules, delivery paths, and tradeoff profiles. |
| Pruning rules | Remove legally impossible, fiscally impossible, data-impossible, dominated, duplicate, or authority-laundering candidates before ranking. |

The allowed B strategies are therefore:

- deterministic enumeration of instrument families plus parameter sampling under
  constraints;
- constraint-guided generation where the LLM proposes fills but the grammar
  validates and canonicalizes them;
- search/optimization over typed parameter ranges after the grammar has
  produced a valid candidate family.

The disallowed strategy is "LLM writes a policy and we coerce it into fields."
That path recreates the narrative drafter failure under a typed wrapper.

A `DesignCandidate` should be first-class, separate from `DraftResult` and from
the PDC graph. It should also be recursive: a candidate may be a leaf design or
a composite `PolicyProgram` / `PolicyPortfolio` whose children are themselves
design candidates. It should include:

- problem/objective refs and authority profile;
- axis-position declaration and inherited/case-specific firewall statuses;
- scale class (`leaf`, `program`, `portfolio`, `national_transformation`,
  `transnational_integration`) and parent/child design refs where composite;
- epistemic-regime refs per major claim and coupling-regime refs per
  composition boundary;
- lifecycle stage, lowering level, state-capacity assumptions,
  reversibility/commitment posture, stakes band, measurability status, and
  strategic-response assumptions;
- instrument type, delivery channel, funding channel, legal path, implementing
  institution, and appeal/contestability path;
- targeting rule, eligibility rule, benefit/service formula, intensity,
  duration, phase-in/phase-out, geographic scope, population scope, and time
  horizon;
- operational dependencies, typed sub-design interfaces, sequencing constraints,
  monitoring plan, failure modes, affected-person participation needs, legal
  constraints, data requirements, method needs, and system-dynamics triggers;
- baseline and named alternatives;
- source classification for every field: deterministic grammar, LLM candidate,
  human reviewer, corpus exemplar, historical prior, simulation proposal, or
  producer-derived constraint.

`DraftResult` can remain a narrative artifact, but it must not be the design
space. The design space needs typed parameters and comparison axes.

### D3.2 Design Search Control Plane

The previous D3.2 shape was a pipeline: frame -> grammar -> LLM -> compile ->
resolve -> predict -> rank -> ground. That is not enough. In that shape A is a
terminal filter, so B can only propose and then be judged. A universal designer
needs A to play two roles:

- **Constraint store before generation.** Cluster producers publish constraints
  into the candidate space before B proposes: regime determines strategy,
  coupling determines decomposability, capacity removes impossible
  instruments, Lex constrains legal paths, measurability constrains claims, and
  strategic-response records flag obvious Goodhart/Lucas traps.
- **Counterexample oracle after generation.** A failures become typed
  counterexamples rather than dead-end blockers. A failed candidate should
  return which firewall or floor failed, why, which axis was affected, and what
  repair moves are legitimate: refine, acquire, reframe, decompose, change
  strategy, request human/governance input, or abstain.

This makes B a **counterexample- and acquisition-guided design search**, not a
one-pass generator. CEGIS/CEGAR is the nearest algorithmic family, but the
policy version differs from pure program synthesis: verification is incomplete,
objectives are multi-principal, evidence can be missing, and some failures must
route to acquisition or governance instead of local refinement.

The runtime shape is a blackboard-style control plane over the cluster map:

```text
Cluster producers (SYSTEM / KNOWLEDGE / ACTOR / INTERVENTION / OTHER_AGENTS)
  -> write constraints and evidence into ConstraintStoreSnapshot
  -> B proposes DesignSketch / DesignCandidate inside the constrained grammar
  -> A verifies candidate across cluster firewalls
  -> if admissible: update ParetoArchive / shadow frontier
  -> if failed: emit CounterexampleRecord
  -> RefinementPolicy chooses next move under VOI, budget, urgency, stakes
  -> SearchLedger records every write, verifier result, and control decision
  -> loop until frontier stability, budget exhaustion, abstention, or approval
```

The cluster ownership map is therefore not only documentation. Its cells are
the control-plane knowledge sources, and its `publishes` / `consumes` edges are
the read/write contracts for the blackboard workspace. This reuses the governed
map instead of inventing a parallel B architecture.

First-class D3 search artifacts:

| Artifact | Purpose | Authority boundary |
| --- | --- | --- |
| `ConstraintStoreSnapshot` | Frozen per-iteration cluster constraints: hard, soft, uncertainty, and unknown. | Search input only; cannot satisfy producer authority by itself. |
| `DesignSketch` | Coarse candidate used for cheap exploration and portfolio-scale search before full lowering. | Shadow-only design hypothesis. |
| `DesignCandidate` | Typed leaf or recursive design graph with parameters, source classification, axis positions, and firewall refs. | Candidate design, not recommendation authority. |
| `CounterexampleRecord` | Design-time specialization of `TypedDiagnosticRecord`: failed axis/firewall, failed assumption, evidence, repair moves, and class. | Verifier feedback; may trigger refinement, acquisition, governance, or abstention. |
| `ValueOfInformationEstimate` | Shared VOI score for the next move: expected design/envelope uncertainty reduction per typed budget unit. | Scheduling/governance input only; cannot override authority floors. |
| `RefinementDecision` | Control-plane choice among valid next moves with VOI, budget, stakes, and human-attention rationale. | Scheduling/route authority only; not domain evidence. |
| `SearchLedger` | Replayable trace of constraints, candidates, counterexamples, decisions, budgets, and frontier movement. | Reproducibility and audit surface; cannot launder search into evidence. |
| `ParetoArchive` | Shadow frontier of non-dominated candidates under authorized or scenario value schedules. | Recommendation support only after A and value-choice provenance pass. |

`CounterexampleRecord` must classify failures, because not every failure should
teach B the same lesson:

| Class | Meaning | Allowed next move |
| --- | --- | --- |
| `real_design_blocker` | Candidate violates a hard legal, rights, capacity, coupling, or evidence floor. | Refine or abstain; do not merely retry. |
| `substrate_gap` | Candidate may be valid, but construct/source/method evidence is missing. | Run D2 acquisition or produce limitation/abstention. |
| `a_spec_gap` | Candidate exposes an incomplete verifier/admissibility spec. | Human/governance-owned A repair; B may not learn to route around it. |
| `abstraction_gap` | Current sketch/lowering/coupling abstraction is too coarse. | Refine lowering, decompose differently, or route to system dynamics. |
| `value_gap` | Objective, social weight, mandate, or legitimacy input is missing or contested. | Human/governance decision request; no scalar ranking. |
| `budget_gap` | The next useful step exceeds compute, acquisition, expert-time, or urgency budget. | Anytime output with honest search incompleteness. |

`a_spec_gap` is deliberately not owned by B or by an automatic planner. Declaring
that A is incomplete is a governance act; otherwise the loop could learn to
label hard failures as verifier defects and game the backbone.

Constraints also need types. Hard constraints can prune. Soft constraints rank
or trigger warnings. Uncertainty constraints change the design strategy.
Unknowns must not silently prune important values; they become limitations,
acquisition requests, or ignorance declarations. This prevents A from becoming
a creativity-killing filter and prevents B from learning streetlight bias.

The search itself is nested and follows **ascending-cost frontier expansion**:
try the cheapest reversible refinement that preserves authority first, then
spend acquisition money, expert time, legal access, or human attention only
when `ValueOfInformationEstimate` justifies the cost under the delegation
budget.

1. **Outer search loop:** candidate -> A verification -> counterexample ->
   refinement decision.
2. **Design/evidence loop:** `substrate_gap` counterexamples decide between
   redesign and D2 acquisition using VOI, legal-use, cost, and urgency.
3. **Sketch/refine loop:** large or composite policies start as sketches, then
   lower promising branches. Coupling decides whether sub-designs can be refined
   independently or must be co-refined.

The LLM may propose, diversify, explain, and generate hypotheses inside the
grammar. It may not certify legal authority, data validity, participation
representativeness, method validity, epistemic regime, coupling, state capacity,
measurability, value weights, refinement validity, `a_spec_gap`, or closeout.

Regime changes search strategy:

- **Risk:** optimize expected welfare subject to legal/data/method constraints.
- **Uncertainty:** search for robust, satisficing, minimax-regret, or
  scenario-stable designs and expose fragility.
- **Ambiguity:** generate frame-indexed portfolios and surface
  incommensurability rather than a single hidden scalar optimum.
- **Ignorance:** generate reversible, option-preserving, safe-to-fail,
  monitored pathways with triggers and no outcome claim.

Coupling changes search structure:

- modular systems allow parallel leaf/module search;
- near-decomposable systems require interface-aware coordination;
- hierarchical systems require topological lowering and propagated constraints;
- entangled systems require holistic/system-dynamics strategies or
  modularization moves such as ring-fencing, pilots, severability, phasing,
  buffers, and sunset rules.

Design generation is also abductive. Given target outcomes and a causal graph,
the system searches for interventions that plausibly move mechanisms. But a
causal graph alone is not enough: the designer needs an **intervention
affordance view** that joins instrument grammar, causal mechanisms, legal paths,
capacity constraints, and construct coverage:

```text
instrument -> mechanism -> construct -> outcome
       joined with Lex legal path
       joined with ACTOR capacity
       joined with SYSTEM/KNOWLEDGE coverage and regime
```

This should be a materialized view over existing clusters, not a new orphan KG.

The control plane must remain replayable. Blackboard-style opportunism is useful
for search but dangerous for PolicyOS unless every cluster write, verifier
result, refinement decision, budget cutoff, and frontier update is recorded in
`SearchLedger`. A closed case must be reproducible against frozen constraints,
rules, and cluster artifact refs.

MVP staging rule: do not build the full control plane before one loop flows.
The minimum viable B loop is:

```text
ConstraintStoreSnapshot
  + DesignCandidate
  + CounterexampleRecord with the six classes above
  + simple RefinementPolicy
  + replayable SearchLedger
```

One of the 13 corpus cases should prove:

```text
typed blocker
  -> CounterexampleRecord
  -> valid RefinementDecision
  -> next iteration or acquisition plan or honest abstention
```

`DesignSketch`, full Pareto archive, multi-fidelity scheduling, DAPP operators,
post-deploy MAPE-K, and rich affordance views are elaborations after the first
loop closes.

### D3.3 Operating Model: Delegation Layer

"Autonomous vs co-pilot" is the wrong global axis for public policy. The right
model is **delegation**. The system is never the principal. It borrows limited
authority from accountable humans and institutions, and it must verify that
the human actor is inside their own mandate.

Autonomy is therefore computed per decision class:

```text
autonomous action allowed =
  system is capable              # CertifiedDesignEnvelope
  AND principal permitted it      # DelegationContract
  AND decision is within bounds   # regime, stakes, reversibility, mandate
```

Outside that intersection, the system pauses and emits a typed
`HumanDecisionRequest`. This prevents both failure modes:

- **black-box oracle:** human rubber-stamps a final answer without seeing the
  real choices, limits, or dissenting evidence;
- **firehose:** every search step becomes a manual decision and the system
  becomes unusable.

Delegation artifacts:

| Artifact | Purpose |
| --- | --- |
| `DelegationContract` | Session or program-level boundary: autonomous decision classes, approval-required decisions, compute/acquisition/human-attention budgets, maximum stakes/reversibility posture, value-policy, and override policy. |
| `GovernanceDecisionClass` | Controlled registry inside the delegation contract for decisions that are autonomous, principal-owned, governance-owned, or non-overridable. |
| `HumanDecisionRequest` | Typed interruption with decision options, recommendation, provenance, disconfirming evidence, value/stakes impact, and what changes under each choice. |
| `HumanDecisionRecord` | Attributed, timestamped, mandate-checked response persisted into `SearchLedger`, closeout, and projection. |

`GovernanceDecisionClass` is the single place to register decisions such as
value authorization, less-cautious regime override, `a_spec_gap`, decomposition
override, acquisition approval, envelope shrink/expansion, shadow-to-authority
promotion, final selection, and post-deploy reissue. Local components may
propose one of these decisions, but they should not create separate governance
enums. Otherwise P04 status proliferation and P26 responsibility laundering
will reappear under a friendlier name.

Typed human entry points:

| Entry point | Loop location | Human act | Authority rule |
| --- | --- | --- | --- |
| Problem framing | Intake / before constraints | Approve or revise frame. | Wicked or contested framing belongs to the principal. |
| Mandate | Before value choice | Confirm who may set objectives/weights. | Gated by `ACTOR.mandate_legitimacy`; the system also checks the principal. |
| Value weights | Before frontier ranking | Authorize objectives or value schedule. | Normative firewall; no hidden scalar. |
| Regime override | A classification | Override with provenance. | More caution can be accepted; less caution needs governance and evidence. |
| `a_spec_gap` | Counterexample classification | Admit verifier incompleteness and assign A repair. | Governance-owned; never B-owned. |
| Acquisition | Refinement decision | Approve cost, legal use, source access, TTL. | Human approval when budget/legal-use/stakes require it. |
| Decomposition | Coupling branch | Accept boundary or entanglement treatment. | Human may accept limitation; cannot mint decomposition evidence. |
| Final selection | After search/frontier | Choose from Pareto frontier. | System presents; accountable human selects. |
| Shadow -> authority promotion | Release/governance | Ratify promotion. | Governance act, not session-level convenience. |
| Override A verdict | Any stage | Override-with-provenance where allowed. | Hard legal/rights firewalls are non-overridable or require exceptional governance. |

Human attention is a budget controlled by `RefinementPolicy`. The surface should
be pull-first and decision-shaped: show the open decisions owned by the human,
ranked by VOI, stakes, urgency, and attention cost. Do not stream the whole
`SearchLedger` by default.

The operating model needs its own firewall: **responsibility-integrity**. The
system may not launder responsibility to a human who could not understand the
decision, and the human may not launder responsibility back to "the AI said so."
An approval counts only if the request showed material limitations,
disconfirming evidence, value/stakes implications, and required an active
choice for high-stakes or value-laden decisions.

**Interaction mode per decision class.** Autonomy is not one global toggle; each
decision class also carries an interaction mode, and the default for value-laden,
high-stakes, or out-of-envelope decisions is **not** AI-first:

| Mode | When |
| --- | --- |
| AI-first | low-stakes, in-envelope, reversible, high confidence. |
| AI-follow | high-stakes: the human forms a preliminary judgment, then sees the system's analysis; mitigates automation bias and the out-of-the-loop problem. |
| request-driven | the expert/principal pulls system support, preserving situation awareness. |
| delegated autonomous | only inside `capable ∩ permitted ∩ within-bounds` and where the `DecisionRightsMatrix` allows it. |

At cold-start most cases are out-of-envelope, so modes skew to
AI-follow/request-driven and shift toward AI-first only as the envelope grows
(consistent with the D3.10 override-rate thermometer).

A `DecisionRightsMatrix` maps each `GovernanceDecisionClass` to the role
authorized to make it — principal, legal approver, budget owner, data steward,
affected-party representative, domain expert, or governance board — so "a human
approved" cannot be satisfied by the wrong human. A `HumanDecisionRequest` is
then valid only as a **five-rights object**: right decision, right person (per
the matrix), right information (limitations + disconfirming evidence), right
format/channel (audience projection), and right time; missing any one
invalidates the resulting `HumanDecisionRecord`. P26 gains an `oversight_theater`
subtype: a procedural approval that lacks causal power, epistemic access,
mandate, competence, attention budget, or active choice is not valid oversight.

This is P03 at the system level: the external surface is not a memo; it is the
operational decision interface through which delegation, accountability, and
typed human judgment enter the design loop.

### D3.4 Normative Firewall

Policy design is not only empirical. The system must not choose social values,
objective weights, affected-group priorities, rights tradeoffs, or distributional
weights on its own. These are governance inputs, not model outputs.

The normative firewall is parallel to the LLM firewall:

- the system may expose tradeoffs, Pareto frontiers, affected groups, dissent,
  distributional consequences, and value-choice sensitivity;
- the system may ask for missing value weights or present scenarios under
  alternative value schedules;
- the system may not invent authoritative value weights, legitimacy judgments,
  or social priorities;
- LLM/historical/corpus-derived value candidates remain `candidate_unverified`
  or `shadow_scenario` until authorized human/governance input admits them;
- every recommendation must cite the value-choice provenance that makes the
  ranking legitimate.

For large multi-principal policies, the firewall is stronger. The Arrow/social
choice caveat applies: there is no universal aggregation rule that legitimately
turns millions of affected people, ministries, regions, firms, and rights claims
into a single "best" ranking without normative assumptions. The system may
expose incompatible objectives, Pareto frontiers, blocking rights, dissent, and
sensitivity to alternative value schedules. It may not resolve those
incompatibilities as if they were empirical facts. A national or transnational
recommendation must therefore cite an authorized governance input for value
weights and must project unresolved normative conflict as contested, not solved.

### D3.5 Epistemic, Prediction, And Recommendation Boundary

Epistemic regime and forecast origin are orthogonal. Regime says what the world
currently lets us know; forecast tier says where a particular prediction came
from. A `validated_local_model` can still sit inside ambiguity if model frames
are contested, and `simulation_only` can be useful in ignorance if it is
projected as exploration rather than evidence.

Outcome prediction needs its own authority envelope. The unified
`ForecastSupport` dictionary has two parts:

- **Base origin:** `simulation_only`, `transported_scholar_estimate`,
  `validated_local_model`, `historical_prior`, or `equilibrium_contested`.
- **Claim scope:** `leaf_only`, `system_effect`, `context_only`, or
  `routing_only`.

Base semantics:

| Base origin | Meaning |
| --- | --- |
| `simulation_only` | Useful for exploration, not claim evidence. |
| `transported_scholar_estimate` | Governed/research support with limitations. |
| `validated_local_model` | Possible governed/production support if source contracts, method validity, and calibration pass. |
| `historical_prior` | Routing/review influence only, never current-run evidence. |
| `equilibrium_contested` | Multiple plausible equilibria, unstable feedback, or strategic response prevents a single authoritative forecast. |

D2.6 system-dynamics labels are specializations of this same dictionary, not a
second ladder. For example, `simulation_only_system_effect` means
`simulation_only + claim_scope=system_effect`, while
`validated_local_dynamic_model` means `validated_local_model +
claim_scope=system_effect` plus dynamic/equilibrium validation. `historical_prior`
may influence routing or review, but it remains outside current-run evidence at
both leaf and system levels.

A recommendation inherits the weakest required boundary among legal, data,
method, participation, epistemic regime, coupling, prediction,
welfare/value-choice provenance, state capacity, reversibility/stakes, and
strategic-response assumptions. Scalar ranking cannot hide Pareto tradeoffs,
multi-principal conflict, system-dynamics uncertainty, or social-weight
provenance.

### D3.6 Multi-Audience Projection And Balanced Memory

Shadow/advisory status must be visible to every consumer. D3 adds new public
surface risk unless `DesignCandidate`, axis-position declaration, per-axis
firewall status, epistemic regime, coupling classification, forecast, frontier,
recommendation, and value-choice records project separately to PUBLIC,
REVIEWER, EXPERT, and MACHINE audiences with the same authority boundary.
PUBLIC views should never make a shadow recommendation look like an approved
policy decision, and should never hide an out-of-envelope, ignorance, entangled,
or high-stakes limitation behind a polished design narrative.

Projection should also be organized by cluster, not only by artifact type:

- SYSTEM: construct coverage, measurability gaps, coupling validity,
  nonstationarity, and aggregation risk.
- KNOWLEDGE: epistemic regime, model contestability, source/evidence coverage,
  and regime-appropriate design strategy.
- ACTOR: legal authority, capacity feasibility, mandate/legitimacy, and
  participation/value-choice provenance.
- INTERVENTION: design graph, lowering level, lifecycle/reform status,
  reversibility/stakes, and critical path.
- OTHER AGENTS: strategic/behavioral response model, Goodhart/Lucas limitations,
  adversarial/capture risk, and reflexive update to SYSTEM.
- DESIGNER ITSELF: tractability budget, search completeness, envelope boundary,
  knowledge-governance throughput, and capability-ratchet state.

Balanced design memory is allowed, but only as influence:

- successful grounded design patterns can inform candidate generation and search
  priors;
- failure lessons can inform pruning and adversarial checks;
- memory cannot satisfy current-run evidence, legality, participation,
  prediction, or value-choice authority;
- memory influence must carry scope, TTL, source case refs, and contamination
  controls.

This closes the P11 gap for a designer: it should learn from designs that
worked, not only from blockers and failures.

### D3.7 Status Composition

D3 introduces statuses such as `shadow`, `advisory`, forecast tiers,
recommendation posture, pruning states, counterexample classes, refinement
decisions, search incompleteness, delegation status, human-decision status,
epistemic-regime statuses, coupling-regime statuses, scale-composition
statuses, system dynamics tiers, capacity/feasibility statuses,
reversibility/stakes statuses, ODD boundary status, and promotion states. These
must compose with the existing status lattice rather than become a parallel
closure system. The generative-design ADR must define mixed-outcome rules for:

- shadow recommendation + production blocker;
- admissible design candidate + unratified value weights;
- useful forecast + low construct coverage;
- proxy-limited data + governed publication;
- successful design memory + stale source authority;
- expert-dominant design + method validity blocker;
- composite portfolio + one non-critical sub-design limitation;
- validated leaf effects + contested system-level equilibrium;
- inside domain envelope + outside scale envelope;
- risk-regime claim + missing risk-regime evidence;
- uncertainty-regime design + available but ignored risk-regime evidence;
- modular decomposition claim + entangled coupling classification;
- high-stakes irreversible design + ignorance regime.
- substrate gap + valid acquisition path + budget exhaustion;
- `a_spec_gap` + candidate that appears high-performing;
- human approval outside mandate;
- delegated autonomy inside envelope but value weights missing;
- search frontier stable but unexplored high-VOI branch remains.

No D3 status may imply publishability unless closeout, authority, value-choice,
and projection statuses all compose to a publishable state.

### D3.8 Promotion Gate

B can be built and evaluated in shadow immediately, but promotion requires:

- D2 substrate coverage above the declared floor for the target domain/posture;
- axis-position declaration and per-axis firewalls pass inside the declared
  envelope;
- computational tractability budget is explicit for the requested scale, with
  approximation/anytime limits projected instead of hidden;
- epistemic-regime classification accuracy and coupling-classification accuracy
  above posture-specific floors, with false-risk and false-modular errors
  penalized heavily;
- graded outcome correctness above floor on the redesign corpus;
- design recall@k above floor against expert candidate sets;
- grammar validity and diversity coverage above floor, so candidates are not
  all LLM variants of the same instrument;
- search-control-plane validation: each failed candidate produces a typed
  `CounterexampleRecord`, each counterexample receives a valid
  `RefinementDecision`, and `SearchLedger` replay reproduces the same frontier
  and abstention/acquisition decisions;
- `a_spec_gap` governance: verifier-spec defects route to governance-owned A
  repair, not to B-side retry or automatic override;
- delegation validation: every value-laden, high-stakes, out-of-envelope,
  acquisition-budget, final-selection, and verifier-spec decision routes to a
  mandate-checked `HumanDecisionRequest` / `HumanDecisionRecord`;
- prediction calibration on observable cases or explicit uncertainty limitation;
- design-time dominance/regret below governed threshold on expert-adjudicated
  cases, and realized-regret only for rare cases where counterfactual evidence
  is credible;
- authorized value-choice provenance for every ranked recommendation;
- A-completeness adversarial probes show that the generator cannot exploit known
  gaps in legal, data, method, participation, fiscal, system-dynamics, or
  projection admissibility specs;
- certified operation envelope is declared and the recommendation remains inside
  its domain x jurisdiction x scale x posture boundary, or it is visibly
  downgraded to advisory/abstained;
- projection tests proving shadow/advisory status is visible to all audiences;
- no P15 laundering: LLM-origin fields remain candidate until producer/readers
  admit them.

### D3.9 Terminal Output: Canonical Design Record And Projection Algebra

The output question is not "decision-support or policy production?" That is a
false fixed-scope choice. A request has two orthogonal parameters:

- **Lowering depth:** `ProblemFrame -> DesignSketch -> DesignCandidate ->
  PolicyProgram -> Legal/Budget/Procedure` and, where authorized, executable
  law/budget/procedure artifacts.
- **Projection aspect:** audience, aspect, depth, redaction, format, and
  revision: public tradeoff brief, expert evidence view, ministry legal diff,
  fiscal package, machine contract, contestability dossier, and so on.

The narrow waist is a replay-frozen **Canonical Design Record**:

```text
recursive design graph
  + claim-bound evidence portfolio
  + Pareto/tradeoff/value-choice records
  + axis-position vector and certified envelope
  + SearchLedger and counterexample/refinement history
  + assurance case
  + limitations/abstentions
  + already-produced lowering artifacts
```

This object is the authority-bearing source. It should contain enough structure
for shallow projections and enough typed state to continue lowering when a
request legitimately asks for deeper artifacts. It should not eagerly generate
all legal, fiscal, procedural, and public variants up front.

The architecture must distinguish **projection** from **lowering**:

| Operation | Meaning | Authority rule |
| --- | --- | --- |
| Projection | Lossy view, formatting, compression, redaction, or audience-specific rendering of content already in the canonical record. | May not add new content or authority; must pass faithfulness against the record. |
| Lowering | Generative deeper design act that creates new content such as legal text, budget line, implementation procedure, or monitoring protocol. | Must re-enter search/verify and can be blocked even when a shallower projection is allowed. |

Depth raises authority requirements. A public tradeoff projection may be
permitted while legal-diff lowering is blocked because legal mandate,
state-capacity, regime, coupling, rights, or budget grounding is insufficient.
The system should answer with the deepest admissible artifact requested, plus a
typed reason for any deeper refusal.

This yields the third algebra:

```text
facet algebra                  # domain / construct breadth
  x design-composition algebra  # scale / structure breadth
  x projection algebra          # output / audience / depth breadth
```

Projection algebra is a grammar over
`audience x aspect x depth x redaction x format`. It prevents hardcoded
artifact lists and keeps "briefing for an activist" and "legal/budget package
for a ministry" as expressions over the same canonical record, not separate
products.

Every projection must pass a **faithfulness verifier**. Public prose is high
risk: it can omit limitations, hide value choices, invert tradeoffs, or make a
shadow candidate look approved without adding any new factual claim. The
structural backbone is authoritative; prose and dashboards are faithful renders
of it, not substitutes for it.

Post-closeout deep lowering is a new design act. If a ministry asks for legal
diffs months after a closed case, the system must either replay against frozen
refs and prove the requested lowering was already in scope, or open a new
review/reissue path. Projection can be cheap; lowering is governed.

### D3.10 Cold-Start And Resource Economics: Reflexive Self-Design

Cold-start and resource economics belong to `DESIGNER_ITSELF`. The universal
designer must apply its own discipline to its own growth:

```text
bootstrap = demand-pulled learning in a tiny certified envelope
resource economics = robust multi-budget portfolio design for growing that envelope
```

The chicken-and-egg loop is real: grounding needs substrate, substrate needs
demand, demand needs design, and design needs grounding. The escape is to seed
**algebra generators**, not products:

- facet primitives and composition operators;
- instrument-modality and design-composition primitives;
- projection primitives;
- A-firewalls for authority, regime, coupling, capacity, mandate, measurability,
  stakes, strategic response, and projection faithfulness.

Do not seed universality with a long list of constructs, templates, or reports.
That is bespoke growth in a safe-looking costume. Constructs, designs, and
outputs should be composed or acquired as demand appears.

D5 must start by freezing a `MinimalSeedManifest`, because "seed algebra
generators" is otherwise too abstract to implement. The manifest should name:

- launch facet primitives and the rules for adding new primitive values;
- launch instrument-modality and design-composition primitives;
- launch projection primitives and the first faithfulness checks;
- the first easy-corner envelope and the real demand it serves;
- required A-firewalls present at bootstrap;
- typed budgets for compute, acquisition, expert time, legal access, and human
  attention;
- held-out cases that the bootstrap process may not see.

The manifest is not a universality proof. Its job is to prevent the first seed
from quietly becoming a bespoke template pack.

Bootstrap is demand-pulled by typed human acts from the delegation layer:

| Human act | Bootstrap signal |
| --- | --- |
| `value_authorization` | Seed for value-choice oracle and normative cases. |
| `regime_override_with_provenance` | Seed for epistemic-regime classifier. |
| `decomposition_override` | Seed for coupling/modularity classifier. |
| `final_selection` | Seed for successful design-pattern memory. |
| `a_spec_gap` governance act | Seed for A-completeness repair. |
| acquisition approval/rejection | Seed for VOI and resource allocation. |

On cold start, the system should begin from the easy corner:

```text
low scale
  x risk regime
  x modular
  x reversible
  x measurable
  x high actor capacity
  x real user demand
```

The "real user demand" qualifier is load-bearing. A harmless toy corner that no
one needs does not bootstrap; it only avoids failure. The first envelope must
be both easy to certify and useful enough to attract decision acts, acquisition
requests, and feedback.

Bootstrap thermometers:

- **Override rate decreases** for regime, coupling, value, decomposition, and
  final-selection decisions, without reducing required questions.
- **Reuse rate rises**: new cases reuse facet/design/projection primitives
  rather than adding case-specific code or one-off constructs.
- **Held-out battery performance improves** without seeing the battery during
  development.

Resource economics is a multi-budget explore/exploit portfolio:

```text
EXPLOIT: answer in-envelope requests now
INVEST: expand or repair the envelope for future requests
budgets: compute, acquisition money, expert time, human attention, legal access
```

Expert/human attention is the binding constraint more often than compute. The
system already has local economies - multi-fidelity computation, acquisition
VOI, and attention-gated interruptions - but it needs a shared
`ValueOfInformationEstimate` and a meta-allocation policy that coordinates them
under the principal's mission and budgets.

The meta-allocation itself is a policy-design problem under deep uncertainty.
It should be robust, adaptive, and governed, not a falsely precise MDP/bandit
optimizer. The principal sets the explore/exploit dial through the
`DelegationContract`; the system presents a Pareto frontier of allocation
policies and their tradeoffs. Typed budgets remain typed: the system may compare
VOI across compute, acquisition money, expert time, legal access, and human
attention, but it may not pretend they are freely interchangeable.

Anti-learning/resource firewalls:

- Do not optimize `useful_design_rate` by lowering floors; optimize calibration,
  honesty, reuse, and validated envelope revision.
- Do not let B capability grow faster than A completeness in the same envelope.
- Do not count bespoke one-off growth as mechanism growth.
- Do not allocate resources to make internal metrics look good while user
  demand or hard-corner evidence is ignored.
- Stop meta-regress at the accountable principal: the system may design
  resource allocation, but the mission, budgets, and value tradeoffs are
  delegated by people/institutions.

## D4 — Evaluation Redesign Draft

The 13-case corpus is valuable, but it mostly measures grounding honesty and
compilation truthfulness. B-on-A needs an evaluation stack that separates
twenty questions:

1. Did the system ask for the right constructs?
2. Could the substrate ground them?
3. Did acquisition close the right gaps?
4. Did it classify epistemic regime correctly and choose the right design
   strategy for that regime?
5. Did it classify connectivity/modularity correctly before composing authority?
6. Did it declare the design's position on the hidden axes and per-axis
   firewalls?
7. Did every relevant cluster have an owner, producer chain, authority
   dimension, firewall, and handshake?
8. Did the generator surface good designs?
9. Did failed candidates produce typed counterexamples and valid refinement
   decisions rather than dead-end blockers?
10. Did the search ledger honestly report explored vs unexplored design space,
    budget cutoffs, and frontier stability?
11. Did recursive design composition preserve interfaces, authority, and
   emergent-risk obligations across scale?
12. Did the operating model ask the right accountable human at the right point,
    without becoming a black-box oracle or a firehose?
13. Did the system abstain honestly outside its certified operation envelope?
14. Were predictions and recommendations calibrated and useful where outcome
   evidence is actually observable?
15. Did post-deploy monitoring update calibration, regime, coupling, response,
    acquisition, and memory without rewriting closed-case authority?
16. Did the generator expose or exploit A-spec gaps, and did governance route
    those gaps to verifier repair rather than recommendation success?
17. Did output requests correctly distinguish faithful projection from deeper
    lowering, and did deeper lowering raise authority requirements?
18. Did bootstrap grow reusable primitives and classifier quality rather than
    bespoke products?
19. Did resource allocation balance exploit/invest under explicit budgets and
    principal-set mission without Goodharting internal metrics?
20. Did the universality claim survive a frozen-system, held-out,
    axis-stratified skeptic battery with per-axis scorecards?

### D4.1 Corpus Tracks

| Track | Purpose | Minimum labels |
| --- | --- | --- |
| Grounding corpus | Preserve W12 honesty and authority-boundary tests. | expected outcome, blockers, limitations, authority posture. |
| Construct-demand corpus | Measure substrate breadth and missed constructs. | demanded constructs, time/geography/population roles, authority floor. |
| Acquisition-loop corpus | Test blocker -> task -> source contract -> re-index -> rerun closure. | expected acquisition strategy, owner, TTL, source-contract fields, closure state. |
| Epistemic-regime corpus | Test risk/uncertainty/ambiguity/ignorance classification and regime-conditional design outputs. | regime label per claim, evidence availability, model contestability, expected design strategy, P16 positive/negative cases. |
| Coupling/modularity corpus | Test decomposition validity and partial-equilibrium refusal. | coupling graph, module boundaries, cross-terms, expected coupling regime, false-modular negative controls. |
| Axis-declaration corpus | Test hidden-axis declarations and per-axis firewalls. | state capacity, measurability, lifecycle, lowering, strategic response, reversibility/stakes, computational tractability, knowledge-governance mode, firewall status. |
| Cluster-ownership corpus | Test the architecture map itself. | package owner, seed files, ratchet state, P01 chain, authority dimension, firewall, publishes/consumes, gap/action. |
| Scale-composition corpus | Test leaf, municipal program, portfolio, national transformation, and transnational integration structures. | sub-design graph, dependency edges, critical path, interface contracts, emergent-risk obligations, expected scoped limitations. |
| Design-quality corpus | Measure B shadow generation. | expert candidate set, unacceptable candidates, design recall@k, diversity, feasibility. |
| Search-control corpus | Test counterexample-guided design search rather than terminal gating. | `ConstraintStoreSnapshot`, candidate, expected counterexample class, valid refinement decision, search budget, frontier delta, replay result. |
| Delegation corpus | Test operational human-in-loop behavior. | delegation contract, decision class, accountable actor, mandate check, expected HumanDecisionRequest, active-choice requirement, responsibility-integrity status. |
| Projection/lowering corpus | Test terminal output algebra and faithful rendering. | canonical Design Record, projection request, lowering request, audience/aspect/depth/redaction/format, expected faithfulness result, expected lowering authority gate. |
| Bootstrap/resource corpus | Test cold-start and self-design economics. | easy-corner demand case, typed human acts, reuse-rate, override-rate, allocation budget, exploit/invest choice, held-out result. |
| System-dynamics/backtest corpus | Measure feedback, equilibrium, dynamic-regime, and system-level claims only where credible historical, simulated, or multi-arm evidence exists. | dynamic assumptions, feedback loops, equilibrium status, baseline, alternatives, realized outcomes where available, uncertainty interval, counterfactual credibility. |
| Post-deploy accountability corpus | Test deployed-policy learning and revalidation. | monitoring signal, drift/error type, update plan, affected claims/designs, replay boundary, memory/calibration update, public accountability record. |
| Prediction/backtest corpus | Measure outcome estimates and realized regret only where credible historical or multi-arm counterfactual evidence exists. | baseline, alternatives, realized outcomes, time horizon, uncertainty interval, counterfactual credibility. |
| Adversarial corpus | Prevent authority, LLM, normative, and verifier-spec laundering. | fake authority, prompt injection, proxy-production leakage, participation speculation, value-weight spoofing, design that games incomplete A-spec. |
| ODD/abstention corpus | Test certified-operation-envelope boundaries and graceful degradation. | domain/jurisdiction/scale/posture envelope, expected advisory/limited/block outcome, abstention reason, projection visibility. |
| Universality battery | Test mechanism-generality and honest-boundary claim under frozen-system conditions. | held-out axis cell, allowed changes, reuse evidence, marginal bespoke cost, envelope membership, skeptic-defeater result. |

### D4.2 Expert Oracle Bootstrap And Breadth Target

The design-quality corpus depends on an expert oracle that does not exist yet.
D4 should bootstrap it in layers rather than pretend a perfect oracle is
available.

| Oracle layer | Use | Limitation |
| --- | --- | --- |
| Historical implemented policies (`weak_gold`) | Seed candidate designs, baselines, observed constraints, and realized outcomes where available. | Implemented policy is not necessarily best design; confounding and political constraints remain. |
| Expert seed panel (`expert_gold_seed`) | Produce candidate sets, unacceptable designs, dominance judgments, and value-choice notes. | Expensive; requires conflict declarations and inter-rater reliability. |
| Literature/Scholar causal claims (`causal_support_seed`) | Supply backtestable outcome estimates and transport evidence. | Narrow subset; often not same context or same instrument. |
| System-generated shadow candidates (`shadow_candidate_pool`) | Stress-test recall, diversity, and pruning. | Cannot define ground truth by itself. |

Minimum breadth for a credible universal-design claim should be named before D5.
The first target should not be "any policy"; it should be a governed breadth
floor such as:

- at least 8-10 domains spanning fiscal, health, housing, education, climate,
  migration/displacement, labor, infrastructure, and digital public service;
- at least 6 jurisdictions or governance contexts, including at least two
  non-OECD or crisis/low-data contexts;
- at least 5 scale classes: leaf intervention, municipal program, multi-agency
  portfolio, national reform package, and transnational/integration program;
- at least 4 epistemic regimes represented, including cases where correct
  output is robust/adaptive/precautionary rather than optimized effect claim;
- at least 4 coupling regimes represented, including entangled cases where
  partial-equilibrium composition must be blocked;
- at least 3 lifecycle stages, including brownfield reform/transition and
  termination/grandfathering;
- at least 3 state-capacity contexts, including low-capacity or crisis contexts;
- at least 3 authority postures: research, governed pilot, production-like;
- at least 3 instrument families per major domain where feasible;
- at least one system-dynamics or feedback-sensitive case per major scale class,
  even when the expected label is simulation-only or contested;
- inter-rater reliability or disagreement taxonomy for expert candidate sets;
- explicit list of excluded domains and why they remain research-only.

Promotion floors should be set by baseline measurement on this corpus, then
ratified as governed config with owner, revision rule, and posture-specific
thresholds. "Above floor" without a floor-setting method is not acceptable for
rollout.

### D4.3 Metrics

Keep the existing safety metrics, but stop treating them as design metrics.

- **Closeout honesty rate**: typed blockers count as honest, not useful.
- **Compilation truthfulness rate**: obligations/claims match annotations.
- **Construct demand recall**: demanded constructs identified by compiler/generator.
- **Authority-weighted substrate coverage**: demanded constructs with admissible
  capability bindings by posture.
- **Axis-declaration accuracy**: declared domain, scale, regime, coupling,
  measurability, capacity, lifecycle, reversibility/stakes, strategic-response,
  lowering, computational tractability, knowledge-governance mode, and authority
  positions match expert/evidence labels.
- **Cluster ownership completeness**: every cluster x axis cell has owner or
  explicit orphan status, ratchet state, P01 chain result, authority dimension,
  firewall, publishes/consumes, and action.
- **Cluster handshake coverage**: required cluster publish/consume edges exist
  before downstream design stages consume the signal.
- **Cluster authority-dimension coverage**: every cluster authority dimension is
  either consumed by closeout/projection or explicitly advisory/out-of-scope.
- **Epistemic-regime classification accuracy**: per-claim risk/uncertainty/
  ambiguity/ignorance labels match expert/evidence labels, with false-risk more
  costly than false-ignorance and false-precaution treated as P16.
- **Regime-conditional strategy correctness**: risk cases optimize; uncertainty
  cases produce robust/satisficing designs; ambiguity cases expose frame-indexed
  portfolios; ignorance cases produce adaptive/precautionary pathways without
  outcome claims.
- **Coupling-classification accuracy**: modular, near-decomposable,
  hierarchically-coupled, and entangled boundaries are identified, with
  false-modular errors weighted more heavily than false-entangled caution.
- **Interaction-residual coverage**: near-decomposable cross-terms are measured,
  limited, or acquired instead of ignored.
- **Compositional correctness**: recursive design graph remains well-typed under
  decomposition/regrouping, with preserved interfaces, dependencies, time roles,
  authority refs, and projection obligations.
- **System-dynamics obligation recall**: non-additive composite designs trigger
  the right feedback/equilibrium/dynamic-regime requirements.
- **Bounded honest abstention**: abstention/limitation/block rates by certified
  domain x jurisdiction x scale x epistemic-regime x coupling x capacity x
  reversibility/stakes x posture, with trend over acquisition rounds.
- **ODD boundary correctness**: out-of-envelope cases are visibly downgraded or
  abstained, not over-presented as universal competence.
- **Acquisition closure rate**: acquisition-required gaps closed after rerun.
- **Graded-outcome correctness**: pass/limitation/blocker matches expert label.
- **Design recall@k**: expert-admissible design appears in top-k candidates.
- **Design diversity adequacy**: candidates cover distinct instruments, target
  rules, delivery mechanisms, and tradeoff profiles.
- **Counterexample conversion rate**: failed candidates produce typed
  `CounterexampleRecord` entries instead of terminal unclassified blockers.
- **Typed diagnostic adequacy**: design-time counterexamples, post-deploy
  divergences, regime/coupling misclassifications, and spec-gaming findings use
  the shared `TypedDiagnosticRecord` fields rather than bespoke local payloads.
- **Refinement-decision validity**: each counterexample gets a legitimate
  `refine`, `acquire`, `reframe`, `decompose`, `human_decision`, or `abstain`
  decision with VOI/budget/stakes rationale.
- **VOI calibration**: high-VOI refinement, acquisition, human-attention, oracle,
  and resource-allocation decisions reduce design/envelope uncertainty more
  than low-VOI alternatives under the same budget class.
- **A-spec-gap containment**: verifier incompleteness routes to governance-owned
  A repair and never counts as B success or recommendation authority.
- **Search replayability**: `SearchLedger` replay with frozen refs reproduces
  candidates, counterexamples, decisions, frontier movement, and abstention.
- **Search incompleteness honesty**: reports distinguish best-known frontier
  from exhaustive optimum and disclose unexplored high-VOI branches or budget
  cutoffs.
- **Delegation precision/recall**: required human decisions surface when
  value-laden, high-stakes, out-of-envelope, budget, acquisition, or final-choice
  decisions occur, without interrupting for low-VOI autonomous actions.
- **Responsibility-integrity pass rate**: human approvals are active,
  mandate-bounded, informed by limitations and disconfirming evidence, and
  never record "AI decided" as accountable principal.
- **Projection faithfulness**: public, reviewer, expert, and machine projections
  preserve load-bearing limitations, tradeoffs, value choices, regime
  declarations, shadow status, and contestability from the canonical record.
- **Lowering authority correctness**: legal, budget, procedure, or monitoring
  lowering is blocked or re-enters search/verify when deeper authority
  requirements are absent.
- **Bootstrap reuse-rate**: new cases reuse facet, design-composition, and
  projection primitives rather than adding case-specific products.
- **Bootstrap override-rate trend**: human override rates fall for regime,
  coupling, value, decomposition, and final-selection decisions while required
  questions remain enforced.
- **Resource allocation honesty**: exploit/invest choices disclose compute,
  acquisition, expert-time, human-attention, and legal-access budgets and do not
  optimize useful-design metrics by weakening floors.
- **Universality mechanism-generality**: frozen held-out cases are handled with
  sublinear marginal bespoke cost and rising primitive reuse.
- **Universality boundary calibration**: in/out envelope predictions are
  calibrated by axis cell, with false-in-envelope errors penalized heavily.
- **Universality assurance status**: top-level universality claims cite the
  battery, per-axis scorecard, certified envelope, and skeptic defeaters.
- **Design-time dominance**: expert panel judges whether the recommended design
  was dominated by another admissible candidate under the evidence and value
  weights available at design time.
- **Process adequacy**: expert review of whether the generator considered the
  right baselines, alternatives, constraints, risks, participation needs, and
  tradeoffs.
- **A-completeness adversarial pass rate**: generated or hand-authored designs
  that exploit missing admissibility specs are blocked, limited, or projected as
  contested rather than recommended.
- **P16/P17 firewall pass rate**: regime-shopping, false precision, false
  precaution, and decomposition laundering are blocked by A before B can promote
  the design.
- **Computational tractability honesty**: large design searches report exact,
  approximate, memoized, incremental, anytime-cutoff, or infeasible status
  rather than pretending exhaustive search happened.
- **Knowledge-governance throughput**: new constructs, source contracts, method
  contracts, and envelope expansions per reviewer-hour / automated proposal,
  with quality and rollback checks.
- **Post-deploy accountability closure**: deployed-outcome or monitoring signals
  produce analysis, update/acquisition/revalidation plans, execution records, and
  public/closed-case replay-safe accountability notes.
- **Envelope revision correctness**: envelope expansions require reusable
  validated mechanism growth, and envelope shrink happens on disconfirming
  deployment/spec-gaming evidence.
- **Learning attribution adequacy**: post-deploy divergence is classified or
  explicitly marked unattributable before it updates regime, coupling, response,
  capacity, calibration, or memory.
- **Prediction calibration on observable cases**: uncertainty intervals and
  point forecasts behave on the narrow subset with realized outcome evidence.
- **Realized regret**: recommended candidate's welfare/effectiveness gap from a
  better known alternative, only for rare multi-arm, staggered, experimental, or
  otherwise credible counterfactual settings.

- **monitorability_rate**: deployable designs that ship a valid
  monitoring/signpost plan; designs without one are advisory only.
- **A_before_B_ratio**: share of learning updates where A/firewall/envelope was
  repaired before any B-prior update, operationalizing the A-leads-B invariant.
- **envelope_shrink_latency**: time from disconfirming or spec-gaming evidence to
  withdrawal of the affected competence claim.
- **action_item_closure_rate**: `DivergenceRecord` / `DeploymentDossier` items
  with owner and deadline that reach closure, so post-deploy review is not
  archival theater.
- **oversight_effectiveness**: rubber-stamp rate, good-vs-bad override rate,
  time-to-intervene, attention burn, and approvals later linked to divergence.

Outcome evaluation is sparse in public policy. Most cases will not have
credible realized counterfactuals for years, and many never will. Therefore
D4 should weight process/expert/design-time metrics more heavily than realized
outcome metrics for near-term promotion, while still tracking realized-outcome
calibration where the evidence exists.

### D4.4 Corpus Re-Basing Rule

The current 13 cases should be retained as a **grounding and substrate-demand
seed**, not rebranded as a design-quality corpus. Each case should be
re-annotated with:

- problem framing independent of the existing policy;
- full axis-position vector and per-axis firewall status;
- epistemic-regime labels per claim and expected regime-conditional design
  strategy;
- scale class and, where composite, recursive sub-design graph;
- coupling graph, decomposition result, and interaction-residual annotations;
- expert candidate designs, including rejected alternatives;
- critical-path and dependency annotations for composite designs;
- system-dynamics/feedback/equilibrium obligations and expected evidence tier;
- construct demand denominator;
- available and unavailable source contracts;
- expected graded outcome by authority posture;
- certified operation envelope status and expected abstention/limitation
  boundary;
- expected counterexample class for failed candidates and the valid refinement
  decision (`refine`, `acquire`, `reframe`, `decompose`, `human_decision`, or
  `abstain`);
- expected search-ledger replay surface: explored branches, budget cutoffs,
  frontier movement, and search incompleteness declaration;
- expected human decision points, accountable actor, mandate boundary, and
  responsibility-integrity requirements;
- canonical Design Record contents, projection requests, redaction/access
  posture, and any lowering requests with expected authority gates;
- bootstrap role: whether the case is easy-corner seed, held-out battery member,
  or hard-corner challenge, plus expected reuse-vs-bespoke signal;
- resource-economics annotation: compute/acquisition/expert/human-attention
  budget pressure and expected exploit/invest choice;
- universality-battery metadata: frozen-system status, axis cell, skeptic attack
  addressed, marginal bespoke cost, and reuse evidence;
- post-deploy monitoring hooks: which outcomes, drift signals, or accountability
  events should update calibration, regime, coupling, response, acquisition, or
  memory;
- whether historical outcomes are usable for prediction/backtest;
- whether realized regret is observable or fundamentally unavailable;
- reviewer disagreement and value-choice provenance.

This makes D4 the evaluation bridge between A and B: A must pass grounding and
substrate metrics; B must additionally pass grammar validity, design recall,
design-time dominance, process adequacy, and sparse prediction/realized-regret
metrics in shadow before promotion.

### D4.5 Evaluation Status Composition

D4 introduces labels such as `weak_gold`, `expert_gold_seed`,
`causal_support_seed`, `shadow_candidate_pool`, `backtestable`,
`counterfactual_unavailable`, `simulation_only_system_effect`,
`equilibrium_contested`, `outside_certified_envelope`, and
`a_spec_gaming_probe`, `risk_regime`, `uncertainty_regime`,
`ambiguity_regime`, `ignorance_regime`, `false_risk_probe`,
`false_precaution_probe`, `modular`, `near_decomposable`,
`hierarchically_coupled`, `entangled`, `false_modular_probe`,
`real_design_blocker`, `substrate_gap`, `a_spec_gap`, `abstraction_gap`,
`value_gap`, `budget_gap`, `refine`, `acquire`, `reframe`, `decompose`,
`human_decision`, `abstain`, `delegated_autonomy`, `human_attention_required`,
`mandate_checked`, `responsibility_integrity_failed`, `search_incomplete`, and
`post_deploy_update_required`, `projection_only`, `lowering_required`,
`lowering_blocked`, `faithfulness_failed`, `bootstrap_seed`,
`held_out_universality_case`, `bespoke_growth_detected`, `mechanism_reuse`,
`envelope_expanded`, `envelope_shrunk`, `divergence_unattributable`,
`regime_error`, `coupling_error`, `world_change`, `implementation_failure`, and
`historical_prior_only`. These labels must compose with existing closure
statuses. For example:

- `counterfactual_unavailable` is not a failure of closeout honesty, but it
  blocks realized-regret claims;
- `expert_disagreement` can produce contested design quality without blocking
  grounding honesty;
- `weak_gold` can seed candidates but cannot define promotion floors alone;
- `shadow_candidate_pool` can improve recall measurement but cannot become the
  oracle;
- `outside_certified_envelope` blocks rollout posture claims but may still allow
  advisory exploration;
- `a_spec_gaming_probe` is a verifier-completeness test, not a generator success
  even if the candidate looks high-performing.
- `a_spec_gap` is a governance-owned verifier repair signal, not a B-side retry
  permission or a recommendation success.
- `ignorance_regime` blocks outcome-effect claims but can still support
  adaptive/precautionary design quality;
- `false_precaution_probe` fails when the system avoids available evidence by
  downgrading regime;
- `entangled` blocks authority composition from sub-designs unless system-level
  evidence exists or the design is downgraded;
- `false_modular_probe` fails when a portfolio passes by ignoring cross-module
  feedback or strategic arbitrage.
- `substrate_gap` can trigger acquisition or limitation, but cannot teach B to
  drop important unmeasured values from the objective;
- `human_attention_required` blocks autonomous continuation only for the
  decision class that exceeds the `DelegationContract`;
- `responsibility_integrity_failed` invalidates an approval record even if a
  human clicked "approve";
- `search_incomplete` does not invalidate a shadow frontier, but blocks claims
  that the frontier is globally optimal;
- `post_deploy_update_required` may trigger revalidation or memory/calibration
  update without mutating the authority basis of already closed cases.
- `projection_only` can be released only if faithfulness passes; it cannot add
  legal, budget, or recommendation content absent from the canonical record;
- `lowering_required` is a new design act and can be blocked even when a shallow
  projection is allowed;
- `bespoke_growth_detected` blocks mechanism-generality claims even if the
  individual case succeeds;
- `envelope_shrunk` is a valid, honest result, not a ratchet failure;
- `historical_prior_only` may influence routing or review but cannot satisfy
  current-run claim authority.

The evaluation ADR must include mixed-status tests so B cannot pass by
reporting only the favorable metrics.

### D4.6 Post-Deploy Accountability And Learning

B-on-A cannot stop at design-time evaluation. A universal designer must remain
accountable for deployed designs over time, while preserving replay semantics
for closed cases. But public policy is the worst domain for a naive
`predict -> observe -> loss -> update` loop: outcomes are lagged,
confounded, counterfactuals are usually unobserved, systems are nonstationary,
and the policy changes the data-generating process it is later measured
against.

**Accountability is a design-time gate, not only a post-deploy loop.** A design
is `deployable` only if it ships a monitoring design: expected outcomes,
implementation-fidelity signals, signposts/triggers, complaint/near-miss
channels, an attribution plan, reissue triggers, and a rollback/adaptation
pathway. Without it the design is `advisory` only. Monitorability is the
**floor** (every deployable design); learnability — pilots, comparison or
synthetic control, staggered adoption — is the **ceiling**, attempted only where
legitimate. A design that can be monitored but not cleanly attributed is
`accountability_only`, still deployable: necessary-but-unlearnable policy
(constitutional change, emergency response) is labeled, not refused. Making a
design accountable is one of the envelope-favorable operators, i.e. the
design-time half of the loop below.

Learning therefore has two time scales:

| Loop | Learns from | Signal quality | Primary role |
| --- | --- | --- | --- |
| Fast design-time loop | Search ledgers, typed counterexamples, A-spec gaps, human overrides, acquisition decisions, expert selections. | Relatively high and immediate. | Main engine for bootstrap, A-completeness, generator priors, and refinement policy. |
| Slow post-deploy loop | Outcomes, implementation reports, complaints, drift, near misses, surprises. | Sparse, lagged, often unattributable. | Accountability, calibration correction, envelope shrink/expansion, and cautious priors. |

The post-deploy loop still follows the MAPE-K shape, but it is
attribution-gated:

```text
Monitor deployed outcomes, drift, complaints, near misses, and implementation state
  -> Analyze via DivergenceRecord and attribution class
  -> Plan acquisition, model update, regime/coupling reclassification, repair, shrink, or reissue
  -> Execute the update under governance and replay rules
  -> Knowledge ledger updates calibration, memory, envelope revision, and corpus labels
```

First-class learning artifacts:

| Artifact | Purpose | Boundary |
| --- | --- | --- |
| `DeploymentDossier` | Lifetime monitoring record for a deployed design: expected outcomes, monitoring plan, implementation state, complaints, surprises, and review obligations, each with owner and review deadline. | Accountability floor, even when learning is impossible. |
| `DivergenceRecord` | Post-deploy specialization of `TypedDiagnosticRecord`: observed-vs-expected divergence with class `design_error`, `evidence_error`, `regime_error`, `coupling_error`, `world_change`, `strategic_response`, `implementation_failure`, or `unattributable`, plus owner, deadline, and action-item closure. | Learning input only after attribution; a divergence without tracked closure is an archive, not learning. |
| `LearningUpdateProposal` | Proposed update to substrate, A-firewall, B-prior, calibration, coupling, response, capacity, memory, corpus, or envelope, with an FDA-PCCP-style change-control class: `pre_authorized`, `reissue_required`, `envelope_shrink`, `historical_prior_only`, or `public_accountability_note`. | Must pass attribution barrier and anti-learning firewalls. |
| `EnvelopeRevision` | Expansion or shrink of the certified envelope with evidence, scope, replay effect, and public/governance note. | Release/readiness boundary; can go down as well as up. |
| `AssuranceCaseDelta` | The change to a design's assurance argument when learning occurs: which claims become weaker, stronger, or invalidated. | A learning update with no assurance-case delta is a hidden authority change (reflexive self-design). |

This loop is not a license to rewrite past authority. Closed PDCs replay under
the rules, source refs, and constraint snapshots that closed them. New evidence
can trigger public accountability notes, revalidation, partial reissue, memory
updates, or envelope expansion/shrink, but it must not silently mutate the
historical claim basis.

Only attributable divergences update the corresponding component. For example:
`regime_error` can update the regime classifier; `coupling_error` can update
coupling/modularity; `strategic_response` can update Goodhart/Lucas models;
`implementation_failure` may trigger capacity or delivery redesign but should
not be counted as proof that the policy theory was false. `unattributable` is a
valid honest result: it records accountability but does not train the system on
noise.

Anti-learning firewalls:

- Do not learn to choose values; learn to expose tradeoffs and ask authorized
  principals.
- Do not let B capability grow faster than A completeness inside the same
  envelope.
- Do not optimize `useful_design_rate` by weakening floors or hiding blockers.
- Do not update from confounded single cases without attribution.
- Do not treat post-policy data as pre-policy evidence without the
  strategic-response/Lucas boundary.
- Do not let learned priors satisfy current-run claim authority.

Learned outputs enter as historical-prior or routing influence with provenance,
TTL, decay, and contamination controls. This reuses the C41 firewall: memory,
calibration priors, and success/failure patterns can influence review,
acquisition, and generation, but cannot close current evidence slots.

Post-deploy learning may update more than data coverage:

- regime priors and false-risk / false-ignorance rates;
- coupling and interaction-residual classifications;
- strategic-response and Goodhart/Lucas models;
- state-capacity and implementation-feasibility priors;
- calibration of forecasts and uncertainty intervals;
- balanced memory: successful design patterns as well as failures;
- corpus labels for future shadow evaluation;
- certified envelope boundaries and abstention rates.

The same delegation layer applies post-deploy. High-stakes reissue, public
correction, value conflict, mandate challenge, and verifier-spec repair require
typed human/governance decisions with responsibility-integrity records.

The key test is bidirectional: across rounds, the certified envelope should
expand where reusable mechanisms and evidence improve, and shrink on seeded
disconfirmation or spec-gaming evidence. A system that can only ratchet upward
is laundering past success.

## Open Decisions To Resolve Next (feed D2-D4)

- **Cross-cutting abstraction:** which parts of D2-D4 must use
  `TypedDiagnosticRecord`, `ValueOfInformationEstimate`,
  `GovernanceDecisionClass`, and the shared faithfulness verifier, and which
  local artifact families should be merged or retired to avoid P13?
- **D2-substrate:** what is the construct ontology's breadth target and
  governance? what sources get indexed by construct, and how is authority
  metadata derived at ingestion? what is the coverage denominator?
- **D2-facet algebra:** which facet primitives and composition rules are
  governed at launch, which combinations inherit authority floors, and which
  new measure primitives require manual governance?
- **D2-axis envelope:** which hidden axes are launch-gated, which are advisory,
  what is the axis-position schema, and how is envelope membership tested?
- **D2-cluster ownership map:** which package/subpackage owns each cluster x axis
  cell, which cells are orphan, and which Foundry/scientist seeds are
  `implemented_but_not_orchestrated` rather than implemented?
- **D2-cluster handshakes:** what does each cluster publish, what does each
  downstream cluster consume, and what negative test proves the consumer fails
  closed when the signal is missing?
- **D2-C3 extension:** which cluster authority dimensions enter the ADR-0174 C3
  envelope, and where are they consumed by closeout/projection?
- **D2-epistemic regime:** what evidence classifies claims as risk,
  uncertainty, ambiguity, ignorance, or contested-model, and how are P16
  overconfidence/precaution laundering probes defined?
- **D2-coupling/modularity:** how is the coupling graph built, what thresholds
  classify modular/near-decomposable/hierarchical/entangled boundaries, and how
  are false-modular errors prevented?
- **D2-design composition:** what is the recursive design graph schema, which
  dependency edge types are in the narrow waist, how is critical path computed,
  and when does composition trigger system-dynamics requirements?
- **D2-ODD/abstention:** what certified domain x jurisdiction x scale x posture
  x regime x coupling x capacity x reversibility/stakes envelopes are declared
  for each release, and what bounded-abstention floors are acceptable by
  posture?
- **D2-acquisition:** which connector-registry routes run first, what are the
  human fallback criteria, and what are the VOI/cost/eligibility rules (C22)?
- **D2-replay/status:** how do capability-index deltas preserve closed-case
  replay, and how do acquisition states compose with the existing status
  lattice?
- **Graded outcomes:** the exact research/governed downgrade rule and its
  guardrails so it cannot leak into production authority.
- **D3 (B, shadow):** is the LLM the designer-within-grammar, or is there a
  structured design-space model it populates? where is the generation/authority
  boundary, and what is the shadow→promotion criterion?
- **D3-terminal output:** what is the canonical `DesignRecord` schema, which
  fields are replay-frozen, which lowerings are included by reference, and what
  consumer contract proves every output is derived from the record rather than
  a separate narrative surface?
- **D3-projection algebra:** what are the governed `audience x aspect x depth x
  redaction x format` primitives, what verifier proves projection faithfulness,
  and which requests require lowering rather than projection?
- **D3-lowering boundary:** which lowering depths are in scope for the first
  posture, what authority requirements are added by legal/budget/procedure
  lowering, and when does a post-closeout lowering request reopen or reissue the
  design?
- **D3-search control plane:** what is the MVP `ConstraintStoreSnapshot`,
  `CounterexampleRecord`, `RefinementDecision`, and `SearchLedger` schema; which
  cluster writes are required for the first end-to-end loop; and what makes the
  control policy deterministic under replay?
- **D3-counterexamples:** how are `real_design_blocker`, `substrate_gap`,
  `a_spec_gap`, `abstraction_gap`, `value_gap`, and `budget_gap` classified,
  who may classify `a_spec_gap`, and which classes can teach B versus trigger A
  repair or acquisition?
- **D3-refinement policy:** how are VOI, compute, acquisition cost, expert time,
  urgency, stakes, and human-attention budgets traded off when choosing
  `refine`, `acquire`, `reframe`, `decompose`, `human_decision`, or `abstain`?
- **D3-delegation:** what classes of decisions can be autonomous under
  `CertifiedDesignEnvelope ∩ DelegationContract ∩ within-bounds`, which require
  `HumanDecisionRequest`, and what makes an approval informed enough for
  responsibility integrity?
- **D3-bootstrap:** what is the first certified easy-corner envelope that is
  also attached to real demand, what typed human acts become training/governance
  labels, and what held-out battery proves the bootstrap is not bespoke growth?
- **D3-minimal seed manifest:** which launch facet primitives, instrument
  primitives, projection primitives, A-firewalls, budgets, and held-out cases are
  frozen before any D5 implementation work starts?
- **D3-resource economics:** who sets the explore/exploit dial, which budgets
  are hard constraints versus tradeoffs, and what prevents the system from
  allocating resources to improve internal metrics rather than principal
  mission, user demand, and hard-corner learning?
- **D3-VOI contract:** what is the minimal `ValueOfInformationEstimate` schema,
  how are typed budgets compared without pretending they are interchangeable,
  and what evidence calibrates VOI over time?
- **D3-A completeness:** what admissibility specs must exist before B can be
  promoted in a given envelope, and what adversarial spec-gaming tests define
  "complete enough"?
- **D3-regime strategy:** which design operators are legal under risk,
  uncertainty, ambiguity, and ignorance, and how does the generator prove it did
  not regime-shop?
- **D3-modularization:** when may the generator propose ring-fencing, phasing,
  pilots, severability, buffers, or sunset rules as design moves to reduce
  coupling, and how are those moves grounded?
- **D3-normative firewall:** who supplies objectives and value weights, how are
  value-choice records ratified, how are alternative value schedules shown, and
  how does the system handle multi-principal incompatibility without pretending
  to solve it?
- **D4-evaluation:** who supplies expert candidate designs and realized-outcome
  labels, which domains are backtestable, and what floors are posture-specific
  versus advisory-only?
- **D4-search evaluation:** how many of the 13 seed cases must produce valid
  counterexample/refinement decisions, and what mix of acquisition,
  robust/limited design, and honest abstention demonstrates "designer rather
  than evaluator" without pretending missing evidence exists?
- **D4-post-deploy accountability:** which deployed outcome, drift, complaint,
  and near-miss signals enter the accountability loop, how do they update
  regime/coupling/response/calibration/memory, and how is closed-case replay
  preserved?
- **D4-learning attribution:** what evidence can classify a divergence as
  `design_error`, `evidence_error`, `regime_error`, `coupling_error`,
  `world_change`, `strategic_response`, `implementation_failure`, or
  `unattributable`, and which classes are allowed to change A, B, substrate,
  memory, or the certified envelope?
- **D4-envelope revision:** what process can expand, shrink, or split the
  envelope, which revisions require operator/governance approval, and how are
  old closed cases replayed under their original envelope refs?
- **D4-universality assurance:** what held-out frozen-system battery, per-axis
  scorecard, reuse-rate, boundary-calibration result, and baseline comparison
  are required before making any universality claim at a given posture?
- **D4-oracle breadth:** what domain/jurisdiction/instrument breadth is enough
  to claim "universal" at each posture, which scale classes are included, and
  what is the floor-setting method?

## Recommendation Summary

1. **B-on-A is accepted** as the north star, operated **shadow-first**: A is the
   release gate, B is the product ambition; B runs advisory/shadow until the
   A-substrate grounds real cases.
2. Treat "universal" as an **assurance claim**, not a slogan: mechanism
   generality, honest boundary, grounded authority inside the envelope,
   held-out frozen-system tests, baseline comparisons, reuse-rate, and
   per-axis/hard-corner reporting.
3. Consolidate D2-D4 around shared abstractions before adding new artifacts:
   `TypedDiagnosticRecord`, `ValueOfInformationEstimate`,
   `GovernanceDecisionClass`, ascending-cost frontier expansion,
   envelope-favorable design operators, and faithfulness verification for both
   policy projections and universality self-claims.
4. Regardless of target posture, **facet-space substrate + acquisition loop
   (D2)** and **design-composition algebra** remain binding constraints. The
   invariant core also includes epistemic-regime classification,
   coupling/modularity classification, cluster authority dimensions, and the
   governed `cluster_ownership_map.toml` as the first ratcheted blind-spot
   inventory.
5. Land **graded outcomes** in parallel - fork-independent, near-term, moves the
   honest metric immediately (statuses exist; wire composition + downgrade).
6. Replace the D3 one-pass pipeline with **counterexample- and
   acquisition-guided design search**: A writes constraints before generation,
   emits typed counterexamples after failure, and a replayable
   `RefinementPolicy` chooses refine/acquire/reframe/decompose/human-decision/
   abstain under VOI, budget, stakes, and urgency. Keep B grammar-first,
   recursive, regime-conditional, and shadow-only until the substrate proves
   grounding succeeds on real data and A-completeness adversarial probes pass
   inside the declared envelope.
7. Make the **Canonical Design Record** the terminal authority-bearing object.
   Projection is faithful rendering; lowering is a new governed design act that
   re-enters search/verify when it creates legal, fiscal, procedural, or
   monitoring content.
8. Add the **delegation operating model** before designing UX/API: autonomy is
   the intersection of certified capability, explicit delegation, and
   mandate/stakes/regime bounds. Human input enters through typed,
   mandate-checked decisions, not a generic co-pilot toggle or rubber-stamp
   review.
9. Treat cold-start and resource allocation as **reflexive self-design**:
   bootstrap from easy-corner real demand, freeze a `MinimalSeedManifest`, seed
   algebra generators rather than products, use typed human acts as labels, and
   optimize honesty, calibration, reuse, VOI quality, and validated envelope
   revision rather than `useful_design_rate`.
10. Rebuild the **corpus/metrics (D4)** to measure design quality, search
   behavior, counterexample/refinement validity, delegation quality, projection
   faithfulness, lowering authority correctness, bootstrap reuse, resource
   allocation honesty, universality assurance, post-deploy accountability, and
   sparse realized-outcome calibration across domains and scales.
11. Treat post-deploy learning as **attribution-gated accountability**, not a
    naive ML loop: deployed outcomes may produce `DivergenceRecord`,
    `LearningUpdateProposal`, and `EnvelopeRevision`, but learned priors remain
    historical-prior/routing influence unless independently re-grounded.
12. Before D5, continue the cluster-ownership mapping SOP from the seeded map:
    re-project the remaining capability-ratchet claims and README ownership
    headers onto the cluster x axis grid, identify orphans and
    `implemented_but_not_orchestrated` seeds, and turn them into a bridge-first
    action list.
13. Only then write the Layer-2 implementation plan (D5), starting with the MVP
    search loop and canonical Design Record rather than the full control-plane
    wishlist.

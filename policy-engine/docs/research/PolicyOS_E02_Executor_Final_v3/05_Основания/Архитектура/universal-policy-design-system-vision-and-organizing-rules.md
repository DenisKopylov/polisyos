---
title: Universal Policy Design — System Vision And Organizing Rules
status: draft design decision — organizing constitution (post-S14 synthesis)
owner: team-architecture
created: 2026-06-03
last_reviewed: 2026-07-20 (additive amendment to §1: identity and the custody boundary; acceptance record in policyos-identity-and-custody-boundary.md)
decision_status: proposed — the durable laws that govern how the Layer 2 system is built and extended
supersedes: nothing
informs:
  - docs/plans/active/POLICYOS_UNIVERSAL_POLICY_DESIGNER_LAYER2_IMPLEMENTATION_PLAN.md
  - docs/plans/active/layer2-slices/
source_design_doc: docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
related:
  - docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
  - docs/system-design-decisions/policyos-identity-and-custody-boundary.md
  - docs/reference/policy-design-case-failure-patterns.md
  - docs/adr/0174-policy-evidence-capability-graph.md
  - architecture/policy_design_case/cluster_ownership_map.toml
---

# Universal Policy Design — System Vision And Organizing Rules

## What This Document Is

This is the **organizing constitution** for the PolicyOS Layer 2 universal policy
designer: the durable vision of what the system is for, and the laws that keep it
coherent as it grows. It is deliberately altitude-stable.

- It is **not** the design (D0–D4 live in
  `universal-policy-design-target-architecture-and-gap.md`).
- It is **not** a task plan (those live in
  `docs/plans/active/layer2-slices/`).
- It is **not** a failure register (that is
  `docs/reference/policy-design-case-failure-patterns.md`).

Read those for *what* and *how*. Read **this** for *why the pieces fit together
the way they do, and the rules you may not break when you extend the system*.

If a change would violate an Organizing Rule below, it is wrong even if every
test is green. The rules exist because the system's value is the discipline, not
the feature count.

## 1. Vision

PolicyOS Layer 2 is a **generative policy designer built on a grounding backbone**
("B-on-A"). Given a request to formulate or evaluate a policy, the system either:

- produces a **useful, grounded result inside a declared operation envelope**
  (a design, a refinement, a limited recommendation, an acquisition plan), or
- produces an **honest abstention or grounded limitation** outside that envelope.

"Useful" never means "confident." The system's worth is that it **tells the truth
about what it can and cannot ground**, and never launders generation, computation,
or fluency into authority it has not earned. An external "universal designer"
claim is admissible only through the S14 universality gate, and only for the
scope the certified envelope actually covers.

The honest target is to convert genuinely hard cases into **typed counterexamples,
valid refinements, robust/limited designs, acquisition plans, or honest
abstentions — without weakening floors**. The envelope may shrink. That is a
feature.

**Identity and the custody boundary (amendment, ratified 2026-07-20).** The system's
identity is the **epistemic custodian of policy justification across the whole life of a
policy**. The honesty promise above has a time dimension: a claim honest at t0 silently
becomes false when law, data, calibration, or the world changes — so custody of every
published signature, for as long as it publicly stands, is the *completion* of this
vision, not an extension of it. The boundary rule: **PolicyOS owns everything it signs,
for exactly as long as the signature stands; it consumes everything others sign as typed
evidence; it makes no claims it cannot custody.** It is therefore a design authority, a
justification custodian, and a post-deployment learning loop — and explicitly **not** an
administrator, executor, case-management system, court, notification channel, or payment
system. Scope questions are adjudicated by the four-way test (`own / integrate / observe /
out_of_scope`) in `docs/system-design-decisions/policyos-identity-and-custody-boundary.md`,
which is the human-principal acceptance record for this amendment (per §12).

## 2. The Two Roles

The whole architecture turns on a single separation.

| Role | What it is | Authority |
| --- | --- | --- |
| **A — the grounding/authority backbone** | Verification, firewalls, evidence binding, calibration, envelope, replay, accountability. The release gate. | A is the **only** source of authority. |
| **B — the generative designer** | Grammar-derived candidates, search, composition, LLM proposals, exploratory engine runs. The product ambition. | B is **always shadow/advisory** until A grounds it and the promotion gate passes. |

**A leads B.** Verifier/firewall completeness for an envelope region is repaired
*before* B is promoted there. New search/generation power raises the
adversarial-against-A obligation; it never relaxes it.

The discovery rule is deliberately three-part: **search discovers; adapters
discipline; the authority gate admits**. A search hit, best-so-far frontier, or
no-hit result is candidate/control-plane information until an adapter translates
it into a port contract and A admits it for a purpose. Search breadth is how the
system grows; replayable search boundaries are how it avoids laundering the
frontier into authority (P25).

## 3. System Anatomy And The Dependency Rule

The system is layered as concentric rings. **Dependencies point inward, toward
the waist. The waist depends on nothing outward.**

```
   ┌─────────────────────────────────────────────────────────────┐
   │  Engines (domain power, ~593k LOC)                            │
   │  src/polisyos/foundry · fabric · scientist                    │
   │  Causal/optimization/bayesian, data acquisition, analysis,    │
   │  LLM orchestration. Know NOTHING of the waist.                │
   └───────────────▲───────────────────────────────────────────────┘
                   │ adapters call engines, never the reverse
   ┌───────────────┴───────────────────────────────────────────────┐
   │  Grounding + Adapter layer                                     │
   │  src/polisyos/runtime/quality (~part of the 125k waist)        │
   │  MAY import engines. Wraps every engine/agent output in a      │
   │  typed contract + authority boundary + calibration, or         │
   │  FAILS CLOSED. Exemplars: ir_analytics_bridge.py,              │
   │  adapter_contracts.py, calibration_ledger.py.                  │
   └───────────────▲───────────────────────────────────────────────┘
                   │ consumes only typed contracts (ports)
   ┌───────────────┴───────────────────────────────────────────────┐
   │  The Narrow Waist — pure core                                  │
   │  src/polisyos/pdc · the typed contracts everything speaks      │
   │  AuthorityBoundary, TypedDiagnosticRecord, ForecastSupport,    │
   │  CertifiedOperationEnvelope, DesignRecord, GovernanceDecision  │
   │  NEVER imports engines. Small on purpose.                      │
   └────────────────────────────────────────────────────────────────┘
```

- **`pdc` is sacred and small.** It is the typed narrow waist every layer speaks.
  It must never import `foundry`/`fabric`/`scientist`. Keeping it pure is what
  lets the rest of the system be large.
- **`runtime/quality` is the grounding and adapter ring.** It is *allowed* to
  import engines; that is its job. But every engine touch-point must obey the
  adapter discipline (§7), not call engines ad hoc.
- **Engines stay where they are.** They are never absorbed into the waist
  (that is the P13 gravity well) and their raw outputs never satisfy an authority
  slot (that is P15 at scale). They enter only as port-conformant projections.
- **The LLM agent is an engine too.** It is subordinated by the same discipline:
  a candidate-generator / search-controller adapter, never a judge.

## 4. The Narrow Waist And Why It Is Sacred

The waist is the set of typed contracts that carry authority: `AuthorityBoundary`
(`authoritative_for` / `may_not_use_for`), `TypedDiagnosticRecord`,
`ForecastSupport`, `ProofCarryingAnalyticsRecord`, `SourceContract`,
`CertifiedOperationEnvelope`, `DesignRecord`, `GovernanceDecisionClass`,
`HumanDecisionRecord`, and the cluster-map `publishes`/`consumes` edges.

Its smallness is load-bearing. The engines are ~5× the waist. The only way a
system this large stays honest is if **all power flows through one small typed
gate** where authority, calibration, envelope, provenance, and firewalls are
checked. Widen the waist to match the engines and you have rebuilt the chaos the
waist exists to prevent.

## 5. Organizing Rules (the laws)

These are the invariants. A change that breaks one is wrong regardless of test
status. Each names the firewall/pattern it enforces.

1. **A grounds, B generates.** No B output bears authority until A grounds it and
   the promotion gate (D3.8) passes. *Enforced by:* shadow-only
   `authority_boundary` on B outputs; the promotion gate.
2. **Generation is a candidate, never an authority slot** (anti-P15). LLM, search,
   and exploratory engine runs are proposals. *Enforced by:* candidate source
   stays shadow; A verifies; grammar precedes candidate.
3. **Fail closed and downgrade by default.** Missing grounding is a typed blocker
   or abstention, never a silent pass. An adapter emits the **lowest tier it can
   prove**, not the engine's confident number. *Enforced by:* fail-closed
   producers; ForecastSupport tiers; adapter preservation/loss blockers.
4. **Authority composes to the weakest boundary.** A composed result is as strong
   as its weakest grounded link — never the average, never the max. Cross-level
   authority is the critical path, not min-over-all. *Enforced by:* sequential
   weakest-boundary downgrade in the design loop; `weakest_boundary_reason`.
5. **Optimize honesty, not usefulness.** Optimize calibration, honesty, reuse, and
   validated envelope revision — **never `useful_design_rate`**. The metric you
   optimize becomes the behavior you get. *Enforced by:* closeout-honesty and
   calibration floors; useful_design_rate is reported, never targeted.
6. **Untested is out-of-envelope.** The `CertifiedOperationEnvelope` declares what
   is in and out; an untested axis or combination is out by default; the envelope
   may shrink on disconfirmation. *Enforced by:* S14 default-out; S13 shrink; an
   envelope on every DesignRecord.
7. **Closed cases are immutable for replay.** Index/acquisition/learning deltas
   never mutate a closed case's replay. Learned priors are historical influence,
   never current evidence. *Enforced by:* ADR-0174 C2; S13 closed-case replay
   integrity; the C41 historical-prior firewall.
8. **One status lattice.** No parallel status systems. New statuses define their
   composition with the existing lattice. *Enforced by:* the composed status
   lattice (D3.7 / S1).
9. **External power enters only through the waist.** Engines and agents reach the
   authority graph **only** via a conformance-proven, registry-admitted adapter
   that fails closed (§7). *Enforced by:* ports = typed slots; adapter admission =
   capability-ratchet maturity + conformance battery; `pdc` never imports engines.
10. **Define once, reference** (anti-P13). Heavy machinery — vocabulary,
    traceability, floor governance, corpus partition — is defined once (S0) and
    referenced. Per-slice entries stay terse. *Enforced by:* the cluster map,
    artifact traceability, and the readiness validator.
11. **A human principal stays accountable** (P26). The system never learns away
    ownership; high-stakes/value-laden/out-of-envelope acts surface a decision to
    an accountable principal; the meta-regress of mission/budgets/values stops at
    that principal. *Enforced by:* DelegationContract, HumanDecisionRecord,
    oversight-effectiveness telemetry.
12. **Capability follows the corpus — discovered by search, never enumerated**
    (free growth). The system's power must be a pure function of what the corpus
    holds (datasets, sources, Foundry methods, agents, claims), discovered at
    runtime by search over typed indexes. Discovery has three distinct postures:
    **discoverable** (the resource is visible to the index), **executable** (it can
    be called or read through a typed interface), and **admitted authority** (it
    has passed adapter conformance for a declared purpose). The first two are
    candidate states, never authority. Adding a correctly-implemented resource
    increases capability with **zero new code** — that is the whole point of the
    waist. A hand-maintained enumeration (a list of methods, constructs, datasets,
    sources, variables) is a **defect, not a convenience**: it is false
    reassurance that hides the real problem — discovery does not work yet, so the
    implementation is not doing what it claims. **Universality or nothing: no
    crutches, no hardcode fallbacks.** Remediation is fixed and mandatory: (1) mark
    the enumeration; (2) build the discovery-search so a correctly-implemented new
    resource becomes visible and executable without code change; (3) **delete the
    hardcoded fallback.** If deletion breaks something, that breakage is the honest
    signal of where discovery is still incomplete — it is the next work item, never
    a reason to restore the fallback. Governed vocabularies, schemas, statuses,
    ports, and rule versions are not banned by this rule; capability-gating
    enumerations are. The discovery postures compose with the one status lattice
    (Rule 8); they never create a parallel authority status system. Abstention
    from a search path is honest only when search recall and index freshness are
    adequate for the declared envelope; a false abstention caused by poor recall is
    hidden capability loss, not honesty. *Enforced by:* corpus-search adapters; replayable
    search-frontier ledgers with index/version/cutoff/incompleteness evidence; the
    no-hardcode-enumeration lint; the mechanism-generality test (one engine handles
    ≥2 distinct inputs); the free-growth test (a correctly-added resource is
    discovered without code change); and recall/freshness checks on known-groundable
    seeds.

## 6. The Capability Reality Bar

A capability is **implemented** only when the full chain exists:

> typed contract/artifact · producer · persisted artifact/event · orchestration
> bridge · consumer · verification · PUBLIC/REVIEWER/EXPERT/MACHINE surface (or
> explicit out-of-scope) · negative + semantic test.

If any link is missing, name it precisely (`contract_only`, `producer_missing`,
`bridge_missing`, `consumer_missing`, `surface_missing`, `semantic_test_missing`,
…) and do not call it implemented. The cluster ownership map, not any green
report, is the single progress meter. (See the failure-patterns register.)

## 7. Subordinating Existing Code — The Integration Discipline

The system's next large value comes from subordinating the ~593k lines of
engines to the waist's discipline **without rewriting them, absorbing them, or
trusting them**. The repository already implements this discipline in seed form
(`adapter_contracts.py`, `ir_analytics_bridge.py`); the rule is to **formalize and
enforce it**, not invent a new framework.

The disciplined flow is stable across every source: search discovers candidates,
adapters translate and downgrade candidates into port contracts, and admission
decides whether that contract may carry authority for a declared purpose.

Four elements, each grounded in an existing seam:

1. **Ports** — the core's authority slots declared as the typed contracts an
   engine must fill (`ForecastSupport`, `ProofCarryingAnalyticsRecord`,
   `SourceContract`, `TypedDiagnosticRecord`). The cluster-map
   `publishes`/`consumes` edges are the port map. The core declares the need; the
   engine adapts to the core (dependency inversion).
2. **Adapters** — engine-side translators living in `runtime/quality`. Pattern =
   `ir_analytics_bridge`: call engine → map to the port contract → attach
   authority boundary + calibration + envelope + provenance → **fail closed /
   downgrade** if it cannot establish them. The adapter's job is to lower an
   engine's output to what it can actually prove. Distrust is the default. An
   adapter is **not** an enumerated mapping (Rule 12): it owns or invokes a
   corpus-search path that takes a typed request and searches the engine's
   indexes (dataset catalogs, claim graphs, method/agent registries) for
   candidates, then translates only conformance-valid candidates into the port.
   It carries **no hand-maintained list** of constructs, datasets, methods, or
   variables. A correctly-added resource becomes discoverable and executable with
   zero adapter changes; a hardcoded list is a defect to be marked, replaced by
   search, and deleted.
3. **Admission registry** — `AdapterContractRegistry` plus the capability-ratchet
   maturity vocabulary. An adapter is admitted to an authority slot at a governed
   maturity (`fail_closed` → `predictive` → `calibrated`). Unregistered output is
   candidate/shadow only.
4. **Conformance harness** — extends `validate_adapter_preservation` plus a
   per-adapter adversarial-against-A battery. **Conformance is the admission
   gate**: no high authority without passing it. Otherwise a wrapped output is
   contract-only laundering (P01) at the adapter level.

**Two-speed connection.** This is what makes arbitrary requests tractable without
losing discipline:

- **Candidate/shadow path** is cheap: engines and the LLM agent feed candidates
  freely; they cannot launder because they are shadow by contract. → breadth.
- **Grounding/authority path** is conformance-gated per port. → earned depth.

Generation gives immediate breadth; grounding earns depth one port at a time; the
S14 gate keeps any "universal" claim honest. One discipline subordinates both the
deterministic engines and the LLM agent.

## 8. Architectural Strengths And Necessary Tradeoffs

This architecture is a deliberate instance of a convergent industry-and-research
pattern — the **anti-corruption layer** (DDD), **ports-and-adapters / hexagonal**
architecture, the **hourglass / narrow-waist spanning layer** (Beck), and
**incremental subordination** (strangler fig). Adopting that pattern buys real
strengths and, by the same logic, incurs unavoidable costs. An honest constitution
declares both: the costs below are **not defects to be fixed away — they are the
price of the guarantees**, and the system must be instrumented to watch them, not
pretend they are absent. This section is the system declaring its own envelope.

### 8.1 Strengths (what the discipline buys)

- **Monotonic, safe growth.** Because every external output fails closed and
  composes to the weakest boundary, adding an engine, adapter, or agent can only
  *add* honest capability or honest limitation — it cannot silently corrupt the
  existing authority graph. A system this large can grow without the usual
  integration decay.
- **Independent evolution above and below the waist.** Engines
  (`foundry`/`fabric`/`scientist`) and the agent evolve on their own cadence; the
  waist is the only thing both sides must agree on. This is the hourglass's core
  dividend.
- **Honest, composable authority.** Authority is a typed, replayable,
  envelope-bounded quantity that composes deterministically — not a vibe that
  accretes through fluent prose or confident numbers.
- **One discipline for all external power.** Deterministic engines and the LLM
  agent are subordinated by the *same* ports/adapters/conformance contract, so
  there is no second, weaker governance path for "the smart component".

### 8.2 Necessary tradeoffs (the price of the guarantees)

| Tradeoff | Why it is unavoidable | Mitigation + health signal |
| --- | --- | --- |
| **T1 — Value is gated on groundability, not orchestration.** The discipline makes value *safe to produce*; it cannot make hard domains *groundable*. The system may settle into "excellent honest abstention" far more often than "grounded useful design". | Policy causal inference is genuinely hard to ground and transport. The architecture is built to refuse to fake this, so it surfaces the limit rather than hiding it. | Treat the limit as a measurement, not a defeat. **Signal: envelope-expansion-rate** per unit of grounding effort — near-zero at healthy throughput ⇒ the ceiling is the domain, not the code. |
| **T2 — The waist's expressiveness is a fixed tradeoff (hourglass theorem).** Squeezing the waist to admit more engines below provably narrows the range of designs it can express above. | Beck's deployment-scalability result: a thinner spanning layer covers more implementations but supports fewer applications. There is no escape, only good placement. | Keep the waist **versioned and slowly evolving**, never frozen. **Signal: `AdapterLossBlocker` / semantic-loss rate** — systematic loss means the waist is placed too thin for the engines' richness. |
| **T3 — The adapter/conformance layer is a bottleneck risk** ("facade as bottleneck", "adapter hell"). Per-port governed conformance can stall (nothing admitted ⇒ permanent shadow) or rubber-stamp (laundering returns). | Any anti-corruption facade concentrates flow; governed admission is socio-technical throughput, not code. | Adapters thin and uniform; conformance **mostly automated** (W12D + adversarial battery, not human review). **Signal: `KnowledgeGovernanceThroughputLedger`** — governance, not code, becomes the growth limiter if it stalls. |
| **T4 — The agent creates authority gradients and selection/framing leakage.** "Candidate, not authority" is clean for a deterministic generator but leaks for an agent that chooses which evidence to fetch and how to frame counterexamples. | 2025 agentic-safety work: authority gradients induce deference and risk accumulates over long-horizon orchestration; the agent biases grounding without ever filling an authority slot. | Adversarial-against-A and the search ledger must cover the agent's **orchestration choices** (tool/evidence selection, framing), not only its proposals; keep tool interfaces structured and deterministic. **Signal: replayable orchestration-choice audit.** |
| **T5 — The waist ossifies** (rigid exactly where change is most expensive). The hourglass lets the layers evolve, but everything depends on the waist; if `authority + envelope + calibration` misses a needed dimension, changing it ripples everywhere. | DDD: a premature or wrong boundary choice is costly when the domain is not yet fully clear. | Minimal waist (less to get wrong), highest-governance for waist changes, and an explicit open-questions register (§8.4). **Signal: frequency of "forced" waist changes under pressure.** |
| **T6 — The honesty objective has no internal pressure to expand.** A system rewarded for honest abstention finds it *always safe to refuse*; the incentive gradient points away from the expensive work of grounding. | Optimizing honesty (Rule 5) is correct, but unbalanced it becomes inertia: abstention costs nothing internally. | Expansion must be pulled **externally** by demand — the S12 VOI/explore-exploit dial, S3 demand-pull, and the accountable principal (Rule 11). **Signal: demand-pull vs abstention-rate** — rising abstention with flat demand-response is the inertia failure. |
| **T7 — Search recall can create false abstention.** Capability via search can miss evidence that is actually in the corpus, especially under stale indexes, weak aliases, narrow budgets, or poor ranking. That false abstention looks externally like honest limitation. | Search breadth is necessary for free growth, but no-hit is not proof that no ground exists. A replayable frontier audits what happened; it does not by itself measure recall. | Treat abstention quality as a measured property. Seed the corpus with known-groundable cases, check index freshness, and distinguish **search ceiling** from **domain ceiling**. **Signal: search-recall@known-seeds + index-staleness.** |

### 8.3 Health metrics (instrument these, or the tradeoffs go silent)

The tradeoffs are acceptable only if they are *watched*. Five signals make them
visible and must be first-class, not buried in a run log:

1. **envelope-expansion-rate** (T1) — grounded envelope gained per unit of grounding effort.
2. **adapter-semantic-loss** (T2) — `AdapterLossBlocker` rate across registered adapters.
3. **governance-throughput** (T3) — `KnowledgeGovernanceThroughputLedger` admit/stall rate.
4. **demand-pull vs abstention-rate** (T6) — does external demand actually move the abstention rate?
5. **search-recall@known-seeds + index-staleness** (T7) — can the search layer find known-groundable resources, and are indexes fresh enough for the declared envelope?

If all five are healthy, the system grows globally and safely. If expansion stalls
at healthy governance-throughput **and** healthy search recall/freshness, the
honest conclusion may be a **domain ceiling**. If recall or freshness fails, the
ceiling is in the search layer — a repairable system defect, not a domain limit.

### 8.4 Open questions (resolve before ADR promotion)

- Is the waist vocabulary (`authority + envelope + calibration`) at the right
  altitude, or does it need a first-class dimension it currently encodes only as a
  status (e.g. value-pluralism / contestedness)? (T2, T5)
- Is real grounding achievable at acceptable cost in the target domains, or is the
  honest equilibrium mostly abstention? (T1)
- Is the demand-pull (S12 VOI / accountable principal) strong enough to overcome
  abstention inertia? (T6)
- Does capability search have enough recall and freshness to distinguish honest
  abstention from a missed grounding path? (T7)
- Does the bounded agent leak authority through orchestration choices in ways the
  current search ledger does not capture? (T4)

### 8.5 Grounding

These tradeoffs are documented costs of the chosen patterns, not speculation: the
hourglass deployment-scalability tradeoff (Beck, *On the Hourglass Model*, CACM);
the anti-corruption-layer / strangler-fig "facade bottleneck" and "adapter hell"
(DDD; AWS and Azure prescriptive guidance); and agentic authority gradients /
risk accumulation (2025 agent-safety literature). The point of naming them here is
that an honest system declares its envelope — including the envelope of its own
architecture.

## 9. Current State (honest)

As of the post-S14 synthesis:

- **The composition mechanism works and is safe.** For the pinned case, every
  axis (regime, coupling, blind-spots, delegation, value, forecast, predictive,
  resource, accountability) composes into one `DesignRecord` whose status is the
  weakest-boundary composition, projected by S9 and gated by S14. B output carries
  shadow-only authority. No production/recommendation leakage.
- **Integration depth is one case.** The full composed design loop runs for
  `ua-msme-affordable-loans-2022`; the other 12 canonical cases are classified
  per-slice (real breadth) but not run through the integrated loop. Cross-slice
  interaction is proven at depth 1.
- **The proving ground is unconverted at runtime.** All 13 cases remain typed
  blockers; `useful_design_rate = 0` — by design, because B is shadow and the
  grounding engines are not yet connected through the waist, and the promotion
  gate (D3.8) is not yet built.
- **"All slices green + S14 gate" means the designer mechanism is built and
  safe — not that the system produces better policies on real cases yet.** That
  is the next phase, and S14 honestly refuses to claim otherwise.

## 10. Forward Direction

Value beyond S14 comes from **widening the certified envelope one grounded region
at a time**, in this order:

1. **Grounding before generation.** Connect the specific engine capabilities a
   proving-ground case needs through conformance-proven adapters (§7), so A can
   ground or refute real claims. Run adversarial-against-A *during* this, because
   real grounding is when laundering and calibration-gaming first become live.
2. **The promotion gate (D3.8).** Build the gate that converts a grounded B output
   from shadow to actual authority. Without it, even perfect grounding stays
   shadow and the proving ground stays at zero useful designs.
3. **The bounded agent.** Add the LLM search-controller/generator (reusing
   `scientist/orchestration/llm`) to generalize from wired cases to a class of
   requests — strictly as candidate/orchestrator, never judge.

First milestone: convert **one** proving-ground case from typed blocker to a
grounded, limited design (or honest grounded abstention) with real evidence,
calibration, and envelope — not shadow. Prove the engines-through-the-waist thesis
on one case before scaling, exactly as every prior slice proved its mechanism on
one case first.

## 11. How To Extend The System (conformance conditions)

Before adding capability, every one of these must hold. They are design-review
conditions, not a task list.

- It enters through the waist (a typed port), not a direct engine call from `pdc`
  or an ad-hoc call from the loop.
- Any engine/agent output is wrapped in a typed contract with an
  `AuthorityBoundary` and fails closed when grounding is absent.
- Its authority is admitted at a governed maturity and proven by conformance, not
  asserted.
- It optimizes honesty/calibration/reuse/envelope, never `useful_design_rate`.
- Untested scope is out-of-envelope; the envelope is declared.
- It reuses shared machinery (define-once) rather than re-deriving vocabulary.
- Capability is **discovered by search over the corpus, never enumerated**
  (Rule 12): the code carries no hand-maintained list of constructs, datasets,
  methods, or agents; a correctly-added resource is usable with zero new code; any
  hardcoded enumeration is marked, replaced by discovery-search, and deleted with
  no fallback.
- Authority-relevant search is replayable and bounded: frontier, selected and
  rejected candidates, index/rule versions, budget cutoffs, and incompleteness or
  absence reasons are recorded before any no-hit, abstention, or selected result
  can affect a port.
- Abstention and domain-ceiling claims depend on measured search recall and index
  freshness for the declared envelope; false abstention from poor search is a
  capability defect.
- A human principal remains accountable for high-stakes/out-of-envelope acts.
- The capability reality chain is complete and the cluster map stays green.
- It is built to **best-in-class engineering standards**: established libraries
  over hand-rolled equivalents, index-backed/lazy/streaming over O(n) scans and
  eager loads (so it scales as the corpus grows — Rule 12), strict types,
  deterministic replay, and fail-closed error handling. A technically weak
  implementation is a defect, not a shortcut.

If any condition fails, the capability is not ready — name the missing link
precisely and stop there.

## 12. Amending This Constitution

Changing this constitution is the highest-governance architecture act. If
execution reveals that a rule is wrong or incomplete, amend the constitution
first; do not violate it and explain the violation later. A rule change requires
an accepted ADR or equivalent human-principal acceptance record, an impact note on
the status lattice, authority boundaries, replay behavior, and affected slice
plans, plus a rule-version reference so closed cases replay under the rules that
closed them. Proposed rules become accepted only when their open questions,
health signals, and enforcement surfaces are owned.

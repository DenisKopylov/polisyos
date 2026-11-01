---
title: Causal Grounding Firewall (CGF) — Formal Target Specification for the Grounding Layer
status: draft design decision — formal target spec for the GY grounding block (Phase 5)
owner: team-architecture
created: 2026-06-30
last_reviewed: 2026-06-30
decision_status: accepted as the target spec the GY grounding block (GY-CG) is subordinated to
source_spec: docs/reference/policy-design-causal-grounding-firewall-CGF-spec.md
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
related:
  - docs/system-design-decisions/policy-design-search-target-spec.md
  - docs/system-design-decisions/policy-design-causal-operating-system-north-star.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/reference/policy-design-case-failure-patterns.md
  - architecture/policy_design_case/layer3_gy_n0_investigation.md
---

# Causal Grounding Firewall (CGF) — Formal Target Specification

This decision record **registers** an externally authored formal specification — the
**Causal Grounding Firewall (CGF)**, the unified synthesis of seven independent studies
(RT1–RT7) — as the **target spec** the GY **grounding block (GY-CG)** is built toward, and
records exactly **what we adopt, what is genuinely new, and what we defer**. The verbatim
spec is archived at `docs/reference/policy-design-causal-grounding-firewall-CGF-spec.md`;
this document is the **PolicyOS reading** of it.

> **One law first.** CGF is the **target architecture, not a from-scratch build**. Under our
> no-parallel-worlds law (P27/P28) it is **subordinated** to existing organs: it consumes
> L2/L3/L6/WorldModelRecord as the credal reference (GY-S2/S3, GY-N3), GY-K as the per-axis
> entailment **witness** (never the decider), N7 as the acquire arm, the N6 QuarantineFront as
> the proxy-gap home, and GY-N12 as the epoch/staling discipline. The mapping below is binding.

## 1. What it is, in our terms

CGF is the **firewall layer between the intervention generator (B / GY-N4) and downstream
search / promotion**. It makes grounding **not** a nearest-name lookup but **provable
correspondence to a typed causal object**. Its central contract converged independently on
our discipline:

> *Grounding is allowed only as a robust-singleton assignment whose relation-set is safe
> across all admissible reference completions, all hard obligations are closed, the risk
> ledger covers probabilistic checks, and the certificate is bound to L2/L3/L6/WMR versions
> and the validator epoch. Embedding, similarity, LLM rationale and proxy score may
> **prioritize**, never **bind**. False bind is worse than abstain.*

This is the third external spec to converge on our architecture, completing the **three
layers of the causal OS**: data (memory) = GY-S / L1–L6; **grounding (the type system /
linker) = CGF**; search (the scheduler/optimizer) = RACE-HOG-PODS. CGF is the glue between
generation, the world model, and search — and it is **the fix for the current live blocker**:
GY-N4's exact-match `trinity_linker_rejected_candidate` is precisely the naive grounding CGF
replaces.

The pipeline: `parse → high-recall retrieve (+adversarial counter-candidates) → JTCG joint
typed cross-modal solver → RT1 relation calculus → RT2 certificate-first bind/abstain → RT3
free-grow admission → RT5 adversarial quarantine → RT7 active acquisition → RT6 benchmark`.
Two guarantees: `P(confident-wrong bind) ≤ δ_ground` and `P(hallucinated admit) ≤ δ_adm`,
both **conditional on maintained assumptions** (see §5).

## 2. The seven components and their boundaries

| RT | Role | Boundary |
| --- | --- | --- |
| **RT1 (CRG)** | typed relation calculus on **causal** (not surface) equivalence; relation set {exact / certified-specialization / generalization / partial / compositional / **false-analog** / novel / unknown}; critical-axis **contradiction veto** | defines `relation(s,atom)`; does not admit novel or run acquisition |
| **RT4 (JTCG)** | joint typed cross-modal solver (MaxSMT/ILP/CP-SAT) over operator × target × params × estimand × admissibility × L3/L6/knob/do/method; hard constraints + **unsat cores** | the constructive layer **before** RT1; greedy per-axis is never a binding method |
| **RT2 (CAAB)** | certificate-first abstaining binder: reference-lift, **robust singleton**, obligations, **risk ledger** δ; conformal only as an efficiency/monitoring layer | decides bind / abstain / **novel-candidate** (novel ≠ new lever) |
| **RT3** | open-world free-grow admission: completion set + proof obligations + **StableUnique** + VOI acquisition → admit / acquire / reject | decides real-new-lever vs needs-acquisition vs hallucination; not promotion/value |
| **RT5 (EG-PIG)** | evidence-gated **phrasing-invariant** grounding: surface channel vs causal-evidence channel; proxy-gap → QuarantineFront | defends bind/admission from phrasing-only proxy-gaming; not the RT1/RT4 validator |
| **RT7 (AG-VOI)** | active grounding controller: typed blockers → {cheap-verify / elicit / acquire / adversarial-validate / abstain} by robust LCB-VOI per cost; never bypasses gates | chooses the next action under ambiguity; cannot buy a bind |
| **RT6** | executable benchmark without a single gold: must+/may+/must-/unknown interval labels; **false-bind headline**; stress/growth/private streams | evaluates the whole trace + safety/utility under growth |

## 3. The credal state IS our substrate + the existing organs (the load-bearing reuse)

CGF does not invent its reference — it **lifts ours into a credal reference**:
`K_ref = K_L2 × K_L3 × K_L6 × K_WMR`, each edge statused
`{confirmed | contested | incomplete | deprecated | out_of_scope}`. Reuse map:

| CGF object | Our organ |
| --- | --- |
| reference (variables, alignments, thresholds, knobs, slots) | **GY-S2** (L2 canonical variables + `variable_alignments` + L3 lex) + **GY-S3** (L6 knobs / lex_intervention_map / method manifest) + **GY-N3** WorldModelRecord (world slots) |
| per-axis entailment witness (`cheap_verify`) | **GY-K** bounded entailment judge — a **witness on one axis/obligation**, never the final decider |
| acquire arm (world-slot / measurement / legal / mechanism acquisition) | **GY-N7** (expanded from data-gap acquisition to grounding-acquisition) |
| proxy-gap / adversarial home | **GY-N6 QuarantineFront** + the in-cycle `adversarial_validate` action |
| epoch-scoped certificates + reference-revision staling | **GY-N12** (epochs + stale certs + OpenWorldRisk) |
| risk ledger δ_ground | composes with the **GY-N11** confidence ledger (`P(false promotion) ≤ δ`) |
| the atom (operator/target/params/effect/estimand/admissibility/world-version) | **GY-N2** `InterventionAtomBinding` (the bind target; JTCG is its joint solver) |
| registry growth on admit | **GY-S0** free-grow registry (a new lever registers; no auto-DecisionFront) |

CGF is **the layer below the search**: the search (RACE-HOG-PODS) operates over grounded
atoms, and **`δ_ground` enters the search's obligation-completeness** — a confident-wrong bind
poisons the whole search. They share the VOI / partial-identification / calibrated-abstention /
proxy-gap machinery.

## 4. Adoption decisions (binding; threaded into the GY plan, Revision 13)

### A new dedicated block: GY-CG0–CG6 (Phase 5, a foundation parallel to GY-S)

Mapped to the spec's implementation phases 0–6, each §3.5.6-gated:

- **GY-CG0 — Reference audit + credal reference** (phase 0): version L2/L3/L6/WMR; status edges;
  build the **set-valued** `K_ref`; stale conditions + epoch. Extends GY-S2/S3/N3/N12.
- **GY-CG1 — JTCG + CRG shadow** (phase 1, **keystone — unblocks GY-N4 now**): retrieve →
  joint typed cross-modal solver (hard constraints + unsat core) → relation CSP (false-analog
  veto) → `GroundingRelationCertificate`. **Shadow only, no production bind.**
- **GY-CG2 — CAAB conservative bind gate** (phase 2): certificate-first, reference-lift,
  robust-singleton, risk-ledger δ_ground, calibration strata + cold-start + drift. Production
  bind **only** exact / certified-specialization with a certificate; else abstain / novel.
- **GY-CG3 — RT3 free-grow admission** (phase 3, **the free-grow core**): open-world completions
  + admission obligations + StableUnique + VOI acquisition → admit / acquire / reject; registry
  patch (grow L6/WMR/atom-index; **no auto-DecisionFront**).
- **GY-CG4 — RT5 phrasing-invariant defense** (phase 4): EG-PIG surface↔evidence channels;
  proxy-gap → QuarantineFront; phrasing-only attack harness.
- **GY-CG5 — RT7 active grounding controller** (phase 5): AG-VOI over typed blockers; never
  bypasses gates. *(Deferred candidate — see below.)*
- **GY-CG6 — RT6 benchmark + false-bind headline** (phase 6, the proving ground).

### Hooks on existing tasks (bar-raises, not duplicates)

GY-N4 (candidate-firewall = CG1/CG2, not exact-match), GY-N2 (atom = CGF target; binding =
JTCG), GY-N6 (QuarantineFront generator = RT5 proxy-gap), GY-N7 (acquisition expands to
grounding-acquisition), GY-N8/N9 (estimand grounding + GroundingCertificate required for
promotion), GY-N11/N12 (δ_ground composition + reference-audit epochs), GY-S2/S3 + GY-K
(reference + axis witness, wire-existing).

### Defer (adopt the contract now, implement later)

The full **RT7 multi-action EVSI**, the RT6 **private-adversarial / retroactive-denominator**
streams, and the **conformal efficiency layer**. The immediate unblock is **CG0 + CG1 + CG2**
(reference audit + shadow relation engine + conservative exact-bind) **plus the RAG-in-prompt
nudge in GY-N4** — this replaces the exact-match grounding and makes the live cycle work.

## 5. Honest caveats (do not paper over)

1. **The δ-guarantees are conditional on validator soundness + the reference credal set
   containing the truth (δ_ref).** This is the same **P29** regress as the search spec: the
   teeth depend on the obligation/validator/reference completeness, which is empirical.
2. **JTCG needs a real SMT/CP-SAT backend on Python 3.14** (z3 / OR-Tools CP-SAT). Confirm
   availability or record a fallback (the same solver gate the search spec records via GY-N0).
3. **Reference quality bounds grounding quality** — garbage L2 alignments → garbage binds. The
   reference audit (CG0) is therefore first and load-bearing.
4. **Scope:** CGF is large (joint solver, conformal, VOI, adversarial harness). The phased
   order (shadow → exact-bind → free-grow) is mandatory; do not build all seven RTs at once.

## 6. Status

Accepted as the target spec for the GY grounding block. The concrete adoption is threaded into
`docs/plans/active/layer3-slices/GY-engine-subordination.md` (Revision 13): the GY-CG block, the
existing-task hooks, and the deferred list. No code is written from this document directly — it
governs the shape of the tasks, the same way the search target-spec and the causal-OS north-star
govern the frame.

---
title: Policy-Design Search & Selection — Formal Target Specification (RACE-HOG-PODS v3.2)
status: draft design decision — formal target spec for Phase 5 (B-on-A generation cycle)
owner: team-architecture
created: 2026-06-27
last_reviewed: 2026-06-27
decision_status: accepted as the target spec the GY Phase-5 cycle is subordinated to
supersedes: nothing
source_spec: docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
related:
  - docs/system-design-decisions/policy-design-causal-operating-system-north-star.md
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/policy-design-execution-topology.md
  - docs/reference/policy-design-case-failure-patterns.md
  - architecture/policy_design_case/layer3_gy_n0_investigation.md
---

# Policy-Design Search & Selection — Formal Target Specification

This decision record **registers** an externally authored formal specification —
**RACE-HOG-PODS v3.2** (*Robust Active Certified Explorer for Honest-Grounded
Partially-identified Optimistic Discovery Search*) — as the **target spec** the GY
Phase-5 *B-on-A generation cycle* is built toward, and records exactly **what we adopt,
what is genuinely new, and what we defer**. The verbatim spec is archived at
`docs/reference/policy-design-search-RACE-HOG-PODS-v3.2-spec.md`; this document is the
**PolicyOS reading** of it.

> **One law first (read before the spec's §27).** The spec is written as a greenfield
> algorithm with a from-scratch 6-phase build plan (its §27). Under our
> **no-parallel-worlds law** (P27/P28/P30, enforced by the GY-N0 disposition ledger) that
> build plan is **superseded**: every object in the spec is realized by **subordinating an
> existing organ** (wire / extend / consolidate), never by a parallel rebuild. The spec is
> the **target architecture**, not a project to start cold. The mapping below is binding.

## 1. What it is, in our terms

The spec's central contract is **identical to ours**:

> *Explore optimistically. Promote conservatively. Separate world evidence, simulation,
> surrogate belief, structural assumptions and normative obligations. Never allow a proxy
> score, LLM rationale or simulator-only output to become a promotion certificate.*

That is our **B-on-A, shadow-first** + the **honest-grounding firewall** (the safety
kernel) + **Rule 5** (optimize honesty, never `useful_design_rate`). Several external
human and agent contributors converged on our own architecture — a strong signal the
direction is right.

The spec is therefore best understood as the **formal twin of GY Phase 5** (N4–N10),
plus the value gate (N8), acquisition (N7), and promotion (N9), written at a much higher
level of mathematical rigor than the plan. Its returned object is **not one "best"
design** but a stratified set: `DecisionFront` (certified), `ResearchFront` (promising,
not promoted), `QuarantineFront` (high-proxy / high-gap, under adversarial validation),
`PortfolioFront` (certified randomized policies), and a `CertificatePackage` per public
point.

## 2. The credal state IS our L1–L6 substrate (the load-bearing mapping)

The spec's separated **credal components** are not abstractions to invent — the
production data substrate (see `[[project-production-data-world-model-substrate]]` and the
GY-S block) **already instantiates them**. This is where the spec lands on current work
(GY-S1):

| Spec credal component | Our substrate (GY-S) | GY task |
| --- | --- | --- |
| `K_world` (world evidence) + `Obs` | L1 DCAT observations / coverage / quality + L4 corpus state | GY-S0 / S1 |
| `K_id` (identification per objective: point / partial / proxy) | **L5 `identification_mode_registry`** + L2 `design_quality_tier` | GY-S1, GY-S2 |
| `K_cal` + `K_meas` (calibration scope + measurement obligations) | **L5 `measurement_registry` / proxy_mappings / trust_tiers** | GY-S1 |
| `DataTrust(u)` | **L5 trust_tiers** (authoritative_high … weak_anchor) | GY-S1, GY-N7 |
| Transportability scope / `transported_limited` | **L2 7 607 `transport_scores`** | GY-S2, GY-N8 |
| Structural ambiguity (disjoint scenario set) | **L2 `contested_edges`** | GY-S2 |
| `K_impl` + `K_norm` (admissibility / obligation) | **L3 rule_thresholds + normative facts** | GY-S2, GY-N1 |
| Epoch / temporal validity | **L3 amendments `effective_from` + L5 `schema_regime` v1/v2 changepoint** | GY-N12 (new) |
| Lever space (atom `op,π`) + method routing | **L6 knob dictionary + lex_intervention_map + observation_to_contract_manifest** | GY-S3, GY-N2, GY-N8 |
| `K_sim` (simulation uncertainty) — **never shrinks `K_world`** | foundry joint-sim output (GY-N5) — kept separate from L1/L4 world state | GY-N5, GY-N8 |

Consequence for the live work: the GY-S substrate lift is not merely "bind the data" — it
**initializes the credal state**, and the bound state must be **set-valued** (point →
narrow, partial → interval, proxy → wide), with the L5 `identification_mode` choosing the
value-set type and a calibration scope-mismatch downgrading proxy → partial → blocked.

## 3. The worked example the spec is missing (and we own)

The spec treats `K_world` shrinkage abstractly. Our most valuable concrete instantiation
is already in hand and should be the canonical example:

> **L2 `parameter_estimates` (estimate + CI + `design_quality_tier` + `trust_score`) →
> a constraint on `K_world` / `K_id`.** A curated causal estimate with a confidence
> interval and a design-quality tier *is* world evidence with an identification status;
> its `transport_score` to the design's scope sets the transportability bound
> (`transported_limited`). This is the L2→credal bridge GY-S2 and GY-N8 implement.

## 4. Adoption decisions (binding; threaded into the GY plan, Revision 11)

### A. Raise the bar on existing tasks (augment in place)

- **GY-S0 / S1 / S2 / S3** — credal-component mapping (§2) + **set-valued value** +
  CalCert scope + DataTrust as explicit substrate contracts; the L2 worked example (§3).
- **GY-N8 (value-as-gate)** — value is a **certified value-outer-set `V_out`** over a
  *named* `WorldModelRecord`, not a scalar + CI; **honest dominance** (strong-robust vs
  marginal fallback, `unknown` on solver timeout — never silently "dominated"); the **six
  evaluation modes** with the rule that `simulate_only` never shrinks `K_world`.
- **GY-N9 (promotion)** — the full **obligations compiler** (the `O(x)` taxonomy) + an
  **anytime-valid confidence ledger** (δ-budget, e-values, union bound,
  `P(false promotion) ≤ δ`). This is the most important new rigor and it is the *right*
  tool: our search is adaptive (candidates depend on prior outcomes), so fixed-time
  intervals do not suffice.
- **GY-N6 (cycle controller)** — return the **four stratified fronts** instead of one
  "best"; mixed proposer with the **grammar-fallback coverage guarantee** (Thm 4).
  *(MCTS / progressive widening / nonstationary meta-controller → deferred, §C.)*
- **GY-N7 (acquisition)** — the **eight acquisition families** (HV / HKG / ID / CERT /
  ADV / COV / AUD / SAFE) + **affected-region revalidation** `R_out(u)` (over-approx) +
  bundle / complementarity (greedy is a heuristic without adaptive submodularity). Start
  with **ID + CERT + COV**.
- **GY-N5 (joint sim)** — declare `equilibrium_semantics ∈ {none … agent_based_model,
  unsupported}`; an `unsupported`-feedback objective **cannot be grounded** (we already
  "gate, not silently sum"; the spec gives the exact taxonomy).
- **GY-N4 (generation)** — the firewall rule (*Proposer proposes, Surrogate prioritizes,
  Validator certifies*) + the **"Not certificates"** list (our P32 + P15 + P29) + a
  **graph-causal surrogate** (foundry NCM / GCM + SKG as the search-ranking model).

### B. Open new tasks / contracts (not in the plan today)

- **GY-N-V — `ValueOuterSet` (set-valued value foundation contract).** A typed carrier of
  credal value (interval / polytope / support-function) consumed by GY-S1, GY-N8, GY-N6. A
  foundation bridge alongside N1–N3, **landing with GY-S1** — it is the typed home for the
  proxy-bounds currently being hand-rolled into `HouseholdCellState`. Without it, S1 / S2 /
  N8 hard-code bounds ad hoc.
- **GY-N11 — honest confidence ledger** (anytime-valid risk accounting; δ-split; e-values;
  union bound). No existing task owns it. Under / after N9.
- **GY-N12 — model-revision epochs + stale certificates + OpenWorldRisk.** Cross-cutting;
  sits on **L3 amendments + L5 `schema_regime`** (both already in the substrate) — a
  natural extension of the temporal competence we already have. Near N10.
- **EvalSafety gate + evaluation-mode ladder** (`simulate_only` … `deployment`; *safe to
  simulate ≠ safe to pilot*) — the Phase-5 → Phase-6 bridge. Modes in N8; the EvalSafety
  gate before any field / deployment evaluation in Phase 6.
- **Quarantine front as an in-cycle action.** `adversarial_validate` is one of the spec's
  eight core actions and the `QuarantineFront` is its target. Today GY-V4 is a
  verification battery, not an in-cycle action/front. Folded into N6 (front) + N7 (ADV).

### C. Defer (over-built for current maturity — adopt the contract now, implement later)

With `useful_design_rate ≈ 0` and depth-1 integration, the mature-frontier machinery is
not yet load-bearing. Carry the **contracts/labels now** so artifacts already speak them;
implement when there is a certified frontier to manage.

- **Portfolio-as-design** (a randomized policy as a new object with nonlinear value) →
  Phase 7 / follow-on; the spec itself requires portfolio semantics be certified before
  any portfolio is returned.
- **CHHV solvers, scenario-tree VOI with rectangularity, EXP3 meta-controller, full
  MCTS** → needed for a rich certified frontier; not now.

## 5. Two honest caveats (do not paper over)

1. **The δ-safety theorem is conditional on obligation completeness + validator
   soundness** (the spec's A4 / `ObligationCompletenessRisk`). That is exactly our
   recurring failure — the "X = permission / verify-the-verifier" regress (**P29**). The
   spec **formalizes the contract around our hardest open problem; it does not close it.**
   Its mitigations (quarantine front, adversarial validation, revision epochs) are the
   same *complete-by-construction + adversarial probes + review* stance we already adopted
   (the P29 stopping point). Keep it clear-eyed: the theorem's teeth are empirical.
2. **Joint-credal dominance is, in general, intractable** (`inf` over an 8-component
   coupled κ, `O(n²)` robust solves). In practice the system lives in the **marginal-
   interval fallback** (spec §9.3) — "safe but conservative, many incomparable." Early
   "robust" power is more aspirational than operative; the `unknown`/incomparable
   discipline (never silently "dominated") is what makes the fallback honest.

Plus the environment reality: **Python 3.14** keeps DoWhy / EconML / CVXPY unavailable.
The spec's robust / dominance / CHHV solves must run on a 3.14-real backend (statsmodels /
JAX / SciPy / pymoo) or an explicit interval-only fallback (GY-N0 records this gate).

## 6. Status

Accepted as the target spec for GY Phase 5. The concrete adoption is threaded into
`docs/plans/active/layer3-slices/GY-engine-subordination.md` (Revision 11): the GY-S
block, the new `GY-N-V` / `GY-N11` / `GY-N12` tasks, the N4–N9 bar-raises, and the
Phase-5 deferred list. No code is written from this document directly — it governs the
shape of the tasks, the same way the causal-OS north-star governs the frame.

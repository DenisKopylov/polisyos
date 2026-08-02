---
title: Custody & Operations — Parallel Deep Research Backlog (Wave 2, Rev 2)
status: active
kind: research-backlog
owner: team-architecture
created: 2026-07-20
revised: 2026-08-02 (Rev 3 — Stage 0 CLOSED and RATIFIED. PAO-R0, PAO-R1 and OPS-R15 delivered and independently audited; consolidated into the sixteen-statement custody kernel; all sixteen ratified 2026-08-02 [docs/system-design-decisions/stage0-custody-kernel-ratification.md]. S0-GAP-01 delivered and its naming carried into ratified S0-K01. OPS-R4 delivered accepted_narrow_scope and ADOPTED as the Custody Time Model [docs/system-design-decisions/policy-design-custody-time-model.md] - which refutes the universal persisted OperationalEventEnvelope, so the OPS-R4 row narrows accordingly. New Group D holds the one active Stage-0 gap: S0-GAP-02, commissioned by the ratification act because ratified S0-K14 blocks OPS-R15 SCORING until an independent oracle exists - designing the capstone under K13/K15 is not blocked. Completion Ledger is now populated, not a template. Counts: 25 active / 7 merged / 36 deferred-with-trigger. | Rev 2 — reshaped under the ratified identity/custody-boundary decision; disposition ledger over all 67 Rev-1 IDs: 24 active / 7 merged / 36 deferred-with-trigger)
governed_by: docs/system-design-decisions/policyos-identity-and-custody-boundary.md
relationship: sibling of docs/research/remaining-deep-research-backlog.md; distils later into docs/research/deep-research-value-distillation.md; INT/PAO findings gate or extend the active GY/Atlas plans, while OPS findings primarily shape a future dedicated H2 custody-runtime implementation plan whose artifacts GY and Atlas consume
authoritative_for: [research_task_specification, parallel_dispatch_registry, wave2_disposition_ledger]
may_not_use_for: [capability_claim, authority_grant, task_execution_contract]
---

# Custody & Operations — Parallel Deep Research Backlog (Wave 2, Rev 2)

> **Governed by the ratified identity decision (2026-07-20):**
> `docs/system-design-decisions/policyos-identity-and-custody-boundary.md`. PolicyOS is the
> **epistemic custodian of policy justification** — it owns everything it signs for as long
> as the signature publicly stands, consumes everything others sign as typed evidence, and
> makes no claims it cannot custody. This wave researches the **custodial core** (Horizon
> H2): design authority + lifetime justification custody + a safe learning loop. It does
> **not** research PolicyOS-as-administrator: administrative execution is INTEGRATE/OBSERVE/
> OUT_OF_SCOPE territory, preserved in the deferred registry until a real pilot produces
> institutional facts. Rev 1 of this file (git history) presumed that question open; Rev 2
> is its resolution — nothing was deleted, every Rev-1 ID has a disposition below.

This is the **second** research wave. Wave 1 (`docs/research/remaining-deep-research-backlog.md`,
139 tasks) covered how to **design and verify a single evidence-native Policy Design Case**.
Its findings are distilled and tiered in `docs/research/deep-research-value-distillation.md`
(40 cross-cutting moves M1–M40, §6 adoption gate). **Do not re-research Wave-1 topics.**

Wave 2 researches what Wave 1 does not: **keeping the justification of every signed policy
decision honest across its whole life** — durable suspension and wakeup, minimal recompute,
world versioning, living law, KPI-to-decision semantics, safe post-deployment learning,
correct human action, and the proof machinery (completeness, delegation, translation,
public verification, compression) that lets any of it be exposed as authority.

Every active task is a **standalone research prompt** with a **research-only** deliverable.
Execution uses **staged parallelism**: first freeze the shared identity/boundary/capstone
anchors (`PAO-R0`, `PAO-R1`, `OPS-R15`), then run the remaining tasks concurrently and
consolidate later. Nothing here is a capability claim, an authority grant, or a code
contract.

## Purpose And Standing

- **Bootstrap, then parallelize.** Dispatch `PAO-R0`, `PAO-R1`, and `OPS-R15` first. Once
  their shared anchor packets are frozen, each remaining task is completable by an isolated
  researcher without depending on another task's unresolved final result. Duplicate
  **hypotheses** are acceptable; duplicate canonical contract families are not. Local
  contract sketches stay candidates for consolidation, never new owners.
- **Research-only.** A completed task lets a later engineering plan decide
  `prototype`/`govern`/`block`/`defer` — it is not an implementation. Direct repo code
  changes are out of scope for this wave.
- **The custody test governs scope.** For every task, the mandatory first finding is the
  four-way boundary verdict — `own / integrate / observe / out_of_scope` — adjudicated
  against the identity decision (its §5 test and §6 rulings), not re-litigated from
  scratch. A task whose function fails OWN must produce the *integrate-contract* (typed
  evidence interface, fail-closed absence behavior), never a proposal to own the function.
- **Two deliverable weights.** Genuinely open problems get the full 10-section research
  bundle. Tasks marked **[adapt]** are *pattern-adaptation dossiers*: the underlying
  mechanism is a solved engineering pattern (durable workflows, incremental dependency
  engines, event-time watermarks, versioned catalog branching); the research content is
  the **authority-delta** — what the known pattern lacks for authority semantics — and the
  dossier is correspondingly narrower and cheaper (see the deliverable form).

## Project Context For Every Researcher

PolicyOS is not a chat assistant that writes attractive policy memos. It is a **runtime for
public-policy design authority**: the system must prove why a recommendation, limitation,
abstention, warning, or publication state is `admissible`, `limited`, `contested`,
`blocked`, or `publishable`. Fluency, plausibility, or a generated answer is never
authority. LLM output, generated search frontiers, synthesized literature notes, and
exploratory engine runs are **candidates** until grounded by typed producers, evidence
contracts, adapters, verification, and authority boundaries.

The architecture is **B-on-A**. A is the grounding and authority backbone (verification,
firewalls, evidence binding, calibration, certified operation envelopes, replay,
accountability, release gates). B is the generative designer (grammar-derived candidates,
search, composition, LLM proposals, exploratory Foundry/Fabric/Scientist runs). **A leads
B.** Search discovers, adapters discipline, the authority gate admits. **Any research that
increases B's power must name the additional obligation it creates for A.**

The core architectural invariant is the **narrow waist**. `src/polisyos/pdc` carries the
small set of typed authority contracts. `src/polisyos/runtime/quality` is the
adapter/grounding ring allowed to import engines and downgrade their outputs into
port-conformant authority records. `foundry`, `fabric`, `scientist` remain engines; their
raw outputs never satisfy an authority slot. A safe research result describes how a later
implementation enters through a typed port, carries an `AuthorityBoundary`, fails closed
when grounding is absent, and stays out-of-envelope when untested.

The **honest diagnostics substrate** is the closeout authority. Every serious evidence
chain must answer: who owned the evidence, what runtime event produced it, which CAS
artifact stores it, what mode/fallback/input/schema/tenant/time context shaped it, which
downstream gate consumed it. Dashboards, readiness views, exports, and bundles may
**project** authority; they may not **mint** it. Unknown provenance, fallback, stale
evidence, schema mismatch, projection substitution, fixture-only evidence, or missing
same-input closure must become a typed blocker/limitation, never a silent pass.

Respect the **reuse-first** operating model: `wire-existing` → `extend-existing` →
`consolidate-existing` → only then `build-new`.

### The ratified identity and the signature rule (the lens for every task)

**PolicyOS = the epistemic custodian of policy justification across the whole life of a
policy.** The honesty promise has a time dimension: a claim honest at t0 silently becomes
false when law, data, calibration, or the world changes — so custody of every published
signature, for as long as it stands, is the *completion* of honesty, not an extension.
Three roles: **design authority** (grounded design or costed refusal-with-a-path),
**justification custodian** (epochs, staleness, perturbation cascade, revalidate/reissue/
supersede/withdraw with full historical provability), **learning loop** (deployed outcomes
grow the world model safely). Binding anti-roles: not an administrator, executor,
case-management system, court, notification channel, payment system, or CRM.

The four-way test (identity decision §5): absence makes OUR published claim silently false
→ **OWN**; output changes our claims' validity → **INTEGRATE** (we own the typed
fail-closed evidence contract, not the function); changes only who answers for claims →
**OBSERVE**; else → **OUT_OF_SCOPE**. Cheap extensions are worth taking exactly when they
are **projections of already-built core machinery** (cascade → appeal ingestion; epochs →
staleness; DDM → KPI contract) — never when they require owning a new sovereign subsystem.

### The organizing insight: five unsynchronized lifecycles

A single real policy simultaneously runs at least five lifecycles: **epistemic**
(what is known), **administrative** (applications, deadlines, notices, appeals),
**implementation** (budget, contracts, rollout, delivery), **institutional** (who holds
authority after reorganization/election), **public-records** (what is published,
corrected, retained, disclosed, erased). PolicyOS owns the epistemic lifecycle *and the
evidence contracts that feed it from the other four*. The custody question for every
non-epistemic event is always: *which of our signatures does this event touch, and through
which typed evidence interface do we learn of it?* Keep the five distinct in every state
machine; never collapse them into one status.

### What is ALREADY researched — do NOT redo it

Cite these rather than re-deriving them:

- **Single-case design machinery** (GY plan): Phase-5 cycle N0–N13, `ValueOuterSet`,
  δ-ledger (N11), epochs/stale-certs/OpenWorldRisk (N12), acquisition census/executor
  (N13a/b → honest `typed_deeper_terminal`), CGF grounding firewall, post-N11 producers
  GY-PA1/PA2/PA3.
- **Surface plan** (Atlas): DS0–DS20; status grammar DS4 (active), value/uncertainty DS16,
  δ-surface DS17, epoch/staleness DS18, human decision DS9, publication DS12, bounded
  agent DS14.
- **Distillation ledger**: moves M1–M40 + §6 adoption gate; especially M30×M31 (shared
  admission port × 7-axis weakest-boundary), M36 (perturbation cascade), M25
  (vintage/as-of, recompute-not-pin).
- **Public-authority wrapper** (Wave-1 CPA-R1..R28): mandate, participation, capacity,
  delivery FMEA, supplier risk/escrow/exit, incidents, appeals, compensation, invalidation
  cascades, transparency, construct validity, obligation grammar. Wave 2 never re-asks
  "are appeals needed" — it asks how the *evidence about them* enters custody.
- **Existing operational primitives** (reuse, don't rebuild): durable control plane
  (job-state today only `pending|running|completed|failed`); Scientist checkpoint/resume +
  CAS snapshots + workflow-fingerprint; Decision-Validity (law/data/source/model/metric/
  context change reaction, scheduled re-evaluation); W9 (drift detectors, partial-scope
  reissue, lifecycle bridge, rule replay) and W10 (bounded liveness, cost enforcement,
  operational FMEA, Net-MAV); Fabric incremental ingestion, cursors, watermarks, CDC,
  quarantine, bitemporal branches; GY §3.5.12 derived-data recipes; Lex staged legal batch
  (the GL-plan **excludes** the amendment detector + reference resolver — Legal-KG search
  and production are still different operational worlds); jurisdiction registry covers
  only `UA`/`EU`, unknown code silently falls back to Ukraine;
  `docs/reference/operations/retention-and-recovery.md` runbooks exist but are **not yet
  closeout evidence** of DR capability; PolicyPortfolio IR (ADR-0022) models *candidate*
  portfolios, not the deployed stock.

## Disposition Ledger (all 67 Rev-1 IDs — nothing deleted)

Per the repo's disposition-ledger law: every Rev-1 task has exactly one verdict. Full
Rev-1 specs for deferred rows remain in git history and in the deferred registry below.

| Verdict | IDs | Count |
| --- | --- | ---: |
| **active** (unchanged or re-scoped) | `INT-R1..R9`; `OPS-R1..R5, R8..R11, R14, R15`; `PAO-R0, R1, R4, R36`; **+ `S0-GAP-02`** (Group D, added by the Rev-3 ratification act; not a Rev-1 ID) | 24 + 1 |
| **merged** (scope absorbed, no loss) | `OPS-R6`→`OPS-R5` · `OPS-R7`→`INT-R4` · `PAO-R24`→`OPS-R4` · `PAO-R25`→`OPS-R2` · `PAO-R26`→`OPS-R3` · `PAO-R28`→`OPS-R14` · `PAO-R42`→`OPS-R15` | 7 |
| **deferred_until_trigger** (INTEGRATE/OBSERVE/OUT zones awaiting institutional facts) | `OPS-R12, R13`; `PAO-R2, R3, R5..R23, R27, R29..R35, R37..R41` | 36 |

## Parallel Execution Protocol

The execution model has two stages:

1. **Bootstrap anchors.** `PAO-R0` freezes the provisional identity/lineage spine,
   `PAO-R1` freezes the operational-boundary register shape, and `OPS-R15` freezes the
   capstone scenario/event vocabulary and success measures. These are shared research
   anchors, not implementation contracts.
2. **Parallel research.** Treat every other active task as if it is being researched
   simultaneously by someone who cannot coordinate with you. Consume the frozen bootstrap
   anchors, but do not depend on another task's unresolved future result. If a task needs a
   producer, consumer, schema, benchmark, or authority rule another task may also define,
   create a **local candidate** marked `external_dependency_assumption` or
   `candidate_for_consolidation`, never canonical project truth.

Parallel work may duplicate an argument or falsifier for independent confirmation. It may
not claim a second canonical artifact family beside an existing owner: every contract sketch
must name the owner it would extend, or prove that no owner exists (`P27`).

**Remaining live overlaps and directionality** (Rev 2 resolved most Rev-1 overlaps by
merging; these remain and must be consolidated deliberately):

- `INT-R7` ↔ `OPS-R14`: consolidate the public-key lifecycle with archive/DR custody;
  `INT-R7` owns the minimum before-first-public-record verification profile.
- `INT-R8` → GY-PA3 / Atlas DS12–DS14: `INT-R8` is the research input that defines safe
  compression loss and disclosure composition; the producer/surfaces must not close first
  and then treat the research as validation of a predetermined contract.
- `INT-R5` → GY-PA2 / Atlas DS9: the decision/delegation authority semantics are a binding
  research input to those producers and flows. `PAO-R4` remains the distinct individual-use
  firewall.
- `OPS-R5` + `INT-R4` → GY O1/O3: KPI diagnosis/adaptation governance and performative
  causal safety are joint closeout inputs to the deployed-effect update/write-back path.
- `OPS-R10`/`OPS-R11` ↔ Lex: extend the canonical Lex owners; do not create a second legal
  release, jurisdiction, time, or competence model.

## Mandatory Repo Baseline Study

Before external research or a new abstraction, inspect the repo and cite the files. At
minimum: `AGENTS.md`; `policy-engine/CONTRIBUTING.md`; the identity decision
(`docs/system-design-decisions/policyos-identity-and-custody-boundary.md`); the
architecture docs (`universal-policy-design-system-vision-and-organizing-rules.md`,
`universal-policy-design-target-architecture-and-gap.md`,
`policy-design-best-in-class-operating-model.md`, `honest-diagnostics-substrate.md`,
`policy-design-causal-operating-system-north-star.md`); the failure-pattern register
(`docs/reference/policy-design-case-failure-patterns.md`); the two active plans (GY +
Atlas); the distillation ledger; and the group-specific anchors in each group's execution
clause. Use `rg` to find existing names, artifacts, tests, docs. If no owner exists, say so
and name the missing capability label.

The report's `current_repo_baseline` section must include: inspected paths + existing
primitives; current capability label; likely producer / artifact-event / bridge / consumer
/ verification / surface; reusable tests/fixtures; repo gaps that are research blockers vs
engineering blockers; and the **four-way boundary verdict adjudicated against the identity
decision** (cite the §6 ruling you extend; flag any tension for consolidation rather than
overriding it).

## Research Quality Bar

Highest-quality research, not implementation planning. Required properties:

- Prefer primary sources, formal definitions, public standards, canonical papers,
  benchmark suites, well-established libraries. Secondary sources orient only.
- Separate theorem / empirical rule / design pattern / benchmark protocol / impossibility
  result / engineering convenience. Do not present a convenient contract as a proven
  method.
- Include ≥1 counterexample or adversarial case that would falsify an unsafe
  implementation.
- Include a benchmark proxy / fixture design / sealed eval / replay scenario /
  human-review packet that can later become a semantic test.
- Preserve authority boundaries: declare `authoritative_for` and `may_not_use_for`, or
  explain why the result stays `research_only`.
- Treat time, provenance, status, rule/schema version, audience, uncertainty, scope, and
  the five lifecycles as load-bearing.
- Report negative findings. A valid result can be `confirmed`, `accepted_narrow_scope`,
  `refuted`, `blocked`, or `deferred_open_problem`.
- **Do not turn unresolved research questions into code contracts.**

## Unified Deliverable Form

Full-weight tasks produce the 10-section bundle; **[adapt]** tasks produce the narrower
pattern-adaptation dossier (differences noted inline):

```text
# <Task ID> - <Short Title>

## 1. Task And Project Fit
Source task, exact research question, why research-first, the false production claim it
prevents, and the four-way boundary verdict (own/integrate/observe/out_of_scope)
adjudicated against the identity decision.

## 2. Current Repo Baseline
Files inspected, existing primitives, docs/tests/fixtures, current capability label, and
the smallest reuse-first integration path visible today.

## 3. External Research Baseline
Full-weight: primary sources, canonical standards/papers, competing approaches, known
limitations. [adapt]: name the canonical pattern class and 2-3 reference implementations;
do NOT survey the field — the pattern is stipulated as solved.

## 4. Result
Full-weight: theorem / rulebook / protocol / benchmark / impossibility / narrow-scope
design / refutation. [adapt]: the AUTHORITY-DELTA — precisely what the known pattern lacks
for authority semantics (identity/authority recheck, authority-dependency edges, governed
heads, epoch inheritance, fail-closed absence), and nothing the pattern already solves.

## 5. Counterexamples And Failure Modes
≥1 adversarial/boundary case; what an unsafe implementation would incorrectly conclude.

## 6. Benchmark Or Fixture Proposal
Synthetic data, frozen fixtures, hidden eval, replay scenario, human-review packet, or
parity test that can later become a semantic/e2e test.

## 7. Artifact Contract Sketch
Typed artifact shape, status inputs to the ONE Atlas lattice (never a parallel lattice),
authority boundary, provenance, time semantics, version/rule refs. Include a canonical-owner
map: existing owner to extend, disposition of adjacent contracts, or evidence that no owner
exists. A research sketch never establishes a new canonical owner.

## 8. Later Integration Handoff
Producer, persisted artifact/event, bridge, consumer, verification, surface — and which
implementation home consumes it: GY / Atlas for an existing gated capability, the proposed
H2 custody-runtime plan for the Group-B mechanical core, or an explicit existing canonical
owner. Do not append a Group-B runtime subsystem to GY merely because GY supplies or consumes
one of its artifacts.

## 9. Promotion And Kill Rules
Conditions for research_only / prototype_allowed / governed_allowed /
production_candidate / blocked / out_of_scope.

## 10. Open Questions For Consolidation
Conflicts with parallel tasks (name the live overlaps), duplicate abstractions, unresolved
dependencies, recommended consolidation owner.
```

### Operational closure addendum (mandatory for Group B; steps 3–5 for Group A)

1. **Boundary census** — the four-way verdict with owner mapping (existing / partial /
   missing-bridge / external-institution owner).
2. **Real operator workflow** — who actually does the work, in which systems, what happens
   on failure and after hours.
3. **A state machine** — states, transitions, clocks, owners, expiry, escalation, terminal
   states, reopening, public meaning.
4. **Typed artifacts** — candidate contracts + authority boundaries, not only
   recommendations.
5. **Edge-case fixtures** — happy path, missing evidence, late event, duplicate event,
   conflicting authority, owner unavailable, malicious actor, degraded mode, partial
   success, rollback, historical replay.
6. **Tabletop / fault injection** — kill a provider, delete a worker, send a duplicate
   amendment, trigger a mass invalidation, inject conflicting rules, recover and
   reconcile.
7. **Capstone linkage** — how the result plugs into the custody-cycle capstone
   (`OPS-R15`), not an isolated unit fixture.

Suggested completed-artifact naming: `docs/research/policy-operations/<task-id>-<short-slug>.md`.

## Pattern Pass

Relevant failure-pattern IDs: `P01`, `P02`, `P03`, `P04`, `P05`, `P07`, `P08`, `P09`,
`P10`, `P11`, `P12`, `P13`, `P14`, `P15`, plus `P16`–`P34` where a task touches universal
policy-design authority. Known risks: `P01` contract-only capability; `P02` mature fragments
without a custody bridge; `P03` internal custody state with no inspectable surface; `P05`/`P15`
prose/LLM/projection becoming authority; `P10` structural completeness instead of semantic
adequacy; `P11` a learning loop that remembers only failures/anomalies; `P12` Lex/Fabric/
Scientist producers resolving meaning only after emission; `P13` governance ritual (or an ERP
surface) out of proportion — **the identity decision is the P13 firewall at institutional
scale; respect its anti-roles**; `P14` inflating evidence by shared-anchor count.
Missing-capability labels: `implemented_but_not_orchestrated`,
`verification_missing`, `semantic_test_missing`, `surface_missing`, `producer_missing`,
`bridge_missing`, `contract_only`. **Acceptance signal:** the artifact answers "what is
safe to implement, what stays research-only, what should be blocked, what fixture
falsifies an overclaim — and what does PolicyOS own vs integrate here?"

## Post-Research Implementation Routing

Distillation decides implementation; this backlog does not. The default routing prevents
the active plans from becoming a new contract gravity well:

- **Group A (`INT-*`)** results become explicit research gates or bounded extensions of
  existing GY/Atlas tasks and canonical runtime owners. They do not create a parallel
  authority lattice or validator stack.
- **Group B (`OPS-*`)** results primarily shape a future dedicated **H2 Custody Runtime**
  implementation plan: long-lived case process, wake/recheck, invalidation/recompute,
  coordinated releases, legal sensing, refresh and resilience. GY supplies design/world/
  promotion artifacts and consumes revalidation results; Atlas projects custody state. The
  mechanical core is not inlined into either plan by default.
- **Group C (`PAO-*`)** results extend the PDC identity/export boundary and selected Atlas
  public/accountability surfaces; INTEGRATE/OBSERVE results land as evidence contracts, not
  newly-owned institutional functions.

Any exception must name the existing canonical owner, explain why a new implementation home
would be duplicative, and pass `P13`/`P27` review.

---

## Group A — Epistemic Closure (`INT-R*`) — 9 active

**Specific context.** Group A hardens the single-case machinery so it can be *operated and
exposed honestly*. Each result **gates a public/authority-bearing surface, not the
underlying mechanism** — the mechanisms exist or are in flight (N11/N12/DS4); these tasks
earn the right to expose them. All nine are custody-core by the signature rule: each
protects the validity of claims PolicyOS itself signs.

Execution clause for every `INT-*` row: inspect the GY plan (N9/N11/N12/N13a/N13b, CGF,
GY-PA1/2/3), the Atlas plan (DS4/DS9/DS12/DS16–18), distillation §6,
`src/polisyos/runtime/quality/construct_registry.py`, and
`src/polisyos/scientist/governance/continuous`. The **δ-bound is conditional on
obligation-completeness (P29 regress, not solved)** — never present "risk ≤ δ" as
unconditional; `INT-R1` bounds that conditional. Route the *legal* dimension of these
seams into `INT-R1/R5/R6/R8` (no separate Lex method wave).

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `INT-R1` | What bounded, checkable, honest form of "completeness" can be proven in an open world where unknown legal, normative, measurement, and implementation obligations may exist? | `ObligationCoverageEnvelope` (declared scope, searched sources, exclusions, unknown remainder, TTL) + `ValidatorGovernanceRecord` (rule owner, change process, independent validator check); statuses `bounded_complete`/`known_incomplete`/`open_world_unresolved` as **inputs to the one lattice**; challenger process + rollback/reissue on a missed obligation. | Mutation + metamorphic tests: **removing a decisive obligation, or a validator fault, must turn the δ-proof red.** | GY-N9/N11/N12; Atlas DS12/DS17/DS18. Without it, "risk ≤ δ" is mathematically correct but institutionally hollow. |
| `INT-R2` | How should PolicyOS model acquisition of things that are **not data** — grounding relation, estimand binding, owner writability, legal mandate, normative authorization, implementation-capacity evidence, competent human decision, independent audit? | `GapAcquisitionCase` discriminated union: per type — who may produce, what counts as sufficient acquisition, what admission proof is required, what authority ceiling results, how re-entry works, what is `deeper_terminal` (not "almost success"). | **Adding many relevant rows must NOT close a relation gap, an estimand gap, or a mandate gap** (the N13a structural-gap finding). | GY-N7/N13, CGF CG5, world growth; Atlas DS7/DS15. Makes "refusal-with-a-path" universal. |
| `INT-R3` | Can a real operator, under time pressure, act correctly when shown a weakest link, a set-valued value, `unknown`, `incomparable`, a δ-budget, a stale epoch, a quarantine, and an acquisition route? | `AuthorityUIComprehensionBenchmark` measuring behavior, not preference: found the true blocker; `unknown` ≠ zero ≠ missing; `incomparable` = no-admissible-ranking; refused stale/quarantined; small δ-budget ≠ high value; chose acquisition/escalation/abstention correctly — under keyboard-only, screen-reader, low-numeracy, time-pressure. | Metrics `false_action`, `false_pass`, `missed_blocker`, `unsafe_override`, time-to-correct, confidence-vs-correctness calibration. | DS4/DS6/DS7/DS9/DS15–18. A **mandatory task input**, not a post-hoc usability test. |
| `INT-R4` | What causal-safety case is required for learning after deployment under performative and endogenous feedback? **(absorbs `OPS-R7`: causal validity under sequential policy adaptations — versioned treatment, interference, stopping rules.)** | `DeploymentLearningSafetyCase`: identification under policy-induced feedback; separation of prediction-error / implementation-failure / measurement-change / behavioral-response; delayed & censored harm; interference; negative controls & sentinel populations; **ban on self-confirming edges**; rollback/freeze/reissue/withdrawal; exploratory→confirmatory promotion; versioned-treatment evaluation under sequential adaptation. | **Adversarial:** model recommends a policy → the policy changes data availability → the system accepts the new data structure as confirmation of its own model. | Binding research gate for GY O1/O3 and N12, jointly with `OPS-R5`; Atlas DS13/DS14/DS18. The only truly greenfield zone. |
| `INT-R5` | How can PolicyOS prove that a specific person or collegial body had the right to make **this** decision, in this role, jurisdiction, amount, time window, and conflict-of-interest posture? | `DecisionAuthorityGraph` + `DelegationValidityCertificate` computed **before** action: temporal & subject-matter delegation, quorum & co-sign, separation of duties, recusal/COI, acting appointments & succession, subdelegation limits, expiry & emergency authority, revocation mid-operation, cross-agency acceptance, consultation vs recommendation vs approval vs binding decision. | Adversarial fixtures: self-approval, expired delegation, wrong forum, quorum loss, post-hoc authorization. | **Must land before** GY-PA2 or its Atlas DS9/DS14 consumers close; also feeds DS20 vocabulary and acquisition approvals. `PAO-R4` remains the distinct individual-use firewall. |
| `INT-R6` | How can PolicyOS prove that `uk`/`en`/legacy translations preserve **authority semantics**, not just structural catalog parity? | `MultilingualAuthorityEquivalenceProtocol`: canonical semantic IDs (not string compare); versioned controlled glossary; source-language anchor for legal claims; translation entailment + scope preservation; **ban on semantic status upgrade**; human adjudication for high-stakes copy; regression fixtures with negation, exceptions, temporal scope, numeric uncertainty; plain-language adaptation checked separately. | **Falsify:** `limited` → "confirmed with caveat"; `may_not_use_for` → optional recommendation; `stale`/`superseded`/`withdrawn` conflated. | DS4/DS5/DS11–13, Lex projections, MACHINE twins. **Dependency:** the unratified language policy (Atlas D4) — flag it. |
| `INT-R7` | What is the full lifecycle of a public cryptographic proof, beyond "what to sign with"? | `PublicVerificationProfile` + threat model: key rotation & compromise recovery; revocation & temporal validity; archival verification after rotation; anti-equivocation / split-view / transparency log; algorithm agility; offline verification; signature binding to audience/jurisdiction/epoch/authority-boundary; privacy-safe addressing; citizen-accessible verification UX; and the **minimum 10–30-year preservation profile required before the first public signature** (format/algorithm migration, retained verification material, custody owner, recovery drill). This absorbs the before-publication core of deferred `PAO-R38`; extended preservation research may still activate from its findings. | Frozen suite: forged packet, replaced payload, revoked key, stale certificate, split-view server, replay under wrong audience, compromised signer, and archival verification after algorithm/key rotation. | Atlas DS12/DS13. **Close before the first public record.** Consolidate archive/DR mechanics with `OPS-R14`. |
| `INT-R8` | What is lost in summary/compression, and what can be reconstructed by combining PUBLIC, REVIEWER, MACHINE views, diffs, timestamps, and provenance snippets? | `CompressionLossReceipt` (retained vs dropped claims, limitations, attacks, denied-uses, counterevidence); semantic parity full-vs-summary; the minimum a summary must retain; typed `lossy_but_safe` / `blocked_material_omission`; cross-view privacy analysis; a **composition budget** for repeated disclosures; no reconstruction via diff/hash/ordering/timing; screenshot/deep-link/export threat model. | The named G6 gap (no compression ledger); a summary that dropped a retained-limitation must fail red. | **Binding research input before** GY-PA3 and Atlas DS12/DS14 close; also feeds Atlas DS13, public exports, and handoffs. The research defines the safe-loss semantics; the producer does not pre-decide them. |
| `INT-R9` | How does PolicyOS prove the **first** positive governed promotion without cherry-picking — and without promising a positive result exists? | `FirstPromotionEvaluationProtocol`: pre-registration of case & criteria; **no selection after seeing the result**; independent adjudicator; public regression + sealed holdout; adjacent unseen case; no-case-specific-code check; external-validity boundary; source-flip and obligation-removal falsifiers; pre-declared NO-GO reasons; **ban on optimizing `useful_design_rate`.** | **Falsify:** a case chosen after its result was seen, or with hand-coded bindings, passes. | GY-N9/N11/N12; Atlas DS12. Cheap now; write early, fires late. |

---

## Group B — The Custody Runtime (`OPS-R*`) — 11 active

**Specific context.** The custodian's mechanical core. GY honestly terminates at
`acquisition_required` — but that is a *search terminal*, not a durable
suspension-and-resume contract; refusal-with-a-path is refusal-with-a-dead-end unless the
case can wait months and wake correctly. The control plane knows only
`pending|running|completed|failed`; Scientist resume protects a computational workflow,
not a policy case; Decision-Validity/W9/W10/Fabric are strong fragments. Group B researches
the missing **custody runtime**: a case as a **long-lived process, not a run**. Most
mechanisms here are solved engineering patterns — durable workflows separate the live
process from the executing worker and version worker code so an in-flight process never
resumes under incompatible logic; incremental engines invalidate reverse dependencies and
prune unchanged branches; streaming systems own event-time/watermarks; versioned catalogs
own shadow/governed heads. **The research content is the authority-delta**: what these
patterns lack when the thing being suspended, recomputed, or versioned is *authority*.

Execution clause for every `OPS-*` row: inspect the durable control plane, Scientist
checkpoint/resume + workflow fingerprint, Decision-Validity, W9/W10, Fabric
watermarks/cursors/CDC/bitemporal, GY-N12 epochs, GY §3.5.12, the Lex legal batch,
`docs/reference/operations/retention-and-recovery.md`. Apply the operational closure
addendum in full. An authority recheck at wake is not a state restore — identity, tenant,
delegation, and permissions must be re-proven, not assumed.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `OPS-R1` **[adapt]** | Durable suspension and resume for a Policy Design Case (adapt the durable-workflow pattern; research = the authority-delta). | `CaseSuspensionRecord` (world-version vector, snapshots, open obligations, budgets spent/remaining, wake conditions, deadlines/escalation, owner, delegation refs, allowed resume modes, required reauthorization, public posture during wait); **typed wake conditions** (data watermark, admitted artifact, legal release, human decision, window closed, review due, incident, appeal upheld, rule/validator change, delegation/license expiring); **resume gates** (integrity, identity/authority, workflow-compat, world-compat, obligation, impact, budget, freshness) → `CaseResumeReceipt` (what woke it, what was reused/stale/invalidated/recomputed, which boundaries downgraded, what differs from pre-pause). | Worker/locks released during suspension; wake by event. **Falsify:** `resume()` without the gates; a *similar* artifact treated as satisfying the specific open obligation. | Future H2 custody-runtime plan over the existing control plane; consumes GY `acquisition_required`; Atlas DS15/DS18 project wait, wake and revalidation state. |
| `OPS-R2` **[adapt]** | Safe selective invalidation and minimal recompute (adapt the incremental dependency-engine pattern). **(absorbs `PAO-R25` as its scale rider: the calculus must be designed mass-fanout-ready — prioritized queue, backpressure, dedup, public-freeze scopes — even though the fleet scheduler itself is deferred.)** | Two distinct graphs — **artifact dependency** (technically derived-from) and **authority dependency** (which evidence permitted which use; an artifact can be payload-unchanged yet authority-lost: source retracted, rights lapsed, calibration expired, competent authority changed, validator unsound); impact output = `payload_recompute_set` / `authority_revalidation_set` / `public_notice_set` / `human_review_set` / `historical_only_set`; **change pruning** (stop downstream when the recomputed value is semantically unchanged). | All real dependencies registered (config, rule/model version, authority policy are inputs; runtime clock is not). **Falsify:** a hidden unregistered dependency corrupts the incremental result; authority-loss-without-payload-change is missed. Periodic incremental-vs-clean-rebuild parity. | Future H2 custody-runtime plan over the content-addressed graph; extends GY-N12 invalidation; Atlas DS18/DS13 project affected scope and public history, while DS16 renders derived-data impact. |
| `OPS-R3` **[adapt]** | Migration of dormant cases across code, schema, rule, and validator versions (adapt workflow-versioning). **(absorbs `PAO-R26`: the in-flight migration dossier.)** | Pinning/migration protocol; four resume modes `resume_under_original_environment` / `migrate_then_resume` / `replay_old_and_new_compare` / `refuse_incompatible_and_escalate`; `CaseStateMigrationDossier` (compatibility matrix, dual-read/write, migration invariants, rollback, old/new semantic comparison, authority downgrade, human-approval classes, **proof the migration did not rewrite historical meaning**). | **Falsify:** a dormant case silently resumes under incompatible logic; a migration changes a closed case's historical meaning. | Future H2 custody-runtime plan extending the Scientist workflow fingerprint and canonical rule/schema replay owners; Atlas DS18 projects migration/revalidation state. |
| `OPS-R4` **[adapt]** — **DELIVERED 2026-07-29** (`accepted_narrow_scope`), artifact `docs/research/policy-operations/ops-r4-temporal-semantics-for-policy-custody.md`, **adopted** as the Custody Time Model (`docs/system-design-decisions/policy-design-custody-time-model.md`). Result narrows this row: nine primitive temporal roles as a **sparse profile**, relations rather than clocks, explicit query coordinates rather than an overloaded `as_of`, family-native persistence with adapters, and the L0–L6 late-event ladder as **advisory** evidence whose final reaction the canonical claim consumer records. **`OperationalEventEnvelope` is REFUTED** as a universal persisted artifact (high semantic loss, very high P13 owner gravity, very high P27 owner-preemption); a thin transport header survives only at boundaries with proven duplication. | Temporal semantics for policy custody: event-time / process-time / legal-effective-time / observation-time, late data, deadlines (adapt event-time/watermark patterns). **(absorbs `PAO-R24`: `OperationalEventEnvelope` — dedupe identity, correction/revocation relation, lateness classes, duplicate/out-of-order/retro events.)** | The multi-clock model + watermarks + late-event policy (`ignore_for_closed_window` / `annotate_only` / `recompute_if_material` / `mandatory_revalidation` / `open_new_epoch` / `human_adjudication`); `OperationalEventEnvelope` (event/effective/published/observed/admitted/processing time, dedupe identity, correction relation, lateness class, allowed downstream actions). | Edge fixtures: duplicate amendment, correction-before-original, retried irreversible op, two workers waking one case, lost webhook found by census, retroactive effective date. **Falsify:** a late record silently changes a published result; the processing clock leaks into a content hash. | Future H2 custody-runtime plan extending Fabric watermarks and GY-N12; Atlas DS18 renders the one shared time semantics. |
| `OPS-R5` | KPI control and adaptation-mode governance — a KPI is a decision-linked contract, not a number with a band. **(absorbs `OPS-R6`: the adaptation ladder.)** Boundary: OWN the contract + diagnosis + response semantics; INTEGRATE data collection. | `KPIControlContract` (construct, definition version, lineage, unit/basis, aggregation, population/subgroups, baseline vintage, target type/band, leading/lagging/guardrail/diagnostic, lag/seasonality/revision policy, gaming risk, owner, decision rights, **pre-declared response table**); KPI-type separation (result / implementation / guardrail / leading / diagnostic / context / measurement-health) that **cannot be summed**; typed diagnosis before any policy change (data revision ≠ refutation; definition change = new semantic epoch; implementation failure ≠ theory failure; subgroup harm under good average = distributional review; unidentifiable cause = freeze auto-adaptation); the adaptation ladder observe→early-warning→diagnose→refresh→recompute→recalibrate→adjust-implementation→narrow-scope→partial-reissue→redesign→pause→rollback→terminate, gated by identification strength, harm-of-waiting vs harm-of-premature-change, reversibility, measurement confidence, VOI, legal deadlines, human authorization. | Anti-Goodhart tests; **falsify:** a threshold crossing auto-changes policy without typed diagnosis; a KPI or plan edited after outcomes are seen (plans/protocols must be timestamped pre-observation). | DDM/`MonitoredMetric`; `DecisionReissuePlan`; GY value gate. **Joint binding input with `INT-R4` before GY O1/O3 close**: monitoring signals must pass typed diagnosis before they update an effect posterior or world edge. |
| `OPS-R8` **[adapt]** | Coordinated `WorldRelease` — a governed vector of compatible snapshot versions across legal / data / knowledge / construct / calibration / intervention / rulebook / validator layers (adapt versioned-catalog branching). | `WorldRelease` (version vector, valid/transaction time, compatibility matrix, known gaps, authority boundary, supersedes); lifecycle `candidate → shadow → benchmark_passed → governed → superseded → archived`; atomic head swap; old tags retained for replay. | **Falsify:** a "latest-of-each-layer" combination that was never verified compatible decides a case (new law + old dataset + new calibration + old construct mapping may never have existed as a verified state). | Fabric bitemporal branches; GY-N12 epochs. |
| `OPS-R9` **[adapt]** | Derived-data refresh orchestration — how derived series live after first build (adapt materialization/refresh patterns). | `DerivedRefreshPlan` (recipe, input-release vector, refresh mode, partition strategy, late-data policy, revision-materiality rule, affected consumers, cost, priority, output epoch, clean-rebuild audit schedule); partition refresh vs full backfill; eager vs lazy; auxiliary-input skew; multiple admissible basis variants; old-derived-artifact validity for historical decisions; stampede control. | **Falsify:** one CPI revision triggers an unbounded recompute stampede; a stale derived artifact feeds a current decision; a backfill silently rewrites a historically-used series. | GY §3.5.12; the deferred transform planner. |
| `OPS-R10` | Continuous legal-corpus operations — a weekly delta release, not a one-off Legal-KG build. Boundary: OWN (Lex is the system's sensory organ; living law = living signatures). | The 9-step weekly release: immutable intake (source identity, fetch/publication time, hashes, signatures, rights) → identity/version resolution (new act / new edition / amendment / corrigendum / repeal / consolidation / duplicate / metadata-only) → delta extraction → temporal & authority resolution (adoption/publication/effective dates, transitional provisions, retroactivity, competent body, territorial scope, binding force) → **shadow legal branch** → differential benchmarks (new/changed/lost provisions, amendment-target + reference resolution, temporal inversions, false-change rate, known-query regression, unexpectedly-changed applicable authority) → governed `LegalWorldRelease` → impact fan-out (affected cases/claims/obligation atoms/public records/monitoring contracts) → typed case response (cosmetic renumbering → annotation only; amendment w/o applicability change → no authority change; new applicable exception → mandatory revalidation; repeal → freeze affected promotion; new delegation → competence recompute; future-only change → historic cases stay replay-valid). | **Falsify:** cosmetic renumbering triggers mass revalidation; a repeal fails to freeze affected promotion; the amendment detector misses a consolidation. | Lex legal batch (builds the GL-plan-excluded amendment detector + reference resolver semantics); GY-N12. |
| `OPS-R11` | Jurisdiction/source-pack promotion — a generic `JurisdictionPack`, and never a silent Ukraine fallback. Boundary: OWN (data-driven jurisdiction growth is the universality thesis). | `JurisdictionPack` (identity & territorial graph, official publishers/feeds, source authentication, identifier system, document families, authority hierarchy, competent-body registry, binding-force taxonomy, time semantics, amendment/repeal/consolidation rules, reference grammar, authoritative-language rules, pre-emption/conflict, delegation/subdelegation, appeal relations, licensing, benchmark corpus, review owner, promotion/rollback rules); municipal variant (territorial boundaries over time, council vs executive acts, delegated vs own powers, official publication rules, boundary changes); international-organization variant (treaty/protocol/resolution/binding-decision/recommendation/model-law/standard; membership, signature, ratification, reservations, entry-into-force for this state, direct applicability, domestic incorporation, withdrawal). | **Falsify:** an unknown jurisdiction silently handled as Ukraine (the current fallback); "international-org source" treated as proof of applicability. ELI/Akoma Ntoso are interoperability, not competence. | Jurisdiction registry (UA/EU only); Lex; `OPS-R10`. |
| `OPS-R14` | Custody-grade resilience and expiring authority. **(re-scoped to protect OUR signatures; absorbs `PAO-R28`: expiring operational authority as watched dependency events. Institutional-scale continuity/DR → deferred with `OPS-R12`.)** | RPO/RTO per custody class (shadow / governed / published / active-incident / appeal-relevant / legal-release / public-verification-log); long-term replay of signed records; legal-hold override semantics for our records; **watched-dependency records** for every expiring right (DSA, API credential, model license, audit right, delegation, reviewer certification, encryption cert, consent, budget authority, contract, jurisdiction-pack review): expiry date, renewal owner, lead time, renewal evidence, grace policy, failure consequence, affected-case query, public effect; disaster fixtures (CAS restored but control DB not; duplicate control event; duplicate wake; world head advanced but fan-out incomplete; signing-key compromise; vanished official source; 10 000 cases stale at once). | **Falsify:** an expiry surfaces as a sudden runtime error instead of a scheduled dependency event; a runbook is accepted as DR closeout evidence without a drill. | retention-and-recovery runbooks; `INT-R7` (key lifecycle overlap). |
| `OPS-R15` — **DELIVERED 2026-07-28 and INDEPENDENTLY AUDITED** (`docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md`; audit at `docs/research/policy-operations/audits/ops-r15/`). **SCORING IS BLOCKED under ratified `S0-K14`** (`docs/system-design-decisions/stage0-custody-kernel-ratification.md` §4.2 and §5): no passage may be claimed until **`S0-GAP-02`** delivers an oracle and declarative evaluator that do **not** share admission, reducers, dependency traversal, or status projection with the implementation — a same-code rebuild proves consistency only. **Designing** the capstone under `S0-K13` (observable semantics, not internal architecture) and `S0-K15` (anti-memorization, preserved dissent) is **not** blocked and proceeds now. Under `S0-K16`, any future passage supports only that the named implementation, revision, environment, fixture population, and evaluator version satisfied the tested predicates. | **The custody-cycle capstone benchmark** (design FIRST — it shapes the other contracts). **(absorbs `PAO-R42`; administrative events enter only as integrate-evidence.)** | A frozen 18–24 month simulated calendar: case designed → `acquisition_required` → suspended → world events arrive (partial data; retroactive data revision; metric schema change; new norm published then in force; workflow+validator update; responsible-body change; KPI early-warning; subgroup harm; **appeal outcome arrives as integrate-evidence**; source outage; DSA expiry; new municipal jurisdiction via data-only pack; another policy shifts the baseline) → typed wakes → minimal recompute → revalidation → partial reissue → supersession-or-confirmation. Success criteria: `lost_case_state = 0` · `stale_public_shown_as_current = 0` · `unauthorized_authority_upgrades = 0` · `silent_historical_rewrites = 0` · `missed_affected_cases = 0` · `duplicate_irreversible_actions = 0` · **`out_of_boundary_actions_attempted = 0`** (the system never tries to execute administration) · reused-artifact share · minimal-recompute share · clean-rebuild equivalence · time-from-world-event-to-correct-revalidation · consumed-evidence binding correctness (proof-of-service consumed and bound, never produced) · historical replay · DR recovery. | The capstone IS the falsifier battery for Group B. | Consolidates the wave; feeds GY Phase-6/7 verification and Atlas DS15–DS18. |

---

## Group C — Boundary & Identity (`PAO-R*`) — 4 active

**Specific context.** Under the ratified identity, most Rev-1 Group-C tasks concern
functions PolicyOS **integrates or observes** — their research needs institutional facts
(which partners exist, which shims institutions need) that only a real pilot produces;
they are preserved in the deferred registry with typed activation triggers. Four tasks
remain active because they are custody-core: the identity spine above cases, the boundary
census itself, the individual-decision firewall (ours by ruling), and correction of our
own published records.

Execution clause: inspect `docs/system-design-decisions` (identity decision first), the
failure-pattern register, `src/polisyos/pdc`, `src/polisyos/runtime/quality`,
`src/polisyos/core/audit`, `src/polisyos/lex`, `src/polisyos/ddm`, the PolicyPortfolio IR,
and relevant fixtures. Keep the five lifecycles distinct. Jurisdiction-neutral contract +
one example mapping.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `PAO-R0` | Stable identity above a single Policy Design Case — a `PolicyMatter` that survives pilots, enactment, scaling, splits, merges, renaming, successor instruments. Boundary: OWN, now (retrofit is brutal). | `PolicyMatter` entity + episode graph (design → enactment → implementation → evaluation → incidents → public records → successor/split/merge lineage); new-version-vs-new-policy distinction; historical-continuity rules; migration of existing `case_id`/`decision_lineage_key`; negatives against merging distinct initiatives; plus a `PolicyMatterCompatibilityFreeze` stating which identity fields/extension points current work must preserve so no new custody artifact irreversibly assumes `case_id` is the lifetime identity. The freeze is a research guard, not a final code contract. | **Falsify:** two unrelated initiatives silently merge; a pilot→national continuation is treated as a brand-new policy; a newly proposed custody artifact cannot attach to a future matter identity without historical rewrite. | PDC lineage; every custody artifact hangs off this identity. Publish the compatibility freeze with the Stage-0 anchor packet before the parallel wave. |
| `PAO-R1` | Boundary census execution — the per-function `OperationalBoundaryDecision` register under the **ratified** four-way test (the meta-question is answered; this task applies it function-by-function). | The register: for each administrative/operational function — the verdict, the existing/partial/missing/external owner, and for every INTEGRATE/OBSERVE row the **typed evidence contract** (interface, provenance, versioning, fail-closed absence behavior) PolicyOS owns in place of the function. | **Falsify:** an INTEGRATE row without a fail-closed absence behavior; an OWN verdict that contradicts an identity-decision §6 ruling without a flagged consolidation question. | The adjudication baseline for all future plans and the deferred registry's activation reviews. |
| `PAO-R4` | The policy-to-individual-decision firewall — ours by ruling (§6): policy-level output must never silently decide an individual case. | The handoff contract + prohibited-individual-use matrix: which artifact classes may cross toward case-management systems, in which form (aggregate/anonymized/rule-level), with which `may_not_use_for` (individual eligibility, individual sanction, individual risk-scoring); detection semantics for violations; the returning-evidence interface (what case systems report back as implementation evidence). | **Falsify:** a policy-level statistical rule is consumed as an individual eligibility rule and no gate goes red. | PDC export gates; runtime quality; DS12 public boundary. |
| `PAO-R36` | Public correction and durable notice **for OUR published records** (re-scoped: custody of our own signatures; third-party misinformation monitoring → deferred rider). | The correction fan-out for owned records: canonical record corrected → public notice → API version/supersession → cache invalidation → subscriber notification → machine-readable correction feed → archive linkage → translation-parity update; handling for corrections that increase risk, legally-significant old versions, records signed with since-revoked keys. | **Falsify:** language versions of one correction diverge; a superseded record renders as current anywhere we control; a correction silently rewrites instead of superseding. | Atlas DS12/DS13; `INT-R7`; M36/M25 (supersede-not-silent-edit). |

---

## Group D — Stage-0 Additional Research (`S0-GAP-*`) — 1 active

**Specific context.** Stage 0 delivered its three anchors, consolidated them into the
sixteen-statement custody kernel, and named exactly two gaps that the anchors themselves
could not close. **`S0-GAP-01` is delivered** (`accepted_profile_with_owner_role_only`;
artifact `docs/research/policy-operations/s0-gap-01-minimum-policy-subject-reference-and-semantic-owner-decision.md`)
and its naming is carried into ratified `S0-K01`. **`S0-GAP-02` is commissioned by the
ratification act** (`docs/system-design-decisions/stage0-custody-kernel-ratification.md` §5)
because ratified `S0-K14` blocks OPS-R15 scoring until it exists — this is the path that
keeps the block a refusal *with a path*. Its full specification is already written in
`docs/research/policy-operations/consolidation/stage0/stage0-additional-research-register.md`;
the row below is the dispatch summary, and the register is authoritative on detail.

| ID | Independent research task | Minimum required output | Benchmark proxy / falsifier | Later integration target |
| --- | --- | --- | --- | --- |
| `S0-GAP-02` | **Independent custody-benchmark oracle and evaluator architecture.** How can an implementation-independent, machine-readable and challengeable oracle establish acceptable custody semantics while keeping expected results sealed, preserving ambiguity and dissent, preventing shared-code circularity, and resisting fixture memorization? OPS-R15 supplies prose inputs and *implementation-visible expected traces* but no independent oracle, reducer, evaluator, sealing protocol, access model, or executable corpus. Relabelling the report as blocked does not create independent semantic truth. Required comparative models: a separately implemented declarative reducer · a property/predicate evaluator without the full reference runtime · dual independent evaluators with disagreement adjudication · a same-code rebuild retained only as a **diagnostic control**. | Machine-readable public schema + input-only fixture corpus; sealed expectation format admitting alternatives; independent-evaluator interface and code-independence rules; clean-rebuild reference semantics and equivalence policy; authority-scenario axioms and a human-adjudication protocol; commitment / custody / access-log / rotation / challenge / supersession protocol; adjacent-case and metamorphic mutation generator; reproducibility receipt and bounded-claim template. | **Falsify:** the evaluator imports implementation admission, reducers, dependency traversal, or status projection; implementation-visible files expose expected actions or labels; an ID-renumbered or adjacent unseen case changes the outcome without a semantic reason; a **seeded shared reducer fault** passes both incremental and clean-build checks; an oracle correction silently changes a prior scored run; reviewer conflict, abstention, or disagreement is discarded. | Unblocks `OPS-R15` **scoring** only. Does **not** authorize a production benchmark runner, legal certification, production readiness, RPO/RTO commitments, or external institutional authority. Owner: an independent benchmark-governance lead with a **separate** oracle custodian and domain reviewers. |

---

## Deferred Registry (36 IDs — typed activation triggers, specs preserved)

Deferred ≠ rejected. Each row keeps its Rev-1 topic and boundary class and gains a typed
**activation trigger** — the wake condition under which it becomes dispatchable (the same
discipline the custody runtime applies to cases). At activation, re-adjudicate against the
identity decision §6 and the then-current `PAO-R1` register; full Rev-1 specs are in git
history of this file.

| ID | Topic | Boundary class | Activation trigger |
| --- | --- | --- | --- |
| `OPS-R12` | Fleet scheduling & priority function for many live cases | OWN later (custody at scale) | fleet formation: >~50 concurrently-governed cases |
| `OPS-R13` | Cross-policy interaction / live policy stock | OWN later | ≥2 deployed policies sharing population/budget/capacity |
| `PAO-R2` | Omnichannel service-episode continuity | INTEGRATE | first pilot with a service-delivery partner |
| `PAO-R3` | Whole-journey accessibility & language operations | INTEGRATE (our surfaces stay in Atlas scope) | first pilot serving citizens directly |
| `PAO-R5` | Administrative clocks, tolling, statutory deadlines | INTEGRATE (consume) | first pilot inside an administrative procedure |
| `PAO-R6` | Notice, delivery, proof-of-service | INTEGRATE (consume proof-of-service as evidence) | first pilot with legally-effective notices |
| `PAO-R7` | Deadline-breach consequences & remedy | INTEGRATE | with `PAO-R5`/`R6` |
| `PAO-R8` | External legal capacity, representation, identity continuity | INTEGRATE (`INT-R5` covers internal rights now) | first pilot with external participants |
| `PAO-R9` | Operational redress & remedy execution | INTEGRATE (cascade ingestion already core via M36) | first real appeal-body partner |
| `PAO-R10` | Records schedule & disposition authority | INTEGRATE (our records' retention partly in `OPS-R14`) | first pilot in a records-regulated institution |
| `PAO-R11` | Disclosure / FOIA / subject access & redaction | INTEGRATE | first disclosure demand on a pilot |
| `PAO-R12` | Erasure, correction, downstream propagation (personal data) | INTEGRATE | first pilot processing personal data at scale |
| `PAO-R13` | Legal hold & litigation preservation | INTEGRATE (hold on OUR records in `OPS-R14`) | first litigation touching a pilot |
| `PAO-R14` | Design-to-enactment fidelity | OWN-adjacent (fidelity deltas are evidence) | first PolicyOS design reaches enactment |
| `PAO-R15` | Enactment-to-service-configuration fidelity | INTEGRATE | first enacted design in service delivery |
| `PAO-R16` | Street-level discretion & local variance | OBSERVE | first multi-office deployment |
| `PAO-R17` | Shadow systems & workaround discovery | OBSERVE | first multi-office deployment |
| `PAO-R18` | Fiscal authority, appropriation, budget cycles | INTEGRATE | first funded pilot |
| `PAO-R19` | Procurement & supplier performance lifecycle | INTEGRATE | first procured dependency in a pilot |
| `PAO-R20` | Payments, reconciliation, clawback, fraud-control effects | INTEGRATE | first payment-bearing pilot |
| `PAO-R21` | Physical delivery & geographic capacity | INTEGRATE | first physical-delivery pilot |
| `PAO-R22` | Access, take-up, administrative burden | INTEGRATE (denominator evidence into ex-post value) | first deployed policy with participants |
| `PAO-R23` | Enforcement & discretion operating model | OBSERVE/OUT | first enforcement-domain pilot |
| `PAO-R27` | Executable dependency exit & substitution drill | INTEGRATE (theory done in CPA-R13) | first governed external provider in production |
| `PAO-R29` | Interagency handoff & reliance | INTEGRATE | a second institution relies on our records |
| `PAO-R30` | Live policy stock (consolidate with `OPS-R13` at activation) | OWN later | same trigger as `OPS-R13` |
| `PAO-R31` | Mandate & institutional transition | OBSERVE (succession freezes/reassigns our authority) | first pilot spanning an institutional change — or earlier if one occurs |
| `PAO-R32` | Degraded, manual, emergency operations | INTEGRATE/OWN-partial (what may WE honestly display when degraded) | first operational deployment |
| `PAO-R33` | Institutional gaming & policy capture | OBSERVE (KPI-gaming tests live in `OPS-R5` now) | first pilot with adversarial stakeholders |
| `PAO-R34` | Compartmented / classified / privileged evidence | OWN-partial (sealed-verifier receipt shape) | first case with sealed decisive evidence |
| `PAO-R35` | Protected disclosure / whistleblower lifecycle | OUT/INTEGRATE | institutional demand |
| `PAO-R37` | Policy experiment & adaptive rollout safety | OWN-adjacent (`INT-R4` covers the learning core now) | first adaptive/randomized pilot design |
| `PAO-R38` | Extended long-term preservation beyond the minimum `INT-R7` public-verification profile (10–30 yr institutional custody, migrations, archive succession) | OWN (custody over decades); the before-first-record minimum is active now inside `INT-R7` | `INT-R7` identifies unresolved extended-preservation questions, or the first public-record program requires institution-specific archival arrangements; it must not delay defining the minimum until after publication |
| `PAO-R39` | Total lifecycle operational cost | OWN-adjacent (GY §3.5.7 covers compute now) | fleet formation |
| `PAO-R40` | Horizon signals & unknown-event admission | OWN-adjacent (foresight intake shape) | post-pilot |
| `PAO-R41` | Operational rule-conflict & control debt | OWN (our own controls' coherence; extends W10 Net-MAV) | W10 closure, or the control inventory crossing ~200 governed rules |

## Priority And Sequencing (first ordering, not a binding schedule)

1. **Stage 0: `PAO-R0` + `PAO-R1` + `OPS-R15`** — freeze the shared identity/
   compatibility anchor, boundary-register shape, and custody-capstone vocabulary before
   the parallel wave. The capstone is designed FIRST so it shapes every Group-B dossier.
2. **`INT-R1` + `INT-R9`** — the δ-conditional and first-promotion protocol are cheap now
   and must exist before the first positive candidate is inspected or public claim is made.
3. **`INT-R5` + `INT-R8` + `PAO-R4`** — immediate gates for already-planned delegation,
   compression, human-decision, agent and export work. Research must lead GY-PA2/GY-PA3 and
   their Atlas consumers, not validate their contracts post hoc. Start `INT-R7` in this wave
   because key/archive lifecycle has a long lead time and gates the first public record.
4. **`OPS-R1` / `OPS-R2` / `OPS-R8`** — the suspension/recompute/world-release spine for
   the future H2 custody-runtime plan.
5. **`OPS-R4` / `OPS-R10` / `OPS-R11`** — one time semantics and the living legal world.
6. **`INT-R2` / `INT-R3`** — generalized acquisition and operator-action safety; `INT-R3`
   must inform the DS6 comprehension instrument before interactive authority surfaces claim
   stability.
7. **`INT-R4` + `OPS-R5`** — joint research gate before the deployed-effect updater or
   world-model write-back closes: performative causal safety plus KPI diagnosis/adaptation.
8. **`OPS-R3` / `OPS-R9` / `OPS-R14` / `PAO-R36`** — remaining custody mechanics and
   public-record continuity; consolidate `OPS-R14` with `INT-R7` rather than duplicating
   key/archive rules. `INT-R6` starts after the language-policy ratification it depends on.

Deferred rows are not scheduled — they activate by trigger and are re-adjudicated at
activation.

## Completion Ledger

Stage 0 is delivered, independently audited, consolidated, and **ratified**. The research
branches were merged into `main` on 2026-08-02 byte-identical: their `research_only`
standing is changed by the appended ratification record, never by rewriting them
(`S0-K08` applied to ourselves).

| ID | Title | Status | Result type | Artifact path | Distilled |
| --- | --- | --- | --- | --- | --- |
| `PAO-R0` | Policy-matter identity & episode graph | **delivered + audited** | `accepted_narrow_scope` (name superseded by `S0-GAP-01`) | `docs/research/policy-operations/stage0/pao-r0-policy-matter-identity-and-episode-graph.md`; audit `docs/research/policy-operations/audits/pao-r0/` | ratified as `S0-K01` (amended) / `S0-K02` |
| `PAO-R1` | Operational-boundary method & evidence-interface census | **delivered + audited** | `accepted_narrow_scope` (method, not a production register) | `docs/research/policy-operations/stage0/pao-r1-operational-boundary-method-and-evidence-interface-census.md`; audit `docs/research/policy-operations/audits/pao-r1/` | ratified as `S0-K03` / `S0-K04` / `S0-K12` |
| `OPS-R15` | Custody-capstone semantic kernel & benchmark architecture | **delivered + audited**; **scoring blocked** (`S0-K14` → `S0-GAP-02`) | `accepted_narrow_scope`; not executable | `docs/research/policy-operations/stage0/ops-r15-custody-capstone-semantic-kernel-and-benchmark-architecture.md`; audit `docs/research/policy-operations/audits/ops-r15/` | ratified as `S0-K10` / `S0-K11` / `S0-K13`–`S0-K16` |
| `S0-GAP-01` | Minimum subject reference & semantic owner | **delivered** | `accepted_profile_with_owner_role_only` | `docs/research/policy-operations/s0-gap-01-minimum-policy-subject-reference-and-semantic-owner-decision.md` | carried into ratified `S0-K01` |
| `OPS-R4` | Temporal semantics for policy custody | **delivered + adopted** | `accepted_narrow_scope`; `OperationalEventEnvelope` refuted | `docs/research/policy-operations/ops-r4-temporal-semantics-for-policy-custody.md` | adopted as the **Custody Time Model**, `docs/system-design-decisions/policy-design-custody-time-model.md`; ratified in pair with `S0-K09` |
| `S0-GAP-02` | Independent custody-benchmark oracle & evaluator | **pending — commissioned 2026-08-02** | — | — | blocks `OPS-R15` scoring |
| … | … | … | … | … | — |

**Consolidation artifacts** (the synthesis layer over the three anchors) live at
`docs/research/policy-operations/consolidation/stage0/`: the consensus kernel, the
cross-audit finding matrix, the owner-contract and vocabulary map, the Wave-2 readiness
and sequencing report, and the additional-research register.

Status ∈ {pending, in_progress, delivered, distilled}. Result type ∈ {confirmed,
accepted_narrow_scope, refuted, blocked, deferred_open_problem}. On delivery, add the
artifact path; on distillation, fold the moves into
`deep-research-value-distillation.md` (§1 moves + a new §2 section) and route surviving
findings, after the §6 adoption gate, according to **Post-Research Implementation Routing**:
bounded gates/extensions into GY and Atlas, and the Group-B mechanical core into a proposed
dedicated H2 custody-runtime implementation plan — sequenced, as always, after in-flight work.

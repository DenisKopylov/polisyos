---
title: Policy Design — Universal Execution Topology (Blackboard Control Plane over an Artifact Graph)
status: draft design decision — execution-topology approach and vision
owner: team-architecture
created: 2026-06-14
decision_status: proposed — the execution model the universal policy designer runs on
supersedes: nothing (the three static scientist workflows become playbooks under this model)
informs:
  - docs/plans/active/layer3-slices/GY-engine-subordination.md
related:
  - docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md
  - docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md
  - docs/system-design-decisions/policy-design-best-in-class-operating-model.md
  - architecture/policy_design_case/layer3_gy_task0_audit/  (the Task 0 audit campaign)
---

# Policy Design — Universal Execution Topology

## What this document is

This is the **execution-topology decision**: the runtime model the universal policy
designer executes on. It is the approach and vision; the **big, detailed build plan,
full type schemas, task sequencing, and audit-finding integration live in**
`docs/plans/active/layer3-slices/GY-engine-subordination.md`.

It is governed by the constitution (`universal-policy-design-system-vision-and-organizing-rules.md`)
and realizes the D-series design (D3.2 design-search control plane, D3.8 promotion
gate, D2.6 composition) from `universal-policy-design-target-architecture-and-gap.md`.
It is grounded in the GY Task 0 audit, whose central empirical finding is that the
system is rich in components but poor in **seams (bridge), authority surfaces, and
route-admissibility tests** — so the execution model must make seams, authority, and
honest stopping first-class.

## 1. The core reframe

From **"a static DAG executed once over base inputs"** to **"a control loop that
repeatedly chooses and applies typed Operations to a growing, content-addressed
Artifact graph, until a typed termination."**

- **Unit of state = the Artifact** (content-addressed, immutable, provenance-carrying), not a node's transient output.
- **Unit of planning = the Operation** (a coarse "verb"), not a foundry method.
- **The three current scientist workflows** (`policy_design` / `causal_full` / `policy_verified`) are not three modes; they become **playbooks** (default trajectories) over Operations under one loop. Per the Task 0 workflow-mode analysis, `policy_design` is the design-complete near-superset and the only one already reaching this variable-search vision; the others are its evidence and legal layers.

Lineage: blackboard architecture (Hearsay-II), CEGIS/CEGAR (counterexample-guided
search), content-addressed build graphs (Nix/Bazel — artifacts as CAS nodes + replay),
contract/assume-guarantee composition, and the constitution's ports/adapters.

## 2. The two-ring waist (and why it *is* the agent boundary)

All execution speaks a small set of typed contracts in `pdc` (the sacred narrow
waist). They split into two rings, and the split is load-bearing:

- **Ring 1 — execution waist** (candidate/shadow path; **B / agent / engines MAY write**): `ArtifactRef`, `ArtifactEnvelope`, `PortSpec`, `OperationContract`, `OperationInvocationRecord`, `ApplicabilityResult`, `WorkspaceContract`, `SearchLedgerEvent`, `BudgetVector`.
- **Ring 2 — promotion / honesty waist** (authority path; **only A / verifier / governance MAY stamp**): `AuthorityBoundary`, `CertifiedOperationEnvelope`, `FrontierSnapshot`, `SearchExitContract`, `SearchIncompletenessRecord`, `ObligationRecord`, `SubDesignContract`, `CompositionCertificate`.

The invariant:

```text
An Operation can run, and an Artifact can enter the shadow frontier, with Ring 1 alone.
An Artifact cannot be PROMOTED, COMPOSED, or exit as GROUNDED without Ring 2 evidence
appropriate to its claim — and Ring 2 is not agent-writable.
```

This makes the agent-boundary decision **enforceable by construction, not by
convention**: the agent ("B") gets full freedom *inside* the loop — propose
operations, assemble method chains, call tools, request data, generate candidate
artifacts, explain rationale. It simply **cannot write Ring 2**. "Not a judge"
sharpens to **"not a self-promoter":** the agent may not assign authority, close an
obligation, mark search complete, or promote/compose. This is exactly the
constitution's two-speed path: Ring 1 = candidate breadth, Ring 2 = earned depth.

(Full schemas for all 17 contracts are in the GY plan. The load-bearing ones appear
below.)

## 3. The model

### 3.1 Workspace (the blackboard)

A run is a `WorkspaceContract` over: a **content-addressed Artifact graph** (CAS;
append-only; each `ArtifactEnvelope` carries producer-roots + lifecycle state +
optional Ring-2 stamps), a **ConstraintStore** (A-published constraints written
*before* generation), a **Frontier/ParetoArchive** (shadow best-so-far), an **Agenda**
(open `ObligationRecord`s), and a **BudgetVector**.

### 3.2 Operation (two levels in the contract, three in implementation)

The control loop chooses an `OperationContract` (a coarse verb: `DISCOVER`,
`ACQUIRE`, `BIND`, `TRANSFORM`, `ESTIMATE`, `SIMULATE`, `TRANSPORT`, `VERIFY`,
`REFINE`, `LOWER`, `DECOMPOSE`, `COMPOSE`, `ELICIT`, `ESCALATE`, `ABSTAIN`). An
operation declares typed `consumes`/`produces` `PortSpec`s, `formal_preconditions`,
`cost_model`, and `authority_transform`. Internally it may run a **`MethodPlan`** —
a chain of foundry methods, an LLM-agent plan, tool calls, or a human/data request —
bottoming out at atomic methods/tools. So:

```text
Workspace loop  →  Operation (waist verb)  →  MethodPlan (agent-assembled)  →  atomic method/tool
```

This is the answer to "an operation ≠ a foundry method": the tourism example
(discover attractions → can traffic be measured? → what data → where → acquire →
apply method) is one `DISCOVER`/`ACQUIRE` operation whose internal `MethodPlan` the
agent assembles. The **Operation registry is discovered, not enumerated** (Rule 12):
operations are derived from the engine registries (foundry methods, fabric
connectors, agent tools) + adapter conformance, never a hand-maintained list.

### 3.3 Control loop (RefinementPolicy)

```text
while not terminated:
  A: cluster producers refresh ConstraintStore                     # gate BEFORE generation
  proposals   = AgentOrPlanner.propose_operations(workspace, agenda, frontier, budget)
  applicable  = FormalGate.filter(proposals)                       # deterministic applicability (§4)
  ranked      = RefinementPolicy.rank_by_VOI(applicable, budget, stakes)
  if should_terminate(ranked, budget, frontier, search_quality):
      return SearchExitContract(terminal_state, frontier, incompleteness, budget, next_best)
  result = execute(ranked.best)                                    # Ring 1 artifacts, shadow
  append artifacts to CAS; append SearchLedgerEvent
  verdict = A.verify(result)                                       # A leads B
      promotable -> update Frontier (Ring 2 stamp)
      failed     -> emit CounterexampleRecord (typed class -> allowed moves)
  if result is SubDesignContract:   register child
  if result is CompositionCandidate: certificate = compose(...); promote-or-obligate
```

CEGIS/CEGAR-shaped: A constrains before, verifies after; failures become typed
counterexamples, not dead ends.

### 3.4 Two recursions

- **Problem decomposition** — `DECOMPOSE` spawns a child Workspace running the same
  loop; its result re-enters the parent as a single `SubDesignContract` artifact.
- **Operation expansion** — an Operation's `MethodPlan` is itself an agent-assembled
  sub-sequence of finer operations/methods.

Both bottom out at deterministic methods/tools behind the formal gate. This is what
makes the model **scale-invariant**: a local tourism policy is one Workspace, few
cycles, no decomposition; an international-accession program is a tree of Workspaces
(chapters), each iterating many cycles, with intermediate `SubDesign` artifacts that
later operations (`COMPOSE`, `TRANSPORT`, `REFINE`, `SIMULATE`) operate on — *operations
on derived artifacts, not only base data*.

## 4. A's in-loop role: the formal applicability gate (deterministic)

A's first, deterministic job in the loop is a **type system for methods/operations** —
not semantic judgment. It checks mechanically-checkable preconditions and emits an
`ApplicabilityResult` with actionable repairs. Example:

```text
difference_in_differences applicability: ≥2 groups? pre-period? post-period? panel index? outcome type?
continuous-method on integer outcome -> ApplicabilityError{repair: apply_count_model | to_rate | poisson}
```

This is **not** "is DiD optimal here" (a semantic/research judgment the agent or a
human does better). It is "is the method even validly applicable." Crucially, the
formal gate is **derivable from existing metadata** (foundry method `input_slots`/
dtypes/`requires`, IR contract assumptions), not hand-written per method — consistent
with Rule 12. Semantic firewalls mature **iteratively** on output artifacts; "what
exactly A must judge semantically" is deliberately deferred and learned from real
failures.

## 5. Decision 3 — Recursive SubDesign contract + port-authority composition

**Authority lives on ports, not on a sub-design as a whole.** A child Workspace
exports only a typed `SubDesignContract` (assume-guarantee style): `provides`/`requires`
`PortSpec`s, **each provided port carrying its own `AuthorityBoundary` +
`CertifiedOperationEnvelope`**, plus coupling declarations, producer-roots,
unresolved obligations, and its `SearchExitContract`. The parent may inspect the
child's internal trace for audit but may **compose only through ports** — no using
internals as an authority shortcut.

`AuthorityBoundary` is multi-dimensional, never a scalar: `authoritative_for` AND
`may_not_use_for` (both mandatory for promoted artifacts), a `grade`
(`measurement_rooted` / `transport_limited` / `simulation_only` / … /
`decision_admissible`), and an evidence basis (producer-roots, methods, calibration,
closed counterexamples).

Composition is a **three-stage operator**, not `min`:

1. **CouplingGate** — is this decomposition legitimate to compose at all? `independent` → compose by ports; `sequential` → downstream port capped by upstream port; `shared_resource` → requires a `CapacityAggregation` operation; **`feedback` → NOT independently composable** (local optima may be invalid) → either a joint sub-Workspace or an explicit `FIXPOINT/EQUILIBRIUM/SIMULATION` operation with its own capped authority; `unknown` → fail closed / discover coupling.
2. **PerPortAuthorityFlow** — authority flows directionally along dependencies via a **lattice `meet`**, not arithmetic min: `authoritative_for = ∩ upstream`, `may_not_use_for = ∪ upstream`, `envelope = ∩ envelopes`, `grade = weakest compatible`, `obligations = ∪ unresolved`. Empty `authoritative_for` ⇒ the port is **fail-closed** for that use, not "low score".
3. **EmergentClaimGrounding** — program-level claims ("accession-ready by year 10") are **not inherited** from parts; they require their own system-level grounding (system-dynamics / sequencing-consistency / capacity-aggregation / cross-chapter counterexample search), and their authority is capped by (weakest relevant part) ∧ (system-model authority) ∧ (coupling certificate). 30 well-grounded chapters do **not** yield a grounded program for free.

Output: a `CompositionCertificate` (coupling verdict + per-port authority flow +
emergent-claim grounding + unresolved obligations + verdict). **The promotion gate
forbids publishing a `PolicyProgram` without one.** (Note for the spec: the
`AuthorityBoundary` lattice — partial order on `authoritative_for`, total order on
`grade`, intersection on envelope — must be defined explicitly; this is the formal
obligation that makes `meet` well-defined.)

## 6. Decision 5 — Anytime SearchExitContract + typed incompleteness + VOI

Every Workspace (including children) terminates with a typed `SearchExitContract`,
never `success/failure`:

- **`BudgetVector`** is multi-dimensional (compute, acquisition $, expert-attention, calendar/deadline, novelty = cycles-without-improvement, recursion depth, **search_quality** = recall@known-seeds + freshness). Different budgets force different honest stops.
- **Typed terminal states**: `grounded_admissible`, `grounded_partial_admissible`, `frontier_stable`, `acquisition_required` (rung-7 plan with cost), `human_decision_required`, `grounded_abstention`, `search_ceiling_repair_required`, `budget_exhausted:<kind>`, `composition_invalid`, `a_spec_gap`, `recursive_blocked`.
- **`SearchIncompletenessRecord`** — the honesty artifact: what was generated/verified/promoted, operations/methods attempted vs not, source classes checked vs missing, recall@known-seeds + freshness, unresolved counterexamples/obligations/couplings, budget consumed/remaining, and `next_best_actions` with VOI/cost. This makes stopping an **audit object**, and the frontier **always anytime-emittable** as shadow with an honest boundary.
- **Domain-ceiling vs search-ceiling is a formal gate.** `grounded_abstention` is permitted **only if** recall@known-seeds ≥ threshold AND freshness ok AND no required source class missing AND no high-VOI untried move AND no verifier gap AND no core tool failure. Otherwise the terminal is `search_ceiling_repair_required` — the system may not say "no ground exists" when it means "we did not look hard enough." (This is the current GX `search_ceiling_repair_required` baseline, formalized.)
- **VOI is the single continue/stop/acquire currency.** Continue while `max(VOI(action)/cost(action)) ≥ threshold` and hard budgets allow; otherwise terminate with the matching typed state. When the best move is "buy data / run a pilot," that is `acquisition_required` with a costed plan (expected-value-of-sample-information anchor), not failure.

**3 and 5 are linked:** a `SubDesignContract` must embed its `SearchExitContract`, so
the parent cannot paper over a child's incompleteness — if a child returns
`acquisition_required`, the parent must fund it, cap the parent claim, or escalate the
obligation to a principal.

## 7. Replay — three honest levels (not byte-exact)

LLMs are necessary and non-deterministic; byte-exact replay is the wrong goal.

- **A. Exact replay** for deterministic operations (foundry/statistical/formal): contract+impl version, container digest, input/param hashes, seed → output hashes.
- **B. Trace replay** for agentic/tool/human operations: `OperationInvocationRecord` + `AgentDecisionRecord` (what the agent saw, candidates considered, selection, model+settings, tool calls + materialized evidence, human requests, produced artifacts).
- **C. Semantic/audit replay** for promoted artifacts: enough provenance + verifier results + authority boundary to **re-walk the audit trail and re-check the claim** — answering "why was this admissible," not "will the model emit the same token." `SearchLedgerEvent` is the spine (anchored on W3C PROV entity/activity/agent ≅ artifact/operation/agent).

## 8. Migration — build the loop directly; legacy is a quarry

Per the decision to build the target form directly (not an intermediate
conditional-DAG step):

- Build the loop fresh on a **minimal vertical slice** (one Workspace; Operations `DISCOVER/ACQUIRE/BIND/ESTIMATE/VERIFY/REFINE/LOWER`; one tourism/local-development case) — right form, small scope.
- Legacy DAG nodes become **`LegacyNodeAdapter`s** → registered Operations (declare ports/preconditions/authority).
- The three workflows become **`Playbook`s** (default trajectories) the loop may follow and **deviate from** on counterexample / missing-data / low-authority / higher-VOI alternative.
- `policy_design/search.py` generalizes into the control loop; `iteration_state_machine` into the loop state machine; `ResearchDAGBuilder` into programmatic trajectory assembly; CAS + `artifacts_index` into the typed artifact graph. Engines stay below the waist; Operations are §7 adapters (pattern `ir_analytics_bridge`).

## 9. Relationship to the constitution and D-series

- **B-on-A / two-speed**: Ring 1 = B/candidate breadth; Ring 2 = A/earned depth. Promotion gate = D3.8.
- **Waist sacred + small**: both rings live in `pdc`; engines never imported by `pdc`; Operations (adapters) live in `runtime/quality`.
- **Rule 12 (no enumeration)**: Operation registry + formal gate + corpus search are discovered, with replayable `SearchLedger`/incompleteness ledgers.
- **Weakest-boundary (Rule 4)**: realized by the port-authority `meet` + the 3-stage composition (which also adds coupling-validity and emergent grounding the bare rule omits).
- **D3.2** = this control plane; **D2.6** = the recursion + composition calculus; **graded outcomes** (the fork-independent near-term `useful_design_rate` win) = the `grounded_partial_admissible` terminal + downgrade routing, and should proceed in parallel.

## 10. Deliberately deferred (resolve iteratively, on real artifacts)

- The exact semantic-firewall content of A beyond formal applicability (learned from real output-artifact failures).
- The concrete VOI formula and its calibration.
- The `AuthorityBoundary` lattice's full algebra (must be pinned before composition ships).
- Whether/which Playbooks survive long-term vs the loop choosing freely.

The full type schemas (all 17 Ring-1/Ring-2 contracts), the build tasks, sequencing,
acceptance gates, and the integration of every Task 0 audit finding are in
`docs/plans/active/layer3-slices/GY-engine-subordination.md`.

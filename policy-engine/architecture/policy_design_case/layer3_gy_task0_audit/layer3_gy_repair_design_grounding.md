# GY Repair-Design Grounding

Date: 2026-06-14
Purpose: the bridge from the Task 0 audit to repair design. It fuses the empirical coverage matrix with the three architecture docs so repairs work *with* the legacy and *bring in* the progressive designs — not invent a parallel system.
Status: orientation for repair design; not yet the repair plan.

Source docs (read in full / strategically):
- Constitution: `docs/system-design-decisions/universal-policy-design-system-vision-and-organizing-rules.md`
- Operating model: `docs/system-design-decisions/policy-design-best-in-class-operating-model.md`
- Target architecture + gap (D0–D4): `docs/system-design-decisions/universal-policy-design-target-architecture-and-gap.md`
- Audit basis: `layer3_gy_capability_coverage_matrix.json` + the 16 GY Task 0 audits.

## 1. The governing frame (non-negotiable for every repair)

From the constitution:

- **B-on-A.** A (grounding/authority backbone in `runtime/quality` + `pdc`) is the only source of authority; B (the generative designer / DAG / LLM agent) is shadow until A grounds it and the **promotion gate D3.8** passes. Every repair output is shadow until it passes A.
- **The waist is `pdc` and it is sacred + small.** Authority contracts (`AuthorityBoundary`, `TypedDiagnosticRecord`, `ForecastSupport`, `SourceContract`, `CertifiedOperationEnvelope`, `DesignRecord`, `GovernanceDecisionClass`, `HumanDecisionRecord`) live in `pdc` and never import engines. Repairs add contracts here.
- **Adapters live in `runtime/quality`.** They MAY import engines; pattern = `ir_analytics_bridge.py` / `adapter_contracts.py` / `calibration_ledger.py`: call engine → map to port → attach authority/calibration/envelope/provenance → **fail closed / downgrade**. Repairs that wire engines go here, never in `pdc`, never by editing the engines.
- **Rule 12 — no hardcoded enumeration.** Adapters own a **corpus-search path**, not a hand-maintained list of constructs/datasets/methods. A correctly-added resource must become usable with zero new code. Any fallback list is a defect: mark → replace with discovery-search → delete. This directly governs GY-1 (catalog), GY-3 (acquisition), GY-6 (scholar).
- **Fail closed; weakest-boundary composition; optimize honesty, never `useful_design_rate`.**

## 2. One reconciled vocabulary (matrix verb ↔ operating-model posture ↔ D1 move)

The three frames use different words for the same four moves. Repairs will use the **operating-model posture** as canonical, because it names the existing owner:

| Coverage-matrix verb | Operating-model posture | D1 move | Meaning |
| --- | --- | --- | --- |
| `wire` | `wire-existing` | orchestrate / wire | owner runs; only needs route wiring / case-record projection |
| `govern` / `repair` | `extend-existing` | assemble / extend | runtime behavior exists; missing telemetry/authority/envelope/fix |
| (consolidate) | `consolidate-existing` | consolidate | several surfaces exist; missing a unified ledger |
| `build` | `build-new` | build-new | no credible owner |

Operating-model rule (binding): **a `build-new` item that overlaps a `wire-existing` owner is a design-review failure.** This is the same discipline as the matrix's verb/gap consistency and constitution Rule 1. The matrix already proves only ~5 rows are genuine `build-new`.

## 3. The Capability Realization Map is the per-repair owner table

The operating model's Capability Realization Map (`policy-design-best-in-class-operating-model.md:568`) assigns every capability an existing owner + posture. Cross-referenced with the coverage matrix, the repair owners are:

| Matrix capability (gap) | Owner (Capability Realization Map) | Posture |
| --- | --- | --- |
| catalog search / fetch / measurement-root (`bridge_missing`) | `data_forge/*`, `fabric/connectors/*`, `fabric/retrieval/*` | wire-existing (+ build-new measurement-root producer) |
| source-contract admissibility (`bridge_missing`) | `fabric/connectors/contracts/*`, `data_requirement/*` | extend-existing |
| DAG spine + governance tail (`wired_but_ungoverned`/`rotten`) | `scientist/policy_design/*`, `runtime/quality/assurance_case.py`, `authority*.py` | wire-existing / extend-existing |
| workflow-mode resolver (`wired_but_rotten`) | `scientist/orchestration/workflows/selection.py` | extend-existing |
| foundry methods route-consumption (`partial`) | `foundry/methods/catalog/*`, `selection/*` | wire-existing |
| ir/analytics evidence ports (`partial`) | `ir/analytics/*` (project, don't rebuild) | wire-existing |
| CAS authority backing (`surface_missing`) | `core/audit/*`, `runtime/quality/authority*.py` | extend-existing |
| time / bitemporal admission (`contract_without_producer`) | runtime bitemporality + `pdc` envelope | build-new contract over gates |
| secret/PII gate (`wired_but_ungoverned`) | `fabric` PII stage, `runtime` artifact routes | extend-existing |
| S12 cost/VOI refs (`wired_but_ungoverned`) | `runtime/quality/performance_budget.py`, S12 producers | consolidate-existing |
| runtime/dashboard/public surfaces (`surface_missing`) | `runtime/http/*`, `apps/runtime-dashboard` | extend-existing |
| agent G6 event backing (`producer_without_consumer`) | `scientist/agent/*`, `runtime/quality/prompt_tool_ledger.py` | extend-existing |
| acquisition loop / DataNeed bridge (`contract_without_producer`) | `acquisition_planner.py`, `foundry` id_engine, `scientist/agent` DataNeedSpec | build-new producer over orchestrate |
| scholar / OpenAlex provider (`contract_without_producer`) | `scholar/*` | build-new provider |
| graded outcomes routing | statuses exist (`selected_proxy_with_limitation`, `publish_with_limitation`) | wire composition/downgrade |

## 4. Sequencing the repairs (from D1 dependency graph)

D1 (`target-architecture-and-gap.md:651`) makes the order explicit; it overrides any package-by-package instinct:

1. **Binding constraint first — the construct-indexed substrate + acquisition loop.** This "starves" the backbone and gates both A and B. It is `implemented_but_not_orchestrated` + `bridge_missing` — exactly the matrix's dominant gap. This is GY-1 (catalog→fetch→measurement-root + source-contract admission) and GY-3 (acquisition/DataNeed bridge). Designing it is "never wasted regardless of target."
2. **Spine-first repair of the `wired_but_rotten` rows** before any governance: the governance/validation judge stack (phase-5), the `run_normative_arbitration` outcome re-validation, the workflow-mode resolver, lex optional-bounds, KnowledgeToolkit registration. (Constitution stop-rule: governance of a rotten asset is forbidden.)
3. **Graded outcomes — the fork-independent near-term win.** D1: "the statuses already exist; only the routing is missing," and it "alone moves the honest `useful_design_rate` off 0 for the 9 publish-with-limitation cases." This is a pure `wire composition/downgrade` at research/governed (production stays strict per ADR-0174). Highest leverage for least new code — surface it early.
4. **Authority surfaces behind one boundary** (the 10 `surface_missing`): CAS authority backing, time-admission envelope, secret/PII gate, S12 refs, runtime/dashboard/public — all consume one `AuthorityBoundary` so a failed/candidate workflow cannot be rendered/exported/signed as authority.
5. **Promotion gate D3.8** to convert any grounded B output from shadow to authority (the constitution's milestone #2). Until it exists, even perfect grounding stays shadow.
6. **Epistemic-regime + coupling are A-gates** (D1 consequence #4): B may not pick its own uncertainty regime or decomposition boundary; A classifies first.

## 5. Progressive designs to bring into the legacy repairs

Working with legacy code, each repair should adopt these D2/D3 abstractions rather than re-deriving bespoke ones (anti-P13 gravity, `target-architecture-and-gap.md:714`):

- **`TypedDiagnosticRecord`** as the one diagnostic shape for design-time counterexamples, post-deploy divergences, and regime/coupling misclassification (replaces ad-hoc `node.invalid_outcome`-style failures with a typed, replayable record carrying attribution + authority boundary + learning-eligibility).
- **`SearchLedger` + replayable frontier** for every adapter's corpus-search (Rule 12 + P25): the catalog/source/method/scholar searches must record frontier, selected/rejected candidates, index/rule versions, budget cutoffs, and no-hit/abstention reasons before any result touches a port. This is also the fix for the P2 "precision@5=0.0 / country-filter zero / no calibrated relevance" findings — abstention is honest only with measured recall + freshness (T7).
- **`ValueOfInformationEstimate`** as the single currency for acquisition/refinement/escalation (fixes the S12 "authorial refs" laundering — VOI/budget become produced objects, not hardcoded payload strings).
- **`AuthorityBoundary` + `CertifiedOperationEnvelope`** on every wrapped output (the surface-laundering fix: `authoritative_for` / `may_not_use_for` carried across run DTOs, artifact content, lineage export, dashboard, public packet).
- **The promotion gate (D3.8)** as the single shadow→authority transition (so GY-2 governs *through* the gate, not via ad-hoc surfacing).
- **Graded-outcome composition/downgrade routing** wired to the already-existing statuses.

## 6. What this means for the repair plan (GY-0.5 re-spec)

- Re-derive GY-1..GY-7 from the coverage-matrix rows + this owner/posture table; mark every work item with a posture; reject any `build-new` that overlaps a `wire-existing` owner.
- Order by the D1 dependency graph, not by package: substrate+acquisition (binding) → spine-rot repair → graded-outcome routing (near-term) → authority surfaces → promotion gate.
- Every repair: contract in `pdc`, adapter in `runtime/quality`, search-based (no enumeration), fail-closed, weakest-boundary, optimize honesty. Output stays shadow until D3.8.
- Resolve the open `policy_design` trigger decision (workflow-mode audit): either make `policy_design` the real default for policy-design intent (intent→workflow_id mapping + honest resolver), or scope GY-2 to the workflow the route runs. This is a prerequisite to repairing the DAG governance tail.

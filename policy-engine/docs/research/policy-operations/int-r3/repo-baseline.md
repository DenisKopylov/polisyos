---
task_id: INT-R3
stage: 1
artifact_role: current_repo_baseline
status: research_complete
base_commit: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
authoritative_for:
  - int_r3_repo_baseline
  - benchmark_target_inventory
may_not_use_for:
  - comprehension_evidence
  - capability_promotion
---

# INT-R3 current repository baseline

## Method and claim boundary

This is a source-coordinate inventory of the operator-facing targets named by `INT-R3`. It records
what exists at the pinned base commit. It does **not** infer that a visible, accessible or
structurally conformant surface is understood. Coordinates use path plus symbol, route, heading or
artifact identity so the inventory remains useful when ordinary line numbers move.

The baseline included the governing pipeline and backlog, `AGENTS.md`,
`policy-engine/CONTRIBUTING.md`, the ratified identity/custody boundary, `W4-K05`, the universal
policy-design architecture set, the failure-pattern register, the active GY and Atlas plans, and the
distillation ledger. Source search then followed the concrete names in the task into the runtime
dashboard, schemas, fixtures and slice plans.

## What reaches the glass today

### 1. Trust posture and the appointment refusal

| Coordinate | Existing projection | Benchmark consequence |
| --- | --- | --- |
| `apps/runtime-dashboard/src/features/trust/routes/TrustPosturePage.tsx` — `TrustPosturePage`, `TrustPostureContent` | PUBLIC/REVIEWER/EXPERT route with unavailable state, posture groups, methodology, evidence envelope, limitations, accessibility, custody, identity boundary and MACHINE download. | Freeze and test the real route, not an isolated copy mock. |
| `apps/runtime-dashboard/src/features/trust/components/ClaimPostureRegister.tsx` — `ClaimPostureRegister` | Claim id, effective state, subject/family, audiences, accountable owner, review dates, `authoritative_for`, `may_not_use_for`, limitations, blockers, source bindings and machine details. | The true blocker can be below the headline; finding and using it are behavioral outcomes. |
| `apps/runtime-dashboard/src/features/trust/domain/posture.ts` — `claimPostureRowSchema`, `claimSourceBindingSchema`, `producerPostureMetadataSchema` | Strict owner, source-state, purpose, jurisdiction, review/currentness, evidence, identity-boundary, blocker, prerequisite and `closure_signal` fields. | The reference key can be derived from typed fields rather than researcher opinion. |
| `apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json` | Generated posture packet consumed by the route. Institutional appointment absence is projected as a blocked claim rather than repaired locally. | Every scored item must bind the exact packet digest. |
| `docs/plans/active/atlas-slices/DS11-trust-docs-posture.md` — `Canonical Closure Contract`, especially `CC05`, `CC15`, `CC16` | Fail-closed posture calculus; unresolved scope stays `not_established`; no institutional role may be invented; identity anti-roles remain visible. | The benchmark must test the whole refusal relation, not only the presence of a red state. |

The repository’s most developed typed refusal can preserve: the absent role or accountable owner,
the blocker/refusal code, the affected authority purpose and scope, the evidence and record that
remain inspectable, denied uses, and the appointment or closure signal that would change the state.
The benchmark must establish whether the operator uses those fields to choose a safe transition.
Locating the panel or recalling its title is not success.

### 2. Time semantics

| Coordinate | Existing behavior | Unestablished property |
| --- | --- | --- |
| `apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.tsx` — `TimeSemanticsLabel` | Distinguishes `createdAt`, `asOf`, `updatedAt`, `validFrom`, `validUntil`, `freshness` and `generic`; freshness can expose state, `asOf` and age seconds. | Whether an operator distinguishes observation time, epoch, decision validity and expiry. |
| `apps/runtime-dashboard/src/shared/ui/temporal/TimeSemanticsLabel.test.tsx` | Component/structural behavior of the primitive. | Human comprehension and action. |
| `docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md` — `DS18 — Epoch & Staleness Chrome` | Requires `as_of`, epoch and validity on decision-bearing surfaces; stale certificates cannot render as current; epoch boundaries remain visible. | Full DS18 behavior remains an in-flight benchmark target. |
| Atlas DS18 distillation augment | Incident, appeal, correction, retraction, legal change and bias are six distinct perturbation classes; downgrade-only until adjudicated; supersession keeps lineage. | The instrument must not collapse the six classes into one generic “reopened” cue. |

### 3. Cycle Board

`apps/runtime-dashboard/src/features/runs/components/CycleBoard.tsx` — `CycleBoard`,
`CycleBoardRow`, `FactField`, `GapCard` renders:

- search terminal kind and lifecycle terminality;
- structural evidence class;
- weakest links and the missing link;
- acquisition route and acquisition economics;
- generation-cycle run id, design problem and surface readiness;
- public-safe explanation and stage-trace link;
- source availability and freshness.

Unavailable facts carry an availability badge, reason and `owner_route`. This is a concrete route by
which a blocker and acquisition path reach the glass. It is also a dense surface where every atomic
fact can be present while the binding relation remains misunderstood.

### 4. Case workspace

`apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx` —
`CaseRecordSummary`, `CaseWorkspaceDocument`, `AuthorizedCaseWorkspace` has three relevant arms:

- `artifact_missing`: availability, capability state, reason code, owner route, closure signal and
  `may_not_use_for`;
- `record_available_authority_abstaining`: grounding/admission/promotion non-receipts and denied uses;
- `available`: blockers, limitations, objections and abstentions, each with status, owner route and
  code.

The page also exposes the stage trace, admitted outputs, a complete semantic roster and the human
decision gate. This is the principal high-fidelity benchmark target because it joins epistemic state,
blockers and terminal action.

### 5. Human decisions

| Coordinate | Existing control | Benchmark use |
| --- | --- | --- |
| `apps/runtime-dashboard/src/features/runs/components/HumanDecisionGate.tsx` — `HumanDecisionGate` | Required role, decision class, channel, representation, information references, time rule, mandate validity, evidence exposure, reasons, appeal and server-offered decisions/modes. | Use the real action controls in high-fidelity trials. |
| `apps/runtime-dashboard/src/features/runs/domain/humanDecisionPresentation.ts` — `buildHumanDecisionMutation` | Rejects actions/modes not offered by the server; requires accountability and dissent; requires mode-specific override or blocking reason. | Log attempted unsafe action separately from successful unsafe commit. |
| `apps/runtime-dashboard/src/features/runs/routes/CaseWorkspacePage.tsx` — human-decision mount | Joins case evidence to the action surface and MACHINE export. | Supports replay and DOM/MACHINE parity. |

Escalation and abstention are not preference responses in this instrument. They are transitional or
terminal acts whose admissibility comes from the sealed scenario reference standard.

## In-flight target surfaces that the benchmark must constrain

| Construct | Planned coordinate | Required target behavior |
| --- | --- | --- |
| set-valued value, `unknown`, `incomparable` | `docs/plans/active/atlas-slices/DS16-value-uncertainty-and-derived-data-grammar.md`, `C01` negatives | A set cannot be collapsed to a point; `unknown` cannot render as zero or a gap; `incomparable` cannot render as a ranking. |
| conditional δ budget | Atlas master plan, `DS17 — Confidence-Ledger & Risk-Spend Surface` | Every rendered δ carries its declared basis, obligation-language version, cutoff, unknown remainder and TTL; open-world unresolved state is a settled refusal, not loading. |
| stale epoch and six perturbations | Atlas master plan, `DS18 — Epoch & Staleness Chrome` | `as_of`, epoch and validity remain distinct; stale looks stale; perturbation class and supersession lineage remain visible. |
| quarantine and re-entry | Atlas dependency table and `DS15` gate on GY-N13b | Admission passport, quarantine, re-entry trace and derived-data basis remain typed. |
| acquisition route | Cycle Board and DS15 planned acquisition surfaces | Route, owner, concrete missing item, economics and closure condition remain available. |

These plans are benchmark inputs because `INT-R3` must constrain their design before closure. They
are not current comprehension evidence.

## Conformance-versus-comprehension debt

The repository has automated structural checks and no admitted evidence that a target operator
understands the result.

| Debt | Recorded state | Why it cannot support a positive comprehension claim |
| --- | --- | --- |
| `DS11-CURRENT-PAGE-A11Y` | The base page suite recorded 20/24 passing; later DS11 receipts changed the denominator and retained failures. | A page-level conformance scan detects selected implementation defects, not conditional reasoning or correct action. |
| `DS11-EXTERNAL-A11Y-COUNTERSIGN` | No current, domain-wide, content-bound external accessibility countersign is admitted. | No independent current accessibility acceptance exists to borrow. |
| `DS11-GENERAL-COPY-SEMANTICS` | The structural checker owns two named surfaces, not arbitrary public copy. | Copy can be structurally valid while communicating the wrong decision rule. |

The historic counts above are institutionally supplied to this stage-1 researcher from committed
receipts. This package does not claim a new complete page census and does not use those counts to
settle a zero under `P35`.

## Existing chain and smallest reuse-first path

| Chain role | Existing or likely owner |
| --- | --- |
| producer | Trust posture producer; Cycle Board projection; case inspection/run paper; DS16/DS17/DS18/GY producers as slices land |
| persisted artifact/event | generated trust posture packet; captured run-paper bytes; Cycle Board packet; future benchmark run/event artifacts |
| bridge | existing runtime API/OpenAPI, generated clients and dashboard hooks |
| consumer | Trust Posture, Cycle Board, Case Workspace, Human Decision Gate |
| verification | existing schema/component/a11y/parity tests plus the proposed behavioral benchmark |
| surface | PUBLIC/REVIEWER/EXPERT/MACHINE Atlas routes |

Reuse-first path: freeze existing producer packets and real surfaces; add no parallel status lattice;
run the benchmark through the existing action controls and event capture; persist a research result
that remains unable to mint authority.

## Reusable tests and fixtures

- DS16 red-first value-grammar negatives;
- `TimeSemanticsLabel.test.tsx`;
- Cycle Board presentation and packet-parity tests;
- Case Workspace typed-unavailable/available branch tests and semantic roster;
- Human Decision Gate action/mode validation and evidence exposure;
- Trust posture schema, generated-byte and route tests;
- DS11 page-a11y receipts as conformance baselines only.

## Gap classification

| Gap | Type | Honest capability label |
| --- | --- | --- |
| No human run against these surfaces | research blocker for a comprehension claim | `absent/unallocated` |
| No appointed benchmark-governance or risk-threshold owner | institutional blocker | `absent/unallocated` |
| No canonical behavioral event/result contract in an admitted chain | later engineering blocker | `absent/unallocated` |
| Partial page-a11y and no external countersign | engineering/institutional accessibility blockers | retain registered DS11 debts |
| Thin evidence for explicit `unknown`, strict incomparability, δ-budget and AT × uncertainty | open research limitation | `deferred_open_problem` finding |

## Four-way boundary census

| Function | Verdict | Owner mapping |
| --- | --- | --- |
| Define and require evidence that PolicyOS’s own authority projections support correct action | **OWN** | PolicyOS design/justification custody; canonical benchmark owner missing |
| Recruit operators, obtain research-ethics approval where required, arrange compensation and working conditions | **INTEGRATE** | external sponsor/ethics/employer; no owner appointed |
| Supply role competence, escalation destinations and operational loss thresholds | **INTEGRATE** | accountable institution; no signer appointed |
| Observe adoption, training and organizational workarounds | **OBSERVE** | employing institution and later learning loop |
| Measure visual preference or general product liking as correctness | **OUT_OF_SCOPE** | secondary UX research only |

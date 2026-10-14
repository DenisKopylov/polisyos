# PolicyOS architecture: target and current code

> **Owner:** `team-architecture`
>
> **Source of truth:** ratified identity/custody decisions, `architecture/imports/policy.toml`,
> `architecture/public_surface/contract.toml`, and the source paths named below.
>
> **Source snapshot reviewed:** `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` (2026-10-14).
>
> **Evidence caveat:** source and test paths below were inspected at this snapshot. This
> documentation refresh did not run those tests. A test reference identifies a test's scope; it
> is not a fresh pass receipt, a completeness claim, or institutional authority.

This page is an orientation map, not a new architecture decision or a capability register. It
separates the strategic target and ratified identity/custody boundary from the paths that can be
located in the current repository. Read the
[north star](../system-design-decisions/policy-design-causal-operating-system-north-star.md)
for the strategic model, the [identity and custody decision](../system-design-decisions/policyos-identity-and-custody-boundary.md)
for PolicyOS's scope, and the
[Stage-0 ratification](../system-design-decisions/stage0-custody-kernel-ratification.md) for the
custody invariants. These design records do not establish that a capability is implemented.

---

## 1. Product identity and authority boundary

The strategic frame is a **causal operating system for policy**. A policy design is treated as a
program over a structural causal model: an intervention changes a target directly and predicts a
distribution over downstream effects; the effects of a composed design need to be checked jointly.
Required data can exceed available data, so acquisition should address the gaps that matter to the
decision. The growing world model, rather than a text generator, is the north-star product. This
is a direction for the build, not a claim that the repository already contains a universal causal
world model or a complete post-deployment learning loop.

The ratified identity is **epistemic custodian of policy justification**. PolicyOS owns everything
it signs for as long as those signatures publicly stand, consumes other institutions' signatures
as typed evidence, and does not claim acts it cannot custody. Its scope includes design authority,
lifetime custody of its own justification, and a safe learning loop; it does not make PolicyOS the
administrator, executor, court, payment system, notification channel, or case-management system.
See the identity decision's §1 and §5 for the signature rule and four-way `own / integrate /
observe / out_of_scope` test.

Stage-0 makes the boundary operational. **S0-K03** requires classifying one plane at a time along
external act → evidence emission → receipt and verification → admission → scoped claim reaction →
public projection. **S0-K05** and **S0-K07** prohibit authority by observation, transport, or
projection. **S0-K06** binds fail-closed behavior to protected actions, published claims, and custody facts: a
candidate computation may continue with an explicit unknown carried as a limitation, but that
unknown cannot silently become a closed scope for authority use. **S0-K08** keeps corrections
append-only. The ratification is authoritative for these boundary rulings, not for production
schemas, capability status, or owner assignment.

LLM-generated claims, legal readings, risk assessments, and method choices remain candidates until
admitted by the relevant producer and consumer path. A response that looks complete, a typed field,
or a dashboard label does not itself establish authority. This is the candidate-to-authority
boundary described by P05 and P15 in the
[failure and repair register](../reference/policy-design-case-failure-patterns.md).

## 2. Two views of the architecture

The upper lane is the north-star flow. The lower lane is a set of representative code paths found
in the snapshot. The lower lane is not a single universal workflow, and matching names between the
two lanes do not prove that a target capability is complete.

```mermaid
flowchart LR
    subgraph target["North-star direction + ratified custody boundary"]
        problem["Policy problem and declared scope"] --> need["Required vs available evidence"]
        need --> acquire["Decision-relevant acquisition"]
        acquire --> world["Growing causal world model"]
        world --> design["Candidate interventions and joint design checks"]
        design --> ground["Grounding and admissibility"]
        ground --> signature["PolicyOS-owned scoped signature"]
        signature --> custody["Revalidate, reissue, supersede, or withdraw"]
        custody --> learn["Observe outcomes: confirmatory evidence or exploratory candidate"]
        learn --> world
    end

    subgraph code["Observed repository paths — selected seams"]
        req["Requirement specs"] --> pipeline["Runtime producer pipeline"]
        pipeline --> planner["Acquisition planner"]
        catalog["Data Forge catalog + Fabric source contract"] --> fabric_api["Runtime Fabric API"]
        scientist["Scientist causal node"] --> foundry["Foundry method boundary"]
        monitor["Governance event artifacts"] --> lifecycle["Claim lifecycle bridge"]
        lifecycle --> ledger["Claim ledger / review projection"]
        receipts["Persisted acquisition route and reentry receipts"] --> cas["Core artifact store"]
        cas --> run_api["Runtime run-history projection"]
        run_api --> dashboard["Runtime dashboard"]
    end
```

The code lane is backed by the tests listed in §5. Some tests prove a positive bounded path; others
prove a refusal path. Their presence does not mean those suites were run during this document
update.

## 3. Repository boundaries and entrypoints

The source tree is organized by package ownership, but there are three different maps to keep
separate:

- `architecture/imports/policy.toml` is the enforced import-direction matrix. Its `internal.allow`
  entries say which package roots may import which others; they are dependency constraints, not a
  runtime call graph or workflow specification. For example, the matrix permits `fabric` to depend
  on `data_requirement`, `data_forge`, `core`, and `ir`, and permits `foundry` to depend on
  `method_requirement`, `calibration`, `data_forge`, `fabric`, `core`, and `ir`. The file also records
  an existing package-cycle baseline, so do not read it as proof of a strictly acyclic layer stack.

- `architecture/public_surface/contract.toml` defines supported Python entrypoints and their
  compatibility class. An unlisted `polisyos` module is internal by default. The contract marks
  `core`, `ir`, `fabric`, `foundry`, `scientist`, `runtime`, and `lex` facades as stable; it marks
  `data_forge` and `runtime.quality` as experimental. It explicitly keeps several requirement and
  evidence packages internal. The generated
  [public-surface reference](../reference/public-surface.md) is the navigable inventory; a package
  being present in `src/` does not make every submodule public.

- Runtime and test paths show where selected producers, bridges, and consumers meet. An allowed
  import or public contract is not evidence that an artifact is produced, persisted, consumed, or
  checked end to end.

Representative package owners and canonical starting points:

| Area | Current owner and starting point | Boundary to keep in view |
| --- | --- | --- |
| Cross-cutting contracts and persistence | `src/polisyos/core/contracts/`, `src/polisyos/core/artifacts/`, `src/polisyos/core/security/` | Core owns shared contracts, artifact storage, and security primitives; it does not own domain conclusions. |
| Policy, observation, and analytics contracts | `src/polisyos/ir/` (`load_policy()`, Trinity and observation contracts) | IR is the shared contract layer; its types do not prove that a producer or workflow consumes them. |
| Prepared data assets | `src/polisyos/data_forge/read_api/` and `src/polisyos/data_forge/domains/` | The facade is experimental. Runtime readers use `read_api`; domain batch internals are not a public runtime surface. |
| Connectors and materialized data/world reads | `src/polisyos/fabric/connectors/`, `src/polisyos/fabric/data_plane/`, `src/polisyos/fabric/world/` | Fabric owns ingestion and world-query paths; source receipts and lineage still need consumer-specific admission. |
| Legal material | `src/polisyos/lex/` and `src/polisyos/data_forge/domains/legal/` | Lex owns runtime legal assembly and evaluation; offline legal preparation is under Data Forge. |
| Compilation, methods, and synthetic worlds | `src/polisyos/foundry/compile/`, `src/polisyos/foundry/execute/`, `src/polisyos/foundry/agent_sim/world/` | The public Foundry facade is stable; the synthetic-world surface is separately experimental and is not by itself the north-star production world model. |
| Workflow and governance | `src/polisyos/scientist/orchestration/workflows/`, `src/polisyos/scientist/nodes/`, `src/polisyos/scientist/governance/`, `src/polisyos/scientist/evidence/claims/` | Scientist routes work and owns claim/lifecycle mechanisms; internal subpackages are not automatically stable public APIs. |
| HTTP and operator-facing projection | `src/polisyos/runtime/http/app.py::create_runtime_api_app`, `src/polisyos/runtime/http/routes/`, `packages/runtime-api-client/`, `apps/runtime-dashboard/` | The stable Python facade is `polisyos.runtime`; HTTP implementation modules remain internal unless separately documented. API projections do not mint authority. |

Policy grammar and requirement/admissibility work has dedicated owners, including
`polisyos.data_requirement`, `polisyos.legal_requirement`, `polisyos.obligation_rules`,
`polisyos.obligation_graph`, `polisyos.method_requirement`, and
`polisyos.participation_requirement`. Their location as separate packages is visible in the import
policy, while their current public status is determined by the public-surface contract. This is
how the repository can reuse a universal grammar and facet requirements without presenting every
internal compiler as an external API.

## 4. Contracts, bridges, and capability claims

A **contract** names a typed shape, boundary, or allowed transition. A **capability** exists only
when the contract is carried through the whole chain:

`typed contract/artifact → producer → persisted artifact/event → orchestration bridge → consumer → verification → API/audit/dashboard surface (or explicit out_of_scope) → negative or end-to-end semantic test`

The labels and definitions in the failure register distinguish a missing bridge, consumer,
verification, or surface from an implemented path. A schema, a component, a passing constructor
check, a generated client, and a research handoff are each insufficient alone. This distinction
addresses P01/P02 (contract without a consumed bridge), P03 (internal evidence without a useful
surface), P05/P15 (authority boundaries), and P10 (semantic adequacy).

## 5. Selected code-backed bridges and their limits

| Path | Source and test locations | What the inspected path establishes | What it does not establish |
| --- | --- | --- | --- |
| Requirement specifications → producer pipeline → acquisition planner | `src/polisyos/runtime/quality/producer_pipeline.py::run_requirement_spec_producer_pipeline`; `src/polisyos/runtime/quality/acquisition_planner.py`; `tests/unit/runtime/quality/test_wave7_requirement_pipeline_integration.py::test_requirement_spec_pipeline_runs_real_w7_adapters_and_acquisition_bridge` | The test supplies requirement and producer inputs, runs the W7 adapter/pipeline path, and inspects the compiled family summaries and planner records. `tests/unit/runtime/quality/test_acquisition_owner_store_requirement.py::test_default_gateway_uses_exact_tenant_store_for_skg_produce_and_replay` checks that the SKG owner uses the supplied tenant store and persists a source-resolution artifact. | The pipeline test uses bounded fixtures; it does not establish universal live acquisition, complete source coverage, or a publishable policy conclusion. |
| Data Forge catalog and Fabric source contract → Runtime Fabric API | `src/polisyos/data_forge/read_api/catalog.py`; `src/polisyos/fabric/connectors/contracts.py`; `src/polisyos/runtime/http/routes/fabric.py::get_fabric_source_scorecards` and `::analyze_fabric_impact`; `tests/integration/data_forge_runtime/test_catalog_to_runtime_bridge.py::test_data_forge_catalog_fixture_source_contract_reaches_runtime_api` | The integration test loads a catalog fixture and source contract, calls the runtime scorecard and impact routes, and checks the fixture's lineage and affected decision-data projection. | A fixture-backed source route does not prove that every domain has this bridge or that its impact projection authorizes a policy claim. |
| Scientist causal node → Foundry method boundary | `src/polisyos/scientist/nodes/builtins/simulate/run_causal_evaluation.py::RunCausalEvaluationNode`; `tests/integration/foundry_scientist/test_method_node_bridge.py::test_foundry_method_bridge_refuses_absent_eval_safety_before_execution` | The test reaches the Scientist node with a registered Foundry method but no EvalSafety execution context; it asserts refusal occurs before `run_job` and state/artifact mutation. | This is a negative admission test. It does not demonstrate a successful causal execution or a complete policy-design workflow. |
| Governance event → claim lifecycle projection | `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py::bridge_governance_events_to_claim_lifecycle`; `src/polisyos/scientist/evidence/claims/lifecycle.py`; `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_bridge_maps_detector_families_to_claim_lifecycle_and_public_revision` | The test maps persisted detector events to append-only claim lifecycle records and a `review_required` public revision; it marks that revision `projection_only`. | A review projection is not a reissue or an authority-bearing current claim head. Raw detector events do not supply that authority. |
| Completed validity batch → Claim owner head | `src/polisyos/scientist/governance/continuous/lifecycle_bridge.py::EpochClaimLifecycleBridgeService`; `src/polisyos/scientist/evidence/claims/head_index.py`; `tests/unit/scientist/governance/continuous/test_lifecycle_bridge.py::test_completed_epoch_batch_is_only_authority_input_to_claim_bridge`, `::test_fabricated_completed_batch_dto_and_matching_ref_cannot_bridge`, and `::test_raw_detector_event_cannot_establish_epoch_claim_transition` | The bridge accepts only its completed-batch evidence type. The inspected fixture returns `ClaimLifecycleBridgeNonReceipt` with `claim_ledger_owner_not_established`; fabricated receipts and raw monitor events are rejected. | This path does not establish successful current-head advancement in that fixture. The missing owner is a concrete integration limit for that path, not evidence that every claim lifecycle path is absent. |
| E02 acquisition route/re-entry receipts → Runtime run history → dashboard | `src/polisyos/runtime/quality/data_state_substrate.py`; `src/polisyos/runtime/http/routes/runs.py::_candidate_acquisition_history_projection`; `apps/runtime-dashboard/src/api/validators.ts`; `apps/runtime-dashboard/src/features/runs/routes/tabs/OverviewTab.tsx`; `tests/integration/core_runtime/test_acquisition_authority_served.py::test_served_acquisition_selects_committed_human_authority_and_reopens_worker`; `apps/runtime-dashboard/e2e/journeys/catalog-profile-source-bound.spec.ts` | The served path joins persisted route and re-entry receipts to a selected candidate occurrence, distinguishes observed origin refs from a verified same-candidate root, and projects the history through the runtime and dashboard surfaces. The test body also asserts authorization and corrupted-artifact behavior. | The projection is explicitly `candidate_observation_only`: it records `currentness_status = not_established` and `publication_authority = false`. The accompanying E02 release fragment, `release-fragments/unreleased/2026-10-14-e02-acquisition-history-lineage-join.toml`, states the same limit. This is lineage evidence for candidate history, not publication authority or proof that the policy remains current. |

The selected E02 acquisition path demonstrates a real producer → persisted receipt → runtime reader →
dashboard bridge for a bounded candidate-history projection. Its source binding is stronger than an
observed source reference, while its authority purpose remains candidate-only. The distinction is
intentional: a verified provenance join can answer *which persisted continuation produced this
candidate* without answering *whether the signed policy claim is currently admissible*.

## 6. What remains beyond this map

- The north-star's growing causal world model, joint simulation of composed interventions, and
  two-contour post-deployment learning loop are design targets. The identity decision describes the
  learning loop as greenfield; the presence of Foundry synthetic worlds or drift monitors does not
  complete it.

- The claim lifecycle bridge has useful review projections and a fail-closed completed-batch
  admission path. The inspected owner-missing case remains a nonreceipt; do not describe it as an
  authority-grade revalidation or head-advance demonstration.

- The selected lifecycle and presentation paths keep separate roles visible: the Scientist bridge
  records a `projection_only` review revision, while the Runtime E02 history route and dashboard
  expose candidate provenance with `publication_authority = false`. These paths do not establish a
  signer, a publisher, or successful authority-bearing claim-head advancement. Those properties
  remain `not_established` by the evidence cited here; a public projection is not a signature.

- Runtime acquisition history has a consumer surface and a checked same-candidate join. It remains
  candidate-only and makes no currentness or publication claim.

- The import and public-surface contracts govern different questions. An import edge says where a
  dependency is allowed; a public entrypoint says what callers may rely on; neither proves the
  end-to-end property. Use the capability labels in the
  [failure and repair register](../reference/policy-design-case-failure-patterns.md) when a producer,
  artifact, bridge, consumer, verification, or external surface is missing.

For detailed operational topology and durable artifact families, see
[operations diagrams](../reference/operations/platform-architecture-diagrams.md),
[generated artifacts](../reference/generated-artifacts.md), the
[API reference](../reference/api/index.md), and the
[IR contract catalog](../contracts/TRINITY.md).

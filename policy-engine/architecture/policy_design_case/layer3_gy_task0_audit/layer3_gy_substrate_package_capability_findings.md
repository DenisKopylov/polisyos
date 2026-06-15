# GY Task 0 Substrate Package Capability Inventory

Date: 2026-06-14
Scope: Core / IR / evidence / BERL / DDM / calibration / requirement packages.
Mode: audit only; no fixes or route rewiring.

## Method

This pass re-opened the Policy Design Case failure register before inspection and used the capability reality check as the unit of accounting:

`typed contract/artifact + producer + persisted artifact/event + orchestration bridge + consumer + verification + external/audit/API/dashboard surface or explicit out_of_scope + negative/e2e semantic test`.

The audit is source-static. It parsed public-surface and package-contract manifests, package READMEs, root facades, AST counts, cross-package import consumers, and the current GY engine census. It did not start a runtime server, perform network fetches, or run the pinned DAG.

## Headline Finding

The substrate packages are not thin. They are mostly mature, typed, and consumed across the repo. They are also almost entirely absent from GY-0 route accounting.

The 11 packages in scope contain `466` Python files, `435` root-facade exports, `2,639` classes, and `2,114` top-level functions. The current GY engine census contains `0` rows referencing these package modules. That is not "no capability"; it is a census coverage boundary.

## Package Classification

| Package | Classification | Capability state | Main gap for GY |
| --- | --- | --- | --- |
| `polisyos.core` | route-pinned substrate | wired substrate, not domain authority | Needs to remain infrastructure, not claim/closeout proof. |
| `polisyos.ir` | route-pinned contract substrate | wired contract substrate, not route evidence | Needs route-consumed evidence/proof roots, not facade presence. |
| `polisyos.evidence` | near-route evidence-strength bridge | implemented with consumers, not pinned closure surface | P14/P05 bridge into GY claim closure not proven. |
| `polisyos.berl` | broader explanation reliability support | implemented with Scientist/runtime-quality consumers | Display/faithfulness gates are not recommendation authority. |
| `polisyos.calibration` | near-route metric validation support | implemented diagnostics, not current GY measurement root | Calibration report must be bound to DAG measurement root. |
| `polisyos.ddm` | out-of-route production monitoring | implemented monitoring package, not GY pinned route | Needs explicit invalidation/reissue bridge if GY wants it. |
| `polisyos.data_requirement` | near-route fetch-admission bridge | near-route, bridge missing at pinned fetch admission | Normal `FetchPlan` route does not consume `DataRequirementSpec`. |
| `polisyos.method_requirement` | near-route method-admission bridge | compiler consumed by Foundry/runtime quality, not pinned GY method gate | Needs route method-selection/admission proof. |
| `polisyos.participation_requirement` | broader legitimacy gate | implemented claim-use ceiling, not GY pinned route | Participation limits cannot be inferred from route absence. |
| `polisyos.obligation_rules` | near-route requirement substrate | real governed catalog, not direct GY route | Candidate/LLM rules cannot be authority without governance decision. |
| `polisyos.obligation_graph` | near-route requirement substrate | real compiler, not direct GY route | Frontier/visibility authority cannot become legal/method/projection authority. |

## Findings That Matter For GY-0.5

1. `core` and `ir` should not become dozens of new GY rows just because they are foundational. They are route-pinned substrate, but their authority is infrastructural and contractual. Counting them as policy evidence would create P05/P10 laundering.

2. `data_requirement` is the load-bearing near-route gap. It has contracts, producers, audit surface, writer, Fabric/runtime consumers, and tests. It is still absent from both `architecture/public_surface/contract.toml` and `architecture/packages/data_requirement.toml`, and the normal catalog `FetchPlan` route does not consume `DataRequirementSpec` or SourceContract binding status before connector fetch.

3. `evidence` is specifically anti-inflation infrastructure. Conflict records are authoritative for conflict materialization only, and effective-independence graphs make raw counts diagnostic-only while preserving counterevidence mass separately. GY should consume this as P14 protection, not as support strength.

4. `BERL` and `calibration` are real validation substrate. BERL has strict `ExplanationBundle` contracts, held-out infidelity checks, disagreement/redundancy gates, and display policies. Calibration has binary/multiclass/continuous diagnostics and a governance `ValidationReport` adapter. Neither is GY authority without a route consumer binding the result to a method/output/root.

5. `DDM` is implemented but belongs to production monitoring/readiness, not the pinned policy-design route. It can become relevant through invalidation/reissue semantics, but the current GY route does not consume DDM window outputs.

6. Requirement packages already encode the right authority ceilings. `method_requirement` blocks overclaiming beyond method-precondition authority; `participation_requirement` blocks LLM speculation/analyst summaries; `obligation_rules` requires explicit governance admission; `obligation_graph` refuses no-facet compilation and exposes `may_not_use_for` boundaries. The GY risk is orchestration, not type absence.

## Anti-Greenwash Assertions

- Do not treat `0` GY census rows as `0` package capability.
- Do not treat Core/IR as claim, legal, data, method, participation, or closeout authority.
- Do not treat `data_requirement` compiler existence as fetch admission.
- Do not treat conflict records or raw evidence counts as positive support.
- Do not treat BERL display policy as recommendation authority.
- Do not treat DDM monitoring as pinned route execution.
- Do not treat LLM/candidate rules as governed obligations.
- Do not treat participation LLM speculation as participation evidence.

## Artifacts

- Source of truth: `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_substrate_package_capability_inventory.json`
- Validator: `tools/quality/validation/check_layer3_gy_substrate_package_capability_inventory.py`
- Tests: `tests/repo_quality/tools/test_layer3_gy_substrate_package_capability_inventory.py`

## GY Planning Implication

The next GY plan should not expand GY-0 into a giant package inventory. It should keep the package inventory as a substrate map, then add route probes only where authority can be laundered across a bridge: `data_requirement -> SourceContract -> FetchPlan`, `evidence -> claim closure`, `calibration/BERL -> method/output roots`, and requirement/obligation packages -> runtime gates.

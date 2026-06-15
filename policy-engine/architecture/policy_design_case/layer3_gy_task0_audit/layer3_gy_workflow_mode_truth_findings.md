# GY Workflow-Mode Truth Audit

Date: 2026-06-14
Scope: the three Scientist execution modes — `scientist_policy_design`, `scientist_causal_full`, `scientist_policy_verified` — which one the production route actually selects, their real per-node failure modes on the real UA panel, and the consolidation (reuse / merge / build-out) map toward a single mode.
Mode: audit-only. No runtime behavior changed. `JAX_PLATFORMS=cpu`. Input is the real production-catalog panel but with thin/synthetic-formalized policy options (no real fabric fetch). Extends GY-0 finding #1.

Artifacts: `layer3_gy_workflow_mode_truth_audit.json` (machine), this file (findings).

## Why this audit exists

Every prior GY-0 artifact — the engine census's 37-node run, the lex root-cause, foundry-breadth, the blocked-upstream cascade — ran `scientist_policy_design`. GY-0 finding #1 proved no production runtime path selects it. This audit resolves what the route *does* run, and turns "3 modes is bad, we want 1" into a concrete merge/reuse/build map.

## Selection truth (two proven bugs)

`resolve_workflow_id` (`src/polisyos/scientist/orchestration/workflows/selection.py`) resolved empirically:

| Input (NL-shaped) | Resolves to |
| --- | --- |
| governed + source/target contexts (`transport_required=True`, what `_build_scientist_context_params` emits) | **`scientist_causal_full`** |
| governed + `policy_question`, no `policy_mode` | **`scientist_policy_verified`** |
| research, no `policy_mode`/question | **`scientist_causal_full`** |
| explicit `workflow_id=scientist_policy_design` | `scientist_policy_design` |
| `policy_mode=True` only | `scientist_policy_design` |

**Bug 1 — the NL route never selects `policy_design`.** `policy_mode` / `workflow_id` are never set anywhere in `nl_pipeline.py`; `_build_scientist_context_params` (`nl_pipeline.py:548`) sets `transport_required=True` but never `policy_mode`. Grep of non-test `src/polisyos/runtime/` finds no `scientist_policy_design` / `policy_mode` trigger (only a string label in `claim_argument.py:459`). So `scientist_policy_design` — the **only** mode containing `run_hierarchical_policy_search` (lex) — is reachable only via the explicit `workflow_run` API (`launch_workflow_run`, `run_lifecycle.py:1164`, which reads `request.params`) or reissue. The GX pinned-route artifact names `scientist_policy_design`, but nothing in-repo triggers it.

**Bug 2 — explicit `causal_full` is silently overridden.** PROVEN: `run_selected_workflow(workflow_id="scientist_causal_full")` with a `policy_question` and no trinity executed the **policy_verified** spec (28 nodes, exact match). Root cause: in `selection.py`, discovery / policy_design / policy_verified receive early explicit honoring (lines 43–48), but the explicit `scientist_causal_full` check is at **line 57**, *after* `_should_use_policy_verified` (line 53) and `_execution_profile_requires_serious_workflow` (line 55). The heuristic wins over the explicit request. The resolver docstring ("treats explicit `params.workflow_id` as authoritative") is **false for causal_full**: to actually run it you must also supply a `trinity_bundle_ref` (disables the policy_verified heuristic) or a serious profile.

## Real failure modes on the real panel

| Mode | Ran spec | ok / fail / skip | Fails at | Cause |
| --- | --- | --- | --- | --- |
| `policy_design` | policy_design (37) | 14 / 1 / 22 | `run_hierarchical_policy_search` (lex) | optional-bounds bug; governance tail never reached |
| `policy_verified` | policy_verified (28) | 17 / 1 / 10 | `run_normative_arbitration` (60-row) **or** `build_verified_policy_report` (40-row) | governance/validation tail |
| `causal_full` | causal_full (29, trinity minted) | 12 / 1 / 16 | `run_normative_arbitration` | `node.invalid_outcome` |

To run `causal_full` at all I minted a real trinity bundle via a `policy_design` run (`formalize_verified_policy` writes `inputs.trinity_bundle_ref`).

## The real blocker is the shared governance tail, not lex

`run_normative_arbitration`, `run_governance`, `build_verified_policy_report`, `build_decision_packet` are part of the **19-node shared spine** common to all three modes. In `policy_design` they are merely `skip` — masked because lex fails first. In the two modes the route actually runs, the DAG reaches them and **fails there**:

- `run_normative_arbitration` → `node.invalid_outcome`: the returned `NodeOutcome` fails **pydantic re-validation** (`NodeOutcome.model_validate`, `async_executor.py:882→903`) — not an `execute()` exception.
- `build_verified_policy_report` → `phase5_validation_failed`: `verdict=blocked`, `readiness=blocked`, **18 gate failures = all 6 phase-5 judges (structural, statistical, robustness, governance, reproducibility, compute) "failed fatally"**, deterministic across 3/3 identical runs.

The failure *node* is input-sensitive (shifts between `run_normative_arbitration` and `build_verified_policy_report` with different panels) but deterministic for a fixed input. **Implication: repairing lex alone does not unblock the route.** On thin/synthetic-formalized input the spine governance tail fails regardless of mode; the judge stack needs real measurement-rooted formalized input.

## Structural map: what to reuse / merge / build

Node-set algebra across the three specs (19/19 common nodes share identical `node_id` — real shared implementations):

- **Reuse as-is — the 19-node shared spine**: data plane (`build_data_snapshot`, `bind_foundry_inputs`, `run_data_plane_gate`), foundry (`build_method_catalog_snapshot`, `run_preflight`, `compile_foundry`, `compile_cross_graph_evidence`, `resolve_parameters`), simulation/analytics (`run_simulation`, `run_metric_validation`, `run_distributional_analysis`, `propagate_welfare`, `propagate_uncertainty`, `run_causal_evaluation`), governance tail (`run_normative_arbitration`, `run_governance`, `build_decision_packet`), plus `start`. **Caveat:** the spine *wiring* diverges for 7 nodes — most importantly `run_simulation` is gated by `counterfactual_identification_gate` **only** in `policy_design`. A unified mode must keep that gate (it is the strongest pre-simulation identification discipline) and pick a union topology with conditional edges.
- **Merge — two shared optional arms**:
  - legal/source arm (9 nodes, `policy_design ∩ policy_verified`): `plan_policy_request`, `assemble_legal_candidate_pack`, `expand_legal_source_pack`, `run_source_verification`, `run_source_gap_review`, `draft_policy_options`, `formalize_verified_policy`, `legal_check`, `build_verified_policy_report`.
  - literature/causal-graph arm (3 nodes, `policy_design ∩ causal_full`): `build_literature_prior`, `reconcile_causal_graph`, `run_causal_readiness`.
- **Build-out / fold — the two genuinely distinct arms** (the real capability difference):
  - lex/design-space (6, policy_design only): `run_hierarchical_policy_search`, `counterfactual_identification_gate`, `build_policy_output_bundle`, `run_policy_blueprint_runtime`, `run_policy_translation`, `run_translator_compliance`.
  - transport/ensemble (7, causal_full only): `link_trinity`, `ready_to_run`, `run_transportability`, `run_causal_queries`, `run_causal_ensemble`, `run_abm_consistency`, `run_evaluator`.
- **`policy_verified` is redundant**: it has **0 unique nodes** (strict subset of `policy_design`). It is expressible as `policy_design` with the lex/translation arm disabled — a strong argument it should not be a separate top-level mode.
- **Input-contract divergence to fix**: `trinity_bundle_ref` is a hard `required_bind` for `causal_full` but produced (`formalize_verified_policy`) by the others. A unified mode should treat trinity as produced-or-supplied, not a hard bind that silently reroutes selection.

## Recommendation for future work (toward one mode)

1. Collapse to **one mode** = the shared 19-node spine + conditional sub-DAG arms (legal, literature, lex/design-space, transport/ensemble) keyed on **typed inputs**, not on a heuristic resolver.
2. In the interim, make the resolver honest: honor explicit `workflow_id` authoritatively for **all** modes (move the `causal_full` explicit check above the heuristics), or delete the heuristic override. Today an explicit `causal_full` request silently becomes `policy_verified`.
3. A single mode lets the artifacts support the cycle / transition / rollback operations you want — one artifact family per stage instead of three divergent ones.
4. Repair order is **spine-first**: the phase-5 judge stack and `run_normative_arbitration` outcome validation must accept real measurement-rooted formalized input before any mode produces a publishable report; the lex optional-bounds bug is a `policy_design`-only upstream fix on top of that, not the route unblocker the original audit implied.

## Production trigger trace (resolved)

Who triggers `scientist_policy_design` in production? **Nobody, by default.** Confirmed:

- No `src/polisyos/runtime/` code sets `workflow_id=scientist_policy_design` or the selector `params.policy_mode` (only a string label `projection_source` in `claim_argument.py:459`).
- `ExecutionProfile = Literal["dev","research","governed","production"]` (`core/contracts/control.py:38`) — `policy_design` is **not** a valid profile, so the `_should_use_policy_design` execution-profile branch is unreachable from the API.
- `POST /api/v1/control/runs` (`control.py:115` → `run_lifecycle.py:1164`) builds `state_payload.params = dict(request.params)`. `WorkflowRunRequest` (`control.py:255`) has **no** first-class `workflow_id` field — only a freeform `params` dict.
- The dashboard Composer (`useLaunchRun` → `buildWorkflowLaunchRequest`, `composer/domain/forms.ts:96`) sets `params` from `operator_intent`/`expected_outputs`/`governance_constraints`/`atlas_context` + user `customParams`; it never defaults `workflow_id`/`policy_mode`.
- The NL path resolves to `causal_full`/`policy_verified`.
- Only CI/ops harnesses (`tools/ci/check_scientist_best_in_class_*`, `tools/ops_runners/.../run_msme_grand_tournament_v2.py`) set `workflow_id=scientist_policy_design` — not production.

Reachable only via: an explicit caller-supplied `params.workflow_id=scientist_policy_design` / `policy_mode=true` (external API or power-user Composer custom-param), reissue of such a run, or non-production harnesses.

GY implication: the GX pinned-route artifact names `policy_design`, but it is **intended-but-untriggered**. GY-0.5 must decide: (a) make `policy_design` the real default for policy-design intent (an intent→workflow_id mapping + an honest resolver), or (b) scope GY-2 governance to the workflow the route actually runs. GY-2 cannot assume `policy_design` is the production route.

## Verification

```bash
python3 tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py --json
```

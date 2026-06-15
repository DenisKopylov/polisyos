# GY-0 (Task 0) — Global Review

Date: 2026-06-14
Author: synthesis across the full GY Task 0 audit campaign (`architecture/policy_design_case/layer3_gy_task0_audit/`) and the engine census.
Status: review of an audit-only body of work. Not a remediation plan.

## 1. Verdict

**Task 0's purpose is met; Task 0's original "Done when" bar is not — and that is the correct outcome.**

GY-0 was specified as a single pinned-route engine census whose bar was "every row execution-verified, zero `unknown`, one gap_class + matching verb." That artifact exists, passes its hardened completeness check, and is real. But the census, taken alone, would have shipped three false premises into GY-0.5. The audit campaign that grew around it (15 follow-on audits + the coverage matrix, all with validators and most with repo-quality tests) is what actually discharges Task 0's *real* charter — "end the exists/wired/works confusion before a single wire is changed." Measured against that charter, Task 0 is in good shape. Measured against "is the pinned route healthy," it is honestly red, with the reasons named.

The census's own bar is met (69 rows, 0 `unknown`, validator green). The broader system bar is deliberately not claimed: the coverage matrix shows **1/29 capability chains fully green**.

## 2. The one structural truth (the matrix diagonal)

The repo-wide capability coverage matrix is the single most useful synthesis. Across 29 capabilities scored on `contract → producer → artifact/event → bridge → consumer → surface → semantic_test`:

- contract: **26/29 proven**
- producer: **29/29 proven-or-partial**
- bridge: **20/29 `bridge_missing`**
- surface: **10/29 `surface_missing`** (+11 `n/a`)
- semantic_test: **16/29 absent**

This is the empirical answer to the framing question — "if everything exists, why doesn't it work." The system is **rich in components, poor in seams and in proof-of-authority.** The dominant gap classes are `wired_but_ungoverned` (8), `partial` (8/9), `wired_but_rotten` (4), `contract_without_producer` (5). `missing` is rare. The defect is integration + governance + verification, not absent capability. Verbs skew **wire/govern/repair**, not **build** (only ~5 genuine build-new items).

## 3. Load-bearing corrections to the plan's premises (what Task 0 changed)

Each of these would have mis-shaped GY-0.5 had the census shipped alone:

1. **The "~1184 reducer_provenance_missing" progress meter is stale.** The GX validator reports `expected_red_check_count=0, issue_count=0` on the consolidated branch. GY's headline meter is already zero. *(engine census)*
2. **The baseline outcome shifted** to `search_ceiling_repair_required` / `unchanged_blocker`, not `typed_blocker`. This points at GY-1 (real catalog) as the unblock, not provenance backfill. *(engine census)*
3. **The census audited the wrong workflow.** The NL route runs `causal_full` / `policy_verified`; `scientist_policy_design` (the only mode with lex) is never selected by runtime. Two resolver bugs (NL never sets `policy_mode`; explicit `causal_full` overridden to `policy_verified`). *(workflow-mode truth)*
4. **lex is not the production blocker.** The shared governance/validation tail (`run_normative_arbitration` → `node.invalid_outcome`; `build_verified_policy_report` → all 6 phase-5 judges fatal) blocks the route the NL path actually runs; lex only blocks `policy_design` and masks the deeper tail failure. Repairing lex alone does not unblock the route. *(workflow-mode truth, lex root cause)*
5. **GY-2 is govern + reframe, not build.** `run_experiment` runs in production, but `run_lifecycle.py:1408` discards the final state while `nl_pipeline.py:6596` captures it; the control job completes even on workflow failure. GY-2 must govern the workflow-report/final-state authority boundary across both paths and their surfaces. *(p0)*
6. **"Wire the catalog" is insufficient for GY-1.** Even injected, `resolve_metric_bindings → FetchPlan → connector fetch` returns rows but `persist_payload=True` writes 0 CAS objects — no measurement root. Catalog top-k has construct+scope precision@5 = 0.0 and country-filtered admission returns zero. Source-contract facets (0/16) and freshness are not joined into fetch admission. *(catalog-fetch, p2, source-contract, connector-family)*
7. **S12 / G5 cost-VOI pass is authorial.** `demand-act://ua-msme/principal` and `voi://ua-msme/site-1` come from a hardcoded readiness payload (`layer3_proving_ground_conversion.py:1219`) and do not dereference to produced S12 objects. *(p1)*
8. **The 406 candidate-positive statuses are all firewall-excluded** (397 diagnostic + 8 search-health + 1 demand-pull) — `positive_status_count=0`. Residual risk is surface laundering of diagnostic `pass` fields, not mis-counting. *(p0)*
9. **Generalization fails at depth-2.** The second case reproduces the lex failure; GX reducers are pinned to the ua-msme `data_home` (not case-parameterized). *(p0, p2)*
10. **Authority substrate gaps**: 0 `manifest.authority` on DAG CAS outputs; time semantics exclude `run_workflow`/`run_nodes`/`artifact_content`; raw `/artifacts/{id}/content` + `/download` leak `error.details.api_token` and bypass preview redaction. *(p1, runtime-surface)*

## 4. Quality of the audit campaign itself

Strengths (rare and worth stating): execution-over-label discipline held throughout; every audit has a recomputing validator and most have a negative repo-quality test; findings consistently resisted converting component maturity into authority (anti-greenwash); root causes were traced to file:line with reproducers (lex `_normalize_value_like(None)→0.0`; the `node.invalid_outcome` pydantic re-validation path; the `persist_payload` no-op).

Residual weaknesses in the campaign (not the system):

- **`output_hash` evidence is not replayable.** Several census smokes hashed wall-clock timing, so re-runs differ; validators check hash *shape*, not *reproducibility*. The evidence model proves presence, not replay. **Recommend**: canonicalize+time-strip before hashing, and add one replay test that re-derives and compares.
- **Two GY validators lack repo-quality tests** (`workflow_mode_truth`, `capability_coverage_matrix`); the lifecycle audit records 14 tests for 16 validators. Minor, but the suite's own discipline expects one test per validator.
- **Single-input depth.** Most execution facts are from the thin/synthetic-formalized UA panel; the governance-tail failure is input-sensitive. A small labelled multi-case set would harden the conclusions.

## 5. Readiness for GY-0.5 (the re-spec gate)

Task 0 now hands GY-0.5 a defensible map. The re-spec should:

1. **Re-baseline the progress meter** (1184→0; baseline = `search_ceiling_repair_required`).
2. **Re-scope to the workflow the route runs** (or first repair the resolver so explicit selection is honored), and decide the "one mode" target (shared 19-node spine + conditional arms; `policy_verified` is redundant).
3. **Order repairs by chain depth, not package**: (a) spine-first repair the `wired_but_rotten` rows (governance judge stack, resolver, lex, KnowledgeToolkit); (b) the 20 `bridge_missing` rows (GY-1 catalog→fetch→root + source-contract admission; GY-3 DataNeed bridge; GY-4 agent role-events; GY-6 OpenAlex provider); (c) the 10 `surface_missing` rows behind one authority boundary (CAS authority, time envelope, secret/PII gate, S12 refs, runtime/dashboard/public surfaces); (d) add a semantic/route-admissibility test at every step.
4. **Verbs must match gap class** (the matrix and census already enforce this): ~5 build-new items only; everything else is wire/govern/repair/extend. Any GY task that says "build" on a present asset is rejected.
5. **Forbid governance of rotten assets** (plan stop-rule): no GY-2 governance on the DAG until the spine governance tail accepts real measurement-rooted input.

## 6. One-line conclusion

Task 0 did its job: it proved, by execution, that PolicyOS's Layer-3 engines almost all *exist* and mostly *run*, and that the failure is concentrated at the **seams (bridge), the authority surfaces, and the missing route-admissibility tests** — and it corrected three stale premises before they could mis-shape the build. GY is an integration-and-governance program, not a construction one.

## Index of evidence

`layer3_gy_task0_audit/`: engine census; runtime-surface; catalog-fetch; connector-family-truth; source-contract-admissibility; data-requirement-compiler; lex-frontier-root-cause; foundry-breadth; agent-workflow-event-backing; generated-public-lifecycle; substrate-package-capability; workflow-mode-truth; p0-coverage; p1-substrate-authority; p2-semantic-evidence-quality; capability-coverage-matrix. Each has a `..._findings.md` and a `tools/quality/validation/check_layer3_gy_*` validator.

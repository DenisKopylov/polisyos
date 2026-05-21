---
title: PolicyOS Production Quality Best-In-Class Acceptance Evidence
status: report
owner: team-polisyos
created: 2026-05-13
last_verified: 2026-05-13
stability: snapshot
related:
  - ../../plans/active/POLICYOS_BEST_IN_CLASS_PRODUCTION_QUALITY_REMEDIATION_PLAN.md
  - ../../reference/runtime/production-quality-maturity.md
  - ../../reference/runtime/production-canary-matrix.md
  - ../../reference/runtime/quality-scorecard.md
---

# PolicyOS Production Quality Best-In-Class Acceptance Evidence

This report archives Phase 6.3 burn-in evidence for the production-quality
remediation program. The evidence was generated on 2026-05-13 from the
`codex/pq-scorecard-readiness-contract` workspace.

## Acceptance Verdict

| Gate | Result | Evidence |
| --- | --- | --- |
| Deterministic matrix burn-in | accepted | Three consecutive deterministic runs passed with no failed, blocked, or skipped lanes. |
| Readiness aggregator | strict gate blocks closeout | `_build/.tmp/production-quality/phase6_3/readiness_aggregator.json` reports `passes_all: false`, `passes_required: false`, `status: fail`, 17 passing findings, 7 failed findings, and 0 warning findings across PQL-001 through PQL-024. |
| Live-provider canary | accepted as quarantined failure evidence | `.polisyos/canary_evidence/phase6_3_live_provider/20260513T143108Z_08435a1b94674f0282db081a6387e98b` failed for a non-code provider/gateway reason after sanitized preflight evidence was recorded. |
| Approval evidence | archived, not approved | `_build/.tmp/production-quality/phase6_3/approval_packets/index.json` contains blocked packet samples for the deterministic warning lane and the live-provider failure lane. |
| Residual risks | accepted for follow-up | Residual risks are explicitly assigned below with owners and next review dates. |

No production decision is approved by this report. The deterministic lane is
CI-safe evidence, not a production release approval. The live-provider lane is
quarantined evidence and failed before a complete model variant, policy bundle,
or production approval packet could be produced. The strict readiness gate is
intentionally red until the remaining serious-profile refs are produced by
their owning layers or explicitly removed from production scope.

## Evidence Index

| Artifact | Path | Summary |
| --- | --- | --- |
| Readiness aggregator JSON | `_build/.tmp/production-quality/phase6_3/readiness_aggregator.json` | `policyos.production_quality_best_in_class_readiness.v1`; `passes_all: false`; `passes_required: false`; `status: fail`; attached live-provider evidence count 1. |
| Canary matrix catalog | `_build/.tmp/production-quality/phase6_3/canary_matrix_catalog.json` | `policyos.canary_matrix.v1`; 128 lanes: 8 ready, 64 quarantined, 40 deferred, 16 skipped, 1 CI-safe. |
| Deterministic matrix iteration 01 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_01.json` | 1 selected, 1 executed, 1 passed, 0 failed, scorecard `warn`. |
| Deterministic matrix iteration 02 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_02.json` | 1 selected, 1 executed, 1 passed, 0 failed, scorecard `warn`. |
| Deterministic matrix iteration 03 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_03.json` | 1 selected, 1 executed, 1 passed, 0 failed, scorecard `warn`. |
| Live-provider bundle | `.polisyos/canary_evidence/phase6_3_live_provider/20260513T143108Z_08435a1b94674f0282db081a6387e98b` | Research profile, `production_data`, live Gonka-compatible provider, execution failed at `llm_gateway/model_variants`. |
| Scenario pack summary | `_build/.tmp/production-quality/phase6_3/quality_benchmark_authority.json` | Catalog schema `policyos.golden_quality_scenarios.v2`; 5 packs, 6 scenarios, validation failures 0. |
| Approval packet samples | `_build/.tmp/production-quality/phase6_3/approval_packets/index.json` | Two blocked samples: `deterministic_warn` and `live_provider_failed`. |
| Replay result | Latest deterministic bundle `quality_evidence/replay_manifest.json` and `quality_evidence/drift_explanation.json` | Drift explanation status `match`; 0 differences; deterministic replay fingerprint archived per bundle. |
| Resilience matrix output | `_build/.tmp/production-quality/phase6_3/resilience_matrix.json` | 8 scenarios, 7 deterministic local, 1 quarantined, 8 approval-blocking scenarios, 4 fail-closed scenarios. |

## Burn-In Runs

| Iteration | Matrix JSON | Evidence bundle | Lane result | Scorecard | Replay fingerprint |
| --- | --- | --- | --- | --- | --- |
| 01 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_01.json` | `.polisyos/canary_evidence/phase6_3_burn_in/iteration_01/profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only/20260513T142933Z_2ec1597763b2477088de0505b0d10e80` | passed | `quality_status: warn`, `approval_state: quality_warn`, no blocking failures | `sha256:028e0b0bfdeb1c13ef7d67eb5295a0da17c463dc86adb0a3ea8459a163edb328` |
| 02 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_02.json` | `.polisyos/canary_evidence/phase6_3_burn_in/iteration_02/profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only/20260513T142952Z_31e4c4f95b9d4ba7ba68242f437acc9e` | passed | `quality_status: warn`, `approval_state: quality_warn`, no blocking failures | `sha256:a53fcaaa07b9aecc5f6b87d588f56f448b74d4b06ee719ca27ec4c6cdcbd7b14` |
| 03 | `_build/.tmp/production-quality/phase6_3/deterministic_matrix_03.json` | `.polisyos/canary_evidence/phase6_3_burn_in/iteration_03/profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only/20260513T143010Z_1b59e55447b84ee48cb59a018bb4c1ec` | passed | `quality_status: warn`, `approval_state: quality_warn`, no blocking failures | `sha256:e92d0ae28e597b581b89df2ed04ef056f001e0364915fec8331d8c615aa08f34` |

The deterministic scorecards warn, rather than fail, because the CI-safe lane
is a dev fixture lane. These warnings are acceptable for deterministic burn-in
evidence, but they do not satisfy the strict aggregate closeout gate. The
warning codes are stable and expected for this burn:
`provider_preflight_missing`, `llm_model_variants_missing`,
`production_data_quality_missing`,
`normative_applicability_report_ref_optional_missing`,
`foundry_method_report_ref_optional_missing`,
`policy_grounding_matrix_ref_optional_missing`, and
`conflict_check_ref_optional_missing`.

## Live-Provider Canary

The quarantined live-provider canary used `--mode=real`,
`--execution-profile=research`, `--canary-kind=research`, and
`--production-data-root=production_data`.

| Field | Value |
| --- | --- |
| Bundle | `.polisyos/canary_evidence/phase6_3_live_provider/20260513T143108Z_08435a1b94674f0282db081a6387e98b` |
| Scorecard | `quality_status: fail`, `approval_state: execution_failed` |
| Failure | `no_model_variant_completed` in `llm_gateway/model_variants` |
| Provider reason | `Failed LLM gateway call to https://proxy.gonka.gg/v1/chat/completions` |
| Next action | Retry after provider recovery or check gateway credentials, base URL, model id, and provider status. |
| Sanitization | `env.sanitized.json` stores API-key presence and fingerprint only; no raw key is archived. |

Provider preflight was archived at `provider_preflight.json` and reported
`status: ok` for health, models, capabilities, pricing, model presence, and a
tiny completion probe. The canary therefore failed after preflight, during the
full model-variant path. This is accepted as a clear non-code provider/gateway
failure with a sanitized evidence bundle.

## Scenario Packs

| Pack | Kind | Visibility | Scenario count | Version |
| --- | --- | --- | --- | --- |
| `public_baseline` | public | public | 2 | catalog schema `policyos.golden_quality_scenarios.v2` |
| `regression_guardrail` | regression | internal | 1 | catalog schema `policyos.golden_quality_scenarios.v2` |
| `adversarial_policy_stress` | adversarial | internal | 1 | catalog schema `policyos.golden_quality_scenarios.v2` |
| `hidden_holdout` | hidden | hidden | 1 | catalog schema `policyos.golden_quality_scenarios.v2` |
| `rotating_challenge` | rotating | hidden | 1 | catalog schema `policyos.golden_quality_scenarios.v2` |

The scenario catalog validation returned no failures. Hidden and rotating packs
remain quarantined and are represented by counts and contamination guards, not
by public answer material.

## System Assurance Summaries

| Assurance area | Evidence | Summary |
| --- | --- | --- |
| Data quality | Latest deterministic bundle `quality_evidence/production_data_quality.json` | Report status is `fail` because the CI-safe lane uses fixture-like data. Dev scorecard downgrades this to a non-blocking warning; serious profiles still fail closed. |
| Causal validity | Latest deterministic bundle `quality_evidence/causal_statistical_validity.json` | `status: pass`; 7 cases across difference-in-differences, regression discontinuity, and synthetic control; includes known-answer, missingness stress, negative control, placebo, and uncertainty calibration scenarios. |
| Security | Latest deterministic bundle `quality_evidence/security_assurance_report.json` | `status: pass`; runtime abuse surfaces are represented in the evidence bundle without secrets. |
| Privacy | Latest deterministic bundle `quality_evidence/privacy_compliance_report.json` | `status: pass`; 3 production-data source records, 0 public artifact families, 0 PII-like fields, 0 blocking issues, 0 warnings. |
| Replay | Latest deterministic bundle `quality_evidence/replay_manifest.json` and `quality_evidence/drift_explanation.json` | Drift explanation `status: match`; 0 differences, 0 accepted differences, 0 unexplained differences. |
| Resilience | `_build/.tmp/production-quality/phase6_3/resilience_matrix.json` | 8 scenarios; 4 performance warnings, 2 operational failures, 1 quality failure, 4 fail-closed scenarios. These are deterministic stress fixtures, not production incident records. |
| Human review | Latest deterministic bundle `quality_evidence/human_review_calibration_report.json` | `status: pass`; no review events were present in the burn-in lane, so reviewer agreement and override correctness denominators are 0. |
| Provider drift | Live-provider bundle `provider_preflight.json` and failure envelope | Preflight was healthy, but no complete model variant was produced. `provider_model_quality_ledger.json` was not generated for this burn because there were no provider-quality observations; PQL-022 is therefore a strict readiness failure. |
| Decision artifact quality | Latest deterministic bundle `quality_evidence/decision_artifact_quality.json` | `status: pass`; 11 required sections, 9 input refs, 0 issues. Recommendation count is 0 for the dev fixture run. |

## Approval Packet Samples

| Sample | Path | Decision | Eligibility reasons |
| --- | --- | --- | --- |
| Deterministic warning lane | `_build/.tmp/production-quality/phase6_3/approval_packets/deterministic_warn.json` | blocked | `quality_not_passing` |
| Live-provider failed lane | `_build/.tmp/production-quality/phase6_3/approval_packets/live_provider_failed.json` | blocked | `blocking_quality_failures`, `conflict_blocking`, `execution_not_completed`, `quality_not_passing` |

These samples prove packet derivation and blocking semantics. They do not grant
approval.

## Residual Risks

| Risk | Owner | Next review date | Evidence or trigger |
| --- | --- | --- | --- |
| CI-safe deterministic lane only covers the dev fixture public-golden API lane; research, governed, production, dashboard, negative, adversarial, and hidden lanes remain quarantined, deferred, or skipped. | team-ops/team-runtime | 2026-05-20 | `_build/.tmp/production-quality/phase6_3/canary_matrix_catalog.json` |
| Fixture-like production data quality is warning-only for dev burn-in but remains blocking for serious profiles. A serious-profile pass still requires non-fixture production data diagnostics. | team-fabric/team-data-forge | 2026-05-20 | latest deterministic `quality_evidence/production_data_quality.json` |
| Live provider failed after healthy preflight with no completed model variant, so provider quality drift metrics could not be measured. | team-scientist/team-ops | 2026-05-16 | live-provider `failure.json`; missing provider ledger observations |
| Human-review calibration has no real reviewer events in this burn; agreement, override correctness, and burden metrics have zero denominators. | team-governance/team-dashboard | 2026-05-27 | latest deterministic `quality_evidence/human_review_calibration_report.json` |
| Resilience matrix records deterministic stress fixtures with approval-blocking outcomes; it is not yet a successful soak/load acceptance for production traffic. | team-ops/team-runtime | 2026-05-20 | `_build/.tmp/production-quality/phase6_3/resilience_matrix.json` |
| Scenario packs rely on catalog schema versioning; pack-level semantic version fields are not declared. | team-quality | 2026-05-27 | `_build/.tmp/production-quality/phase6_3/quality_benchmark_authority.json` |

## Verification Commands

Phase 6.3 verification targets:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic
PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract
corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke
uv run python tools/quality/testing/local_integration_stack.py smoke
```

The burn-in matrix was run three times with explicit JSON outputs under
`_build/.tmp/production-quality/phase6_3/`.

Fresh verification on 2026-05-13:

| Command | Result | Evidence |
| --- | --- | --- |
| `uv run python tools/ops_runners/runtime/run_canary_matrix.py --deterministic` | passed | 1 selected, 1 executed, 1 passed; bundle `.polisyos/canary_evidence/profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only/20260513T144857Z_a5f7d0aae66d44aeb8038b272c85b30e`; scorecard `warn`. |
| `PYTHONPATH=src:. uv run --extra runtime --extra ml polisyos-tools runtime check-runtime-api-contract` | passed | OpenAPI contract and generated runtime API clients matched after archiving the production-approval success example. |
| `corepack pnpm --dir apps/runtime-dashboard run test:journeys:smoke` | passed | 16 Playwright smoke journeys passed across desktop and mobile Chromium. |
| `uv run python tools/quality/testing/local_integration_stack.py smoke` | passed | Runtime API, dashboard, and proxy health were ready; nested dashboard smoke reported 16 passed. |

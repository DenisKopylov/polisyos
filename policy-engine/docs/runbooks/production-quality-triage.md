# Production Quality Triage

Related runbook: [Production quality canary](production-quality-canary.md).
Related reference: [Production quality approval](../reference/runtime/production-quality-approval.md),
[Runtime quality scorecard](../reference/runtime/quality-scorecard.md), and
[Production resilience matrix](../reference/runtime/production-resilience-matrix.md).

Owner: `@platform-owners`
Primary responders: `@runtime-owners`, `@scientist-owners`,
`@foundry-owners`, `@fabric-owners`, `@lex-owners`, and
security/compliance reviewers.
Evidence path: `.polisyos/canary_evidence/<bundle>/`,
`_build/.tmp/production-quality/`, and CAS refs copied into scorecards.

Use this runbook when a canary, matrix lane, approval packet, replay check,
resilience matrix, provider ledger, or aggregate production-quality gate fails.

## First Five Minutes

1. Stop promotion for the affected candidate. Do not delete or overwrite the
   bundle.
2. Locate the failure envelope:

   ```bash
   uv run python - "$MATRIX_JSON" <<'PY'
   import json
   import sys
   from pathlib import Path

   payload = json.loads(Path(sys.argv[1]).read_text())
   print(json.dumps(payload.get("summary", {}).get("failure_envelope"), indent=2, sort_keys=True))
   for lane in payload.get("lanes", []):
       if lane.get("failure_envelope"):
           print("lane=", lane.get("lane_id"))
           print(json.dumps(lane["failure_envelope"], indent=2, sort_keys=True))
   PY
   ```

3. If a bundle exists, locate the scorecard and blocking failures:

   ```bash
   uv run python - "$BUNDLE" <<'PY'
   import json
   import sys
   from pathlib import Path

   bundle = Path(sys.argv[1])
   scorecard = json.loads((bundle / "quality_evidence" / "quality_scorecard.json").read_text())
   print("bundle=", bundle)
   print("scorecard=", bundle / "quality_evidence" / "quality_scorecard.json")
   print("execution=", scorecard.get("execution_status"))
   print("quality=", scorecard.get("quality_status"))
   print("approval=", scorecard.get("approval_state"))
   for item in scorecard.get("blocking_quality_failures") or []:
       print(f"{item.get('code')} | {item.get('layer')} | {item.get('phase')} | {item.get('evidence_ref')} | {item.get('next_action')}")
   PY
   ```

4. Route by `layer` and `phase`. If the envelope has no layer, route to
   `@runtime-owners` until the runtime failure shape is understood.
5. Record the next action from the failure envelope or scorecard. Do not invent
   a new action while a machine-readable one is already present.

## Layer And Phase Routing

| Layer | Common phases | Primary evidence | First owner | First action |
| --- | --- | --- | --- | --- |
| `control_plane` | `control.job_lease`, `control.job_heartbeat`, `workflow_run` | job response, failure envelope, control SQLite state | `@runtime-owners` | Check worker lease, heartbeat, queue saturation, and retry posture. |
| `runtime_api` | `runtime.run_index_refresh`, `runtime.timeline_build`, `api.job_detail` | run/timeline/lineage responses, hot-path observations | `@runtime-owners` | Separate read-path degradation from failed write/control execution. |
| `llm_gateway` or `provider_gateway` | `provider.preflight`, model variant selection, schema repair | `provider_preflight.json`, provider ledger, failure variants | `@scientist-owners` + ops | Check provider availability, model id, budget, timeout, schema failure, and drift. |
| `fabric` or `fabric_materialization` | `fabric.materialization`, source selection, retrieval trace | `production_data_evidence.json`, `fabric_retrieval_trace.json`, data-quality report | `@fabric-owners` | Verify production snapshot, source family, lineage, missingness, and TTL. |
| `data_forge` | production manifest, compliance inputs, source bundles | `production_data_quality_report_ref`, privacy report | `@fabric-owners` + compliance | Check data dictionary, units, PII/license/retention, and cohort leakage. |
| `lex` | normative applicability, conflict check | `normative_evidence.json`, `conflict_check.json` | `@lex-owners` | Check applicable norms, rejected norms, legal scope, and conflict issues. |
| `foundry` | method report, causal/statistical validity | `foundry_method_report.json`, `causal_statistical_validity_report_ref` | `@foundry-owners` | Check estimator assumptions, placebo/negative-control failures, sensitivity, and uncertainty. |
| `scientist` | grounding, citation, source quality, decision artifact | policy grounding matrix, citation/source/decision reports | `@scientist-owners` | Check major claims, citation refs, support predicates, and public artifact completeness. |
| `runtime_quality_scorecard` | scorecard build, report gates, approval state | `quality_scorecard.json` | `@runtime-owners` | Confirm refs are runtime-owned and serious-profile gates fail closed. |
| `security` | abuse gate, injection, exfiltration, artifact path hardening | `security_assurance_report_ref`, abuse fixtures | security reviewer | Block promotion until injection/exfiltration findings are closed or explicitly non-applicable. |
| `privacy_compliance` | PII, license, retention, jurisdiction, export | `privacy_compliance_report_ref` | compliance reviewer | Confirm basis, redaction, license, public export, retention, and override completeness. |
| `replay` | manifest, drift explanation | `replay.json`, `replay_manifest_ref`, `drift_explanation_ref` | `@runtime-owners` | Require typed drift source and accepted impact for any replay difference. |
| `resilience` | load, soak, retry storm, brownout, CAS pressure, dashboard | `resilience_matrix.json`, `operator_findings[]` | `@platform-owners` | Distinguish performance warning, operational failure, quality failure, and quarantine. |
| `dashboard` | route render, failure/approval panels | Playwright trace, `dashboard.json` | `@frontend-owners` | Confirm operator can see scorecard, bundle, approval, and next action. |

## Report Interpretation

| Report | Healthy signal | Blocking signal | Operator action |
| --- | --- | --- | --- |
| Data quality | `status=pass`, production snapshot refs present, diagnostics clean | fixture-like evidence, schema drift, missingness, unit drift, leakage, TTL, affected major claim | Open `issues[]`, check `claim_diagnostics[]`, then verify manifest checksum and source bundle versions. |
| Causal/statistical validity | known-answer, placebo, negative-control, sensitivity, power, and calibration cases pass | benchmark `status=fail` for major causal/numerical claim | Route to Foundry; do not approve major causal/numeric recommendations until the failing case is fixed or removed from scope. |
| Security assurance | abuse gates pass and public artifacts contain no injection/exfiltration material | prompt/tool/provider injection, malicious source, poisoned provider response, secret exfiltration | Treat as release blocker; attach the failing abuse case and never override a live secret leak. |
| Privacy compliance | basis/redaction/license/retention/export checks pass | PII without basis, restricted license, public export disallowed, incomplete compliance override | Compliance reviewer decides; production approval blocks until packet is complete. |
| Replay | `production_readiness=pass` and no unexplained differences | unaccepted drift across code, data, source, norm, provider, model, config, prompt, CAS, dependency, or nondeterminism | Compare baseline/replay manifest, accept only typed bounded drift, rerun if nondeterminism is suspected. |
| Resilience | no operational or quality failures; warnings are understood | queue/heartbeat/preflight operational failure, missing evidence under soak, brownout without approval | Route by scenario classification; performance warnings need review or override for serious profiles. |
| Human review | agreement, override correctness, burden, and unresolved disagreements within thresholds | low agreement, high override rate, low correctness, high burden, unresolved disagreement | Block or escalate; weak reviewer behavior cannot approve a weak scorecard. |
| Provider drift | default production model action is `approve` | `require_review`, `demote`, `block_production_approval`, stale/missing default evidence | Attach provider ledger, check model fingerprint and evidence age, then choose approve/review/demote/block. |
| Decision artifact | major sections complete, citations preserved, public export clean | missing uncertainty/tradeoff/distributional/budget/risk sections, overconfidence, dropped citations, forbidden data | Recompile/fix final artifact; public export leaks are blockers. |

## Approval Triage

Open the approval packet or dry-run it from the bundle:

```bash
uv run python - "$BUNDLE" <<'PY'
import json
import sys
from pathlib import Path
from polisyos.runtime.quality.approval import build_production_approval_packet

scorecard = json.loads((Path(sys.argv[1]) / "quality_evidence" / "quality_scorecard.json").read_text())
packet = build_production_approval_packet(scorecard=scorecard).model_dump(mode="json", exclude_none=True)
print(packet["decision"])
print(packet["eligibility"]["reasons"])
PY
```

Expected clean output:

```text
approved
[]
```

If the decision is `blocked`, route each reason:

| Reason | Route |
| --- | --- |
| `execution_not_completed` | Control-plane failure envelope. |
| `quality_not_passing` | Scorecard gates and assurance reports. |
| `blocking_quality_failures` | Each failure layer and phase. |
| `performance_budget_blocking` | Resilience matrix and override review. |
| `conflict_blocking` | Lex conflict report and legal reviewer. |

## PQL Finding Triage Table

| Finding | Severity | Layer and phase | Evidence to open | Next action | Verification |
| --- | --- | --- | --- | --- | --- |
| PQL-001 | Critical | Lex/Fabric/Foundry/Scientist, Phase 1 | `quality_scorecard.evidence_refs`, runtime-owned report refs | Missing runtime-owned subreport refs fail serious profiles; route to the owning layer that should emit the ref. | `uv run python tools/quality/validation/production_quality_evidence_inventory.py --repo-root . --check` |
| PQL-002 | Critical | Scientist final artifact, Phases 1-2 | policy grounding matrix, claim support, citation report | Rebuild final claims with automatic extraction, grounding matrix, and citation preservation. | `uv run pytest tests/unit/scientist/validation/test_policy_grounding_matrix.py tests/unit/scientist/validation/test_claim_support.py -q` |
| PQL-003 | Critical | runtime, IR metric registry, Trinity linker, Phase 1 | foundry method report, metric registry diagnostics, control failure envelope | Reject unknown metrics before late healing; add registry/trinity mapping or correct the request. | `uv run pytest tests/unit/core/phase0/test_metrics.py tests/contract/test_trinity_linker_contract.py -q` |
| PQL-004 | Critical | Lex, Scientist governance, Phase 2 | `quality_evidence/conflict_check.json` | Run conflict checks from active corpus plus final claims; block unresolved legal/norm conflicts. | `uv run pytest tests/unit/lex/test_conflict_check_report.py -q` |
| PQL-005 | High | runtime quality, control API, Phase 2 | `quality_scorecard.json`, approval eligibility, progress projection | Confirm scorecard refs, provenance, and approval readiness are projected from persisted runtime evidence. | `uv run pytest tests/unit/runtime/quality/test_scorecard.py tests/unit/runtime/http/test_control_api.py -q` |
| PQL-006 | High | dashboard, governance, Phase 2 | approval packet ref, override packet, dashboard review panel | Create or inspect production approval packet; require reviewer trail for overrides. | `uv run pytest tests/unit/runtime/quality/test_approval.py tests/unit/tools/test_canary_evidence.py -q` |
| PQL-007 | Critical | quality/evals, Phase 3 | `golden_quality_scenarios.json`, benchmark authority public export | Validate public, regression, adversarial, hidden, and rotating scenario-pack metadata without leaking hidden answers. | `uv run pytest tests/repo_quality/tools/test_quality_benchmark_authority.py -q` |
| PQL-008 | Critical | Scientist evidence, Lex, Phase 3 | citation faithfulness, claim support, legal exception issues | Verify semantic support, citation faithfulness, scope fit, and legal exceptions for major claims. | `uv run pytest tests/unit/scientist/validation/test_citation_faithfulness.py tests/unit/scientist/validation/test_claim_support.py -q` |
| PQL-009 | High | Scientist evidence, Fabric, Phase 3 | source quality report, Fabric retrieval trace | Treat stale, withdrawn, conflicted, duplicate, or low-authority source state as decision signal, not a cosmetic score. | `uv run pytest tests/unit/scientist/evidence/test_source_quality.py tests/unit/fabric/test_source_selection_audit.py -q` |
| PQL-010 | High | Scientist LLM orchestration, Phase 3 | LLM variant evidence, provider/model ledger, adjudication rationale | Inspect disagreement and selected-variant rationale; require runtime adjudication for conflicting model outputs. | `uv run pytest tests/unit/scientist/orchestration/llm/test_provider_quality.py -q` |
| PQL-011 | Medium | ops/runtime/dashboard, Phase 4 | `canary_performance_budget.json`, matrix run JSON, dashboard smoke evidence | Normalize performance evidence across control job, CAS, runtime API, and dashboard route render. | `uv run pytest tests/performance/test_runtime_hot_paths.py tests/repo_quality/tools/test_canary_matrix.py -q` |
| PQL-012 | High | core artifacts, runtime, Phase 4 | artifact ownership refs, CAS tenant/cell evidence | Block governed/production approval when tenant-scoped artifact ownership cannot be proven. | `uv run pytest tests/unit/core/artifacts/test_artifact_id_serialization_contract.py tests/unit/runtime/http/test_control_api.py -q` |
| PQL-013 | High | ops runners, Phase 4 | canary matrix JSON and lane bundle paths | Run the stable matrix lane or explain quarantined/deferred/skipped status with exit criteria. | `uv run python tools/ops_runners/runtime/canary_matrix.py --list --json-output _build/.tmp/production-quality/canary_matrix.json` |
| PQL-014 | High | continuous governance, Phase 4 | reissue plan, withdrawal record, decision validity report | Use reissue for stale/review-required decisions and withdrawal records for explicit public withdrawal. | `uv run pytest tests/unit/scientist/governance/continuous -q` |
| PQL-015 | Critical | Fabric/Data Forge, Phase 5 | `production_data_quality_report_ref`, production data evidence | Check schema drift, missingness, outliers, unit drift, leakage, construct validity, coverage, and TTL. | `uv run pytest tests/unit/runtime/quality/test_data_quality.py tests/unit/data_forge -q` |
| PQL-016 | Critical | Foundry/Scientist, Phase 5 | `causal_statistical_validity_report_ref` | Block major causal/numeric claims when known-answer, placebo, negative-control, sensitivity, power, or calibration cases fail. | `uv run pytest tests/unit/foundry/validation/test_causal_validity.py tests/unit/scientist/validation/test_policy_grounding_matrix.py -q` |
| PQL-017 | Critical | security/runtime/Scientist, Phase 5 | `security_assurance_report_ref`, abuse fixture result | Treat prompt/tool/provider injection, malicious sources, and secret exfiltration as release blockers. | `uv run pytest tests/security/test_policyos_runtime_abuse_gates.py -q` |
| PQL-018 | Critical | governance/Data Forge, Phase 5 | `privacy_compliance_report_ref` | Verify PII basis, redaction, license, retention, jurisdiction, export posture, and compliance override completeness. | `uv run pytest tests/unit/runtime/quality/test_compliance.py tests/unit/data_forge -q` |
| PQL-019 | High | runtime/Scientist, Phase 5 | `replay.json`, replay manifest, drift explanation | Require deterministic replay and accepted typed drift before approval. | `uv run pytest tests/unit/runtime/quality/test_replay.py tests/repo_quality/tools/test_replay_canary_bundle.py -q` |
| PQL-020 | High | ops/runtime/dashboard, Phase 5 | resilience matrix, performance budget, dashboard evidence | Classify load/soak/retry/brownout/CAS/dashboard failures and decide block, override, or quarantine. | `uv run python tools/quality/testing/runtime_resilience_matrix.py --deterministic --json-output _build/.tmp/production-quality/resilience_matrix.json` |
| PQL-021 | High | governance/dashboard, Phase 5 | `human_review_calibration_report_ref`, override packet | Check reviewer agreement, override correctness, burden, unresolved disagreements, and reviewer attribution. | `uv run pytest tests/unit/runtime/quality/test_human_review.py tests/unit/runtime/quality/test_approval.py -q` |
| PQL-022 | High | LLM orchestration/ops, Phase 5 | `provider_model_quality_ledger_ref` | Review schema failure, grounding failure, disagreement, latency, cost, context pressure, and stale default evidence. | `uv run python -m tools.ops_runners.runtime.provider_quality_ledger --input-root .polisyos/canary_evidence --output .polisyos/provider_quality/provider_model_quality_ledger.json` |
| PQL-023 | Critical | Scientist/dashboard, Phase 5 | `decision_artifact_quality_report_ref`, public decision artifact | Require uncertainty, tradeoffs, distributional impact, feasibility, budget, stakeholders, residual risk, and citations. | `uv run pytest tests/unit/scientist/validation/test_decision_artifact_quality.py tests/unit/scientist/artifacts/test_decision_compiler.py -q` |
| PQL-024 | Medium | team-polisyos, Phase 6 | aggregate readiness gate output, docs closeout, release evidence pack | Attach aggregate pass/warn/fail findings, canary summaries, approval packets, residual risks, and docs refs. | `uv run python tools/quality/validation/check_docs_gate.py --repo-root .` |

## Escalation Rules

- Critical PQL findings block production approval unless the owning lead and
  governance reviewer explicitly mark the run out of production scope.
- Security, privacy, public-export, and hidden-benchmark leaks are not
  performance overrides. Treat them as blockers.
- Live-provider quarantines are expected until an operator supplies explicit
  approval and credentials in a controlled environment.
- A warning without a named owner, evidence ref, and expiry becomes a blocker
  for `production`, `governed`, and `research` profiles.

## Closeout Record

Every triage note should include:

- UTC detection and mitigation timeline;
- lane id or run id;
- bundle path;
- scorecard ref and status;
- failure envelope code, layer, phase, and next action;
- approval packet ref or reason no packet was created;
- replay and resilience refs when applicable;
- PQL ids touched;
- owner and due date for each remediation.

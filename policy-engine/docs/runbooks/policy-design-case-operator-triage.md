# Policy Design Case Operator Triage

Related runbooks: [Honest Diagnostics Operator Triage](honest-diagnostics.md),
[Production Quality Triage](production-quality-triage.md),
[Production Quality Canary](production-quality-canary.md), and
[Replay or Restore Workflow](replay-or-restore.md). For promotion, hold,
rollback, or kill-switch work, use
[Policy Design Case Rollout And Rollback](policy-design-case-rollout-rollback.md).

Related reference:
`docs/system-design-decisions/policy-design-best-in-class-operating-model.md`,
[Policy Design Case Operator Guide](../reference/policy-design-case-operator-guide.md),
[Policy Design Case Evidence Paths](../reference/policy-design-case-evidence-paths.md),
[Production Quality Approval](../reference/runtime/production-quality-approval.md),
[Runtime Quality Scorecard](../reference/runtime/quality-scorecard.md), and
[Run Cost Proportionality Ledger](../reference/runtime/run-cost-proportionality-ledger.md).

Owner: `@platform-owners` with `@runtime-owners`, `@scientist-owners`,
`@foundry-owners`, `@fabric-owners`, `@lex-owners`, `@core-audit-owners`,
`@ddm-owners`, and governance reviewers.
Last tested: `2026-05-19` against Wave 40 closeout evidence.
Evidence path: `quality_evidence/policy_design_case.json`,
`quality_evidence/quality_scorecard.json`,
`quality_evidence/assurance_case.json`,
`quality_evidence/semantic_binding_ledger.json`,
`quality_evidence/decision_artifact_quality.json`,
`quality_evidence/replay_manifest.json`, Wave 35H provenance artifacts under
`_build/policy-design-case/rebaseline/wave-35H/`, and Wave 40 closeout artifacts
under `_build/policy-design-case/rebaseline/wave-40/`. Durable command-evidence
and closeout-note paths follow
`docs/reference/policy-design-case-evidence-paths.md`.
Rollback path: follow
`docs/runbooks/policy-design-case-rollout-rollback.md`; stop promotion,
preserve the original bundle and runtime CAS refs, quarantine
public/dashboard/API/export projections, disable or downgrade the affected
feature flags and tuned configs, and rerun only the producer that owns the
missing or contradictory record family.

Use this runbook when a serious PolicyOS run cannot close because the Policy
Design Case is missing, incomplete, divergent, too weak for the requested
authority profile, or projected more strongly than runtime evidence permits.

## Authority Rules

- Runtime-owned Policy Design Case records and typed blockers are authority.
  Scorecards, dashboards, public exports, and archive reports are readers.
- A missing case family must stay visible as a blocker. Do not fill it with a
  static inventory row, generic note, or bundle-local file path.
- Evidence that is not applicable must be represented as typed
  out-of-scope authority policy, not as absence.
- Human judgement, consultation, benchmarking, proportionality, and external
  audit evidence are first-class record families. They cannot masquerade as
  observed data or automatic model output.
- If a public export, dashboard, or API response claims stronger authority than
  the case evidence supports, freeze publication before retrying producers.

## First 15 Minutes

1. Stop publication, approval, and promotion for the affected run.
2. Capture `RUN_ID`, `JOB_ID`, tenant, cell, execution profile, bundle path,
   scorecard ref, public export ref, and dashboard URL.
3. Inspect the scorecard blockers and evidence refs:

   ```bash
   uv run python - "$SCORECARD_JSON" <<'PY'
   import json
   import sys
   from pathlib import Path

   scorecard = json.loads(Path(sys.argv[1]).read_text())
   print("execution=", scorecard.get("execution_status"))
   print("quality=", scorecard.get("quality_status"))
   print("approval=", scorecard.get("approval_state"))
   print(json.dumps(scorecard.get("evidence_refs", {}), indent=2, sort_keys=True))
   for item in scorecard.get("blocking_quality_failures") or []:
       print(
           item.get("code"),
           "| gate=", item.get("gate"),
           "| layer=", item.get("layer"),
           "| phase=", item.get("phase"),
           "| ref=", item.get("evidence_ref"),
           "| next=", item.get("next_action"),
       )
   PY
   ```

4. Confirm whether the Policy Design Case artifact exists and which record
   families are present:

   ```bash
   uv run python - "$BUNDLE" <<'PY'
   import json
   import sys
   from pathlib import Path

   root = Path(sys.argv[1]) / "quality_evidence"
   case_path = root / "policy_design_case.json"
   print("policy_design_case=", case_path if case_path.exists() else "missing")
   if case_path.exists():
       payload = json.loads(case_path.read_text())
       for key, value in sorted(payload.items()):
           if key.endswith("_refs") or key.endswith("_ledgers") or key.endswith("_records"):
               print(key, "count=", len(value) if isinstance(value, list) else "present")
   PY
   ```

5. Route by the first missing authority family. If multiple families are missing,
   start with intent/capability/spine before producer, portfolio, claim, or
   publication layers.

## Failure Routing

| Failure mode | Primary signals | First checks | Mitigation and owner | Verification |
| --- | --- | --- | --- | --- |
| Missing case | `policy_design_case_missing`, `policy_design_case_ref_missing`, missing `quality_evidence/policy_design_case.json`, or a scorecard with no case ref | Check runtime progress refs, CAS manifest, `assurance_case.json`, and scorecard evidence refs | Keep approval blocked. Route to `@runtime-owners`; reemit the runtime case or a typed case blocker. | `uv run pytest tests/unit/runtime/quality/test_policy_design_case_record_registry.py tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py -q` |
| Missing intent | `policy_intent_envelope_ref_missing`, missing capability ledger, requester-capture challenge absent, or route chosen before intent materialization | Check intent envelope, capability ledger, requested/effective authority profile, and skip blockers | Rerun pre-routing intent/capability producers. Owner: `@runtime-owners` with `@scientist-owners`. | `uv run pytest tests/unit/runtime/quality/test_policy_intent_envelope.py tests/unit/runtime/quality/test_skip_blockers.py -q` |
| Missing spine | `semantic_spine_context_missing`, unresolved concept spine, jurisdiction competence blocker, or claim refs bound to incompatible concepts | Check concept spine, jurisdiction spine, semantic binding ledger, legal/data/method/claim refs, and conflict records | Block final claims until the spine producer emits a resolved spine or typed unresolved-jurisdiction blocker. Owner: `@lex-owners`, `@fabric-owners`, and `@scientist-owners`. | `uv run pytest tests/unit/runtime/quality/test_policy_design_case_concept_spine.py tests/unit/runtime/quality/test_policy_design_jurisdiction_spine.py -q` |
| Missing producer refs | Lex, Fabric, Scholar, Data Forge, Foundry, BERL, DDM, or audit families absent while claims consume their output | Open `quality_scorecard.evidence_refs`, producer-specific report refs, and first missing producer breadcrumbs | Rerun or repair the owning producer. Do not substitute static inventory or manifest role rows. Owner follows the missing producer. | `uv run python tools/quality/validation/production_quality_evidence_inventory.py --repo-root . --check` |
| Portfolio divergence | Evidence portfolio count exists but independent strands, disconfirming evidence, or specification curves disagree with the major claim | Check portfolio design, evidence line model, independence map, multiverse/specification curve, and disconfirming ledgers | Downgrade or block major claims until divergence is represented in synthesis and rebuttal records. Owner: `@scientist-owners` and `@foundry-owners`. | `uv run pytest tests/unit/runtime/quality/test_evidence_portfolio_design.py tests/unit/runtime/quality/test_evidence_independence_map.py -q` |
| Synthesis fragility | Synthesis report missing, certainty changes under sensitivity, stopping rule absent, or one evidence line dominates without accepted deficit | Check synthesis sensitivity, certainty rating, stopping-rule result, and information saturation report | Keep claim compiler blocked or attach an accepted deficit visible to reviewers. Owner: `@scientist-owners`. | `uv run pytest tests/unit/runtime/quality/test_evidence_synthesis_report.py tests/unit/runtime/quality/test_multiverse_specification_curve.py -q` |
| Unsupported claim | Major claim lacks data, norm, method, portfolio, uncertainty, or argument/warrant refs | Inspect claim argument records, final artifact section refs, rebuttals, counter-evidence, and assurance deficits | Recompile claims from runtime refs or block the claim. Owner: `@scientist-owners` and `@claim-compiler-owners`. | `uv run pytest tests/unit/runtime/quality/test_claim_argument.py tests/unit/scientist/validation/test_claim_support.py -q` |
| BERL failure | BERL reliability required by authority profile but missing, stale, below threshold, or not bound to a warrant | Check explanation reliability refs, local infidelity bounds, BERL warrant bridge, and authority profile | Remove BERL-backed warrant support or emit valid reliability evidence before acceptance. Owner: `@claim-compiler-owners`. | `uv run pytest tests/unit/runtime/quality/test_berl_warrant_reliability.py -q` |
| DDM failure | DDM readiness, drift, degradation, stationarity, incident, or root-cause refs missing for claims that depend on model or lifecycle evidence | Check DDM monitoring bridge, model registry readiness, lifecycle events, and claim-to-monitor map | Block publication or mark stale/reissue/withdraw until DDM evidence is present. Owner: `@ddm-owners`. | `uv run pytest tests/unit/runtime/quality/test_policy_design_case_lifecycle.py tests/unit/ddm/test_readiness_mapping.py -q` |
| External audit failure | Publication trust, external audit archive, standalone verifier, signature, redaction proof, or public export authority missing | Check publication trust record, verifier output, PROV/SLSA refs, public export bundle, and archive refs | Freeze public export. Rebuild audit package or record typed non-public scope. Owner: `@core-audit-owners`. | `uv run pytest tests/unit/runtime/quality/test_external_audit.py tests/unit/runtime/quality/test_public_export.py -q` |
| Self-FMEA failure | Integrity self-FMEA absent, adversarial assumptions untested, partial-state contradictions unrepresented, or threat model gaps ignored | Check self-FMEA record, integrity threat model, partial-state reconciliation, and adversarial negative traces | Keep scorecard blocked until the integrity record is regenerated or a typed blocker is visible. Owner: `@platform-owners`. | `uv run pytest tests/unit/runtime/quality/test_policy_design_case_evidence_graph_threat_model.py tests/unit/runtime/quality/test_crash_retry_partial_state.py -q` |
| Maturity regression | Case maturity profile drops below authority floor, previous pass becomes warning/fail, or dashboard hides maturity caveat | Check maturity profile, coverage deltas, target failures, and public/dashboard labels | Demote readiness or freeze publication until regression is explained and accepted. Owner: `@platform-owners`. | `uv run pytest tests/unit/runtime/quality/test_case_maturity.py tests/repo_quality/tools/test_policy_design_case_coverage.py -q` |
| Missing formal invariant | Required invariant spec, proof harness evidence, or invariant registry row missing for authority ordering, phase barriers, lifecycle, publication, or proportionality | Open `architecture/policy_design_case/formal_invariant_specs.toml` and `quality_evidence/invariant_proof_harness_report.json` | Treat closeout as blocked. Add the invariant evidence or explicitly scope it out by authority policy. Owner: `@platform-owners`. | `uv run python tools/quality/validation/check_policy_design_formal_invariants.py --repo-root . --require-passing` |
| Missing consultation response | Consultation record absent, response-to-comment incomplete, stakeholder challenge unresolved, or zero-denominator caveat missing | Check consultation evidence, structured judgement record, human oversight calibration, and public contestability ledger | Keep public authority blocked or mark consultation out of scope with typed authority policy. Owner: governance reviewers. | `uv run pytest tests/unit/runtime/quality/test_consultation.py tests/unit/runtime/quality/test_human_review.py -q` |
| Hidden expert judgement | Expert judgement affects claims without protocol, qualification, independence, dissent, or requester-capture evidence | Check structured judgement record, reviewer independence, dissent, override, and requester-capture challenge | Strip judgement from claim support or emit full structured judgement evidence. Owner: governance reviewers. | `uv run pytest tests/unit/runtime/quality/test_human_review.py tests/unit/runtime/quality/test_policy_design_case_false_passes.py -q` |
| Proportionality failure | Run cost, evidence budget, reviewer/consultation burden, or budget-change authority missing or disproportionate for impact level | Check run cost proportionality ledger, evidence budget, stopping-rule proof, and cost waiver policy | Block closeout until proportionality is justified; cost alone cannot waive required evidence. Owner: `@scientist-owners` and `@platform-owners`. | `uv run pytest tests/unit/runtime/quality/test_run_cost_proportionality.py -q` |
| Benchmarking failure | Best-in-class benchmark missing, stale, hidden-answer contaminated, not bound to claim family, or below threshold | Check benchmarking record, benchmark authority pack, hidden/public split, leakage guard, and comparison baseline | Demote readiness or require review; never expose hidden benchmark answers in public artifacts. Owner: `@scientist-owners`. | `uv run pytest tests/unit/runtime/quality/test_policy_benchmarking.py tests/repo_quality/tools/test_quality_benchmark_authority.py -q` |

## Escalation Map

| Evidence family | First owner | Supporting owners |
| --- | --- | --- |
| Case artifact, scorecard refs, readiness gates, record registry | `@runtime-owners` | `@platform-owners` |
| Intent, capability, requester-capture, profile mapping | `@runtime-owners` | `@scientist-owners` |
| Concept spine, jurisdiction, legal authority | `@lex-owners` | `@fabric-owners`, governance reviewers |
| Data, source, snapshot, lineage, rights | `@fabric-owners` | `@runtime-owners` |
| Method validity, uncertainty, portfolio, synthesis, benchmarking | `@foundry-owners` and `@scientist-owners` | `@platform-owners` |
| Claim argument, warrant, BERL reliability, final artifact | `@claim-compiler-owners` | `@scientist-owners` |
| Lifecycle, DDM, ex-post, monitoring | `@ddm-owners` | `@scientist-owners` |
| Human oversight, consultation, structured judgement | governance reviewers | `@platform-owners` |
| Publication trust, external audit, archive | `@core-audit-owners` | security and compliance reviewers |

## Acquisition Strategy Ownership

Use this section when scorecards, resolver output, or
`capability_white_space_report_v1.json` show `blocked_construct_not_observed`,
`blocked_acquisition_required`, `blocked_construct_validity_below_floor`,
`blocked_sample_size_below_floor`, `blocked_freshness`,
`blocked_rights_boundary`, or `blocked_authority_boundary`.

1. Open the primary capability index, not a copied status string:

   ```bash
   uv run python tools/quality/validation/production_quality_evidence_inventory.py \
     --capability-index "$CAPABILITY_INDEX_DUCKDB" \
     --output _build/.tmp/production-quality/capability-white-space-triage.json
   ```

2. For each failure node, identify the grouped row by construct, domain,
   authority posture, and producer owner. If any grouping is missing, treat the
   report as invalid and route to `@runtime-owners`.
3. Confirm every `acquisition_strategy_ref` resolves to an owned strategy with
   owner team, legal counsel owner when government/official/administrative data
   is involved, estimated cost, estimated time, prerequisites, resulting
   authority envelope, contact path, TTL, review cadence, and escalation owner.
4. Add a new strategy only by updating the capability-index producer or its
   governed fixture source. Do not paste strategy notes into an incident ticket
   as if they were runtime authority.
5. Review active acquisition and proxy strategies at their `review_cadence`.
   When `ttl` expires without evidence, escalate to the strategy
   `escalation_owner` and keep closeout blocked or demoted according to the
   failure node authority posture.
6. Sunset a strategy only after one of these closure events is recorded in the
   capability index: acquired producer-backed capability supersedes the gap,
   legal counsel rejects the acquisition path, construct validity review fails,
   or the policy claim is explicitly scoped out. The sunset note must preserve
   the previous strategy id, owner, reason, and replacement or out-of-scope
   authority policy.

For `credit_program_enrollment`, the expected active strategies are
`acquire_from_nbu_registry`, `derive_proxy_from_tax_relief_records`, and
`simulation_only_dynamic_treatment`. The simulation route is advisory/modeling
support only and must remain blocked for production claim evidence unless a
producer-backed observed or validated equivalent is emitted under a new
authority envelope.

## Closeout Record

Every incident note must include:

- UTC detection, mitigation, rerun, and restoration timestamps;
- run id, job id, tenant, cell, execution profile, and bundle path;
- scorecard, case, assurance-case, public-export, and dashboard refs;
- every missing or failed Policy Design Case record family;
- first missing producer, owner, and next diagnostic command;
- whether evidence was runtime-emitted, runtime-derived, test-observed,
  projection-only, static inventory, manual assertion, or out-of-scope by typed
  authority policy;
- rerun commands and output paths;
- explicit residual limitations if the run remains blocked, demoted,
  quarantined, or outside public/production scope.

Accepted phase or wave closeout notes should be promoted to
`docs/archive/reports/YYYY-MM-DD-policy-design-case-<wave-or-phase>-closeout.md`
with optional sibling `.json` when structured evidence exists. `_build/.tmp/`
or `_build/policy-design-case/` output may support the note, but it is not the
durable operator memory by itself.

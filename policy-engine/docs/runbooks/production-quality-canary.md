# Production Quality Canary Runbook

Related reference: [Production canary matrix](../reference/runtime/production-canary-matrix.md),
[Runtime quality scorecard](../reference/runtime/quality-scorecard.md),
[Production quality approval](../reference/runtime/production-quality-approval.md),
[Deterministic replay](../reference/runtime/deterministic-replay.md), and
[Production resilience matrix](../reference/runtime/production-resilience-matrix.md).
Related triage: [Production quality triage](production-quality-triage.md).

Owner: `@platform-owners` with `@runtime-owners`, `@scientist-owners`,
`@foundry-owners`, `@fabric-owners`, and security/compliance reviewers.
Last tested: 2026-05-13 against Phase 6.2 docs-gate probes.
Evidence path: `.polisyos/canary_evidence/`, `.polisyos/provider_quality/`,
`_build/.tmp/production-quality/`, and CAS refs named in the scorecard.
Rollback path: stop promotion, keep the evidence bundle immutable, and return
traffic/config to the last approved runtime candidate.

Use this runbook when a production-quality gate needs deterministic evidence,
live-provider evidence, scenario-matrix evidence, approval review, override
review, or reissue/withdrawal review.

## Safety Boundary

- Run commands from the product root: `policy-engine/`.
- Do not paste live API keys into commands, docs, tickets, or evidence bundles.
- Live-provider lanes require an operator-approved environment where
  `POLISYOS_LLM_GATEWAY_API_KEY` is already present.
- Public exports must not include hidden benchmark answers, sentinel strings,
  raw prompts, private reviewer notes, raw sensitive records, bearer tokens, or
  query-string secrets.
- Treat the evidence bundle as immutable once it is attached to an approval
  packet. New evidence gets a new bundle or a new sidecar ref.

## Locate The Evidence

| Operator question | Primary location | Backup location |
| --- | --- | --- |
| Where is the bundle? | The runner prints `Evidence bundle: <path>` | `canary_matrix_run.json` at `summary.bundle_paths` or `lanes[].bundle_path` |
| Where is the scorecard? | `<bundle>/quality_evidence/quality_scorecard.json` | `bundle.json` fields `quality_scorecard_ref` and `quality_evidence_bundle_path` |
| Where is the failure envelope? | `<bundle>/failure.json` when a bundle exists | Matrix `summary.failure_envelope`, lane `failure_envelope`, or job `failure_envelope` |
| Where is the approval packet? | `<bundle>/production_approval_packet.json` after runtime approval | Runtime progress `approval_packet_ref` or scorecard `evidence_refs.approval_packet_ref` |
| Where are assurance reports? | `<bundle>/quality_evidence/*.json` | Scorecard `evidence_refs` and `bundle.json.files.quality_evidence` |
| What is the next action? | `blocking_quality_failures[].next_action` | `quality_gates[].next_action`, failure `next_action`, or resilience `operator_findings[]` |

## List Declared Matrix Lanes

```bash
uv run python tools/ops_runners/runtime/canary_matrix.py \
  --list \
  --json-output _build/.tmp/production-quality/canary_matrix.json
```

Expected output starts with:

```text
Canary matrix: 128 lanes, 8 ready, 64 quarantined, 40 deferred, 16 skipped, 1 CI-safe
profile-dev__provider-live_gonka_proxy__data-canonical_production__scenario-adversarial__ui-api_only [quarantined]
...
profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only [ready ci]
```

Interpretation:

- `ready ci` is safe for ordinary deterministic CI.
- `ready` is executable locally but not necessarily selected by the CI-safe
  subset.
- `quarantined` requires explicit live-provider approval and credentials.
- `deferred` and `skipped` are declared gaps, not missing rows.

## Run The Deterministic Canary Subset

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --deterministic \
  --output-root .polisyos/canary_evidence/deterministic \
  --run-root .polisyos/canary_matrix_runs/deterministic \
  --json-output _build/.tmp/production-quality/canary_matrix_run.json \
  --timeout-s 1200
```

Expected success output:

```text
Canary matrix run: 1 selected, 1 executed, 1 passed, 0 failed, 0 blocked, 0 skipped
profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only [passed] bundle=.polisyos/canary_evidence/... scorecard=pass
```

Expected failure output:

```text
Canary matrix run: 1 selected, 1 executed, 0 passed, 1 failed, 0 blocked, 0 skipped
profile-dev__provider-simulated__data-fixture__scenario-public_golden__ui-api_only [failed] bundle=<path-or-none> scorecard=<status>
```

If the command exits `2`, open
`_build/.tmp/production-quality/canary_matrix_run.json` and inspect
`summary.failure_envelope` first. If a lane produced a bundle, inspect that
bundle before rerunning.

## Run One Simulated Lane Directly

Use this when you need a fresh bundle without the matrix wrapper:

```bash
uv run python -m tools.ops_runners.runtime.local_production_canary \
  --mode simulated \
  --execution-profile dev \
  --canary-kind dev \
  --quality-scenarios-file tools/ops_runners/runtime/golden_quality_scenarios.json \
  --quality-scenario ukraine_msme_wartime_credit_support \
  --output-root .polisyos/canary_evidence/manual-dev \
  --run-root .polisyos/local_production_canary/manual-dev \
  --timeout-s 900
```

Expected output includes:

```text
Evidence bundle: .polisyos/canary_evidence/manual-dev/<timestamp>_<job_id>
```

Open the scorecard:

```bash
uv run python - "$BUNDLE" <<'PY'
import json
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
scorecard = json.loads((bundle / "quality_evidence" / "quality_scorecard.json").read_text())
print("execution_status=", scorecard.get("execution_status"))
print("quality_status=", scorecard.get("quality_status"))
print("approval_state=", scorecard.get("approval_state"))
print("blocking_failures=", len(scorecard.get("blocking_quality_failures") or []))
for failure in scorecard.get("blocking_quality_failures") or []:
    print(f"- {failure.get('code')}: {failure.get('layer')} {failure.get('phase')} -> {failure.get('next_action')}")
PY
```

Expected clean output has `execution_status= completed`,
`quality_status= pass`, `approval_state= approval_ready`, and
`blocking_failures= 0`.

## Run A Scenario Matrix Lane

Run a single stable lane id when you need profile-specific evidence:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --lane-id profile-production__provider-simulated__data-fixture__scenario-public_golden__ui-api_only \
  --output-root .polisyos/canary_evidence/production-simulated \
  --run-root .polisyos/canary_matrix_runs/production-simulated \
  --json-output _build/.tmp/production-quality/production_simulated_lane.json \
  --timeout-s 1200
```

Expected output:

```text
Canary matrix run: 1 selected, 1 executed, 1 passed, 0 failed, 0 blocked, 0 skipped
profile-production__provider-simulated__data-fixture__scenario-public_golden__ui-api_only [passed] bundle=<bundle> scorecard=pass
```

For scenario-wide deterministic selection:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --scenario public_golden \
  --json-output _build/.tmp/production-quality/public_golden_matrix_run.json
```

Scenario mode selects CI-safe deterministic lanes unless
`--allow-live-provider` is also supplied.

## Run A Live-Provider Canary

First confirm the operator-approved environment is present without printing the
secret:

```bash
test -n "${POLISYOS_LLM_GATEWAY_API_KEY:-}" && echo "live provider credential present"
```

Expected output:

```text
live provider credential present
```

Then run the lane with explicit approval:

```bash
uv run python tools/ops_runners/runtime/run_canary_matrix.py \
  --lane-id profile-production__provider-live_gonka_proxy__data-fixture__scenario-public_golden__ui-api_only \
  --allow-live-provider \
  --output-root .polisyos/canary_evidence/live-provider \
  --run-root .polisyos/canary_matrix_runs/live-provider \
  --json-output _build/.tmp/production-quality/live_provider_lane.json \
  --timeout-s 1800
```

If `--allow-live-provider` or the credential is absent, the runner must block
instead of trying the provider:

```text
Canary matrix run: 1 selected, 0 executed, 0 passed, 0 failed, 1 blocked, 0 skipped
profile-production__provider-live_gonka_proxy__data-fixture__scenario-public_golden__ui-api_only [blocked] bundle=none scorecard=not_run
```

Open `lanes[0].failure_envelope.missing` in the JSON to confirm whether the
blocker was the flag, the environment, or both.

## Run Replay On A Bundle

```bash
uv run python -m tools.ops_runners.runtime.replay_canary_bundle \
  --bundle "$BUNDLE" \
  --cas-root .polisyos/canary_replay_cas \
  --json-output "$BUNDLE/replay.json"
```

Expected output:

```text
Replay manifest: <cas-ref>
Drift explanation: <cas-ref>
Production readiness: pass
```

Exit code `2` means the drift explanation has
`production_readiness: fail`. Open `$BUNDLE/replay.json` and then the linked
`drift_explanation_ref`; accepted drift must name a typed source such as
`code`, `data`, `provider`, `model`, `prompt`, `cas`, or `dependency`.

## Run Resilience Evidence

```bash
uv run python tools/quality/testing/runtime_resilience_matrix.py \
  --deterministic \
  --list \
  --json-output _build/.tmp/production-quality/resilience_matrix.json
```

Expected output starts with:

```text
Runtime resilience matrix: 8 scenarios, 4 performance warnings, 2 operational failures, 1 quality failures, 1 quarantined
load_overload [performance_warning]: control_plane control.job_heartbeat 1450.0ms/1000.0ms
```

Performance warnings can still require approval override for serious profiles.
Operational failures fail closed. Quality failures route back to the scorecard
and assurance report that is incomplete or weak.

## Build Provider Drift Evidence

After one or more bundles exist:

```bash
uv run python -m tools.ops_runners.runtime.provider_quality_ledger \
  --input-root .polisyos/canary_evidence \
  --output .polisyos/provider_quality/provider_model_quality_ledger.json \
  --default-production-model simulated:policyos-sim-v1:fixture-fp:policy_drafting
```

Expected success: exit code `0` and a JSON file containing
`schema_version: policyos.provider_model_quality_ledger.v1` plus
`provider_model_quality_ledger_ref`.

If the command reports no observations, run or attach a canary bundle that
contains `provider_model_quality_observations.json` or LLM variant evidence.

## Approval Review

Use the runtime API when the run and persisted scorecard are available:

```bash
cat > _build/.tmp/production-quality/approval-request.json <<'JSON'
{
  "quality_scorecard_ref": "artifact-ref-from-scorecard"
}
JSON

curl -sS -X POST "$RUNTIME_URL/api/v1/runs/$RUN_ID/production-approval" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data @_build/.tmp/production-quality/approval-request.json
```

Expected response shape:

```json
{
  "run_id": "...",
  "decision": "approved",
  "approval_packet_ref": {"artifact_id": "..."},
  "evidence_bundle_packet_path": ".polisyos/canary_evidence/.../production_approval_packet.json"
}
```

If the response decision is `blocked`, inspect
`packet.eligibility.reasons`, `packet.evidence_refs`, and the scorecard
`blocking_quality_failures`.

For a local dry-run against a bundle:

```bash
uv run python - "$BUNDLE" <<'PY'
import json
import sys
from pathlib import Path
from polisyos.runtime.quality.approval import build_production_approval_packet

bundle = Path(sys.argv[1])
scorecard = json.loads((bundle / "quality_evidence" / "quality_scorecard.json").read_text())
packet = build_production_approval_packet(scorecard=scorecard).model_dump(mode="json", exclude_none=True)
out = bundle / "production_approval_packet.review.json"
out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
print("approval_decision=", packet["decision"])
print("approval_reasons=", packet["eligibility"].get("reasons", []))
print("approval_packet=", out)
PY
```

The dry-run file is review evidence only; it is not a CAS-persisted approval
packet.

## Override Review

Only use overrides for exceptional approval of a non-eligible scorecard. The
request must include reviewer attribution, reason, exact scope, expiry, and
evidence refs:

```json
{
  "quality_scorecard_ref": "artifact-ref-from-scorecard",
  "override": {
    "reviewer_identity": "review-board-member",
    "reason": "Bounded performance warning accepted for this canary window.",
    "scope": "run:${RUN_ID}",
    "expires_at": "2026-05-20T00:00:00Z",
    "evidence_refs": ["resilience_report_ref-or-ticket-ref"]
  }
}
```

Expected accepted decision:

```text
decision=approved_with_override
```

Expected blocked reasons include:

- `override_reviewer_attribution_missing`
- `override_packet_incomplete`
- `override_expired`
- `override_scope_mismatch`
- `override_rationale_weak`

An override never mutates the original scorecard. It creates a separate packet
with an override trail.

## Reissue Flow

Use reissue when drift, source withdrawal, stale data, model/provider drift, or
policy-context change requires a replacement run:

```bash
curl -sS -X POST "$RUNTIME_URL/api/v1/control/runs/$RUN_ID/reissue" \
  -H "Authorization: Bearer $TOKEN"
```

Expected response shape:

```json
{
  "action": "reissue",
  "status": "accepted",
  "reissue_plan_ref": {"artifact_id": "..."},
  "reissued_run_id": "...",
  "message": "Reissue for run ... accepted as ... and queued for durable execution."
}
```

Record the original scorecard, original approval packet, reissue plan ref, and
new run id together. The original decision remains part of the audit trail.

## Withdrawal Flow

Withdrawal is not a retry and is not deletion. It is an explicit continuous
governance action for a public decision artifact.

Before marking a decision withdrawn, collect:

- original decision packet ref;
- incident or monitor event refs;
- human-review ref when the withdrawal came from review;
- audit event ref;
- actor id and reason.

The persisted sidecar kind is `scientist.withdrawal_record`. It must contain
`actor_id`, `reason`, `audit_event_ref`, and either `monitor_event_refs` or
`human_review_ref`. Public exports may expose the withdrawal status and action
posture, but not private reviewer notes, hidden benchmark refs, or internal
monitor identifiers.

## Close The Canary Review

Before promotion, make sure all of these are linked from the ticket or release
record:

- bundle path and `bundle.json`;
- scorecard path and `quality_scorecard_ref`;
- any failure envelope and the owning layer/phase;
- approval packet ref and decision;
- replay refs and drift decision;
- resilience matrix ref or attached report;
- provider drift ledger ref for live/default model evidence;
- next action for every blocking or warning gate.

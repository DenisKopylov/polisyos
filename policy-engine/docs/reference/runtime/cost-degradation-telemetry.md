# Cost And Degradation Telemetry

`cost_degradation_telemetry.json` is the W2.C local production-debug artifact
for Policy Design Case runs. It uses schema version
`policyos.runtime.policy_design_case.cost_degradation_telemetry.v1`.

The artifact records governed observations for provider calls, tokens, search,
compute, retry, wall-clock time, acquisition, and degradation states. Its
default posture is telemetry-first: warning and limitation rows are visible for
operators and scorecard readers, but they do not block closeout unless the row
cites an authority-level `authority_policy_ref`.

Every warning, limitation, or blocking row must carry an owner, TTL, next
action, evidence ref, and closeout effect. Cost rows are diagnostic-only and
cannot downgrade evidence quality.

Local canary bundles write the artifact under
`quality_evidence/cost_degradation_telemetry.json`; scorecards expose the
reader gate `policy_design_w2c_cost_degradation_telemetry`.

# Production Resilience Matrix

Phase 5.5/5.6 defines the `policyos.runtime_resilience_matrix.v1` payload
emitted by:

```bash
uv run python tools/quality/testing/runtime_resilience_matrix.py --deterministic --json-output _build/.tmp/production-quality/resilience_matrix.json
```

The JSON output is the authoritative local resilience report. It is deterministic
in CI, safe to diff, and carries `resilience_report_ref` so downstream approval
evidence can point at the exact matrix artifact.

## Scenario Coverage

| Scenario | Lane | Classification | Purpose |
| --- | --- | --- | --- |
| `load_overload` | deterministic local | `performance_warning` | Control heartbeat and job-detail behavior under overload. |
| `soak_incomplete_evidence` | deterministic local | `quality_failure` | Long-running pressure with missing required evidence. |
| `retry_storm` | deterministic local | `operational_failure` | Provider retry storm and preflight budget exhaustion. |
| `provider_brownout_live` | live provider manual | `quarantined` by default | Live-provider brownout lane, never CI-safe without an explicit flag. |
| `cas_pressure` | deterministic local | `performance_warning` | CAS put/get contention and round-trip pressure. |
| `queue_saturation` | deterministic local | `operational_failure` | Lease and heartbeat saturation in the control queue. |
| `run_index_pressure` | deterministic local | `performance_warning` | Run-index refresh/list plus timeline and lineage build pressure. |
| `dashboard_degraded_rendering` | deterministic local | `performance_warning` | First meaningful dashboard route render degradation. |

Live-provider brownout remains quarantined unless the operator passes
`--include-live-provider-brownout`. The flag only marks the lane manual-ready;
it does not make the lane CI-safe.

## Runtime-Owned Lane Evidence

Every scenario carries a `readiness_lane` projection and a
`runtime_owned_evidence` artifact descriptor. The descriptor is emitted as
`runtime.resilience_lane_evidence` under
`quality_evidence/resilience_lanes/<scenario>.json`, includes the required,
observed, and missing evidence list for the lane, and records a runtime
diagnostic event with `producer=runtime.resilience_matrix`.

The Phase 5.5 readiness lanes are:

- `load`
- `soak`
- `retry_storm`
- `provider_brownout`
- `cas_pressure`
- `queue_saturation`
- `dashboard_degradation`

`run_index_pressure` is also retained as a deterministic runtime hot-path lane.

## Lane Diagnostic SLO Evidence

Each readiness lane includes `diagnostic_slo_evidence` with schema
`policyos.runtime.lane_diagnostic_slos.v1`. The per-lane SLO metrics cover:

- `trace_continuity`
- `event_loss`
- `payload_mismatch`
- `latency`
- `retry_amplification`
- `stale_evidence`
- `operator_root_cause_fields`

The root-cause metric carries owner, phase, cause, missing input, downstream
impact, refs, and next command fields so operators can move from a resilience
finding to the owning runtime artifact without relying on a static report alone.

## SLO Budgets

| Phase | Layer | Budget |
| --- | --- | --- |
| `control.job_lease` | `control_plane` | 250ms |
| `control.job_heartbeat` | `control_plane` | 1000ms |
| `fabric.materialization` | `fabric` | 120000ms |
| `cas.put` | `artifact_store` | 250ms |
| `cas.get` | `artifact_store` | 200ms |
| `runtime.run_index_refresh` | `runtime_api` | 500ms |
| `runtime.run_index_list` | `runtime_api` | 100ms |
| `runtime.timeline_build` | `runtime_api` | 500ms |
| `runtime.lineage_build` | `runtime_api` | 750ms |
| `provider.preflight` | `provider_gateway` | 10000ms |
| `evidence.bundle_assembly` | `canary_evidence` | 5000ms |
| `api.job_detail` | `runtime_api` | 250ms |
| `dashboard.first_meaningful_route_render` | `dashboard` | 3000ms |

Every budget row includes a layer, phase, observed value, budget, status, and
operator next action. Dashboard approval surfaces render those bottlenecks
separately from operational failures and quality gates.

## Failure Semantics

`performance_warning` means the run completed and quality evidence can still be
complete, but production approval requires operator review or override for
serious profiles.

`operational_failure` means the runtime layer could not satisfy a resilience
contract, such as queue lease/heartbeat or provider preflight. These fail closed
and are not quality failures.

`quality_failure` means required evidence is incomplete or weak. Under load,
missing evidence such as `quality_evidence/policy_grounding_matrix.json` blocks
approval instead of silently passing.

`quarantined` means the lane is declared but intentionally excluded from
deterministic CI. Operators must opt in explicitly and attach the resulting
provider evidence before using it for approval.

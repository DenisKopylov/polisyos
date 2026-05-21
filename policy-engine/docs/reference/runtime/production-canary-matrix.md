# Production Canary Matrix

The Phase 0.4 baseline defines the `policyos.canary_matrix.v1` payload emitted by:

```bash
uv run python tools/ops_runners/runtime/canary_matrix.py --list --json-output _build/.tmp/production-quality/canary_matrix.json
```

The JSON output is the authoritative lane inventory. It is deterministic and
safe to diff in CI.

## Dimensions

| Dimension | Values |
| --- | --- |
| `profile` | `dev`, `research`, `governed`, `production` |
| `provider` | `simulated`, `live_gonka_proxy` |
| `data` | `fixture`, `canonical_production` |
| `scenario` | `public_golden`, `negative`, `adversarial`, `hidden_quarantined` |
| `ui` | `api_only`, `dashboard_smoke` |

The full cartesian product contains 128 lanes. Lane ids are stable strings with
the form:

```text
profile-{profile}__provider-{provider}__data-{data}__scenario-{scenario}__ui-{ui}
```

## Coverage States

| Status | Meaning |
| --- | --- |
| `ready` | The lane has a current runner contract. The dev fixture/simulated public-golden API lane is CI-safe. |
| `quarantined` | The lane requires live Gonka-compatible LLM proxy access and must not run in ordinary CI. |
| `deferred` | The dimension is declared but the scenario or dashboard harness is not implemented yet. |
| `skipped` | The hidden/quarantined scenario suite is intentionally absent from the public repo. |

Missing lanes are represented as `deferred` or `skipped`, never omitted from the
matrix. Live-provider lanes are represented as `quarantined` with an exit
criterion rather than mixed into CI-safe coverage.

Governed and production lanes that require PostgreSQL-backed control-plane
state carry a typed `setup_error` instead of being declared ready on local
SQLite or unset backing services. The setup error uses
`type=local_backing_service_unavailable`,
`code=canary_postgresql_state_store_unavailable`, and
`readiness_state=not_ready`; the matrix runner blocks these lanes before
execution and emits the setup error in the lane failure envelope.

Every lane also carries `coverage.missing_or_deferred_gaps`. This list preserves
dimension-specific gaps even when the lane-level status is dominated by live
provider quarantine. For example, a live-provider negative lane remains
`quarantined`, but its coverage gaps still include the deferred `negative`
scenario contract.

Runner contracts pass the profile dimension through both
`--execution-profile=<profile>` and `--canary-kind=<profile>`. Production,
governed, and research lanes therefore exercise serious-profile scorecard
semantics even when the provider is simulated.

For operator-approved one-lane cloud debugging, the matrix runner accepts
`--deterministic --only-lane <lane-id>`. This selects the exact stable lane id
even when the inventory marks it `quarantined`; live-provider lanes still
require `POLISYOS_LLM_GATEWAY_API_KEY` before execution. Without credentials,
the runner emits a typed `live_provider_not_enabled` failure envelope instead
of running or reporting unknown provenance.

## Evidence Bundle Files

Every lane declares required evidence bundle files. The common target evidence is:

- `bundle.json`
- `request.sanitized.json`
- `env.sanitized.json`
- `artifacts.json`
- `job.json`
- `run.json`
- `agents.json`
- `timeline.json`
- `lineage.json`
- `quality_evidence/quality_scorecard.json`
- `quality_evidence/golden_scenario_contract.json`
- `quality_evidence/normative_evidence.json`
- `quality_evidence/fabric_retrieval_trace.json`
- `quality_evidence/foundry_method_report.json`
- `quality_evidence/policy_grounding_matrix.json`
- `quality_evidence/conflict_check.json`

Additional files are required by lane dimension:

| Dimension value | Additional evidence |
| --- | --- |
| `provider=live_gonka_proxy` | `provider_preflight.json` |
| `data=canonical_production` | `production_data_evidence.json` |
| `ui=dashboard_smoke` | `dashboard.json` |
| `profile=research`, `governed`, `production` | `performance.json` |

## Current Baseline

The current baseline records:

- API-only, simulated, public-golden lanes as implemented through
  `tools.ops_runners.runtime.local_production_canary`.
- The dev fixture (`tests/_data/data_forge/ukraine_shadow`), simulated,
  public-golden, API-only lane as CI-safe for local deterministic CI.
- Live Gonka-compatible provider lanes as quarantined because they require
  explicit proxy credentials and budget approval.
- Governed/production local PostgreSQL requirements as typed setup errors with
  non-ready readiness state.
- Negative and adversarial lanes as deferred until their quality regression
  scenario contracts exist.
- Hidden/quarantined lanes as skipped because the hidden suite is intentionally
  not checked into the public repository.
- Dashboard smoke lanes as deferred until Playwright/dashboard evidence is wired
  into the production canary runner.

# Runtime API Outage

Related how-to: [Deploy Runtime](../how-to/deploy-runtime.md),
[Use Control Plane](../how-to/use-control-plane.md),
[Debug Failed Run](../how-to/debug-failed-run.md).

> Use this runbook when the runtime HTTP surface is fully or partially unavailable:
> health, runs, artifacts, control-plane endpoints, or the operator
> dashboard has become unusable.

Owner: `@runtime-owners`
Historical validation receipt: `2026-04-17` — recorded against the runtime contract and observability evidence available then; this is not a fresh runtime check.
Evidence path: `docs/archive/reports/core-runtime-closeout.md`; `docs/archive/reports/platform-acceptance.md`; `tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
Rollback path: restore the last known-good deployment, preserve read-only access when possible, and block new risky changes until the service is stable.

## Operational Metadata

| Field              | Value                                                                                                                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary owner      | `@runtime-owners`                                                                                                                                                                        |
| Coordination owner | `@platform-owners`                                                                                                                                                                       |
| Historical receipt | 2026-04-17, D1-L1 documentation validation pass; historical record only, with no current runtime verdict                                                                                 |
| Evidence anchors   | `tests/unit/runtime/http/test_runtime_api_contract_hardening.py`, `tests/unit/runtime/http/test_runtime_api_observability.py`, `tools/ops_runners/runtime/check_runtime_api_contract.py` |
| Rollback posture   | restore last known-good deployment, preserve read-only surface when write path is the failing branch                                                                                     |

## Symptom

- `/health` or `/ready` does not respond or returns `degraded` or `5xx`;
- `GET /api/v1/runs`, `GET /api/v1/runs/{run_id}`, or
  `POST /api/v1/control/runs` fail at scale;

- The dashboard shows `Health: unavailable`, and `/platform` or `/runs`
  cannot load data;

- An alert family for DAG success rate, runtime latency, agent error spikes, or
  connector errors enters `warning` or `critical`.

## Likely Causes

- Runtime boot failure in `create_runtime_api_app(...)`;
- A bad deployment or configuration drift in authz, OIDC, OPA, or state-store variables;
- Degradation of the Postgres/SQLite state store, worker backend, or outbox consumer;
- upstream dependency outage: Keycloak, OPA, LLM gateway, external connectors;
- Resource exhaustion, saturation, or deadlock among control-plane workers.

## Timeline Capture Expectations

Start a single incident timeline immediately:

- The UTC timestamp when symptoms began and who noticed them first;
- environment, deployment SHA, execution profile;
- failing URL, HTTP method, status code, request ID, trace ID;
- affected routes: `health`, `runs`, `artifacts`, `control`;
- Active alerts and dashboard snapshots;
- Configuration or deployment changes in the 60 minutes before the incident;

## First Triage Steps

1. Confirm the blast radius:

   ```bash
   curl -i http://localhost:8000/health
   curl -i http://localhost:8000/ready
   curl -i http://localhost:8000/api/v1/health
   ```

2. Check the read and control surfaces separately:

   ```bash
   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/runs

   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/workers

   curl -i -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/outbox
   ```

3. If a known `job_id` or `run_id` is available, inspect durable state:

   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/control/jobs/$JOB_ID

   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/runs/$RUN_ID/timeline
   ```

4. Switch to the trusted dashboards:
   `slo-overview`, `executive-overview`, `scientist-agents`,
   `security-phase4`.

5. If the outage looks like configuration drift, compare the runtime environment with the last
   known-good deployment instead of editing environment variables at random.

## Rollback / Mitigation

- Restore the last known-good deployment or release candidate;
- If only the write path is affected, temporarily limit the `POST` workload and
  preserve the operators’ read-only surface;

- If an optional security or dependency sidecar is involved, a temporary bypass
  requires an explicit incident-commander decision and a timeline entry;

- Reduce ingress load or concurrency if saturation, rather than a logic fault,
  is the cause;

- Do not start migrations, contract refreshes, or dependency bumps until
  the service is stable.

## Escalation Owner

- primary: `@runtime-owners`;
- incident coordination: `@platform-owners`;
- Supporting owners: `@frontend-owners` for operator UX and affected subsystem
  owners for downstream remediation.

## Follow-up Checklist

- Request IDs, trace IDs, and related logs were preserved;
- Dashboard panels actually used during triage were attached;
- The rollback or mitigation point and its effect were recorded;
- Alert routing was updated if the signal reached the wrong owner;
- If the outage was silent for dashboard users, a synthetic check or
  frontend UX signal was added.

## Blameless Postmortem

### What Went Well

- Which signal provided the fastest accurate detection;
- Where correlation across `alert -> dashboard -> trace/log -> runbook` worked quickly;
- What reduced MTTR.

### What Went Poorly

- Where correlation IDs were missing;
- Which alerts were too late or noisy;
- What had to be recovered from chat instead of system artifacts.

### Action Items

| Action item                                                         | Owner              | Due date   | Status |
| ------------------------------------------------------------------- | ------------------ | ---------- | ------ |
| Add or improve detection for the specific failing route/dependency  | `@runtime-owners`  | YYYY-MM-DD | open   |
| Close the config, scaling, or dependency gap that caused the outage | affected owner     | YYYY-MM-DD | open   |
| Update dashboard, alert, or runbook routing if triage was slow      | `@platform-owners` | YYYY-MM-DD | open   |

# End-to-end runtime data flow

> A code-inspected trace of one run-bound predictive diagnostic, from run-rooted
> inputs to a verified API read.

**Owner:** the Runtime HTTP run route and predictive-calibration service own
this integration; the Scientist `ForecastOwner` and calibration bridge own the
forecast and empirical-evidence production contracts.

**Source of truth:** the [run routes](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/routes/runs.py#L3960),
[predictive-calibration service](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L236),
[ForecastOwner](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py#L596),
and [empirical calibration producer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/calibration/forecast_bridge.py#L399).

**Snapshot and evidence level:** inspected at commit
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on branch
`codex/docs-refresh-e02-20261014`. The implementation and linked semantic-test
source were read; this documentation task did not execute those tests or inspect
a deployed service, database, or production CAS.

---

## Scope

This trace starts with a completed `natural_language_run` control job and its
Core run manifest. An authorized run reviewer submits run-rooted candidate and
observation references to calculate empirical predictive coverage for one
already-produced candidate simulation. It does not trace every upstream route
that created the run, and it is not a causal-effect estimate, policy ranking,
publication decision, or universal PolicyOS workflow.

The API surface is `POST` and `GET /api/v1/runs/{run_id}/predictive-calibration`
([Runs API reference](../reference/api/runs.md)). The route resolves the run,
checks tenant and cell ownership, and reconstructs the candidate projection
before calling the service.

## Flow

```mermaid
sequenceDiagram
    actor Caller
    participant API as Runtime runs route
    participant Service as Predictive-calibration service
    participant Run as Run index + completed control job
    participant CAS as Core / IR CAS
    participant Forecast as Scientist ForecastOwner
    participant Evidence as Empirical calibration bridge
    participant S10 as S10 forecast consumer
    participant SQL as Control store + diagnostic event log

    Caller->>API: POST run ID + exact selected refs, split, method, rule, times, intent
    API->>Run: Resolve owned run
    API->>Service: Candidate projection + typed request
    Service->>CAS: Check full profiles and exact run-root membership
    Service->>SQL: Read completed job; verify Core run/manifest binding
    Service->>Forecast: Observed snapshot ref + explicit forecasting inputs
    Forecast->>CAS: Resolve DataSnapshot, then its data_ref
    Forecast->>CAS: Persist training slice, method, uncertainty, diagnostics, report
    Service->>Evidence: Reopen report and produce empirical evidence
    Evidence->>CAS: Persist typed empirical evidence
    Service->>S10: Apply reopened evidence to candidate and world context
    S10-->>Service: Bounded forecast projection
    Service->>CAS: Persist run-bound association v2
    Service->>SQL: Append association-ref event + complete same-intent owner row
    Caller->>API: GET run ID
    API->>Service: Resolve current diagnostic
    Service->>SQL: Read latest association event and verify payload hash/scope
    Service->>CAS: Reopen association, report, evidence, and exact selected profiles
    Service->>S10: Recompute from reopened inputs
    Service-->>API: Typed limited association and CAS ref
    API-->>Caller: Predictive-only response
```

## What moves across the boundary

The strict request carries an `intent_id`, candidate source, observed `DataSnapshotRef`,
model and policy specs, calibration-rule artifact, threshold, train/holdout split,
target metric, method parameters, temporal roles, and seed. The candidate source
must resolve to the run's N4 candidate scenario source; the observed snapshot,
model spec, policy spec, and rule must be exact run-root views. The service checks
both run membership and each selected CAS profile, including its manifest-profile
digest and artifact kind. A profileless reference or a sibling profile with the
same artifact ID does not satisfy the run-root check.

[`DataSnapshotRef`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/core/contracts/fabric.py#L56)
and [`DataSnapshot`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/core/contracts/fabric.py#L161)
make the snapshot-to-data reference explicit. `ForecastOwner` resolves both
artifacts, validates the snapshot, extracts the requested series, and applies the
explicit split. It
persists a training slice, method artifact, uncertainty bundle, calibration
diagnostics, and backtest report. The report carries role-labelled `InputRef`
edges with the selected manifest-profile digests, including the run manifest,
candidate, observation, model, policy, and rule views.

The empirical bridge reads the persisted report, reconciles its observed interval
counts, checks the report context and lineage, and persists typed empirical
calibration evidence. The runtime then passes that evidence reference through
[`RealValueOwnerGateway.produce_forecast_inputs`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5213)
to the existing S10 consumer using the candidate and its world-model context. The
association stores the exact input refs, report/evidence/uncertainty refs,
recomputed counts and rate, S10 summary, request digest, and run, job, tenant, and
cell bindings. Its CAS manifest repeats the exact-profile edges.

The persisted association is `runtime.predictive_calibration_association`, schema
`polisyos.runtime.predictive_calibration_association.v2`. Its publication event is
`polisyos.runtime.diagnostic.ref_publication.v1`, schema version `1.0`; the
forecast method is `forecasting.univariate.exponential_smoothing@1.0.0`, and the
calibration-rule artifact is checked against rule ID
`rolling-origin-residual-conformal.v1` and rule version `1.0`. Empirical
evidence is persisted as schema `1.2`. These identities are code contracts for
this path, not claims that all PolicyOS producers use one artifact format.

## Provenance, time, and authority

The run, control job, and Core attempt have distinct identifiers. The binding
reader requires the control row to be completed and of kind `natural_language_run`,
then joins its persisted progress pointer to the selected Core run ID and exact
manifest profile. It does not infer that the control job ID, control `run_id`, and
Core `run_id` are interchangeable.

The six caller-declared times are `data_valid_time`, calibration-window start and
end, `policy_effective_time`, `prediction_time`, and `observation_time`.
[`ForecastTemporalRoles`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py#L120)
requires timezone-aware, distinct values and the order
`data_valid_time < calibration_window_start < calibration_window_end <= prediction_time < observation_time`,
with `policy_effective_time <= prediction_time`. The
association still records `source_time_status: not_established`,
`issuer_status: not_established`, `population_scope_status: not_established`, and
`counterfactual_credibility_status: not_established`; syntactic ordering does not
prove that those times or scopes describe the source institutionally.

The output is fixed to `assessment: limited` and `authority_scope: predictive_only`.
It explicitly forbids use for promotion, publication, policy selection, or a causal
effect claim. The S10 projection also fixes counterfactual credibility to
`not_established`. A successful empirical grade is therefore a bounded diagnostic,
not authority to choose or publish a policy.

## Readback and failure behavior

The GET reader inspects at most 1,000 diagnostic events for the run/job and
refuses with `predictive_calibration_event_history_bounded` when that bound is
reached. Within the admitted history, it selects the latest association-publication event,
checks event scope and payload SHA-256, reopens the exact association profile,
checks manifest schema and input edges, binds the association back to the current
run and completed job, reopens empirical evidence, compares the stored summary
with recomputed evidence, and recomputes S10. Refusal paths return a typed conflict
or not-found response rather than trusting a copied response projection.

The POST operation key is scoped by purpose, tenant, cell, authenticated-principal
digest, run, and intent; its body digest binds the request and exact run-manifest
profile. Identical completed retries reopen the same association, changed bodies
under the same intent conflict, and a concurrent owner receives an in-progress
conflict. The association bytes are written to CAS before the SQL completion
transaction. [`ControlPlaneStore.complete_runtime_operation_intent`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/services/control_plane_store.py#L5266)
couples diagnostic-event append with completion of the owner row; this is not one
transaction spanning CAS and SQL. A pending or
ambiguous owner is fail-closed and requires recovery rather than automatic takeover.

The composed semantic test
[`test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/http/test_control_service_di.py#L4178)
checks actual `ForecastOwner` execution, CAS persistence, event publication,
fresh-app GET reopening, exact retries, changed-body conflict, event-payload
tamper refusal, and two run-rooted observation sets that produce different
empirical grades while holding the forecast inputs fixed. The
[profile-boundary test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/http/test_predictive_calibration_profile_boundary.py#L1)
checks selected-profile tampering. These are inspected test sources, not fresh
execution receipts for this snapshot.

## Invalidation and learning boundary

A later request with a new intent appends a new association; GET chooses the latest
matching event. The previous association remains a historical artifact. This
diagnostic path does not revoke earlier records, reissue a policy claim, or update
decision validity when a source, rule, law, or world epoch changes. Rule replay
and decision-validity tracking are separate mechanisms in
[`rule_replay_engine.py`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/rule_replay_engine.py#L202)
and [`decision_validity.py`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/validation/decision_validity.py).
Claim lifecycle/current-head handling is separate in
[`lifecycle.py`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/evidence/claims/lifecycle.py).
The default Scientist workflow builder installs
[`UnappointedClaimLedgerOwner`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/evidence/claims/head_index.py#L2762),
so root issuance and current-head resolution remain `not_established` in that
composition. The predictive-calibration path hands off to none of these mechanisms.

The longitudinal [`CalibrationLedger`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/calibration_ledger.py#L525)
and [`MemoryInfluenceRecord`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/memory_influence.py#L95)
owners define future routing, review, and acquisition influence while forbidding
current-claim evidence use. The predictive-calibration association does not itself
call those owners or adapt its event into a ledger entry in this flow.

For the selected slice, the source contains the route, producer, typed CAS
association, event/SQL owner, GET reader, API response, and composed semantic-test
source. Test execution and deployment are not established here.

The two possible downstream handoffs remain scoped gaps. Each `bridge_missing`
label applies only if that consumer is required; it does not imply the run-bound
diagnostic chain is absent or override the association's authority denials.

- Association to claim or decision invalidation/reissue: the inspected producer
  does not call the claim lifecycle or decision-validity owner. State:
  `bridge_missing` if this consumer is required.
- Association to longitudinal calibration or memory influence: the inspected
  path has no adapter from the association to those owners' input records. State:
  `bridge_missing` if this consumer is required.

Pattern pass: P01/P02 have a source-backed producer-to-reader chain;
the linked semantic-test source is present but was not executed here. P03 has an
API surface in this slice, while broader audience projections are outside this
trace. P04 keeps the association `limited` and the S10 statuses finite. P05 is
explicit in the predictive-only contract. P07's selected rule
artifact is pinned, but rule-change replay is outside this path. P08 keeps distinct
time roles while source-time authority remains `not_established`. P10 has
content-level readback and negative checks in test source. P11's historical
learning owner remains separate. P14 evidence independence is not established by
this predictive diagnostic and is not claimed.

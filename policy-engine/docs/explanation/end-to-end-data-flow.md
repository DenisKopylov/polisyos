# End-to-end runtime data flow

Owner: Runtime HTTP runs route, predictive-calibration service, Scientist ForecastOwner and calibration bridge

Source of truth: `repo:policy-engine/src/polisyos/runtime/http/routes/runs.py` (route and permission
  bindings), `repo:policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py`,
  `repo:policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py`,
  `repo:policy-engine/src/polisyos/calibration/forecast_bridge.py`, and
  `repo:policy-engine/tests/unit/runtime/http/test_control_service_di.py`.

Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`

This is one source-inspected trace of a run-bound predictive diagnostic, from
selected run inputs through persisted evidence to a verified API read. The
source check compares only the declared files; the named semantic test below
was inspected, not executed for this documentation pass.

Pinned source references: [run route](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/routes/runs.py#L3960),
[route permission bindings](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/routes/runs.py#L194),
[predictive-calibration service](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/services/predictive_calibration.py#L236),
[ForecastOwner](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py#L596),
[empirical calibration producer](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/calibration/forecast_bridge.py#L399),
and [composed semantic test](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/tests/unit/runtime/http/test_control_service_di.py#L4178).

**Snapshot and evidence level:** inspected at commit
`bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on branch
`codex/docs-refresh-e02-20261014`. The implementation and linked semantic-test
source were read; this documentation task did not execute those tests or inspect
a deployed service, database, or production CAS.

---

## Scope

This trace starts with a completed `natural_language_run` control job and its
Core run manifest. An actor with `RUNS_FEEDBACK_EVALUATE` permission submits
run-rooted candidate and observation references to calculate empirical
coverage for a predictive diagnostic attached to the run's candidate context.
The ETS owner forecasts a holdout from the selected observed `DataSnapshot`
using the explicit split; it does not forecast the candidate intervention's
trajectory or estimate a causal effect. The POST route also requires
`allow_candidate_run_predictive_calibration_surface`. It compares the run's
tenant and cell with values from the authenticated `AccessScope`; tenant and
cell are not request-body fields. GET uses `RUNS_REVIEW` and the owned run path.
The service pins the method FQN to
`forecasting.univariate.exponential_smoothing@1.0.0`; the body supplies method
parameters, not a method selector. If the feature flag is off, either route
returns service unavailable. This is one bounded path, not every route that
creates a run, a causal-effect estimate, a policy ranking, a publication
decision, or a universal PolicyOS workflow.

The API surface is `POST` and `GET /api/v1/runs/{run_id}/predictive-calibration`
([Runs API reference](../reference/api/runs.md)). Both routes resolve the owned
run and reconstruct its candidate projection before calling the service. POST
checks the authenticated tenant and cell from `AccessScope` against the run;
GET's event and association checks bind the read back to that run scope.

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

    Caller->>API: POST selected refs, split, rule, times, intent
    API->>Run: Authorize; check tenant/cell; resolve owned run
    API->>Service: Candidate projection + typed request
    Service->>CAS: Check full profiles and exact run-root membership
    Service->>SQL: Read completed job; verify Core run/manifest binding
    Service->>Forecast: Observed snapshot ref + explicit forecasting inputs
    Forecast->>CAS: Resolve selected DataSnapshot, then its data_ref
    Forecast->>CAS: Persist training slice, method, uncertainty, diagnostics, report
    Service->>Evidence: Reopen report and produce empirical evidence
    Evidence->>CAS: Persist typed empirical evidence
    Service->>S10: Apply reopened evidence to candidate and world context
    S10-->>Service: Bounded forecast projection
    Service->>CAS: Persist run-bound association v2
    Note over CAS,SQL: CAS and SQL writes do not share one transaction
    Service->>SQL: Append event + complete owner row in one SQL transaction
    Caller->>API: GET run ID
    API->>Run: Resolve current run + candidate projection
    API->>Service: Load diagnostic
    Service->>SQL: Read bounded event history; verify latest association event
    Service->>CAS: Reopen association, report, evidence, and exact selected profiles
    Note over Service,CAS: GET reopens selected profiles; it does not fetch a new upstream snapshot
    Service->>S10: Recompute from reopened inputs
    Service-->>API: Typed limited association and CAS ref
    API-->>Caller: Predictive-only response
```

## Typed handoffs and artifact boundary

**Admission.** The strict `PredictiveCalibrationRequest` carries an `intent_id`,
candidate source, observed `DataSnapshotRef`, model and policy specs,
calibration-rule artifact, threshold, train/holdout split, target metric, method
parameters, temporal roles, and seed. The service requires the candidate source
to be the run's N4 candidate scenario source; the snapshot, specs, and rule must
be exact run-root views. It verifies each complete CAS reference, manifest
profile digest, and artifact kind. A profileless reference or a sibling profile
with the same artifact ID is refused. The original request is bound by
`request_sha256`; the association records that digest and its input refs rather
than copying the request body.

[`DataSnapshotRef`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/core/contracts/fabric.py#L56)
and [`DataSnapshot`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/core/contracts/fabric.py#L161)
make the snapshot-to-data reference explicit. `ForecastOwner` resolves the
snapshot and its `data_ref`, validates the snapshot, extracts the requested
series, and applies the explicit split. It persists a training slice, method
artifact, uncertainty bundle, calibration diagnostics, and backtest report in
CAS. The report's role-labelled `InputRef` edges retain the selected profile
digests for the run manifest, candidate, observation, model, policy, and rule.
The method FQN is fixed by the predictive-calibration service; the request
supplies only its `method_params`. This producer's result and report remain
`authority_scope: predictive_only` and
`bridge_status: bridge_pending`; the report must remain trust-ineligible. The
later bridge does not upgrade the report's trust status.

**Empirical evidence.** The calibration bridge reopens the persisted report,
recomputes and reconciles observed interval counts, checks context and lineage,
then persists typed `ir.empirical_calibration_evidence` schema `1.2` in CAS.
The evidence carries the run-bound report reference, context/provenance refs,
recomputed counts, failure codes, predictive-only authority, and explicit use
denials. Persistence requires `context_bound=True` and every failure code to be
in the producer's allowlist (`calibration_floor_not_met`,
`zero_observation_denominator`, or `nominal_confidence_only`). Persistence alone
does not mean usable calibration: a zero-denominator result is projected to a
blocked S10 status. For below-floor, context-bound evidence with a denominator,
S10 records `calibration_status: limit` and `forecast_tier: blocked`; the
association's separate `assessment` remains `limited` for every result.

**S10 consumption.** Runtime passes the persisted evidence reference through
[`RealValueOwnerGateway.produce_forecast_inputs`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/quality/generation_cycle.py#L5213)
to the S10 forecast consumer with the candidate and world-model context. S10
reopens and checks evidence authority denials, method/rule identity, time roles,
and metrics before returning a typed calibration/support projection. In this
route, S10 is recomputed in memory; the association persists the bounded S10
summary, not a separate S10 CAS artifact. Its counterfactual credibility remains
`not_established`.

**Runtime attachment.** The service persists
`runtime.predictive_calibration_association` under schema
`polisyos.runtime.predictive_calibration_association.v2` (manifest version
`2.0`). It binds the run, completed job, tenant and cell, selected input refs,
report/evidence/uncertainty refs, recomputed counts/rate, S10 summary, request
digest, and fixed authority denials. The CAS manifest repeats exact-profile
edges. The service then appends a `polisyos.runtime.diagnostic.ref_publication.v1`
event (schema `1.0`) containing the association ref and request digest while
completing the same-intent owner row in one SQL transaction. CAS persistence
precedes that SQL transaction; there is no cross-store transaction. The forecast
method is pinned by the service to
`forecasting.univariate.exponential_smoothing@1.0.0`, and the selected rule is
`rolling-origin-residual-conformal.v1` version `1.0`. These are this path's
contracts, not a universal PolicyOS artifact format.

The API response exposes the typed association and its CAS ref. A successful GET
also records a data-access audit for that association ref; it does not create a
new diagnostic or refresh the original observation source.

For the request/response contract, start with the
[Runs API reference](../reference/api/runs.md). For upstream observation and
snapshot boundaries, see [Observation contracts](observation-contracts.md) and
[Data fabric](data-fabric.md).

## Provenance, time, and authority

The run, control job, and Core attempt have distinct identifiers. The control
job's stable `run_id` becomes `control_run_id`; the indexed Core attempt has a
different run ID, and `job_id` identifies the control row. The service reads the
completed `natural_language_run` row and its persisted progress pointer, then
requires the Core run ID and selected manifest profile to match. This is a
read-and-verify binding, not a write that assigns the job to a manifest.

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

The association's output is fixed to `assessment: limited` and
`authority_scope: predictive_only`, regardless of the ForecastOwner's
`supported`/`limited`/`blocked` suitability label or S10's finite calibration
status. It forbids use for promotion, publication, policy selection, or a causal
effect claim. The S10 projection fixes counterfactual credibility to
`not_established`. A successful empirical grade is therefore a bounded
diagnostic, not authority to choose or publish a policy.

## Readback and failure behavior

The GET reader inspects at most 1,000 diagnostic events for the run/job and
refuses with `predictive_calibration_event_history_bounded` when that bound is
reached. It selects the latest association-publication event, checks event scope
and payload SHA-256, reopens the exact association profile, checks manifest
schema and input edges, binds the association to the current run and completed
job, reopens the empirical evidence, compares stored values with recomputed
evidence, and recomputes S10. The route records a read audit only after this
reopen succeeds.

The POST operation key is scoped by purpose, tenant, cell, authenticated-principal
digest, run, and intent; its body digest binds the full request and exact run
manifest profile. Identical completed retries reopen the same association,
changed bodies under the same intent conflict, and a concurrent owner receives
an in-progress conflict. [`ControlPlaneStore.complete_runtime_operation_intent`](https://github.com/DenisKopylov/polisyos/blob/bafca83bff9ff49eef1466bc491a8420b5cd1dbb/policy-engine/src/polisyos/runtime/http/services/control_plane_store.py#L5266)
couples diagnostic-event append with completion of the owner row. The CAS write
is outside that transaction, so a failed or ambiguous completion may leave an
unpublished CAS artifact. Once owner execution has started, failures require
explicit recovery; they do not trigger automatic takeover.

At the HTTP boundary, disabled surface or unavailable event log maps to `503`;
POST input/profile refusals map to `422`, while intent conflict, in-progress, and
recovery-required outcomes map to `409`. GET maps a `FileNotFoundError` escaping
the service to `404`: this includes an absent association event or missing
association, report, or empirical-evidence CAS content during reopen. Integrity,
scope, current-run-binding, and event-history refusals represented as
`PredictiveCalibrationError` map to `409`. These mappings describe the route
code, not deployment availability.

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

A later request with a new intent appends a new association; GET reads the latest
association event in the bounded run/job history. The previous association
remains in CAS as a historical artifact. The reader does re-check the old
association against the current run's selected manifest profile and root refs;
if those bindings differ, it conflicts instead of returning the old projection.
This is current-run binding, not external-source freshness: GET reopens the exact
selected CAS profiles and recomputes the diagnostic, but does not fetch a new
snapshot or replay against a changed rule, law, or world epoch. This path does not
revoke earlier records, reissue a policy claim, or update decision validity.
Rule replay and decision-validity tracking are separate mechanisms in
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
contracts can represent future routing, review, and acquisition influence while
forbidding current-claim evidence use. The predictive-calibration association
does not itself call those owners or adapt its event into a ledger entry here.

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

# DDM-15.7 Model Registry Gate

The internal registry adapter computes DDM readiness eligibility. A served
deployment owner must still provide its purpose, current observation basis and
institutional signoff; this library result does not execute a deployment.

## Wire versions and reader migration

The current producer emits `schema_version="2"` under
`https://polisyos.local/schemas/ddm_15_7/v2/model_registry_record.schema.json`.
The original closed schema and its original `$id` are preserved byte-for-byte
in `model_registry_record.v1.schema.json`. The package classification remains
`internal` (`architecture/public_surface/contract.toml`, owner `team-scientist`);
this migration grants no public or institutional authority.

| Producer record | Original strict v1 schema reader | Current Python reader | Promotion after reading |
| --- | --- | --- | --- |
| Unversioned v1 without the four source/time fields | Accepts | Accepts as version 1; serializes in original v1 form | Unestablished; rebuild from original sources to create a distinct v2 record |
| Explicit v2 | Rejects new fields and version | Accepts | No private checker authority until exact fresh rebind |
| E02 prerelease unversioned enriched record | Rejects four new fields | Rejects ordinary read; explicit `migrate_unversioned_source_record` accepts as v2 candidate | Fresh exact source rebind remains required |
| Unknown version or extra field | Rejects | Rejects | Refused |

Migration owner: `team-scientist`, DDM registry adapter/consumer owner. Upgrade
readers before enabling v2 emission in a served consumer. Keep historical bytes
and schema refs unchanged. For prerelease enriched records, explicitly produce
and persist new v2 bytes through `migrate_unversioned_source_record`; for legacy
v1, rebuild using `build_model_registry_record` and the original source context.
Never downgrade a v2 record by deleting fields to satisfy a v1 reader. A rollback
replays original historical bytes with its original reader; it does not invent
present eligibility. Release promotion and served reader selection are separate
owner decisions, not actions performed by this library patch.

The behavioral reader matrix is exercised in
`tests/unit/ddm/test_registry_schema_compatibility.py` on actual calibration and
monitor outputs, persisted/fresh reads, exact rebind, stored veto, unsupported
versions and a schema-valid forged source digest.

## Evidence inputs for a served promotion decision

The bounded library witness uses a synthetic stationary stream and an explicitly
supplied empty trigger list. Those inputs establish library consistency only.
For LA-054/LA-055, the DDM monitoring/feed owner must supply an immutable window
receipt identifying model/version, source stream/cursor, monitored interval,
delivery/completeness and label-delay policy, plus actual invalidation events
and their observation time. An empty list or `observed=True` is insufficient
institutional evidence. The registry/deployment owner must declare action and
purpose and bind a real R2 signoff to the actor, mandate, model/version, effective
period and admitted readiness/calibration refs. No boolean establishes that
authority. Freshness/allowed-age bounds require the applicable owner policy;
the library must not manufacture them.

Next owner-verifiable result: on one admitted deployment-purpose profile,
persist an observed-empty window receipt and signoff, reopen its exact source
objects, rebind and decide; repeat with unavailable feed, stale receipt,
foreign model/version, missing mandate and explicit veto. Report the library
decision separately from authorization and performed deployment. Until those
inputs and the consumer exist, feed/signoff/deployment authority is
`not_established` and LA-054/LA-055 remain limited.

## Registry fields and rules

Required registry fields:

| Field | Meaning |
| --- | --- |
| `readiness_state` | `R4`, `R3`, `R2`, `R1`, or `R0` |
| `readiness_score` | 0-100 score derived from worst active risk |
| `primary_metric_budget_used` | Current primary metric budget consumption |
| `active_calibration_id` | Calibration artifact that certified FP behavior |
| `stationarity_regime_id` | Declared regime under which FP claims are valid |
| `active_incident_id` | Linked incident or `null` |
| `promotion_allowed` | Persisted baseline permission; for R4/R3, `false` is a binding veto |
| `calibration_validity` | Optional durable projection of checker context; it is not authority by itself |
| `readiness_event_id`, `readiness_effective_at`, `readiness_expires_at` | Original readiness event and distinct readiness time roles |
| `source_binding_digest` | Digest of exact ordered source DTOs; not a self-authenticating receipt |

`calibration_validity` carries the calibration and detector identities, stationarity
regime, canonical report digest, verifier id/version, effective time, expiration,
configured and observed invalidation triggers, observation status, current status,
and checker reasons. `observation_status=unavailable` is distinct from an observed
empty trigger list. A legacy payload with no projection is
`calibration_validity_not_established`.

The projection is an inspectable persisted record, not a self-authenticating
permission. A reloaded record can become current only through
`rebind_calibration_validity` with the exact `CalibrationReport`, matching
`CalibrationAudit`, effective `now`, and observed-trigger context. The rebind
recomputes the canonical report digest and validity result, compares the
persisted report identity/digest, and emits a current projection before
attaching fresh private checker evidence. Effective time, observed triggers,
status, and reasons therefore reflect the new rebind context rather than a
stale payload. Missing context, tampered identity/digest, unavailable
observations, or a mismatch remain fail-closed; an unavailable observation
still preserves the deterministic `calibration_expired` reason when the
current time is past `valid_until`.

Promotion after reload additionally requires the original `readiness_event`,
`metric_budget`, ordered normalized `shift_events`, and enriched
`last_degradation_event`. The existing producer compares all shared calibration
and metric-policy fields, and rebind compares the full source-bound projection.
Public field mutation cannot modify the private checker projection. Legacy
records missing their source or time projection stay non-gating. Readiness
expiry is checked separately at the fresh calibration check's effective time;
an expired readiness event cannot gain a new TTL by refreshing calibration.
The same admission recomputes `budget_used` from the exact metric policy,
confidence bounds and current estimate through the existing readiness helper.
Nonfinite inputs or a different supplied quantity are not admitted; this does
not certify the calibration law or the completeness of the observation feed.

Promotion rules:

| State | Promotion |
| --- | --- |
| R4 | Allowed only when the persisted permission is `true` and checker evidence is valid |
| R3 | Allowed with investigation note only when the persisted permission is `true` and checker evidence is valid |
| R2 | Block expansion unless owner signs off |
| R1 | Block promotion |
| R0 | Block promotion and require rollback/fallback |

The evaluator treats a persisted `promotion_allowed=false` as a fail-closed
`persisted_readiness_veto` for R4 and R3. `owner_signoff` does not override
that veto in those states. The documented R2 owner-signoff exception remains
limited to R2 and does not remove the certificate or calibration-validity
checks; R1 and R0 remain blocked.

The gate must reject readiness updates that cite uncalibrated Track 2.2 shift
events. Required shift fields are `stationarity_regime_id`, `calibration_id`,
`empirical_fp_rate`, and one of `p_value`, `e_value`, or `ert`.

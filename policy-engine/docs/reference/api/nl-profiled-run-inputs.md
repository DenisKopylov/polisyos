# Selected forecast inputs for natural-language runs

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/control.py`, `src/polisyos/core/contracts/control.py`, `src/polisyos/runtime/http/services/control/run_lifecycle.py`, `src/polisyos/runtime/http/services/control/job_attempt_publication.py`, `schemas/runtime_api_v1.openapi.json`

This note supplements the [Control Plane API reference](control.md#post-apiv1controlrunsnl). The existing `POST /api/v1/control/runs/nl` route accepts an optional, source-bound input set for N4 candidate generation. Every request still requires `Idempotency-Key`; reuse it only for an exact retry of the same immutable request intent.

## Selected input bundle

A caller may omit the predictive basis fields and use the existing profileless request path. That path does not select or synthesize a value-data profile. To request a profile-backed N4 run, provide all five fields below as non-null values:

| Request field | Required selected artifact |
| --- | --- |
| `value_data_profile_ref` | `runtime.value_data_profile` |
| `value_data_unit_id` | A unit present in the selected profile |
| `model_spec_ref` | `ir.model_spec` |
| `policy_spec_ref` | `ir.policy_spec` |
| `calibration_rule_ref` | `ir.forecast_calibration_rule` |

Each artifact reference carries `artifact_id`, `kind`, `media_type`, and its exact `manifest_profile_sha256`. For this bundle the references are JSON artifacts with a selected manifest profile. `value_data_profile_ref` is resolved through the configured catalog serving source.

The same request must include `data_source.data_snapshot_ref` as a typed, profile-qualified `fabric.data_snapshot` reference, with no second data-source reference, and set `joint_interaction_candidate_intent` to `n4_unique_parent_source_members.v1`. The runtime reopens the selected CAS views, checks the profile unit and joins its declared value series to the selected snapshot before it admits the run. It attaches the selected snapshot, profile, model, policy, and calibration-rule references to the Core run input manifest before N4 execution.

A partial bundle, an explicit null for a bundle field, an untyped or wrong-kind reference, or a profile that does not join to the selected snapshot is refused with a typed `422` response. A supplied but invalid value is never treated as an omitted optional input.

## Compatibility and limits

Requests that omit the new basis fields and candidate-intent field retain the profileless request form and immutable request-intent v1 representation. A selected-basis request is captured in the v2 intent representation; stored v1 intent bytes remain readable without being rewritten. Strict Runtime API clients must be regenerated from the canonical OpenAPI schema before they consume the new request fields.

The bundle records selected inputs for a candidate run. It does not by itself establish issuer authority, external custody, production currentness, causal validity, calibration success, or publication permission. A generated model result remains a candidate until independently grounded and validated.

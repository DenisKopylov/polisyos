# E02 Persisted Artifact Compatibility and Recovery

Owner: @runtime-owners, with the owning Core, Scientist, and Data Forge teams.
Source of truth: [Predictive-calibration API](../reference/api/runs.md#predictive-calibration), [Artifact Inspection API](../reference/api/artifacts.md), [selected N4 inputs](../reference/api/nl-profiled-run-inputs.md), `src/polisyos/core/contracts/README.md`, and `src/polisyos/runtime/quality/README.md`.
Status: operator guidance for the repository source contract. It does not establish a deployed service, external owner, or current production data.

## Persisted legacy N4 outcome binding

A legacy-v2 predictive-calibration association is a persisted CAS artifact. An association without the complete current S10 owner projection is not upgraded in place. Keep its CAS bytes and event. A fresh read that returns 409 predictive_calibration_association_invalid is the expected refusal for an incomplete association.

Read the latest association using the exact owned run and the existing runs.review permission:

~~~bash
curl -sS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/runs/$RUN_ID/predictive-calibration"
~~~

If a new diagnostic is intentionally needed, use the same run-bound POST route with a complete PredictiveCalibrationRequest body, the current selected refs, and a distinct intent_id for the new immutable request. The authenticated principal must have runs.feedback.evaluate for that run. Use the request schema and input requirements in the linked API reference; do not invent replacement refs from a 409 response.

~~~bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data-binary "@$REQUEST_FILE" "http://localhost:8000/api/v1/runs/$RUN_ID/predictive-calibration"
~~~

On the first successful POST for a new intent_id, the route returns 201 and persists one new association plus one association-ref event; earlier events and CAS bytes remain unchanged. An identical retry with that completed intent_id also returns 201, returns the existing association, and persists no additional event or artifact bytes. Changing the request body or selected refs while reusing an intent_id conflicts; use a new intent_id for a distinct diagnostic. After either successful response, issue the fresh GET above. A 422 is an inadmissible input; a fresh GET 409 remains a current-binding refusal. A successful diagnostic response is candidate-only and does not establish issuer authority, source currentness, a causal effect, or publication permission.

## Persisted DataSnapshot owner-lineage schema 0.3

Do not restamp or rewrite historical DataSnapshot bytes or manifests. The Runtime owner verifier accepts exact selected Core profiles and applies owner-specific checks only for recognized source families. A generic manifest or lineage inspection shows selected bytes and edges; it does not itself establish producer ownership.

Inspect one exact artifact view with its selected manifest profile:

~~~bash
curl -sS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID?manifest_profile_sha256=$PROFILE_SHA256"
curl -sS -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/lineage?max_depth=4&max_nodes=500&manifest_profile_sha256=$PROFILE_SHA256"
~~~

Use the returned exact DataSnapshotRef in the protected consumer only as part of an intended new run. The ordinary NL consumer's selected-basis request and required companion refs are documented in [Selected forecast inputs](../reference/api/nl-profiled-run-inputs.md). That POST /api/v1/control/runs/nl performs runtime admission and may enqueue work; it is not a read-only probe. A refusal means keep the operation blocked and preserve the supplied artifact for owner diagnosis.

There is no common DataSnapshot in-place migration or generic reissue endpoint. The three 0.3 writer families emit persisted CAS artifacts: measurement-root fetch, Scientist FabricBridge tabular snapshot, and activated acquisition overlay. Obtain a replacement only through the owning producer's normal authorized workflow, then record its returned artifact ID and exact manifest-profile digest and let the intended protected consumer verify it. Do not use the policy-run /reissue action as a DataSnapshot converter, and do not treat generic artifact inspection or connector ingestion as proof that one of these owner families emitted the replacement. If the owner-specific producer workflow or source refs are unavailable, stop that replacement attempt and escalate to the corresponding owner; do not synthesize or restamp lineage.

Deploy and verify readers that recognize schema 0.3 before enabling any writer that emits it. If a required consumer cannot be confirmed compatible, hold the writer rollout. Retain 0.2 historical artifacts as written; schema version and a valid manifest alone do not prove external source truth, causal adequacy, or publication authority.

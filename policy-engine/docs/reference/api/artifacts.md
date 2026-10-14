# Artifact Inspection API

Related explanation: [Architecture](../../explanation/architecture.md).

Freshness: 2026-10-14
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/artifacts.py`, `src/polisyos/runtime/http/services/artifact_inspector.py`, `src/polisyos/runtime/http/response_policies.py`, `src/polisyos/runtime/http/routes/public_decisions.py`, `src/polisyos/runtime/http/services/public_decision_verification.py`, `src/polisyos/runtime/http/services/public_decision_verification_contracts.py`, `src/polisyos/scientist/governance/continuous/governed_public_record_contracts.py`, `src/polisyos/core/artifacts/**`, and `schemas/runtime_api_v1.openapi.json`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source and test-reference inspection only for this documentation update; the listed tests and contract check were not run.
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_artifact_inspector_api.py tests/unit/runtime/http/test_artifact_inspector_service.py tests/unit/runtime/http/test_runtime_api_authz.py`
- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

The artifact surface provides manifest, content, schema, and lineage inspection over CAS-backed runtime artifacts.

Inspection, rendering, and export describe or materialize selected stored
content. They do not prove the producer's causal claims or grant external
institutional approval to publish; each surface remains subject to its own
purpose-specific authority and custody checks.

Related L1 references:

- [CAS and Storage Reference](../operations/cas-storage.md)
- [Runtime Auth and Tenant Model](auth-tenant-model.md)
- [Runtime API Error Semantics](error-semantics.md)

## Artifact Identifier Format

Artifact endpoints expect `artifact_id` values in the form:

```text
sha256:<64-hex>
```

If parsing fails, the runtime returns:

- `400 invalid_artifact_id`

If the artifact does not exist or is not visible to the current tenant:

- `404 artifact_not_found`
- or `403` for access denial

Manifest views may share one content-addressed `artifact_id` while carrying different selected
manifest profiles. The `manifest_profile_sha256` query parameter on manifest, content, schema,
download, and artifact-specific lineage reads selects one exact view. A supplied profile that is malformed or
unavailable is rejected; it never falls back to the default manifest. Supply the selector at most
once: repeated values are ambiguous and rejected, including when the repeated values are identical.
Omitted profile selection is unqualified legacy access and makes no selected-profile claim. Content
bytes remain addressed by `artifact_id`, while the response metadata and cache identity retain the
selected profile.

For single-artifact operations that use the shared manifest resolver (manifest, predictive
diagnostic, content, lineage, schema, render, export, and download), route-specific conflicts or
refusals use `application/problem+json` and reference the strict `RuntimeApiProblem` schema. Verified CAS corruption is one such `409 artifact_integrity_failed` outcome. The `code` field identifies the reason when an operation has multiple 409 conditions. A missing artifact is
`404 artifact_not_found`. An unavailable selected profile is `404 artifact_manifest_profile_not_found`
when the store can distinguish that state. The generic `ArtifactStore` contract cannot always
distinguish an exact-only profile from the absence of a default view, so that case may still return
`404 artifact_not_found`; both outcomes remain in the 404 family. `POST /api/v1/artifacts/batch`
does not use this shared resolver and is outside the route-scoped 409 declaration.

Bureaucratic render accepts the source profile in its strict request body, and export accepts it
as a query parameter. A supplied selector is resolved exactly and may appear only once. The
response identifies the source manifest kind, media type, and profile; a missing profile never
falls back to the mutable default.

The separate quantity `LineageRef`/`/api/v1/lineage/{lineage_id}` contract is ID-only and does not
carry or infer a manifest profile. Use the artifact-specific endpoint when a selected manifest view
is required.

## Endpoint Summary

| Method | Path                                                             | Response body                         | Notes                                                                            |
| ------ | ---------------------------------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------- |
| `POST` | `/api/v1/artifacts/batch`                                        | `ArtifactBatchResponse`               | Bulk manifest lookup for dashboard/operator clients                              |
| `GET`  | `/api/v1/artifacts/{artifact_id}`                                | `ArtifactManifestResponse`            | Manifest metadata and references                                                 |
| `GET`  | `/api/v1/artifacts/{artifact_id}/content`                        | `ArtifactContentResponse`             | Content preview, text/JSON decode, or binary preview                             |
| `GET`  | `/api/v1/artifacts/{artifact_id}/predictive-coverage-diagnostic` | `PredictiveCoverageDiagnosticPreview` | Limited reader-materialized coverage projection; server gate disabled by default |
| `GET`  | `/api/v1/artifacts/{artifact_id}/lineage`                        | `ArtifactLineageResponse`             | Profile-qualified rooted lineage graph                                           |
| `GET`  | `/api/v1/artifacts/{artifact_id}/schema`                         | `ArtifactSchemaResponse`              | Schema metadata and schema ref                                                   |
| `POST` | `/api/v1/artifacts/{packet_id}/render`                           | `BureaucraticRenderResponse`          | Rendered bureaucratic document                                                   |
| `GET`  | `/api/v1/artifacts/{packet_id}/export`                           | `BureaucraticExportResponse`          | Rendered export representation                                                   |
| `GET`  | `/api/v1/artifacts/{artifact_id}/download`                       | raw bytes                             | OpenAPI-described raw download                                                   |

Committed OpenAPI status codes: `200`, `400`, `401`, `403`, `404`, `406`, `409`,
`422`, `500`. The route-scoped `409` declaration uses the same
`application/problem+json` media type and `RuntimeApiProblem` model as the runtime serializer. It
applies to the resolver-backed operations above; batch is not included.

Validation anchors:

- `tests/unit/runtime/http/test_artifact_inspector_api.py`
- `tests/unit/runtime/http/test_artifact_inspector_service.py`
- `tests/unit/runtime/http/test_runtime_api_authz.py`
- `tests/unit/runtime/http/test_runtime_api_contract_hardening.py`
- `tests/unit/runtime/http/test_public_decision_verification.py`
- `tests/unit/runtime/http/test_public_decision_verification_routes.py`

## Public Decision Verification Routes

These routes issue and verify public projections for an owned run; they are
separate from the `/api/v1/artifacts/*` inspection routes. A verified report
authenticates the retained record and its exact document bytes. It is not proof
that the underlying policy decision is admissible, currently authoritative, or
approved for publication.

### `POST /api/v1/runs/{run_id}/public-verification-record`

Issue one of the explicitly selected output classes. `publication_class` is a
query parameter and defaults to `verification_report_only`; the request body
is expected to be empty. The inspected route rejects a nonzero declared
`Content-Length`; missing-length or chunked-body rejection was not exercised
by this source review. The caller does not supply a document, signing key, or authority
verdict.

- Authorization requires `RuntimePermission.PLATFORM_ADMIN`; the pre-policy
  binder resolves `run_id` through `ResourceBindingSource.OWNED_EXISTING_PATH`
  for `runtime.run.public_verification_record`. The handler then resolves that
  run, enforces tenant access, and requires its declared decision-packet
  artifact.
- `verification_report_only` builds the redacted export from the owned packet,
  applies the public-export limits, persists and signs a verification report,
  verifies it before publishing its opaque locator, and returns
  `publication_class="verification_report_only"` with `promoted_record=null`.
- `governed_public_record_candidate` requires a configured governed owner and
  returns a prepared candidate reference, document, and digest. It does not
  issue a public record locator.
- `governed_public_record` requires the same owner, asks it to issue the record,
  and returns only after owner verification reads back a promoted record. This
  is a distinct governed-owner path; the route's report signer does not supply
  that authority. Missing owner composition fails with `503`.

### `GET /api/v1/public-decisions/verification?record_id=...`

Read an opaque issued `pvr_…` report ID, or a `gpr_…` ID when the governed
owner is composed. The no-store response separates report authentication,
cryptographic signature validity, and trusted-key status. A `pvr_` report's
`PublicDecisionVerificationResponse` fixes all seven authority dimensions to
`not_established`: `issuer_issuance`, `projection_faithfulness`,
`public_history_establishment`, `durable_verifiability`, `current_authority`,
`status_snapshot_selection`, and `public_evidence_obtainability`. Its
`promoted_record` is always null. Only a verified result exposes the bound
issuer, decision ID, issue time, digest, and public document.

The separate governed `gpr_` response may establish only
`issuer_issuance` and `projection_faithfulness` after owner verification. It
still reports `public_history_establishment`, `durable_verifiability`,
`current_authority`, `status_snapshot_selection`, and
`public_evidence_obtainability` as `not_established`. Thus a successful GET is
verification evidence for its declared class, not an admission or publication
gate for later policy use.

Source and test references above were inspected at the pinned source revision;
the listed tests and HTTP contract check were not run for this documentation
update.

## `POST /api/v1/artifacts/batch`

Return many artifact manifest views in one request so clients can avoid one-by-one metadata fetches.

- Request body: `ArtifactBatchRequest`
  - `artifact_ids`: ordered list of artifact identifiers
- Response body: `ArtifactBatchResponse`
  - `artifacts`: ordered list of `ArtifactManifestView`
  - `meta`: `ApiMeta`

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/artifacts/batch" \
  -d '{"artifact_ids":["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]}'
```

```bash
http POST :8000/api/v1/artifacts/batch \
  "Authorization:Bearer $TOKEN" \
  artifact_ids:='["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]'
```

## `GET /api/v1/artifacts/{artifact_id}`

Return the manifest view for a single artifact.

- Path parameters:
  - `artifact_id`: `sha256:<64-hex>`
- Query parameters:
  - `manifest_profile_sha256`: optional exact profile digest; when supplied, only that manifest
    profile is resolved
- Response body: `ArtifactManifestResponse`
  - `artifact`: `ArtifactManifestView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID?manifest_profile_sha256=$PROFILE_SHA256"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID \
  "Authorization:Bearer $TOKEN" \
  manifest_profile_sha256==sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

## `GET /api/v1/artifacts/{artifact_id}/content`

The optional `predictive_coverage_diagnostic` field is a reader-materialized projection.
It is emitted only when the existing `allow_candidate_predictive_diagnostic_surface`
server setting is enabled; that setting defaults to false. It does not attest the
report producer's input basis.

Return a preview of artifact content.

- Query parameters:
  - `max_bytes`: optional preview cap, `1024..2000000`
  - `manifest_profile_sha256`: optional exact profile digest
- Response body: `ArtifactContentResponse`
  - `artifact`: `ArtifactContentPreview`
- Notes:
  - JSON and text payloads are decoded where possible.
  - Binary payloads are previewed rather than fully streamed.
  - Redaction hooks may apply before content is returned.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/content?max_bytes=65536&manifest_profile_sha256=$PROFILE_SHA256"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/content \
  "Authorization:Bearer $TOKEN" \
  max_bytes==65536 \
  manifest_profile_sha256==sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

## `GET /api/v1/artifacts/{artifact_id}/predictive-coverage-diagnostic`

Return only the existing strict `PredictiveCoverageDiagnosticPreview` projection for a
selected `ir.backtest_report` 1.0 JSON manifest. The projection is recomputed by the reader
from the selected CAS bytes; it does not return raw content or a content preview. The route is
server-gated and returns `409 predictive_coverage_diagnostic_not_admitted` unless server
composition enables the internal candidate surface. This prototype does not read or verify a
governance admission record; keep the switch false unless governance explicitly approves this
disclosure. No request field, query parameter, or header enables it.

- Query parameters:
  - `manifest_profile_sha256`: optional exact manifest profile; repeated selectors are rejected
- Response body: `PredictiveCoverageDiagnosticPreview`
- Unsupported kind/schema and oversized sources return a typed `409` refusal. Malformed supported
  reports return `measurement_status=invalid_source`.
- The projection remains `assessment=limited` and marks producer attestation, S10 mapping and
  thresholds, issuer, effective time, counterfactual credibility, and causal-effect status as
  `not_established`. Omitted profile selection resolves the current default view and is not a
  producer-attestation claim.
- The existing `/content` and `/download` raw artifact gates remain in force. This route does not
  grant access to those surfaces or to promotion, publication, policy selection, or causal claims.

## `GET /api/v1/artifacts/{artifact_id}/lineage`

Build a lineage graph rooted at the artifact.

- Query parameters:
  - `max_depth`: optional depth cap, `1..256`
  - `max_nodes`: optional node cap, `1..20000`
  - `manifest_profile_sha256`: optional exact root profile digest; the returned root ref echoes
    the selected profile
- Response body: `ArtifactLineageResponse`
  - `lineage`: `ArtifactLineageView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/lineage?max_depth=4&max_nodes=500&manifest_profile_sha256=$PROFILE_SHA256"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/lineage \
  "Authorization:Bearer $TOKEN" \
  max_depth==4 max_nodes==500 \
  manifest_profile_sha256==sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

## `GET /api/v1/artifacts/{artifact_id}/schema`

Return schema metadata for the artifact.

- Query parameters:
  - `manifest_profile_sha256`: optional exact profile digest

- Response body: `ArtifactSchemaResponse`
  - `schema`: `ArtifactSchemaView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/schema"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/schema \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/artifacts/{artifact_id}/download`

Download immutable artifact bytes with explicit raw-content negotiation.

- Query parameters:
  - `manifest_profile_sha256`: optional exact manifest profile; repeated selectors are rejected
- Request headers:
  - `Accept: application/octet-stream` or the concrete artifact media type
- Response body: raw artifact bytes
- Response headers:
  - `ETag`
  - `Last-Modified`
  - `Cache-Control`
  - `Content-Disposition`
- Special error:
  - `406 artifact_representation_not_acceptable` when the `Accept` header does
    not allow the raw representation

```bash
curl -L \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/octet-stream" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/download?manifest_profile_sha256=$PROFILE_SHA256" \
  -o artifact.bin
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/download \
  "Authorization:Bearer $TOKEN" \
  Accept:application/octet-stream \
  manifest_profile_sha256==sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --download
```

## Typical Inspection Flow

1. Read `/api/v1/artifacts/{artifact_id}` to identify kind, media type, and schema hints.
2. Read `/content` to preview the materialized payload.
3. Read `/schema` when the artifact points to a JSON schema or ABI contract.
4. Read `/lineage` to understand upstream sources, derived artifacts, and downstream dependents.
5. Read `/download` only when the client needs raw immutable bytes.

Selected manifest profiles are exact views of a CAS artifact. A request that
supplies `manifest_profile_sha256` is immutable-cacheable; a request that omits
it resolves the current default view and must revalidate. The resolved profile is
returned and carried by artifact links. Authority admission resolves the same
selected manifest view used by the route before reading its envelope.

A selected manifest envelope is checked together with any authority boundary in
the artifact payload. Both constraints must permit the requested surface purpose;
the payload cannot weaken a selected manifest restriction, and the manifest
cannot upgrade a stricter payload boundary. Render and export apply the selected
manifest view before and after producing their response.

When a composed authority decision is returned with a refusal, its
`authority_contributors` rows preserve the evaluated `base_surface` and
`selected_manifest` decisions, including each boundary reference, reason,
restriction list, and any selected-envelope resolution error. If an authority
evaluation supplies the final reason, the top-level boundary fields describe that
contributor; if a different gate takes precedence, they retain the base-surface
decision. `may_not_use_for` is the stable union of restrictions from every
evaluated contributor. These fields explain the existing conjunctive decision
and do not grant authority to either source. The `selected_manifest` basis means
the route-resolved view; when the request omits a profile, that is the current
default view and does not attest which profile a producer selected. The selected
manifest contributor is omitted when that view has no linked authority
envelope.

## Composed authority-purpose checks

The route checks compose by effective purpose; every check in the path must allow
its purpose. The HTTP route matrix follows the current route/service call chain:

| Route representation                      | Ordered effective-purpose checks                                             |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| `GET /{artifact_id}` manifest             | `runtime_closeout_authority` (route and inspector), then `dashboard_display` |
| `GET /{artifact_id}/content` JSON preview | `runtime_closeout_authority` (route and inspector), then `dashboard_display` |
| `GET /{artifact_id}/content` raw bytes    | `runtime_closeout_authority` (route, inspector, and raw-response branch)     |
| `GET /{artifact_id}/lineage`              | `runtime_closeout_authority` (inspector, lineage service, and route)         |
| `GET /{artifact_id}/schema`               | `runtime_closeout_authority` (schema inspector), then `dashboard_display`    |
| `GET /{artifact_id}/download`             | `runtime_closeout_authority` (raw admission checks)                          |
| `POST /{artifact_id}/render`              | `dashboard_display` before and after rendering                               |
| `GET /{artifact_id}/export`               | `publication` before and after export                                        |

This table records existing gates; it does not change their purposes or introduce a
new grant. A runtime-purpose refusal blocks the schema inspector before the
separate dashboard route check, while render and export use their existing
route-level dashboard and publication checks. Raw content is admitted before its
conditional-response handling, so an authority refusal is not converted into a
`304` response.

### Writer-selected manifest profiles

`put_bytes()` and `put_json()` keep their historical ID/default-view result by default. A producer that must retain the exact manifest selected by its own write can pass the strict `return_selected_profile=True` keyword. The returned profile is computed inside the write operation and selects that immutable sidecar after later sibling writes. Stores that do not implement this result capability refuse; they do not synthesize the profile from a later default-manifest read.

An opted-in store must accept `return_selected_profile` as an explicit keyword parameter. Positional-only and variadic catch-all signatures are refused before a write; a parameter name alone does not establish this capability.

## Selected canonical-profile verification

Semantic JSON reads resolve the selected manifest sidecar and validate its raw
`canon` profile before consuming the artifact bytes. When the profile is
present, Core decodes and re-encodes those same selected bytes with the declared
settings. A malformed/incomplete/unsupported declaration or a byte mismatch
returns HTTP `409` with a typed `canon_profile_*` refusal; it is not treated as a
missing profile and reader defaults are not substituted. The response models
for predictive-coverage diagnostics, JSON content previews, and schema views
include `canon_read_status` (`declared_bytes_conformant`,
`profile_absent_unqualified_candidate`, `declared_unknown_candidate`, `not_evaluated`, or `not_applicable`).

Core semantic reads refuse an absent profile by default. A caller that explicitly
opts into candidate-only compatibility receives `profile_absent_unqualified_candidate`;
that status is `not_established` for historical eligibility and producer intent, and
its decoded value cannot enter authority, promotion, or issuer consumers. No source
currently supplies the original proof needed to authorize a historical profileless
semantic read. Raw content
negotiation continues to serve the exact selected bytes through its existing
raw-response and authority gates without decoding them. Render and export
materialize the selected semantic view and retain its `canon_read_status` in the
HTML response metadata and PDF/DOCX output packet. Predictive diagnostic
reports are likewise reader-materialized and never raw-byte responses.

## Typed refusal for malformed selected profiles

The manifest and semantic JSON surfaces validate the raw selected sidecar before typed
manifest admission. If a present `canon` profile is malformed, incomplete, unsupported,
or inconsistent with the selected payload bytes, the operation returns HTTP 409 as
`application/problem+json` with the `RuntimeApiProblem` schema. Default semantic reads
refuse absence. Only an explicit candidate-only call can inspect profileless bytes, and
that result neither proves historical eligibility nor attests the producer. The API
documents the refusal only on operations that execute these selected semantic reads.
Binary/raw-content responses continue to preserve the selected payload bytes.

Artifact-inspector semantic views keep profile refusals typed across the whole service family: malformed, unsupported, default-absent, or nonconformant JSON is not returned as text, an empty schema, or an invalid-source diagnostic. Explicit raw content and download responses retain the exact selected bytes under their existing ownership and integrity checks. An application/octet-stream preview remains binary even when its bytes happen to be valid UTF-8; UTF-8 text rendering is limited to text media types.

Predictive coverage diagnostics enforce the source-byte limit on the exact selected payload before Core canonical decoding. Manifest byte-size metadata is a preliminary hint; the decision uses the retrieved content length. Oversized inputs remain refused without semantic parsing.

JSON content previews enforce the normalized preview byte limit against the exact selected payload before Core decoding; manifest byte_size is only a hint. The predictive-coverage diagnostic uses its existing 2,000,000-byte source limit. Schema-view top-level-key inspection has no existing payload cap and remains explicitly uncapped; this change does not claim that route is resource-bounded. Oversized JSON previews remain truncated binary previews without semantic parsing.

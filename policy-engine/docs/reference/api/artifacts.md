# Artifact Inspection API
Related explanation: [Architecture](../../explanation/architecture.md).

The artifact surface provides manifest, content, schema, and lineage inspection over CAS-backed runtime artifacts.

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

## Endpoint Summary

| Method | Path | Response body | Notes |
|--------|------|---------------|-------|
| `GET` | `/api/v1/artifacts/{artifact_id}` | `ArtifactManifestResponse` | Manifest metadata and references |
| `GET` | `/api/v1/artifacts/{artifact_id}/content` | `ArtifactContentResponse` | Content preview, text/JSON decode, or binary preview |
| `GET` | `/api/v1/artifacts/{artifact_id}/lineage` | `ArtifactLineageResponse` | Rooted lineage graph |
| `GET` | `/api/v1/artifacts/{artifact_id}/schema` | `ArtifactSchemaResponse` | Schema metadata and schema ref |

Committed OpenAPI status codes: `200`, `400`, `401`, `403`, `404`, `422`, `500`.

## `GET /api/v1/artifacts/{artifact_id}`

Return the manifest view for a single artifact.

- Path parameters:
  - `artifact_id`: `sha256:<64-hex>`
- Response body: `ArtifactManifestResponse`
  - `artifact`: `ArtifactManifestView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/artifacts/{artifact_id}/content`

Return a preview of artifact content.

- Query parameters:
  - `max_bytes`: optional preview cap, `1024..2000000`
- Response body: `ArtifactContentResponse`
  - `artifact`: `ArtifactContentPreview`
- Notes:
  - JSON and text payloads are decoded where possible.
  - Binary payloads are previewed rather than fully streamed.
  - Redaction hooks may apply before content is returned.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/content?max_bytes=65536"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/content \
  "Authorization:Bearer $TOKEN" \
  max_bytes==65536
```

## `GET /api/v1/artifacts/{artifact_id}/lineage`

Build a lineage graph rooted at the artifact.

- Query parameters:
  - `max_depth`: optional depth cap, `1..256`
  - `max_nodes`: optional node cap, `1..20000`
- Response body: `ArtifactLineageResponse`
  - `lineage`: `ArtifactLineageView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/artifacts/$ARTIFACT_ID/lineage?max_depth=4&max_nodes=500"
```

```bash
http GET :8000/api/v1/artifacts/$ARTIFACT_ID/lineage \
  "Authorization:Bearer $TOKEN" \
  max_depth==4 max_nodes==500
```

## `GET /api/v1/artifacts/{artifact_id}/schema`

Return schema metadata for the artifact.

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

## Typical Inspection Flow

1. Read `/api/v1/artifacts/{artifact_id}` to identify kind, media type, and schema hints.
2. Read `/content` to preview the materialized payload.
3. Read `/schema` when the artifact points to a JSON schema or ABI contract.
4. Read `/lineage` to understand upstream sources, derived artifacts, and downstream dependents.

# Runtime Bureaucratic Rendering

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/artifacts.py`, `src/polisyos/runtime/http/services/bureaucratic_rendering.py`, `packages/runtime-api-client/`, `apps/runtime-dashboard/src/features/artifacts/bureaucratic/`, and `tests/unit/runtime/http/test_bureaucratic_rendering_api.py`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source and test-reference inspection only for this documentation update; the tests and HTTP routes were not run.

The current artifact routes map a selected decision-packet artifact to a
canonical document AST, then render HTML/PDF/DOCX from that same source.

## Render

```http
POST /api/v1/artifacts/{packet_id}/render
```

```json
{
  "genre": "postanova_kmu",
  "jurisdiction": "ua",
  "template_version": "ua.kmu.postanova.v1",
  "temporal_scope": {
    "valid_at": "2026-02-11T12:00:00Z",
    "tx_at": "2026-02-11T12:05:00Z"
  },
  "trust_view": false
}
```

The response contains `document: BureaucraticDocument`. The AST is canonical:
React components, print preview and export helpers consume the same blocks.

## Export

```http
GET /api/v1/artifacts/{packet_id}/export?format=html&genre=expert_vysnovok
```

The response is a deterministic export source packet with:

- `content_type`
- `filename`
- `content`
- `metadata.watermark`
- `metadata.template_id`
- `metadata.packet_hash`

Frontend PDF uses the browser print pipeline from the same AST to preserve HTML
semantics and preview parity.

## Document AST

Each block includes:

- stable `id`
- `kind`
- optional `number`
- text/items/children
- optional `QuantityValue`
- `epistemic_origin`
- `authorship`
- compact provenance and raw source refs

## Compliance Gates

- Watermark is mandatory in preview and export metadata.
- Official signatures and seals are placeholders only.
- All decision numbers must remain `QuantityValue`.
- Legal/document specialist review is required before template approval changes
  from `pending_external_review` to `approved`.

Rendered content and watermarks describe a draft representation; they do not
create an official signature, legal approval, or publication authority. Route
tests cover the implemented AST/export contract, not an external institution's
review or signature.

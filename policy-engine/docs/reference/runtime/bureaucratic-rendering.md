# Runtime Bureaucratic Rendering

Phase 2.5 adds a renderer that maps a decision packet artifact to a canonical
document AST, then renders HTML/PDF/DOCX from that same source.

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

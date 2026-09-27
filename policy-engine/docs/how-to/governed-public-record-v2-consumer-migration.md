# Consume governed public records v2

Governed public-record issuance now defaults to the paired v2 document/profile and signed-record schema/rule. The HTTP routes and artifact ID wire format have not changed. Consumers that use the governed response must read its declared versions before interpreting evidence references.

## Read the version pair

Accept a governed document only when its `schema_version` and `profile` form a supported pair, and a promoted record only when its `schema_version` and `rule_version` form the corresponding pair. Require the document and record to agree on v1 or v2. Reject a mixed pair, an unknown version, or a missing required field as an unsupported response. The runtime dashboard's response validator is a concrete consumer of this rule; the generated OpenAPI type union alone is insufficient.

The v1 owner projection emits selector-free public evidence references. The dashboard's v1 JSON parser does not independently reject a nested selector, so do not infer that property from a successfully parsed v1 response. Historical v1 signed-byte replay is not established by this migration.

## Preserve the selected view

In v2, an evidence reference may carry both `artifact_id` and `manifest_profile_sha256`. Preserve both keys and their JSON relationships; do not deduplicate references by `artifact_id` alone. One blob can have several typed manifest views. In a public document the selected-profile value is relocated to a `gph_...` **opaque handle**. It is not a CAS address, a digest that a public consumer can recompute, or an evidence retrieval URL. The owner keeps the private binding and verifies it before issuance. A displayed handle does not itself establish evidence truth or public obtainability.

## Regenerate the typed consumers

From `policy-engine/`, use the registered owners in this order, inspecting each generated diff before continuing:

```sh
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-api-client run generate -- --openapi schemas/runtime_api_v1.openapi.json
corepack pnpm --filter @polisyos/runtime-dashboard run generate:api -- --openapi schemas/runtime_api_v1.openapi.json
```

The outputs are `schemas/runtime_api_v1.openapi.json`, the package-owned runtime client types and canonical client, and `apps/runtime-dashboard/src/api/types.ts`. Do not hand-edit them. Validate the result with the runtime API contract check, the client and dashboard typechecks, the dashboard contract check, and behavioral issuance/readback and viewer tests. The OpenAPI schema describes the record version union; `public_document` remains recursive JSON, so only the owner and consumer behavioral tests establish the nested selected-view rule.

This migration establishes the current v2 response contract and consumer handling. It does not claim historical v1 signed-byte replay, source evidence obtainability, or institutional authority.
